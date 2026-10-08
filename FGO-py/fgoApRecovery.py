"""CN recovery: bounded, positively identified, at most one selection/confirmation."""
from dataclasses import dataclass
import re
import cv2,numpy
from fgoDetect import OCR
from fgoSchedule import ScriptStop
from fgoLogging import getLogger
from fgoBattleFlow import BattleFlowState as S

logger=getLogger('APRecovery')
FORBIDDEN='CN自动恢复禁止使用此资源；圣晶石自动消费被硬禁'
UNVERIFIED='AP恢复未获得正向确认；未重复消费资源'
RESOURCES=('gold','silver','bronze','copper')
RESOURCE_LABELS=('黄金果实','白银果实','青铜果实','赤铜果实')
_uncertainDevices=set()

def ensureNotUncertain(device):
    if id(device) in _uncertainDevices:raise ScriptStop(UNVERIFIED)

@dataclass(frozen=True)
class RecoveryConfirmation:
    resource:int
    button:tuple

def validateResourceCN(kind):
    if kind not in range(4):raise ScriptStop(FORBIDDEN)

def label(d,rect):
    text,score=OCR.ZHS.ocr_single_line(d._crop(rect))
    return re.sub(r'\s+','',str(text)) if float(score)>=.85 else ''

def isResourceSelector(d):
    return (d.isApEmpty() and label(d,(520,32,770,72))=='行动力回复'
        and label(d,(520,67,780,100))=='消耗道具回复行动力'
        and label(d,(575,588,707,645))=='关闭')

def resourceTarget(d,kind):
    validateResourceCN(kind)
    if not isResourceSelector(d):return None
    # OCR proposes only a resource name inside the observed list. Independent
    # native/2x reads and a positive held-count confirm the actionable row.
    proposals=[]
    for span in OCR.ZHS.detect_and_ocr(d._crop((440,110,985,575)),drop_score=.85):
        if str(span.text).strip()!=RESOURCE_LABELS[kind]:continue
        points=numpy.asarray(span.box).reshape(-1,2)
        x0,y0=points.min(axis=0)+[440,110];x1,y1=points.max(axis=0)+[440,110]
        if not (440<=x0<x1<=710 and 115<=y0<y1<=510):continue
        rect=(max(440,int(x0)-8),int(y0)-5,min(710,int(x1)+12),int(y1)+6)
        line=d._crop(rect)
        reads=[OCR.ZHS.ocr_single_line(line),OCR.ZHS.ocr_single_line(cv2.resize(line,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC))]
        if not all(float(score)>=.85 and re.sub(r'\s+','',str(text))==RESOURCE_LABELS[kind] for text,score in reads):continue
        held=label(d,(785,int(y0)-7,980,int(y1)+9))
        match=re.fullmatch(r'([0-9,]+)个持有',held)
        if match and int(match[1].replace(',',''))>0:proposals.append((650,int((y0+y1)/2)+40))
    return proposals[0] if len(proposals)==1 else None

def confirmation(d,kind):
    # Populated only from the real current confirmation UI; unknown dialogs
    # cannot authorize spending. The selector and AP-full notice are not it.
    return None

def safeAp(d):
    # Support/formation layouts can contain unrelated fractions. Only read
    # AP when its own fixed caption is positively visible. Otherwise unknown.
    if label(d,(180,660,237,688))!='行动力':return None
    try:return d.getAp()
    except ScriptStop:return None

def restoreApCN(main,flow,device):
    validateResourceCN(main.appleKind)
    ensureNotUncertain(device)
    if main.appleTotal<=0:return False
    if getattr(main,'_cnApRecoveryPending',False):raise ScriptStop(UNVERIFIED)
    kind=main.appleKind;budget=main.appleTotal
    end=min(flow.clock()+35,flow.deadline if flow.deadline is not None else float('inf'))
    def wait(predicate,timeout):
        limit=min(end,flow.clock()+timeout)
        while flow.clock()<limit:
            flow.observe()
            if flow.clock()>=limit:break
            result=predicate(flow.detect)
            if result:return result
            flow.schedule.sleep(flow.poll)
        raise ScriptStop(UNVERIFIED)
    flow.observe()
    if flow.observation.state!=S.AP_EMPTY or not isResourceSelector(flow.detect):raise ScriptStop(UNVERIFIED)
    before=safeAp(flow.detect)
    target=resourceTarget(flow.detect,kind)
    for attempt in range(2):
        if target is not None:break
        if flow.clock()>=end or not isResourceSelector(flow.detect):raise ScriptStop(UNVERIFIED)
        begin,endPoint=((650,470),(650,240)) if kind>=2 else ((650,240),(650,470))
        flow.action('ap_resource_scroll',lambda:device.swipe(begin,endPoint))
        flow.observe();target=resourceTarget(flow.detect,kind)
    if target is None:raise ScriptStop('未正向确认指定AP恢复资源；未选择资源')
    # A second fresh frame must identify the same resource row before input.
    flow.observe()
    repeated=resourceTarget(flow.detect,kind)
    if repeated is None or max(abs(a-b) for a,b in zip(repeated,target))>3:raise ScriptStop('AP恢复资源位置不稳定；未选择资源')
    main._cnApRecoveryPending=True
    _uncertainDevices.add(id(device))
    flow.action('ap_select_'+RESOURCES[kind],lambda:device.touch(target,duration=.08))
    confirmed=wait(lambda d:confirmation(d,kind),10)
    flow.observe()
    stable=confirmation(flow.detect,kind)
    if stable!=confirmed:raise ScriptStop(UNVERIFIED)
    flow.action('ap_confirm_'+RESOURCES[kind],lambda:device.touch(confirmed.button,duration=.08))
    def success(d):
        if d.isApEmpty() or confirmation(d,kind):return False
        state=flow.observation.state
        after=safeAp(d)
        if state in {S.FRIEND,S.FRIEND_EMPTY,S.FORMATION}:return (True,after)
        if state==S.QUEST_READY and before is not None and after is not None and after>before:return (True,after)
        return False
    _,after=wait(success,20)
    main.appleTotal=budget-1
    main._cnApRecoveryPending=False
    _uncertainDevices.discard(id(device))
    main.apRecoveryLog=getattr(main,'apRecoveryLog',[])+[dict(resource=RESOURCES[kind],beforeAP=before,afterAP=after,budgetBefore=budget,budgetAfter=main.appleTotal,verified=True)]
    logger.warning('[APRecovery] resource=%s beforeAP=%s afterAP=%s budget=%d->%d verified=True',RESOURCES[kind],before if before is not None else 'unknown',after if after is not None else 'unknown',budget,main.appleTotal)
    return True

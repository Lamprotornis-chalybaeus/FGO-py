"""Opt-in CN event progression; private ledger and shared BattleCycle.

The conservative GUI API does not grant resource permission. Callers must
explicitly supply EventResourcePolicy to enable this development runner.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib,json,re,time

import fgoDevice
import fgoEventProgress as event
import fgoKernel as kernel
import fgoNavigation as nav
import fgoQuickQuest as daily
from fgoAutomation import automationOwner,INPUT_OBSERVER
from fgoBattleFlow import BattleCycle,BattleFlowState as S,FlowTimeout,FriendSelectionResult
from fgoDetect import Detect,XDetect,OCR
from fgoPaths import paths
from fgoSchedule import ScriptStop,schedule

class EventCaptureError(ScriptStop):
    """Lost capture transport stops this run; it never authorizes recovery input."""


@dataclass(frozen=True)
class EventResourcePolicy:
    allowApples:bool=True
    allowQuartz:bool=False
    allowTemporaryAutoFormation:bool=False
    def __post_init__(self):
        if self.allowQuartz:raise ValueError('Event QuartzGuard cannot be disabled')


class QuartzGuard:
    """Resource dialogs fail closed, including mixed apple/quartz selectors."""
    quartz=('圣晶石','saintquartz','石头恢复')
    apples=('黄金果实','白银果实','赤铜果实','青铜果实','金苹果','银苹果','铜苹果','蓝苹果')
    @staticmethod
    def text(items):return ' '.join(event._text(i) for i in items)
    @classmethod
    def resourceContext(cls,items):
        text=cls.text(items)
        return any(v in text for v in ('恢复ap','回复ap','ap恢复','ap回复','ap不足','复活','继续战斗','购买','是否使用','是否消耗','是否恢复','是否回复','消耗圣晶石'))
    @classmethod
    def check(cls,items,*,appleOption=None,appleConfirm=False,dismissNotice=False):
        if dismissNotice:
            if not (loginRewardInfoClose(items) or promotionalInfoClose(items)):
                raise ScriptStop('Unverified informational close')
            return
        text=cls.text(items)
        if any(v in text for v in ('请选择奖励','奖励选择','选择奖励','二选一','任选')):
            raise ScriptStop('Event reward choice: no automatic selection')
        if not cls.resourceContext(items):return
        if appleOption is not None:
            # Only a positively identified apple label may be selected from a
            # mixed selector. Confirmations are never treated as selectors.
            if appleConfirm or event._text(appleOption) not in cls.apples:
                raise ScriptStop('Unverified apple option')
            if any(v in text for v in ('是否使用','是否消耗','复活','购买')):
                raise ScriptStop('Resource confirmation is not an apple selector')
            return
        if any(v in text for v in cls.quartz):
            raise ScriptStop('QuartzGuard: quartz consumption forbidden')
        if not appleConfirm or not any(v in text for v in cls.apples):
            raise ScriptStop('Unverified resource confirmation')
        if any(v in text for v in ('复活','购买')):
            raise ScriptStop('Resource action outside AP apple policy')


@dataclass(frozen=True)
class MissionRequirement:
    mission:str
    kind:str
    target:str
    count:int
    @classmethod
    def parse(cls,text):
        # No inferred enemy inventory: this records an explicit requirement,
        # not permission to choose an arbitrary Free Quest.
        match=re.search(r'(?:任务|Mission)\s*(\d+).*?(击败|收集|通关)\s*(\d+)\s*(?:个|次|名)?\s*(.+)',text,re.I)
        return cls(match[1],match[2],match[4].strip(),int(match[3])) if match else None


class ProgressLedger:
    def __init__(self,path):
        self.path=Path(path)
        self.data=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {'version':1,'records':[]}
        if self.data.get('version')!=1 or not isinstance(self.data.get('records'),list):
            raise ValueError('Invalid local event ledger')
    def append(self,kind,**fields):
        row={'time':time.time(),'kind':kind,**fields}
        self.data['records'].append(row)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.data,ensure_ascii=False,indent=2),encoding='utf-8')
        # Windows scanners can briefly hold the destination after a write.
        # Retry only the atomic file operation; never replay a game input.
        for attempt in range(5):
            try:
                tmp.replace(self.path)
                break
            except PermissionError:
                if attempt==4:raise
                time.sleep(.05*(2**attempt))
        return row


def announcementClose(d,items):
    """Observed CN bulletin: independent title and close glyph, two scales."""
    import cv2
    titles=[i for i in items if event._reliable(i) and event._text(i)=='游戏公告' and 450<i.center[0]<800 and i.center[1]<95]
    closes=[i for i in items if event._text(i)=='x' and i.score>=.65 and 1200<i.center[0]<1280 and i.center[1]<75]
    if len(titles)!=1 or len(closes)!=1 or event._unsafeEventOverlay(items):return None
    for label,ocr,expected in ((titles[0],OCR.ZHS,'游戏公告'),(closes[0],OCR.EN,'x')):
        crop=d._crop(label.box)
        a,sa=ocr.ocr_single_line(crop);b,sb=ocr.ocr_single_line(cv2.resize(crop,None,fx=2,fy=2))
        if not min(float(sa),float(sb))>=.85 or event.normalizeText(a)!=expected or event.normalizeText(b)!=expected:return None
    return closes[0].center


def loginRewardInfoClose(items):
    """Dismiss an already-awarded notice, never claim from the gift box."""
    positive=[i for i in items if i.score>=.85]
    headers=[i for i in positive if event._text(i) in ('连续登录奖励','开幕纪念登录奖励') and 400<i.center[0]<850 and 90<i.center[1]<180]
    instruction=[i for i in positive if '请在礼物盒中领取' in event._text(i)]
    awarded=[i for i in positive if re.fullmatch(r'(?:获得了第\d+日|已获得第\d+次)的登录奖励[!！]?',event._text(i))]
    closes=[i for i in positive if event._text(i)=='关闭' and 480<i.center[0]<800 and 520<i.center[1]<620]
    return closes[0].center if len(headers)==len(instruction)==len(awarded)==len(closes)==1 and not event._unsafeEventOverlay(items) else None


def promotionalInfoClose(items):
    """The observed campaign information panel, not its exchange shop."""
    positive=[i for i in items if i.score>=.85]
    title=[i for i in positive if '纪念活动' in event._text(i) and 90<i.center[1]<155]
    ongoing=[i for i in positive if event._text(i) in ('举办中!','举办中！') and 130<i.center[1]<190]
    date=[i for i in positive if '举办时间:' in event._text(i) and re.search(r'20\d\d年\d+月\d+日',event._text(i)) and 475<i.center[1]<530]
    closes=[i for i in positive if event._text(i)=='关闭' and 480<i.center[0]<800 and 520<i.center[1]<620]
    controls=[i for i in positive if event._text(i) in ('兑换','确定','确认','开始','领取','领取奖励','取消')]
    return closes[0].center if len(title)==len(ongoing)==len(date)==len(closes)==1 and not controls else None


def guideInfoClose(d,items):
    import cv2
    if event._unsafeEventOverlay(items):return None
    for text,(lo,hi) in (('游玩指引',(150,220)),('最新情报',(220,295)),('查找攻略',(295,370))):
        matches=[i for i in items if i.score>=.85 and event._text(i)==text and i.center[0]<180 and lo<i.center[1]<hi]
        if len(matches)!=1:return None
    if not any(i.score>=.85 and event._text(i)=='本月不再提示' and i.center[0]<200 and i.center[1]>630 for i in items):return None
    rect=(1219,7,1273,61);crop=d._crop(rect)
    a,sa=OCR.EN.ocr_single_line(crop);b,sb=OCR.EN.ocr_single_line(cv2.resize(crop,None,fx=2,fy=2))
    if min(float(sa),float(sb))>=.85 and event.normalizeText(a)==event.normalizeText(b)=='x':return (1246,34)
    return None


def weeklyUpdateInfoClose(items):
    positive=[i for i in items if i.score>=.85]
    updated=[i for i in positive if event._text(i).rstrip('。.!！')=='御主任务已更新' and 200<i.center[1]<360]
    description=[i for i in positive if event._text(i).rstrip('。.!！')=='来挑战最新的御主任务吧' and 250<i.center[1]<400]
    entry=[i for i in positive if event._text(i)=='前往御主任务界面' and 650<i.center[0]<1030 and 520<i.center[1]<620]
    close=[i for i in positive if event._text(i)=='关闭' and 300<i.center[0]<600 and 520<i.center[1]<620]
    return close[0].center if len(updated)==len(description)==len(entry)==len(close)==1 and not event._unsafeEventOverlay(items) else None


def startupInfoClose(d,items):
    return announcementClose(d,items) or loginRewardInfoClose(items) or promotionalInfoClose(items) or guideInfoClose(d,items) or weeklyUpdateInfoClose(items)


def startupNoticeKey(items):
    # Fixed information headings only. No account, servant or reward identity.
    for text in ('游戏公告','连续登录奖励','开幕纪念登录奖励','游玩指引','御主任务已更新。'):
        if any(i.score>=.85 and event._text(i)==text for i in items):return text
    titles=[event._text(i) for i in items if i.score>=.85 and '纪念活动' in event._text(i) and 90<i.center[1]<155]
    return titles[0] if len(titles)==1 else None


def storyItems(d,items):
    """Observed arrow contaminates full-screen 跳过 OCR; verify text only."""
    import cv2
    weak=[i for i in items if '跳过' in event._text(i) and 1100<i.center[0]<1280 and i.center[1]<100]
    auto=[i for i in items if i.score>=.85 and event._text(i)=='自动' and i.center[0]>1180 and i.center[1]>600]
    dialogue=[i for i in items if i.score>=.85 and 570<i.center[1]<680 and i.center[0]<1100 and len(event._text(i))>=4]
    # Full-screen OCR may omit the arrow-contaminated label altogether. The
    # two fixed text reads plus independent dialogue/auto controls produce it.
    if len(weak)>1 or len(auto)>1 or not dialogue:return items
    if not auto:
        line=d._crop((1208,621,1244,647))
        a,sa=OCR.ZHS.ocr_single_line(line);b,sb=OCR.ZHS.ocr_single_line(cv2.resize(line,None,fx=2,fy=2))
        if not min(float(sa),float(sb))>=.85 or event.normalizeText(a)!='自动' or event.normalizeText(b)!='自动':return items
    line=d._crop((1160,20,1225,60))
    a,sa=OCR.ZHS.ocr_single_line(line);b,sb=OCR.ZHS.ocr_single_line(cv2.resize(line,None,fx=2,fy=2))
    if not min(float(sa),float(sb))>=.85:return items
    if event.normalizeText(a)!='跳过' or event.normalizeText(b)!='跳过':return items
    return [i for i in items if not weak or i is not weak[0]]+[event.OcrItem('跳过',(1160,20,1225,60),min(float(sa),float(sb)))]

def worldMapItems(d,items):
    # The observed yellow arrow caused full-screen OCR to omit 下一个.
    # Read the text above a visible area plaque at two scales, never infer a
    # main quest from the plaque alone. Other layouts safely remain unlocated.
    if not d.isMainInterface() or not event.eventWorldMapControls(items):return items
    if any(event._text(i)=='下一个' for i in items):return items
    import cv2
    markers=[]
    for area in items:
        x,y=event._center(area)
        if area.score<.85 or not 300<y<520 or not 200<x<1080 or not 2<=len(event._text(area))<=12:continue
        # The yellow marker bounces vertically. These bounded text bands
        # cover its observed range; every candidate still needs two reads.
        for offset in (233,243,223,253,213):
            rect=(x-55,y-offset,x+59,y-offset+46)
            crop=d._crop(rect)
            a,sa=OCR.ZHS.ocr_single_line(crop);b,sb=OCR.ZHS.ocr_single_line(cv2.resize(crop,None,fx=2,fy=2))
            if min(float(sa),float(sb))>=.85 and event.normalizeText(a)==event.normalizeText(b)=='下一个':
                markers.append(event.OcrItem('下一个',rect,min(float(sa),float(sb))));break
    return items+markers

def mainTitleItems(d,items):
    """Decorated first-area card: verify its title text without the arrow."""
    if not any(i.score>=.85 and '关卡举办时间' in event._text(i) for i in items):return items
    import cv2
    result=list(items)
    for i in items:
        if not event._isMainTitle(i.text) or not 750<i.center[0]<1120 or not 100<i.center[1]<250:continue
        # Observed first row text band; fixed card origin, variable text width.
        rect=(775,i.center[1]-16,min(1080,max(1000,i.box[2]+30)),i.center[1]+16)
        crop=d._crop(rect);a,sa=OCR.ZHS.ocr_single_line(crop);b,sb=OCR.ZHS.ocr_single_line(cv2.resize(crop,None,fx=2,fy=2))
        if min(float(sa),float(sb))>=.85 and event.normalizeText(a)==event.normalizeText(b) and event._isMainTitle(a):
            result.remove(i);result.append(event.OcrItem(a,rect,min(float(sa),float(sb))))
    return result

def startConfirmationItems(d,items):
    # Actual story-only start modal has a weak cancel glyph in whole-frame OCR.
    message=[i for i in items if i.score>=.85 and event._text(i).rstrip('?？')=='是否开始任务' and 450<i.center[1]<530]
    story=[i for i in items if i.score>=.85 and event._text(i)=='该任务没有战斗' and 250<i.center[1]<380]
    cancel=[i for i in items if event._text(i)=='取消' and 300<i.center[0]<600 and 530<i.center[1]<620]
    if len(message)!=1 or len(story)!=1 or len(cancel)>1:return items
    import cv2
    rect=(404,540,489,588);crop=d._crop(rect)
    a,sa=OCR.ZHS.ocr_single_line(crop);b,sb=OCR.ZHS.ocr_single_line(cv2.resize(crop,None,fx=2,fy=2))
    if min(float(sa),float(sb))<.85 or event.normalizeText(a)!=event.normalizeText(b) or event.normalizeText(a)!='取消':return items
    return [i for i in items if not cancel or i is not cancel[0]]+[event.OcrItem('取消',rect,min(float(sa),float(sb)))]

def itemReceiptItems(d,items):
    kind=[i for i in items if i.score>=.85 and event._text(i)=='概念礼装' and 570<i.center[0]<720 and 580<i.center[1]<650]
    health=[i for i in items if i.score>=.85 and event._text(i)=='生命值' and 700<i.center[0]<830 and 580<i.center[1]<650]
    value=[i for i in items if i.score>=.85 and re.fullmatch(r'(?:\+\d+|0)',event._text(i)) and 450<i.center[0]<600 and 625<i.center[1]<675]
    if len(kind)!=1:return servantReceiptItems(d,items)
    if len(health)>1 or len(value)>1:return items
    import cv2
    if not health:
        rect=(745,600,805,634);crop=d._crop(rect)
        a,sa=OCR.ZHS.ocr_single_line(crop);b,sb=OCR.ZHS.ocr_single_line(cv2.resize(crop,None,fx=2,fy=2))
        if min(float(sa),float(sb))<.85 or event.normalizeText(a)!=event.normalizeText(b) or event.normalizeText(a)!='生命值':return items
        items=items+[event.OcrItem('生命值',rect,min(float(sa),float(sb)))]
    if not value:
        rect=(495,627,522,662);crop=d._crop(rect)
        a,sa=OCR.ZHS.ocr_single_line(crop);b,sb=OCR.ZHS.ocr_single_line(cv2.resize(crop,None,fx=2,fy=2))
        if min(float(sa),float(sb))<.85 or event.normalizeText(a)!=event.normalizeText(b) or event.normalizeText(a)!='0':return items
        items=items+[event.OcrItem('0',rect,min(float(sa),float(sb)))]
    rect=(507,671,777,717);crop=d._crop(rect)
    a,sa=OCR.ZHS.ocr_single_line(crop);b,sb=OCR.ZHS.ocr_single_line(cv2.resize(crop,None,fx=2,fy=2))
    if min(float(sa),float(sb))<.85 or event.normalizeText(a)!=event.normalizeText(b) or event.normalizeText(a)!='请点击游戏界面':return items
    return [i for i in items if not(event._text(i)=='请点击游戏界面' and i.center[1]>670)]+[event.OcrItem('请点击游戏界面',rect,min(float(sa),float(sb)))]

def servantReceiptItems(d,items):
    # Actual post-story card: supplement omitted class/health text only when
    # attack, both numeric stat regions and dismissal footer are independent.
    if event._unsafeEventOverlay(items):return items
    strong=[i for i in items if i.score>=.85]
    if not any(event._text(i)=='攻击力' and 450<i.center[0]<600 and 600<i.center[1]<635 for i in strong):return items
    if not all(sum(bool(re.fullmatch(r'\d+',event._text(i))) and lo<i.center[0]<hi and 625<i.center[1]<675 for i in strong)==1 for lo,hi in ((450,600),(680,830))):return items
    if not any(event._text(i)=='请点击游戏界面' and 450<i.center[0]<850 and i.center[1]>670 for i in strong):return items
    import cv2
    result=list(items)
    for expected,rect,ocr in (('lancer',(582,546,704,585),OCR.EN),('生命值',(741,603,814,634),OCR.ZHS)):
        crop=d._crop(rect);a,sa=ocr.ocr_single_line(crop);b,sb=ocr.ocr_single_line(cv2.resize(crop,None,fx=2,fy=2))
        if min(float(sa),float(sb))<.85 or event.normalizeText(a)!=expected or event.normalizeText(b)!=expected:return items
        result=[i for i in result if not(rect[0]<i.center[0]<rect[2] and rect[1]<i.center[1]<rect[3])]+[event.OcrItem(a,rect,min(float(sa),float(sb)))]
    return result

def itemDetailItems(d,items):
    if not event.eventItemDetailProof(items):return items
    import cv2
    rect=(25,26,67,60);crop=d._crop(rect)
    a,sa=OCR.ZHS.ocr_single_line(crop);b,sb=OCR.ZHS.ocr_single_line(cv2.resize(crop,None,fx=2,fy=2))
    if min(float(sa),float(sb))<.85 or event.normalizeText(a)!=event.normalizeText(b) or event.normalizeText(a)!='关闭':return items
    return [i for i in items if not(i.center[0]<100 and i.center[1]<100)]+[event.OcrItem('关闭',rect,min(float(sa),float(sb)))]

def skipConfirmationItems(d,items):
    import cv2
    message=[i for i in items if i.score>=.85 and '是否跳过该段剧情' in event._text(i) and 200<i.center[1]<400]
    no=[i for i in items if i.score>=.85 and event._text(i)=='否' and 250<i.center[0]<600 and 480<i.center[1]<620]
    yes=[i for i in items if event._text(i)=='是' and 650<i.center[0]<1000 and 480<i.center[1]<620]
    if len(message)!=1 or len(no)!=1 or len(yes)>1:return items
    rect=(800,532,854,589)
    crop=d._crop(rect);a,sa=OCR.ZHS.ocr_single_line(crop);b,sb=OCR.ZHS.ocr_single_line(cv2.resize(crop,None,fx=2,fy=2))
    if not min(float(sa),float(sb))>=.85 or event.normalizeText(a)!='是' or event.normalizeText(b)!='是':return items
    return [i for i in items if not yes or i is not yes[0]]+[event.OcrItem('是',rect,min(float(sa),float(sb)))]


def storySignature(items):
    # Dialogue only, excluding speaker identity and blinking controls. The
    # digest stays in the private ledger; it is not a public image fixture.
    lines=sorted((i.box[1],i.box[0],event.normalizeText(i.text)) for i in items if i.score>=.85 and 570<i.center[1]<680 and i.center[0]<1100 and len(event.normalizeText(i.text))>=4)
    if not lines:return None
    return hashlib.sha256('|'.join(v[2] for v in lines).encode('utf-8')).hexdigest()

def enrichedEventItems(d):
    items=itemDetailItems(d,itemReceiptItems(d,startConfirmationItems(d,mainTitleItems(d,worldMapItems(d,skipConfirmationItems(d,storyItems(d,nav.labels(d))))))))
    if event.eventTutorialCloseProof(items):
        import cv2
        rect=(1219,7,1273,61);crop=d._crop(rect)
        a,sa=OCR.EN.ocr_single_line(crop);b,sb=OCR.EN.ocr_single_line(cv2.resize(crop,None,fx=2,fy=2))
        if min(float(sa),float(sb))>=.85 and event.normalizeText(a)==event.normalizeText(b)=='x':
            items=items+[event.OcrItem('x',rect,min(float(sa),float(sb)))]
        else:
            score=tutorialCloseScore(d)
            if score>=.75:items=items+[event.OcrItem('x',rect,score,visualProof=True)]
    return items

def tutorialCloseGlyph(d):
    return tutorialCloseScore(d)>=.75

def tutorialCloseScore(d):
    """Actual navy X is not recognized by English OCR. Prove both strokes.

    This generated geometric mask contains no captured image or identity. It
    is used only after the independent final-tutorial structure is confirmed.
    """
    import cv2,numpy
    crop=d._crop((1230,18,1263,49))
    mask=(cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)<100).astype('uint8')
    points=cv2.findNonZero(mask)
    if points is None:return 0.0
    x,y,w,h=cv2.boundingRect(points)
    if not(20<=w<=30 and 20<=h<=30 and abs(x+w/2-16.5)<=3 and abs(y+h/2-15.5)<=3):return 0.0
    mask=cv2.resize(mask[y:y+h,x:x+w],(32,32),interpolation=cv2.INTER_NEAREST)>0
    yy,xx=numpy.indices((32,32));expected=(abs(xx-yy)<=3)|(abs(xx+yy-31)<=3)
    return float((mask&expected).sum())/float((mask|expected).sum())


class EventMain(kernel.Main):
    def __init__(self,runner,**kwargs):
        super().__init__(appleTotal=0,appleKind=0,**kwargs)
        self.runner=runner
        self.teamIndex=0;self.autoFormation=False
    def eatApple(self):
        # Shared preparation must never enter the legacy coordinate resource
        # sequence, even if an AP modal unexpectedly interrupts preparation.
        self.runner.restoreAp()
        return True
    def finishFriendSelection(self,flow,template,refreshes,*,directBattle=False):
        # Real special-event formation offers automatic replacement. Preserve
        # the prepared temporary party by declining that verified offer once.
        deadline=min(flow.deadline or float('inf'),flow.clock()+30)
        expected={S.FORMATION}|({S.TURN_BEGIN} if directBattle else set())
        def accept(d):
            return flow.observation.state in expected or event.findSpecialFormationDecline(nav.labels(d)) is not None
        observation=flow.waitForFlowState(expected|{S.UNKNOWN},timeout=max(0,deadline-flow.clock()),transition_name='event friend exit',allowed_intermediate={S.FRIEND,S.LOADING},accept=accept)
        items=nav.labels(flow.detect)
        if event.findSpecialFormationDecline(items):
            self.runner.configureSpecialFormation(flow.detect,items,flow=flow,deadline=deadline)
            observation=flow.observation
        if observation.state not in expected:raise ScriptStop('Event support did not reach a legal formation')
        return FriendSelectionResult(True,template,refreshes,observation.state)
    def prepareFormation(self,flow):
        items=nav.labels(flow.detect)
        QuartzGuard.check(items)
        if event.isEventFormationBlocked(items):
            raise ScriptStop('Event formation blocked: three starting members required; party unchanged')
        if event.isEventAutoFormationSettings(items) or event.isEventIncompleteFormation(items):
            raise ScriptStop('Event special party requires configuration; no background start or automatic replacement')
        if not event.findEventBattleStart(items):
            raise ScriptStop('Event formation has no unique active start label; party unchanged')
        return super().prepareFormation(flow)
    def waitFormationStart(self,flow):
        # Story before battle is an event boundary. Positive story/confirmation
        # producers may handle it; UNKNOWN itself still authorizes no input.
        deadline=min(flow.deadline or float('inf'),flow.clock()+180)
        lastProgress=flow.clock();seen=set();signature=None
        while flow.clock()<deadline:
            observation=flow.observe()
            if observation.state==S.TURN_BEGIN:return observation
            if observation.state==S.NETWORK_ERROR:
                if not flow.networkHandled:
                    flow.action('network_error_confirm',lambda:kernel.handleNetworkError(flow.detect));flow.networkHandled=True
            elif observation.state in {S.UNKNOWN,S.QUEST_READY}:
                items=skipConfirmationItems(flow.detect,storyItems(flow.detect,nav.labels(flow.detect)));state=event.classifyEventState(items,event._detectFlags(flow.detect))
                if state in ('story','story_skip_confirmation','start_confirmation'):
                    self.runner.handleTransition(flow.detect,items,state,deadline=deadline)
                    lastProgress=flow.clock()
                elif state=='formation_blocked':raise ScriptStop('Event formation blocked: three starting members required; no repeated start input')
                elif state not in ('unknown',):raise ScriptStop('Unexpected event start boundary: '+state)
            elif observation.state not in {S.FORMATION,S.LOADING}:
                raise ScriptStop('Unexpected event formation departure: '+observation.state.name)
            if observation.state in {S.FORMATION,S.LOADING} and observation.state not in seen:
                seen.add(observation.state);lastProgress=flow.clock()
            if observation.state==S.LOADING:
                current=getattr(flow.detect,'getLoadingProgressSignature',lambda:None)()
                if current is not None and current!=signature:signature=current;lastProgress=flow.clock()
            if flow.clock()-lastProgress>=60:flow.fail(FlowTimeout,'STALL event formation start',{S.TURN_BEGIN},60)
            schedule.sleep(.2)
        flow.fail(FlowTimeout,'TIMEOUT event formation start',{S.TURN_BEGIN},180)


class EventRunner:
    def __init__(self,policy,*,friendPolicy='first',friendMaxRefresh=2,storyMode='skip',autoClaim=False,ledger=None,reader=None,clock=time.monotonic):
        if not isinstance(policy,EventResourcePolicy):raise TypeError('Explicit EventResourcePolicy required')
        self.policy=policy;self.reader=reader or (lambda:Detect(0,0));self.clock=clock
        if storyMode not in ('skip','pause'):raise ValueError('Unknown story policy')
        self.storyMode=storyMode
        self.autoClaim=bool(autoClaim)
        self.ledger=ledger or ProgressLedger(paths.logRoot/'event'/'progress-ledger.json')
        self.main=EventMain(self,friendPolicy=friendPolicy,friendMaxRefresh=friendMaxRefresh)
        self.completed=0;self.storySegments=0;self.claimed=0;self.apples={};self.captureFailures=0;self.settledResumes=0
        self.last=None;self.flow=None;self.seenItemReceipts=[];self.seenTutorials=set()
    def read(self):
        schedule.checkStop();schedule.checkSuspend()
        try:d=self.reader()
        except (ConnectionError,StopIteration) as error:
            raise EventCaptureError('Event capture transport lost: '+type(error).__name__+'; no automatic restart or input') from error
        if d.im.shape[:2]!=(720,1280) or XDetect.region!='CN':raise ScriptStop('Event requires CN 1280x720')
        items=enrichedEventItems(d)
        state=event.classifyEventState(items,{**event._detectFlags(d),'main_interface':d.isMainInterface()})
        self.last=(d,items,state)
        return self.last
    def wait(self,states,*,timeout=30,exclude=(),deadline=None,accept=None):
        end=min(self.clock()+timeout,deadline or float('inf'))
        mapFrames=0
        while self.clock()<end:
            d,items,state=self.read()
            if state in states and state not in exclude and (accept is None or accept(d,items,state)):
                if state in ('event_map','event_world_map'):
                    # A fading old map after start is not a completion edge.
                    # Require the menu template and HUD on three acquisitions.
                    mapFrames=mapFrames+1 if d.isMainInterface() and self.ap(d) is not None else 0
                    if mapFrames>=3:return d,items,state
                else:return d,items,state
            else:mapFrames=0
            if state in ('battle_defeated','unsafe_modal','mission_gate'):
                raise ScriptStop('Event transition blocked: '+state)
            # Fresh captures after a verified action are read-only; no retry.
            schedule.sleep(.2)
        raise FlowTimeout('Event transition timed out; no repeated input')
    def touch(self,items,pos,action,**guard):
        if guard.get('dismissNotice') and pos not in (loginRewardInfoClose(items),promotionalInfoClose(items)):
            raise ScriptStop('Informational permission only authorizes its close button')
        if guard.get('appleOption') is not None and pos!=event._center(guard['appleOption']):
            raise ScriptStop('Apple selector permission does not authorize another control')
        QuartzGuard.check(items,**guard)
        schedule.checkStop()
        if self.flow:self.flow.trace.record('EVENT_'+self.last[2].upper(),(),action)
        self.ledger.append('input_intent',action=action)
        fgoDevice.device.touch(pos,duration=.08)
        self.ledger.append('input',action=action)
    def ap(self,d):
        try:return d.getAp()
        except ScriptStop:return None
    def evidence(self,reason):
        fresh=False
        try:self.read();fresh=True
        except ScriptStop:pass # Already stopping: retain prior frame, mark it.
        if self.last:
            import cv2
            d,items,state=self.last
            folder=paths.logRoot/'event'/time.strftime('%Y%m%d-%H%M%S')
            folder.mkdir(parents=True,exist_ok=True)
            cv2.imwrite(str(folder/'blocked.png'),d.im)
            (folder/'blocked.json').write_text(json.dumps({'reason':str(reason),'errorType':type(reason).__name__,'freshCapture':fresh,'state':state,'labels':[{'text':i.text,'box':i.box,'score':i.score} for i in items]},ensure_ascii=False,indent=2),encoding='utf-8')
        self.ledger.append('blocked',reason=str(reason),errorType=type(reason).__name__,freshCapture=fresh,stats=self.main.result)
    def openMap(self):
        d,items,state=self.read()
        if state=='unknown' and not startupInfoClose(d,items) and nav.safeMenuPageCN(d,items)=='UNKNOWN':
            # Story controls can pulse out of full-screen OCR. Finite fresh
            # observation may recover a positive producer, never an input.
            end=self.clock()+10
            while self.clock()<end:
                schedule.sleep(.2);d,items,state=self.read()
                if state!='unknown' or startupInfoClose(d,items) or nav.safeMenuPageCN(d,items)!='UNKNOWN':break
            else:raise ScriptStop('Unknown event entry after bounded fresh reads; no navigation input')
        if state in ('event_map','event_world_map'):return d,items,state
        if state in ('formation_settings','formation_review') and self.policy.allowTemporaryAutoFormation:return d,items,state
        if state in ('formation_blocked','formation_settings','formation_review'):
            raise ScriptStop('Event special party requires configuration: '+state+'; no automatic replacement')
        if state in ('story','story_skip_confirmation','start_confirmation','support','special_formation_offer','formation','battle','battle_result','ap_empty','reward_receipt','item_receipt','item_detail','event_tutorial','mission_list','mission_reward_receipt'):
            return d,items,state # Resume actual state, never ledger-driven.
        dismissed=set()
        for _ in range(8):
            close=startupInfoClose(d,items)
            if not close:break
            key=startupNoticeKey(items)
            if key is None or key in dismissed:raise ScriptStop('Startup information instance not unique; no repeated close')
            # A bulletin is not a generic UNKNOWN: repeat both producers on a
            # fresh capture before one close input, then only wait for home.
            d,items,state=self.read()
            if startupInfoClose(d,items)!=close or startupNoticeKey(items)!=key:raise ScriptStop('Startup notice close unstable; no input')
            isInfo=bool(loginRewardInfoClose(items) or promotionalInfoClose(items))
            self.touch(items,close,'close_startup_information',dismissNotice=isInfo)
            dismissed.add(key)
            end=self.clock()+30
            while self.clock()<end:
                d,items,state=self.read()
                if state=='event_map':return d,items,state
                if startupInfoClose(d,items):
                    if startupNoticeKey(items)!=key:break
                elif nav.terminalHomeCN(d,items):break
                schedule.sleep(.2)
            else:raise FlowTimeout('Startup notice close did not reach a positive page; no retry')
        d=nav.normalizeToTerminalCN()
        guard=nav.NavigationGuard('活动入口',90)
        for _ in range(10):
            guard.check();items=nav.labels(d)
            if not nav.terminalHomeCN(d,items):raise ScriptStop('Event banner directory unconfirmed')
            anchor=event._eventAnchor(items)
            if anchor and event._center(anchor)[1]>=220:
                self.last=(d,items,'home');x,y=event._center(anchor)
                self.touch(items,(x,y-70),'event_banner')
                return self.wait({'event_map','event_world_map'},timeout=30)
            d,_=daily._swipe(d,True)
        raise ScriptStop('No complete unique event banner')
    def stableNode(self):
        previous=None;count=0;end=self.clock()+15
        while self.clock()<end:
            d,items,state=self.read();QuartzGuard.check(items)
            if state=='unknown':
                previous=None;count=0;schedule.sleep(.2);continue
            if state!='event_map':raise ScriptStop('Event map lost during node confirmation')
            node=event.findNextMainQuest(items)
            if not node:
                previous=None;count=0;schedule.sleep(.2);continue
            identity=(event.normalizeText(node['title']),node['position'])
            same=previous is not None and identity[0]==previous[0] and max(abs(a-b) for a,b in zip(identity[1],previous[1]))<=6
            count=count+1 if same else 1;previous=identity
            if count>=3:return d,items,node
            schedule.sleep(.2)
        raise ScriptStop('Main node transient; no selection')
    def openNextArea(self):
        previous=None;count=0;end=self.clock()+15
        while self.clock()<end:
            d,items,state=self.read();QuartzGuard.check(items)
            area=event.findNextEventArea(items) if state=='event_world_map' else None
            if area is None:raise ScriptStop('No unique next event area; no world map input')
            identity=(event.normalizeText(area['title']),area['position'])
            same=previous is not None and identity[0]==previous[0] and max(abs(a-b) for a,b in zip(identity[1],previous[1]))<=6
            count=count+1 if same else 1;previous=identity
            if count>=3:
                self.touch(items,area['position'],'open_next_event_area')
                self.ledger.append('area',title=area['title'],AP=self.ap(d))
                return self.wait({'event_map'},timeout=30)
        raise ScriptStop('Event area marker transient; no navigation input')
    def handleTransition(self,d,items,state,*,deadline=None):
        if state in ('story','story_skip_confirmation') and getattr(self,'storyMode','skip')!='skip':
            raise ScriptStop('Event story pause policy; no skip input')
        if state=='story_skip_confirmation':
            position=event.findSkipConfirmation(items)
            if not position:raise ScriptStop('Unverified story skip confirmation')
            intents=[r for r in self.ledger.data['records'] if r['kind']=='story_skip_intent']
            reference=intents[-1]['signature'] if intents else None
            self.touch(items,position,'confirm_story_skip')
            outcome=self.waitAfterSkip(reference,deadline=deadline)
            self.storySegments+=1;self.ledger.append('story_skip_complete',nextState=outcome[2])
            return outcome
        if state=='start_confirmation':
            position=event.findStartQuestConfirmation(items)
            if position is None:raise ScriptStop('Unverified start confirmation')
            self.touch(items,position,'confirm_event_start')
            return self.wait({'story','support','formation','battle','ap_empty'},deadline=deadline)
        if state=='story':
            d,items,reference=self.stableStory()
            position=event.findSkipButton(items)
            if not position:raise ScriptStop('Story has no unique positive SKIP; no dialogue blind click')
            self.ledger.append('story_skip_intent',signature=reference)
            self.touch(items,position,'story_skip')
            end=min(self.clock()+15,deadline or float('inf'))
            while self.clock()<end:
                d,items,_=self.read()
                position=event.findSkipConfirmation(items)
                if position:
                    self.touch(items,position,'confirm_story_skip')
                    outcome=self.waitAfterSkip(reference,deadline=deadline)
                    self.storySegments+=1;self.ledger.append('story_skip_complete',nextState=outcome[2])
                    return outcome
                schedule.sleep(.2)
            raise ScriptStop('SKIP confirmation not positively proven')
        raise ScriptStop('No handler for '+state)
    def stableStory(self):
        deadline=self.clock()+15;previous=None;count=0
        while self.clock()<deadline:
            d,items,state=self.read()
            if state=='unknown':
                count=0;previous=None;schedule.sleep(.2);continue
            if state!='story':raise ScriptStop('Story episode lost before skip; no input')
            signature=storySignature(items)
            count=count+1 if signature is not None and signature==previous else 1
            previous=signature
            if signature is not None and count>=3:return d,items,signature
            schedule.sleep(.2)
        raise ScriptStop('Dialogue signature not stable; no skip input')
    def declineSpecialFormation(self,d,items,*,flow=None,deadline=None):
        position=event.findSpecialFormationDecline(items)
        if position is None:raise ScriptStop('Special formation offer unconfirmed')
        fresh,labels,state=self.read()
        if state!='special_formation_offer' or event.findSpecialFormationDecline(labels)!=position:
            raise ScriptStop('Special formation decline unstable; no input')
        callback=lambda:self.touch(labels,position,'decline_special_auto_formation')
        if flow:
            flow.action('decline_special_auto_formation',callback)
            return flow.waitForFlowState({S.FORMATION},timeout=max(0,(deadline or flow.clock()+30)-flow.clock()),transition_name='special formation offer exit',allowed_intermediate={S.UNKNOWN})
        callback()
        return self.wait({'formation'},timeout=30,deadline=deadline)
    def configureSpecialFormation(self,d,items,*,flow=None,deadline=None):
        if not self.policy.allowTemporaryAutoFormation:
            return self.declineSpecialFormation(d,items,flow=flow,deadline=deadline)
        # The offer itself explicitly isolates this party from normal settings.
        if event.findSpecialFormationDecline(items) is None:
            raise ScriptStop('Temporary party isolation unproven; no automatic formation')
        fresh,labels,state=self.read()
        if state!='special_formation_offer' or event.findSpecialFormationDecline(labels) is None:
            raise ScriptStop('Special formation offer unstable; no input')
        target=[i for i in labels if i.score>=.85 and event._text(i)=='自动编成' and 540<i.center[1]<640]
        if len(target)!=1:raise ScriptStop('Special auto formation button ambiguous')
        callback=lambda:self.touch(labels,target[0].center,'auto_form_isolated_event_party')
        if flow:
            flow.action('auto_form_isolated_event_party',callback)
            d,items,state=self.wait({'formation','formation_review'},timeout=30,deadline=deadline,accept=lambda d,i,s:bool(event.findTemporaryPartyDecision(i) or event.findEventBattleStart(i)))
            if state=='formation_review':self.confirmTemporaryParty(d,items,deadline=deadline)
            return flow.waitForFlowState({S.FORMATION},timeout=max(0,(deadline or flow.clock()+30)-flow.clock()),transition_name='special auto formation exit',allowed_intermediate={S.UNKNOWN},accept=lambda d:event.findEventBattleStart(nav.labels(d)) is not None)
        callback()
        d,items,state=self.wait({'formation','formation_review'},timeout=30,deadline=deadline,accept=lambda d,i,s:bool(event.findTemporaryPartyDecision(i) or event.findEventBattleStart(i)))
        return self.confirmTemporaryParty(d,items,deadline=deadline) if state=='formation_review' else (d,items,state)
    def configureTemporaryParty(self,d,items,state):
        if not self.policy.allowTemporaryAutoFormation:
            raise ScriptStop('Temporary auto formation permission disabled')
        def restricted(labels):return sum(i.score>=.85 and event._text(i)=='受限' and i.center[1]<100 for i in labels)==1
        if not restricted(items):raise ScriptStop('Not a positively restricted event party; no changes')
        if state=='formation':
            if not event.isEventIncompleteFormation(items):raise ScriptStop('No evidenced missing starting member')
            auto=[i for i in items if i.score>=.85 and event._text(i)=='自动' and 260<i.center[0]<330 and 640<i.center[1]<685]
            party=[i for i in items if i.score>=.85 and event._text(i)=='编队' and 260<i.center[0]<330 and 675<i.center[1]<715]
            if len(auto)!=len(party) or len(auto)!=1:raise ScriptStop('Temporary auto settings entry ambiguous')
            fresh,labels,current=self.read()
            if current!='formation' or not restricted(labels) or not event.isEventIncompleteFormation(labels):
                raise ScriptStop('Temporary party changed before settings; no input')
            self.touch(labels,auto[0].center,'open_temporary_auto_settings')
            d,items,state=self.wait({'formation_settings'},timeout=15)
        if state!='formation_settings' or not restricted(items) or not event.isEventAutoFormationSettings(items):
            raise ScriptStop('Temporary auto formation settings not confirmed')
        fresh,labels,current=self.read()
        target=[i for i in labels if i.score>=.85 and event._text(i)=='自动编成' and 800<i.center[0]<1050 and 500<i.center[1]<620]
        if current!='formation_settings' or not restricted(labels) or not event.isEventAutoFormationSettings(labels) or len(target)!=1:
            raise ScriptStop('Temporary auto formation confirmation unstable; no input')
        self.touch(labels,target[0].center,'auto_form_isolated_event_party')
        d,items,state=self.wait({'formation','formation_review'},timeout=30,accept=lambda d,i,s:bool(event.findTemporaryPartyDecision(i) or event.findEventBattleStart(i)))
        if state=='formation_review':return self.confirmTemporaryParty(d,items)
        if event.isEventIncompleteFormation(items):raise ScriptStop('Game automatic formation still has missing starting members; no retry')
        self.ledger.append('temporary_party_ready',formalPartyChanged=False)
        return d,items,state
    def confirmTemporaryParty(self,d,items,*,deadline=None):
        if not self.policy.allowTemporaryAutoFormation:raise ScriptStop('Temporary party confirmation permission disabled')
        position=event.findTemporaryPartyDecision(items)
        if position is None:raise ScriptStop('Restricted temporary party review unproven')
        for _ in range(2):
            d,items,state=self.read()
            if state!='formation_review' or event.findTemporaryPartyDecision(items)!=position:
                raise ScriptStop('Temporary party decision unstable; no input')
        self.touch(items,position,'confirm_temporary_event_party')
        previous=None;stable=0
        def ready(d,items,state):
            nonlocal previous,stable
            position=event.findEventBattleStart(items)
            header=[i for i in items if i.score>=.85 and event._text(i)=='队伍确认' and i.center[0]>1000 and i.center[1]<100]
            stable=stable+1 if position is not None and len(header)==1 and position==previous else 1 if position is not None and len(header)==1 else 0
            previous=position
            return stable>=3
        d,items,state=self.wait({'formation'},timeout=30,deadline=deadline,accept=ready)
        self.ledger.append('temporary_party_ready',formalPartyChanged=False)
        return d,items,state
    def waitAfterSkip(self,reference,*,deadline=None):
        deadline=min(self.clock()+45,deadline or float('inf'))
        departure=False;previous=None;stable=0
        while self.clock()<deadline:
            d,items,state=self.read()
            if state in ('support','formation','battle','start_confirmation','ap_empty','reward_receipt','item_receipt','item_detail','event_tutorial'):return d,items,state
            if state in ('event_map','event_world_map'):return self.wait({'event_map','event_world_map'},deadline=deadline)
            if state=='story':
                signature=storySignature(items)
                changed=signature is not None and (signature!=reference if reference is not None else departure)
                stable=stable+1 if changed and signature==previous else 1 if changed else 0
                previous=signature
                if stable>=3:return d,items,state
            else:
                stable=0;previous=None
                if state=='unknown' and (float(d.im.mean())<18 or getattr(d,'isLoading',lambda:False)()):departure=True
                if state in ('unsafe_modal','battle_defeated','mission_gate'):
                    raise ScriptStop('Story departure blocked: '+state)
            schedule.sleep(.2)
        raise FlowTimeout('Story episode did not depart; no repeated skip input')
    def handleRewardReceipt(self,d,items):
        position=event.findEventRewardReceipt(items) or event.findEventItemReceipt(items)
        if position is None:raise ScriptStop('Completion receipt unproven; no input')
        def reward(labels):return tuple(sorted(event._text(i) for i in labels if i.score>=.85 and (re.fullmatch(r'获得.+[×x]\d+[!！]?',event._text(i)) and 450<i.center[1]<600 or event._text(i)=='概念礼装' or re.fullmatch(r'(?:\+\d+|0)',event._text(i)) and 625<i.center[1]<675)))
        reference=reward(items);stable=1;end=self.clock()+15
        while self.clock()<end:
            d,items,state=self.read()
            current=event.findEventRewardReceipt(items) or event.findEventItemReceipt(items)
            same=state in ('reward_receipt','item_receipt') and current is not None and max(abs(a-b) for a,b in zip(current,position))<=6 and reward(items)==reference
            stable=stable+1 if same else 0
            if stable>=3:position=current;break
            if state not in ('unknown','reward_receipt','item_receipt'):raise ScriptStop('Completion receipt changed foreground; no input')
            schedule.sleep(.2)
        else:raise ScriptStop('Completion receipt unstable; no input')
        if event.findEventItemReceipt(items):
            import cv2,numpy
            signature=cv2.resize(d.im[150:500,500:780],(16,16)).astype('float32')
            if any(float(numpy.abs(signature-old).mean())<8 for old in self.seenItemReceipts):
                raise ScriptStop('Already advanced this awarded item instance; no repeated input')
            self.seenItemReceipts.append(signature)
        self.touch(items,position,'dismiss_earned_event_reward_receipt')
        allowed={'event_map','event_world_map','story','mission_list','mission_gate','event_tutorial'}
        if event.findEventItemReceipt(items):allowed.add('item_detail');allowed.add('reward_receipt')
        outcome=self.wait(allowed,timeout=30)
        self.ledger.append('reward_receipt',alreadyAwarded=True,consumed=False,nextState=outcome[2])
        return outcome
    def closeItemDetail(self,d,items):
        position=event.findEventItemDetailClose(items)
        if position is None:raise ScriptStop('Item detail close unproven')
        for _ in range(2):
            d,items,state=self.read()
            if state!='item_detail' or event.findEventItemDetailClose(items)!=position:raise ScriptStop('Item detail close unstable; no input')
        self.touch(items,position,'close_awarded_item_details')
        return self.wait({'event_map','event_world_map','story','reward_receipt','item_receipt','event_tutorial'},timeout=30)
    def advanceTutorial(self,d,items,*,deadline=None):
        position=event.findEventTutorialNext(items)
        key=event.eventTutorialKey(items)
        if position is None or key is None or key in self.seenTutorials:raise ScriptStop('Event tutorial forward unproven or already advanced')
        for _ in range(2):
            d,items,state=self.read()
            if state!='event_tutorial' or event.findEventTutorialNext(items)!=position or event.eventTutorialKey(items)!=key:raise ScriptStop('Event tutorial transient; no input')
        if deadline is not None and self.clock()>=deadline:raise FlowTimeout('Event tutorial parent deadline expired; no input')
        self.seenTutorials.add(key)
        self.touch(items,position,'advance_event_instructions')
        return self.wait({'event_map','event_world_map','story','event_tutorial','mission_list','item_detail'},timeout=30,deadline=deadline,accept=lambda d,labels,state:state!='event_tutorial' or event.eventTutorialKey(labels)!=key)
    def claimCompletedMission(self):
        if not self.autoClaim:raise ScriptStop('Completed Mission claim policy disabled')
        previous=None;stable=0;end=self.clock()+15
        while self.clock()<end:
            d,items,state=self.read();card=event.findCompletedMissionCard(items) if state=='mission_list' else None
            if card is None:
                if state not in ('unknown','mission_list'):raise ScriptStop('Mission claim foreground changed; no input')
                stable=0;previous=None;schedule.sleep(.2);continue
            before=event.missionCompletedCount(items);identity=(card['mission'],card['progress'],before,card['position'])
            same=previous is not None and identity[:3]==previous[:3] and max(abs(a-b) for a,b in zip(identity[3],previous[3]))<=6
            stable=stable+1 if same else 1;previous=identity
            if stable>=3:break
        else:raise ScriptStop('Completed Mission card transient; no claim')
        self.ledger.append('mission_claim_intent',mission=card['mission'],title=card['title'],beforeCount=before)
        self.touch(items,card['position'],'claim_completed_event_mission')
        end=self.clock()+30;stable=0
        while self.clock()<end:
            d,items,state=self.read()
            if state in ('reward_receipt','item_receipt'):
                d,items,state=self.handleRewardReceipt(d,items)
            elif state=='mission_reward_receipt':
                proof=event.missionRewardReceipt(items)
                if proof is None or proof['beforeCount']!=before:
                    raise ScriptStop('Mission receipt counter context disagrees; no close')
                d,items,state=self.closeMissionRewardReceipt(d,items)
                # The receipt handler already proved three incremented frames.
                if state!='mission_list' or event.missionCompletedCount(items)!=before+1:
                    raise ScriptStop('Mission receipt returned without proved increment')
                self.claimed+=1;self.ledger.append('mission_claim',mission=card['mission'],title=card['title'],beforeCount=before,afterCount=before+1,choice=False)
                return d,items,state
            count=event.missionCompletedCount(items) if state=='mission_list' else None
            stable=stable+1 if count is not None and count==before+1 else 0
            if stable>=3:
                self.claimed+=1;self.ledger.append('mission_claim',mission=card['mission'],title=card['title'],beforeCount=before,afterCount=count,choice=False)
                return d,items,state
            if state in ('unsafe_modal','battle_defeated'):raise ScriptStop('Mission claim stopped: '+state)
            schedule.sleep(.2)
        raise FlowTimeout('Mission claim has no proved counter increment; no repeated claim')
    def closeMissionRewardReceipt(self,d,items,*,countResumedClaim=False):
        proof=event.missionRewardReceipt(items)
        if proof is None:raise ScriptStop('Earned Mission reward receipt unproven')
        before=proof['beforeCount'];stable=1;end=self.clock()+15
        while self.clock()<end:
            d,items,state=self.read();current=event.missionRewardReceipt(items)
            same=state=='mission_reward_receipt' and current is not None and current['reward']==proof['reward'] and max(abs(a-b) for a,b in zip(current['position'],proof['position']))<=6
            stable=stable+1 if same else 0
            if same and current['beforeCount'] is not None:before=current['beforeCount']
            if stable>=3:proof=current;break
            if state not in ('unknown','mission_gate','mission_reward_receipt'):raise ScriptStop('Reward receipt changed foreground; no close')
            schedule.sleep(.2)
        else:raise ScriptStop('Earned Mission receipt transient; no close')
        self.touch(items,proof['position'],'close_earned_mission_reward')
        stable=0
        def counted(d,labels,state):
            nonlocal stable
            count=event.missionCompletedCount(labels)
            stable=stable+1 if state=='mission_list' and count is not None and before is not None and count==before+1 else 0
            return stable>=3
        end=self.clock()+30
        outcome=self.wait({'mission_list','event_tutorial'},deadline=end,accept=lambda d,labels,state:state=='event_tutorial' or counted(d,labels,state))
        if outcome[2]=='event_tutorial':
            # The actual first claim opens a passive unlock tutorial. Prove and
            # close it once, then still require the real list counter increment.
            outcome=self.advanceTutorial(outcome[0],outcome[1],deadline=end)
            outcome=self.wait({'mission_list'},deadline=end,accept=counted)
        if outcome[2]!='mission_list' or before is None or event.missionCompletedCount(outcome[1])!=before+1:
            raise ScriptStop('Mission receipt increment unconfirmed')
        if countResumedClaim:self.claimed+=1
        self.ledger.append('mission_reward_receipt',reward=proof['reward'],consumed=False,beforeCount=before,afterCount=event.missionCompletedCount(outcome[1]),resumedClaim=countResumedClaim)
        return outcome
    def returnFromMissions(self,d,items):
        if not event._missionListConfirmed(items):raise ScriptStop('Mission list unconfirmed')
        position=event._missionReturnButton(items)
        if position is None:raise ScriptStop('Mission return unconfirmed')
        for _ in range(2):
            d,items,state=self.read()
            if state!='mission_list' or event._missionReturnButton(items)!=position:raise ScriptStop('Mission return transient; no input')
        self.touch(items,position,'return_from_event_missions')
        return self.wait({'event_map','event_world_map'},timeout=30)
    def restoreAp(self):
        if not self.policy.allowApples:raise ScriptStop('Apple policy disabled')
        d,items,state=self.read()
        if state!='ap_empty':raise ScriptStop('AP selector not positively confirmed')
        # Resource details must be visible in the same option row: stock and
        # numeric restoration. No implicit amount/coordinate tables.
        options=[]
        for row in event._rows(items,delta=35):
            labels=[i for i in row['items'] if event._reliable(i)]
            apples=[i for i in labels if event._text(i) in QuartzGuard.apples]
            text=QuartzGuard.text(labels)
            amount=re.search(r'(?:恢复|回复)(\d+)(?:点)?ap',text)
            stock=re.search(r'(?:持有|所持)[:：]?(\d+)',text)
            if len(apples)==1 and amount and stock and int(stock[1])>0:
                options.append((int(amount[1]),apples[0]))
        if not options:raise ScriptStop('AP item quantity/amount unproven; diagnostic saved, quartz blocked')
        _,apple=min(options,key=lambda v:v[0]);before=self.ap(d)
        self.touch(items,event._center(apple),'select_apple',appleOption=apple)
        end=self.clock()+15
        while self.clock()<end:
            d,items,_=self.read()
            if event._text(apple) not in QuartzGuard.text(items):raise ScriptStop('Selected apple missing from confirmation')
            buttons=[i for i in items if event._reliable(i) and event._text(i) in ('确定','确认','使用')]
            cancels=[i for i in items if event._reliable(i) and event._text(i)=='取消']
            if len(buttons)==len(cancels)==1:
                self.touch(items,event._center(buttons[0]),'confirm_apple',appleConfirm=True)
                after,_,_=self.wait({'support','formation','event_map','story','start_confirmation'},timeout=30)
                name=event._text(apple);self.apples[name]=self.apples.get(name,0)+1
                self.ledger.append('apple',item=name,beforeAP=before,afterAP=self.ap(after));return
            schedule.sleep(.2)
        raise ScriptStop('Apple confirmation unproven')
    def runBattle(self):
        main=self.main;flow=main.makeFlow();self.flow=flow;cycle=BattleCycle(main,flow)
        token=INPUT_OBSERVER.set(flow.deviceInput)
        try:
            d,items,state=self.read();QuartzGuard.check(items)
            if state=='battle_result':
                cycle.settleBattleResult(boundary=self.eventBoundary)
                if flow.observation.state==S.CONTINUE:
                    flow.action('decline_event_repeat',lambda:main.press('F'))
                    outcome=self.wait({'event_map','event_world_map','story'},timeout=30)
                else:outcome=self.read()
                if outcome[2] not in ('event_map','event_world_map','story','reward_receipt','item_receipt','item_detail'):raise ScriptStop('Resumed result has no positive event boundary')
                self.settledResumes+=1
                self.ledger.append('settlement_resume',nextState=outcome[2],newBattleEntry=False)
                return outcome
            if state not in ('support','formation','battle'):raise ScriptStop('Unverified event battle entry')
            if not cycle.prepare():raise ScriptStop('Event preparation stopped')
            main.startedBattles+=1;main.battleCount=main.startedBattles
            flow.trace.battle_sequence=main.startedBattles
            battle=main.battleClass();battle.flow=flow;main.battleProc=battle
            try:won=battle()
            except ScriptStop:
                if battle.defeated:
                    main.recordCompleted(False,battle.result);main.emitCompleted(False,battle.result)
                raise
            main.recordCompleted(won,battle.result)
            self.ledger.append('battle',won=won,result=battle.result,stats=main.result)
            if not won:raise ScriptStop('Battle defeated; no revival')
            try:cycle.settleBattleResult(boundary=self.eventBoundary)
            finally:main.emitCompleted(won,battle.result)
            if flow.observation.state==S.CONTINUE:
                flow.action('decline_event_repeat',lambda:main.press('F'))
                return self.wait({'event_map','event_world_map','story'},timeout=30)
            return self.read()
        except (ConnectionError,StopIteration) as error:
            flow.trace.failure('CAPTURE_ERROR',(),0,(type(error).__name__,))
            self.ledger.append('battle_interrupted',reason=type(error).__name__,stats=main.result,completed=False)
            raise EventCaptureError('Event battle capture transport lost: '+type(error).__name__+'; outcome unconfirmed') from error
        finally:
            INPUT_OBSERVER.reset(token);self.flow=None
    def eventBoundary(self,d):
        items=enrichedEventItems(d)
        state=event.classifyEventState(items,{**event._detectFlags(d),'main_interface':d.isMainInterface()})
        return state in ('event_map','event_world_map','story','reward_receipt','item_receipt') and not event._unsafeEventOverlay(items)
    def run(self,maxNodes=1,*,mapSmoke=False):
        with automationOwner.claim():
            try:
                d,items,state=self.openMap()
                if mapSmoke:
                    if state!='event_map':raise ScriptStop('Map smoke requires verified map')
                    node=event.findNextMainQuest(items)
                    if not node:raise ScriptStop('Map smoke has no next main node')
                    return self.report('map_smoke_pass',nextNode=node,AP=self.ap(d))
                pending=None;before=None;entryStart=self.clock();steps=0
                if state in ('story','story_skip_confirmation','start_confirmation','support','special_formation_offer','formation_settings','formation_review','formation','battle','battle_result'):
                    # Actual in-progress UI proves a resumable entry. A saved
                    # ledger may annotate it, but never causes another tap.
                    pending={'title':'resumed actual event node','battlesBefore':self.main.completedAttempts,'storyBefore':self.storySegments,'settlementsBefore':self.settledResumes}
                while self.completed<int(maxNodes):
                    steps+=1
                    if steps>1000 or self.clock()-entryStart>3600:raise ScriptStop('Event bounded node progress exhausted')
                    if state in ('event_map','event_world_map'):
                        if pending:
                            d,items,state=self.wait({'event_map','event_world_map'},timeout=30)
                            if self.main.completedAttempts<=pending['battlesBefore'] and self.storySegments<=pending['storyBefore'] and self.settledResumes<=pending['settlementsBefore']:
                                raise ScriptStop('Event map return has no completed story/battle evidence; node not counted')
                            self.completed+=1
                            self.ledger.append('node',title=pending['title'],type='battle' if self.main.completedAttempts>pending['battlesBefore'] or self.settledResumes>pending['settlementsBefore'] else 'story',beforeAP=before,afterAP=self.ap(d),apples=dict(self.apples),stats=self.main.result,nextState=state,resumedSettlements=self.settledResumes-pending['settlementsBefore'])
                            pending=None;entryStart=self.clock()
                            if self.completed>=int(maxNodes):break
                        if state=='event_world_map':d,items,state=self.openNextArea()
                        d,items,node=self.stableNode();before=self.ap(d)
                        pending={**node,'battlesBefore':self.main.completedAttempts,'storyBefore':self.storySegments,'settlementsBefore':self.settledResumes}
                        self.ledger.append('node_intent',title=node['title'],beforeAP=before,restrictions=node['restrictions'])
                        self.touch(items,node['position'],'select_main_node')
                        d,items,state=self.wait({'start_confirmation','story','support','formation','battle','ap_empty'},timeout=30)
                    elif state in ('start_confirmation','story','story_skip_confirmation'):
                        d,items,state=self.handleTransition(d,items,state)
                    elif state in ('support','formation','battle','battle_result'):
                        if state=='formation' and event.isEventIncompleteFormation(items):
                            d,items,state=self.configureTemporaryParty(d,items,state)
                        else:d,items,state=self.runBattle()
                    elif state=='special_formation_offer':
                        d,items,state=self.configureSpecialFormation(d,items)
                    elif state=='formation_settings':
                        d,items,state=self.configureTemporaryParty(d,items,state)
                    elif state=='formation_review':
                        d,items,state=self.confirmTemporaryParty(d,items)
                    elif state in ('reward_receipt','item_receipt'):
                        d,items,state=self.handleRewardReceipt(d,items)
                    elif state=='item_detail':
                        d,items,state=self.closeItemDetail(d,items)
                    elif state=='event_tutorial':
                        d,items,state=self.advanceTutorial(d,items)
                    elif state=='mission_reward_receipt':
                        d,items,state=self.closeMissionRewardReceipt(d,items,countResumedClaim=True)
                    elif state=='ap_empty':
                        self.restoreAp();d,items,state=self.read()
                    elif state=='mission_list':
                        if event.findCompletedMissionCard(items) and self.autoClaim:d,items,state=self.claimCompletedMission()
                        else:d,items,state=self.returnFromMissions(d,items)
                    elif state=='mission_gate':
                        requirement=[MissionRequirement.parse(v) for v in event.findMissionGate(items)]
                        self.ledger.append('mission_gate',requirements=[vars(v) for v in requirement if v])
                        raise ScriptStop('Mission conditions need evidenced quest mapping; no random Free Quest')
                    else:raise ScriptStop('Event unexpected state '+state)
                return self.report('limit_reached')
            except ScriptStop as error:
                if isinstance(error,EventCaptureError):self.captureFailures+=1
                self.evidence(error)
                return self.report('blocked',message=str(error),errorType=type(error).__name__)
    def report(self,state,**fields):
        return {'type':'EventProgress','state':state,'nodes':self.completed,'storySegments':self.storySegments,'claimed':self.claimed,'apples':self.apples,'quartz':0,'quartzRevive':0,'captureFailures':self.captureFailures,'stats':self.main.result,**fields}

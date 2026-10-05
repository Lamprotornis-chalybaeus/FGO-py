from dataclasses import dataclass
import re,unicodedata
import fgoDevice
import fgoKernel
import fgoQuickQuest
from fgoDetect import Detect,OCR,XDetect
from fgoSchedule import ScriptStop,schedule

EVENT_STORY_PAUSE='pause'
EVENT_STORY_SKIP='skip'
EVENT_SCROLL_LIMIT=10
EVENT_NODE_LIMIT=100

@dataclass(frozen=True)
class OcrItem:
    text:str
    box:tuple[int,int,int,int]
    score:float=1.0
    visualProof:bool=False
    @property
    def center(self):return ((self.box[0]+self.box[2])//2,(self.box[1]+self.box[3])//2)

def normalizeText(text):
    return re.sub(r'\s+','',unicodedata.normalize('NFKC',str(text))).casefold()

def ocrScreen(image,dropScore=.4):
    spans=OCR.ZHS.detect_and_ocr(image,drop_score=dropScore)
    items=[]
    for span in spans:
        import numpy
        box=numpy.asarray(span.box,dtype=float).reshape(-1,2)
        items.append(OcrItem(str(span.text),tuple(int(v)for v in(*box.min(axis=0),*box.max(axis=0))),float(span.score)))
    return items

def _text(item):return normalizeText(getattr(item,'text',''))
def _box(item):
    box=getattr(item,'box',(0,0,0,0))
    if len(box)==4:return tuple(map(int,box))
    import numpy
    points=numpy.asarray(box,dtype=float).reshape(-1,2)
    return tuple(int(v)for v in(*points.min(axis=0),*points.max(axis=0)))
def _center(item):
    box=_box(item)
    return ((box[0]+box[2])//2,(box[1]+box[3])//2)

def _reliable(item):return float(getattr(item,'score',0))>=.8

def _unsafeEventOverlay(items):
    """Reject foreground choices before acting on still-visible menu rows."""
    central=[i for i in items if 280<=_center(i)[0]<=1020 and 150<=_center(i)[1]<=650]
    text=' '.join(_text(i) for i in central)
    if any(token in text for token in ('请选择','选择奖励','奖励选择','任选','二选一')):return True
    if any(token in text for token in ('ap不足','ap恢复','ap回复','恢复ap','体力不足','购买','购入','圣晶石恢复','使用苹果')):return True
    cancel=any(_text(i) in ('取消','cancel','否','no') for i in central)
    confirm=any(_text(i) in ('确认','确定','ok','confirm','是','yes','开始') for i in central)
    return bool(cancel and confirm and ('是否' in text or any(token in text for token in ('恢复','回复','购买','领取奖励','奖励'))))

def _rows(items,delta=84):
    rows=[]
    for item in sorted(items,key=lambda value:_center(value)[1]):
        y=_center(item)[1]
        row=next((value for value in reversed(rows) if abs(y-value['y'])<=delta),None)
        if row is None:rows.append({'y':y,'items':[item]})
        else:
            row['items'].append(item)
            row['y']=sum(_center(v)[1] for v in row['items'])//len(row['items'])
    return rows

def _eventAnchor(items):
    matches=[item for item in items if '活动举办时间' in _text(item) and _reliable(item) and _center(item)[0]>=640 and 95<_center(item)[1]<600]
    return matches[0] if len(matches)==1 else None

def _isMainTitle(text):
    compact=normalizeText(text)
    return ('主线' in compact or '序幕' in compact or 'mainquest' in compact or 'mainstory' in compact or 'prologue' in compact or 'epilogue' in compact or bool(re.search(r'第[0-9一二三四五六七八九十]+[节幕话章]',compact)))

def findNextMainQuest(items):
    candidates=[]
    for row in _rows(items):
        rowItems=row['items']
        rowText=' '.join(_text(item) for item in rowItems)
        positiveItems=[item for item in rowItems if _reliable(item)]
        titleItems=[item for item in positiveItems if _isMainTitle(_text(item))]
        if not titleItems:continue
        if any(re.search(r'完成任务no[.．]?\d+后开放',_text(i)) for i in rowItems):continue
        if any(token in rowText for token in ('已完成','通关','clear','complete')):continue
        positiveText=' '.join(_text(item) for item in positiveItems)
        isNew=any(token in positiveText for token in ('new','新!','新！'))
        explicitMain=any(token in positiveText for token in ('主线','mainquest','mainstory'))
        hasAp=any(re.search(r'ap\s*\d+',_text(item)) for item in positiveItems)
        explicitEpisode=any(any(token in _text(item) for token in ('序幕','终幕','epilogue','prologue')) or bool(re.search(r'第[0-9一二三四五六七八九十]+[节幕话章]',_text(item))) for item in titleItems)
        if not (isNew or explicitMain or explicitEpisode) or not (hasAp or explicitEpisode):continue
        title=min(titleItems,key=lambda item:_center(item)[0])
        x,y=_center(title)
        candidates.append((0 if isNew else 1,y,title,(x,y),rowText))
    if not candidates:return None
    _,_,title,position,rowText=min(candidates,key=lambda v:(v[0],v[1]))
    restrictions=[str(i.text) for i in items if any(t in _text(i) for t in ('编制需符合要求','编队限制','限定编队','只能使用npc从者','请使用指定编队','固定编队出击')) and abs(_center(i)[1]-position[1])<=110]
    return {'title':str(title.text),'position':position,'rowText':rowText,'restrictions':restrictions}

def findMissionGate(items):
    result=[]
    verbs=('完成','击败','收集','通关','解锁','需要','达到')
    for item in items:
        text=str(getattr(item,'text','')).strip()
        compact=normalizeText(text)
        if compact.rstrip('，,。.!！?？') in ('任务完成','已完成任务','完成任务','达成任务','确认活动任务'):continue
        if '任务' not in compact or '任务进度' in compact or '任务进行度' in compact:continue
        if any(normalizeText(word) in compact for word in verbs):result.append(text)
    return result

def findLockedEventMission(items):
    if _unsafeEventOverlay(items) or not _eventMap(items):return None
    locks=[i for i in items if float(i.score)>=.85 and re.fullmatch(r'完成任务no[.．]?\d+后开放',_text(i)) and 750<_center(i)[0]<1100 and 100<_center(i)[1]<250]
    entry=[i for i in items if float(i.score)>=.85 and _text(i)=='活动报酬' and _center(i)[0]>1100 and _center(i)[1]<100]
    if len(locks)!=1 or len(entry)!=1:return None
    number=int(re.search(r'\d+',_text(locks[0]))[0])
    return {'mission':number,'condition':str(locks[0].text),'position':_center(entry[0])}

def _isStory(items,flags=None):
    flags=flags or {}
    if flags.get('story'):return True
    allText=' '.join(_text(i) for i in items)
    if any(token in allText for token in ('活动举办时间','ap5','ap10','推荐职阶')):return False
    controls=[i for i in items if _text(i) in ('menu','菜单','skip','跳过') and _center(i)[1]<180]
    dialogue=[i for i in items if 570<_center(i)[1]<680 and _center(i)[0]<1100 and len(_text(i))>=4]
    return bool(controls and dialogue)

def _isStartQuestConfirmation(items):
    return findStartQuestConfirmation(items) is not None

def findStartQuestConfirmation(items):
    positive=[item for item in items if _reliable(item)]
    text=' '.join(_text(item) for item in positive)
    oldStart=[i for i in positive if _text(i)=='开始']
    if '是否开始关卡' in text and len(oldStart)==1 and sum(1 for item in positive if _text(item)=='取消')==1:return _center(oldStart[0])
    strong=[i for i in items if float(i.score)>=.85]
    title=[i for i in strong if _isMainTitle(i.text) and 300<_center(i)[0]<1000 and 80<_center(i)[1]<180]
    message=[i for i in strong if _text(i).rstrip('?？')=='是否开始任务' and 400<_center(i)[0]<900 and 450<_center(i)[1]<530]
    story=[i for i in strong if _text(i)=='该任务没有战斗' and 400<_center(i)[0]<900 and 250<_center(i)[1]<380]
    start=[i for i in strong if _text(i)=='任务开始' and 700<_center(i)[0]<1000 and 530<_center(i)[1]<620]
    cancel=[i for i in strong if _text(i)=='取消' and 300<_center(i)[0]<600 and 530<_center(i)[1]<620]
    return _center(start[0]) if len(title)==len(message)==len(story)==len(start)==len(cancel)==1 else None

def findFormationRestrictionNotice(items):
    if _unsafeEventOverlay(items):return None
    strong=[i for i in items if i.score>=.85]
    heading=[i for i in strong if _text(i)=='编制限制' and 500<_center(i)[0]<800 and 60<_center(i)[1]<140]
    required=[i for i in strong if re.fullmatch(r'请将[\u4e00-\u9fff]{2,12}',_text(i)) and 400<_center(i)[0]<900 and 180<_center(i)[1]<250]
    instruction=[i for i in strong if _text(i).rstrip('。.')=='设置为首发队员' and 400<_center(i)[0]<900 and 250<_center(i)[1]<310]
    close=[i for i in strong if _text(i)=='关闭' and 500<_center(i)[0]<800 and 560<_center(i)[1]<640]
    if len(heading)!=1 or len(close)!=1:return None
    if len(required)==len(instruction)==1:
        return {'position':_center(close[0]),'requirement':str(required[0].text)+' '+str(instruction[0].text)}
    context=[i for i in strong if _text(i).rstrip('，,')=='在本关卡中' and 400<_center(i)[0]<900 and 290<_center(i)[1]<345]
    forbidden=[i for i in strong if re.fullmatch(r'[\u4e00-\u9fff]{2,12}',_text(i)) and 400<_center(i)[0]<900 and 345<_center(i)[1]<375]
    exclusion=[i for i in strong if _text(i).rstrip('。.')=='不可编队' and 400<_center(i)[0]<900 and 380<_center(i)[1]<430]
    if len(context)==len(forbidden)==len(exclusion)==1:
        return {'position':_center(close[0]),'requirement':str(context[0].text)+' '+str(forbidden[0].text)+' '+str(exclusion[0].text)}
    return None

def findSpecialFormationDecline(items):
    positive=[i for i in items if float(i.score)>=.85]
    text=' '.join(_text(i) for i in positive)
    if not all(t in text for t in ('自动编成执行确认','不使用通常编队设置','的特殊关卡','是否进行自动编队')):return None
    buttons={name:[i for i in positive if _text(i)==name and 540<_center(i)[1]<640] for name in ('不进行自动编成','详细设定','自动编成')}
    return _center(buttons['不进行自动编成'][0]) if all(len(v)==1 for v in buttons.values()) else None

def isEventFormationBlocked(items):
    """Observed start refusal; background start button does not make it ready."""
    positive=[i for i in items if float(i.score)>=.85]
    header=[i for i in positive if _text(i)=='先发成员不足' and 50<_center(i)[1]<150]
    requirement=[i for i in positive if _text(i)=='先发成员需要凑足3人' and 180<_center(i)[1]<270]
    explanation=[i for i in positive if _text(i).rstrip('。.')=='才可开始执行任务' and 240<_center(i)[1]<320]
    return len(header)==len(requirement)==len(explanation)==1

def isEventAutoFormationSettings(items):
    positive=[i for i in items if float(i.score)>=.85]
    title=[i for i in positive if _text(i)=='自动编成' and 100<_center(i)[1]<180]
    text=' '.join(_text(i) for i in positive)
    return len(title)==1 and '基于职阶相性考虑的基础上' in text and '自动编成攻击力高的从者' in text and '编队方法' in text

def isEventIncompleteFormation(items):
    # Actual special-party layout: slots 2/3 must not be empty when three
    # starting members are required. This never chooses replacement servants.
    restricted=[i for i in items if float(i.score)>=.85 and _text(i)=='受限' and _center(i)[1]<100]
    empty=[i for i in items if float(i.score)>=.85 and _text(i)=='选择' and 250<_center(i)[0]<630 and 260<_center(i)[1]<340]
    return len(restricted)==1 and bool(empty)

def findTemporaryPartyDecision(items,*,readContext=False):
    positive=[i for i in items if float(i.score)>=.85]
    title=[i for i in positive if _text(i)=='队伍编制' and _center(i)[0]>1000 and _center(i)[1]<100]
    restricted=[i for i in positive if _text(i)=='受限' and _center(i)[1]<100]
    if not restricted:
        heading=[i for i in positive if _text(i)=='编成限制' and 500<_center(i)[0]<800 and _center(i)[1]<65]
        condition=[i for i in positive if re.fullmatch(r'请将[\u4e00-\u9fff]{2,12}设置为首发队员[。.]?',_text(i)) and 400<_center(i)[0]<900 and 65<_center(i)[1]<105]
        fixed=[i for i in positive if _text(i)=='编队限制' and _center(i)[0]<250 and 300<_center(i)[1]<390]
        if len(heading)==len(condition)==len(fixed)==1:restricted=heading
    instruction=[i for i in positive if _text(i).rstrip('。.')=='拖动修改从者配置' and 600<_center(i)[1]<660]
    cancel=[i for i in positive if _text(i)=='取消' and _center(i)[0]<250 and _center(i)[1]>640]
    decision=[i for i in (items if readContext else positive) if _text(i)=='决定' and (not readContext or i.score>=.65) and _center(i)[0]>1050 and _center(i)[1]>640]
    return _center(decision[0]) if len(title)==len(restricted)==len(instruction)==len(cancel)==len(decision)==1 and not isEventIncompleteFormation(items) else None

def findEventRewardReceipt(items):
    # Observed automatic completion receipt, not a reward selection/claim list.
    if _unsafeEventOverlay(items):return None
    positive=[i for i in items if float(i.score)>=.85]
    headers=[i for i in positive if _text(i)=='任务完成' and 150<_center(i)[0]<600 and 50<_center(i)[1]<200]
    earned=[i for i in positive if _text(i)=='获得报酬' and 650<_center(i)[0]<1150 and 50<_center(i)[1]<200]
    amount=[i for i in positive if re.fullmatch(r'获得.+[×x]\d+[!！]?',_text(i)) and 450<_center(i)[1]<600]
    footer=[i for i in positive if _text(i)=='请点击游戏界面' and 400<_center(i)[0]<900 and 600<_center(i)[1]<700]
    return _center(footer[0]) if len(headers)==len(earned)==len(amount)==len(footer)==1 else None

def findEventItemReceipt(items):
    """Observed automatically awarded card; no inventory/choice action."""
    if findEventServantReceipt(items):return findEventServantReceipt(items)
    if _unsafeEventOverlay(items):return None
    positive=[i for i in items if float(i.score)>=.85]
    if any(_text(i) in ('强化','召唤','决定','取消','选择','装备') for i in items):return None
    kind=[i for i in positive if _text(i)=='概念礼装' and 570<_center(i)[0]<720 and 580<_center(i)[1]<650]
    health=[i for i in positive if _text(i)=='生命值' and 700<_center(i)[0]<830 and 580<_center(i)[1]<650]
    value=[i for i in positive if re.fullmatch(r'(?:\+\d+|0)',_text(i)) and 450<_center(i)[0]<600 and 625<_center(i)[1]<675]
    footer=[i for i in positive if _text(i)=='请点击游戏界面' and 450<_center(i)[0]<850 and 670<_center(i)[1]<720]
    return _center(footer[0]) if len(kind)==len(health)==len(value)==len(footer)==1 else None

def findEventServantReceipt(items):
    if _unsafeEventOverlay(items):return None
    if any(_text(i) in ('强化','召唤','决定','取消','选择','装备') for i in items):return None
    strong=[i for i in items if float(i.score)>=.85]
    kind=[i for i in strong if _text(i)=='lancer' and 570<_center(i)[0]<720 and 540<_center(i)[1]<590]
    attack=[i for i in strong if _text(i)=='攻击力' and 450<_center(i)[0]<600 and 600<_center(i)[1]<635]
    health=[i for i in strong if _text(i)=='生命值' and 700<_center(i)[0]<830 and 600<_center(i)[1]<635]
    values=[[i for i in strong if re.fullmatch(r'\d+',_text(i)) and lo<_center(i)[0]<hi and 625<_center(i)[1]<675] for lo,hi in ((450,600),(680,830))]
    footer=[i for i in strong if _text(i)=='请点击游戏界面' and 450<_center(i)[0]<850 and 670<_center(i)[1]<720]
    # The observed full card/text band opens its information page. The
    # instruction explicitly allows touching the game canvas; use the clear
    # right-hand background outside that card, only after all receipt proofs.
    return (1000,690) if len(kind)==len(attack)==len(health)==len(footer)==1 and all(len(v)==1 for v in values) else None

def eventServantDetailProof(items):
    if _unsafeEventOverlay(items):return False
    strong=[i for i in items if float(i.score)>=.85]
    for name,(lo,hi) in (('能力',(500,700)),('资料',(700,900)),('战斗形象',(900,1100)),('语音',(1100,1280))):
        if sum(_text(i)==name and lo<_center(i)[0]<hi and 100<_center(i)[1]<180 for i in strong)!=1:return False
    classLabel=[i for i in strong if _text(i)=='枪兵' and _center(i)[0]>1100 and 50<_center(i)[1]<100]
    skills=[i for i in strong if _text(i)=='持有技能' and 500<_center(i)[0]<700 and 590<_center(i)[1]<650]
    return len(classLabel)==len(skills)==1

def eventItemDetailProof(items):
    if eventServantDetailProof(items):return True
    if _unsafeEventOverlay(items):return False
    positive=[i for i in items if float(i.score)>=.85]
    kind=[i for i in positive if _text(i)=='概念礼装' and _center(i)[0]>1100 and _center(i)[1]<100]
    ability=[i for i in positive if _text(i)=='能力' and 500<_center(i)[0]<700 and 100<_center(i)[1]<180]
    info=[i for i in positive if _text(i)=='详细信息' and 700<_center(i)[0]<900 and 100<_center(i)[1]<180]
    skills=[i for i in positive if _text(i)=='持有技能' and 500<_center(i)[0]<700 and 450<_center(i)[1]<520]
    return len(kind)==len(ability)==len(info)==len(skills)==1

def findEventItemDetailClose(items):
    if not eventItemDetailProof(items):return None
    close=[i for i in items if float(i.score)>=.85 and _text(i)=='关闭' and _center(i)[0]<100 and _center(i)[1]<100]
    return _center(close[0]) if len(close)==1 else None

def missionRewardReceipt(items):
    if _unsafeEventOverlay(items):return None
    strong=[i for i in items if float(i.score)>=.85]
    obtained=[i for i in strong if _text(i)=='获得了' and 500<_center(i)[0]<800 and 350<_center(i)[1]<430]
    amounts=[i for i in strong if re.fullmatch(r'[『「]?[^『「』」]+[×x]\d+[』」]?[。.]*',_text(i)) and 400<_center(i)[0]<900 and 400<_center(i)[1]<470]
    close=[i for i in strong if _text(i)=='关闭' and 450<_center(i)[0]<850 and 480<_center(i)[1]<590]
    mission=[i for i in strong if re.fullmatch(r'编号\d+',_text(i)) and _center(i)[0]>1100 and 260<_center(i)[1]<500]
    if len(obtained)!=1 or len(amounts)!=1 or len(close)!=1 or len(mission)!=1:return None
    counts=[i for i in strong if re.fullmatch(r'\d+/\d+',_text(i)) and 900<_center(i)[0]<1050 and 35<_center(i)[1]<90]
    before=int(_text(counts[0]).split('/')[0]) if len(counts)==1 else None
    return {'position':_center(close[0]),'reward':_text(amounts[0]).strip('『「』」。.'),'beforeCount':before,'mission':int(re.search(r'\d+',_text(mission[0]))[0])}

def findEventTutorialNext(items):
    if _unsafeEventOverlay(items):return None
    notice=findTemporaryServantNoticeClose(items)
    if notice is not None:return notice
    strong=[i for i in items if float(i.score)>=.85]
    instruction=[i for i in strong if _text(i)=='点击界面右上方的' and 250<_center(i)[0]<600 and _center(i)[1]<100]
    reward=[i for i in strong if _text(i)=='活动报酬按钮' and 250<_center(i)[0]<600 and 65<_center(i)[1]<140]
    ce=[i for i in strong if _text(i)=='装备活动限定概念礼装' and 250<_center(i)[0]<650 and 340<_center(i)[1]<440]
    story=[i for i in strong if _text(i)=='推进主线剧情' and 800<_center(i)[0]<1100 and 340<_center(i)[1]<440]
    forward=[i for i in strong if _text(i)=='前进' and 1000<_center(i)[0]<1250 and 620<_center(i)[1]<720]
    if len(instruction)==len(reward)==len(ce)==len(story)==len(forward)==1:return _center(forward[0])
    title=[i for i in strong if _text(i)=='任务报酬的领取方法' and 400<_center(i)[0]<900 and 40<_center(i)[1]<140]
    click=[i for i in strong if _text(i)=='点击进度为' and 700<_center(i)[0]<1000 and 300<_center(i)[1]<400]
    board=[i for i in strong if _text(i)=='的任务板' and 1000<_center(i)[0]<1230 and 300<_center(i)[1]<400]
    claim=[i for i in strong if _text(i)=='领取对应报酬' and 850<_center(i)[0]<1150 and 350<_center(i)[1]<440]
    if len(title)==len(click)==len(board)==len(claim)==len(forward)==1:return _center(forward[0])
    close=[i for i in items if _text(i)=='x' and (float(i.score)>=.85 or getattr(i,'visualProof',False)) and _center(i)[0]>1200 and _center(i)[1]<75]
    return _center(close[0]) if eventTutorialCloseProof(items) and len(close)==1 else None

def eventTutorialCloseProof(items):
    if eventMissionUnlockTutorialProof(items):return True
    strong=[i for i in items if float(i.score)>=.85]
    title=[i for i in strong if _text(i)=='任务列表的显示切换' and 400<_center(i)[0]<900 and 40<_center(i)[1]<140]
    change=[i for i in strong if _text(i)=='列表将进行切换' and 900<_center(i)[0]<1250 and 150<_center(i)[1]<250]
    instructions=[i for i in strong if _text(i).replace('，','').replace(',','')=='每当点击按钮列表中所显示的任务将进行切换' and 300<_center(i)[0]<1000 and 570<_center(i)[1]<650]
    states=[name for name in ('全部','未开放','可领取','已达成') if sum(_text(i)==name and 470<_center(i)[1]<550 for i in strong)==1]
    return len(title)==len(change)==len(instructions)==1 and len(states)==4 and not _unsafeEventOverlay(items)

def findTemporaryServantNoticeClose(items):
    # Observed passive explanation of an already granted temporary servant.
    # OCR confuses 入/人 in these two fixed phrases; no servant name is used.
    if _unsafeEventOverlay(items):return None
    strong=[i for i in items if float(i.score)>=.85]
    title=[i for i in strong if re.fullmatch(r'关于暂时加[入人]状态的从者',_text(i).strip('~～')) and 400<_center(i)[0]<900 and 100<_center(i)[1]<180]
    limited=[i for i in strong if _text(i).rstrip('。.')=='活动期间限时加入' and 400<_center(i)[0]<900 and 280<_center(i)[1]<360]
    quest=[i for i in strong if _text(i)=='在活动中通关特定关卡后' and 400<_center(i)[0]<900 and 370<_center(i)[1]<450]
    permanent=[i for i in strong if re.fullmatch(r'即可正式加[入人][。.]?',_text(i)) and 400<_center(i)[0]<900 and 430<_center(i)[1]<490]
    close=[i for i in strong if _text(i)=='关闭' and 500<_center(i)[0]<800 and 520<_center(i)[1]<610]
    return _center(close[0]) if len(title)==len(limited)==len(quest)==len(permanent)==len(close)==1 else None

def eventMissionUnlockTutorialProof(items):
    # Actual post-claim instructional page, not a main-quest requirement.
    if _unsafeEventOverlay(items):return False
    strong=[i for i in items if float(i.score)>=.85]
    proofs=(('完成任务后将解锁新任务',(400,900,40,140)),
            ('开放新任务',(900,1250,200,300)),
            ('完成任务不仅可以获得各种奖励',(300,1000,480,570)),
            ('还可以解锁新任务',(350,900,550,640)))
    for text,(x1,x2,y1,y2) in proofs:
        matches=[i for i in strong if _text(i).rstrip('，,。.!！?？')==text and x1<_center(i)[0]<x2 and y1<_center(i)[1]<y2]
        if len(matches)!=1:return False
    return True

def eventTutorialKey(items):
    if findEventTutorialNext(items) is None:return None
    if findTemporaryServantNoticeClose(items):return 'temporary-servant-info'
    if eventMissionUnlockTutorialProof(items):return 'mission-unlock'
    if eventTutorialCloseProof(items):return 'mission-display'
    return 'mission-rewards' if any(_text(i)=='任务报酬的领取方法' for i in items) else 'overview'

def eventWorldMapControls(items):
    """Independent controls on the observed event world map, not a quest row."""
    if _unsafeEventOverlay(items):return False
    positive=[i for i in items if float(i.score)>=.85]
    home=[i for i in positive if _text(i)=='管理室' and _center(i)[0]<220 and _center(i)[1]<100]
    reward=[i for i in positive if _text(i)=='活动报酬' and _center(i)[0]>1100 and _center(i)[1]<100]
    menu=[i for i in positive if _text(i)=='菜单' and _center(i)[0]>1100 and _center(i)[1]>600]
    # The mission counter alternates with event currency, so it is not an
    # invariant. The producer additionally requires a proved next-area pair.
    return len(home)==len(reward)==len(menu)==1

def findNextEventArea(items):
    if not eventWorldMapControls(items):return None
    markers=[i for i in items if float(i.score)>=.85 and _text(i)=='下一个' and 150<_center(i)[1]<450]
    if len(markers)!=1:return None
    x,y=_center(markers[0])
    areas=[i for i in items if float(i.score)>=.85 and 2<=len(_text(i))<=12 and abs(_center(i)[0]-x)<45 and 120<_center(i)[1]-y<300]
    if len(areas)!=1:return None
    area=areas[0]
    return {'title':str(area.text),'position':_center(area)}

def classifyEventState(items,flags=None):
    flags=flags or {}
    # Confirmations can cover a still-recognizable support/formation background.
    if _isStartQuestConfirmation(items):return 'start_confirmation'
    if findSkipConfirmation(items):return 'story_skip_confirmation'
    if flags.get('ap_empty'):return 'ap_empty'
    if flags.get('defeated'):return 'battle_defeated'
    if flags.get('friend_request'):return 'friend_request'
    if flags.get('battle_continue'):return 'continue'
    if _unsafeEventOverlay(items):return 'unsafe_modal'
    if missionRewardReceipt(items):return 'mission_reward_receipt'
    if findMissionItemInfoClose(items):return 'item_information'
    if findEventQuestInfoClose(items):return 'quest_information'
    if eventQuestInfoContext(items):return 'unknown'
    if findFormationRestrictionNotice(items):return 'formation_restriction_notice'
    if isEventFormationBlocked(items):return 'formation_blocked'
    if isEventAutoFormationSettings(items):return 'formation_settings'
    if findTemporaryPartyDecision(items):return 'formation_review'
    if findEventRewardReceipt(items):return 'reward_receipt'
    if findEventItemReceipt(items):return 'item_receipt'
    if findEventItemDetailClose(items):return 'item_detail'
    if findEventTutorialNext(items):return 'event_tutorial'
    if findSpecialFormationDecline(items):return 'special_formation_offer'
    if flags.get('choose_friend'):return 'support'
    if flags.get('formation'):return 'formation'
    if flags.get('battle'):return 'battle'
    if flags.get('battle_result'):return 'battle_result'
    if _isStory(items,flags):return 'story'
    if flags.get('main_interface') and findNextEventArea(items):return 'event_world_map'
    if any(_text(item)=='每日任务' and _center(item)[0]>=900 and _center(item)[1]<95 for item in items):return 'daily_quest'
    if flags.get('main_interface') and findLockedEventMission(items):return 'mission_gate'
    if _eventMap(items):return 'event_map'
    if _missionListConfirmed(items):return 'mission_list'
    if _eventAnchor(items):return 'home'
    if findMissionGate(items) and not _missionListContext(items):return 'mission_gate'
    return 'unknown'

def findSkipButton(items):
    candidates=[item for item in items if _text(item) in ('skip','跳过') and _center(item)[0]>=850 and _center(item)[1]<=180]
    return _center(candidates[0]) if len(candidates)==1 and _reliable(candidates[0]) else None

def findSkipConfirmation(items):
    text=' '.join(_text(item) for item in items if _reliable(item))
    if '是否跳过该段剧情' in text:
        yes=[i for i in items if _reliable(i) and _text(i)=='是' and 650<_center(i)[0]<1000 and 480<_center(i)[1]<620]
        no=[i for i in items if _reliable(i) and _text(i)=='否' and 250<_center(i)[0]<600 and 480<_center(i)[1]<620]
        if len(yes)==len(no)==1:return _center(yes[0])
        return None
    if not any(token in text for token in ('跳过剧情','跳过故事','skipstory')):return None
    if not any(token in text for token in ('取消','cancel')):return None
    candidates=[item for item in items if _text(item) in ('确认','确定','ok','confirm')]
    return _center(candidates[0]) if len(candidates)==1 and _reliable(candidates[0]) else None

def findClaimableMissionReward(items):
    if _unsafeEventOverlay(items):return None
    for row in _rows(items,delta=60):
        rowText=' '.join(_text(item) for item in row['items'])
        positiveText=' '.join(_text(item) for item in row['items'] if _reliable(item))
        if not any(token in positiveText for token in ('已完成','可领取')):continue
        if any(token in rowText for token in ('选择奖励','请选择','任选','兑换','商店')):continue
        buttons=[item for item in row['items'] if _text(item) in ('领取','领取奖励')]
        if len(buttons)==1 and _reliable(buttons[0]):return _center(buttons[0])
    return None

def findMissionListEntry(items):
    candidates=[item for item in items if _text(item) in ('任务进行度','任务进度','活动任务','任务列表') and 600<=_center(item)[0]<=1120 and _center(item)[1]<360]
    return _center(candidates[0]) if len(candidates)==1 and _reliable(candidates[0]) else None

def _missionReturnButton(items):
    candidates=[item for item in items if _text(item) in ('关闭','返回') and _center(item)[0]<250 and _center(item)[1]<120]
    return _center(candidates[0]) if len(candidates)==1 and _reliable(candidates[0]) else None

def findEventBattleStart(items):
    if findFormationRestrictionNotice(items) or isEventFormationBlocked(items) or isEventAutoFormationSettings(items) or isEventIncompleteFormation(items) or findTemporaryPartyDecision(items):return None
    tokens=('开始任务','开始战斗','战斗开始','出击')
    candidates=[item for item in items if _text(item) in tokens and _center(item)[0]>=800 and _center(item)[1]>=470]
    return _center(candidates[0]) if len(candidates)==1 and _reliable(candidates[0]) else None

def findBattleProgressButton(items):
    tokens=('下一步','继续','next')
    candidates=[item for item in items if _text(item) in tokens and _center(item)[0]>=800 and _center(item)[1]>=470]
    return _center(candidates[0]) if len(candidates)==1 and _reliable(candidates[0]) else None

def _missionListContext(items):
    """Partial list evidence only prevents treating background locks as modal.

    It never authorizes a claim or return input. Full list proof is still needed.
    """
    strong=[i for i in items if float(i.score)>=.85]
    anchors=(
        any(_text(i)=='关闭' and _center(i)[0]<220 and _center(i)[1]<100 for i in strong),
        any(_text(i)=='任务报酬' and 650<_center(i)[0]<850 and 100<_center(i)[1]<180 for i in strong),
        any(_text(i)=='活动道具兑换' and 1000<_center(i)[0]<1250 and 100<_center(i)[1]<180 for i in strong),
        any(_text(i)=='任务报酬一览' and 800<_center(i)[0]<1100 and 175<_center(i)[1]<230 for i in strong),
        any(_text(i)=='已达成的任务' and 600<_center(i)[0]<800 and 220<_center(i)[1]<270 for i in strong))
    return sum(anchors)>=3

def _missionListConfirmed(items):
    titles=[i for i in items if _text(i) in ('活动任务列表','活动任务','eventmissions') and _reliable(i) and 100<=_center(i)[0]<=1240 and 0<=_center(i)[1]<180]
    if len(titles)==1 and _center(titles[0])[1]>=100 and not _unsafeEventOverlay(items):return True
    if _unsafeEventOverlay(items):return False
    if any(_text(i) in ('关闭','取消','确定','是','否') and 400<_center(i)[0]<900 and 350<_center(i)[1]<620 for i in items):return False
    strong=[i for i in items if float(i.score)>=.85]
    tab=[i for i in strong if _text(i)=='任务报酬' and 650<_center(i)[0]<850 and 100<_center(i)[1]<180]
    exchange=[i for i in strong if _text(i)=='活动道具兑换' and 1000<_center(i)[0]<1250 and 100<_center(i)[1]<180]
    heading=[i for i in strong if _text(i)=='任务报酬一览' and 800<_center(i)[0]<1100 and 175<_center(i)[1]<230]
    completed=[i for i in strong if _text(i)=='已达成的任务' and 600<_center(i)[0]<800 and 220<_center(i)[1]<270]
    count=missionCompletedCount(items)
    close=[i for i in strong if _text(i)=='关闭' and _center(i)[0]<220 and _center(i)[1]<100]
    filters=[i for i in strong if _text(i) in ('全部','未开放','进行中','可领取','已达成') and _center(i)[0]>1100 and 220<_center(i)[1]<270]
    numbers=[i for i in strong if re.fullmatch(r'编号\d+',_text(i)) and _center(i)[0]>1100 and 260<_center(i)[1]<650]
    progress=[i for i in strong if _text(i)=='目标进行度' and 580<_center(i)[0]<800 and _center(i)[1]>280]
    structure=len(heading)==1 or len(filters)==1 and bool(numbers and progress)
    return len(tab)==len(exchange)==len(completed)==len(close)==1 and structure and count is not None

def eventQuestInfoContext(items):
    return any(float(i.score)>=.85 and _text(i)=='关卡情报' and 250<_center(i)[0]<400 and 90<_center(i)[1]<145 for i in items)


def eventQuestInfoProof(items):
    if _unsafeEventOverlay(items):return False
    strong=[i for i in items if float(i.score)>=.85]
    title=[i for i in strong if _text(i)=='关卡情报' and 250<_center(i)[0]<400 and 90<_center(i)[1]<145]
    instruction=[i for i in strong if '可点击' in _text(i) and '战利品' in _text(i) and '敌人' in _text(i) and '切换' in _text(i) and 200<_center(i)[0]<700 and _center(i)[1]<80]
    body=[i for i in strong if _text(i) in ('之前在该关卡中获得的战利品一览。','此为过去在此关卡中所遇到过的敌人一览') and 100<_center(i)[0]<550 and 210<_center(i)[1]<255]
    tab=[i for i in strong if _text(i)=='战利品' and 100<_center(i)[0]<300 and 150<_center(i)[1]<210]
    return len(title)==1 and (len(instruction)==1 or len(body)==len(tab)==1)


def findEventQuestInfoClose(items):
    if not eventQuestInfoProof(items):return None
    close=[i for i in items if float(i.score)>=.85 and _text(i)=='关闭' and 250<_center(i)[0]<400 and 630<_center(i)[1]<700]
    return _center(close[0]) if len(close)==1 else None


def findEventQuestEnemyTab(items):
    if findEventQuestInfoClose(items) is None:return None
    tabs=[i for i in items if float(i.score)>=.85 and _text(i)=='敌人' and 400<_center(i)[0]<500 and 150<_center(i)[1]<210]
    return _center(tabs[0]) if len(tabs)==1 else None


def missionItemInfoProof(items):
    if _unsafeEventOverlay(items) or not _missionListContext(items):return False
    strong=[i for i in items if float(i.score)>=.85]
    kind=[i for i in strong if _text(i).strip('【】[]')=='灵基再临素材' and 400<_center(i)[0]<900 and 270<_center(i)[1]<335]
    origin=[i for i in strong if re.fullmatch(r'获得的.+[。.]',_text(i)) and 400<_center(i)[0]<900 and 335<_center(i)[1]<400]
    passive=[i for i in strong if _text(i).rstrip('。.')=='构造保密' and 400<_center(i)[0]<900 and 380<_center(i)[1]<440]
    return len(kind)==len(origin)==len(passive)==1


def findMissionItemInfoClose(items):
    if not missionItemInfoProof(items):return None
    close=[i for i in items if float(i.score)>=.85 and _text(i)=='关闭' and 500<_center(i)[0]<800 and 480<_center(i)[1]<550]
    return _center(close[0]) if len(close)==1 else None

def findMissionCard(items,number):
    if not _missionListConfirmed(items):return None
    headers=[i for i in items if float(i.score)>=.85 and _text(i)==f'编号{int(number)}' and _center(i)[0]>1100 and 270<_center(i)[1]<540]
    if len(headers)!=1:return None
    y=_center(headers[0])[1]
    conditions=[i for i in items if float(i.score)>=.85 and 590<_center(i)[0]<1080 and y+5<_center(i)[1]<y+80 and _text(i) not in ('目标进行度','达成报酬') and '后开放下一个主线关卡' not in _text(i) and not re.fullmatch(r'[?？]+',_text(i))]
    progress=[i for i in items if float(i.score)>=.85 and _text(i)=='目标进行度' and 590<_center(i)[0]<800 and y+60<_center(i)[1]<y+130]
    count=[i for i in items if float(i.score)>=.85 and re.fullmatch(r'\d+/\d+',_text(i)) and 580<_center(i)[0]<1000 and y+95<_center(i)[1]<y+150]
    if not conditions or len(progress)!=1 or len(count)!=1:return None
    condition=' '.join(str(i.text) for i in sorted(conditions,key=lambda i:(_center(i)[1],_center(i)[0])))
    compact=normalizeText(condition)
    if not re.search(r'(?:击败|收集|通关|完成|达到|获得|使用|装备|编入|进行)',compact):return None
    if compact.count('(')!=compact.count(')'):return None
    return {'mission':int(number),'condition':condition,'progress':_text(count[0]),'position':_center(headers[0])}

def missionCompletedCount(items):
    counts=[i for i in items if float(i.score)>=.85 and re.fullmatch(r'\d+/\d+',_text(i)) and 800<_center(i)[0]<950 and 220<_center(i)[1]<270]
    if len(counts)!=1:return None
    completed,total=map(int,_text(counts[0]).split('/'))
    return completed if 0<=completed<=total and total>0 else None

def findCompletedMissionCard(items,target=None):
    if not _missionListConfirmed(items):return None
    strong=[i for i in items if float(i.score)>=.85]
    cards=[]
    for number in strong:
        matched=re.fullmatch(r'编号(\d+)',_text(number))
        if not matched or _center(number)[0]<1100 or not 260<_center(number)[1]<650:continue
        if target is not None and int(matched.group(1))!=int(target):continue
        top=_center(number)[1]-24
        row=[i for i in strong if _center(i)[0]>580 and top<=_center(i)[1]<top+150]
        claim=[i for i in row if _text(i)=='可领取']
        completed=[i for i in row if _text(i)=='已完成']
        progress=[i for i in row if re.fullmatch(r'\d+/\d+',_text(i)) and _center(i)[0]<750]
        label=[i for i in row if _text(i)=='目标进行度']
        if len(claim)!=1 or len(completed)!=1 or len(progress)!=1 or len(label)!=1:continue
        done,total=map(int,_text(progress[0]).split('/'))
        if total<=0 or done!=total:continue
        if any(t in ' '.join(_text(i) for i in row) for t in ('未开放','选择奖励','任选')):continue
        title=[i for i in items if _reliable(i) and 580<_center(i)[0]<1100 and top+30<_center(i)[1]<top+90 and any(t in _text(i) for t in ('通关','击败','收集','达成','完成'))]
        cards.append({'mission':int(matched.group(1)),'title':str(title[0].text) if len(title)==1 else '', 'position':_center(claim[0]),'progress':(done,total)})
    return min(cards,key=lambda v:v['position'][1]) if cards else None

def _detectFlags(detect):
    return {
        'choose_friend':detect.isChooseFriend(),
        'formation':detect.isBattleFormation(),
        'battle':detect.isTurnBegin(),
        'battle_result':detect.isBattleFinished(),
        'ap_empty':getattr(detect,'isApEmpty',lambda:False)(),
        'defeated':getattr(detect,'isBattleDefeated',lambda:False)(),
        'friend_request':getattr(detect,'isAddFriend',lambda:False)(),
        'battle_continue':getattr(detect,'isBattleContinue',lambda:False)(),
    }

def _readScreen(detect):return ocrScreen(detect.im)

def _waitClassified(maxChecks=20,exclude=()):
    for _ in range(maxChecks):
        detect=Detect(.3)
        items=_readScreen(detect)
        state=classifyEventState(items,_detectFlags(detect))
        if state!='unknown' and state not in exclude:return detect,items,state
    return detect,items,'unknown'

def _skipStory(items):
    position=findSkipButton(items)
    if not position:return {'state':'blocked','message':'剧情跳过模式已选择，但未能可靠识别唯一的 SKIP/跳过按钮，已停止。'}
    fgoDevice.device.touch(position)
    for _ in range(12):
        detect=Detect(.3); confirmItems=_readScreen(detect)
        if position:=findSkipConfirmation(confirmItems):
            fgoDevice.device.touch(position)
            break
        schedule.sleep(.2)
    else:return {'state':'blocked','message':'未识别到包含跳过剧情与取消按钮的确认弹窗；没有点击确认。'}
    for _ in range(30):
        detect=Detect(.4); afterItems=_readScreen(detect)
        afterState=classifyEventState(afterItems,_detectFlags(detect))
        if afterState in ('event_map','support','formation','battle'):
            return {'state':'story_skipped','message':'已通过正向识别的按钮跳过剧情。'}
        if afterState in ('home','mission_gate'):
            return {'state':'blocked','message':'跳过后到达非活动地图状态，已停止。'}
        schedule.sleep(.2)
    return {'state':'blocked','message':'确认跳过后剧情界面仍未结束，已停止。'}

def _eventMap(items):
    text=' '.join(_text(item) for item in items)
    hasMapHeader=any('关卡举办时间' in _text(item) for item in items)
    hasEventControls=any(token in text for token in ('活动奖励','活动报酬')) and any(token in text for token in ('任务进行度','任务进度'))
    hasNode=findNextMainQuest(items) is not None
    positive=[i for i in items if float(i.score)>=.85]
    close=[i for i in positive if _text(i)=='关闭' and _center(i)[0]<220 and _center(i)[1]<100]
    reward=[i for i in positive if _text(i)=='活动报酬' and _center(i)[0]>1100 and _center(i)[1]<100]
    ap=[i for i in positive if re.fullmatch(r'ap[0-9o]+',_text(i)) and 750<_center(i)[0]<1000 and 180<_center(i)[1]<600]
    story=[i for i in positive if _text(i)=='无战斗' and _center(i)[0]>1100 and 100<_center(i)[1]<600]
    # This identifies the area list even when its decorated title momentarily
    # disappears from OCR. It does not authorize selecting any absent title.
    locked=[i for i in positive if re.fullmatch(r'完成任务no[.．]?\d+后开放',_text(i)) and 750<_center(i)[0]<1100 and 100<_center(i)[1]<250]
    main=[i for i in positive if re.fullmatch(r'主线关卡第[一二三四五六七八九十百0-9]+话',_text(i)) and 750<_center(i)[0]<1100 and 100<_center(i)[1]<180]
    # A locked battle row has no 'no battle' label, and the progress heading
    # can be misread. Its unique real lock and main-row heading provide an
    # independent area-list proof; they never authorize starting the lock.
    areaList=len(close)==len(reward)==1 and bool(ap) and (bool(story) or len(locked)==len(main)==1)
    return bool(hasMapHeader and (hasNode or hasEventControls or areaList))

def _openEventMap(detect,items):
    import fgoNavigation
    guard=fgoNavigation.NavigationGuard('活动入口',90,20)
    closes=scrolls=waits=0
    for _ in range(20):
        guard.check()
        state=classifyEventState(items,_detectFlags(detect))
        if state in ('event_map','mission_list','mission_gate','story','start_confirmation','support','formation','battle','battle_result','ap_empty','battle_defeated','friend_request','unsafe_modal'):return detect,items
        gateHeader=any(_text(i)=='迦勒底之门' and _center(i)[0]>=900 and _center(i)[1]<95 for i in items)
        close=[i for i in items if _text(i)=='关闭' and _reliable(i) and _center(i)[0]<200 and _center(i)[1]<95]
        home=any(_text(i)=='通知' and _reliable(i) and _center(i)[0]<200 and _center(i)[1]<95 for i in items)
        if (state=='daily_quest' or gateHeader) and len(close)==1:
            if closes>=2:raise ScriptStop('返回活动入口的目录层级异常，已停止')
            fgoDevice.device.touch(_center(close[0]));closes+=1;waits=0
            schedule.sleep(.8)
        elif home:
            anchor=_eventAnchor(items)
            if anchor and _center(anchor)[1]>=220:
                # The timer is below the event banner, not inside its tap target.
                x,y=_center(anchor)
                fgoDevice.device.touch((x,y-70))
                detect,items,state=_waitClassified(25,exclude=('home','daily_quest'))
                if state!='event_map':raise ScriptStop('点击活动入口后未确认活动地图，已停止')
                return detect,items
            if scrolls>=EVENT_SCROLL_LIMIT:raise ScriptStop('当前主目录未唯一确认活动入口，已停止')
            detect,_=fgoQuickQuest._swipe(detect,True);scrolls+=1;waits=0
            items=_readScreen(detect);continue
        elif closes and waits<3:
            waits+=1;schedule.sleep(.5)
        else:raise ScriptStop('当前界面未被可靠识别为活动地图或导航目录，已停止')
        detect=Detect(.3);items=_readScreen(detect)
    raise ScriptStop('返回活动入口超时，已停止')

def _missionRewardGate(items,autoClaim):
    gates=findMissionGate(items)
    if not gates:return None
    if not autoClaim:return {'state':'mission_blocked','message':'活动推进暂时被任务条件阻挡：'+'；'.join(gates)}
    if not _missionListConfirmed(items):return {'state':'mission_blocked','message':'活动推进暂时被任务条件阻挡；请先在活动任务列表手动领取可领取奖励。当前画面未可靠识别为活动任务列表。'}
    position=findClaimableMissionReward(items)
    if not position:return {'state':'mission_blocked','message':'活动推进暂时被任务条件阻挡；奖励开关已开，但当前界面没有可唯一确认的已完成领取项。'}
    return {'state':'claimable','position':position,'message':'仅发现明确标为已完成/可领取的奖励。'}

def _claimMissionRewards(detect,items):
    if _unsafeEventOverlay(items):return detect,items,{'state':'unsafe_modal','claimed':0,'message':'活动任务存在奖励选择或确认弹窗，已停止；没有点击背景领取或返回按钮。'}
    if not _missionListConfirmed(items):return None,items,{'state':'mission_blocked','message':'当前页面未可靠识别为活动任务列表；没有领取奖励。'}
    claimed=0
    for _ in range(20):
        if _unsafeEventOverlay(items):return detect,items,{'state':'unsafe_modal','claimed':claimed,'message':'活动任务存在奖励选择或确认弹窗，已停止；没有点击背景领取或返回按钮。'}
        if not _missionListConfirmed(items):return detect,items,{'state':'mission_blocked','claimed':claimed,'message':'活动任务顶部标题不再被可靠确认，已停止；没有继续领取或返回。'}
        position=findClaimableMissionReward(items)
        if position:
            fgoDevice.device.touch(position);claimed+=1
            for _ in range(8):
                detect,items,state=_waitClassified(1)
                if state=='event_map':return detect,items,{'state':'event_map','claimed':claimed,'message':f'已领取 {claimed} 项明确完成的活动任务奖励并返回活动地图。'}
                if state=='unsafe_modal':return detect,items,{'state':'unsafe_modal','claimed':claimed,'message':'领取后出现奖励选择或确认弹窗，已停止；没有点击背景按钮。'}
                if state!='mission_list':return detect,items,{'state':'mission_blocked','claimed':claimed,'message':'领取后出现未识别的任务奖励界面，已停止。'}
                if findClaimableMissionReward(items)!=position:break
                schedule.sleep(.2)
            else:return detect,items,{'state':'mission_blocked','claimed':claimed,'message':'领取后奖励状态未变化，已停止以避免重复点击。'}
            continue
        position=_missionReturnButton(items)
        if not position:return detect,items,{'state':'mission_blocked','claimed':claimed,'message':'奖励检查完成，但未唯一识别返回活动地图按钮。'}
        fgoDevice.device.touch(position)
        detect,items,state=_waitClassified(25,exclude=('mission_list',))
        if state=='event_map':return detect,items,{'state':'event_map','claimed':claimed,'message':f'已领取 {claimed} 项明确完成的活动任务奖励并返回活动地图。'}
        return detect,items,{'state':'mission_blocked','claimed':claimed,'message':'点击返回后未确认活动地图，已停止。'}
    return detect,items,{'state':'mission_blocked','claimed':claimed,'message':'已达 20 项奖励领取上限，已停止。'}

def _runEventBattle(detect,items,state,friendPolicy,friendMaxRefresh):
    """Shared preparation/Battle/settlement; no second OCR result loop."""
    from fgoEventCycle import EventResourcePolicy,EventRunner
    runner=EventRunner(EventResourcePolicy(allowApples=False),friendPolicy=friendPolicy,friendMaxRefresh=friendMaxRefresh,storyMode=EVENT_STORY_PAUSE)
    try:
        detect,items,state=runner.runBattle()
        return detect,items,{'state':state,'battles':runner.main.completedAttempts,'battle':getattr(getattr(runner.main,'battleProc',None),'result',None),'message':'Shared BattleCycle completed.'}
    except ScriptStop as error:
        runner.evidence(error)
        return detect,items,{'state':'blocked','battles':runner.main.completedAttempts,'message':str(error)}


def progress(maxNodes=1,storyMode=EVENT_STORY_PAUSE,autoClaim=False,friendPolicy='first',friendMaxRefresh=2,resourcePolicy=None):
    """Conservative CN event state machine: unknown screens stop; story pauses by default."""
    if resourcePolicy is not None:
        from fgoEventCycle import EventRunner
        return EventRunner(resourcePolicy,friendPolicy=friendPolicy,friendMaxRefresh=friendMaxRefresh,storyMode=storyMode,autoClaim=autoClaim).run(maxNodes)
    if XDetect.region!='CN':return {'type':'EventProgress','state':'blocked','message':'活动推进首版仅适配简体中文服务器。'}
    maxNodes=max(1,min(EVENT_NODE_LIMIT,int(maxNodes)))
    if storyMode not in (EVENT_STORY_PAUSE,EVENT_STORY_SKIP):return {'type':'EventProgress','state':'blocked','message':'剧情策略无效，已停止。'}
    detect=Detect(.2)
    if detect.im.shape[:2]!=(720,1280):return {'type':'EventProgress','state':'blocked','message':'活动推进首版只允许 1280×720 横屏。'}
    items=_readScreen(detect)
    try:detect,items=_openEventMap(detect,items)
    except ScriptStop as error:return {'type':'EventProgress','state':'blocked','message':str(error)}
    nodes=0;battles=0;lastBattle=None
    for _ in range(maxNodes+20):
        flags=_detectFlags(detect)
        state=classifyEventState(items,flags)
        if state=='unsafe_modal':return {'type':'EventProgress','state':'unsafe_modal','nodes':nodes,'battles':battles,'message':'活动界面存在奖励选择、AP恢复、购买或确认弹窗，已停止；没有点击背景控件。'}
        if state in ('ap_empty','battle_defeated','friend_request','mission_gate'):
            messages={'ap_empty':'AP 不足，已停止；没有使用任何 AP 恢复。','battle_defeated':'战败界面，已停止；没有复活。','friend_request':'好友申请界面，请手动处理后继续。','mission_gate':'活动任务条件阻挡：'+'；'.join(findMissionGate(items))}
            return {'type':'EventProgress','state':'blocked','nodes':nodes,'battles':battles,'message':messages[state]}
        if state in ('support','formation','battle','battle_result'):
            if nodes==0:nodes=1
            detect,items,outcome=_runEventBattle(detect,items,state,friendPolicy,friendMaxRefresh)
            battles+=outcome.get('battles',0);lastBattle=outcome.get('battle',lastBattle)
            if outcome['state']=='event_map':continue
            return {'type':'EventProgress','nodes':nodes,'battles':battles,'battle':lastBattle,'message':outcome['message'],'state':outcome['state']}
        if state=='mission_list':
            if not autoClaim:return {'type':'EventProgress','state':'mission_blocked','nodes':nodes,'battles':battles,'message':'当前位于活动任务列表；自动领取已关闭，请手动检查任务奖励。'}
            detect,items,outcome=_claimMissionRewards(detect,items)
            if outcome['state']=='event_map':continue
            return {'type':'EventProgress','state':outcome['state'],'nodes':nodes,'battles':battles,'claimed':outcome.get('claimed',0),'message':outcome['message']}
        if state=='start_confirmation':
            return {'type':'EventProgress','state':'start_confirmation','nodes':nodes,'battles':battles,'message':'已到达关卡开始确认；为避免消耗 AP 或启动战斗，未点击“开始”。'}
        if state=='story':
            if storyMode==EVENT_STORY_PAUSE:
                return {'type':'EventProgress','state':'story_paused','nodes':nodes,'battles':battles,'message':'已进入剧情，请阅读完成后继续。未点击跳过。'}
            result=_skipStory(items)
            if result['state']!='story_skipped':return {'type':'EventProgress','state':result['state'],'nodes':nodes,'battles':battles,'message':result['message']}
            detect,items,state=_waitClassified(25)
        if state!='event_map':
            return {'type':'EventProgress','state':'blocked','nodes':nodes,'battles':battles,'message':'活动状态无法可靠分类，已安全停止。'}
        if nodes>=maxNodes:return {'type':'EventProgress','state':'limit_reached','nodes':nodes,'battles':battles,'battle':lastBattle,'message':f'已达到活动推进上限 {maxNodes}，等待再次启动后重新扫描。'}
        candidate=findNextMainQuest(items)
        if candidate and candidate.get('restrictions'):
            return {'type':'EventProgress','state':'blocked','nodes':nodes,'battles':battles,'message':'当前活动关卡有编队限制：'+'；'.join(candidate['restrictions'])+'。请手动确认；未选择关卡或修改编队。'}
        if candidate is None:
            if autoClaim:
                entry=findMissionListEntry(items)
                if entry:
                    fgoDevice.device.touch(entry)
                    detect,items,state=_waitClassified(25,exclude=('event_map',))
                    if state=='mission_list':
                        detect,items,outcome=_claimMissionRewards(detect,items)
                        if outcome['state']=='event_map':continue
                        return {'type':'EventProgress','state':outcome['state'],'nodes':nodes,'battles':battles,'claimed':outcome.get('claimed',0),'message':outcome['message']}
                    return {'type':'EventProgress','state':'mission_blocked','nodes':nodes,'battles':battles,'message':'点击 OCR 识别的活动任务入口后未确认任务列表，已停止且未领取奖励。'}
            gate=_missionRewardGate(items,autoClaim)
            if gate:return {'type':'EventProgress','nodes':nodes,'battles':battles,**gate}
            return {'type':'EventProgress','state':'no_main_quest','nodes':nodes,'battles':battles,'message':'活动地图未发现可确认的未完成主线；没有随机刷 Free Quest。'}
        if nodes>=maxNodes:return {'type':'EventProgress','state':'limit_reached','nodes':nodes,'battles':battles,'battle':lastBattle,'message':f'已达到活动推进上限 {maxNodes}，等待再次启动后重新扫描。'}
        fgoDevice.device.touch(candidate['position'])
        nodes+=1
        detect,items,state=_waitClassified(30,exclude=('event_map',))
        if state=='start_confirmation':
            return {'type':'EventProgress','state':'start_confirmation','nodes':nodes,'battles':battles,'message':'已到达关卡开始确认；为避免消耗 AP 或启动战斗，未点击“开始”。'}
        if state=='story':
            if storyMode==EVENT_STORY_PAUSE:return {'type':'EventProgress','state':'story_paused','nodes':nodes,'battles':battles,'message':'已进入剧情，请阅读完成后继续。未点击跳过。'}
            result=_skipStory(items)
            if result['state']!='story_skipped':return {'type':'EventProgress','state':result['state'],'nodes':nodes,'battles':battles,'message':result['message']}
            detect,items,state=_waitClassified(30)
        if state in ('support','formation','battle','battle_result'):
            detect,items,outcome=_runEventBattle(detect,items,state,friendPolicy,friendMaxRefresh)
            battles+=outcome.get('battles',0);lastBattle=outcome.get('battle',lastBattle)
            if outcome['state']=='event_map':continue
            return {'type':'EventProgress','nodes':nodes,'battles':battles,'battle':lastBattle,'message':outcome['message'],'state':outcome['state']}
        if state!='event_map':return {'type':'EventProgress','state':'blocked','nodes':nodes,'battles':battles,'message':'主线节点进入无法可靠识别的界面，已停止。'}
    return {'type':'EventProgress','state':'limit_reached','nodes':nodes,'battles':battles,'battle':lastBattle,'message':f'已达到活动推进上限 {maxNodes}，等待再次启动后重新扫描。'}

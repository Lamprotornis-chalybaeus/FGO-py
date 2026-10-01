from dataclasses import dataclass
import re,unicodedata
import fgoDevice
import fgoKernel
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
    matches=[item for item in items if '活动举办时间' in _text(item) and _center(item)[1]<260]
    return matches[0] if len(matches)==1 else None

def _isMainTitle(text):
    compact=normalizeText(text)
    return ('主线' in compact or '序幕' in compact or 'mainquest' in compact or 'mainstory' in compact or 'prologue' in compact or 'epilogue' in compact or bool(re.search(r'第[0-9一二三四五六七八九十]+[节幕]',compact)))

def findNextMainQuest(items):
    candidates=[]
    for row in _rows(items):
        rowItems=row['items']
        rowText=' '.join(_text(item) for item in rowItems)
        titleItems=[item for item in rowItems if _isMainTitle(_text(item))]
        if not titleItems:continue
        if any(token in rowText for token in ('已完成','通关','clear','complete')):continue
        isNew=any(token in rowText for token in ('new','新!','新！'))
        explicitMain=any(token in rowText for token in ('主线','mainquest','mainstory'))
        hasAp=any(re.search(r'ap\s*\d+',_text(item)) for item in rowItems)
        explicitEpisode=any(any(token in _text(item) for token in ('序幕','终幕','epilogue','prologue')) or bool(re.search(r'第[0-9一二三四五六七八九十]+[节幕]',_text(item))) for item in titleItems)
        if not (isNew or explicitMain or explicitEpisode) or not (hasAp or explicitEpisode):continue
        title=min(titleItems,key=lambda item:_center(item)[0])
        x,y=_center(title)
        candidates.append((0 if isNew else 1,y,title,(x,y),rowText))
    if not candidates:return None
    _,_,title,position,rowText=min(candidates,key=lambda v:(v[0],v[1]))
    return {'title':str(title.text),'position':position,'rowText':rowText}

def findMissionGate(items):
    result=[]
    verbs=('完成','击败','收集','通关','解锁','需要','达到')
    for item in items:
        text=str(getattr(item,'text','')).strip()
        compact=normalizeText(text)
        if '任务' not in compact or '任务进度' in compact or '任务进行度' in compact:continue
        if any(normalizeText(word) in compact for word in verbs):result.append(text)
    return result

def _isStory(items,flags=None):
    flags=flags or {}
    if flags.get('story'):return True
    allText=' '.join(_text(i) for i in items)
    if any(token in allText for token in ('活动举办时间','ap5','ap10','推荐职阶')):return False
    controls=[i for i in items if _text(i) in ('menu','菜单','skip','跳过') and _center(i)[1]<180]
    dialogue=[i for i in items if _center(i)[1]>=470 and len(_text(i))>=7]
    return bool(controls and dialogue)

def _isStartQuestConfirmation(items):
    text=' '.join(_text(item) for item in items)
    return '是否开始关卡' in text and sum(1 for item in items if _text(item)=='开始')==1 and sum(1 for item in items if _text(item)=='取消')==1

def classifyEventState(items,flags=None):
    flags=flags or {}
    if flags.get('choose_friend'):return 'support'
    if flags.get('formation'):return 'formation'
    if flags.get('battle'):return 'battle'
    if flags.get('battle_result'):return 'battle_result'
    if _isStartQuestConfirmation(items):return 'start_confirmation'
    if _isStory(items,flags):return 'story'
    if any('每日任务' in _text(item) for item in items):return 'daily_quest'
    if _eventMap(items):return 'event_map'
    if _missionListConfirmed(items):return 'mission_list'
    if _eventAnchor(items):return 'home'
    if findMissionGate(items):return 'mission_gate'
    return 'unknown'

def findSkipButton(items):
    candidates=[item for item in items if _text(item) in ('skip','跳过') and _center(item)[0]>=850 and _center(item)[1]<=180]
    return _center(candidates[0]) if len(candidates)==1 else None

def findSkipConfirmation(items):
    text=' '.join(_text(item) for item in items)
    if not any(token in text for token in ('跳过剧情','跳过故事','skipstory')):return None
    if not any(token in text for token in ('取消','cancel')):return None
    candidates=[item for item in items if _text(item) in ('确认','确定','ok','confirm')]
    return _center(candidates[0]) if len(candidates)==1 else None

def findClaimableMissionReward(items):
    for row in _rows(items,delta=60):
        rowText=' '.join(_text(item) for item in row['items'])
        if not any(token in rowText for token in ('已完成','可领取')):continue
        if any(token in rowText for token in ('选择奖励','请选择','任选','兑换','商店')):continue
        buttons=[item for item in row['items'] if _text(item) in ('领取','领取奖励')]
        if len(buttons)==1:return _center(buttons[0])
    return None

def findMissionListEntry(items):
    candidates=[item for item in items if _text(item) in ('任务进行度','任务进度','活动任务','任务列表') and 600<=_center(item)[0]<=1120 and _center(item)[1]<360]
    return _center(candidates[0]) if len(candidates)==1 else None

def _missionReturnButton(items):
    candidates=[item for item in items if _text(item) in ('关闭','返回') and _center(item)[0]<250 and _center(item)[1]<120]
    return _center(candidates[0]) if len(candidates)==1 else None

def findEventBattleStart(items):
    tokens=('开始任务','开始战斗','出击')
    candidates=[item for item in items if _text(item) in tokens and _center(item)[0]>=800 and _center(item)[1]>=470]
    return _center(candidates[0]) if len(candidates)==1 else None

def findBattleProgressButton(items):
    tokens=('下一步','继续','next')
    candidates=[item for item in items if _text(item) in tokens and _center(item)[0]>=800 and _center(item)[1]>=470]
    return _center(candidates[0]) if len(candidates)==1 else None

def _missionListConfirmed(items):
    text=' '.join(_text(item) for item in items)
    return any(token in text for token in ('活动任务列表','活动任务','任务列表','已达成的任务','missionlist','eventmissions'))

def _detectFlags(detect):
    return {
        'choose_friend':detect.isChooseFriend(),
        'formation':detect.isBattleFormation(),
        'battle':detect.isTurnBegin(),
        'battle_result':detect.isBattleFinished(),
    }

def _readScreen(detect):return ocrScreen(detect.im)

def _waitClassified(maxChecks=20):
    for _ in range(maxChecks):
        detect=Detect(.3)
        items=_readScreen(detect)
        state=classifyEventState(items,_detectFlags(detect))
        if state!='unknown':return detect,items,state
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
    return bool(hasMapHeader and (hasNode or hasEventControls))

def _openEventMap(detect,items):
    state=classifyEventState(items,_detectFlags(detect))
    if state in ('event_map','mission_list','start_confirmation','support','formation','battle','battle_result'):return detect,items
    if state!='home':raise ScriptStop('请先返回游戏主界面或活动地图；当前界面未被可靠识别')
    anchor=_eventAnchor(items)
    if not anchor:raise ScriptStop('未能唯一识别主界面当前活动入口，已停止')
    fgoDevice.device.touch(_center(anchor))
    detect,items,state=_waitClassified(25)
    if state!='event_map':raise ScriptStop('点击活动入口后未确认活动地图，已停止')
    return detect,items

def _missionRewardGate(items,autoClaim):
    gates=findMissionGate(items)
    if not gates:return None
    if not autoClaim:return {'state':'mission_blocked','message':'活动推进暂时被任务条件阻挡：'+'；'.join(gates)}
    if not _missionListConfirmed(items):return {'state':'mission_blocked','message':'活动推进暂时被任务条件阻挡；请先在活动任务列表手动领取可领取奖励。当前画面未可靠识别为活动任务列表。'}
    position=findClaimableMissionReward(items)
    if not position:return {'state':'mission_blocked','message':'活动推进暂时被任务条件阻挡；奖励开关已开，但当前界面没有可唯一确认的已完成领取项。'}
    return {'state':'claimable','position':position,'message':'仅发现明确标为已完成/可领取的奖励。'}

def _claimMissionRewards(detect,items):
    if not _missionListConfirmed(items):return None,items,{'state':'mission_blocked','message':'当前页面未可靠识别为活动任务列表；没有领取奖励。'}
    claimed=0
    for _ in range(20):
        position=findClaimableMissionReward(items)
        if position:
            fgoDevice.device.touch(position);claimed+=1
            for _ in range(8):
                detect,items,state=_waitClassified(1)
                if state=='event_map':return detect,items,{'state':'event_map','claimed':claimed,'message':f'已领取 {claimed} 项明确完成的活动任务奖励并返回活动地图。'}
                if state!='mission_list':return detect,items,{'state':'mission_blocked','claimed':claimed,'message':'领取后出现未识别的任务奖励界面，已停止。'}
                if findClaimableMissionReward(items)!=position:break
                schedule.sleep(.2)
            else:return detect,items,{'state':'mission_blocked','claimed':claimed,'message':'领取后奖励状态未变化，已停止以避免重复点击。'}
            continue
        position=_missionReturnButton(items)
        if not position:return detect,items,{'state':'mission_blocked','claimed':claimed,'message':'奖励检查完成，但未唯一识别返回活动地图按钮。'}
        fgoDevice.device.touch(position)
        detect,items,state=_waitClassified(25)
        if state=='event_map':return detect,items,{'state':'event_map','claimed':claimed,'message':f'已领取 {claimed} 项明确完成的活动任务奖励并返回活动地图。'}
        return detect,items,{'state':'mission_blocked','claimed':claimed,'message':'点击返回后未确认活动地图，已停止。'}
    return detect,items,{'state':'mission_blocked','claimed':claimed,'message':'已达 20 项奖励领取上限，已停止。'}

def _runEventBattle(detect,items,state,friendPolicy,friendMaxRefresh):
    """Run one entered event battle using the existing friend picker and Battle AI.

    Team controls and AP restore controls are intentionally never invoked here.
    """
    battleReport=None
    if state=='support':
        main=fgoKernel.Main(appleTotal=0,appleKind=0,battleClass=fgoKernel.Battle,friendPolicy=friendPolicy,friendMaxRefresh=friendMaxRefresh)
        try:main.chooseFriend()
        except ScriptStop as error:return detect,items,{'state':'blocked','battles':0,'message':str(error)}
        detect,items,state=_waitClassified(60)
        if state=='story':return detect,items,{'state':'story_paused','battles':0,'message':'助战选择后进入剧情，请阅读完成后继续。未点击跳过。'}
        if state!='formation':return detect,items,{'state':'blocked','battles':0,'message':'选择助战后未确认编队界面，已停止。'}
    if state=='formation':
        position=findEventBattleStart(items)
        if not position:return detect,items,{'state':'blocked','battles':0,'message':'未能唯一识别编队界面的开始按钮；没有更改编队或开始战斗。'}
        fgoDevice.device.touch(position)
        detect,items,state=_waitClassified(30)
        if state=='story':return detect,items,{'state':'story_paused','battles':0,'message':'开始战斗前进入剧情，请阅读完成后继续。未点击跳过。'}
        if state!='battle':return detect,items,{'state':'blocked','battles':0,'message':'点击 OCR 确认的开始按钮后未识别到战斗，已停止。'}
    if state=='battle':
        battle=fgoKernel.Battle()
        try:won=battle()
        except ScriptStop as error:return Detect(.2),items,{'state':'blocked','battles':0,'message':str(error)}
        battleReport=battle.result
        if not won:return Detect(.2),items,{'state':'battle_defeated','battles':1,'battle':battleReport,'message':'活动战斗失败；没有复活或恢复 AP。'}
        detect=Detect(.3);items=_readScreen(detect);state=classifyEventState(items,_detectFlags(detect))
    for _ in range(8):
        if state=='event_map':return detect,items,{'state':'event_map','battles':1 if battleReport else 0,'battle':battleReport,'message':'活动战斗已完成并返回活动地图。'}
        if state=='story':return detect,items,{'state':'story_paused','battles':1 if battleReport else 0,'battle':battleReport,'message':'活动战斗后进入剧情，请阅读完成后继续。未点击跳过。'}
        if state!='battle_result':return detect,items,{'state':'blocked','battles':1 if battleReport else 0,'battle':battleReport,'message':'战斗结算界面未能可靠识别，已停止。'}
        position=findBattleProgressButton(items)
        if not position:return detect,items,{'state':'blocked','battles':1 if battleReport else 0,'battle':battleReport,'message':'未能唯一识别战斗结算“下一步/继续”按钮，已停止。'}
        fgoDevice.device.touch(position)
        detect,items,state=_waitClassified(20)
    return detect,items,{'state':'blocked','battles':1 if battleReport else 0,'battle':battleReport,'message':'活动战斗结算超过 8 个已确认步骤，已停止。'}

def progress(maxNodes=1,storyMode=EVENT_STORY_PAUSE,autoClaim=False,friendPolicy='first',friendMaxRefresh=2):
    """Conservative CN event state machine: unknown screens stop; story pauses by default."""
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
        candidate=findNextMainQuest(items)
        if candidate is None:
            if autoClaim:
                entry=findMissionListEntry(items)
                if entry:
                    fgoDevice.device.touch(entry)
                    detect,items,state=_waitClassified(25)
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
        detect,items,state=_waitClassified(30)
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

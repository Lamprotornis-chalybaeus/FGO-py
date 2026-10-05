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
    return ('主线' in compact or '序幕' in compact or 'mainquest' in compact or 'mainstory' in compact or 'prologue' in compact or 'epilogue' in compact or bool(re.search(r'第[0-9一二三四五六七八九十]+[节幕]',compact)))

def findNextMainQuest(items):
    candidates=[]
    for row in _rows(items):
        rowItems=row['items']
        rowText=' '.join(_text(item) for item in rowItems)
        positiveItems=[item for item in rowItems if _reliable(item)]
        titleItems=[item for item in positiveItems if _isMainTitle(_text(item))]
        if not titleItems:continue
        if any(token in rowText for token in ('已完成','通关','clear','complete')):continue
        positiveText=' '.join(_text(item) for item in positiveItems)
        isNew=any(token in positiveText for token in ('new','新!','新！'))
        explicitMain=any(token in positiveText for token in ('主线','mainquest','mainstory'))
        hasAp=any(re.search(r'ap\s*\d+',_text(item)) for item in positiveItems)
        explicitEpisode=any(any(token in _text(item) for token in ('序幕','终幕','epilogue','prologue')) or bool(re.search(r'第[0-9一二三四五六七八九十]+[节幕]',_text(item))) for item in titleItems)
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
    positive=[item for item in items if _reliable(item)]
    text=' '.join(_text(item) for item in positive)
    return '是否开始关卡' in text and sum(1 for item in positive if _text(item)=='开始')==1 and sum(1 for item in positive if _text(item)=='取消')==1

def classifyEventState(items,flags=None):
    flags=flags or {}
    # Confirmations can cover a still-recognizable support/formation background.
    if _isStartQuestConfirmation(items):return 'start_confirmation'
    if flags.get('ap_empty'):return 'ap_empty'
    if flags.get('defeated'):return 'battle_defeated'
    if flags.get('friend_request'):return 'friend_request'
    if _unsafeEventOverlay(items):return 'unsafe_modal'
    if flags.get('choose_friend'):return 'support'
    if flags.get('formation'):return 'formation'
    if flags.get('battle'):return 'battle'
    if flags.get('battle_result'):return 'battle_result'
    if _isStory(items,flags):return 'story'
    if any(_text(item)=='每日任务' and _center(item)[0]>=900 and _center(item)[1]<95 for item in items):return 'daily_quest'
    if _eventMap(items):return 'event_map'
    if _missionListConfirmed(items):return 'mission_list'
    if _eventAnchor(items):return 'home'
    if findMissionGate(items):return 'mission_gate'
    return 'unknown'

def findSkipButton(items):
    candidates=[item for item in items if _text(item) in ('skip','跳过') and _center(item)[0]>=850 and _center(item)[1]<=180]
    return _center(candidates[0]) if len(candidates)==1 and _reliable(candidates[0]) else None

def findSkipConfirmation(items):
    text=' '.join(_text(item) for item in items if _reliable(item))
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
    tokens=('开始任务','开始战斗','出击')
    candidates=[item for item in items if _text(item) in tokens and _center(item)[0]>=800 and _center(item)[1]>=470]
    return _center(candidates[0]) if len(candidates)==1 and _reliable(candidates[0]) else None

def findBattleProgressButton(items):
    tokens=('下一步','继续','next')
    candidates=[item for item in items if _text(item) in tokens and _center(item)[0]>=800 and _center(item)[1]>=470]
    return _center(candidates[0]) if len(candidates)==1 and _reliable(candidates[0]) else None

def _missionListConfirmed(items):
    titles=[i for i in items if _text(i) in ('活动任务列表','活动任务','eventmissions') and _reliable(i) and 100<=_center(i)[0]<=1240 and 0<=_center(i)[1]<180]
    return len(titles)==1 and not _unsafeEventOverlay(items)

def _detectFlags(detect):
    return {
        'choose_friend':detect.isChooseFriend(),
        'formation':detect.isBattleFormation(),
        'battle':detect.isTurnBegin(),
        'battle_result':detect.isBattleFinished(),
        'ap_empty':getattr(detect,'isApEmpty',lambda:False)(),
        'defeated':getattr(detect,'isBattleDefeated',lambda:False)(),
        'friend_request':getattr(detect,'isAddFriend',lambda:False)(),
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
    return bool(hasMapHeader and (hasNode or hasEventControls))

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
    runner=EventRunner(EventResourcePolicy(allowApples=False),friendPolicy=friendPolicy,friendMaxRefresh=friendMaxRefresh)
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
        return EventRunner(resourcePolicy,friendPolicy=friendPolicy,friendMaxRefresh=friendMaxRefresh).run(maxNodes)
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

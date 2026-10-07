"""Guarded CN menu-only indexed scanning/positioning; never selects a quest."""
from dataclasses import asdict,replace
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import json,time
from statistics import median
from fgoDailyIndex import (DailyScanAccumulator,DailyScanMetrics,DailyIndexError,DailyQuestLocator,
                          DailyQuestIndex,DailyIndexRecord,DailyObservation,DailyScrollResult,DailyContinuityResult,
                          save_index,load_index,fingerprint)
from fgoSchedule import ScriptStop,schedule
from fgoLogging import getLogger

logger=getLogger('DailyIndex');_metrics=ContextVar('daily_metrics',default=None)
_cached=None;_invalid=False;_anchors={};_dragGain=1.;_dragSamples=[];_thumbTargetHistory={};_thumbHistoryGeometry=None

class DailyContextError(ScriptStop):
    """Not currently on a confirmed DAILY page; advisory data stays intact."""

class DailyIndexMismatch(ValueError):
    """Fresh confirmed DAILY content contradicts advisory index structure."""

def dailyContextLost(reason):
    logger.warning('[DailyIndex] %s; preserving cached index and anchors',reason)

def count(field):
    if m:=_metrics.get():setattr(m,field,getattr(m,field)+1)

@contextmanager
def measuring(metrics):
    # Instrument the OCR calls themselves, including foreground/modal guards.
    # Context-local counters do not count OCR performed by other workers.
    from fgoDetect import OCR
    outer=_metrics.get();token=_metrics.set(metrics);originals=[]
    try:
        if outer is None:
            for model in (OCR.ZHS,OCR.EN):
                for name in ('detect_and_ocr','ocr_single_line'):
                    original=getattr(model,name)
                    def observed(image,*args,_fn=original,_batch=name=='detect_and_ocr',**kwargs):
                        count('fullOcrCalls' if _batch and image.shape[0]>300 else 'localOcrCalls')
                        return _fn(image,*args,**kwargs)
                    originals.append((model,name,original));setattr(model,name,observed)
        yield
    finally:
        for model,name,original in reversed(originals):setattr(model,name,original)
        _metrics.reset(token)


def cachePath():
    from fgoPaths import paths
    return paths.dataRoot/'fgoTemp'/'daily-index.json'

def currentIndex():
    global _cached
    if _cached is None and not _invalid:_cached=load_index(cachePath())
    return _cached

def invalidateIndex(reason):
    global _cached,_invalid,_anchors
    _cached=None;_invalid=True;_anchors={}
    mismatch=DailyIndexMismatch(reason)
    logger.warning('Daily index invalidated: confirmed DAILY mismatch: %s',mismatch)
    path=cachePath();path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'version':1,'invalidated':True,'reason':reason}),encoding='utf-8')
    return mismatch

def remember(index):
    global _cached,_invalid
    save_index(index,cachePath());_cached=index;_invalid=False


def rememberAnchor(entry,thumb,y):
    key=__import__('fgoQuickQuest')._title_key(entry.title)
    _anchors[key]={'title_key':key,'thumb_top':float(thumb[0]),'thumb_bottom':float(thumb[1]),'local_y':float(y)}
    path=cachePath();path.parent.mkdir(parents=True,exist_ok=True)
    payload=asdict(_cached) if _cached else {'version':1,'partial':True}
    if _cached:payload['entry_count']=_cached.entry_count
    payload['anchors']=list(_anchors.values())
    temp=path.with_name(path.name+'.tmp');temp.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8');temp.replace(path)

def advisoryAnchor(key):
    if key in _anchors:return _anchors[key]
    try:
        path=cachePath()
        if path.stat().st_size>2_000_000:return None
        payload=json.loads(path.read_text(encoding='utf-8'))
        if payload.get('version')!=1 or payload.get('invalidated'):return None
        import math
        for a in payload.get('anchors',[]):
            values=[a[f] for f in ('thumb_top','thumb_bottom','local_y')]
            if all(isinstance(v,(int,float)) and math.isfinite(v) for v in values) and 99<=values[0]<values[1]<=575 and 130<=values[2]<=220:
                _anchors[a['title_key']]=a
        return _anchors.get(key)
    except (OSError,ValueError,TypeError,KeyError):return None

def locateAnchor(entry,anchor,metrics,deadline):
    import fgoQuickQuest as q
    d=capture();safe(d);thumb=q._scrollbar(d.im)
    if abs((thumb[1]-thumb[0])-(anchor['thumb_bottom']-anchor['thumb_top']))>2:
        invalidateIndex('partial anchor geometry changed');return None
    d,_=seekApprox(anchor['thumb_top'],deadline,d,mode='anchor-seek')
    key=q._title_key(entry.title);target=_find(localEntries(d,anchor['local_y']),key)
    if not target:invalidateIndex('partial anchor title missing');return None
    d=capture();safe(d);target=_find(localEntries(d,target.discovered_position[2]),key)
    if not target or not 125<=target.discovered_position[2]<=220:raise ScriptStop('缓存定点标题/AP最终确认失败，未点击')
    return dict(type='DailyQuestReady',entry=entry,position=target.discovered_position[1:],mode='index')

def entryFromRecord(record):
    import fgoQuickQuest as q
    loc=record.locator
    return q.DailyQuestEntry(record.title,record.quest_type,record.difficulty,'',(loc.ordinal or 0,947,round(loc.local_y)),loc)

def _checkDeadline(deadline):
    schedule.checkStop();schedule.checkSuspend()
    if time.monotonic()>=deadline:raise ScriptStop('每日任务索引操作超时，未点击关卡')

def capture():
    import fgoQuickQuest as q
    return q._dailyCapture(.2)

def safe(d):
    import fgoQuickQuest as q
    if getattr(d,'_indexedSafeFrame',None) is d.im:return
    # Reuse the existing full foreground/modal safety proof. Count that OCR too.
    if not q.confirmedDailyPageCN(d):
        dailyContextLost(f'current page is {q._dailyNavigationStateCN(d)}; NOT_ON_DAILY')
        raise DailyContextError('当前未正向确认每日任务页，已停止菜单输入；保留索引，请等待导航完成')
    q._dailyLocatorFrameCN(d)
    d._indexedSafeFrame=d.im

def _moveThumb(target,mode,deadline,detect=None,*,tolerance=.5):
    """Issue one scrollbar drag and report the observed position without chasing it."""
    import fgoQuickQuest as q
    global _dragGain
    _checkDeadline(deadline);d=detect or capture();safe(d);top,bottom=q._scrollbar(d.im);height=bottom-top
    if not 95<=top<bottom<=585 or not 30<=height<=490:raise ScriptStop('每日任务滚动条几何无效，已停止拖动')
    target=max(99,min(575-height,float(target)));error=target-top
    if abs(error)<=tolerance:return d,DailyScrollResult(float(target),float(top),float(top-target),0.,mode)
    center=round((top+bottom)/2);endpoint=max(100,min(574,round(center+error/_dragGain)))
    q._menuScrollbarDrag((1258,center),(1258,endpoint));count('scrollbarDrags')
    physical=endpoint-center;schedule.sleep(.1);d=capture();safe(d)
    for sample in range(3):
        _checkDeadline(deadline)
        try:new=q._scrollbar(d.im);break
        except ScriptStop as error:
            if sample==2 or '未唯一识别每日任务滚动条' not in str(error):raise
            # A released handle can have one transient render frame. Re-read only.
            d=capture();safe(d)
    moved=new[0]-top
    if abs((new[1]-new[0])-height)>2:raise ScriptStop('每日任务滚动条几何发生变化，已停止拖动')
    if abs(physical)>=5 and abs(moved)>=2 and new[0]>101 and new[1]<574 and .65<=moved/physical<=1.2:
        _dragSamples.append(moved/physical);del _dragSamples[:-21]
        if len(_dragSamples)>=3:_dragGain=float(median(_dragSamples))
    return d,DailyScrollResult(float(target),float(new[0]),float(new[0]-target),float(moved),mode)

def _quantizedChoice(target,candidates,absolute_y,scroll_scale,local_y):
    """Choose between observed reachable thumb positions when the target is quantized."""
    values=[]
    for value in candidates:
        if not any(abs(value-old)<.75 for old in values):values.append(float(value))
    if len(values)<2:return None
    low,high=min(values),max(values)
    if high-low>6 or not low<=target<=high:return None
    def rank(value):
        if absolute_y is None or not scroll_scale:return (0,abs(value-target))
        y=absolute_y-scroll_scale*value
        return (0 if 120<=y<=300 else 1,abs(y-local_y))
    return min(values,key=rank),low,high

def seekApprox(target,deadline,detect=None,*,absolute_y=None,scroll_scale=None,local_y=185,mode='seek'):
    """Move near a predicted thumb position once; caller trusts observed content and actual thumb."""
    import fgoQuickQuest as q
    global _thumbHistoryGeometry
    _checkDeadline(deadline);requested=float(target);d=detect or capture();safe(d);thumb=q._scrollbar(d.im)
    geometry=round(thumb[1]-thumb[0],1)
    if _thumbHistoryGeometry is None:_thumbHistoryGeometry=geometry
    elif _thumbHistoryGeometry!=geometry:_thumbTargetHistory.clear();_thumbHistoryGeometry=geometry
    key=round(requested,1);history=_thumbTargetHistory.setdefault(key,[])
    if len(_thumbTargetHistory)>128:_thumbTargetHistory.pop(next(iter(_thumbTargetHistory)))
    choice=_quantizedChoice(requested,history,absolute_y,scroll_scale,local_y)
    selected=requested if choice is None else choice[0]
    if choice:
        logger.info('[DailyScroll] quantized target=%.1f reachable=(%.1f,%.1f) selected=%.1f',requested,choice[1],choice[2],selected)
    d,result=_moveThumb(selected,mode,deadline,d,tolerance=2.)
    actual=q._scrollbar(d.im)[0]
    if not any(abs(actual-old)<.75 for old in history):history.append(float(actual));del history[:-6]
    crossed=any((old-requested)*(actual-requested)<0 and abs(actual-old)<=6 for old in history[:-1])
    quantized=choice is not None or crossed
    if quantized and choice is None:
        nearby=[v for v in history if abs(v-requested)<=6]
        if nearby:logger.info('[DailyScroll] quantized target=%.1f reachable=(%.1f,%.1f) selected=%.1f',requested,min(nearby),max(nearby),actual)
    if quantized:count('quantizedAccepts')
    return d,replace(result,requested_thumb=requested,actual_thumb=float(actual),error=float(actual-requested),
                     mode=mode,quantized=quantized)

def seekEndpoint(endpoint,deadline,detect=None):
    """Reach and positively confirm a real top or bottom boundary."""
    import fgoQuickQuest as q
    if endpoint not in ('top','bottom'):raise ValueError("endpoint must be 'top' or 'bottom'")
    d=detect or capture();safe(d);thumb=q._scrollbar(d.im);height=thumb[1]-thumb[0]
    initial_top=float(thumb[0])
    requested=99. if endpoint=='top' else 575.-height;result=None
    if (endpoint=='top' and thumb[0]<=101) or (endpoint=='bottom' and thumb[1]>=574):
        return d,DailyScrollResult(requested,float(thumb[0]),float(thumb[0]-requested),0.,f'endpoint:{endpoint}')
    for correction in range(3):
        d,result=_moveThumb(requested,f'endpoint:{endpoint}',deadline,d);thumb=q._scrollbar(d.im)
        confirmed=thumb[0]<=101 if endpoint=='top' else thumb[1]>=574
        logger.info('[DailyScroll] endpoint=%s correction=%s thumb=(%.1f,%.1f) moved=%.1f gain=%.4f confirmed=%s',
                    endpoint,correction+1,thumb[0],thumb[1],result.moved,_dragGain,confirmed)
        if confirmed:return d,replace(result,requested_thumb=requested,actual_thumb=thumb[0],error=thumb[0]-requested,
                                      corrections=correction)
    if endpoint=='top':
        # A track drag can stop a few pixels short at the top edge. Use only
        # bounded content-up nudges, and still require a fresh positive proof.
        # This never publishes a partial list or infers the endpoint from input.
        for correction,distance in enumerate((80,100),1):
            _checkDeadline(deadline);before=float(thumb[0])
            q._swipe_input_only(d,True,distance);d=capture();safe(d);thumb=q._scrollbar(d.im)
            confirmed=thumb[0]<=101
            logger.info('[DailyScroll] endpoint=top contentNudge=%s distance=%s thumb=(%.1f,%.1f) moved=%.1f confirmed=%s',
                        correction,distance,thumb[0],thumb[1],thumb[0]-before,confirmed)
            if confirmed:
                moved=float(thumb[0]-initial_top)
                return d,DailyScrollResult(requested,float(thumb[0]),float(thumb[0]-requested),moved,
                                           'endpoint:top-content-nudge',corrections=3+correction,
                                           reached_endpoint=True)
    raise ScriptStop(f'每日任务列表{("顶部" if endpoint=="top" else "底部")}端点未能正向确认，未发布列表')

def dragTo(target,deadline,detect=None):
    """Compatibility wrapper; ordinary positioning is approximate, never an endpoint proof."""
    return seekApprox(target,deadline,detect)[0]

def _freshScrollState(deadline,expected_height):
    """Re-read a stopped gesture with a fresh DAILY proof and stable geometry."""
    import fgoQuickQuest as q
    _checkDeadline(deadline);d=capture();safe(d);thumb=q._scrollbar(d.im)
    if abs((thumb[1]-thumb[0])-expected_height)>2:
        raise ScriptStop('每日任务滚动条几何发生变化，已停止恢复')
    return d,thumb

def _nearBottom(thumb):
    gap=574.-thumb[1]
    return 0<gap<=3

def _bootstrapShift(entries):
    """Conservatively retain the last complete title near the middle of the next frame."""
    if not entries:raise ScriptStop('每日任务bootstrap没有完整标题，未滚动')
    last_y=max(e.discovered_position[2] for e in entries)
    return max(120,min(220,round(last_y-260)))

def performScanMove(d,entries,acc,deadline,*,phase='bootstrap',target_thumb=None,
                    target_absolute_y=None,target_local_y=185,distance=None):
    """Move the DAILY list and report fresh thumb movement; do not parse continuity here."""
    import fgoQuickQuest as q
    safe(d);old_thumb=q._scrollbar(d.im);old_top=old_thumb[0];height=old_thumb[1]-old_thumb[0]
    if phase=='bootstrap':
        shift=_bootstrapShift(entries) if distance is None else max(120,min(220,int(distance)))
        attempts=0;recovered=False
        while attempts<2:
            _checkDeadline(deadline);attempts+=1
            q._swipe_input_only(d,False,shift);d=capture();safe(d);new_thumb=q._scrollbar(d.im)
            moved=new_thumb[0]-old_top
            if new_thumb[1]>=574 or moved>.5:
                if attempts>1:recovered=True;count('recoveredNoProgress')
                result=DailyScrollResult(float(new_thumb[0]),float(new_thumb[0]),0.,float(moved),
                    'scan-bootstrap',attempts=attempts,recovered_no_progress=recovered,
                    reached_endpoint=new_thumb[1]>=574)
                return d,result,old_thumb,new_thumb
            count('noProgressAttempts')
            if attempts==1:
                stalled=new_thumb[0];d,new_thumb=_freshScrollState(deadline,height)
                logger.info('[DailyScroll] mode=bootstrap no-progress captured=%.1f fresh=%.1f',stalled,new_thumb[0])
                if new_thumb[1]>=574 or new_thumb[0]-old_top>.5:
                    count('recoveredNoProgress')
                    result=DailyScrollResult(float(new_thumb[0]),float(new_thumb[0]),0.,float(new_thumb[0]-old_top),
                        'scan-bootstrap',attempts=attempts,recovered_no_progress=True,reached_endpoint=new_thumb[1]>=574)
                    return d,result,old_thumb,new_thumb
                shift=max(120,min(220,round(shift*.75)))
        raise ScriptStop('每日任务bootstrap内容滑动连续两次无进展，未发布列表')
    if phase!='calibrated':raise ValueError(f'unknown scan phase: {phase}')
    if target_thumb is None:raise ValueError('calibrated scan requires target_thumb')
    requested=float(target_thumb);bottom_top=575.-height;attempts=1
    recovered=False;used_content_fallback=False;endpoint_attempted=False
    if requested>=bottom_top-.1:
        d,result=_moveThumb(bottom_top,'scan-endpoint',deadline,d)
        result=replace(result,requested_thumb=requested,error=result.actual_thumb-requested)
    else:
        d,result=seekApprox(requested,deadline,d,absolute_y=target_absolute_y,
            scroll_scale=acc.scroll_scale,local_y=target_local_y,mode='scan')
    new_thumb=q._scrollbar(d.im);moved=new_thumb[0]-old_top
    if new_thumb[1]<574 and moved<=.5:
        count('noProgressAttempts');stalled=new_thumb[0]
        d,new_thumb=_freshScrollState(deadline,height);moved=new_thumb[0]-old_top
        logger.info('[DailyScroll] mode=calibrated no-progress stage=1 captured=%.1f fresh=%.1f bottom=%s',
                    stalled,new_thumb[0],new_thumb[1]>=574)
        if new_thumb[1]>=574:moved=0.
        elif moved>.5:recovered=True;count('recoveredNoProgress')
        elif _nearBottom(new_thumb):
            endpoint_attempted=True;attempts=2
            try:
                d,result=seekEndpoint('bottom',deadline,d);new_thumb=q._scrollbar(d.im)
                if new_thumb[1]>=574:recovered=True;count('recoveredNoProgress');count('endpointRecoveries')
            except ScriptStop as error:
                if '每日任务列表底部端点未能正向确认' not in str(error):raise
                d,new_thumb=_freshScrollState(deadline,height)
        else:
            attempts=2
            retry_target=min(bottom_top,max(new_thumb[0]+8.,requested))
            d,retry=seekApprox(retry_target,deadline,d,absolute_y=target_absolute_y,
                scroll_scale=acc.scroll_scale,local_y=target_local_y,mode='scan-retry')
            new_thumb=q._scrollbar(d.im);moved=new_thumb[0]-old_top
            if new_thumb[1]>=574:recovered=True;count('recoveredNoProgress')
            elif moved>.5:recovered=True;count('recoveredNoProgress');result=retry
            else:
                count('noProgressAttempts');stalled=new_thumb[0]
                d,new_thumb=_freshScrollState(deadline,height);moved=new_thumb[0]-old_top
                logger.info('[DailyScroll] mode=calibrated no-progress stage=2 captured=%.1f fresh=%.1f bottom=%s',
                            stalled,new_thumb[0],new_thumb[1]>=574)
        if new_thumb[1]<574 and new_thumb[0]-old_top<=.5 and _nearBottom(new_thumb) and not endpoint_attempted:
            attempts=max(attempts,2);endpoint_attempted=True
            try:
                d,result=seekEndpoint('bottom',deadline,d);new_thumb=q._scrollbar(d.im)
                if new_thumb[1]>=574:recovered=True;count('recoveredNoProgress');count('endpointRecoveries')
            except ScriptStop as error:
                if '每日任务列表底部端点未能正向确认' not in str(error):raise
                d,new_thumb=_freshScrollState(deadline,height)
        moved=new_thumb[0]-old_top
        if new_thumb[1]<574 and moved<=.5:
            attempts=3;used_content_fallback=True;count('contentFallbacks')
            fallback_start=new_thumb[0]
            q._swipe_input_only(d,False,max(120,min(180,int((distance or 280)/2))))
            d=capture();safe(d);new_thumb=q._scrollbar(d.im)
            if abs((new_thumb[1]-new_thumb[0])-height)>2:raise ScriptStop('每日任务滚动条几何发生变化，已停止恢复')
            moved=new_thumb[0]-old_top
            if new_thumb[1]>=574 or new_thumb[0]-fallback_start>.5:recovered=True;count('recoveredNoProgress')
            else:
                count('noProgressAttempts');stalled=new_thumb[0]
                d,new_thumb=_freshScrollState(deadline,height);moved=new_thumb[0]-old_top
                logger.info('[DailyScroll] mode=calibrated no-progress stage=3 captured=%.1f fresh=%.1f bottom=%s',
                            stalled,new_thumb[0],new_thumb[1]>=574)
        moved=new_thumb[0]-old_top
        if new_thumb[1]<574 and moved<=.5:
            raise ScriptStop('每日任务滚动连续三次无进展且未到列表末端，未发布列表')
    return d,replace(result,actual_thumb=float(new_thumb[0]),error=float(new_thumb[0]-requested),
                     moved=float(new_thumb[0]-old_top),attempts=attempts,
                     recovered_no_progress=recovered,used_content_fallback=used_content_fallback,
                     reached_endpoint=new_thumb[1]>=574),old_thumb,new_thumb

def verifyScanContinuity(old_entries,new_entries,old_thumb,new_thumb,acc,*,phase='bootstrap'):
    """Explain why adjacent fresh DAILY frames do or do not form a safe scan chain."""
    import fgoQuickQuest as q
    old_keys=[q._title_key(e.title) for e in old_entries]
    new_keys=[q._title_key(e.title) for e in new_entries]
    shared=tuple(k for k in old_keys if k in set(new_keys))
    if shared:
        ordered=[k for k in new_keys if k in set(old_keys)]
        if ordered==list(shared):return DailyContinuityResult(True,'TITLE_OVERLAP',shared,None,acc.card_pitch)
        return DailyContinuityResult(False,'FAILED',shared,None,acc.card_pitch)
    if phase=='bootstrap' or not old_entries or not new_entries:
        return DailyContinuityResult(False,'FAILED',(),None,acc.card_pitch)
    if not acc.scroll_scale or not acc.card_pitch:return DailyContinuityResult(False,'FAILED',(),None,acc.card_pitch)
    old_last=old_keys[-1]
    before=acc.absolute.get(old_last)
    if before is None:return DailyContinuityResult(False,'FAILED',(),None,acc.card_pitch)
    first=min(new_entries,key=lambda e:e.discovered_position[2])
    after=first.discovered_position[2]+acc.scroll_scale*new_thumb[0]
    gap=float(after-before);pitch=float(acc.card_pitch)
    accepted=.65*pitch<=gap<=1.3*pitch
    return DailyContinuityResult(accepted,'ABSOLUTE_ADJACENCY' if accepted else 'FAILED',(),gap,pitch)

def recoverContinuity(d,old_entries,new_entries,old_thumb,new_thumb,acc,deadline,frame_index,metrics,*,phase):
    """Recover a moved frame using at most two small reverse content swipes, never a new down-seek."""
    import fgoQuickQuest as q
    if new_thumb[0]<=old_thumb[0]+.5:return d,new_entries,new_thumb,DailyContinuityResult(False,'FAILED',(),None,acc.card_pitch)
    for attempt,distance in enumerate((80,100),1):
        _checkDeadline(deadline);q._swipe_input_only(d,True,distance);d=capture();safe(d)
        d,candidate=_readPage(d,frame_index);thumb=q._scrollbar(d.im)
        overlap=verifyScanContinuity(old_entries,candidate,old_thumb,thumb,acc,phase='bootstrap')
        if overlap.accepted and thumb[0]>old_thumb[0]+.5:
            metrics.continuityRecoveries+=1;metrics.bootstrapOverlapRecoveries+=int(phase=='bootstrap')
            accepted=DailyContinuityResult(True,'RECOVERED_OVERLAP',overlap.shared_keys,None,acc.card_pitch)
            logger.info('[DailyContinuity] mode=%s reason=%s shared=%s recovery=%s thumbMoved=%.1f pitch=%s',
                        phase,accepted.reason,len(accepted.shared_keys),attempt,thumb[0]-old_thumb[0],accepted.card_pitch)
            return d,candidate,thumb,accepted
        logger.info('[DailyContinuity] mode=%s reason=FAILED shared=%s recovery=%s thumbMoved=%.1f',
                    phase,len(overlap.shared_keys),attempt,thumb[0]-old_thumb[0])
    return d,new_entries,new_thumb,DailyContinuityResult(False,'FAILED',(),None,acc.card_pitch)

def advanceScan(d,entries,acc,deadline,frame_index,*,phase='calibrated',target_thumb=None,
                target_absolute_y=None,target_local_y=185,distance=None,metrics=None):
    """Move, verify continuity, and invoke the distinct bounded continuity recovery."""
    import fgoQuickQuest as q
    metrics=metrics or _metrics.get() or DailyScanMetrics()
    d,result,old_thumb,new_thumb=performScanMove(d,entries,acc,deadline,phase=phase,
        target_thumb=target_thumb,target_absolute_y=target_absolute_y,target_local_y=target_local_y,distance=distance)
    d,new_entries=_readPage(d,frame_index);new_thumb=q._scrollbar(d.im)
    # Title recovery may move the content backwards after the motion controller
    # reached its target. Re-establish forward overlap before accepting a frame;
    # endpoint evidence must come from the recovered capture, never the old one.
    if new_thumb[0]<old_thumb[0]-2:
        for retry_distance in (80,100):
            _checkDeadline(deadline);safe(d)
            q._swipe_input_only(d,False,retry_distance);d=capture();safe(d)
            d,new_entries=_readPage(d,frame_index);new_thumb=q._scrollbar(d.im)
            if new_thumb[0]>=old_thumb[0]-.5:break
        else:raise ScriptStop('每日任务标题复核后未恢复前向位置，未发布列表')
        metrics.continuityRecoveries+=1
    continuity=verifyScanContinuity(entries,new_entries,old_thumb,new_thumb,acc,phase=phase)
    if continuity.accepted:
        if phase=='bootstrap':metrics.bootstrapOverlapSamples+=1
        result=replace(result,actual_thumb=float(new_thumb[0]),error=float(new_thumb[0]-result.requested_thumb),
            moved=float(new_thumb[0]-old_thumb[0]),continuity=True,reached_endpoint=new_thumb[1]>=574)
        logger.info('[DailyContinuity] mode=%s reason=%s shared=%s gap=%s pitch=%s',
                    phase,continuity.reason,len(continuity.shared_keys),continuity.predicted_gap,continuity.card_pitch)
    else:
        logger.info('[DailyContinuity] mode=%s reason=FAILED shared=%s gap=%s pitch=%s',
                    phase,len(continuity.shared_keys),continuity.predicted_gap,continuity.card_pitch)
        d,new_entries,new_thumb,continuity=recoverContinuity(d,entries,new_entries,old_thumb,new_thumb,
            acc,deadline,frame_index,metrics,phase=phase)
        if not continuity.accepted:raise ScriptStop('每日任务相邻屏连续覆盖未恢复，未发布完整列表')
        metrics.bootstrapOverlapSamples+=int(phase=='bootstrap')
        result=replace(result,actual_thumb=float(new_thumb[0]),error=float(new_thumb[0]-result.requested_thumb),
            moved=float(new_thumb[0]-old_thumb[0]),continuity=True,mode='scan-recovery',
            corrections=1,attempts=result.attempts,reached_endpoint=new_thumb[1]>=574)
    if result.reached_endpoint and new_thumb[1]<574:
        raise ScriptStop('每日任务底部端点复核后丢失，未发布列表')
    logger.info('[DailyScroll] mode=%s requested=%.1f actual=%.1f error=%.1f moved=%.1f continuity=%s attempts=%s noProgressRetry=%s recovered=%s contentFallback=%s reachedEndpoint=%s',
        result.mode,result.requested_thumb,result.actual_thumb,result.error,result.moved,continuity.reason,
        result.attempts,max(0,result.attempts-1),result.recovered_no_progress,
        result.used_content_fallback,result.reached_endpoint)
    return d,new_entries,result

def _readPage(d,n):
    import fgoQuickQuest as q
    if not q._isDailyPage(d):raise ScriptStop('每日任务扫描页面已变化，未发布列表')
    safe(d)
    frame,entries=q._observeDailyScanPage(d,n)
    return frame,sorted(entries,key=lambda e:e.discovered_position[2])

def localEntries(d,y,radius=60):
    """Local proposals are accepted only by real full-title consensus + own AP."""
    import fgoQuickQuest as q
    top=max(95,int(y-radius-28));bottom=min(695,int(y+radius+105))
    spans=q.OCR.ZHS.detect_and_ocr(d.im[top:bottom,750:910],drop_score=.5)
    proposals=q.parseDailyQuestEntries(spans,d.im,0,(750,top));entries=[];apMap={}
    rows=[sum((q._span_rect(s,(750,top))[1],q._span_rect(s,(750,top))[3]))/2 for s in spans if q.re.fullmatch(r'AP\d+',q._compact_title(s.text),q.re.I)]
    for e in proposals:
        cy=e.discovered_position[2]
        if not 115<=cy<=600:continue
        ap=next((a for a in rows if 40<=a-cy<=105),None)
        if ap is None:
            text,score=q.OCR.EN.ocr_single_line(d.im[cy+50:cy+93,775:900])
            if score<.8 or not q.re.fullmatch(r'AP\d+',q._compact_title(text),q.re.I):continue
            ap=cy+71.5
        title=q._readDailyTitle(d.im,cy)
        if title:
            entries.append(q.DailyQuestEntry(title,q._quest_type(title),q._difficulty(title),'',(0,947,cy)))
            apMap[q._title_key(title)]=ap
    for ap in rows:
        if not 190<=ap<=675 or any(40<=ap-e.discovered_position[2]<=105 for e in entries):continue
        cy=round(ap-75)
        if not 115<=cy<=600:continue
        title=q._readDailyTitle(d.im,cy)
        if title:
            entries.append(q.DailyQuestEntry(title,q._quest_type(title),q._difficulty(title),'',(0,947,cy)))
            apMap[q._title_key(title)]=ap
    entries=q._dailyUniqueVisibleCards(entries)
    d._dailyVerifiedAP={**getattr(d,'_dailyVerifiedAP',{}),**apMap}
    return entries

def _add(acc,d,entries,frame,forward=False):
    import fgoQuickQuest as q
    try:acc.add_frame(sorted(entries,key=lambda e:e.discovered_position[2]),q._scrollbar(d.im),frame,getattr(d,'_dailyVerifiedAP',{}),forward)
    except DailyIndexError as e:raise ScriptStop(f'每日任务位置索引冲突：{e}；未发布完整列表') from e

def _resolveConflicts(acc,deadline,metrics,d):
    import fgoQuickQuest as q
    # Conflicting OCR aliases occupy one slot. Resolve only with independent
    # real title/AP observations; two competing verified names remain unsafe.
    for _ in range(3):
        conflicts=acc.conflicts()
        if not conflicts:break
        for a,b in conflicts:
            if a not in acc.absolute or b not in acc.absolute:continue
            absolute=(acc.absolute[a]+acc.absolute[b])/2
            for y in (185,275):
                metrics.targetedRechecks+=1;prior=d
                d,_=seekApprox((absolute-y)/acc.scroll_scale,deadline,d,absolute_y=absolute,
                               scroll_scale=acc.scroll_scale,local_y=y,mode='index-recheck')
                if d is prior:d=capture();safe(d)
                entries=localEntries(d,absolute-acc.scroll_scale*q._scrollbar(d.im)[0])
                _add(acc,d,entries,metrics.screensCaptured)
            slot=[k for k,y in acc.absolute.items() if abs(y-absolute)<acc.card_pitch*.45]
            verified=[k for k in slot if acc.verified(k)]
            if len(verified)!=1:raise ScriptStop('同一卡槽的标题仍有冲突，未发布完整列表')
            for stale in slot:
                if stale!=verified[0]:del acc.entries[stale];del acc.observations_by_title[stale]
            acc.calibrate()
    if acc.conflicts():raise ScriptStop('每日任务标题位置冲突未解决，未发布完整列表')
    return d

def _targeted(acc,deadline,metrics,d=None,top_key=None,deferred_keys=()):
    import fgoQuickQuest as q
    d=_resolveConflicts(acc,deadline,metrics,d)
    # Recover actual content gaps, not names, with finite local-only observations.
    for _ in range(3):
        gaps=acc.gaps()
        if not gaps:break
        for gap in gaps:
            found=False
            for offset in (0,-60,60):
                _checkDeadline(deadline);metrics.targetedRechecks+=1
                target=(gap.expected_absolute_y-200+offset)/acc.scroll_scale
                d,_=seekApprox(target,deadline,d,absolute_y=gap.expected_absolute_y,
                               scroll_scale=acc.scroll_scale,local_y=200,mode='gap-seek')
                y=gap.expected_absolute_y-acc.scroll_scale*q._scrollbar(d.im)[0]
                entries=localEntries(d,y);before=len(acc.entries)
                _add(acc,d,entries,metrics.screensCaptured)
                if len(acc.entries)>before:metrics.gapRecoveries+=1;found=True;break
            if not found:raise ScriptStop('每日任务内容缺口定点复核失败，未发布完整列表')
    if acc.gaps():raise ScriptStop('每日任务内容仍有未解决缺口，未发布完整列表')
    # Group nearby single observations on one newly acquired frame. OCR remains
    # local per predicted band; edge exceptions are explicitly rechecked here.
    for _ in range(3):
        # Rechecks can reveal the real title next to a one-frame OCR alias.
        # Resolve newly created same-slot conflicts before spending another
        # round trying to confirm a stale name. Never accept competing verified
        # names or pick the requested/cached name without real observations.
        d=_resolveConflicts(acc,deadline,metrics,d)
        pending=sorted((k for k in acc.unverified() if k!=top_key and k not in deferred_keys),key=acc.absolute.get)
        if not pending:return d
        while pending:
            first=pending.pop(0);group=[first]
            while pending and acc.absolute[pending[0]]-acc.absolute[first]<=410:group.append(pending.pop(0))
            original=acc.observations_by_title[first][0]
            target=(acc.absolute[first]-185)/acc.scroll_scale
            # Change alignment enough for independent positional evidence.
            if abs(target-original.thumb_top)*acc.scroll_scale<30:target+=(30 if target>=original.thumb_top else -30)/acc.scroll_scale
            previous_frame=d
            d,_=seekApprox(target,deadline,d,absolute_y=acc.absolute[first],
                           scroll_scale=acc.scroll_scale,local_y=185,mode='index-recheck')
            if d is previous_frame:d=capture();safe(d)
            thumb=q._scrollbar(d.im);metrics.targetedRechecks+=1
            rows=[]
            for key in group:
                y=acc.absolute[key]-acc.scroll_scale*thumb[0]
                rows.extend(localEntries(d,y))
            unique={q._title_key(e.title):e for e in rows}
            _add(acc,d,list(unique.values()),metrics.screensCaptured)
            ordered=sorted(acc.entries,key=acc.absolute.get)
            for key in group:
                if key in unique and key in (ordered[0],ordered[-1]) and (thumb[0]<=105 or thumb[1]>=574):
                    acc.edge_rechecks.add(key)
    d=_resolveConflicts(acc,deadline,metrics,d)
    if any(k!=top_key and k not in deferred_keys for k in acc.unverified()):raise ScriptStop('每日任务单次观测定点复核仍未确认，未发布完整列表')
    return d

def _nextScanShift(entries,acc,stride):
    # A repeated two-card advance leaves every middle card observed only once.
    # Keep that real, unverified card in the next forward overlap instead of
    # making a separate return trip after reaching the bottom. Once it has
    # independent title/AP evidence, the larger bounded advance is safe again.
    anchor=entries[-1]
    if len(entries)>=3 and not acc.verified(__import__('fgoQuickQuest')._title_key(entries[-2].title)):
        anchor=entries[-2]
    return max(180,min(stride,anchor.discovered_position[2]-170))

def _readScanTop(d,n,deadline):
    """Thumb quantization alone cannot prove the leading card is readable."""
    import fgoQuickQuest as q
    for attempt in range(3):
        _checkDeadline(deadline);safe(d)
        if q._scrollbar(d.im)[0]>101:raise ScriptStop('每日任务扫描顶部滚动条未确认，未发布列表')
        d,entries=_readPage(d,n)
        if entries and min(e.discovered_position[2] for e in entries)<=220:return d,entries
        if attempt==2:break
        # At thumb 100 the content may still be ~32 px below the true endpoint:
        # the first title/AP lies outside the full-card read band. One bounded
        # upward-list normalization input needs fresh DAILY and top proof.
        # Never invent that missing leading card from the advisory index.
        q._swipe_input_only(d,True,100);d=capture()
    raise ScriptStop('每日任务顶部第一张完整卡片未确认，未发布不完整列表')

def scan():
    import fgoQuickQuest as q
    from fgoNavigation import publish
    if q.XDetect.region!='CN':raise ScriptStop('每日任务 OCR 仅适配简体中文服务器')
    metrics=DailyScanMetrics();start=time.monotonic();deadline=start+q.DAILY_SCAN_TIMEOUT
    acc=DailyScanAccumulator(q._title_key);prior=currentIndex();reused=False
    with measuring(metrics):
        d=capture()
        if not q._isDailyPage(d):q.openDailyPageCN();d=capture()
        safe(d);d,_=seekEndpoint('top',deadline,d);stride=280;stable=0;n=0;phase='bootstrap';prior_matches=False
        firstPage=_readScanTop(d,n,deadline);d=firstPage[0];pending_entries=firstPage[1]
        while True:
            _checkDeadline(deadline);entries=pending_entries;thumb=q._scrollbar(d.im)
            if not entries:raise ScriptStop('未校验到完整每日任务卡片，请检查识别日志')
            if n==0 and prior:
                keys=[q._title_key(e.title) for e in entries]
                if prior.geometry_matches(thumb) and prior.order_matches(keys) and len(keys)>=2 and all(prior.record(k) for k in keys):
                    predicted=[e.discovered_position[2]+prior.scroll_scale*thumb[0] for e in entries]
                    prior_matches=all(abs(y-prior.record(k).locator.absolute_y)<=60 for y,k in zip(predicted,keys))
                if not prior_matches:invalidateIndex('fresh top anchors or geometry changed')
            # The accepted scan-page ordinal is unique even on test clocks or
            # platforms where monotonic_ns is coarse/frozen for one process.
            frame_id=n
            _add(acc,d,entries,frame_id,n>0)
            if phase=='bootstrap':metrics.bootstrapFrames+=1
            else:metrics.calibratedFrames+=1
            n+=1
            publish(f'正在建立每日任务位置索引：第 {n} 屏，{len(acc.entries)} 项…')
            status=acc.bootstrapStatus()
            if phase=='bootstrap' and status['ready']:
                if prior_matches and prior and abs(prior.scroll_scale-status['scroll_scale'])<=.10*status['scroll_scale']:
                    acc.applyScale(prior.scroll_scale);reused=True
                phase='calibrated';stable=0
                logger.info('[DailyScan] bootstrap complete frames=%s overlapSamples=%s repeatedTitles=%s scrollScale=%.4f cardPitch=%.1f scaleDispersion=%.4f pitchDispersion=%.4f',
                    status['frames'],status['overlap_samples'],status['repeated_titles'],status['scroll_scale'],
                    status['card_pitch'],status['scale_dispersion'],status['pitch_dispersion'])
            if thumb[1]>=574:break
            if phase=='calibrated':
                stable+=1
                if stable>=3:stride=min(380,stride+20)
            safe(d)
            if phase=='calibrated':
                # Finish independent verification within the forward overlap;
                # avoid leaving every middle card for a later targeted trip.
                shift=_nextScanShift(entries,acc,stride)
                anchor=entries[-1]
                if len(entries)>=3 and not acc.verified(q._title_key(entries[-2].title)):anchor=entries[-2]
                anchor_key=q._title_key(anchor.title)
                anchor_absolute=acc.absolute.get(anchor_key,anchor.discovered_position[2]+acc.scroll_scale*thumb[0])
                target_local=anchor.discovered_position[2]-shift
                d,pending_entries,_=advanceScan(d,entries,acc,deadline,n,phase='calibrated',
                    target_thumb=thumb[0]+shift/acc.scroll_scale,target_absolute_y=anchor_absolute,
                    target_local_y=target_local,distance=stride,metrics=metrics)
            else:
                distance=_bootstrapShift(entries)
                d,pending_entries,_=advanceScan(d,entries,acc,deadline,n,phase='bootstrap',distance=distance,metrics=metrics)
        if phase!='calibrated':raise ScriptStop('每日任务bootstrap未达到稳定校准条件，未发布完整列表')
        if not acc.scroll_scale:raise ScriptStop('每日任务没有足够重叠样本校准滚动条比例，未发布完整列表')
        top_key=min(acc.absolute,key=acc.absolute.get)
        first_observation=acc.observations_by_title[top_key][0]
        if first_observation.thumb_top>101 or first_observation.local_y>220:top_key=None
        pending=sorted((k for k in acc.unverified() if k!=top_key),key=acc.absolute.get)
        deferred=[]
        if pending and 99<(acc.absolute[pending[0]]-185)/acc.scroll_scale<=115:
            deferred=[k for k in pending if acc.absolute[k]-acc.absolute[pending[0]]<=410]
        d=_targeted(acc,deadline,metrics,d,top_key,deferred)
        deferred=[k for k in deferred if k in acc.entries and not acc.verified(k)]
        if deferred:
            # Reuse the final normalization journey for a low-position group,
            # rather than making an early trip there and returning again later.
            # These are ordinary independent-position checks, not edge waivers.
            prior_frame=d
            d,_=seekApprox((acc.absolute[deferred[0]]-185)/acc.scroll_scale,deadline,d,
                           absolute_y=acc.absolute[deferred[0]],scroll_scale=acc.scroll_scale,local_y=185,mode='deferred-recheck')
            if d is prior_frame:d=capture();safe(d)
            rows=[];metrics.targetedRechecks+=1
            for key in deferred:
                rows.extend(localEntries(d,acc.absolute[key]-acc.scroll_scale*q._scrollbar(d.im)[0]))
            _add(acc,d,list({q._title_key(e.title):e for e in rows}.values()),metrics.screensCaptured)
            d=_resolveConflicts(acc,deadline,metrics,d)
            if any(k in acc.entries and not acc.verified(k) for k in deferred):
                raise ScriptStop('返回顶部途中的定点标题/AP独立确认失败，未发布列表')
        # The required final return to the top is also the independent top-edge
        # recheck. Do not make a separate early trip to this same boundary.
        d,_=seekEndpoint('top',deadline,d);safe(d)
        d,entries=_readScanTop(d,n,deadline);_add(acc,d,entries,metrics.screensCaptured)
        first=min(acc.absolute,key=acc.absolute.get)
        if not _find(entries,first):raise ScriptStop('每日任务顶部边缘标题/AP未确认，未发布列表')
        if len(acc.observations_by_title[first])<2:
            d=capture();safe(d);d,entries=_readPage(d,n);_add(acc,d,entries,metrics.screensCaptured)
            if not _find(entries,first):raise ScriptStop('每日任务顶部边缘复读失败，未发布列表')
        acc.edge_rechecks.add(first);metrics.targetedRechecks+=1
        try:index=acc.build()
        except DailyIndexError as e:raise ScriptStop(f'每日任务索引未通过完整性校验：{e}') from e
        remember(index);metrics.elapsedSeconds=time.monotonic()-start
        publish(f'已确认 {index.entry_count} 项任务')
        logger.info('[DailyScan] entries=%s screens=%s bootstrapFrames=%s bootstrapOverlapSamples=%s bootstrapOverlapRecoveries=%s calibratedFrames=%s continuityRecoveries=%s fullOCR=%s localOCR=%s drags=%s quantized=%s noProgress=%s recoveredNoProgress=%s contentFallbacks=%s endpointRecoveries=%s targeted=%s gaps=%s elapsed=%.2f',
                    index.entry_count,metrics.screensCaptured,metrics.bootstrapFrames,metrics.bootstrapOverlapSamples,
                    metrics.bootstrapOverlapRecoveries,metrics.calibratedFrames,metrics.continuityRecoveries,
                    metrics.fullOcrCalls,metrics.localOcrCalls,metrics.scrollbarDrags,metrics.quantizedAccepts,
                    metrics.noProgressAttempts,metrics.recoveredNoProgress,metrics.contentFallbacks,metrics.endpointRecoveries,
                    metrics.targetedRechecks,metrics.gapRecoveries,metrics.elapsedSeconds)
        return dict(type='DailyQuestScan',entries=[entryFromRecord(e) for e in index.entries],screens=metrics.screensCaptured,
                    complete=True,reachedEnd=True,restoredTop=True,reverified=metrics.targetedRechecks,index=index,reusedCalibration=reused,metrics=asdict(metrics))

def _find(entries,key):
    import fgoQuickQuest as q
    matches=[e for e in entries if q._title_key(e.title)==key]
    if len(matches)>1:raise ScriptStop('每日任务目标出现重复标题，未唯一确认')
    return matches[0] if matches else None

def locate(entry,index,metrics,deadline):
    import fgoQuickQuest as q
    key=q._title_key(entry.title);record=index.record(key)
    if not record:return None
    d=capture();safe(d)
    if not index.geometry_matches(q._scrollbar(d.im)):invalidateIndex('scrollbar geometry changed');return None
    requested=index.target_thumb(record.locator.absolute_y)
    d,scroll=seekApprox(requested,deadline,d,absolute_y=record.locator.absolute_y,
                        scroll_scale=index.scroll_scale,local_y=185,mode='locate')
    y=record.locator.absolute_y-index.scroll_scale*q._scrollbar(d.im)[0]
    entries=localEntries(d,y)
    if not index.order_matches([q._title_key(e.title) for e in entries]):invalidateIndex('title order conflict');return None
    target=_find(entries,key);mode='index'
    if target is None:
        anchors=[index.record(k) for k in (record.locator.before_key,record.locator.after_key) if k]
        anchor_seen=False;mode='neighbor'
        for anchor in anchors:
            _checkDeadline(deadline);anchor_thumb=index.target_thumb(anchor.locator.absolute_y,300)
            d,scroll=seekApprox(anchor_thumb,deadline,
                absolute_y=anchor.locator.absolute_y,scroll_scale=index.scroll_scale,local_y=300,mode='neighbor-anchor')
            ay=anchor.locator.absolute_y-index.scroll_scale*q._scrollbar(d.im)[0]
            if not _find(localEntries(d,ay),anchor.title_key):continue
            anchor_seen=True
            abs_target=record.locator.absolute_y
            if len(anchors)==2:abs_target=sum(a.locator.absolute_y for a in anchors)/2
            for offset in (0,-60,60):
                requested=index.target_thumb(abs_target,185+offset)
                d,scroll=seekApprox(requested,deadline,
                    absolute_y=abs_target,scroll_scale=index.scroll_scale,local_y=185+offset,mode='neighbor-seek')
                y=abs_target-index.scroll_scale*q._scrollbar(d.im)[0]
                target=_find(localEntries(d,y),key)
                if target:break
            if target:break
        if not target:
            if anchor_seen:raise ScriptStop('已定位目标卡槽，但标题未通过确认；未点击')
            invalidateIndex('target and neighboring anchors missing');return None
    d,target=alignTarget(entry,key,d,target,deadline,metrics,mode)
    y=target.discovered_position[2]
    logger.info('[DailyLocate] target=%s requestedThumb=%.1f actualThumb=%.1f predictedY=%.1f mode=%s drag=%s microAdjust=%s',
                entry.title,scroll.requested_thumb,scroll.actual_thumb,y,mode,metrics.scrollbarDrags,metrics.microAdjustments)
    return dict(type='DailyQuestReady',entry=entry,position=target.discovered_position[1:],mode=mode,
                requestedThumb=scroll.requested_thumb,actualThumb=scroll.actual_thumb,predictedY=y)

def alignTarget(entry,key,d,target,deadline,metrics,mode='index'):
    """Fine-align only a target title already proved by local title + AP OCR."""
    import fgoQuickQuest as q
    _checkDeadline(deadline);safe(d);cy=target.discovered_position[2]
    if not 125<=cy<=220:
        delta=cy-185;q._menuSwipe((950,420),(950,420-max(-180,min(180,delta))))
        metrics.microAdjustments+=1;schedule.sleep(.35);d=capture();safe(d)
        target=_find(localEntries(d,185),key)
        if not target or not 125<=target.discovered_position[2]<=220:
            raise ScriptStop('每日任务索引一次有限对齐后未通过标题/AP最终确认，未点击')
    # Another fresh title/AP observation authorizes readiness; position alone is not enough.
    d=capture();safe(d);again=_find(localEntries(d,target.discovered_position[2]),key)
    if not again or not 125<=again.discovered_position[2]<=220:raise ScriptStop('每日任务最终标题/AP确认失败，未点击')
    return d,again

def goto(entry):
    import fgoQuickQuest as q
    if not isinstance(entry,q.DailyQuestEntry):raise ScriptStop('每日任务队列项格式无效')
    if q.XDetect.region!='CN':raise ScriptStop('每日任务定位仅适配简体中文服务器')
    start=time.monotonic();metrics=DailyScanMetrics();deadline=start+q.DAILY_SCAN_TIMEOUT
    with measuring(metrics):
        q.openDailyPageCN()
        # Legacy/offline callers with no advisory metadata retain the controlled
        # sequential route. A connected runtime can also reload the local cache.
        index=currentIndex() if entry.locator is not None or getattr(q.fgoDevice.device,'available',False) else _cached
        result=locate(entry,index,metrics,deadline) if index else None
        if result is None and (entry.locator is not None or getattr(q.fgoDevice.device,'available',False)) and (anchor:=advisoryAnchor(q._title_key(entry.title))):
            result=locateAnchor(entry,anchor,metrics,deadline)
        if result is None:
            metrics.fallbacks+=1;result=q._gotoDailyEntrySequential(entry,opened=True)
            result['mode']='fallback'
            if not getattr(q.fgoDevice.device,'available',False):
                metrics.elapsedSeconds=time.monotonic()-start;result['metrics']=asdict(metrics);return result
            d=capture();safe(d);thumb=q._scrollbar(d.im);found=_find(localEntries(d,result['position'][1]),q._title_key(entry.title))
            if not found:raise ScriptStop('每日任务fallback后未重新确认标题/AP，未点击')
            # Even without a calibrated complete index, preserve the actual
            # anchor for the next queue item; never fabricate a global scale.
            rememberAnchor(entry,thumb,found.discovered_position[2])
            result['entry']=replace(entry,locator=DailyQuestLocator(thumb[0],thumb[1],found.discovered_position[2]))
        metrics.elapsedSeconds=time.monotonic()-start;result['metrics']=asdict(metrics)
        logger.info('[DailyLocate] target=%s requestedThumb=%s actualThumb=%s predictedY=%s mode=%s drag=%s microAdjust=%s elapsed=%.2f',
                    entry.title,result.get('requestedThumb'),result.get('actualThumb'),result.get('predictedY'),
                    result['mode'],metrics.scrollbarDrags,metrics.microAdjustments,metrics.elapsedSeconds)
        return result

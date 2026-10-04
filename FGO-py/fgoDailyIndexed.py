"""Guarded CN menu-only indexed scanning/positioning; never selects a quest."""
from dataclasses import asdict,replace
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import json,time
from statistics import median
from fgoDailyIndex import (DailyScanAccumulator,DailyScanMetrics,DailyIndexError,DailyQuestLocator,
                          DailyQuestIndex,DailyIndexRecord,DailyObservation,save_index,load_index,fingerprint)
from fgoSchedule import ScriptStop,schedule
from fgoLogging import getLogger

logger=getLogger('DailyIndex');_metrics=ContextVar('daily_metrics',default=None)
_cached=None;_invalid=False;_anchors={};_dragGain=1.;_dragSamples=[]

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

def invalidate(reason):
    global _cached,_invalid,_anchors
    _cached=None;_invalid=True;_anchors={}
    logger.warning('Daily index invalidated: %s',reason)
    path=cachePath();path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'version':1,'invalidated':True,'reason':reason}),encoding='utf-8')

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
        invalidate('partial anchor geometry changed');return None
    d=dragTo(anchor['thumb_top'],deadline,d)
    key=q._title_key(entry.title);target=_find(localEntries(d,anchor['local_y']),key)
    if not target:invalidate('partial anchor title missing');return None
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
    if not q._isDailyPage(d):
        invalidate('daily header changed')
        raise ScriptStop('每日任务标题已变化，索引失效，未点击')
    q._dailyLocatorFrameCN(d)
    d._indexedSafeFrame=d.im

def dragTo(target,deadline,detect=None):
    """Positive DAILY + actual scrollbar, at most one input and two corrections."""
    import fgoQuickQuest as q
    global _dragGain
    d=detect or capture()
    for attempt in range(3):
        _checkDeadline(deadline);safe(d);top,bottom=q._scrollbar(d.im);height=bottom-top
        target=max(99,min(575-height,float(target)));error=target-top
        if abs(error)<=2 and (target<575-height or bottom>=574) or target==99 and top<=101:return d
        center=round((top+bottom)/2)
        motion=error/_dragGain
        endpoint=max(100,min(574,round(center+motion)))
        q._menuScrollbarDrag((1258,center),(1258,endpoint))
        count('scrollbarDrags');schedule.sleep(.1);d=capture();safe(d)
        for sample in range(3):
            _checkDeadline(deadline)
            try:new=q._scrollbar(d.im);break
            except ScriptStop as error:
                if sample==2 or '未唯一识别每日任务滚动条' not in str(error):raise
                # A released handle can have one transient render frame. Re-read
                # only; never repeat the drag without positive geometry.
                d=capture();safe(d)
        moved=new[0]-top
        # The CN handle's physical drag gain is about .93, not exactly 1.
        # Learn only from a substantial, positively observed movement.
        physical=endpoint-center
        if abs(physical)>=5 and abs(moved)>=2 and new[0]>101 and new[1]<574 and .65<=moved/physical<=1.2:
            _dragSamples.append(moved/physical);del _dragSamples[:-21]
            if len(_dragSamples)>=3:_dragGain=float(median(_dragSamples))
        if abs((new[1]-new[0])-height)>2:raise ScriptStop('每日任务滚动条几何发生变化，已停止拖动')
        if abs(new[0]-target)<=2 and (target<575-height or new[1]>=574) or target==99 and new[0]<=101:return d
    raise ScriptStop('每日任务滚动条跳转有限校正仍未达到目标，未点击')

def _readPage(d,n):
    import fgoQuickQuest as q
    if not q._isDailyPage(d):raise ScriptStop('每日任务扫描页面已变化，未发布列表')
    safe(d)
    frame,entries=q._observeDailyScanPage(d,n)
    return frame,sorted(entries,key=lambda e:e.discovered_position[2])

def localEntries(d,y,radius=60):
    """Local proposals are accepted only by real full-title consensus + own AP."""
    import fgoQuickQuest as q
    top=max(95,int(y-radius));bottom=min(695,int(y+radius+105))
    spans=q.OCR.ZHS.detect_and_ocr(d.im[top:bottom,750:910],drop_score=.5)
    proposals=q.parseDailyQuestEntries(spans,d.im,0,(750,top));entries=[];apMap={}
    rows=[sum((q._span_rect(s,(750,top))[1],q._span_rect(s,(750,top))[3]))/2 for s in spans if q.re.fullmatch(r'AP\d+',q._compact_title(s.text),q.re.I)]
    for e in proposals:
        cy=e.discovered_position[2]
        if not 120<=cy<=600:continue
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
        if not 120<=cy<=600:continue
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

def _continuous(acc,entries,thumb):
    import fgoQuickQuest as q
    if not acc.frame_order:return True
    old=acc.frame_order[-1][1];keys=[q._title_key(e.title) for e in entries]
    if set(old)&set(keys):return True
    if not acc.scroll_scale or not acc.card_pitch or not old or not entries:return False
    before=acc.absolute[old[-1]];after=entries[0].discovered_position[2]+acc.scroll_scale*thumb[0]
    return .65*acc.card_pitch<=after-before<=1.3*acc.card_pitch

def _targeted(acc,deadline,metrics,d=None,top_key=None):
    import fgoQuickQuest as q
    # Conflicting OCR aliases occupy one slot. Resolve only with independent
    # real title/AP observations; two competing verified names remain unsafe.
    for _ in range(3):
        conflicts=acc.conflicts()
        if not conflicts:break
        for a,b in conflicts:
            absolute=(acc.absolute[a]+acc.absolute[b])/2
            for y in (185,275):
                metrics.targetedRechecks+=1;prior=d
                d=dragTo((absolute-y)/acc.scroll_scale,deadline,d)
                if d is prior:d=capture();safe(d)
                entries=localEntries(d,absolute-acc.scroll_scale*q._scrollbar(d.im)[0])
                _add(acc,d,entries,metrics.screensCaptured)
            verified=[k for k in (a,b) if acc.verified(k)]
            if len(verified)!=1:raise ScriptStop('同一卡槽的标题仍有冲突，未发布完整列表')
            stale=b if verified[0]==a else a
            del acc.entries[stale];del acc.observations_by_title[stale];acc.calibrate()
    if acc.conflicts():raise ScriptStop('每日任务标题位置冲突未解决，未发布完整列表')
    # Recover actual content gaps, not names, with finite local-only observations.
    for _ in range(3):
        gaps=acc.gaps()
        if not gaps:break
        for gap in gaps:
            found=False
            for offset in (0,-60,60):
                _checkDeadline(deadline);metrics.targetedRechecks+=1
                target=(gap.expected_absolute_y-200+offset)/acc.scroll_scale
                d=dragTo(target,deadline,d);y=gap.expected_absolute_y-acc.scroll_scale*q._scrollbar(d.im)[0]
                entries=localEntries(d,y);before=len(acc.entries)
                _add(acc,d,entries,metrics.screensCaptured)
                if len(acc.entries)>before:metrics.gapRecoveries+=1;found=True;break
            if not found:raise ScriptStop('每日任务内容缺口定点复核失败，未发布完整列表')
    if acc.gaps():raise ScriptStop('每日任务内容仍有未解决缺口，未发布完整列表')
    # Group nearby single observations on one newly acquired frame. OCR remains
    # local per predicted band; edge exceptions are explicitly rechecked here.
    for _ in range(3):
        pending=sorted((k for k in acc.unverified() if k!=top_key),key=acc.absolute.get)
        if not pending:return d
        while pending:
            first=pending.pop(0);group=[first]
            while pending and acc.absolute[pending[0]]-acc.absolute[first]<=410:group.append(pending.pop(0))
            original=acc.observations_by_title[first][0]
            target=(acc.absolute[first]-185)/acc.scroll_scale
            # Change alignment enough for independent positional evidence.
            if abs(target-original.thumb_top)*acc.scroll_scale<30:target+=(30 if target>=original.thumb_top else -30)/acc.scroll_scale
            previous_frame=d
            d=dragTo(target,deadline,d)
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
    if any(k!=top_key for k in acc.unverified()):raise ScriptStop('每日任务单次观测定点复核仍未确认，未发布完整列表')
    return d

def scan():
    import fgoQuickQuest as q
    from fgoNavigation import publish
    if q.XDetect.region!='CN':raise ScriptStop('每日任务 OCR 仅适配简体中文服务器')
    metrics=DailyScanMetrics();start=time.monotonic();deadline=start+q.DAILY_SCAN_TIMEOUT
    acc=DailyScanAccumulator(q._title_key);prior=currentIndex();reused=False
    with measuring(metrics):
        d=capture()
        if not q._isDailyPage(d):q.openDailyPageCN();d=capture()
        safe(d);d=dragTo(99,deadline,d);stride=280;stable=0;stalled=0;n=0
        while True:
            _checkDeadline(deadline);planned=q._scrollbar(d.im)[0]
            d,entries=_readPage(d,n);thumb=q._scrollbar(d.im)
            if acc.frame_order and thumb[0]<acc.frame_order[-1][0]-2:
                d=dragTo(planned,deadline,d);d,entries=_readPage(d,n);thumb=q._scrollbar(d.im)
            if not entries:raise ScriptStop('未校验到完整每日任务卡片，请检查识别日志')
            if n==0 and prior:
                keys=[q._title_key(e.title) for e in entries]
                if prior.geometry_matches(thumb) and prior.order_matches(keys) and len(keys)>=2 and all(prior.record(k) for k in keys):
                    predicted=[e.discovered_position[2]+prior.scroll_scale*thumb[0] for e in entries]
                    if all(abs(y-prior.record(k).locator.absolute_y)<=60 for y,k in zip(predicted,keys)):
                        acc.scroll_scale=prior.scroll_scale;reused=True
                if not reused:invalidate('fresh top anchors or geometry changed')
                else:stable=3;stride=360
            if not _continuous(acc,entries,thumb):
                previous=acc.frame_order[-1][0]
                # Return toward the last verified anchor, not a full reverse pass.
                for retry in range(2):
                    stride=180;metrics.gapRecoveries+=1
                    d=dragTo(previous+(thumb[0]-previous)/(2**(retry+1)),deadline,d)
                    d,entries=_readPage(d,n);thumb=q._scrollbar(d.im)
                    if _continuous(acc,entries,thumb):break
                else:raise ScriptStop('每日任务相邻屏连续覆盖未恢复，未发布完整列表')
            _add(acc,d,entries,metrics.screensCaptured,True);n+=1
            publish(f'正在建立每日任务位置索引：第 {n} 屏，{len(acc.entries)} 项…')
            if thumb[1]>=574:break
            stable+=1
            if stable>=3 and acc.scroll_scale:stride=min(380,stride+20)
            safe(d)
            if acc.scroll_scale and stable>=3:
                # Place the last real visible anchor near the top. This keeps
                # three complete cards in view and avoids inertial swipe skips.
                # Advance stays within the same bounded adaptive content step.
                shift=max(180,min(stride,entries[-1].discovered_position[2]-170))
                d=dragTo(thumb[0]+shift/acc.scroll_scale,deadline,d)
            else:q._swipe_input_only(d,False,stride);d=capture()
            new=q._scrollbar(d.im);stalled=stalled+1 if new[0]<=thumb[0]+1 else 0
            if stalled>=3:raise ScriptStop('每日任务滚动条连续未向末端移动，未发布不完整列表')
        if not acc.scroll_scale:raise ScriptStop('每日任务没有足够重叠样本校准滚动条比例，未发布完整列表')
        top_key=min(acc.absolute,key=acc.absolute.get)
        first_observation=acc.observations_by_title[top_key][0]
        if first_observation.thumb_top>101 or first_observation.local_y>220:top_key=None
        d=_targeted(acc,deadline,metrics,d,top_key)
        # The required final return to the top is also the independent top-edge
        # recheck. Do not make a separate early trip to this same boundary.
        d=dragTo(99,deadline,d);safe(d)
        if q._scrollbar(d.im)[0]>101:raise ScriptStop('每日任务完成后未确认顶部，未发布列表')
        d,entries=_readPage(d,n);_add(acc,d,entries,metrics.screensCaptured)
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
        logger.info('[DailyScan] entries=%s screens=%s fullOCR=%s localOCR=%s targeted=%s gaps=%s elapsed=%.2f',
                    index.entry_count,metrics.screensCaptured,metrics.fullOcrCalls,metrics.localOcrCalls,metrics.targetedRechecks,metrics.gapRecoveries,metrics.elapsedSeconds)
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
    if not index.geometry_matches(q._scrollbar(d.im)):invalidate('scrollbar geometry changed');return None
    d=dragTo(index.target_thumb(record.locator.absolute_y),deadline,d)
    y=record.locator.absolute_y-index.scroll_scale*q._scrollbar(d.im)[0]
    entries=localEntries(d,y)
    if not index.order_matches([q._title_key(e.title) for e in entries]):invalidate('title order conflict');return None
    target=_find(entries,key);mode='index'
    if target is None:
        anchors=[index.record(k) for k in (record.locator.before_key,record.locator.after_key) if k]
        anchor_seen=False;mode='neighbor'
        for anchor in anchors:
            _checkDeadline(deadline);d=dragTo(index.target_thumb(anchor.locator.absolute_y,300),deadline)
            ay=anchor.locator.absolute_y-index.scroll_scale*q._scrollbar(d.im)[0]
            if not _find(localEntries(d,ay),anchor.title_key):continue
            anchor_seen=True
            abs_target=record.locator.absolute_y
            if len(anchors)==2:abs_target=sum(a.locator.absolute_y for a in anchors)/2
            for offset in (0,-60,60):
                d=dragTo(index.target_thumb(abs_target,185+offset),deadline)
                target=_find(localEntries(d,abs_target-index.scroll_scale*q._scrollbar(d.im)[0]),key)
                if target:break
            if target:break
        if not target:
            if anchor_seen:raise ScriptStop('已定位目标卡槽，但标题未通过确认；未点击')
            invalidate('target and neighboring anchors missing');return None
    for attempt in range(3):
        safe(d);cy=target.discovered_position[2]
        if 125<=cy<=220:
            # Another acquisition and own title/AP consensus authorize readiness.
            d=capture();safe(d);again=_find(localEntries(d,cy),key)
            if not again or not 125<=again.discovered_position[2]<=220:raise ScriptStop('每日任务最终标题/AP确认失败，未点击')
            return dict(type='DailyQuestReady',entry=entry,position=again.discovered_position[1:],mode=mode)
        if attempt==2:break
        delta=cy-185;q._menuSwipe((950,420),(950,420-max(-180,min(180,delta))))
        metrics.microAdjustments+=1;schedule.sleep(.35);d=capture();safe(d)
        target=_find(localEntries(d,185),key)
        if not target:raise ScriptStop('已定位目标卡槽，但标题未通过确认；未点击')
    raise ScriptStop('每日任务索引对齐超过两次微调，未点击')

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
        logger.info('[DailyLocate] target=%s mode=%s drag=%s microAdjust=%s elapsed=%.2f',entry.title,result['mode'],metrics.scrollbarDrags,metrics.microAdjustments,metrics.elapsedSeconds)
        return result

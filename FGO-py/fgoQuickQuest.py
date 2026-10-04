from dataclasses import dataclass
from fgoDailyIndex import DailyQuestLocator
import cv2,hashlib,re,time,unicodedata
import numpy
import fgoDevice
from fgoDetect import Detect,OCR,XDetect
from fgoSchedule import ScriptStop,schedule

DAILY_CATEGORY='daily'
DAILY_SCROLL_TIMEOUT=180
DAILY_SCAN_TIMEOUT=600
DAILY_NAV_SCROLL_LIMIT=10
DAILY_NAVIGATION_LIMIT=20
DAILY_NAV_CLOSE_LIMIT=3
# Locate title/AP rows in the left text column; full titles are read separately.
# Exclude timers, infinity icons and recommendation text from expensive OCR.
DAILY_TITLE_REGION=(750,105,910,695)
DAILY_VIEWPORT=(620,140,1120,675)
DIFFICULTIES=('极级','超级','上级','中级','初级')

@dataclass(frozen=True)
class DailyQuestEntry:
    title:str
    quest_type:str
    difficulty:str
    screenshot_signature:str
    discovered_position:tuple[int,int,int]
    @property
    def type(self):return 'daily'
    locator:DailyQuestLocator|None=None

def _clean_text(text):
    return unicodedata.normalize('NFKC',str(text)).replace('\u3000',' ').strip()

def _compact_title(text):
    text=re.sub(r'\s+','',_clean_text(text))
    # Normalize typography only; preserve class order and every title/difficulty.
    return re.sub(r'([<〈《「【])([剑弓枪骑术杀狂暗])[·・‧]?([剑弓枪骑术杀狂暗])篇([>〉》」】])',
                  lambda m:'<'+m[2]+'·'+m[3]+'篇>',text)

def _title_key(text):return re.sub(r'^每日替换','',_compact_title(text)).casefold()

def _valid_daily_title(text):
    # This is text hygiene, not a quest/class whitelist. Eligibility comes from
    # the daily page, the title band, its AP row and independent crop agreement.
    compact=re.sub(r'^每日替换','',_compact_title(text))
    if not 3<=len(compact)<=64 or not re.search(r'[\u4e00-\u9fff]',compact):return False
    if compact.startswith(('等级','推荐','职阶','AP','消耗','任务进度','任务进行度','关卡举办时间','每日任务','每日替换','之修炼场')):return False
    return compact not in ('初级','中级','上级','超级','极级','关闭','菜单','完成','自由关卡')

def _readDailyTitle(image,center):
    # Upscaling the same crop is not independent: the recognizer resizes it
    # back and can confidently repeat a wrong glyph (e.g. 术 -> 水/木).
    # Use different vertical context and grayscale instead; never repair names
    # from a class schedule or the requested target. Two of three must agree.
    reads={}
    def read(height,gray):
        y=int(round(center));line=image[y-height//2:y+height//2,775:1120]
        if gray:line=cv2.cvtColor(cv2.cvtColor(line,cv2.COLOR_BGR2GRAY),cv2.COLOR_GRAY2BGR)
        name,score=_dailyLine(OCR.ZHS,line)
        if score>=.85 and _valid_daily_title(name):reads.setdefault(_title_key(name),[]).append(name)
    for height,gray in ((20,False),(32,False)):read(height,gray)
    winners=[names for names in reads.values() if len(names)>=2]
    # Two equal first reads have the same outcome as the old three-read vote:
    # one additional vote cannot create a second winning pair.
    if len(winners)==1:return _format_title(winners[0][0],_difficulty(winners[0][0]))
    read(28,True)
    winners=[names for names in reads.values() if len(names)>=2]
    if not winners:
        # A broad line can drop a narrow glyph (弓). Re-read the same pixels
        # with two additional contexts; ambiguity still rejects the entire card.
        for height,gray in ((24,False),(20,True)):read(height,gray)
        winners=[names for names in reads.values() if len(names)>=2]
    return _format_title(winners[0][0],_difficulty(winners[0][0])) if len(winners)==1 else None

def _difficulty(text):
    compact=_compact_title(text)
    return next((value for value in DIFFICULTIES if compact.endswith(value)),'unknown')

def _format_title(text,difficulty):
    compact=_compact_title(text)
    if difficulty!='unknown':compact=compact[:-len(difficulty)].rstrip()+ ' '+difficulty
    if compact.startswith('每日替换'):
        compact='每日替换 '+compact[len('每日替换'):].strip()
    return compact

def _quest_type(text):
    compact=_compact_title(text)
    if '搜集种火' in compact or '种火' in compact:return 'ember'
    if '宝物库' in compact:return 'treasure'
    if '修炼场' in compact:return 'training'
    return 'unknown'

def _span_rect(span,offset=(0,0)):
    box=numpy.asarray(span.box,dtype=float).reshape(-1,2)
    x0,y0=box.min(axis=0);x1,y1=box.max(axis=0)
    return (int(x0+offset[0]),int(y0+offset[1]),int(x1+offset[0]),int(y1+offset[1]))

def parseDailyQuestEntries(detections,screenshot,scrollIndex=0,offset=(0,0),minScore=.8,requireCardMetadata=False):
    """Parse OCR title lines into dynamic daily-quest entries; contains no date/class/title list."""
    lines=[]
    for item in detections:
        if float(getattr(item,'score',1))<minScore:continue
        text=_clean_text(getattr(item,'text',''))
        if not text:continue
        rect=_span_rect(item,offset)
        x0,y0,x1,y1=rect
        if not (620<=x0<1120 and 110<=y0<675):continue
        lines.append({'text':text,'rect':rect,'cy':(y0+y1)/2})
    lines.sort(key=lambda row:(row['cy'],row['rect'][0]))
    groups=[]
    for line in lines:
        group=next((g for g in reversed(groups) if abs(line['cy']-g['cy'])<=12 and line['rect'][0]<=g['x1']+24),None)
        if group is None:
            groups.append({'parts':[line],'cy':line['cy'],'x1':line['rect'][2]})
        else:
            group['parts'].append(line)
            group['cy']=sum(p['cy'] for p in group['parts'])/len(group['parts'])
            group['x1']=max(group['x1'],line['rect'][2])
    entries=[]
    for group in groups:
        parts=sorted(group['parts'],key=lambda row:row['rect'][0])
        raw=' '.join(part['text'] for part in parts)
        difficulty=_difficulty(raw)
        if not _valid_daily_title(raw):continue
        if requireCardMetadata:
            # Only complete card titles with their AP row are actionable. Clipped
            # edge titles get another opportunity on the next overlapping page.
            if min(p['rect'][1] for p in parts)<120 or max(p['rect'][3] for p in parts)>530:continue
            if not any(re.fullmatch(r'AP\d+',_compact_title(item.text),re.I) and 740<=_span_rect(item,offset)[0]<900 and 40<=(_span_rect(item,offset)[1]+_span_rect(item,offset)[3])/2-group['cy']<=105 for item in detections):continue
        # Discard card chrome/status labels that happen to contain a difficulty word.
        compact=_compact_title(raw)
        if compact.startswith(('等级','推荐','职阶','AP','消耗','任务进度','任务进行度','关卡举办时间')):continue
        title=_format_title(raw,difficulty)
        x0=min(p['rect'][0] for p in parts); y0=min(p['rect'][1] for p in parts)
        x1=max(p['rect'][2] for p in parts); y1=max(p['rect'][3] for p in parts)
        x0=max(0,x0-12); y0=max(0,y0-28); x1=min(screenshot.shape[1],x1+12); y1=min(screenshot.shape[0],y1+28)
        crop=screenshot[y0:y1,x0:x1]
        if crop.size==0:signature=''
        else:
            small=cv2.resize(crop,(64,24),interpolation=cv2.INTER_AREA)
            signature=hashlib.sha256(small.tobytes()).hexdigest()[:16]
        entries.append(DailyQuestEntry(title,_quest_type(title),difficulty,signature,(int(scrollIndex),int((x0+x1)/2),int((y0+y1)/2))))
    return entries

def deduplicateDailyEntries(entries):
    unique={}
    for entry in entries:
        unique.setdefault(_title_key(entry.title),entry)
    return list(unique.values())

def _viewport(image):
    x0,y0,x1,y1=DAILY_VIEWPORT
    return cv2.resize(cv2.cvtColor(image[y0:y1,x0:x1],cv2.COLOR_BGR2GRAY),(100,107),interpolation=cv2.INTER_AREA)

def _viewportMoved(before,after,threshold=2.5):
    return float(numpy.mean(cv2.absdiff(_viewport(before),_viewport(after))))>threshold

def _dailyHeader(detect):
    image=detect.im
    if getattr(detect,'_dailyHeaderImage',None) is image:return detect._dailyHeaderValue
    spans=_dailyBatch(image[0:95,900:1280],drop_score=.35)
    value=any('每日任务' in _clean_text(item.text) for item in spans)
    detect._dailyHeaderImage=image;detect._dailyHeaderValue=value
    return value

def _dailyEntriesAt(detect,scrollIndex=0,strict=True):
    if detect.im.shape[:2]!=(720,1280):raise ScriptStop(f'每日任务扫描要求 1280x720，实际为 {detect.im.shape[1]}x{detect.im.shape[0]}')
    x0,y0,x1,y1=DAILY_TITLE_REGION
    if getattr(detect,'_dailyNavigationImage',None) is detect.im:
        # Foreground OCR can omit a low-level card's AP/title together. Read
        # the AP column independently in small overlapping local strips; every
        # complete AP row still requires its actual full-title consensus.
        spans=list(detect._dailyNavigationLabels)+_dailyAPSpans(detect.im);x0=y0=0
    else:spans=_dailyBatch(detect.im[y0:y1,x0:x1],drop_score=.5)
    entries=parseDailyQuestEntries(spans,detect.im,scrollIndex,(x0,y0))
    # Acceptance below still requires two local title reads plus the AP row.
    agreed=[]
    for entry in entries:
        y=entry.discovered_position[2]
        if not 120<=y<=600:continue
        hasAp=any(re.fullmatch(r'AP\d+',_compact_title(s.text),re.I) and 740<=_span_rect(s,(x0,y0))[0]<900 and 40<=(_span_rect(s,(x0,y0))[1]+_span_rect(s,(x0,y0))[3])/2-y<=105 for s in spans)
        if not hasAp:
            # CN multi-line OCR sometimes drops/misreads AP10. Independently
            # verify the same visible card's AP label with the Latin model.
            apText,apScore=_dailyLine(OCR.EN,detect.im[y+50:y+93,775:900])
            if apScore<.8 or not re.fullmatch(r'AP\d+',_compact_title(apText),re.I):continue
        title=_readDailyTitle(detect.im,y)
        if title:
            agreed.append(DailyQuestEntry(title,_quest_type(title),_difficulty(title),entry.screenshot_signature,entry.discovered_position))
    # An AP row well inside the viewport represents a complete card. Fail the
    # whole scan if its title is missing or disagrees; do not advertise a partial
    # recognition as a complete list or retain stale items from the previous day.
    apRows=[(_span_rect(s,(x0,y0))[1]+_span_rect(s,(x0,y0))[3])/2 for s in spans if re.fullmatch(r'AP\d+',_compact_title(s.text),re.I)]
    for y in apRows:
        if not 190<=y<=675 or any(40<=y-e.discovered_position[2]<=105 for e in agreed):continue
        # Recover a title rejected/missed by multi-line OCR using the AP row on
        # that actual card. Verify the fixed title band by crop consensus; never fill from a
        # schedule or from the requested quest name.
        title=_readDailyTitle(detect.im,y-75)
        if title:
            agreed.append(DailyQuestEntry(title,_quest_type(title),_difficulty(title),'',(int(scrollIndex),947,int(y)-75)))
    agreed.extend(_recoverDailyNeighborsCN(detect,agreed,apRows,scrollIndex))
    if strict and any(190<=y<=675 and not any(40<=y-e.discovered_position[2]<=105 for e in agreed) for y in apRows):raise ScriptStop('完整每日任务卡片的标题未通过双重校验；未发布扫描列表，请刷新重试')
    agreed=_dailyUniqueVisibleCards(agreed)
    detect._dailyVerifiedAP={_title_key(e.title):next((y for y in apRows if 40<=y-e.discovered_position[2]<=105),e.discovered_position[2]+71.5) for e in agreed}
    return agreed

def _recoverDailyNeighborsCN(detect,observed,apRows,scrollIndex=0):
    """Neighbour positions propose crops; only real title/AP pixels add a card."""
    centers=sorted(set(e.discovered_position[2] for e in observed))
    apRows=sorted(set(apRows));proposals=[]
    # Measure this screenshot's card spacing, never infer a missing quest name
    # or difficulty from a class schedule, cached task, or ordinal sequence.
    spacings=[b-a for rows in (centers,apRows) for a,b in zip(rows,rows[1:]) if 145<=b-a<=230]
    pitch=float(numpy.median(spacings)) if spacings else None
    unresolved=[y for y in apRows if 190<=y<=675 and not any(40<=y-c<=105 for c in centers)]
    if pitch is not None:
        for ap in unresolved:
            for anchor in centers:
                for direction in (-1,1):
                    center=anchor+direction*pitch
                    if 40<=ap-center<=105:proposals.append(center)
    # If A3 and A5 are both visible, interpolate the missing title band. A gap
    # must admit exactly one plausible number of equal CN card intervals.
    for a,b in zip(centers,centers[1:]):
        divisions=[n for n in range(2,4) if 145<=(b-a)/n<=230]
        if len(divisions)==1:
            n=divisions[0];proposals.extend(a+(b-a)*i/n for i in range(1,n))
    recovered=[];tested=[];known={_title_key(e.title) for e in observed}
    for value in proposals:
        center=int(round(value))
        if not 120<=center<=600 or any(abs(center-y)<12 for y in centers+tested):continue
        tested.append(center);schedule.checkStop()
        hasAp=any(40<=y-center<=105 for y in apRows)
        if not hasAp:
            ap,score=_dailyLine(OCR.EN,detect.im[center+50:center+93,775:900])
            if score<.8 or not re.fullmatch(r'AP\d+',_compact_title(ap),re.I):continue
        title=_readDailyTitle(detect.im,center)
        if not title or _title_key(title) in known:continue
        known.add(_title_key(title));recovered.append(DailyQuestEntry(title,_quest_type(title),_difficulty(title),'',(int(scrollIndex),947,center)))
        from fgoLogging import getLogger
        getLogger('QuickQuest').info(f'Daily neighbour crop verified: title={title!r}, y={center}, anchors={centers}, measured_pitch={pitch}')
    return recovered

def _scrollbar(image):
    if image.shape[:2]!=(720,1280):raise ScriptStop('每日任务滚动条识别要求 1280x720')
    hsv=cv2.cvtColor(image[95:585,1253:1264],cv2.COLOR_BGR2HSV)
    white=numpy.mean((hsv[...,1]<45)&(hsv[...,2]>210),axis=1)>.7
    edges=numpy.flatnonzero(numpy.diff(numpy.r_[False,white,False]))
    runs=[(int(a+95),int(b+95)) for a,b in zip(edges[::2],edges[1::2]) if b-a>=30]
    if len(runs)!=1:raise ScriptStop('未唯一识别每日任务滚动条，已停止菜单操作')
    return runs[0]

def _menuSwipe(begin,end):
    android=getattr(fgoDevice.device,'I',None)
    if isinstance(android,fgoDevice.Android) and android.name and android.display_info['orientation']==0:
        # Android's standard input command avoids dropped maxtouch drag packets
        # during GUI capture. Keep this transport change limited to menu swipes.
        points=[round(p[i]/android.scale+android.border[i]+android.render[i]) for p in (begin,end) for i in range(2)]
        with android.mutex:android.adb.shell('input touchscreen swipe '+' '.join(map(str,points))+' 350')
    else:fgoDevice.device.swipe(begin,end)

def _swipe(detect,toTop,distance=180):
    from fgoDailyIndexed import _metrics,safe
    if _metrics.get():safe(detect)
    before=detect.im
    _swipe_input_only(detect,toTop,distance)
    after=_dailyCapture(.2)
    return after,_viewportMoved(before,after.im)

def _scrollToTop():
    detect=_dailyCapture(.2)
    # The confirmed CN scrollbar supports direct dragging. This avoids dozens
    # of short swipes on long lists; verify the endpoint, never assume success.
    android=getattr(fgoDevice.device,'I',None)
    if XDetect.region=='CN' and isinstance(android,fgoDevice.Android) and android.name and _isDailyPage(detect):
        thumb=_scrollbar(detect.im)
        if thumb[0]>105:
            _menuSwipe((1258,sum(thumb)//2),(1258,100));schedule.sleep(.7)
            detect=_dailyCapture(.2)
            if not _isDailyPage(detect):raise ScriptStop('每日任务返回顶部时页面已变化，已停止')
    deadline=time.monotonic()+DAILY_SCROLL_TIMEOUT;stalled=0
    while time.monotonic()<deadline:
        thumb=_scrollbar(detect.im)
        after,_=_swipe(detect,True);newThumb=_scrollbar(after.im)
        if thumb[0]<=105 and newThumb[0]<=thumb[0]+1 and abs(newThumb[0]-thumb[0])<=1:return after,True
        stalled=stalled+1 if newThumb[0]>=thumb[0]-1 else 0
        if stalled>=3:raise ScriptStop('每日任务滚动条连续未向顶部移动，已停止定位')
        detect=after
    raise ScriptStop('每日任务列表返回顶部超时，已停止定位')

def _observeDailyScanPage(detect,scrollIndex=0,toTop=False):
    """Return both the verified entries and the frame after bounded recovery."""
    from fgoNavigation import publish
    try:return detect,_settledDailyEntriesAt(detect,scrollIndex)
    except ScriptStop as error:
        if '标题未通过双重校验' not in str(error):raise
    # Repeating identical pixels cannot recover a clipped/aliased glyph. Move
    # back into the already scanned overlap, never forward past unread cards.
    for attempt in range(2):
        if not _isDailyPage(detect):raise ScriptStop('每日任务标题复核时页面已变化，未发布列表')
        _scrollbar(detect.im)
        publish(f'正在调整每日任务标题位置复核：第 {scrollIndex+1} 屏，{attempt+1}/2…')
        detect,_=_swipe(detect,not toTop,60)
        if not _isDailyPage(detect):raise ScriptStop('每日任务标题复核时页面已变化，未发布列表')
        try:return detect,_dailyEntriesAt(detect,scrollIndex)
        except ScriptStop as error:
            if '标题未通过双重校验' not in str(error):raise
    raise ScriptStop(f'每日任务第 {scrollIndex+1} 屏换位复核仍未通过；未发布不完整列表')

def _isDailyPage(detect):return _dailyHeader(detect)

def _navigationLabels(detect):
    return [(_clean_text(item.text),_span_rect(item)) for item in _dailyBatch(detect.im,drop_score=.5)]

def _navigationLabel(labels,text,region):
    x0,y0,x1,y1=region
    matches=[rect for title,rect in labels if _title_key(title)==_title_key(text) and x0<=(rect[0]+rect[2])/2<x1 and y0<=(rect[1]+rect[3])/2<y1]
    if len(matches)>1:raise ScriptStop(f'导航入口“{text}”重复，未选择任何关卡')
    if not matches:return None
    rect=matches[0]
    return ((rect[0]+rect[2])//2,(rect[1]+rect[3])//2)

def dailyNavigationAction(labels):
    """Choose only navigation controls on a positively identified CN page."""
    header=(900,0,1280,95);cards=(640,95,1230,600);back=(0,0,200,95)
    # A visible confirmation must not be treated as a navigable background.
    if any(350<=(r[0]+r[2])/2<1100 and 180<=(r[1]+r[3])/2<650 and (_title_key(t) in ('取消','确定','确认','开始','ok','cancel') or '是否' in t) for t,r in labels):return ('blocked',None)
    if _navigationLabel(labels,'每日任务',header):return ('ready',None)
    if _navigationLabel(labels,'迦勒底之门',header):
        position=_navigationLabel(labels,'每日任务',cards)
        return ('daily',position) if position else ('scroll',None)
    close=_navigationLabel(labels,'关闭',back)
    listHeader=any(r[0]>=900 and r[1]<95 and len(_title_key(t))>=2 for t,r in labels)
    listTimer=any('关卡举办时间' in _title_key(t) and r[0]>=640 for t,r in labels)
    if close and (listHeader or listTimer):return ('close',close)
    if _navigationLabel(labels,'通知',back):
        position=_navigationLabel(labels,'迦勒底之门',cards)
        return ('gate',position) if position else ('scroll',None)
    return ('blocked',None)

def _openDailyFromTerminalCN():
    """Open the CN daily-quest list without selecting or starting a battle."""
    if XDetect.region!='CN':raise ScriptStop('每日任务快捷入口仅适配简体中文服务器')
    closes=scrolls=unchanged=transitionWaits=0;lastTap=None;toTop=True
    for _ in range(DAILY_NAVIGATION_LIMIT):
        detect=_dailyCapture(.3)
        if detect.im.shape[:2]!=(720,1280):raise ScriptStop('每日任务快捷入口仅支持 1280x720 横屏')
        action,position=dailyNavigationAction(_navigationLabels(detect)) if detect.isMainInterface() else ('blocked',None)
        if action=='ready':return {'type':'DailyPage'}
        if action=='blocked':
            # Navigation animations can temporarily hide both the menu and its title.
            # Only wait after a verified navigation tap; never act on the unknown frame.
            if lastTap is not None and transitionWaits<3:
                transitionWaits+=1
                schedule.sleep(.5)
                continue
            raise ScriptStop('未能唯一确认每日任务导航入口，或存在确认弹窗；请关闭弹窗或返回主界面后刷新')
        transitionWaits=0
        if action in ('gate','daily') and lastTap==(action,position):
            unchanged+=1
            if unchanged>=3:raise ScriptStop('点击导航入口后页面未变化，已停止重复点击')
            schedule.sleep(.3)
            continue
        unchanged=0
        if action=='scroll':
            if scrolls>=DAILY_NAV_SCROLL_LIMIT:raise ScriptStop('主目录入口未找到；已停止导航滚动，未选择任何关卡')
            scrolls+=1
            after,moved=_swipe(detect,toTop)
            if not moved:
                # Pinned costume quests can precede Daily in the Gate directory.
                # Unchanged pixels alone do not prove an endpoint (a drag may fail).
                # Only two positive scrollbar endpoints authorize reversing once.
                thumbs=(_scrollbar(detect.im),_scrollbar(after.im))
                endpoint=all(t[0]<=105 for t in thumbs) if toTop else all(t[1]>=575 for t in thumbs)
                if not endpoint:raise ScriptStop('导航滚动未移动且未确认列表边界，已停止；未选择任何关卡')
                if not toTop:raise ScriptStop('已扫描导航列表至底部，但未唯一识别入口；未选择任何关卡')
                toTop=False
                from fgoNavigation import publish
                publish('导航列表顶部未见入口，正在向下寻找…')
            lastTap=None
        else:
            if action=='daily':
                from fgoNavigation import publish
                publish('正在打开每日任务…')
            if action=='close':
                if closes>=DAILY_NAV_CLOSE_LIMIT:raise ScriptStop('返回主界面超过 3 层导航上限，已停止')
                closes+=1
            fgoDevice.device.touch(position)
            lastTap=(action,position)
            toTop=True
            schedule.sleep(.6)
    raise ScriptStop('每日任务导航超过有限步骤上限；未选择任何关卡')

def openDailyPageCN():
    """Every daily entry point uses the shared, guarded terminal normalization."""
    from fgoNavigation import normalizeToTerminalCN,publish,safeMenuPageCN,labels
    if XDetect.region!='CN':raise ScriptStop('每日任务快捷入口仅适配简体中文服务器')
    detect=_dailyCapture(.2)
    if safeMenuPageCN(detect,labels(detect))=='DAILY' and _isDailyPage(detect):return {'type':'DailyPage'}
    normalizeToTerminalCN()
    publish('正在进入迦勒底之门…')
    return _openDailyFromTerminalCN()

def _open_chapter(chapter):
    for _ in range(30):
        detect=_dailyCapture(.4)
        if detect.isMainInterface():break
    else:raise ScriptStop('等待关卡导航界面超时')
    for _ in range(10):
        detect=_dailyCapture(.4)
        if detect.isQuestListBegin():break
        fgoDevice.device.swipe((1000,200),(1000,600))
    else:raise ScriptStop('无法确认章节列表起始位置，已停止每日任务导航')
    for _ in range(20):
        detect=_dailyCapture(.4)
        if pos:=detect.findChapter(chapter):
            fgoDevice.device.touch(pos)
            schedule.sleep(.8)
            return
        fgoDevice.device.swipe((1000,600),(1000,200))
    raise ScriptStop(f'章节模板 {chapter} 搜索超限，已停止每日任务导航')

def _settledDailyEntriesAt(detect,scrollIndex=0):
    # Retry an OCR disagreement in place; never publish the partial frame.
    from fgoLogging import getLogger
    for attempt in range(3):
        try:return _dailyEntriesAt(detect,scrollIndex)
        except ScriptStop as error:
            if '标题未通过双重校验' not in str(error) or attempt==2:raise
            getLogger('QuickQuest').warning(f'Daily title disagreement at page {scrollIndex}; observation retry {attempt+1}/2')
            schedule.sleep(.4);detect=_dailyCapture(.2)
            if not _isDailyPage(detect):raise ScriptStop('每日任务标题重读时页面已变化，未发布列表')

def _reverifyDailyTitlesCN(entries,missing):
    # Presence verification has no first-card/launch-coordinate requirement.
    # A changed stride samples different crop alignments from both earlier passes.
    from fgoNavigation import publish
    pending=set(missing);detect,_=_scrollToTop();deadline=time.monotonic()+DAILY_SCAN_TIMEOUT
    stalled=0;page=0
    while time.monotonic()<deadline:
        if not _isDailyPage(detect):raise ScriptStop('每日任务复核时页面已变化，未发布列表')
        observed=_dailyEntriesAt(detect,page,strict=False)
        pending.difference_update(_title_key(e.title) for e in observed)
        if not pending:
            _scrollToTop();return
        publish(f'正在重新核对遗漏项：剩余 {len(pending)} 项，第 {page+1} 屏…')
        thumb=_scrollbar(detect.im)
        if thumb[1]>=574:break
        after,_=_swipe(detect,False,220);newThumb=_scrollbar(after.im)
        stalled=stalled+1 if newThumb[0]<=thumb[0]+1 else 0
        if stalled>=3:raise ScriptStop('每日任务遗漏项复核滚动没有进展，未发布列表')
        detect=after;page+=1
    titles=[e.title for e in entries if _title_key(e.title) in pending]
    raise ScriptStop(f'每日任务遗漏项未获独立确认，未发布列表：{titles}')

def scanDailyQuestsCN():
    from fgoDailyIndexed import scan
    from fgoAutomation import automationOwner
    with automationOwner.claim():return scan()


def refreshDailyQuestsCN():
    from fgoNavigation import normalizeToTerminalCN,publish,safeMenuPageCN,labels
    if XDetect.region!='CN':raise ScriptStop('每日任务刷新仅支持国服中文界面')
    detect=_dailyCapture(.2)
    # Already at the confirmed target: reset the list itself, avoiding an
    # unnecessary terminal/loading round trip. Modal guards still take priority.
    if safeMenuPageCN(detect,labels(detect))=='DAILY' and _isDailyPage(detect):
        publish('已确认每日任务页，直接重新扫描…')
        return scanDailyQuestsCN()
    openDailyPageCN()
    return scanDailyQuestsCN()


def gotoDailyEntry(entry):
    from fgoDailyIndexed import goto
    from fgoAutomation import automationOwner
    with automationOwner.claim():return goto(entry)

def _gotoDailyEntrySequential(entry,*,opened=False):
    """Return to top, then scroll the matched dynamic title into the first visible quest-card row."""
    if not isinstance(entry,DailyQuestEntry):raise ScriptStop('每日任务队列项格式无效')
    if XDetect.region!='CN':raise ScriptStop('每日任务定位仅适配简体中文服务器')
    if not opened:openDailyPageCN()
    detect,_=_scrollToTop()
    from fgoNavigation import publish
    from fgoLogging import getLogger
    deadline=time.monotonic()+DAILY_SCAN_TIMEOUT;stalled=0;page=0;alignments=0;aligning=False
    while time.monotonic()<deadline:
        if aligning:
            detect,entries=_reacquireDailyTargetCN(detect,entry,deadline)
        else:
            _dailyLocatorFrameCN(detect);previous=detect
            detect,entries=_observeDailyScanPage(detect,page)
            if detect is not previous:_dailyLocatorFrameCN(detect)
        schedule.checkStop()
        if time.monotonic()>=deadline:break
        matches=[item for item in entries if _title_key(item.title)==_title_key(entry.title)]
        getLogger('QuickQuest').debug(f'Daily locate target={entry.title!r}, phase={"align" if aligning else "search"}, page={page}, thumb={_scrollbar(detect.im)}, observed={[(e.title,e.discovered_position[2]) for e in entries]}')
        if len(matches)>1:raise ScriptStop(f'每日任务目标出现重复标题，未唯一确认：{entry.title}')
        if matches:
            target=matches[0]
            y=target.discovered_position[2]
            # Kernel.Main presses (845,203) for its first quest. Verify that
            # coordinate lies inside this exact card, rather than merely choosing
            # the first OCR title (a preceding card may be clipped at the top).
            if 125<=y<=220:
                publish(f'已确认出击位置：{entry.title}，标题 y={y}，未启动战斗')
                return {'type':'DailyQuestReady','entry':entry,'position':target.discovered_position[1:]}
            if alignments>=6:raise ScriptStop(f'目标卡片对齐超过有限次数，未启动战斗：{entry.title}')
            # Aim well inside the OCR/Kernel overlap. The old y=150 aim was
            # close to the crop boundary and treated a lost title as "not found".
            distance=max(-180,min(180,int(y-185)))
            start=420;end=start-distance
            publish(f'已找到 {entry.title}，正在对齐出击位置：y={y}，第 {alignments+1}/6 次…')
            _menuSwipe((950,start),(950,end));schedule.sleep(.8);after=_dailyCapture(.2)
            aligning=True;alignments+=1
            stalled=stalled+1 if abs(_scrollbar(after.im)[0]-_scrollbar(detect.im)[0])<=1 else 0
        else:
            if _scrollbar(detect.im)[1]>=574:raise ScriptStop(f'已到每日任务列表末端，但未确认“{entry.title}”，未启动战斗')
            publish(f'正在定位每日任务：{entry.title}，第 {page+1} 屏…')
            thumb=_scrollbar(detect.im);after,_=_swipe(detect,False,280);page+=1
            stalled=stalled+1 if _scrollbar(after.im)[0]<=thumb[0]+1 else 0
        if stalled>=3:raise ScriptStop('每日任务定位滚动没有进展，未启动战斗')
        detect=after
    raise ScriptStop(f'每日任务定位超时，未启动战斗：{entry.title}')

def _dailyLocatorFrameCN(detect):
    from fgoNavigation import safeMenuPageCN,labels
    schedule.checkStop()
    if detect.im.shape[:2]!=(720,1280):raise ScriptStop('每日任务定位截图尺寸异常，未点击')
    items=labels(detect)
    if not _isDailyPage(detect) or safeMenuPageCN(detect,items)!='DAILY':raise ScriptStop('每日任务定位页面已变化或存在危险状态，未点击')
    detect._dailyNavigationImage=detect.im;detect._dailyNavigationLabels=items
    if detect.isNetworkError():raise ScriptStop('每日任务定位出现网络错误，未确认或重试')

def _reacquireDailyTargetCN(detect,entry,deadline):
    """After a verified alignment, never resume a blind search past the target."""
    from fgoNavigation import publish
    for attempt in range(5):
        schedule.checkStop()
        if time.monotonic()>=deadline:raise ScriptStop('每日任务目标对齐复核超时，未启动战斗')
        _dailyLocatorFrameCN(detect)
        entries=_dailyEntriesAt(detect,strict=False)
        if any(_title_key(e.title)==_title_key(entry.title) for e in entries):return detect,entries
        if attempt==4:break
        if attempt<2:
            publish(f'正在原地重读已找到的目标：{entry.title}，第 {attempt+1}/2 次…')
            schedule.sleep(.3);detect=_dailyCapture(.2)
        else:
            # Every alignment scroll moves upward from a visible title y>220.
            # A small downward restoration returns to the known overlap.
            publish(f'正在回移复核已找到的目标：{entry.title}，第 {attempt-1}/2 次…')
            _scrollbar(detect.im);detect,_=_swipe(detect,True,60)
    raise ScriptStop(f'已找到“{entry.title}”，但对齐后失去唯一识别；已停止，未继续滚向末端或启动战斗')


def _dailyCapture(*args,**kwargs):
    from fgoDailyIndexed import count
    count('screensCaptured')
    return Detect(*args,**kwargs)

def _dailyBatch(image,**kwargs):
    return OCR.ZHS.detect_and_ocr(image,**kwargs)

def _dailyLine(model,*args,**kwargs):
    return model.ocr_single_line(*args,**kwargs)

def _swipe_input_only(detect,toTop,distance=180):
    from fgoDailyIndexed import count
    count('scrollSwipes')
    start=240 if distance==180 else 210
    _menuSwipe((950,start),(950,start+distance)) if toTop else _menuSwipe((950,start+distance),(950,start))
    schedule.sleep(.7)

def _dragDailyScrollbarTo(target_thumb_top):
    from fgoDailyIndexed import dragTo
    return dragTo(target_thumb_top,time.monotonic()+30)


def _menuScrollbarDrag(begin,end):
    """One held drag in the positively detected track, including a held tail.

    A short end-to-end swipe can be ignored within the thumb. A bounded
    excursion arms dragging; returning to the requested endpoint stays in the
    same gesture. Holding the final point avoids losing its last MOVE frame.
    """
    android=getattr(fgoDevice.device,'I',None)
    if isinstance(android,fgoDevice.Android) and android.name and android.display_info['orientation']==0:
        from airtest.core.android.android import Android as AirAndroid
        from fgoAutomation import noteDeviceInput
        direction=1 if end[1]>begin[1] else -1
        if not 100<=begin[1]+65*direction<=574:direction=-direction
        excursion=(1258,begin[1]+65*direction)
        end=(end[0],max(100,min(574,end[1])))
        points=[begin,excursion,end,end]
        points=[[round(p[i]/android.scale+android.border[i]+android.render[i]) for i in range(2)] for p in points]
        noteDeviceInput('daily scrollbar drag '+repr((begin,end)))
        with android.mutex:AirAndroid.swipe_along(android,points,duration=.12,steps=4)
    else:fgoDevice.device.swipe(begin,end)


def _dailyUniqueVisibleCards(entries):
    # Broad OCR and AP-neighbour recovery can propose the same actual card
    # twice with slightly different title centres. Merge only that spatially
    # coincident evidence; identical names on different cards remain ambiguous.
    result={}
    for entry in sorted(entries,key=lambda e:e.discovered_position[2]):
        key=_title_key(entry.title)
        if key in result:
            if abs(result[key].discovered_position[2]-entry.discovered_position[2])>20:
                raise ScriptStop('每日任务不同卡片出现重复标题，未唯一确认')
        else:result[key]=entry
    return list(result.values())


def _dailyAPSpans(image):
    from types import SimpleNamespace
    spans=[]
    for top,bottom in ((170,445),(425,700)):
        for span in _dailyBatch(image[top:bottom,775:900],drop_score=.5):
            if not re.fullmatch(r'AP\d+',_compact_title(span.text),re.I):continue
            rect=_span_rect(span,(775,top))
            spans.append(SimpleNamespace(text=span.text,box=rect,score=float(span.score)))
    return spans

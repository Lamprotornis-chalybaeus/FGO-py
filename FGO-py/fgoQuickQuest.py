from dataclasses import dataclass
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
DAILY_TITLE_REGION=(750,105,1120,610)
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
    @property
    def locator(self):return self.discovered_position[1:]

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
    for height,gray in ((20,False),(32,False),(28,True)):
        y=int(round(center));line=image[y-height//2:y+height//2,775:1120]
        if gray:line=cv2.cvtColor(cv2.cvtColor(line,cv2.COLOR_BGR2GRAY),cv2.COLOR_GRAY2BGR)
        name,score=OCR.ZHS.ocr_single_line(line)
        if score<.85 or not _valid_daily_title(name):continue
        reads.setdefault(_title_key(name),[]).append(name)
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
    spans=OCR.ZHS.detect_and_ocr(image[0:95,900:1280],drop_score=.35)
    return any('每日任务' in _clean_text(item.text) for item in spans)

def _dailyEntriesAt(detect,scrollIndex=0,strict=True):
    if detect.im.shape[:2]!=(720,1280):raise ScriptStop(f'每日任务扫描要求 1280x720，实际为 {detect.im.shape[1]}x{detect.im.shape[0]}')
    x0,y0,x1,y1=DAILY_TITLE_REGION
    spans=OCR.ZHS.detect_and_ocr(detect.im[y0:y1,x0:x1],drop_score=.5)
    entries=parseDailyQuestEntries(spans,detect.im,scrollIndex,(x0,y0))
    # Acceptance below still requires two local title reads plus the AP row.
    agreed=[]
    for entry in entries:
        y=entry.discovered_position[2]
        if not 130<=y<=520:continue
        hasAp=any(re.fullmatch(r'AP\d+',_compact_title(s.text),re.I) and 740<=_span_rect(s,(x0,y0))[0]<900 and 40<=(_span_rect(s,(x0,y0))[1]+_span_rect(s,(x0,y0))[3])/2-y<=105 for s in spans)
        if not hasAp:
            # CN multi-line OCR sometimes drops/misreads AP10. Independently
            # verify the same visible card's AP label with the Latin model.
            apText,apScore=OCR.EN.ocr_single_line(detect.im[y+50:y+93,775:900])
            if apScore<.8 or not re.fullmatch(r'AP\d+',_compact_title(apText),re.I):continue
        title=_readDailyTitle(detect.im,y)
        if title:
            agreed.append(DailyQuestEntry(title,_quest_type(title),_difficulty(title),entry.screenshot_signature,entry.discovered_position))
    # An AP row well inside the viewport represents a complete card. Fail the
    # whole scan if its title is missing or disagrees; do not advertise a partial
    # recognition as a complete list or retain stale items from the previous day.
    apRows=[(_span_rect(s,(x0,y0))[1]+_span_rect(s,(x0,y0))[3])/2 for s in spans if re.fullmatch(r'AP\d+',_compact_title(s.text),re.I)]
    for y in apRows:
        if not 200<=y<=580 or any(40<=y-e.discovered_position[2]<=105 for e in agreed):continue
        # Recover a title rejected/missed by multi-line OCR using the AP row on
        # that actual card. Read the fixed title band twice; never fill from a
        # schedule or from the requested quest name.
        title=_readDailyTitle(detect.im,y-75)
        if title:
            agreed.append(DailyQuestEntry(title,_quest_type(title),_difficulty(title),'',(int(scrollIndex),947,int(y)-75)))
    if strict and any(200<=y<=580 and not any(40<=y-e.discovered_position[2]<=105 for e in agreed) for y in apRows):raise ScriptStop('完整每日任务卡片的标题未通过双重校验；未发布扫描列表，请刷新重试')
    return agreed

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
    before=detect.im
    # Scan stride 280 retains overlap within the 390px title verification band.
    start=240 if distance==180 else 210
    _menuSwipe((950,start),(950,start+distance)) if toTop else _menuSwipe((950,start+distance),(950,start))
    schedule.sleep(.7)
    after=Detect(.2)
    return after,_viewportMoved(before,after.im)

def _scrollToTop():
    detect=Detect(.2)
    deadline=time.monotonic()+DAILY_SCROLL_TIMEOUT;stalled=0
    while time.monotonic()<deadline:
        thumb=_scrollbar(detect.im)
        after,_=_swipe(detect,True);newThumb=_scrollbar(after.im)
        if thumb[0]<=105 and newThumb[0]<=thumb[0]+1 and abs(newThumb[0]-thumb[0])<=1:return after,True
        stalled=stalled+1 if newThumb[0]>=thumb[0]-1 else 0
        if stalled>=3:raise ScriptStop('每日任务滚动条连续未向顶部移动，已停止定位')
        detect=after
    raise ScriptStop('每日任务列表返回顶部超时，已停止定位')

def _isDailyPage(detect):return _dailyHeader(detect)

def _navigationLabels(detect):
    return [(_clean_text(item.text),_span_rect(item)) for item in OCR.ZHS.detect_and_ocr(detect.im,drop_score=.5)]

def _navigationLabel(labels,text,region):
    x0,y0,x1,y1=region
    matches=[rect for title,rect in labels if _title_key(title)==_title_key(text) and x0<=(rect[0]+rect[2])/2<x1 and y0<=(rect[1]+rect[3])/2<y1]
    if len(matches)!=1:return None
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

def openDailyPageCN():
    """Open the CN daily-quest list without selecting or starting a battle."""
    if XDetect.region!='CN':raise ScriptStop('每日任务快捷入口仅适配简体中文服务器')
    closes=scrolls=unchanged=transitionWaits=0;lastTap=None
    for _ in range(DAILY_NAVIGATION_LIMIT):
        detect=Detect(.3)
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
            after,moved=_swipe(detect,True)
            if not moved:raise ScriptStop('已到导航列表顶部，但未唯一识别迦勒底之门/每日任务入口')
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
            schedule.sleep(.6)
    raise ScriptStop('每日任务导航超过有限步骤上限；未选择任何关卡')

def _open_chapter(chapter):
    for _ in range(30):
        detect=Detect(.4)
        if detect.isMainInterface():break
    else:raise ScriptStop('等待关卡导航界面超时')
    for _ in range(10):
        detect=Detect(.4)
        if detect.isQuestListBegin():break
        fgoDevice.device.swipe((1000,200),(1000,600))
    else:raise ScriptStop('无法确认章节列表起始位置，已停止每日任务导航')
    for _ in range(20):
        detect=Detect(.4)
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
            schedule.sleep(.4);detect=Detect(.2)
            if not _isDailyPage(detect):raise ScriptStop('每日任务标题重读时页面已变化，未发布列表')

def scanDailyQuestsCN():
    """Scan overlapping, settled pages until the scrollbar confirms the bottom."""
    if XDetect.region!='CN':raise ScriptStop('每日任务 OCR 仅适配简体中文服务器')
    detect=Detect(.2)
    if not _isDailyPage(detect):
        openDailyPageCN()
        detect=Detect(.3)
    from fgoNavigation import publish
    publish('正在扫描每日任务…')
    detect,_=_scrollToTop();entries=[];screens=0;stalled=0
    deadline=time.monotonic()+DAILY_SCAN_TIMEOUT
    while time.monotonic()<deadline:
        thumb=_scrollbar(detect.im)
        entries.extend(_settledDailyEntriesAt(detect,screens));screens+=1
        publish(f'正在扫描每日任务：第 {screens} 屏，已核验 {len(deduplicateDailyEntries(entries))} 项…')
        after,_=_swipe(detect,False,280);newThumb=_scrollbar(after.im)
        if thumb[1]>=574 and abs(newThumb[0]-thumb[0])<=1:
            entries.extend(_settledDailyEntriesAt(after,screens));screens+=1
            detect=after;break
        stalled=stalled+1 if newThumb[0]<=thumb[0]+1 else 0
        if stalled>=3:raise ScriptStop('每日任务滚动条连续未向末端移动，未发布不完整列表')
        detect=after
    else:raise ScriptStop('每日任务完整扫描超时，未发布不完整列表')
    entries=deduplicateDailyEntries(entries)
    # Independently verify the list on the return trip. A single pass can miss
    # a cropped edge title or an AP label during animation; never label that
    # partial OCR collection as complete.
    reverse=[];stalled=0;deadline=time.monotonic()+DAILY_SCAN_TIMEOUT
    while time.monotonic()<deadline:
        reverse.extend(_settledDailyEntriesAt(detect,screens));screens+=1
        publish(f'正在返回校验每日任务：第 {screens} 屏…')
        thumb=_scrollbar(detect.im);after,_=_swipe(detect,True,280);newThumb=_scrollbar(after.im)
        if thumb[0]<=105 and abs(newThumb[0]-thumb[0])<=1:
            reverse.extend(_settledDailyEntriesAt(after,screens));screens+=1
            break
        stalled=stalled+1 if newThumb[0]>=thumb[0]-1 else 0
        if stalled>=3:raise ScriptStop('每日任务返回校验滚动没有进展，未发布列表')
        detect=after
    else:raise ScriptStop('每日任务返回校验超时，未发布列表')
    missing={_title_key(e.title) for e in entries}^{_title_key(e.title) for e in reverse}
    if missing:
        from fgoLogging import getLogger
        getLogger('QuickQuest').warning(f'Daily forward titles: {[e.title for e in entries]}; reverse titles: {[e.title for e in deduplicateDailyEntries(reverse)]}')
        # A return swipe can put a card at a clipped edge in every sampled frame.
        # Re-locate each discrepant title independently before accepting it. This
        # verifies actual presence and performs no quest/AP/battle click.
        combined=deduplicateDailyEntries(entries+reverse)
        for entry in combined:
            if _title_key(entry.title) in missing:gotoDailyEntry(entry)
        _scrollToTop()
        entries=combined
    if not entries:raise ScriptStop('未校验到完整每日任务卡片，请检查识别日志')
    publish(f'已确认 {len(entries)} 项任务')
    return {'type':'DailyQuestScan','entries':entries,'screens':screens,'complete':True,'reachedEnd':True,'restoredTop':True,'reverified':len(missing)}

def refreshDailyQuestsCN():
    from fgoNavigation import normalizeToTerminalCN,publish
    if XDetect.region!='CN':raise ScriptStop('每日任务刷新仅支持国服中文界面')
    normalizeToTerminalCN()
    publish('正在进入迦勒底之门…')
    openDailyPageCN()
    return scanDailyQuestsCN()

def gotoDailyEntry(entry):
    """Return to top, then scroll the matched dynamic title into the first visible quest-card row."""
    if not isinstance(entry,DailyQuestEntry):raise ScriptStop('每日任务队列项格式无效')
    if XDetect.region!='CN':raise ScriptStop('每日任务定位仅适配简体中文服务器')
    detect=Detect(.2)
    if not _isDailyPage(detect):
        openDailyPageCN()
    detect,_=_scrollToTop()
    deadline=time.monotonic()+DAILY_SCAN_TIMEOUT;stalled=0
    while time.monotonic()<deadline:
        entries=_dailyEntriesAt(detect,strict=False)
        matches=[item for item in entries if _title_key(item.title)==_title_key(entry.title)]
        if matches:
            target=min(matches,key=lambda item:item.discovered_position[2])
            y=target.discovered_position[2]
            # Kernel.Main presses (845,203) for its first quest. Verify that
            # coordinate lies inside this exact card, rather than merely choosing
            # the first OCR title (a preceding card may be clipped at the top).
            if 125<=y<=220:return {'type':'DailyQuestReady','entry':entry,'position':target.discovered_position[1:]}
            distance=int(y-150)
            start=420;end=max(130,min(590,start-distance))
            _menuSwipe((950,start),(950,end));schedule.sleep(.8);after=Detect(.2)
            stalled=stalled+1 if abs(_scrollbar(after.im)[0]-_scrollbar(detect.im)[0])<=1 else 0
        else:
            if _scrollbar(detect.im)[1]>=574:raise ScriptStop(f'完整列表找不到“{entry.title}”，未启动战斗')
            thumb=_scrollbar(detect.im);after,_=_swipe(detect,False)
            stalled=stalled+1 if _scrollbar(after.im)[0]<=thumb[0]+1 else 0
        if stalled>=3:raise ScriptStop('每日任务定位滚动没有进展，未启动战斗')
        detect=after
    raise ScriptStop(f'每日任务定位超时，未启动战斗：{entry.title}')

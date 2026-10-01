from dataclasses import dataclass
import cv2,hashlib,re,unicodedata
import numpy
import fgoDevice
from fgoDetect import Detect,OCR,XDetect
from fgoSchedule import ScriptStop,schedule

DAILY_CATEGORY='daily'
DAILY_SCROLL_LIMIT=10
DAILY_RESTORE_SCROLL_LIMIT=20
DAILY_TITLE_REGION=(620,120,1120,675)
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

def _compact_title(text):return re.sub(r'\s+','',_clean_text(text))

def _title_key(text):return _compact_title(text).casefold()

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

def parseDailyQuestEntries(detections,screenshot,scrollIndex=0,offset=(0,0),minScore=.4):
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
        if difficulty=='unknown':continue
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

def _dailyEntriesAt(detect,scrollIndex=0):
    if detect.im.shape[:2]!=(720,1280):raise ScriptStop(f'每日任务扫描要求 1280x720，实际为 {detect.im.shape[1]}x{detect.im.shape[0]}')
    x0,y0,x1,y1=DAILY_TITLE_REGION
    spans=OCR.ZHS.detect_and_ocr(detect.im[y0:y1,x0:x1],drop_score=.4)
    return parseDailyQuestEntries(spans,detect.im,scrollIndex,(x0,y0))

def _swipe(detect,toTop):
    before=detect.im
    fgoDevice.device.swipe((950,220),(950,600)) if toTop else fgoDevice.device.swipe((950,600),(950,220))
    schedule.sleep(.25)
    after=Detect(.25)
    return after,_viewportMoved(before,after.im)

def _scrollToTop(maxScrolls=DAILY_SCROLL_LIMIT):
    maxScrolls=max(0,min(DAILY_RESTORE_SCROLL_LIMIT,int(maxScrolls)))
    detect=Detect(.2)
    for _ in range(maxScrolls):
        after,moved=_swipe(detect,True)
        if not moved:return after,True
        detect=after
    # Probe the boundary without allowing more than the configured number of moves.
    return detect,False

def _isDailyPage(detect):return _dailyHeader(detect) or bool(_dailyEntriesAt(detect))

def openDailyPageCN():
    """Open the CN daily-quest list without selecting or starting a battle."""
    if XDetect.region!='CN':raise ScriptStop('每日任务快捷入口仅适配简体中文服务器')
    if not Detect(0,1).isMainInterface():raise ScriptStop('请先将游戏返回主界面，再打开每日任务页')
    if Detect.cache.im.shape[:2]!=(720,1280):raise ScriptStop('每日任务快捷入口仅支持 1280x720 横屏')
    _open_chapter((0,))
    _open_chapter((0,0))
    if not _isDailyPage(Detect(.2)):raise ScriptStop('进入章节后未确认每日任务页，未继续操作')
    return {'type':'DailyPage'}

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

def scanDailyQuestsCN(maxScrolls=DAILY_SCROLL_LIMIT):
    """Open if needed, scan OCR card titles from the top with a hard scroll bound, and restore the top."""
    if XDetect.region!='CN':raise ScriptStop('每日任务 OCR 仅适配简体中文服务器')
    maxScrolls=max(0,min(DAILY_SCROLL_LIMIT,int(maxScrolls)))
    detect=Detect(.2)
    if not _isDailyPage(detect):
        if not detect.isMainInterface():raise ScriptStop('请返回游戏主界面后再刷新每日任务列表')
        openDailyPageCN()
        detect=Detect(.3)
    top,atTop=_scrollToTop(maxScrolls)
    if not atTop:raise ScriptStop(f'向上滚动 {maxScrolls} 次后仍无法确认每日任务列表顶部，已停止扫描')
    topFrame=top.im.copy()
    frames=[top]
    reachedEnd=False
    for _ in range(maxScrolls):
        after,moved=_swipe(frames[-1],False)
        if not moved:
            reachedEnd=True
            break
        frames.append(after)
    entries=[]
    for index,frame in enumerate(frames):entries.extend(_dailyEntriesAt(frame,index))
    entries=deduplicateDailyEntries(entries)
    restored,restoredTop=_scrollToTop(DAILY_RESTORE_SCROLL_LIMIT)
    restoredTop=restoredTop and not _viewportMoved(topFrame,restored.im)
    complete=reachedEnd and restoredTop
    return {'type':'DailyQuestScan','entries':entries,'screens':len(frames),'complete':complete,'reachedEnd':reachedEnd,'restoredTop':restoredTop,'scrollLimit':maxScrolls}

def gotoDailyEntry(entry,maxScrolls=DAILY_SCROLL_LIMIT):
    """Return to top, then scroll the matched dynamic title into the first visible quest-card row."""
    if not isinstance(entry,DailyQuestEntry):raise ScriptStop('每日任务队列项格式无效')
    if XDetect.region!='CN':raise ScriptStop('每日任务定位仅适配简体中文服务器')
    detect=Detect(.2)
    if not _isDailyPage(detect):
        if not detect.isMainInterface():raise ScriptStop('执行每日任务前请先返回游戏主界面')
        openDailyPageCN()
    detect,atTop=_scrollToTop(maxScrolls)
    if not atTop:raise ScriptStop('无法确认每日任务列表顶部，已停止定位')
    for _ in range(maxScrolls+1):
        entries=_dailyEntriesAt(detect)
        matches=[item for item in entries if _title_key(item.title)==_title_key(entry.title)]
        if matches:
            target=min(matches,key=lambda item:item.discovered_position[2])
            first=min(entries,key=lambda item:item.discovered_position[2])
            delta=target.discovered_position[2]-first.discovered_position[2]
            if delta<=45:return {'type':'DailyQuestReady','entry':entry,'position':target.discovered_position[1:]}
            distance=max(100,min(420,delta))
            after,moved=_swipe(detect,False) if distance>=320 else (None,False)
            if after is None:
                start=600; end=max(180,start-distance)
                fgoDevice.device.swipe((950,start),(950,end)); schedule.sleep(.25); after=Detect(.25); moved=_viewportMoved(detect.im,after.im)
            if not moved:raise ScriptStop('每日任务卡片无法向首位定位，已停止')
            detect=after
        else:
            after,moved=_swipe(detect,False)
            if not moved:raise ScriptStop(f'当前每日任务列表找不到“{entry.title}”，未启动战斗')
            detect=after
    raise ScriptStop(f'每日任务定位超过 {maxScrolls} 次滚动上限，未启动战斗：{entry.title}')

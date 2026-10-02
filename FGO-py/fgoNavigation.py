"""Bounded menu routing. Navigation never selects a quest card or spends AP."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
import re,time,unicodedata,xml.etree.ElementTree as ET
from functools import wraps
import cv2,numpy
import fgoDevice
from fgoDetect import Detect,OCR,XDetect
from fgoMetadata import chapterImg,mapImg
from fgoLogging import getLogger
from fgoSchedule import ScriptStop,schedule

logger=getLogger('Navigation')
_feedback=ContextVar('navigation_feedback',default=None)
_deadline=ContextVar('navigation_deadline',default=None)

def boundedNavigation(timeout=180):
    def decorate(func):
        @wraps(func)
        def call(*args,**kwargs):
            end=time.monotonic()+timeout
            if parent:=_deadline.get():end=min(end,parent)
            token=_deadline.set(end)
            try:return func(*args,**kwargs)
            finally:_deadline.reset(token)
        return call
    return decorate

@contextmanager
def feedback(callback):
    token=_feedback.set(callback)
    try:yield
    finally:_feedback.reset(token)

def publish(message):
    logger.info(message)
    if callback:=_feedback.get():callback(message)

def compact(text):return re.sub(r'[\s\-—－·]', '',unicodedata.normalize('NFKC',str(text))).casefold()

_names={}
def questTitle(quest):
    if not _names:
        tree=ET.parse(Path(__file__).with_name('fgoI18n.zh.ts'))
        for context in tree.findall('context'):
            if context.findtext('name')=='quest':
                _names.update({m.findtext('source'):m.findtext('translation') for m in context.findall('message')})
    key='-'.join(map(str,quest))
    return _names.get(key) or key

@dataclass
class NavigationGuard:
    target:str
    timeout:float=120
    max_steps:int=100
    current_state:str='UNKNOWN'
    no_progress_count:int=0
    boundary:str='unknown'
    def __post_init__(self):
        self.deadline=time.monotonic()+self.timeout
        if parent:=_deadline.get():self.deadline=min(self.deadline,parent)
        self._previous=None
    def check(self):
        schedule.checkStop()
        if time.monotonic()>=self.deadline:self.fail('timeout')
    def fail(self,reason):
        raise ScriptStop(f'Navigation failed [{self.current_state}] {self.target}: {reason}')
    def stage(self,state,message):
        self.current_state=state;self.check();publish(message)
    def steps(self):
        for i in range(self.max_steps):
            self.check();yield i
        self.fail('maximum state transitions exceeded')
    def progress(self,value,limit=3):
        self.no_progress_count=self.no_progress_count+1 if value==self._previous else 0
        self._previous=value
        if self.no_progress_count>=limit:self.fail('page made no progress')
    def wait(self,predicate,description,timeout=15):
        deadline=min(self.deadline,time.monotonic()+timeout)
        for _ in range(self.max_steps):
            self.check()
            if time.monotonic()>=deadline:break
            detect=Detect(.3)
            if predicate(detect):return detect
        self.fail(f'{description}: page did not reach the expected state')

def legacyWait(predicate,target,timeout=25):
    return NavigationGuard(target,timeout).wait(predicate,target,timeout)

def legacyScroll(predicate,target,begin,end,signature=None,timeout=60):
    guard=NavigationGuard(target,timeout)
    for _ in guard.steps():
        detect=Detect(.4)
        if predicate(detect):return detect
        guard.progress(signature(detect) if signature else stableCrop(detect))
        fgoDevice.device.swipe(begin,end)
    guard.fail('target not found')

def stableCrop(detect,rect=(650,115,1110,580)):
    # Ignore the animated background where a real scrollbar is available.
    try:return scrollbar(detect.im)
    except ScriptStop:
        gray=cv2.cvtColor(detect._crop(rect),cv2.COLOR_BGR2GRAY)
        return tuple((cv2.resize(gray,(16,16))//32).flat)

def scrollbar(image):
    from fgoQuickQuest import _scrollbar
    return _scrollbar(image)

@dataclass(frozen=True)
class Label:
    text:str
    box:tuple
    score:float
    @property
    def center(self):return ((self.box[0]+self.box[2])//2,(self.box[1]+self.box[3])//2)

def labels(detect):
    result=[]
    for span in OCR.ZHS.detect_and_ocr(detect.im,drop_score=.65):
        points=numpy.asarray(span.box).reshape(-1,2)
        result.append(Label(str(span.text),tuple(int(v) for v in (*points.min(axis=0),*points.max(axis=0))),float(span.score)))
    # The small fixed return label fluctuates around .8 in full-screen OCR.
    # Read its own text band twice instead of relaxing the global threshold.
    for rect in ((75,23,143,62),(60,20,160,65)):
        line=detect._crop(rect)
        text,score=OCR.ZHS.ocr_single_line(line)
        text2,score2=OCR.ZHS.ocr_single_line(cv2.resize(line,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC))
        if min(score,score2)>=.85 and compact(text)==compact(text2) and compact(text) in ('通知','管理室','关闭'):
            result=[i for i in result if not(i.center[0]<200 and i.center[1]<95 and compact(i.text)==compact(text))]
            result.append(Label(text,rect,float(min(score,score2))))
            break
    return result

def unique(items,text,region,substring=False):
    x0,y0,x1,y1=region;key=compact(text)
    matches=[i for i in items if i.score>=.8 and x0<=i.center[0]<x1 and y0<=i.center[1]<y1 and (key in compact(i.text) if substring else key==compact(i.text))]
    if len(matches)>1:raise ScriptStop(f'Navigation failed: ambiguous OCR target “{text}”')
    return matches[0] if matches else None

def confirmedFuyukiHeaderCN(detect,items):
    """Confirm the fixed map identity without guessing a misread 冬 character."""
    if hasattr(detect,'_navFuyukiHeader'):return detect._navFuyukiHeader
    prefix=compact('燃烧污染都市')
    proposals=[i for i in items if i.score>=.8 and i.center[0]>=850 and i.center[1]<60 and compact(i.text).startswith(prefix)]
    if len(proposals)!=1:return False
    reads=[]
    for rect in ((900,0,1178,55),(1170,51,1278,85)):
        line=detect._crop(rect)
        a,sa=OCR.ZHS.ocr_single_line(line)
        b,sb=OCR.ZHS.ocr_single_line(cv2.resize(line,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC))
        reads.append((a,b,float(sa),float(sb)))
    # Exclude the animated map behind 冬木 and the A glyph in A.D.
    # Both fixed text bands must match exactly at both scales.
    expected=(prefix,compact('D.2004'))
    valid=all(min(sa,sb)>=.85 and compact(a)==compact(b)==key for (a,b,sa,sb),key in zip(reads,expected))
    detect._navFuyukiHeader=bool(valid)
    logger.debug(f'CN map header identity: confirmed={valid}, reads={reads}')
    return bool(valid)

def mapChapterConfirmed(detect,items,chapter):
    header=[i for i in items if i.score>=.8 and i.center[0]>=850 and i.center[1]<95]
    recognized={key for key in mapImg if len(key)==2 and any(compact(questTitle(key)) in compact(i.text) for i in header)}
    if len(recognized)>1:raise ScriptStop('Navigation failed [MAP]: conflicting chapter headers')
    if recognized:return recognized=={tuple(chapter)}
    return tuple(chapter)==(1,0) and confirmedFuyukiHeaderCN(detect,items)

def classify(detect,items=None):
    items=labels(detect) if items is None else items
    # Modal overlays override recognizable backgrounds.
    if any(350<i.center[0]<1100 and 180<i.center[1]<650 and (compact(i.text) in ('取消','确定','确认','开始','ok','cancel') or '是否' in i.text) for i in items):return 'BLOCKED'
    menu=detect.isMainInterface()
    if unique(items,'通知',(0,0,200,95)) and menu:return 'ROOT_CATEGORY'
    header=[i for i in items if i.center[0]>=850 and i.center[1]<95]
    close=unique(items,'关闭',(0,0,200,95))
    if close and menu:
        if any('每日任务' in i.text for i in header):return 'DAILY'
        if any('迦勒底之门' in i.text for i in header):return 'GATE'
        if any('第一部' in i.text for i in header):return 'FIRST_PART'
        if any('关卡举办时间' in i.text for i in items):return 'EVENT'
        if any('自由关卡' in compact(i.text) for i in items if i.center[0]>750) or cnFreeQuestReturn(detect,items):return 'FREE_QUEST'
    manager=unique(items,'管理室',(0,0,200,95))
    if manager and menu and (any(any(compact(questTitle(key)) in compact(i.text) for key in mapImg if len(key)==2) for i in header) or confirmedFuyukiHeaderCN(detect,items)):return 'MAP'
    if detect.isWeeklyMission() and any('任务' in i.text for i in items):return 'WEEKLY'
    return 'UNKNOWN'

def _signature(items):
    return tuple(sorted((compact(i.text),i.center[0]//8,i.center[1]//8) for i in items if i.center[0]>640 and 95<i.center[1]<580))

def cnFreeQuestReturn(detect,items):
    """Strict local verification when global OCR misses the returned green card."""
    if XDetect.region!='CN' or not unique(items,'关闭',(0,0,200,95)) or not detect.isMainInterface():return False
    if any('每日任务' in i.text or '关卡举办时间' in i.text for i in items):return False
    if not any(mapChapterConfirmed(detect,items,key) for key in mapImg if len(key)==2):return False
    for rect,expected,model in (((775,157,855,188),'自由关卡',OCR.ZHS),((775,199,895,235),None,OCR.EN)):
        crop=detect._crop(rect);a,sa=model.ocr_single_line(crop);b,sb=model.ocr_single_line(cv2.resize(crop,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC))
        if min(sa,sb)<.85 or compact(a)!=compact(b):return False
        if expected and compact(a)!=compact(expected):return False
        if not expected and not re.fullmatch(r'ap[1-9]\d*',compact(a)):return False
    return True

def terminalHomeCN(detect,items):
    if classify(detect,items)!='ROOT_CATEGORY':return False
    directory=any(i.score>=.85 and 640<i.center[0]<1230 and 95<i.center[1]<720 and
                  (compact(i.text)=='迦勒底之门' or any(compact(questTitle(k))==compact(i.text) for k in chapterImg if len(k)==2)) for i in items)
    return bool(directory and unique(items,'通知',(0,0,200,95)))

def expandedMenuCN(detect,items):
    terminal=unique(items,'终端',(40,600,215,700))
    if not terminal or not unique(items,'关闭',(1080,420,1280,520)):return None
    controls=0
    for text,rect in (('编队',(260,617,347,666)),('强化',(430,617,520,666)),('召唤',(598,617,688,666)),('好友',(932,617,1025,666))):
        if unique(items,text,rect):controls+=1;continue
        crop=detect._crop(rect);a,sa=OCR.ZHS.ocr_single_line(crop);b,sb=OCR.ZHS.ocr_single_line(cv2.resize(crop,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC))
        if min(sa,sb)>=.85 and compact(a)==compact(b)==compact(text):controls+=1
    if controls<3:return None
    image,alpha=detect.tmpl.MENU
    # Keep the neutral button frame; translucent blue corners depend on the
    # current map backdrop and are not a stable feature of expanded MENU.
    mask=numpy.where((image.max(axis=2)-image.min(axis=2)<20)&(image.min(axis=2)>170),alpha,0).astype(numpy.uint8)
    if not detect._compare((image,mask),(1104,434,1267,497)):return None
    crop=detect._crop(terminal.box);a,sa=OCR.ZHS.ocr_single_line(crop);b,sb=OCR.ZHS.ocr_single_line(cv2.resize(crop,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC))
    return terminal if min(sa,sb)>=.85 and compact(a)==compact(b)=='终端' else None

def safeMenuPageCN(detect,items):
    if any(getattr(detect,m,lambda:False)() for m in ('isTurnBegin','isBattleFinished','isBattleDefeated','isApEmpty')):return 'UNSAFE_BATTLE_OR_AP'
    if any(getattr(detect,m,lambda:False)() for m in ('isBattleContinue','isSkillCastFailed','isAddFriend','isSummonContinue')):return 'UNSAFE_MODAL'
    if any('是否' in i.text or compact(i.text) in ('确定','确认','取消','ok','cancel','请选择奖励','选择奖励') for i in items if 300<i.center[0]<1100 and 150<i.center[1]<650):return 'UNSAFE_MODAL'
    text=compact(' '.join(i.text for i in items))
    if any(t in text for t in ('skip','跳过剧情','跳过故事','奖励选择','二选一')):return 'UNSAFE_STORY_OR_REWARD'
    state=classify(detect,items)
    if state=='BLOCKED':return 'UNSAFE_MODAL'
    if state in ('ROOT_CATEGORY','FREE_QUEST','MAP','DAILY','GATE','EVENT','FIRST_PART','WEEKLY'):return state
    if getattr(detect,'isBattleFormation',lambda:False)():return 'FORMATION'
    if getattr(detect,'isChooseFriend',lambda:False)():return 'FRIEND'
    from fgoEventProgress import _eventMap,_eventAnchor
    if detect.isMainInterface() and (_eventMap(items) or _eventAnchor(items)):return 'EVENT'
    if detect.isMainInterface() and any(i.score>=.85 and i.center[1]<95 and compact(i.text) in ('编队','强化','召唤','商店','好友','个人空间') for i in items):return 'MENU_PAGE'
    return 'UNKNOWN'

@boundedNavigation(120)
def normalizeToTerminalCN():
    guard=NavigationGuard('返回终端',120,80);guard.stage('NORMALIZE','正在返回终端…')
    for _ in range(6):
        guard.check();d=Detect(.3);items=labels(d);state=safeMenuPageCN(d,items)
        logger.debug(f'normalize state={state}, labels={[(i.text,i.box,i.score) for i in items]}')
        if state.startswith('UNSAFE'):guard.fail(f'{state}：战斗/剧情/奖励或确认弹窗不能自动退出')
        if terminal:=expandedMenuCN(d,items):
            # On the terminal itself its menu tile is disabled. Close the
            # positively confirmed menu, then require the full home proof.
            target=unique(items,'关闭',(1080,420,1280,520)) if unique(items,'通知',(0,0,200,95)) else terminal
            fgoDevice.device.touch(target.center)
            result=guard.wait(lambda frame:terminalHomeCN(frame,labels(frame)),'strict terminal home',25)
            publish('已回到终端');return result
        if terminalHomeCN(d,items):publish('已回到终端');return d
        if state in ('FORMATION','FRIEND'):
            back=unique(items,'返回',(0,0,200,95))
            if not back:guard.fail(f'{state} 返回按钮未唯一确认')
            fgoDevice.device.touch(back.center);schedule.sleep(1);continue
        if state not in ('FREE_QUEST','MAP','DAILY','GATE','EVENT','FIRST_PART','WEEKLY','MENU_PAGE'):guard.fail(f'{state}：未确认可安全退出的菜单页')
        menu=unique(items,'菜单',(1080,590,1280,710))
        if not menu or not d.isMainInterface():guard.fail('MENU文字与模板未共同确认')
        fgoDevice.device.touch(menu.center)
        guard.wait(lambda frame:bool(expandedMenuCN(frame,labels(frame))),'expanded MENU',15)
    guard.fail('安全返回链超过上限')

def _read(guard):
    guard.check();d=Detect(.2);items=labels(d);state=classify(d,items)
    logger.debug(f'state={state}, target={guard.target}, boundary={guard.boundary}, no_progress={guard.no_progress_count}, labels={[(i.text,i.center) for i in items]}')
    return d,items,state

def _tapTransition(guard,item,oldState,expected):
    fgoDevice.device.touch(item.center)
    schedule.sleep(.8)
    for _ in range(15):
        d,items,state=_read(guard)
        if state in expected:return d,items,state
        if state=='BLOCKED':guard.fail('confirmation dialog encountered; no confirmation clicked')
        schedule.sleep(.3)
    guard.fail(f'click did not change {oldState} into {sorted(expected)}')

def returnRootCN(guard=None):
    guard=guard or NavigationGuard('返回主界面',60,30)
    guard.stage('RETURN_ROOT','正在返回主界面…')
    for _ in guard.steps():
        d,items,state=_read(guard)
        if state=='ROOT_CATEGORY':return d
        if state in ('FREE_QUEST','DAILY','GATE','EVENT','FIRST_PART'):
            item=unique(items,'关闭',(0,0,200,95))
            _tapTransition(guard,item,state,{'MAP','ROOT_CATEGORY','GATE'})
        elif state=='MAP':
            item=unique(items,'管理室',(0,0,200,95))
            _tapTransition(guard,item,state,{'ROOT_CATEGORY'})
        elif state=='WEEKLY':
            item=unique(items,'关闭',(0,0,200,120))
            if not item:guard.fail('weekly return control is not uniquely recognized')
            _tapTransition(guard,item,state,{'ROOT_CATEGORY'})
        else:guard.fail(f'cannot safely return from {state}; no blind clicks')
    guard.fail('return routing exceeded transitions')

def _scroll(guard,d,items,toTop):
    from fgoQuickQuest import _menuSwipe
    before=scrollbar(d.im)
    _menuSwipe((950,240),(950,420)) if toTop else _menuSwipe((950,420),(950,240))
    schedule.sleep(.7)
    after,newItems,state=_read(guard);new=scrollbar(after.im)
    moved=abs(new[0]-before[0])>1
    atBoundary=(before[0]<=105 if toTop else before[1]>=574) and not moved
    guard.boundary=('top' if toTop else 'bottom') if atBoundary else 'middle'
    logger.debug(f'scroll {"up" if toTop else "down"}: before={before}, after={new}, state={state}, boundary={guard.boundary}')
    if not atBoundary:
        guard.no_progress_count=0 if moved else guard.no_progress_count+1
        if guard.no_progress_count>=3:guard.fail('scrollbar made no progress before the confirmed boundary')
    return after,newItems,state,atBoundary

def gotoChapterCN(chapter,guard=None):
    title=questTitle(chapter);guard=guard or NavigationGuard(title)
    d=returnRootCN(guard)
    guard.stage('ROOT_CATEGORY',f'正在寻找章节：{title}')
    d,items,state=_read(guard)
    # CN currently exposes unlocked chapters directly. Never require a missing
    # first-part template, and never click the story catalogue as a substitute.
    top=False
    for _ in guard.steps():
        if state not in ('ROOT_CATEGORY','FIRST_PART'):guard.fail(f'unexpected chapter directory {state}')
        item=unique(items,title,(640,95,1230,580))
        if item:
            # A localized title and a stable chapter emblem jointly confirm the
            # entry. Keep the upstream emblem; do not widen its threshold.
            if chapter not in chapterImg:guard.fail('chapter emblem is unavailable')
            score=d._loc((chapterImg[chapter],None),(640,95,1230,600))[0]
            position=d.findChapter(chapter)
            logger.info(f'chapter {chapter}: score={score:.6f}, threshold=.05, OCR={item.text}, template={position}')
            if position and abs(position[1]-item.center[1])>90:guard.fail('chapter title and emblem disagree')
            if not position:
                x0,y0,x1,y1=item.box;line=d.im[max(0,y0-2):min(720,y1+2),max(0,x0-2):min(1280,x1+2)]
                text,a=OCR.ZHS.ocr_single_line(line)
                text2,b=OCR.ZHS.ocr_single_line(cv2.resize(line,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC))
                tags=[i for i in items if i.center[0]>640 and abs(i.center[1]-item.center[1])<120 and any(t in i.text for t in ('特异点','异闻带','亚种','奏章'))]
                if not tags or min(a,b)<.85 or compact(text)!=compact(title) or compact(text2)!=compact(title):guard.fail('chapter title could not be independently verified')
                logger.info(f'chapter OCR fallback: {text}/{a:.3f}, {text2}/{b:.3f}, category={[i.text for i in tags]}')
            d,items,state=_tapTransition(guard,item,state,{'MAP'})
            if not mapChapterConfirmed(d,items,chapter):guard.fail('selected chapter map title does not match')
            guard.stage('MAP',f'已进入{title}')
            return d
        if not top:
            d,items,state,top=_scroll(guard,d,items,True)
        else:
            d,items,state,bottom=_scroll(guard,d,items,False)
            if bottom:guard.fail(f'已到达章节列表底部，但未找到“{title}”（可能尚未解锁）')
    guard.fail('chapter not found')

def mapCamera(detect,chapter):
    if chapter not in mapImg:raise ScriptStop(f'Navigation failed [MAP]: no atlas for {chapter}')
    image=cv2.resize(detect._crop((200,200,1080,520)),(0,0),fx=.3,fy=.3,interpolation=cv2.INTER_CUBIC)
    result=cv2.matchTemplate(mapImg[chapter],image,cv2.TM_SQDIFF_NORMED)
    score,_,pos,_=cv2.minMaxLoc(result)
    camera=numpy.asarray(pos,dtype=float)/.3+(440,160)
    logger.debug(f'map {chapter}: camera={camera.tolist()}, score={score:.6f}')
    if not numpy.isfinite(camera).all() or not numpy.isfinite(score) or score>.65:
        raise ScriptStop(f'Navigation failed [MAP]: atlas match unreliable ({score:.6f})')
    return camera

def mapLabelKey(text):
    # Fixed CN label prefix can OCR as 末. The coordinate suffix must still
    # match exactly; never use fuzzy chapter/node matching.
    return re.sub(r'^(?:末)?[未末]确认','未确认',compact(text)).replace('x°c','xc').replace('x=','x')

def verifiedMapLabel(detect,point,title,knownLabel=None):
    x,y=map(int,point)
    rect=(max(0,x-230),max(90,y+25),min(1240,x+250),min(580,y+110))
    crop=detect._crop(rect);candidates=[]
    for span in OCR.ZHS.detect_and_ocr(crop,drop_score=.8):
        if mapLabelKey(span.text)==mapLabelKey(title):candidates.append(span)
    if len(candidates)>1:return False
    if candidates:
        points=numpy.asarray(candidates[0].box).reshape(-1,2)
        a,b=points.min(axis=0).astype(int);c,e=points.max(axis=0).astype(int)
    elif knownLabel and knownLabel.score>=.65 and mapLabelKey(knownLabel.text)==mapLabelKey(title):
        a,b,c,e=(knownLabel.box[0]-rect[0],knownLabel.box[1]-rect[1],knownLabel.box[2]-rect[0],knownLabel.box[3]-rect[1])
    else:return False
    for padding in (0,2,4):
        line=crop[max(0,b-padding):min(crop.shape[0],e+padding),max(0,a-padding):min(crop.shape[1],c+padding)]
        text,score=OCR.ZHS.ocr_single_line(line)
        text2,score2=OCR.ZHS.ocr_single_line(cv2.resize(line,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC))
        logger.info(f'node {title}: point={list(point)}, padding={padding}, OCR={text!r}/{score:.3f}, {text2!r}/{score2:.3f}')
        if min(score,score2)>=.8 and mapLabelKey(text)==mapLabelKey(title) and mapLabelKey(text2)==mapLabelKey(title):return True
    return False

def visibleMapNode(detect,items,title):
    # Full-screen OCR only proposes a crop. Acceptance always requires both
    # local reads >= .8 plus the adjacent infinity marker below.
    matches=[i for i in items if mapLabelKey(i.text)==mapLabelKey(title) and i.score>=.65 and 100<i.center[1]<580]
    if len(matches)>1:raise ScriptStop(f'Navigation failed [MAP]: duplicate node label {title}')
    if not matches:return None
    label=matches[0];x,y=label.center;point=(x,y-70)
    # A localized map title alone is insufficient: require the cyan Free Quest
    # infinity marker immediately next to this exact map label.
    a=max(0,label.box[2]+2);b=min(1280,label.box[2]+85)
    crop=detect.im[max(0,y-25):min(720,y+25),a:b]
    if not crop.size:return None
    hsv=cv2.cvtColor(crop,cv2.COLOR_BGR2HSV)
    cyan=(hsv[...,0]>=85)&(hsv[...,0]<=120)&(hsv[...,1]>120)&(hsv[...,2]>180)
    if numpy.count_nonzero(cyan)<90:return None
    return point if verifiedMapLabel(detect,point,title,label) else None

def visibleMapCameraCN(detect,items,chapter):
    """Use a verified visible node for panning, never to authorize a target tap."""
    from fgoReishift import Map,place
    if tuple(chapter)!=(1,0):return mapCamera(detect,chapter)
    for key,route in place.items():
        if len(key)!=3 or tuple(key[:2])!=tuple(chapter) or not isinstance(route,Map):continue
        point=visibleMapNode(detect,items,questTitle(tuple(key)+(0,)))
        if point:
            camera=route.coord-(numpy.asarray(point)-(640,360))
            logger.info(f'Map pan anchor: chapter={chapter}, node={key}, point={point}, camera={camera.tolist()}')
            return camera
    return mapCamera(detect,chapter)


def locateMapCN(quest,guard):
    from fgoReishift import Map,place
    from fgoQuickQuest import _menuSwipe
    route=place.get(tuple(quest[:-1]));chapter=tuple(quest[:2]);title=questTitle(quest)
    if not isinstance(route,Map):guard.fail('CN special map is not verified; manual navigation required')
    guard.stage('MAP',f'正在定位：{title}')
    previous=None;stalled=0
    for _ in guard.steps():
        d,items,state=_read(guard)
        if state!='MAP' or not mapChapterConfirmed(d,items,chapter):
            logger.warning(f'Map confirmation failed: state={state}, expected={chapter}, controls={[(i.text,i.score) for i in items if i.center[0]<200 and i.center[1]<95]}, headers={[(i.text,i.score) for i in items if i.center[0]>=850 and i.center[1]<95]}')
            guard.fail('chapter map is no longer confirmed')
        visible=visibleMapNode(d,items,title)
        camera=route.coord-(numpy.array(visible)-(640,360)) if visible else visibleMapCameraCN(d,items,chapter)
        if previous is not None:
            stalled=stalled+1 if numpy.linalg.norm(camera-previous)<5 else 0
            guard.no_progress_count=stalled
            if stalled>=3:guard.fail('map camera did not move; reachable map boundary or input failure')
        v=route.coord-camera;p=numpy.array((640,360))+v
        if cv2.pointPolygonTest(Map.poly,tuple(map(float,p)),False)>0:
            # Confirm the actual node label before touching its map marker.
            if not visible and not verifiedMapLabel(d,p,title):
                guard.fail('map node label is not uniquely confirmed; no map marker clicked')
            # Map-marker glow can briefly hide the adjacent label in OCR.
            # Retry the same strict verification without authorizing a tap
            # from the atlas or relaxing either label/marker threshold.
            settled=False
            for _ in range(3):
                guard.check()
                confirm=Detect(.3);freshItems=labels(confirm)
                if not mapChapterConfirmed(confirm,freshItems,chapter):continue
                confirmedPoint=visibleMapNode(confirm,freshItems,title)
                if not confirmedPoint and visible:
                    # Reuse only the proposed crop box. visibleMapNode still
                    # verifies two fresh local OCR reads and the fresh marker.
                    confirmedPoint=visibleMapNode(confirm,items,title)
                if confirmedPoint and numpy.linalg.norm(numpy.asarray(confirmedPoint)-p)<=15:
                    settled=True;break
            if not settled:guard.fail('map target is not settled or its Free Quest marker is missing')
            guard.check()
            fgoDevice.device.touch(tuple(map(int,p)))
            schedule.sleep(.8)
            guard.wait(lambda frame:classify(frame)=='FREE_QUEST','waiting for Free Quest list')
            return
        previous=camera
        norm=max(abs(v[0])/260,abs(v[1])/190,1)
        shift=v/norm
        _menuSwipe((700,350),tuple(map(int,numpy.array((700,350))-shift)))
        schedule.sleep(.8)
    guard.fail('map target unreachable')

def freeCards(items):
    result=[]
    for item in items:
        if compact(item.text)!='自由关卡' or not 775<=item.center[0]<=1090 or not 110<=item.center[1]<=580:continue
        if any(re.fullmatch(r'ap\d+',compact(i.text)) and abs(i.center[0]-item.center[0])<90 and 10<i.center[1]-item.center[1]<80 for i in items):result.append(item)
    return sorted(result,key=lambda item:item.center[1])

def locateFreeListCN(quest,guard):
    from fgoQuickQuest import _menuSwipe
    guard.stage('FREE_QUEST',f'正在校验 Free Quest：{questTitle(quest)}')
    top=False
    for _ in guard.steps():
        d,items,state=_read(guard)
        if state!='FREE_QUEST':guard.fail('not a positively identified Free Quest list')
        cards=freeCards(items)
        if len(cards)>1:guard.fail('multiple Free Quest cards; target is ambiguous')
        if cards:
            item=cards[0]
            if 125<=item.center[1]<=235 and d.isQuestFreeContains(quest[0]) and d.isQuestFreeFirst(quest[0]):
                guard.stage('FREE_QUEST',f'已定位关卡，准备出击：{questTitle(quest)}')
                return {'type':'FreeQuestReady','quest':tuple(quest),'position':item.center,'title':questTitle(quest)}
            guard.progress((scrollbar(d.im),item.center[1]//4))
            _menuSwipe((950,420),(950,max(150,min(580,420-(item.center[1]-180)))))
            schedule.sleep(.7)
            continue
        if not top:d,items,state,top=_scroll(guard,d,items,True)
        else:
            d,items,state,bottom=_scroll(guard,d,items,False)
            if bottom:guard.fail('Free Quest not found at list bottom')
    guard.fail('Free Quest placement exceeded transitions')

@boundedNavigation(180)
def gotoFreeQuestCN(quest):
    if XDetect.region!='CN':raise ScriptStop('CN navigation invoked for another region')
    if len(quest)!=4:raise ScriptStop('Navigation failed: unsupported metadata route')
    guard=NavigationGuard(f'{questTitle(quest[:2])} → {questTitle(quest)}',180,120)
    gotoChapterCN(tuple(quest[:2]),guard)
    locateMapCN(tuple(quest),guard)
    return locateFreeListCN(tuple(quest),guard)

def checkCurrentQuest():
    if XDetect.region=='CN':
        d=Detect(.2);items=labels(d)
        if classify(d,items) not in ('FREE_QUEST','DAILY') or not (freeCards(items) or classify(d,items)=='DAILY'):
            raise ScriptStop('当前关卡前置检查失败：请停在目标 Free Quest / 每日任务列表；未点击关卡')
    else:
        d=Detect(.2)
        if not d.isMainInterface() or not d.isQuestFreeFirst(1):raise ScriptStop('当前关卡前置检查失败：未确认 Free Quest 列表')
    publish('当前关卡列表已确认')
    return {'type':'CurrentQuestReady'}

def refuseUnverifiedCNAction(action):
    if XDetect.region=='CN':raise ScriptStop(f'Navigation failed: {action} 的 CN 菜单路径未验证；本地安全约束禁止自动执行')

def _thumbAt(image,rect):
    x0,y0,x1,y1=rect
    hsv=cv2.cvtColor(image[y0:y1,x0:x1],cv2.COLOR_BGR2HSV)
    white=numpy.mean((hsv[...,1]<45)&(hsv[...,2]>210),axis=1)>.7
    edges=numpy.flatnonzero(numpy.diff(numpy.r_[False,white,False]))
    runs=[(int(a+y0),int(b+y0)) for a,b in zip(edges[::2],edges[1::2]) if b-a>=30]
    if len(runs)!=1:raise ScriptStop('Navigation failed [WEEKLY]: scrollbar is not unique')
    return runs[0]

def _weeklyKey(text):
    value=compact(text).split('(',1)[0]
    if value.startswith('在队伍内编人'):value=value.replace('在队伍内编人','在队伍内编入',1)
    # The animated event name is irrelevant to the observed material task.
    if '重新累计获得' in value:value=value[value.index('重新累计获得'):].replace('战利品','利品')
    return value.translate(str.maketrans('', '', '『』「」【】'))

def weeklyRowsAt(detect):
    items=labels(detect);rows=[]
    for item in items:
        if compact(item.text)!='目标进行度' or not 600<item.center[0]<1050 or not 330<item.center[1]<665:continue
        y=item.center[1]
        crop=detect.im[max(265,y-76):y-13,610:1095]
        reads=[]
        for scale in (1,2):
            frame=crop if scale==1 else cv2.resize(crop,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC)
            spans=OCR.ZHS.detect_and_ocr(frame,drop_score=.75)
            spans=sorted(spans,key=lambda s:numpy.asarray(s.box).reshape(-1,2)[:,1].mean())
            reads.append(''.join(str(s.text) for s in spans))
        if not reads[0] or len(compact(reads[0]))<6 or _weeklyKey(reads[0])!=_weeklyKey(reads[1]):
            logger.debug(f'weekly title rejected: {reads}')
            continue
        progress=set()
        for x0,x1,dy0,dy1 in ((605,665,17,42),(605,685,8,49),(610,690,16,41)):
            line=detect.im[y+dy0:y+dy1,x0:x1]
            a,sa=OCR.EN.ocr_single_line(line);b,sb=OCR.EN.ocr_single_line(cv2.resize(line,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC))
            a=compact(a);b=compact(b)
            if min(sa,sb)>=.8 and a==b and re.fullmatch(r'\d+/\d+',a):progress.add(a)
        if len(progress)!=1:
            logger.debug(f'weekly progress rejected: {progress}')
            continue
        done,total=map(int,progress.pop().split('/'))
        if done>total:raise ScriptStop('Navigation failed [WEEKLY]: invalid task progress')
        rows.append((reads[0],done,total))
    return rows

def readWeeklyRowsCN(guard):
    from fgoQuickQuest import _menuSwipe
    guard.stage('WEEKLY','正在完整读取每周任务；不会领取奖励…')
    d=Detect(.3)
    # Read the fixed numeric header independently of its large Chinese label.
    line=d.im[200:228,870:929]
    a,sa=OCR.EN.ocr_single_line(line);b,sb=OCR.EN.ocr_single_line(cv2.resize(line,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC))
    a=compact(a);b=compact(b)
    if min(sa,sb)<.8 or a!=b or not re.fullmatch(r'\d+/\d+',a):guard.fail('weekly total counter is not independently confirmed')
    completed,expected=map(int,a.split('/'))
    if not 0<=completed<=expected<=20:guard.fail('invalid weekly total counter')
    found={};rect=(1253,250,1264,711)
    def swipe(frame,top):
        if classify(frame)!='WEEKLY':guard.fail('weekly panel no longer confirmed')
        before=_thumbAt(frame.im,rect)
        _menuSwipe((1000,350),(1000,530)) if top else _menuSwipe((1000,530),(1000,350))
        schedule.sleep(.7);after=Detect(.3);new=_thumbAt(after.im,rect)
        boundary=(before[0]<=268 if top else before[1]>=660) and abs(new[0]-before[0])<=1
        guard.boundary=('top' if top else 'bottom') if boundary else 'middle'
        guard.no_progress_count=0 if abs(new[0]-before[0])>1 else guard.no_progress_count+1
        if not boundary and guard.no_progress_count>=3:guard.fail('weekly scrollbar made no progress')
        logger.debug(f'weekly scroll: top={top}, before={before}, after={new}, boundary={guard.boundary}')
        return after,boundary
    for _ in guard.steps():
        d,end=swipe(d,True)
        if end:break
    for _ in guard.steps():
        for title,done,total in weeklyRowsAt(d):
            key=_weeklyKey(title)
            if key in found and found[key][1:]!=(done,total):guard.fail('weekly task progress changed during read')
            found[key]=(title,done,total)
        d,end=swipe(d,False)
        if end:
            for title,done,total in weeklyRowsAt(d):found.setdefault(_weeklyKey(title),(title,done,total))
            break
    for _ in guard.steps():
        d,end=swipe(d,True)
        if end:break
    if len(found)!=expected:guard.fail(f'weekly task count mismatch: confirmed {len(found)}, page says {expected}; no queue generated')
    rows=[]
    for title,done,total in found.values():
        targets=[] if any(word in title for word in ('编入','队伍','累计获得')) else re.findall(r'[『「【](.*?)[』」】]',title)
        rows.append((targets or [title],'从者' not in title,total-done))
    logger.info(f'weekly rows confirmed: page={completed}/{expected}, rows={list(found.values())}')
    return {'tasks':rows,'explicitCompleted':sum(done==total for _,done,total in found.values()),'malformed':0,'header':(completed,expected),'lines':[title for title,_,_ in found.values()]}

"""Live event quest catalog and advisory LIST/MAP locator.

Only a fresh, stable title/AP/available card authorizes a quest touch. Scrolls
restore a viewport, never imply a quest exists there. Screenshots stay local.
"""
from dataclasses import replace
import hashlib,re,time
from pathlib import Path
import cv2,numpy
import fgoEventProgress as event
from fgoEventEngine import EventQuestEntry,textKey
from fgoDetect import OCR
from fgoSchedule import ScriptStop,schedule
import fgoQuickQuest as daily

TRACK=(95,590)

class QuestNotObserved(ScriptStop):
    """Completed bounded area scan did not re-prove a cached quest."""
def scrollbar(image):
    if image.shape[:2]!=(720,1280):return None
    strip=image[TRACK[0]:TRACK[1],1255:1267]
    white=numpy.mean((strip.min(axis=2)>200)&(strip.max(axis=2)-strip.min(axis=2)<40),axis=1)>.45
    groups=[];start=None
    for y,on in enumerate(list(white)+[False]):
        if on and start is None:start=y
        if not on and start is not None:
            if y-start>=18:groups.append((start+TRACK[0],y+TRACK[0]))
            start=None
    return max(groups,key=lambda v:v[1]-v[0]) if groups else None

def viewportSignature(image):
    # Advisory identity only; exact equality is never click authorization.
    band=cv2.resize(image[95:620,760:1100],(24,32))//16
    return hashlib.sha256(band.tobytes()).hexdigest()[:24]

def titleSignature(d,box):
    x,y,r,b=box;gray=cv2.cvtColor(d.im[y:b,x:r],cv2.COLOR_BGR2GRAY)
    small=cv2.resize(gray,(33,8));bits=(small[:,1:]>small[:,:-1]).reshape(-1)
    return format(int(''.join('1' if v else '0' for v in bits),2),'064x')

def patchMatch(image,box,name,root):
    """Local, operator-reviewed full text patch; tolerate OCR box translation.

    Only basenames inside the private index directory are accepted. Pixel proof
    supplements exact observed OCR/AP/area, never replaces their agreement.
    """
    if not root or not name or Path(name).name!=name:return False
    template=cv2.imread(str(Path(root)/name),cv2.IMREAD_GRAYSCALE)
    if template is None:return False
    x,y,r,b=box;search=image[max(0,y-8):min(720,b+8),max(0,x-8):min(1280,r+8)]
    if min(search.shape[:2])==0:return False
    search=cv2.cvtColor(search,cv2.COLOR_BGR2GRAY)
    if any(a<b for a,b in zip(search.shape,template.shape)):return False
    return float(cv2.matchTemplate(search,template,cv2.TM_CCOEFF_NORMED).max())>=.97

def verifiedTitle(raw,AP,areaKey,signature,proofs,*,image=None,box=None,proofRoot=None):
    matched=[]
    for p in proofs:
        if p.get('areaKey')!=areaKey or p.get('AP')!=AP or not all(p.get(k) for k in ('source','canonical','titleHash')):continue
        if p.get('titlePatch') and image is not None and box is not None:
            # Two-scale OCR already proved a full text line. The exact reviewed
            # pixels establish its spelling, including previously unseen OCR
            # substitutions; a string alias never authorizes this path alone.
            proven=bool(raw) and patchMatch(image,box,p['titlePatch'],proofRoot)
        else:
            proven=textKey(raw) in {textKey(t) for t in p.get('ocrTexts',[])} and (int(signature,16)^int(p['titleHash'],16)).bit_count()<=12
        if proven:matched.append(p)
    if len({p['canonical'] for p in matched})>1:raise ScriptStop('Conflicting local full-title proofs')
    return matched[0]['canonical'] if matched else raw

def areaIdentity(items):
    values=[i for i in items if i.score>=.85 and 200<i.center[0]<580 and 150<i.center[1]<550 and len(re.findall(r'[\u4e00-\u9fff]',i.text))>=3 and not any(w in event._text(i) for w in ('举办','进行','报酬','任务','推荐'))]
    return str(values[0].text) if len(values)==1 else None

def strongLine(d,box,model=OCR.ZHS):
    x,y,r,b=box
    if not 0<=x<r<=1280 or not 0<=y<b<=720:return None
    crop=d._crop(box)
    a,sa=model.ocr_single_line(crop);c,sc=model.ocr_single_line(cv2.resize(crop,None,fx=2,fy=2))
    return str(a) if min(float(sa),float(sc))>=.85 and textKey(a)==textKey(c) else None

def readListQuests(d,items,eventKey,areaKey,proofs=(),proofRoot=None):
    if event._unsafeEventOverlay(items) or not d.isMainInterface() or areaIdentity(items)!=areaKey:return []
    thumb=scrollbar(d.im);signature=viewportSignature(d.im);result=[]
    aps=[i for i in items if i.score>=.4 and re.fullmatch(r'ap\d+',event._text(i)) and 770<i.center[0]<900 and 180<i.center[1]<595]
    for apLabel in aps:
        ay=apLabel.center[1]
        row=[i for i in items if i.score>=.4 and 600<i.center[0]<1235 and ay-130<i.center[1]<ay+70]
        if any(event._isMainTitle(i.text) or re.search(r'完成任务no[.．]?\d+后开放',event._text(i)) for i in row if i.center[1]<ay):continue
        titles=[i for i in row if 770<i.center[0]<1130 and ay-110<i.center[1]<ay-35 and len(re.findall(r'[\u4e00-\u9fff]',i.text))>=4 and not any(w in event._text(i) for w in ('举办','任务进行','推荐','等级','目标','完成任务','报酬'))]
        if len(titles)!=1:continue
        titleLabel=titles[0];title=strongLine(d,titleLabel.box)
        apText=strongLine(d,apLabel.box,OCR.EN)
        if title is None or apText is None or not re.fullmatch(r'ap\d+',textKey(apText)):continue
        AP=int(re.search(r'\d+',apText)[0])
        if AP!=int(re.search(r'\d+',apLabel.text)[0]):continue
        feature=titleSignature(d,titleLabel.box)
        title=verifiedTitle(title,AP,areaKey,feature,proofs,image=d.im,box=titleLabel.box,proofRoot=proofRoot)
        ty=titleLabel.center[1]
        new=[i for i in row if i.score>=.85 and event._text(i) in ('新','新!','新！','new','new!') and 620<i.center[0]<750 and ty-35<i.center[1]<ty+10]
        clears=[i for i in row if '完成' in event._text(i) and 620<i.center[0]<760 and ay+15<i.center[1]<ay+65]
        clearText=strongLine(d,clears[0].box) if len(clears)==1 else None
        if clearText is None and 0<ay+65<620:clearText=strongLine(d,(635,int(ay+20),766,int(ay+65)))
        cleared=clearText is not None and '完成' in textKey(clearText)
        if not cleared:
            cleared=any(p.get('canonical')==title and p.get('areaKey')==areaKey and p.get('AP')==AP and p.get('source') and patchMatch(d.im,(635,int(ay+15),766,int(ay+65)),p.get('clearPatch'),proofRoot) for p in proofs)
        state='NEW' if len(new)==1 else 'CLEARED' if cleared else 'AVAILABLE'
        targets=[i for i in row if i.score>=.85 and textKey(i.text)=='missiontarget' and ay<i.center[1]<ay+55]
        fingerprints=[]
        if len(targets)==1:
            y=targets[0].box[3]+1
            if y+30<720:
                for x in range(targets[0].box[0],min(1080,targets[0].box[0]+160),32):
                    icon=cv2.resize(d.im[y:y+30,x:x+30],(12,12))//16
                    fingerprints.append(hashlib.sha256(icon.tobytes()).hexdigest()[:24])
        locator={'mode':'LIST','thumb':thumb,'track':TRACK,'localY':ty,'neighbors':[],'titleHash':feature,'ocrTitle':str(titleLabel.text)}
        result.append(EventQuestEntry(eventKey,areaKey,title,AP,state,titleLabel.center,signature,locator,tuple(fingerprints)))
    result.sort(key=lambda q:q.screenPosition[1])
    keys=[e.key for e in result]
    return [replace(e,locator={**e.locator,'neighbors':keys[max(0,j-1):j]+keys[j+1:j+2]}) for j,e in enumerate(result)]

class EventQuestLocator:
    def __init__(self,runner,index,*,mapNavigator=None):
        self.runner=runner;self.index=index;self.mapNavigator=mapNavigator
        self.metrics={'indexHits':0,'fallbacks':0,'locateTimes':[],'scrolls':0}
    def view(self,areaKey=None):
        d,items,state=self.runner.read()
        if state=='unknown' and not event._unsafeEventOverlay(items):return d,items,None,[]
        if state not in ('event_map','mission_gate') or event._unsafeEventOverlay(items) or not d.isMainInterface():raise ScriptStop('Event quest list foreground unproven')
        actual=areaIdentity(items)
        if actual is None:return d,items,None,[]
        if areaKey is not None and actual!=areaKey:raise ScriptStop('Event quest area mismatch; cached position cannot authorize input')
        return d,items,actual,readListQuests(d,items,self.index.eventKey,actual,self.index.titleProofs,self.index.path.parent if self.index.path else None)
    def stable(self,areaKey=None):
        previous=None;count=0;end=self.runner.clock()+20
        while self.runner.clock()<end:
            d,items,actual,entries=self.view(areaKey)
            # NEW/CLEARED badges can briefly disappear under their animation.
            # All three reads still must prove the same title/AP and available
            # card; badge type is advisory, unlike a LOCKED observation.
            identity=[(e.key,e.available,e.screenPosition) for e in entries]
            same=previous is not None and len(identity)==len(previous) and all(a[:2]==b[:2] and max(abs(x-y) for x,y in zip(a[2],b[2]))<=6 for a,b in zip(identity,previous))
            count=count+1 if entries and same else 1 if entries else 0;previous=identity
            if count>=3:
                for e in entries:self.index.add(e)
                self.index.save();return d,items,actual,entries
            schedule.sleep(.2)
        raise ScriptStop('Event quest card title/AP/state not stable; no selection')
    def scan(self,*,complete=True):
        end=self.runner.clock()+240;lastThumb=None;seen=set();area=None
        if complete:
            d,items,area,_=self.stable()
            thumb=scrollbar(d.im)
            for _ in range(3):
                if thumb is None or thumb[0]<=TRACK[0]+12:break
                oldTop=thumb[0]
                self.runner.ledger.append('input_intent',action='event_catalog_top',area=area)
                daily._menuSwipe((1261,round(sum(thumb)/2)),(1261,TRACK[0]+round((thumb[1]-thumb[0])/2)))
                self.runner.ledger.append('input',action='event_catalog_top',area=area)
                d,items,area,_=self.stable(area)
                thumb=scrollbar(d.im)
                if thumb is None or oldTop-thumb[0]<3:raise ScriptStop('Event catalog top restore made no measured progress')
            if thumb is None or thumb[0]>TRACK[0]+12:raise ScriptStop('Event catalog top endpoint not reached; bounded restore exhausted')
        while self.runner.clock()<end:
            d,items,area,entries=self.stable(area)
            thumb=scrollbar(d.im)
            seen.update(e.key for e in entries)
            if not complete or thumb is None:return self.index.available(area)
            if thumb[1]>=TRACK[1]-12:
                self.index.completeScan(area,seen);self.index.save();return self.index.available(area)
            if lastThumb is not None and thumb[0]<=lastThumb+1:raise ScriptStop('Event list scrollbar stalled; partial index retained')
            lastThumb=thumb[0]
            # Positive list + real scrollbar authorizes a viewport scroll only.
            self.runner.ledger.append('input_intent',action='event_catalog_scroll',area=area)
            daily._menuSwipe((1050,555),(1050,310))
            self.runner.ledger.append('input',action='event_catalog_scroll',area=area)
            self.metrics['scrolls']+=1
            schedule.sleep(.2)
        raise ScriptStop('Event catalog hard deadline; partial index retained')
    def locate(self,entry):
        start=self.runner.clock()
        if entry.eventKey!=self.index.eventKey or not entry.available:raise ScriptStop('Unavailable/foreign cached quest')
        if entry.locator['mode']=='MAP':
            if self.mapNavigator is None:raise ScriptStop('MAP locator adapter not yet verified for this event')
            # An adapter must verify anchors and bound panning; it returns live
            # title/AP/availability proof, never a cached-coordinate click.
            proof=self.mapNavigator(entry,maxPans=4)
            if not isinstance(proof,EventQuestEntry) or proof.key!=entry.key or not proof.available:raise ScriptStop('MAP fresh quest proof missing')
            self.metrics['indexHits']+=1;return proof
        d,items,area,entries=self.stable(entry.areaKey)
        hit=next((q for q in entries if q.key==entry.key and q.available),None)
        if hit is None:
            thumb=scrollbar(d.im);target=entry.locator.get('thumb')
            if thumb and target and abs((thumb[1]-thumb[0])-(target[1]-target[0]))<=max(3,(target[1]-target[0])*.1):
                self.runner.ledger.append('input_intent',action='event_index_viewport',quest=entry.key)
                daily._menuSwipe((1261,round(sum(thumb)/2)),(1261,round(sum(target)/2)))
                self.runner.ledger.append('input',action='event_index_viewport',quest=entry.key)
                d,items,area,entries=self.stable(entry.areaKey)
                hit=next((q for q in entries if q.key==entry.key and q.available),None)
            if hit is None:
                self.metrics['fallbacks']+=1
                # One complete bounded scan, then fresh re-location of its
                # newly observed locator; no endless recursive fallback.
                self.scan()
                if entry.key in self.index.unobserved:raise QuestNotObserved('Cached quest absent from completed fresh area scan; no quest input')
                fresh=self.index.entries.get(entry.key)
                if fresh is None:raise ScriptStop('Indexed quest absent from fresh scan')
                d,items,area,entries=self.stable(entry.areaKey)
                thumb=scrollbar(d.im);target=fresh.locator.get('thumb')
                if thumb and target:
                    self.runner.ledger.append('input_intent',action='event_index_fallback_viewport',quest=entry.key)
                    daily._menuSwipe((1261,round(sum(thumb)/2)),(1261,round(sum(target)/2)))
                    self.runner.ledger.append('input',action='event_index_fallback_viewport',quest=entry.key)
                d,items,area,entries=self.stable(entry.areaKey)
                hit=next((q for q in entries if q.key==entry.key and q.available),None)
        if hit is None:raise ScriptStop('Fresh indexed title/AP not found; no quest input')
        self.metrics['indexHits']+=1;self.metrics['locateTimes'].append(self.runner.clock()-start)
        self.runner.touch(items,hit.screenPosition,'select_indexed_event_free_quest')
        self.runner.ledger.append('quest_selected',quest=hit.key,title=hit.title,AP=hit.AP,area=hit.areaKey,fresh=True,locateTime=self.metrics['locateTimes'][-1])
        return hit

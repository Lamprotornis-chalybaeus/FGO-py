"""Text/numeric advisory Daily index. No device, image, OCR or account data."""
from dataclasses import dataclass,field,asdict,replace
from datetime import datetime,timezone
from pathlib import Path
from statistics import median
import hashlib,json,math

class DailyIndexError(ValueError):pass

@dataclass(frozen=True)
class DailyQuestLocator:
    thumb_top:float
    thumb_bottom:float
    local_y:float
    absolute_y:float|None=None
    ordinal:int|None=None
    before_key:str|None=None
    after_key:str|None=None
    observations:int=1

@dataclass(frozen=True)
class DailyObservation:
    title_key:str
    thumb_top:float
    thumb_bottom:float
    local_y:float
    ap_y:float
    frame_index:int

@dataclass(frozen=True)
class MissingPositionCandidate:
    before_key:str
    after_key:str
    expected_absolute_y:float

@dataclass
class DailyScanMetrics:
    screensCaptured:int=0
    fullOcrCalls:int=0
    localOcrCalls:int=0
    scrollSwipes:int=0
    scrollbarDrags:int=0
    targetedRechecks:int=0
    gapRecoveries:int=0
    microAdjustments:int=0
    fallbacks:int=0
    elapsedSeconds:float=0

@dataclass(frozen=True)
class DailyIndexRecord:
    title:str
    title_key:str
    quest_type:str
    difficulty:str
    locator:DailyQuestLocator
    observations:tuple[DailyObservation,...]=()
    edge_verified:bool=False

@dataclass(frozen=True)
class DailyQuestIndex:
    version:int
    generated_at:str
    scrollbar_height:float
    scroll_scale:float
    ordered_title_keys:tuple[str,...]
    entries:tuple[DailyIndexRecord,...]
    fingerprint:str
    top:float=99
    bottom:float=575
    @property
    def entry_count(self):return len(self.entries)
    def record(self,key):return next((e for e in self.entries if e.title_key==key),None)
    def geometry_matches(self,thumb):return abs((thumb[1]-thumb[0])-self.scrollbar_height)<=max(2,self.scrollbar_height*.12)
    def target_thumb(self,absolute_y,local_y=185):
        return max(self.top,min(self.bottom-self.scrollbar_height,(absolute_y-local_y)/self.scroll_scale))
    def order_matches(self,keys):
        positions=[self.ordered_title_keys.index(k) for k in keys if k in self.ordered_title_keys]
        return len(positions)==len(set(positions)) and positions==sorted(positions)

def fingerprint(keys,height,scale,top=99,bottom=575):
    text=json.dumps([list(keys),round(height,2),round(scale,3),float(top),float(bottom)],ensure_ascii=False,separators=(',',':'))
    return hashlib.sha256(text.encode()).hexdigest()

class DailyScanAccumulator:
    def __init__(self,key):
        self.key=key;self.observations_by_title={};self.entries={};self.frame_order=[]
        self.thumb_positions=[];self.overlap_edges=[];self.unresolved_ap_rows=[];self.scroll_scale=None
        self.absolute={};self.card_pitch=None
        self.edge_rechecks=set()
    def add_frame(self,entries,thumb,frame_index,ap_rows=None,forward=False):
        keys=[self.key(e.title) for e in entries]
        if len(keys)!=len(set(keys)):raise DailyIndexError('duplicate title on one frame')
        if forward and self.frame_order:
            old_thumb,old_keys=self.frame_order[-1]
            if thumb[0]<old_thumb-2:raise DailyIndexError('forward scrollbar order conflict')
            common=set(old_keys)&set(keys)
            if common:
                a=[k for k in old_keys if k in common];b=[k for k in keys if k in common]
                if a!=b:raise DailyIndexError('overlap title order conflict')
                self.overlap_edges.append((len(self.frame_order)-1,len(self.frame_order),tuple(a)))
        rows=ap_rows or {}
        for e,k in zip(entries,keys):
            y=e.discovered_position[2]
            if k not in rows:raise DailyIndexError('unmatched AP row')
            ap=float(rows[k])
            if not 40<=ap-y<=105:raise DailyIndexError('unmatched AP row')
            obs=DailyObservation(k,float(thumb[0]),float(thumb[1]),float(y),ap,int(frame_index))
            self.entries.setdefault(k,e)
            values=self.observations_by_title.setdefault(k,[])
            if not any(o.frame_index==obs.frame_index for o in values):values.append(obs)
        self.frame_order.append((float(thumb[0]),keys));self.thumb_positions.append(tuple(thumb))
        self.calibrate()
    def calibrate(self):
        samples=[]
        for values in self.observations_by_title.values():
            for a,b in zip(values,values[1:]):
                dt=b.thumb_top-a.thumb_top;dy=b.local_y-a.local_y
                if abs(dt)>=3 and abs(dy)>=20:
                    scale=-dy/dt
                    if 1<=scale<=150:samples.append(scale)
        if len(samples)>=3:
            center=median(samples);good=[s for s in samples if abs(s-center)<=center*.25]
            if len(good)>=3:self.scroll_scale=float(median(good))
        if self.scroll_scale:
            self.absolute={k:float(median(o.local_y+self.scroll_scale*o.thumb_top for o in values)) for k,values in self.observations_by_title.items()}
            for k,values in self.observations_by_title.items():
                if len(values)>1 and max(abs(o.local_y+self.scroll_scale*o.thumb_top-self.absolute[k]) for o in values)>70:
                    raise DailyIndexError('same-title absolute position conflict')
            positions=sorted(self.absolute.values());distances=[b-a for a,b in zip(positions,positions[1:]) if 120<=b-a<=240]
            if len(distances)>=3:self.card_pitch=float(median(distances))
    def verified(self,key):
        values=self.observations_by_title[key]
        return key in self.edge_rechecks or any(a.frame_index!=b.frame_index and abs(a.thumb_top-b.thumb_top)>=.5 and (abs(a.thumb_top-b.thumb_top)>=3 or abs(a.local_y-b.local_y)>=20)
                   for i,a in enumerate(values) for b in values[i+1:])
    def unverified(self):return [k for k in self.entries if not self.verified(k)]
    def gaps(self):
        if not self.card_pitch:return []
        ordered=sorted(self.absolute,key=self.absolute.get);result=[]
        for a,b in zip(ordered,ordered[1:]):
            distance=self.absolute[b]-self.absolute[a];n=round(distance/self.card_pitch)
            if n>=2:
                if n>6 or abs(distance/n-self.card_pitch)>self.card_pitch*.2:raise DailyIndexError('unresolved nonuniform content gap')
                result.extend(MissingPositionCandidate(a,b,self.absolute[a]+distance*i/n) for i in range(1,n))
        return result
    def build(self):
        if self.unresolved_ap_rows or self.unverified() or self.gaps():raise DailyIndexError('unverified entries or unresolved content gap')
        if not self.scroll_scale or len(self.absolute)!=len(self.entries):raise DailyIndexError('insufficient independent scrollbar calibration')
        keys=tuple(sorted(self.entries,key=self.absolute.get));records=[]
        for n,k in enumerate(keys):
            values=self.observations_by_title[k];representative=min(values,key=lambda o:abs(o.local_y-185));e=self.entries[k]
            loc=DailyQuestLocator(representative.thumb_top,representative.thumb_bottom,representative.local_y,self.absolute[k],n,
                                 keys[n-1] if n else None,keys[n+1] if n+1<len(keys) else None,len(values))
            records.append(DailyIndexRecord(e.title,k,e.quest_type,e.difficulty,loc,tuple(values),k in self.edge_rechecks))
        height=float(median(b-a for a,b in self.thumb_positions))
        return DailyQuestIndex(1,datetime.now(timezone.utc).isoformat(),height,self.scroll_scale,keys,tuple(records),fingerprint(keys,height,self.scroll_scale))

def save_index(index,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    payload=asdict(index);payload['entry_count']=index.entry_count
    temp=path.with_name(path.name+'.tmp');temp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)

def load_index(path):
    try:
        path=Path(path)
        if path.stat().st_size>2_000_000:return None
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('version')!=1 or data.get('invalidated'):return None
        records=[]
        for e in data['entries']:
            loc=DailyQuestLocator(**e['locator']);obs=tuple(DailyObservation(**o) for o in e['observations'])
            for value in (loc.thumb_top,loc.thumb_bottom,loc.local_y,loc.absolute_y):
                if not isinstance(value,(int,float)) or not math.isfinite(value):return None
            if len(obs)<2 or loc.observations!=len(obs):return None
            if any(o.title_key!=e['title_key'] or not 40<=o.ap_y-o.local_y<=105 or not 95<=o.thumb_top<o.thumb_bottom<=585 for o in obs):return None
            records.append(DailyIndexRecord(e['title'],e['title_key'],e['quest_type'],e['difficulty'],loc,obs,bool(e.get('edge_verified',False))))
        index=DailyQuestIndex(data['version'],data['generated_at'],float(data['scrollbar_height']),float(data['scroll_scale']),
                             tuple(data['ordered_title_keys']),tuple(records),data['fingerprint'],float(data['top']),float(data['bottom']))
        if not 1<=index.scroll_scale<=150 or not 20<=index.scrollbar_height<=490:return None
        if index.entry_count!=data['entry_count'] or tuple(e.title_key for e in records)!=index.ordered_title_keys:return None
        if len(set(index.ordered_title_keys))!=index.entry_count:return None
        if [e.locator.absolute_y for e in records]!=sorted(e.locator.absolute_y for e in records):return None
        if index.fingerprint!=fingerprint(index.ordered_title_keys,index.scrollbar_height,index.scroll_scale,index.top,index.bottom):return None
        return index
    except (OSError,ValueError,TypeError,KeyError):return None

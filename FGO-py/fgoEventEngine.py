"""Event-scoped advisory indexes and empirical learning; no device or images.

Cached positions suggest where to look. A live locator must independently prove
the title/AP/availability before any input. No FGO enemy-attribute database.
"""
from dataclasses import dataclass,asdict,field
from enum import Enum
from pathlib import Path
import hashlib,json,math,time,unicodedata,re

def textKey(text):return re.sub(r'\s+','',unicodedata.normalize('NFKC',str(text))).casefold()
def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:24]
def saveLocal(path,payload):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp');temp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)

class CampaignState(Enum):
    ENTER_EVENT='enter_event';EVENT_MAP='event_map';MAIN_NODE='main_node';STORY='story';BATTLE='battle'
    MISSION_GATE='mission_gate';MISSION_LIST='mission_list';FREE_QUEST='free_quest';FARMING='farming'
    REWARD='reward';NEXT_AREA='next_area';EVENT_COMPLETE='event_complete'

@dataclass(frozen=True)
class EventQuestEntry:
    eventKey:str
    areaKey:str
    title:str
    AP:int
    state:str
    screenPosition:tuple
    viewportSignature:str
    locator:dict
    missionTargetFingerprints:tuple=()
    observedMissionEffects:dict=field(default_factory=dict)
    firstSeen:float=field(default_factory=time.time)
    lastVerified:float=field(default_factory=time.time)
    questKind:str='free'
    def __post_init__(self):
        if not self.eventKey or not self.areaKey or not self.title:raise ValueError('Quest identity missing')
        if type(self.AP) is not int or self.AP<0:raise ValueError('Invalid AP')
        if self.state not in {'NEW','CLEARED','LOCKED','AVAILABLE'}:raise ValueError('Invalid availability')
        if self.locator.get('mode') not in {'LIST','MAP'}:raise ValueError('Unknown locator structure')
        if len(self.screenPosition)!=2 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in self.screenPosition):raise ValueError('Invalid position')
    @property
    def key(self):return digest([self.eventKey,self.areaKey,textKey(self.title),self.AP,self.questKind])
    @property
    def available(self):return self.state!='LOCKED' and self.questKind=='free'

class EventQuestIndex:
    def __init__(self,eventKey,path=None):
        self.eventKey=eventKey;self.path=Path(path) if path else None;self.entries={};self.completeAreas=set()
        if self.path and self.path.exists():
            data=json.loads(self.path.read_text(encoding='utf-8'))
            if data.get('version')!=1 or data.get('eventKey')!=eventKey:raise ValueError('Event index scope mismatch')
            self.completeAreas=set(data.get('completeAreas',[]))
            for raw in data.get('entries',[]):
                raw['screenPosition']=tuple(raw['screenPosition']);raw['missionTargetFingerprints']=tuple(raw.get('missionTargetFingerprints',[]))
                entry=EventQuestEntry(**raw)
                if entry.eventKey!=eventKey:raise ValueError('Foreign event entry')
                self.entries[entry.key]=entry
    def add(self,entry):
        if entry.eventKey!=self.eventKey:raise ValueError('Foreign event entry')
        old=self.entries.get(entry.key)
        if old:
            raw=asdict(entry);raw['firstSeen']=old.firstSeen;raw['observedMissionEffects']=old.observedMissionEffects
            entry=EventQuestEntry(**raw)
        self.entries[entry.key]=entry
    def save(self):
        if self.path:saveLocal(self.path,{'version':1,'eventKey':self.eventKey,'completeAreas':sorted(self.completeAreas),'entries':[asdict(e) for e in self.entries.values()]})
    def available(self,areaKey=None):return [e for e in self.entries.values() if e.available and (areaKey is None or e.areaKey==areaKey)]

@dataclass(frozen=True)
class EventFarmTask:
    quest:str
    runs:int|None=None
    mission:int|None=None
    untilComplete:bool=False
    def __post_init__(self):
        fixed=type(self.runs) is int and self.runs>0 and self.mission is None and not self.untilComplete
        target=self.runs is None and type(self.mission) is int and self.mission>0 and self.untilComplete
        if not self.quest or not(fixed or target):raise ValueError('Specify positive runs or one Mission-until-complete task')

@dataclass(frozen=True)
class EventCurrency:
    name:str
    current:int
    source:str
    def __post_init__(self):
        if not self.name or type(self.current) is not int or self.current<0 or not self.source:raise ValueError('Unproven currency')

def missionValue(card):
    match=re.fullmatch(r'(\d+)/(\d+)',str(card.get('progress','')))
    if not match or not card.get('condition'):raise ValueError('Mission requires full condition/fraction')
    current,total=map(int,match.groups())
    if not 0<=current<=total or total<=0:raise ValueError('Invalid progress')
    return current,total

class MissionEvidenceDB:
    def __init__(self,eventKey,path=None):
        self.eventKey=eventKey;self.path=Path(path) if path else None
        self.data={'version':1,'eventKey':eventKey,'quests':{},'experiments':[]}
        if self.path and self.path.exists():
            self.data=json.loads(self.path.read_text(encoding='utf-8'))
            if self.data.get('version')!=1 or self.data.get('eventKey')!=eventKey:raise ValueError('Evidence scope mismatch')
    def record(self,quest,entryId,before,after,*,won,source):
        if quest.eventKey!=self.eventKey or not entryId or won is not True or not source:raise ValueError('Experiment lacks unique won entry/evidence')
        old=next((r for r in self.data['experiments'] if r['entryId']==entryId),None)
        if old:
            if old['quest']!=quest.key or old['before']!=before or old['after']!=after:raise ValueError('Conflicting experiment identity')
            return old
        vector={}
        for number in sorted(set(before)&set(after)):
            a,b=before[number],after[number]
            av,at=missionValue(a);bv,bt=missionValue(b)
            if textKey(a['condition'])!=textKey(b['condition']) or at!=bt or bv<av:raise ValueError('Mission changed/reset; no mapping')
            if av==at:continue # A capped Mission cannot establish a negative.
            vector[str(number)]={'condition':a['condition'],'before':av,'after':bv,'total':at,'delta':bv-av}
        row={'entryId':entryId,'quest':quest.key,'before':before,'after':after,'deltaVector':vector,'source':source,'time':time.time()}
        self.data['quests'][quest.key]={'title':quest.title,'AP':quest.AP,'areaKey':quest.areaKey,'targetFingerprints':list(quest.missionTargetFingerprints)}
        self.data['experiments'].append(row);self.save();return row
    def effects(self,mission,condition):
        effects={}
        for row in self.data['experiments']:
            effect=row['deltaVector'].get(str(mission))
            if effect is None or textKey(effect['condition'])!=textKey(condition):continue
            values=effects.setdefault(row['quest'],[]);values.append(effect['delta'])
        return {key:{'samples':len(v),'positiveSamples':sum(x>0 for x in v),'negativeSamples':sum(x==0 for x in v),'averageDelta':sum(v)/len(v)} for key,v in effects.items()}
    def rank(self,quests,requirement):
        effects=self.effects(requirement['mission'],requirement['condition'])
        positiveIcons=set()
        for key,value in effects.items():
            if value['positiveSamples']:positiveIcons.update(self.data['quests'][key]['targetFingerprints'])
        result=[]
        for quest in quests:
            if not quest.available or quest.eventKey!=self.eventKey:continue
            effect=effects.get(quest.key,{})
            if effect.get('negativeSamples') and not effect.get('positiveSamples'):continue
            rank=(not bool(effect.get('positiveSamples')),not bool(positiveIcons.intersection(quest.missionTargetFingerprints)),quest.state!='NEW',quest.AP,quest.state=='CLEARED',textKey(quest.title))
            result.append((rank,quest))
        return [q for _,q in sorted(result,key=lambda v:v[0])]
    def save(self):
        if self.path:
            payload={**self.data,'derivedMappings':{},'negativeMappings':{}}
            pairs={(n,e['condition']) for r in self.data['experiments'] for n,e in r['deltaVector'].items()}
            for n,c in pairs:
                values=self.effects(n,c)
                payload['derivedMappings'][n]={k:v for k,v in values.items() if v['positiveSamples']}
                payload['negativeMappings'][n]={k:v for k,v in values.items() if v['negativeSamples'] and not v['positiveSamples']}
            saveLocal(self.path,payload)

@dataclass
class EventProfile:
    eventKey:str
    heading:str
    goal:str='CLEAR_MAIN_STORY'
    areas:list=field(default_factory=list)
    mapModes:list=field(default_factory=list)
    receiptTypes:list=field(default_factory=list)
    specialFormationTypes:list=field(default_factory=list)
    continueSupported:bool|None=None
    completeEvidence:list=field(default_factory=list)
    unsupported:list=field(default_factory=list)
    def save(self,path):saveLocal(path,asdict(self))

"""Small, Qt-free transition journal. Failure artifacts are local only."""
from dataclasses import asdict,dataclass
from datetime import datetime
from pathlib import Path
import json,logging,time,hashlib,math

@dataclass(frozen=True)
class TransitionRecord:
    timestamp:float
    monotonic_timestamp:float
    from_state:str
    to_state:str
    elapsed:float
    action:str
    evidence:tuple[str,...]
    last_input:str
    battle_sequence:int

class FlowTrace:
    def __init__(self,*,clock=time.monotonic,wall=time.time,logger=None,root=None):
        self.clock,self.wall=clock,wall
        self.logger=logger or logging.getLogger('fgo.Flow')
        self.root=Path(root) if root is not None else None
        self.records=[];self.state='UNKNOWN';self.since=clock()
        self.last_input='';self.battle_sequence=0;self.frames=[];self.last_evidence=()
        self.prebattle=None;self.last_physical_input=''
    def record(self,state,evidence=(),action=''):
        name=getattr(state,'name',str(state));now=self.clock()
        if name==self.state and not action and tuple(evidence)==self.last_evidence:return
        if action:
            if action.startswith(('press ','touch ','swipe ')):self.last_physical_input=action
            else:self.last_input=action
        row=TransitionRecord(self.wall(),now,self.state,name,max(0,now-self.since),action,tuple(evidence),self.last_input,self.battle_sequence)
        self.records.append(row)
        self.last_evidence=tuple(evidence)
        self.logger.info('[FLOW][流程] %s → %s (%.2fs) action=%s evidence=%s battle=%s',row.from_state,row.to_state,row.elapsed,action or '-',row.evidence,row.battle_sequence)
        if name!=self.state:self.state=name;self.since=now
    def beginFormationStart(self):
        # Narrow authorization: positive FORMATION, one recorded start action,
        # expected TURN_BEGIN. Other UNKNOWN screens remain forbidden.
        if self.state!='FORMATION' or self.last_input!='start_quest':return
        self.prebattle={'started':self.clock(),'samples':[],'frames':{},'previous':None,'unchanged_since':self.clock(),'logged':-float('inf'),'eligible':True}
    def endFormationStart(self):
        if self.prebattle is not None and self.root is not None:
            folder=self.root/(datetime.fromtimestamp(self.wall()).strftime('%Y%m%d-%H%M%S-%f')+'-formation')
            folder.mkdir(parents=True,exist_ok=False)
            (folder/'capture-diagnostics.json').write_text(json.dumps(self.prebattle['samples'],ensure_ascii=False,indent=2),encoding='utf-8')
            import cv2
            for name,image in self.prebattle['frames'].items():cv2.imwrite(str(folder/name),image)
        self.prebattle=None
    def formationSample(self,detect,state,capture_started,capture_finished):
        session=self.prebattle
        image=getattr(detect,'im',None)
        if session is None or getattr(image,'shape',None)!=(720,1280,3):return
        import numpy as np
        now=self.clock();name=getattr(state,'name',str(state))
        # A different positive foreground state revokes the narrow exception;
        # UNKNOWN after a network/login detour is not formation-start evidence.
        if name not in {'FORMATION','UNKNOWN','LOADING','TURN_BEGIN'}:session['eligible']=False
        digest=hashlib.sha256(image.tobytes()).hexdigest()[:16]
        previous=session['previous'];same=previous is not None and digest==previous[0]
        delta=None if previous is None else float(np.mean(np.abs(image[::8,::8].astype(np.int16)-previous[1])))
        if not same:session['unchanged_since']=now
        score=float(detect._loc(detect.tmpl.ATTACK,(1155,635,1210,682))[0]) if hasattr(detect,'_loc') else None
        if score is not None and not math.isfinite(score):score=None
        row={'capture_started_monotonic':capture_started,'capture_finished_monotonic':capture_finished,'observed_monotonic':now,'signature':digest,'mean_brightness':float(image.mean()),'attack_score':score,'attack_threshold':.05,'isTurnBegin':bool(detect.isTurnBegin()),'state':name,'identical_previous':same,'sampled_mean_delta':delta,'near_identical_previous':delta is not None and delta<.5,'identical_seconds':now-session['unchanged_since']}
        row['loading_progress_signature']=getattr(detect,'getLoadingProgressSignature',lambda:None)() if name=='LOADING' else None
        session['previous']=(digest,image[::8,::8].astype(np.int16))
        # Metadata is sampled at <=0.5Hz; full images occupy only four slots.
        if now-session['logged']>=2 or not session['samples'] or name!=session['samples'][-1]['state']:
            session['samples'].append(row);session['logged']=now
            self.logger.info('[FLOW][CAPTURE] %s',json.dumps(row,ensure_ascii=False))
        if name=='UNKNOWN' and session['eligible']:
            frames=session['frames'];frames.setdefault('first-unknown.png',image.copy())
            if now-session['started']>=30:frames.setdefault('middle-unknown.png',image.copy())
            frames['last-unknown.png']=image.copy()
        elif name=='LOADING' and session['eligible']:session['frames'].setdefault('loading-representative.png',image.copy())
    def frame(self,image,state):
        # Never persist an unclassified screen which could be a login/account page.
        safe={'TURN_BEGIN','BATTLE_RESULT','FORMATION','CONTINUE','DEFEATED','LOADING'}
        if image is not None and getattr(image,'shape',None)==(720,1280,3):
            self.frames=(self.frames+[(image.copy(),getattr(state,'name',str(state)) in safe)])[-2:]
    def failure(self,kind,expected,elapsed,evidence=(),from_state=None):
        summary={'kind':kind,'from':from_state or self.state,'last_observed':self.state,'expected':sorted(getattr(s,'name',str(s)) for s in expected),'elapsed':elapsed,'last_input':self.last_input,'last_physical_input':self.last_physical_input,'evidence':tuple(evidence),'battle_sequence':self.battle_sequence}
        self.logger.error('[FLOW][%s] from=%s expected=%s elapsed=%.2f last_input=%s evidence=%s',kind,summary['from'],'|'.join(summary['expected']),elapsed,self.last_input,tuple(evidence))
        if self.root is None:return summary
        try:
            folder=self.root/datetime.fromtimestamp(self.wall()).strftime('%Y%m%d-%H%M%S-%f')
            folder.mkdir(parents=True,exist_ok=False)
            (folder/'trace.json').write_text(json.dumps([asdict(row) for row in self.records],ensure_ascii=False,indent=2),encoding='utf-8')
            (folder/'summary.txt').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
            # Optional image dependency is loaded only when saving a failure.
            import cv2
            for name,(image,safe) in zip(('last-frame.png','previous-frame.png'),reversed(self.frames)):
                if safe:cv2.imwrite(str(folder/name),image)
            if self.prebattle is not None:
                (folder/'capture-diagnostics.json').write_text(json.dumps(self.prebattle['samples'],ensure_ascii=False,indent=2),encoding='utf-8')
                for name,image in self.prebattle['frames'].items():cv2.imwrite(str(folder/name),image)
            summary['local_path']=str(folder)
        except Exception:
            self.logger.exception('Could not save local flow diagnostics')
        return summary

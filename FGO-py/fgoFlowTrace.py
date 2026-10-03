"""Small, Qt-free transition journal. Failure artifacts are local only."""
from dataclasses import asdict,dataclass
from datetime import datetime
from pathlib import Path
import json,logging,time

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
        self.last_input='';self.battle_sequence=0;self.frames=[]
    def record(self,state,evidence=(),action=''):
        name=getattr(state,'name',str(state));now=self.clock()
        if name==self.state and not action:return
        if action:self.last_input=action
        row=TransitionRecord(self.wall(),now,self.state,name,max(0,now-self.since),action,tuple(evidence),self.last_input,self.battle_sequence)
        self.records.append(row)
        self.logger.info('[FLOW][流程] %s → %s (%.2fs) action=%s evidence=%s battle=%s',row.from_state,row.to_state,row.elapsed,action or '-',row.evidence,row.battle_sequence)
        if name!=self.state:self.state=name;self.since=now
    def frame(self,image,state):
        # Never persist an unclassified screen which could be a login/account page.
        safe={'TURN_BEGIN','BATTLE_RESULT','FORMATION','CONTINUE','DEFEATED','LOADING'}
        if image is not None and getattr(image,'shape',None)==(720,1280,3):
            self.frames=(self.frames+[(image.copy(),getattr(state,'name',str(state)) in safe)])[-2:]
    def failure(self,kind,expected,elapsed,evidence=()):
        summary={'kind':kind,'from':self.state,'expected':sorted(getattr(s,'name',str(s)) for s in expected),'elapsed':elapsed,'last_input':self.last_input,'evidence':tuple(evidence),'battle_sequence':self.battle_sequence}
        self.logger.error('[FLOW][%s] from=%s expected=%s elapsed=%.2f last_input=%s evidence=%s',kind,self.state,'|'.join(summary['expected']),elapsed,self.last_input,tuple(evidence))
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
            summary['local_path']=str(folder)
        except Exception:
            self.logger.exception('Could not save local flow diagnostics')
        return summary

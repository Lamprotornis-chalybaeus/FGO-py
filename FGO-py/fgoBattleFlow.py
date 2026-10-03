"""Read-only classification and bounded waits shared by every battle entry."""
from dataclasses import dataclass
from enum import Enum,auto
import time
from fgoSchedule import ScriptStop
from fgoFlowTrace import FlowTrace

class BattleFlowState(Enum):
    UNKNOWN=auto();QUEST_READY=auto();AP_EMPTY=auto();FRIEND=auto()
    FRIEND_EMPTY=auto();FORMATION=auto();STARTING=auto();LOADING=auto()
    TURN_BEGIN=auto();BATTLE_RESULT=auto();ADD_FRIEND=auto();CONTINUE=auto()
    DEFEATED=auto();NETWORK_ERROR=auto();SPECIAL_MODAL=auto()
    SKILL_CAST_FAILED=auto();AMBIGUOUS=auto()

@dataclass(frozen=True)
class FlowObservation:
    state:BattleFlowState
    evidence:tuple[str,...]
    timestamp:float

@dataclass(frozen=True)
class FriendSelectionResult:
    selected:bool
    template:str|None=None
    refreshes:int=0
    state:BattleFlowState=BattleFlowState.FORMATION

class FlowTimeout(ScriptStop):pass
class AmbiguousState(ScriptStop):pass

DETECTORS=(('isNetworkError','NETWORK_ERROR'),('isBattleContinue','CONTINUE'),
    ('isApEmpty','AP_EMPTY'),('isAddFriend','ADD_FRIEND'),('isBattleDefeated','DEFEATED'),
    ('isSkillCastFailed','SKILL_CAST_FAILED'),('isBattleFormation','FORMATION'),
    ('isChooseFriend','FRIEND'),('isNoFriend','FRIEND_EMPTY'),('isTurnBegin','TURN_BEGIN'),
    ('isBattleFinished','BATTLE_RESULT'),('isSpecialDropSuspended','SPECIAL_MODAL'),
    ('isMainInterface','QUEST_READY'))

def observeBattleFlow(detect,*,clock=time.monotonic):
    hits=[];evidence=[]
    for method,state in DETECTORS:
        predicate=getattr(detect,method,None)
        if callable(predicate) and bool(predicate()):
            hits.append(BattleFlowState[state]);evidence.append(method+'=True')
    # Foreground dialogs may have a recognized background. This precedence is
    # explicit, recorded, and never permits a friend input through CONTINUE.
    foreground=('NETWORK_ERROR','CONTINUE','AP_EMPTY','ADD_FRIEND','DEFEATED','SKILL_CAST_FAILED','SPECIAL_MODAL','FRIEND_EMPTY')
    priority=next((BattleFlowState[s] for s in foreground if BattleFlowState[s] in hits),None)
    if priority:
        if len(hits)>1:evidence.append('ambiguous evidence: explicit foreground priority '+priority.name)
        state=priority
    else:
        strong=[s for s in hits if s!=BattleFlowState.QUEST_READY]
        if len(strong)>1:state=BattleFlowState.AMBIGUOUS;evidence.append('ambiguous evidence: conflicting foreground states')
        elif strong:state=strong[0]
        elif hits:state=hits[0]
        else:
            image=getattr(detect,'im',None)
            # Darkness only authorizes waiting; never input or battle counting.
            loading=getattr(detect,'isLoading',None)
            if callable(loading) and loading() or getattr(image,'shape',None)==(720,1280,3) and float(image.mean())<18:
                state=BattleFlowState.LOADING;evidence.append('dark loading frame; wait only')
            else:state=BattleFlowState.UNKNOWN;evidence.append('all known positive detectors false')
    return FlowObservation(state,tuple(evidence),clock())

class BattleFlow:
    def __init__(self,reader,schedule,*,trace=None,clock=time.monotonic,poll=.2,network=None):
        self.reader,self.schedule,self.clock=reader,schedule,clock
        self.poll=poll;self.trace=trace or FlowTrace(clock=clock)
        self.network=network;self.observation=None;self.detect=None;self.networkHandled=False
    def observe(self):
        self.schedule.checkStop();self.schedule.checkSuspend()
        self.detect=self.reader()
        self.observation=observeBattleFlow(self.detect,clock=self.clock)
        self.trace.frame(getattr(self.detect,'im',None),self.observation.state)
        self.trace.record(self.observation.state,self.observation.evidence)
        if self.observation.state==BattleFlowState.AMBIGUOUS:
            self.fail(AmbiguousState,'AMBIGUOUS',(),0)
        return self.observation
    def action(self,name,callback):
        self.schedule.checkStop()
        self.trace.record(self.observation.state if self.observation else BattleFlowState.UNKNOWN,
            self.observation.evidence if self.observation else (),name)
        return callback()
    def fail(self,exception,kind,expected,elapsed):
        evidence=self.observation.evidence if self.observation else ()
        summary=self.trace.failure(kind,expected,elapsed,evidence)
        raise exception(f'Flow {kind}: from={summary["from"]} expected={"|".join(summary["expected"])} elapsed={elapsed:.2f} last_input={summary["last_input"]} evidence={evidence}')
    def waitForFlowState(self,expected,*,timeout,transition_name,allowed_intermediate=(),on_skill_error=None):
        expected=set(expected);allowed=set(allowed_intermediate);start=self.clock()
        while self.clock()-start<timeout:
            observation=self.observe();state=observation.state
            if state in expected:return observation
            if state==BattleFlowState.NETWORK_ERROR and self.network:
                if not self.networkHandled:
                    self.action('network_error_confirm',lambda:self.network(self.detect));self.networkHandled=True
            else:
                self.networkHandled=False
                if state==BattleFlowState.SKILL_CAST_FAILED and on_skill_error:
                    self.action('skill_cast_failed_recover',on_skill_error)
                elif state not in allowed|{BattleFlowState.UNKNOWN,BattleFlowState.LOADING}:
                    self.fail(FlowTimeout,'UNEXPECTED_STATE '+transition_name,expected,self.clock()-start)
            self.schedule.sleep(self.poll)
        self.fail(FlowTimeout,'TIMEOUT '+transition_name,expected,self.clock()-start)

def waitForFlowState(flow,expected,**kwargs):return flow.waitForFlowState(expected,**kwargs)

"""Read-only classification and bounded waits shared by every battle entry."""
from dataclasses import dataclass
from enum import Enum,auto
import time
from fgoSchedule import ScriptStop
from fgoFlowTrace import FlowTrace

class BattleFlowState(Enum):
    UNKNOWN=auto();QUEST_READY=auto();AP_EMPTY=auto();FRIEND=auto()
    FRIEND_EMPTY=auto();FORMATION=auto();LOADING=auto()
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
        self.deadline=None
        self.network=network;self.observation=None;self.detect=None;self.networkHandled=False
    def observe(self):
        self.schedule.checkStop();self.schedule.checkSuspend()
        capture_started=self.clock();self.detect=self.reader();capture_finished=self.clock()
        self.observation=observeBattleFlow(self.detect,clock=self.clock)
        self.trace.formationSample(self.detect,self.observation.state,capture_started,capture_finished)
        if self.observation.state not in {BattleFlowState.NETWORK_ERROR,BattleFlowState.UNKNOWN,BattleFlowState.LOADING}:self.networkHandled=False
        self.trace.frame(getattr(self.detect,'im',None),self.observation.state)
        self.trace.record(self.observation.state,self.observation.evidence)
        if self.observation.state==BattleFlowState.AMBIGUOUS:
            self.fail(AmbiguousState,'AMBIGUOUS',(),0)
        return self.observation
    def action(self,name,callback):
        self.schedule.checkStop()
        if self.deadline is not None and self.clock()>=self.deadline:
            self.fail(FlowTimeout,'TIMEOUT battle total before input',(),0)
        self.trace.record(self.observation.state if self.observation else BattleFlowState.UNKNOWN,
            self.observation.evidence if self.observation else (),name)
        return callback()
    def deviceInput(self,action):
        # Observe input names/coordinates, never game/account data.
        self.schedule.checkStop()
        if self.deadline is not None and self.clock()>=self.deadline:
            self.fail(FlowTimeout,'TIMEOUT battle total before input',(),0)
        self.trace.record(self.observation.state if self.observation else BattleFlowState.UNKNOWN,
            self.observation.evidence if self.observation else (),action)
    def fail(self,exception,kind,expected,elapsed,*,from_state=None):
        evidence=self.observation.evidence if self.observation else ()
        summary=self.trace.failure(kind,expected,elapsed,evidence,from_state or getattr(self,'waitFrom',None))
        raise exception(f'Flow {kind}: from={summary["from"]} expected={"|".join(summary["expected"])} elapsed={elapsed:.2f} last_input={summary["last_input"]} evidence={evidence}')
    def waitForFlowState(self,expected,*,timeout,transition_name,allowed_intermediate=(),on_skill_error=None):
        expected=set(expected);allowed=set(allowed_intermediate);start=self.clock()
        if self.deadline is not None:timeout=min(timeout,max(0,self.deadline-start))
        skillHandled=self.trace.last_input=='skill_cast_failed_recover'
        self.waitFrom=self.trace.state
        while self.clock()-start<timeout:
            observation=self.observe();state=observation.state
            if state in expected:self.waitFrom=None;return observation
            if state==BattleFlowState.NETWORK_ERROR and self.network:
                if not self.networkHandled:
                    self.action('network_error_confirm',lambda:self.network(self.detect));self.networkHandled=True
            else:
                if state==BattleFlowState.SKILL_CAST_FAILED and on_skill_error:
                    if not skillHandled:self.action('skill_cast_failed_recover',on_skill_error);skillHandled=True
                elif state not in allowed|{BattleFlowState.UNKNOWN,BattleFlowState.LOADING}:
                    self.fail(FlowTimeout,'UNEXPECTED_STATE '+transition_name,expected,self.clock()-start)
                elif state not in {BattleFlowState.UNKNOWN,BattleFlowState.LOADING}:skillHandled=False
            self.schedule.sleep(self.poll)
        self.fail(FlowTimeout,'TIMEOUT '+transition_name,expected,self.clock()-start)

def waitForFlowState(flow,expected,**kwargs):return flow.waitForFlowState(expected,**kwargs)

class BattleCycle:
    """Both initial and repeat entries converge on FRIEND -> FORMATION -> TURN."""
    def __init__(self,main,flow):self.main,self.flow=main,flow
    def prepare(self,quest_index=0):
        S=BattleFlowState;deadline=self.flow.clock()+180
        observation=self.flow.observe()
        while self.flow.clock()<deadline:
            state=observation.state
            if state==S.TURN_BEGIN:return True
            if state==S.QUEST_READY:
                self.main.verifyQuest()
                self.flow.action('enter_quest',lambda:self.main.press('84L'[quest_index]))
                quest_index=0
                observation=self.flow.waitForFlowState({S.FRIEND,S.FRIEND_EMPTY,S.FORMATION,S.CONTINUE,S.AP_EMPTY,S.SKILL_CAST_FAILED},timeout=45,transition_name='quest entry',allowed_intermediate={S.QUEST_READY})
            elif state==S.CONTINUE:
                self.flow.action('continue',lambda:self.main.press('K'))
                observation=self.flow.waitForFlowState({S.FRIEND,S.FRIEND_EMPTY,S.FORMATION,S.AP_EMPTY,S.SKILL_CAST_FAILED},timeout=45,transition_name='continue exit',allowed_intermediate={S.CONTINUE})
            elif state==S.AP_EMPTY:
                restored=self.flow.action('ap_policy',self.main.eatApple)
                if not restored:self.main.completionReason='Ap Empty';return False
                observation=self.flow.waitForFlowState({S.FRIEND,S.FRIEND_EMPTY,S.FORMATION},timeout=45,transition_name='AP policy',allowed_intermediate={S.AP_EMPTY})
            elif state in {S.FRIEND,S.FRIEND_EMPTY}:
                self.main.chooseFriend(flow=self.flow)
                observation=self.flow.observation
            elif state==S.FORMATION:
                self.main.prepareFormation(self.flow)
                return True
            elif state==S.SKILL_CAST_FAILED:
                self.flow.action('storm_pot_unavailable_close',lambda:self.main.press('J'))
                self.main.completionReason='No Storm Pot';return False
            else:
                observation=self.flow.waitForFlowState({S.QUEST_READY,S.FRIEND,S.FRIEND_EMPTY,S.FORMATION,S.CONTINUE,S.AP_EMPTY,S.TURN_BEGIN},timeout=min(45,max(0,deadline-self.flow.clock())),transition_name='battle entry')
        self.flow.fail(FlowTimeout,'TIMEOUT battle preparation',{S.TURN_BEGIN},180)
    def settleBattleResult(self):
        S=BattleFlowState;observation=self.flow.observe()
        deadline=self.flow.clock()+60
        while self.flow.clock()<deadline:
            state=observation.state
            if state in {S.CONTINUE,S.QUEST_READY}:return observation
            if state==S.BATTLE_RESULT:
                self.flow.action('result_next',lambda:self.main.press(' '))
                observation=self.flow.waitForFlowState({S.ADD_FRIEND,S.CONTINUE,S.QUEST_READY,S.SPECIAL_MODAL},timeout=30,transition_name='result dismissal',allowed_intermediate={S.BATTLE_RESULT})
            elif state==S.ADD_FRIEND:
                self.flow.action('close_add_friend',lambda:self.main.press('X'))
                observation=self.flow.waitForFlowState({S.CONTINUE,S.QUEST_READY,S.BATTLE_RESULT},timeout=20,transition_name='friend request close',allowed_intermediate={S.ADD_FRIEND})
            elif state==S.SPECIAL_MODAL:
                self.main.checkSpecialModal()
                self.flow.action('close_special_modal',lambda:self.main.press('\x1B'))
                observation=self.flow.waitForFlowState({S.CONTINUE,S.QUEST_READY,S.BATTLE_RESULT,S.ADD_FRIEND},timeout=20,transition_name='special result modal',allowed_intermediate={S.SPECIAL_MODAL})
            else:
                observation=self.flow.waitForFlowState({S.BATTLE_RESULT,S.ADD_FRIEND,S.CONTINUE,S.QUEST_READY,S.SPECIAL_MODAL},timeout=30,transition_name='settlement')
        self.flow.fail(FlowTimeout,'TIMEOUT settlement',{S.CONTINUE,S.QUEST_READY},60)
    def finish(self):
        S=BattleFlowState
        if self.flow.observation and self.flow.observation.state==S.CONTINUE:
            self.flow.action('decline_continue',lambda:self.main.press('F'))
            self.flow.waitForFlowState({S.QUEST_READY},timeout=30,transition_name='return after limit',allowed_intermediate={S.CONTINUE})

"""Read-only classification and bounded waits shared by every battle entry."""
from dataclasses import dataclass,replace
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
    # Incremented only after reader() completes a new capture. Identical pixels
    # are allowed; this is acquisition freshness, not a claim about JAVACAP.
    capture_sequence:int|None=None

@dataclass(frozen=True)
class FriendSelectionResult:
    selected:bool
    template:str|None=None
    refreshes:int=0
    state:BattleFlowState=BattleFlowState.FORMATION

class FlowTimeout(ScriptStop):pass
class AmbiguousState(ScriptStop):pass

class BondResultEpisode:
    """Only CN bond overlays may repeat by a stable, local instance signature."""
    def __init__(self):
        self.acknowledged=None;self.candidate=None;self.count=0;self.sequence=None
    @staticmethod
    def distance(a,b):
        if len(a)!=len(b):return 1
        return sum(x!=y for x,y in zip(a,b))/len(a)
    def ready(self,detect,sequence):
        signature=getattr(detect,'_battleResultInstanceSignature',lambda:None)()
        if not isinstance(signature,bytes) or not signature or sequence is None:
            self.candidate=None;self.count=0;self.sequence=sequence;return False
        # Small raster/animation jitter cannot authorize a second input. The
        # stable foreground mask must differ materially from the last overlay.
        if self.acknowledged is not None and self.distance(signature,self.acknowledged)<.05:
            self.candidate=None;self.count=0;self.sequence=sequence;return False
        if sequence==self.sequence:return self.count>=3
        consecutive=self.sequence is not None and sequence==self.sequence+1
        if consecutive and self.candidate is not None and self.distance(signature,self.candidate)<=.01:
            self.count+=1
        else:self.candidate=signature;self.count=1
        self.sequence=sequence
        return self.count>=3
    def acknowledge(self):
        self.acknowledged=self.candidate
        self.candidate=None;self.count=0

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
            if state=='BATTLE_RESULT' and callable(getattr(detect,'getBattleResultPage',None)):
                evidence.append('result_page='+str(detect.getBattleResultPage()))
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
            if callable(loading) and loading():
                state=BattleFlowState.LOADING;evidence.append('isLoading=True; positive fixed loading labels; wait only')
            elif getattr(image,'shape',None)==(720,1280,3) and float(image.mean())<18:
                state=BattleFlowState.LOADING;evidence.append('dark loading frame; wait only')
            else:state=BattleFlowState.UNKNOWN;evidence.append('all known positive detectors false')
    return FlowObservation(state,tuple(evidence),clock())

class BattleFlow:
    def __init__(self,reader,schedule,*,trace=None,clock=time.monotonic,poll=.2,network=None):
        self.reader,self.schedule,self.clock=reader,schedule,clock
        self.poll=poll;self.trace=trace or FlowTrace(clock=clock)
        self.deadline=None
        self.network=network;self.observation=None;self.detect=None;self.networkHandled=False
        self.captureSequence=0
    def observe(self):
        self.schedule.checkStop();self.schedule.checkSuspend()
        if self.deadline is not None and self.clock()>=self.deadline:
            self.fail(FlowTimeout,'TIMEOUT active hard deadline',(),0)
        capture_started=self.clock();self.detect=self.reader();capture_finished=self.clock()
        self.captureSequence+=1
        self.observation=replace(observeBattleFlow(self.detect,clock=self.clock),capture_sequence=self.captureSequence)
        self.trace.formationSample(self.detect,self.observation.state,capture_started,capture_finished)
        if self.observation.state not in {BattleFlowState.NETWORK_ERROR,BattleFlowState.UNKNOWN,BattleFlowState.LOADING}:self.networkHandled=False
        self.trace.frame(getattr(self.detect,'im',None),self.observation.state)
        self.trace.record(self.observation.state,self.observation.evidence)
        if self.deadline is not None and self.clock()>=self.deadline:
            self.fail(FlowTimeout,'TIMEOUT active hard deadline',(),0)
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
        context=''
        if 'turn' in summary:
            context=(f' battle={summary["battle_sequence"]} turn={summary["turn"]} phase={summary["phase"]}'
                     f' last_positive={summary["last_positive_state"]} sinceProgress={summary["elapsed_since_progress"]:.2f}'
                     f' phaseElapsed={summary["elapsed_since_turn_input"]:.2f} last_physical_input={summary["last_physical_input"]}')
        raise exception(f'Flow {kind}: from={summary["from"]} expected={"|".join(summary["expected"])} elapsed={elapsed:.2f} last_input={summary["last_input"]} evidence={evidence}{context}')
    def waitForFlowState(self,expected,*,timeout,transition_name,allowed_intermediate=(),on_skill_error=None,accept=None,stall_timeout=None,progress_signature=None):
        expected=set(expected);allowed=set(allowed_intermediate);start=self.clock()
        if self.deadline is not None:timeout=min(timeout,max(0,self.deadline-start))
        skillHandled=self.trace.last_input=='skill_cast_failed_recover'
        self.waitFrom=self.trace.state
        lastProgress=start;seenStates=set();lastSignature=None
        while self.clock()-start<timeout:
            observation=self.observe();state=observation.state
            if self.clock()-start>=timeout:self.fail(FlowTimeout,'TIMEOUT '+transition_name,expected,self.clock()-start)
            if state in expected:
                if accept is None or accept(self.detect):self.waitFrom=None;return observation
                self.schedule.sleep(self.poll);continue
            if stall_timeout is not None:
                # A positive intermediate state advances once; UNKNOWN flicker
                # cannot repeatedly renew the stall budget. Only a positively
                # gated loading indicator signature can keep renewing it.
                if state in allowed and state not in seenStates:
                    seenStates.add(state);lastProgress=self.clock()
                signature=progress_signature(self.detect) if progress_signature and state==BattleFlowState.LOADING else None
                if signature is not None and signature!=lastSignature:lastSignature=signature;lastProgress=self.clock()
                if self.clock()-lastProgress>=stall_timeout:self.fail(FlowTimeout,'STALL '+transition_name,expected,self.clock()-lastProgress)
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
    """Initial formation and CN repeat direct entry share one preparation budget."""
    def __init__(self,main,flow):self.main,self.flow=main,flow
    def prepare(self,quest_index=0):
        previousDeadline=self.flow.deadline
        self.flow.deadline=min(self.flow.clock()+180,previousDeadline if previousDeadline is not None else float('inf'))
        try:return self._prepare(quest_index,self.flow.deadline)
        finally:self.flow.deadline=previousDeadline
    def _prepare(self,quest_index,deadline):
        S=BattleFlowState;continued=False
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
                continued=True
                self.flow.action('continue',lambda:self.main.press('K'))
                observation=self.flow.waitForFlowState({S.FRIEND,S.FRIEND_EMPTY,S.FORMATION,S.AP_EMPTY,S.SKILL_CAST_FAILED},timeout=45,transition_name='continue exit',allowed_intermediate={S.CONTINUE})
            elif state==S.AP_EMPTY:
                restored=self.flow.action('ap_policy',lambda:self.main.eatApple(self.flow))
                if not restored:self.main.completionReason='Ap Empty';return False
                observation=self.flow.waitForFlowState({S.QUEST_READY,S.FRIEND,S.FRIEND_EMPTY,S.FORMATION},timeout=45,transition_name='AP policy',allowed_intermediate={S.AP_EMPTY})
            elif state in {S.FRIEND,S.FRIEND_EMPTY}:
                self.main.chooseFriend(flow=self.flow,continued=continued)
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
        overlay=BondResultEpisode()
        def nextResultInstance(d,page):
            if not page or not d.isBattleFinished() or d.getBattleResultPage()!=page:return True
            return page=='BOND_LEVEL_UP' and overlay.ready(d,self.flow.observation.capture_sequence)
        while self.flow.clock()<deadline:
            state=observation.state
            if state in {S.CONTINUE,S.QUEST_READY}:return observation
            if state==S.BATTLE_RESULT:
                page=getattr(self.flow.detect,'getBattleResultPage',lambda:None)()
                if page=='BOND_LEVEL_UP':
                    if not overlay.ready(self.flow.detect,observation.capture_sequence):
                        observation=self.flow.waitForFlowState({S.BATTLE_RESULT,S.ADD_FRIEND,S.CONTINUE,S.QUEST_READY,S.SPECIAL_MODAL},timeout=min(30,max(0,deadline-self.flow.clock())),transition_name='bond result instance',accept=lambda d:nextResultInstance(d,page))
                        continue
                    overlay.acknowledge()
                self.flow.action('result_next',lambda:self.main.press(' '))
                expected={S.ADD_FRIEND,S.CONTINUE,S.QUEST_READY,S.SPECIAL_MODAL}|({S.BATTLE_RESULT} if page else set())
                observation=self.flow.waitForFlowState(expected,timeout=min(30,max(0,deadline-self.flow.clock())),transition_name='result dismissal',allowed_intermediate={S.BATTLE_RESULT},accept=lambda d:nextResultInstance(d,page))
            elif state==S.ADD_FRIEND:
                self.flow.action('close_add_friend',lambda:self.main.press('X'))
                # Observed result-to-list dark load lasted 24s. The former
                # 20s sub-wait expired despite a valid eventual QUEST_READY.
                # Allow bounded positive loading within the existing overall
                # settlement deadline; no extra dismissal input is sent.
                observation=self.flow.waitForFlowState({S.CONTINUE,S.QUEST_READY,S.BATTLE_RESULT},
                    timeout=min(45,max(0,deadline-self.flow.clock())),stall_timeout=30,
                    transition_name='friend request close',allowed_intermediate={S.ADD_FRIEND,S.LOADING},
                    progress_signature=lambda d:getattr(d,'getLoadingProgressSignature',lambda:None)())
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

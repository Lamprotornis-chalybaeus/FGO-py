"""Whole-cycle simulations exercise the real Main/Cycle and inputs in order."""
import os,sys,time,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];APP=ROOT/'FGO-py'
sys.path.insert(0,str(APP))
cwd=os.getcwd();os.chdir(APP)
try:import fgoKernel as kernel
finally:os.chdir(cwd)
from fgoBattleFlow import BattleFlow,BattleFlowState as S,FlowTimeout
from fgoFlowTrace import FlowTrace
from test_battle_flow import Clock,frame

class Scenario(Clock):
    def __init__(self,*,friend_delay=0,formation_delay=0,loading=20,add_friend=True,ap_empty=False,fail=None,network=False,defeated=False):
        self.now=0;self.state='QUEST_READY';self.actions=[];self.pending=None
        self.friend_delay=friend_delay;self.formation_delay=formation_delay;self.loading=loading
        self.add_friend=add_friend;self.ap_empty=ap_empty;self.fail=fail;self.network=network;self.defeated=defeated
        self.limit=0;self.battles=0;self.callbacks=[];self.network_return=None
    def read(self):
        if self.pending and self.now>=self.pending[0]:self.state=self.pending[1];self.pending=None
        f=frame(self.state);f.getTeamIndex=lambda:0
        return f
    def to(self,state,delay=0):
        if delay:self.state='LOADING';self.pending=(self.now+delay,state)
        else:self.state=state;self.pending=None
    def press(self,key):
        state=self.state;self.actions.append((state,key))
        if state=='QUEST_READY' and key=='8':self.to('AP_EMPTY' if self.ap_empty else 'FRIEND',self.friend_delay)
        elif state=='CONTINUE' and key=='K':
            if self.fail!='continue':self.to('FRIEND',self.friend_delay)
        elif state=='FRIEND' and key=='8':
            self.to('UNKNOWN' if self.fail=='friend' else 'FORMATION',self.formation_delay)
        elif state=='FORMATION' and key==' ':
            self.to('UNKNOWN' if self.fail=='formation' else 'TURN_BEGIN',self.loading)
            if self.fail=='loading':self.pending=None
            if self.network:self.network=False;self.network_return=self.pending;self.state='NETWORK_ERROR'
        elif state=='NETWORK_ERROR' and key=='K':self.state='LOADING';self.pending=self.network_return
        elif state=='BATTLE_RESULT' and key==' ':self.to('ADD_FRIEND' if self.add_friend else 'CONTINUE')
        elif state=='ADD_FRIEND' and key=='X':self.to('CONTINUE')
        elif state=='CONTINUE' and key=='F':self.to('QUEST_READY')
        elif state=='AP_EMPTY' and key=='Z':self.to('QUEST_READY')
        else:raise AssertionError(f'Unexpected input {state}:{key}')
    def checkStopLater(self):
        if self.limit:
            self.limit-=1
            if not self.limit:raise kernel.ScriptStop('Stop Appointment Effected')
    def checkKizunaReisou(self):pass
    def checkDefeated(self):
        if self.defeated:raise kernel.ScriptStop('Battle Defeated')
    def battle(self):
        scenario=self
        class FakeBattle:
            defeated=False
            def __call__(self):
                assert scenario.state=='TURN_BEGIN','Battle ran before confirmed TURN_BEGIN'
                scenario.battles+=1
                if scenario.fail=='during_battle':raise kernel.ScriptStop('Interrupted after TURN_BEGIN')
                scenario.now+=30
                scenario.state='DEFEATED' if scenario.defeated else 'BATTLE_RESULT'
                self.defeated=scenario.defeated
                if self.defeated:raise kernel.ScriptStop('Battle Defeated')
                return True
            @property
            def result(self):return {'turn':3,'time':30}
        return FakeBattle()

class CycleTests(unittest.TestCase):
    def runScenario(self,scenario,total=1):
        trace=FlowTrace(clock=scenario,wall=lambda:1)
        flow=BattleFlow(scenario.read,scenario,clock=scenario,trace=trace,network=kernel.handleNetworkError)
        run=kernel.Main(0,0,scenario.battle,friendPolicy='first',onProgress=scenario.callbacks.append)
        with patch.object(run,'makeFlow',return_value=flow),patch.object(kernel,'schedule',scenario),patch.object(kernel.fgoDevice.device,'press',side_effect=scenario.press),patch.object(kernel.friendImg,'flush',return_value=False),patch.object(run,'verifyQuest'):
            try:run(0,total);error=None
            except kernel.ScriptStop as e:error=e
        return run,flow,error
    def assertCounters(self,run,started,completed,wins,defeats):
        r=run.result
        self.assertEqual((r['startedBattles'],r['completedAttempts'],r['wins'],r['defeats']),(started,completed,wins,defeats))
        self.assertEqual(r['battle'],completed);self.assertEqual(r['defeated'],defeats)
        self.assertEqual(wins+defeats,completed);self.assertGreaterEqual(started,completed)
    def test_first_full_cycle(self):
        s=Scenario();run,flow,error=self.runScenario(s)
        self.assertIsNone(error);self.assertCounters(run,1,1,1,0)
        self.assertEqual(s.actions,[('QUEST_READY','8'),('FRIEND','8'),('FORMATION',' '),('BATTLE_RESULT',' '),('ADD_FRIEND','X'),('CONTINUE','F')])
    def test_two_complete_cycles_share_formation_start(self):
        s=Scenario();run,flow,error=self.runScenario(s,2)
        self.assertIsNone(error);self.assertCounters(run,2,2,2,0)
        self.assertEqual([a for a in s.actions if a[0]=='FORMATION'],[('FORMATION',' ')]*2)
        self.assertEqual([a for a in s.actions if a[0]=='CONTINUE'],[('CONTINUE','K'),('CONTINUE','F')])
    def test_persistent_continue_never_selects_friend(self):
        s=Scenario(fail='continue');run,flow,error=self.runScenario(s,2)
        self.assertIsInstance(error,FlowTimeout);self.assertCounters(run,1,1,1,0)
        self.assertEqual(s.actions.count(('FRIEND','8')),1)
        self.assertEqual(s.actions.count(('CONTINUE','K')),1)
    def test_delayed_friend_ten_seconds(self):
        run,flow,error=self.runScenario(Scenario(friend_delay=10));self.assertIsNone(error);self.assertCounters(run,1,1,1,0)
    def test_delayed_formation_ten_seconds(self):
        run,flow,error=self.runScenario(Scenario(formation_delay=10));self.assertIsNone(error);self.assertCounters(run,1,1,1,0)
    def test_twenty_second_loading_does_not_assume_sleep_six(self):
        s=Scenario(loading=20);run,flow,error=self.runScenario(s)
        self.assertIsNone(error);self.assertGreaterEqual(s.now,50)
        turn=next(r for r in flow.trace.records if r.to_state=='TURN_BEGIN')
        self.assertGreaterEqual(turn.monotonic_timestamp,20)
    def test_friend_unknown_timeout_before_start(self):
        run,flow,error=self.runScenario(Scenario(fail='friend'))
        self.assertIsInstance(error,FlowTimeout);self.assertCounters(run,0,0,0,0)
    def test_formation_unknown_timeout_before_start(self):
        run,flow,error=self.runScenario(Scenario(fail='formation'))
        self.assertIsInstance(error,FlowTimeout);self.assertCounters(run,0,0,0,0)
    def test_loading_timeout_before_start(self):
        run,flow,error=self.runScenario(Scenario(fail='loading'))
        self.assertIsInstance(error,FlowTimeout);self.assertCounters(run,0,0,0,0)
    def test_network_during_start_has_one_worker_confirmation(self):
        s=Scenario(network=True);run,flow,error=self.runScenario(s)
        self.assertIsNone(error);self.assertEqual(s.actions.count(('NETWORK_ERROR','K')),1)
    def test_settle_without_friend_request(self):
        s=Scenario(add_friend=False);run,flow,error=self.runScenario(s)
        self.assertIsNone(error);self.assertNotIn(('ADD_FRIEND','X'),s.actions)
    def test_ap_empty_zero_never_recovers(self):
        s=Scenario(ap_empty=True);run,flow,error=self.runScenario(s)
        self.assertIsNone(error);self.assertCounters(run,0,0,0,0)
        self.assertEqual(s.actions,[('QUEST_READY','8'),('AP_EMPTY','Z')]);self.assertEqual(run.appleTotal,0)
    def test_appointment_one_stops_after_settlement(self):
        s=Scenario();s.limit=1;run,flow,error=self.runScenario(s,None)
        self.assertIsNone(error);self.assertCounters(run,1,1,1,0);self.assertEqual(s.state,'QUEST_READY')
    def test_appointment_multiple_stops_after_settlement(self):
        s=Scenario();s.limit=3;run,flow,error=self.runScenario(s,None)
        self.assertIsNone(error);self.assertCounters(run,3,3,3,0);self.assertEqual(s.state,'QUEST_READY')
    def test_defeat_records_no_revival_input(self):
        s=Scenario(defeated=True);run,flow,error=self.runScenario(s)
        self.assertIsNotNone(error);self.assertCounters(run,1,1,0,1);self.assertEqual(s.state,'DEFEATED')
        self.assertFalse(any(a[0]=='DEFEATED' for a in s.actions))
    def test_post_start_interruption_only_counts_started(self):
        run,flow,error=self.runScenario(Scenario(fail='during_battle'))
        self.assertIsNotNone(error);self.assertCounters(run,1,0,0,0)
    def test_progress_events_follow_settled_terminal_results(self):
        s=Scenario();run,flow,error=self.runScenario(s,3)
        self.assertEqual([e.completed for e in s.callbacks],[1,2,3])
        self.assertEqual([e.attempted for e in s.callbacks],[1,2,3])
    def test_trace_preserves_every_repeat_formation_path(self):
        run,flow,error=self.runScenario(Scenario(),3)
        names=[r.to_state for r in flow.trace.records if r.from_state!=r.to_state]
        self.assertEqual(names.count('FORMATION'),3);self.assertEqual(names.count('TURN_BEGIN'),3)

if __name__=='__main__':unittest.main()

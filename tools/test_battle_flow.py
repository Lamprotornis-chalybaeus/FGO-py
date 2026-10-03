"""Deterministic state/trace tests: no device, private fixture or wall-clock sleep."""
import sys,unittest,tempfile
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'FGO-py'))
from fgoBattleFlow import BattleFlow,BattleFlowState as S,observeBattleFlow,FlowTimeout,AmbiguousState
from fgoFlowTrace import FlowTrace

def frame(*states):
    from fgoBattleFlow import DETECTORS
    return SimpleNamespace(isLoading=lambda:'LOADING' in states,**{method:(lambda value=state in states:value) for method,state in DETECTORS})

class Clock:
    now=0
    def __call__(self):return self.now
    def sleep(self,seconds):self.now+=seconds
    def checkStop(self):pass
    def checkSuspend(self):pass

class ObservationTests(unittest.TestCase):
    def test_each_known_state_has_positive_evidence(self):
        from fgoBattleFlow import DETECTORS
        for method,name in DETECTORS:
            with self.subTest(state=name):
                obs=observeBattleFlow(frame(name));self.assertEqual(obs.state,S[name]);self.assertIn(method+'=True',obs.evidence)
    def test_unknown_explains_missing_evidence(self):
        self.assertIn('all known',observeBattleFlow(frame()).evidence[0])
    def test_continue_foreground_cannot_be_swallowed_by_friend(self):
        obs=observeBattleFlow(frame('CONTINUE','FRIEND','SKILL_CAST_FAILED'))
        self.assertEqual(obs.state,S.CONTINUE);self.assertTrue(any('ambiguous evidence' in e for e in obs.evidence))
    def test_conflicting_battle_and_formation_is_ambiguous(self):
        self.assertEqual(observeBattleFlow(frame('TURN_BEGIN','FORMATION')).state,S.AMBIGUOUS)
    def test_network_foreground_has_recorded_priority(self):
        self.assertEqual(observeBattleFlow(frame('NETWORK_ERROR','TURN_BEGIN')).state,S.NETWORK_ERROR)

class WaitTests(unittest.TestCase):
    def make(self,frames,root=None):
        clock=Clock();iterator=iter(frames);last=frames[-1]
        trace=FlowTrace(clock=clock,wall=lambda:1,root=root)
        flow=BattleFlow(lambda:next(iterator,last),clock,clock=clock,trace=trace)
        return flow,clock
    def test_delayed_frame_polling_uses_monotonic_deadline(self):
        flow,clock=self.make([frame()]*50+[frame('FRIEND')])
        self.assertEqual(flow.waitForFlowState({S.FRIEND},timeout=11,transition_name='friend').state,S.FRIEND)
        self.assertGreaterEqual(clock.now,9.9)
    def test_timeout_retains_last_input_and_expected(self):
        flow,clock=self.make([frame('FORMATION'),frame()])
        flow.observe();flow.action('start_quest',lambda:None)
        with self.assertRaisesRegex(FlowTimeout,'from=FORMATION expected=TURN_BEGIN.*last_input=start_quest'):
            flow.waitForFlowState({S.TURN_BEGIN},timeout=1,transition_name='start')
        self.assertGreaterEqual(clock.now,1)
    def test_trace_only_logs_changes_and_actions(self):
        flow,_=self.make([frame('FRIEND')]*5+[frame('FORMATION')])
        flow.observe();flow.action('choose_friend',lambda:None)
        flow.waitForFlowState({S.FORMATION},timeout=5,transition_name='friend exit',allowed_intermediate={S.FRIEND})
        self.assertEqual([(r.from_state,r.to_state,r.action) for r in flow.trace.records],[('UNKNOWN','FRIEND',''),('FRIEND','FRIEND','choose_friend'),('FRIEND','FORMATION','')])
    def test_ambiguous_state_stops_before_any_action(self):
        flow,_=self.make([frame('FORMATION','TURN_BEGIN')])
        with self.assertRaises(AmbiguousState):flow.observe()
    def test_failure_diagnostic_is_local_and_omits_unknown_frame(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as root:
            f=frame();f.im=np.full((720,1280,3),100,np.uint8)
            flow,_=self.make([f],root)
            with self.assertRaises(FlowTimeout):flow.waitForFlowState({S.FRIEND},timeout=.5,transition_name='unknown')
            files={p.name for p in Path(root).rglob('*') if p.is_file()}
            self.assertEqual(files,{'trace.json','summary.txt'})

if __name__=='__main__':unittest.main()

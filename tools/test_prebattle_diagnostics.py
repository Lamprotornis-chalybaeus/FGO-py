"""Synthetic diagnostics only: never publish a private game screenshot."""
import tempfile,unittest
from pathlib import Path
import numpy as np
from test_battle_flow import Clock,frame
from fgoBattleFlow import BattleFlowState as S,DETECTORS,observeBattleFlow
from fgoFlowTrace import FlowTrace

class PrebattleDiagnosticsTests(unittest.TestCase):
    def test_all_states_have_producers(self):
        produced={S[name] for _,name in DETECTORS}|{S.UNKNOWN,S.LOADING,S.AMBIGUOUS}
        self.assertEqual(set(S),produced)
        self.assertEqual(observeBattleFlow(frame('LOADING')).state,S.LOADING)
        self.assertEqual(observeBattleFlow(frame('FORMATION','TURN_BEGIN')).state,S.AMBIGUOUS)
    def test_exception_requires_formation_and_logical_start(self):
        for state,action in [('FRIEND','start_quest'),('FORMATION','choose_friend'),('UNKNOWN','start_quest')]:
            trace=FlowTrace();trace.record(state,action=action);trace.beginFormationStart()
            self.assertIsNone(trace.prebattle)
    def test_physical_input_preserves_logical_start(self):
        trace=FlowTrace();trace.record(S.FORMATION,action='start_quest');trace.record(S.FORMATION,action="press ' '")
        trace.beginFormationStart();self.assertIsNotNone(trace.prebattle)
        self.assertEqual(trace.last_input,'start_quest');self.assertEqual(trace.last_physical_input,"press ' '")
    def test_four_slots_only_and_freshness_metadata(self):
        clock=Clock();trace=FlowTrace(clock=clock);trace.record(S.FORMATION,action='start_quest');trace.beginFormationStart()
        detect=frame();detect.im=np.full((720,1280,3),100,np.uint8)
        for index in range(350):
            clock.now=index*.2;trace.formationSample(detect,S.UNKNOWN,clock.now,clock.now)
        trace.formationSample(detect,S.LOADING,clock.now,clock.now)
        self.assertEqual(len(trace.prebattle['frames']),4)
        self.assertLess(len(trace.prebattle['samples']),40)
        row=trace.prebattle['samples'][-1]
        self.assertTrue(row['identical_previous']);self.assertGreater(row['identical_seconds'],60)
        self.assertEqual(row['mean_brightness'],100)
    def test_local_capture_is_closed_after_success(self):
        with tempfile.TemporaryDirectory() as root:
            trace=FlowTrace(root=root);trace.record(S.FORMATION,action='start_quest');trace.beginFormationStart()
            detect=frame();detect.im=np.full((720,1280,3),100,np.uint8)
            trace.formationSample(detect,S.UNKNOWN,0,1);trace.endFormationStart()
            self.assertIsNone(trace.prebattle)
            self.assertEqual({p.name for p in Path(root).rglob('*.png')},{'first-unknown.png','last-unknown.png'})
    def test_other_positive_page_revokes_unknown_capture(self):
        trace=FlowTrace();trace.record(S.FORMATION,action='start_quest');trace.beginFormationStart()
        detect=frame();detect.im=np.full((720,1280,3),100,np.uint8)
        trace.formationSample(detect,S.NETWORK_ERROR,0,1)
        trace.formationSample(detect,S.UNKNOWN,1,2)
        self.assertFalse(trace.prebattle['frames'])
    def test_input_observer_spans_preparation_and_settlement_and_resets(self):
        from test_battle_cycle import Scenario,CycleTests
        from fgoAutomation import INPUT_OBSERVER,noteDeviceInput
        scenario=Scenario();original=scenario.press
        def press(key,**kwargs):noteDeviceInput('press '+repr(key));return original(key,**kwargs)
        scenario.press=press
        run,flow,error=CycleTests().runScenario(scenario)
        self.assertIsNone(error)
        physical=[r for r in flow.trace.records if r.action.startswith('press ')]
        self.assertEqual([r.to_state for r in physical],['QUEST_READY','FRIEND','FORMATION','BATTLE_RESULT','ADD_FRIEND','CONTINUE'])
        self.assertIsNone(INPUT_OBSERVER.get())

if __name__=='__main__':unittest.main()

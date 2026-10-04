import os,sys,unittest
from pathlib import Path
from unittest.mock import patch
APP=Path(__file__).resolve().parents[1]/'FGO-py';sys.path.insert(0,str(APP))
cwd=os.getcwd();os.chdir(APP)
try:import fgoKernel as kernel
finally:os.chdir(cwd)
from fgoBattleFlow import BattleFlow,BattleFlowState as S,FlowTimeout
from fgoFlowTrace import FlowTrace
from test_battle_flow import Clock,frame

class BattleWaitTests(unittest.TestCase):
    def flow(self,clock,reader):return BattleFlow(reader,clock,clock=clock,trace=FlowTrace(clock=clock))
    def test_unknown_battle_stops_by_wall_clock_not_fuse(self):
        clock=Clock();battle=kernel.Battle(turnClass=lambda:lambda n:None)
        battle.flow=self.flow(clock,lambda:frame());battle.unknownTimeout=1
        with patch.object(kernel,'schedule',clock),patch.object(kernel.fgoDevice.device,'perform') as inputs:
            with self.assertRaisesRegex(FlowTimeout,'battle progress'):battle()
        self.assertGreaterEqual(clock.now,1);inputs.assert_not_called()
    def test_total_deadline_stops_even_with_repeated_valid_turn_marker(self):
        clock=Clock();battle=kernel.Battle(turnClass=lambda:lambda n:None)
        battle.flow=self.flow(clock,lambda:frame('TURN_BEGIN'));battle.totalTimeout=1
        with patch.object(kernel,'schedule',clock):
            with self.assertRaisesRegex(FlowTimeout,'battle total'):battle()
        self.assertGreaterEqual(clock.now,1)
    def test_wrong_formation_never_runs_turn_ai(self):
        clock=Clock();turn=[];battle=kernel.Battle(turnClass=lambda:turn.append)
        battle.flow=self.flow(clock,lambda:frame('FORMATION'))
        with patch.object(kernel,'schedule',clock):
            with self.assertRaisesRegex(FlowTimeout,'UNEXPECTED battle state'):battle()
        self.assertEqual(turn,[])
    def test_long_valid_animation_then_result(self):
        clock=Clock();turns=[]
        def reader():return frame('TURN_BEGIN' if not turns else 'LOADING' if clock.now<20 else 'BATTLE_RESULT')
        battle=kernel.Battle(turnClass=lambda:turns.append);battle.flow=self.flow(clock,reader)
        with patch.object(kernel,'schedule',clock):self.assertTrue(battle())
        self.assertEqual(turns,[1]);self.assertGreaterEqual(clock.now,20)
    def test_skill_and_card_inputs_do_not_consume_the_unknown_wait_budget(self):
        # Real resume: ~36 seconds of legitimate inputs followed by animation.
        # The old clock expired 60 seconds after turn start, not 60 seconds
        # after input completion. No larger timeout or synthetic popup.
        clock=Clock();turns=[]
        def turn(n):turns.append(n);clock.now+=36
        def reader():return frame('TURN_BEGIN' if not turns else 'BATTLE_RESULT' if clock.now>=76 else 'UNKNOWN')
        battle=kernel.Battle(turnClass=lambda:turn);battle.flow=self.flow(clock,reader)
        with patch.object(kernel,'schedule',clock):self.assertTrue(battle())
        self.assertEqual(turns,[1]);self.assertGreaterEqual(clock.now,76)
    def test_input_completion_cannot_renew_the_whole_battle_hard_deadline(self):
        clock=Clock();turns=[]
        def turn(n):turns.append(n);clock.now+=36
        battle=kernel.Battle(turnClass=lambda:turn);battle.flow=self.flow(clock,lambda:frame('TURN_BEGIN'))
        battle.totalTimeout=30
        with patch.object(kernel,'schedule',clock):
            with self.assertRaisesRegex(FlowTimeout,'battle total'):battle()
        self.assertEqual(turns,[1])
    def test_skill_animation_wait_is_bounded(self):
        clock=Clock();flow=self.flow(clock,lambda:frame());token=kernel._activeBattleFlow.set(flow)
        try:
            with self.assertRaisesRegex(FlowTimeout,'normal skill cast'):kernel.waitForTurnBegin('normal skill cast',timeout=1)
            self.assertGreaterEqual(clock.now,1)
        finally:kernel._activeBattleFlow.reset(token)
    def test_skill_failed_modal_is_recovered_once_not_treated_as_ap(self):
        clock=Clock();states=['SKILL_CAST_FAILED'];flow=self.flow(clock,lambda:frame(states[0]));token=kernel._activeBattleFlow.set(flow)
        try:
            with patch.object(kernel.fgoDevice.device,'press',side_effect=lambda key:states.__setitem__(0,'TURN_BEGIN')) as press:
                kernel.waitForTurnBegin('master skill',timeout=1)
            press.assert_called_once_with('J')
            self.assertIn('skill_cast_failed_recover',[r.action for r in flow.trace.records])
        finally:kernel._activeBattleFlow.reset(token)
    def test_skill_wait_defeat_interrupts_before_next_ai_input(self):
        clock=Clock();flow=self.flow(clock,lambda:frame('DEFEATED'));token=kernel._activeBattleFlow.set(flow)
        try:
            with self.assertRaises(kernel.BattlePhaseEnded) as error:kernel.waitForTurnBegin('skill')
            self.assertEqual(error.exception.state,S.DEFEATED)
        finally:kernel._activeBattleFlow.reset(token)
    def test_skill_wait_cannot_exceed_whole_battle_deadline(self):
        clock=Clock();turns=[]
        def turn(n):
            turns.append(n);clock.now=.8
            kernel.waitForTurnBegin('nested skill',timeout=45)
        battle=kernel.Battle(turnClass=lambda:turn);battle.totalTimeout=1
        battle.flow=self.flow(clock,lambda:frame('TURN_BEGIN' if not turns else 'LOADING'))
        with patch.object(kernel,'schedule',clock):
            with self.assertRaises(FlowTimeout):battle()
        self.assertLess(clock.now,1.3);self.assertIsNone(battle.flow.deadline)
    def test_persistent_skill_modal_is_not_repeatedly_clicked(self):
        clock=Clock();flow=self.flow(clock,lambda:frame('SKILL_CAST_FAILED'));token=kernel._activeBattleFlow.set(flow)
        try:
            with patch.object(kernel.fgoDevice.device,'press') as press:
                with self.assertRaises(FlowTimeout):kernel.waitForTurnBegin('skill',timeout=1)
            press.assert_called_once_with('J')
        finally:kernel._activeBattleFlow.reset(token)
    def test_user_stop_checked_on_each_poll(self):
        class StoppedClock(Clock):
            def checkStop(self):
                if self.now>=.4:raise kernel.ScriptStop('Stopped')
        clock=StoppedClock();flow=self.flow(clock,lambda:frame())
        with self.assertRaisesRegex(kernel.ScriptStop,'Stopped'):
            flow.waitForFlowState({S.TURN_BEGIN},timeout=20,transition_name='stop test')
        self.assertLess(clock.now,1)

if __name__=='__main__':unittest.main()

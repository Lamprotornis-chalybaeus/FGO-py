"""Synthetic animation evidence; no game, private screenshot or real sleeps."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from test_battle_cycle import kernel
from test_battle_flow import Clock,frame
from fgoBattleFlow import BattleFlow,FlowTimeout
from fgoBattleProgress import BattleProgressTracker


class TrackerTests(unittest.TestCase):
    def setUp(self):self.clock=Clock();self.tracker=BattleProgressTracker(clock=self.clock);self.seq=0
    def observe(self,state='UNKNOWN',seconds=1,value=80,loading=None,sequence=None):
        self.clock.now+=seconds;self.seq+=1
        return self.tracker.observe(SimpleNamespace(state=SimpleNamespace(name=state),capture_sequence=sequence or self.seq),
            SimpleNamespace(im=np.full((720,1280,3),value,np.uint8),getLoadingProgressSignature=lambda:loading))
    def test_seventy_seconds_changing_unknown_then_next_turn(self):
        self.tracker.mark_turn_input_complete(1)
        for i in range(14):
            self.observe(seconds=5,value=80+(i%2)*80);self.assertFalse(self.tracker.stalled())
        self.observe('TURN_BEGIN');self.assertFalse(self.tracker.hard_expired())
    def test_unknown_loading_unknown_over_sixty(self):
        self.observe(seconds=20);self.observe('LOADING',seconds=35,loading='A')
        self.observe(seconds=30);self.observe('TURN_BEGIN',seconds=30)
        self.assertFalse(self.tracker.stalled());self.assertFalse(self.tracker.hard_expired())
    def test_loading_signature_renews_stall(self):
        self.observe('LOADING',loading='A')
        self.observe('LOADING',seconds=55,loading='B')
        self.clock.now+=55;self.assertFalse(self.tracker.stalled())
    def test_static_unknown_stalls(self):
        self.observe();self.observe(seconds=61)
        self.assertTrue(self.tracker.stalled())
    def test_animation_cannot_renew_phase_hard_deadline(self):
        self.tracker.mark_turn_input_complete(2)
        for i in range(37):self.observe(seconds=5,value=80+(i%2)*80)
        self.assertFalse(self.tracker.stalled());self.assertTrue(self.tracker.hard_expired())
    def test_duplicate_capture_cannot_renew_stall(self):
        self.observe(sequence=1);self.observe(seconds=61,value=200,sequence=1)
        self.assertTrue(self.tracker.stalled())
    def test_pixel_noise_is_not_progress(self):
        self.observe(value=80);self.observe(seconds=61,value=81)
        self.assertTrue(self.tracker.stalled())
    def test_input_complete_does_not_change_last_positive(self):
        self.observe('TURN_BEGIN');self.tracker.mark_turn_input_complete(3)
        self.assertEqual(self.tracker.snapshot()['last_positive_state'],'TURN_BEGIN')
        self.assertEqual(self.tracker.snapshot()['phase'],'WAIT_NEXT_TURN')


class BattleIntegrationTests(unittest.TestCase):
    def runBattle(self,*,duration=70,moving=True,loading=False,end='BATTLE_RESULT',total=1800):
        clock=Clock();turns=[];holder={}
        def read():
            name='TURN_BEGIN' if not turns else end if duration==0 or len(turns)>1 else 'TURN_BEGIN' if clock.now>=duration else 'LOADING' if loading and 25<=clock.now<45 else 'UNKNOWN'
            d=frame(name);d.im=np.full((720,1280,3),80+(int(clock.now)//5%2)*80 if moving else 80,np.uint8)
            d.getLoadingProgressSignature=lambda:int(clock.now)//5
            return d
        def turn(n):turns.append(n)
        battle=kernel.Battle(turnClass=lambda:turn);battle.totalTimeout=total
        battle.flow=BattleFlow(read,clock,clock=clock)
        with patch.object(kernel,'schedule',clock):
            try:result=battle();error=None
            except FlowTimeout as e:result=None;error=e
        return battle,turns,result,error,clock
    def test_long_animation_passes_without_duplicate_turn(self):
        battle,turns,result,error,clock=self.runBattle()
        self.assertEqual(turns,[1,2]);self.assertTrue(result);self.assertIsNone(error)
    def test_loading_resets_old_sixty_second_watchdog(self):
        self.assertIsNone(self.runBattle(moving=False,loading=True)[3])
    def test_static_scene_stalls_and_failure_names_actual_turn(self):
        battle,turns,result,error,clock=self.runBattle(duration=100,moving=False)
        self.assertIn('STALL battle progress',str(error));self.assertIn('turn=1',str(error))
        self.assertIn('phase=WAIT_NEXT_TURN',str(error));self.assertNotIn('last_input=start_quest',str(error))
    def test_moving_scene_hits_phase_hard_limit(self):
        self.assertIn('TIMEOUT battle phase',str(self.runBattle(duration=200)[3]))
    def test_total_deadline_survives_progress(self):
        self.assertIn('TIMEOUT',str(self.runBattle(duration=100,total=25)[3]))
        self.assertEqual(kernel.Battle.totalTimeout,1800)
    def test_result_directly_ends(self):
        battle,turns,result,error,clock=self.runBattle(duration=0)
        self.assertTrue(result);self.assertIsNone(error)
    def test_defeat_directly_ends(self):
        with patch.object(Clock,'checkDefeated',create=True):
            battle,turns,result,error,clock=self.runBattle(duration=0,end='DEFEATED')
        self.assertFalse(result);self.assertTrue(battle.defeated)

if __name__=='__main__':unittest.main()

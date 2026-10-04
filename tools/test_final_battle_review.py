"""Final review regression; synthetic structural frames, no private identities."""
import unittest
from unittest.mock import patch
import numpy as np
from test_battle_cycle import kernel
from test_battle_flow import Clock,frame
from fgoBattleFlow import BattleFlow,BattleCycle,BondResultEpisode,FlowTimeout
from fgoDetect import XDetectCN

class StableDepartureTests(unittest.TestCase):
    def runStates(self,states,nested=False):
        clock=Clock();iterator=iter(states);turns=[];holder={}
        def read():return frame(next(iterator,'BATTLE_RESULT'))
        def turn(n):
            turns.append(n)
            if nested:
                original=holder['battle'].flow.reader
                for state in ('UNKNOWN','UNKNOWN','TURN_BEGIN'):
                    holder['battle'].flow.reader=lambda:frame(state)
                    holder['battle'].flow.observe()
                holder['battle'].flow.reader=original
        battle=kernel.Battle(turnClass=lambda:turn);holder['battle']=battle
        battle.flow=BattleFlow(read,clock,clock=clock)
        with patch.object(kernel,'schedule',clock):result=battle()
        return turns,result
    def test_one_unknown_does_not_rearm(self):
        self.assertEqual(self.runStates(['TURN_BEGIN','UNKNOWN','TURN_BEGIN','BATTLE_RESULT']),( [1],True))
    def test_two_fresh_unknowns_rearm_even_with_identical_pixels(self):
        self.assertEqual(self.runStates(['TURN_BEGIN','UNKNOWN','UNKNOWN','TURN_BEGIN','BATTLE_RESULT']),([1,2],True))
    def test_loading_immediately_rearms(self):
        self.assertEqual(self.runStates(['TURN_BEGIN','LOADING','TURN_BEGIN','BATTLE_RESULT']),([1,2],True))
    def test_unknown_streak_resets_on_attack(self):
        self.assertEqual(self.runStates(['TURN_BEGIN','UNKNOWN','TURN_BEGIN','UNKNOWN','TURN_BEGIN','BATTLE_RESULT']),([1],True))
    def test_nested_unknowns_do_not_rearm(self):
        self.assertEqual(self.runStates(['TURN_BEGIN','TURN_BEGIN','BATTLE_RESULT'],nested=True),([1],True))
    def test_result_without_departure_ends(self):
        self.assertEqual(self.runStates(['TURN_BEGIN','BATTLE_RESULT']),([1],True))
    def test_defeat_without_departure_ends(self):
        with patch.object(Clock,'checkDefeated',create=True):
            self.assertEqual(self.runStates(['TURN_BEGIN','DEFEATED']),([1],False))
    def test_observation_sequence_counts_captures_not_different_pixels(self):
        clock=Clock();same=frame('UNKNOWN');flow=BattleFlow(lambda:same,clock,clock=clock)
        self.assertEqual([flow.observe().capture_sequence for _ in range(3)],[1,2,3])

class BondInstancesTests(unittest.TestCase):
    A=bytes([0])*2560
    B=bytes([1])*2560
    def settle(self,sequence,advance=None):
        clock=Clock();frames=iter(sequence);last=sequence[-1];inputs=[];state=[None]
        def read():
            page,signature=next(frames,last);state[0]=page
            d=frame(page if page in {'ADD_FRIEND','CONTINUE'} else 'BATTLE_RESULT')
            d.getBattleResultPage=lambda:page
            d._battleResultInstanceSignature=lambda:signature
            return d
        main=kernel.Main();main.press=lambda key:inputs.append((state[0],key))
        flow=BattleFlow(read,clock,clock=clock);error=None
        try:BattleCycle(main,flow).settleBattleResult()
        except FlowTimeout as e:error=e
        return inputs,error
    def tail(self):return [(p,None) for p in ('BOND','MASTER_EXP','REWARDS','ADD_FRIEND','CONTINUE')]
    def test_persistent_identical_overlay_one_input_then_timeout(self):
        inputs,error=self.settle([('BOND_LEVEL_UP',self.A)]*8)
        self.assertIsInstance(error,FlowTimeout);self.assertEqual(inputs,[('BOND_LEVEL_UP',' ')])
    def test_two_stable_instances_each_advance_once(self):
        inputs,error=self.settle([('BOND_LEVEL_UP',self.A)]*4+[('BOND_LEVEL_UP',self.B)]*4+self.tail())
        self.assertIsNone(error);self.assertEqual([p for p,k in inputs],['BOND_LEVEL_UP']*2+['BOND','MASTER_EXP','REWARDS','ADD_FRIEND'])
    def test_a_then_b_then_persistent_b_never_reclicks_b(self):
        inputs,error=self.settle([('BOND_LEVEL_UP',self.A)]*4+[('BOND_LEVEL_UP',self.B)]*8)
        self.assertIsInstance(error,FlowTimeout);self.assertEqual(inputs,[('BOND_LEVEL_UP',' ')]*2)
    def test_overlay_then_bond_retains_original_pages(self):
        inputs,error=self.settle([('BOND_LEVEL_UP',self.A)]*4+self.tail())
        self.assertIsNone(error);self.assertEqual([p for p,k in inputs],['BOND_LEVEL_UP','BOND','MASTER_EXP','REWARDS','ADD_FRIEND'])
    def test_oscillating_animation_does_not_create_new_instance(self):
        inputs,error=self.settle([('BOND_LEVEL_UP',self.A)]*4+[( 'BOND_LEVEL_UP',x) for x in [self.B,self.A]*5])
        self.assertIsInstance(error,FlowTimeout);self.assertEqual(inputs,[('BOND_LEVEL_UP',' ')])
    def test_minor_signature_noise_is_not_new_instance(self):
        noisy=bytes([1])*8+self.A[8:]
        inputs,error=self.settle([('BOND_LEVEL_UP',self.A)]*4+[('BOND_LEVEL_UP',noisy)]*8)
        self.assertIsInstance(error,FlowTimeout);self.assertEqual(inputs,[('BOND_LEVEL_UP',' ')])
    def test_missing_signature_fails_closed_without_click(self):
        inputs,error=self.settle([('BOND_LEVEL_UP',None)]*5)
        self.assertIsInstance(error,FlowTimeout);self.assertEqual(inputs,[])
    def test_signature_requires_positive_overlay(self):
        d=XDetectCN.__new__(XDetectCN);d.im=np.full((720,1280,3),225,np.uint8)
        d.getBattleResultPage=lambda:'BOND'
        self.assertIsNone(d._battleResultInstanceSignature())
    def test_signature_captures_only_fixed_overlay_region(self):
        d=XDetectCN.__new__(XDetectCN);d.im=np.full((720,1280,3),225,np.uint8)
        d.getBattleResultPage=lambda:'BOND_LEVEL_UP';a=d._battleResultInstanceSignature()
        d.im[:80]=0;self.assertEqual(a,d._battleResultInstanceSignature())
        d.im[350:570,660:1190]=0;self.assertNotEqual(a,d._battleResultInstanceSignature())
    def test_same_capture_cannot_confirm_three_frames(self):
        gate=BondResultEpisode();d=frame('BATTLE_RESULT');d._battleResultInstanceSignature=lambda:self.A
        self.assertEqual([gate.ready(d,1) for _ in range(4)],[False]*4)
        self.assertFalse(gate.ready(d,2));self.assertTrue(gate.ready(d,3))
    def test_unknown_capture_gap_breaks_instance_confirmation(self):
        gate=BondResultEpisode();d=frame('BATTLE_RESULT');d._battleResultInstanceSignature=lambda:self.A
        self.assertFalse(gate.ready(d,1));self.assertFalse(gate.ready(d,3))
        self.assertFalse(gate.ready(d,4));self.assertTrue(gate.ready(d,5))
    def test_instance_signature_is_not_logged(self):
        d=XDetectCN.__new__(XDetectCN);d.im=np.full((720,1280,3),225,np.uint8)
        d.getBattleResultPage=lambda:'BOND_LEVEL_UP'
        with self.assertNoLogs('fgo.Detect',level='DEBUG'):d._battleResultInstanceSignature()

if __name__=='__main__':unittest.main()

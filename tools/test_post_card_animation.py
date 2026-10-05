"""Synthetic frames derived from real long noble-chain timeout; no screenshots."""
import unittest
from unittest.mock import patch
import numpy
import test_battle_waits as waits
kernel=waits.kernel
from test_battle_flow import Clock,frame
from fgoBattleFlow import PostCardAnimationProgress,FlowTimeout

class AnimationTests(unittest.TestCase):
    def tracker(self,cards='867',enabled=True):
        a=PostCardAnimationProgress(enabled);a.input("press ' '")
        for c in cards:a.input('press '+repr(c))
        a.finish(0);return a
    def test_actual_noble_selection_required_and_first_three_only(self):
        self.assertFalse(self.tracker('123678').eligible)
        self.assertTrue(self.tracker().eligible)
        self.assertFalse(self.tracker(enabled=False).eligible)
        a=PostCardAnimationProgress(True);a.input("press '8'");a.finish(0)
        self.assertFalse(a.eligible)
    def test_two_material_fresh_changes_required_not_hash_only(self):
        a=self.tracker();dark=numpy.full((720,1280,3),80,dtype='uint8');bright=dark+100
        self.assertFalse(a.activity(dark,1));self.assertFalse(a.activity(bright,2))
        self.assertFalse(a.activity(dark,2)) # same acquisition cannot count
        self.assertTrue(a.activity(dark,3))
        self.assertFalse(a.activity(dark,4)) # static frame resets the streak
    def test_small_background_jitter_or_nonconsecutive_capture_never_renews(self):
        for jump in (False,True):
            a=self.tracker();im=numpy.full((720,1280,3),80,dtype='uint8')
            self.assertFalse(a.activity(im,1))
            other=im.copy();other[100:120,200:300]+=100
            self.assertFalse(a.activity(other,4 if jump else 2))
            self.assertFalse(a.activity(im,5 if jump else 3))
    def battle(self,*,active=True,noble=True,resultAt=None):
        clock=Clock();turns=[]
        def turn(n):
            turns.append(n)
            observer=kernel.INPUT_OBSERVER.get();observer("press ' '")
            for c in ('867' if noble else '123'):observer('press '+repr(c))
        def reader():
            state='TURN_BEGIN' if not turns else 'BATTLE_RESULT' if resultAt is not None and clock.now>=resultAt else 'UNKNOWN'
            d=frame(state);d.im=numpy.full((720,1280,3),80+100*(round(clock.now/.2)%2 if active else 0),dtype='uint8')
            return d
        b=kernel.Battle(turnClass=lambda:turn);b.flow=waits.BattleWaitTests().flow(clock,reader)
        b.allowAnimationProgress=True;b.unknownTimeout=1;b.animationHardTimeout=3
        return b,clock,turns
    def test_material_animation_can_outlast_stall_without_extra_turn(self):
        b,clock,turns=self.battle(resultAt=2)
        with patch.object(kernel,'schedule',clock):self.assertTrue(b())
        self.assertEqual(turns,[1]);self.assertGreaterEqual(clock.now,2)
    def test_animation_cannot_renew_hard_deadline(self):
        b,clock,turns=self.battle()
        with patch.object(kernel,'schedule',clock),self.assertRaisesRegex(FlowTimeout,'animation hard'):b()
        self.assertLess(clock.now,3.3);self.assertEqual(turns,[1])
    def test_static_noble_or_unplanned_normal_cards_keep_stall_timeout(self):
        for args in ({'active':False},{'noble':False}):
            b,clock,turns=self.battle(**args)
            with patch.object(kernel,'schedule',clock),self.assertRaisesRegex(FlowTimeout,'battle progress'):b()
            self.assertLess(clock.now,1.3);self.assertEqual(turns,[1])

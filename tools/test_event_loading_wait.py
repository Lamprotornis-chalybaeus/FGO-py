"""Read-only event loading waits; synthetic pixels, no game operations."""
import unittest
from unittest.mock import Mock,patch
import numpy
import test_event_cycle as fixtures
from test_battle_flow import Clock
ec=fixtures.ec

class LoadingWaitTests(unittest.TestCase):
    def scenario(self,mode,*,arrive=None,hard=180,deadline=None):
        clock=Clock();runner=ec.EventRunner(ec.EventResourcePolicy(),clock=clock,ledger=Mock());runner.touch=Mock()
        image=numpy.full((720,1280,3),0 if mode=='dark' else 80,dtype='uint8')
        d=Mock(im=image);d.isLoading.return_value=mode=='labels'
        d.getLoadingProgressSignature.side_effect=lambda:str(int(clock.now//2))
        runner.read=Mock(side_effect=lambda:(d,[],'story' if arrive is not None and clock.now>=arrive else 'unknown'))
        with patch.object(ec,'schedule',clock):
            try:result=runner.wait({'story'},timeout=30,loadingHardTimeout=hard,deadline=deadline);error=None
            except ec.FlowTimeout as e:result=None;error=e
        runner.touch.assert_not_called();return clock,runner,result,error
    def test_first_real_dark_loading_can_complete_after_thirty_seconds(self):
        clock,runner,result,error=self.scenario('dark',arrive=45)
        self.assertIsNone(error);self.assertEqual(result[2],'story');self.assertLess(clock.now,60)
        self.assertEqual(runner.ledger.append.call_count,1)
    def test_identical_black_frames_do_not_renew_sixty_second_stall(self):
        clock,_,_,error=self.scenario('dark',arrive=65)
        self.assertIsNotNone(error);self.assertLess(clock.now,60.3)
    def test_only_positive_local_loading_progress_can_extend_to_hard_cap(self):
        clock,_,result,error=self.scenario('labels',arrive=80,hard=90)
        self.assertIsNone(error);self.assertEqual(result[2],'story')
        clock,_,_,error=self.scenario('labels',hard=90)
        self.assertIsNotNone(error);self.assertLess(clock.now,90.3)
    def test_unknown_bright_background_keeps_original_timeout(self):
        clock,_,_,error=self.scenario('unproven',arrive=40)
        self.assertIsNotNone(error);self.assertLess(clock.now,30.3)
    def test_parent_deadline_is_never_extended_by_loading(self):
        clock,_,_,error=self.scenario('dark',arrive=45,deadline=40)
        self.assertIsNotNone(error);self.assertLess(clock.now,40.3)

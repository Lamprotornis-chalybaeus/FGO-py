"""Verified terminal tap can load >25 seconds; still no repeated input."""
import runpy,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
env=runpy.run_path(str(Path(__file__).with_name('test_standard_terminal.py')));nav=env['nav']
class TerminalLoadingTests(unittest.TestCase):
    def frame(self,value=255,network=False):return SimpleNamespace(im=np.full((720,1280,3),value,np.uint8),isNetworkError=lambda:network)
    def guard(self,deadline=120):
        guard=nav.NavigationGuard('返回终端');guard.deadline=deadline;guard.current_state='NORMALIZE';return guard
    def test_loading_dark_frame_is_only_wait_evidence(self):
        frame=self.frame(0);frame.im[690:695,1200:1240]=255
        self.assertTrue(nav._terminalLoadingFrameCN(frame))
        frame.im[120:550,300:1000]=80
        self.assertFalse(nav._terminalLoadingFrameCN(frame))
    def test_real_home_after_25_seconds_is_accepted_without_second_tap(self):
        clock=[0];frames=[self.frame(0),self.frame()]
        def read(*args):clock[0]=30 if len(frames)==2 else 42;return frames.pop(0)
        with patch.object(nav.time,'monotonic',side_effect=lambda:clock[0]),patch.object(nav,'Detect',side_effect=read),patch.object(nav,'labels',return_value=[]) as labels,patch.object(nav,'safeMenuPageCN',return_value='ROOT_CATEGORY'),patch.object(nav,'terminalHomeCN',return_value=True),patch.object(nav.fgoDevice.device,'touch') as touch:
            self.assertEqual(nav.waitTerminalHomeCN(self.guard()).im.mean(),255)
        labels.assert_called_once();touch.assert_not_called()
    def test_black_loading_does_not_spend_cpu_on_ocr_and_times_out(self):
        clock=[0]
        def read(*args):clock[0]+=20;return self.frame(0)
        with patch.object(nav.time,'monotonic',side_effect=lambda:clock[0]),patch.object(nav,'Detect',side_effect=read),patch.object(nav,'labels') as labels,patch.object(nav.fgoDevice.device,'touch') as touch:
            with self.assertRaisesRegex(nav.ScriptStop,'transition timeout'):nav.waitTerminalHomeCN(self.guard(180))
        labels.assert_not_called();touch.assert_not_called();self.assertLessEqual(clock[0],100)
    def test_shorter_parent_budget_is_not_extended(self):
        clock=[0];guard=self.guard(15)
        def read(*args):clock[0]=20;return self.frame(0)
        with patch.object(nav.time,'monotonic',side_effect=lambda:clock[0]),patch.object(nav,'Detect',side_effect=read),patch.object(nav,'labels') as labels:
            with self.assertRaisesRegex(nav.ScriptStop,'timeout'):nav.waitTerminalHomeCN(guard)
        labels.assert_not_called();self.assertEqual(guard.deadline,15)
    def test_modal_stops_before_accepting_background_home(self):
        with patch.object(nav,'Detect',return_value=self.frame()),patch.object(nav,'labels',return_value=[]),patch.object(nav,'safeMenuPageCN',return_value='UNSAFE_MODAL'),patch.object(nav,'terminalHomeCN') as home,patch.object(nav.fgoDevice.device,'touch') as touch:
            with self.assertRaisesRegex(nav.ScriptStop,'UNSAFE_MODAL'):nav.waitTerminalHomeCN(self.guard(float('inf')))
        home.assert_not_called();touch.assert_not_called()
    def test_network_error_is_not_confirmed(self):
        with patch.object(nav,'Detect',return_value=self.frame(network=True)),patch.object(nav,'labels',return_value=[]),patch.object(nav,'safeMenuPageCN',return_value='UNKNOWN'),patch.object(nav,'terminalHomeCN') as home,patch.object(nav.fgoDevice.device,'touch') as touch:
            with self.assertRaisesRegex(nav.ScriptStop,'网络错误'):nav.waitTerminalHomeCN(self.guard(float('inf')))
        home.assert_not_called();touch.assert_not_called()
    def test_stop_request_interrupts_loading_before_capture(self):
        with patch.object(nav.schedule,'checkStop',side_effect=nav.ScriptStop('Stop Command Effected')),patch.object(nav,'Detect') as capture:
            with self.assertRaisesRegex(nav.ScriptStop,'Stop Command Effected'):nav.waitTerminalHomeCN(self.guard(float('inf')))
        capture.assert_not_called()
    def test_header_without_directory_cannot_become_home(self):
        clock=[0]
        def read(*args):clock[0]+=30;return self.frame()
        with patch.object(nav.time,'monotonic',side_effect=lambda:clock[0]),patch.object(nav,'Detect',side_effect=read),patch.object(nav,'labels',return_value=[]),patch.object(nav,'safeMenuPageCN',return_value='ROOT_CATEGORY'),patch.object(nav,'terminalHomeCN',return_value=False),patch.object(nav.fgoDevice.device,'touch') as touch:
            with self.assertRaisesRegex(nav.ScriptStop,'transition timeout'):nav.waitTerminalHomeCN(self.guard(180))
        touch.assert_not_called()
    def test_invalid_capture_dimensions_stop(self):
        frame=self.frame(0);frame.im=frame.im[:360]
        with patch.object(nav,'Detect',return_value=frame),patch.object(nav,'labels') as labels:
            with self.assertRaisesRegex(nav.ScriptStop,'截图尺寸'):nav.waitTerminalHomeCN(self.guard(float('inf')))
        labels.assert_not_called()
if __name__=='__main__':unittest.main()

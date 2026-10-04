"""Bounded recovery and menu-only performance guards, with no device."""
import runpy,unittest
from pathlib import Path
from unittest.mock import patch,Mock
env=runpy.run_path(str(Path(__file__).with_name('test_gui_navigation.py')))
daily=env['daily'];Frame=env['FakeDetect']
class RepositionTests(unittest.TestCase):
    def entry(self):return daily.DailyQuestEntry('未来的新挑战 特级','unknown','unknown','',(0,940,250))
    def test_recovery_uses_fresh_frame_and_moves_back_into_forward_overlap(self):
        old,new=Frame(),Frame();entry=self.entry()
        with patch.object(daily,'_settledDailyEntriesAt',side_effect=daily.ScriptStop('标题未通过双重校验')),patch.object(daily,'_isDailyPage',return_value=True),patch.object(daily,'_scrollbar',return_value=(200,250)),patch.object(daily,'_swipe',return_value=(new,True)) as swipe,patch.object(daily,'_dailyEntriesAt',return_value=[entry]) as read:
            self.assertEqual(daily._observeDailyScanPage(old,80),(new,[entry]))
        swipe.assert_called_once_with(old,True,60);read.assert_called_once_with(new,80)
    def test_reverse_recovery_moves_toward_previously_scanned_bottom(self):
        frame=Frame()
        with patch.object(daily,'_settledDailyEntriesAt',side_effect=daily.ScriptStop('标题未通过双重校验')),patch.object(daily,'_isDailyPage',return_value=True),patch.object(daily,'_scrollbar',return_value=(200,250)),patch.object(daily,'_swipe',return_value=(frame,True)) as swipe,patch.object(daily,'_dailyEntriesAt',return_value=[self.entry()]):daily._observeDailyScanPage(frame,80,True)
        swipe.assert_called_once_with(frame,False,60)
    def test_unresolved_after_two_moves_stops_without_partial_publication(self):
        frame=Frame()
        with patch.object(daily,'_settledDailyEntriesAt',side_effect=daily.ScriptStop('标题未通过双重校验')),patch.object(daily,'_isDailyPage',return_value=True),patch.object(daily,'_scrollbar',return_value=(200,250)),patch.object(daily,'_swipe',return_value=(frame,True)) as swipe,patch.object(daily,'_dailyEntriesAt',side_effect=daily.ScriptStop('标题未通过双重校验')),patch.object(daily.fgoDevice.device,'touch') as touch:
            with self.assertRaisesRegex(daily.ScriptStop,'换位复核仍未通过'):daily._observeDailyScanPage(frame)
        self.assertEqual(swipe.call_count,2);touch.assert_not_called()
    def test_changed_page_never_swipes(self):
        with patch.object(daily,'_settledDailyEntriesAt',side_effect=daily.ScriptStop('标题未通过双重校验')),patch.object(daily,'_isDailyPage',return_value=False),patch.object(daily,'_swipe') as swipe:
            with self.assertRaisesRegex(daily.ScriptStop,'页面已变化'):daily._observeDailyScanPage(Frame())
        swipe.assert_not_called()
    def test_changed_page_after_move_refuses_an_ocr_result(self):
        frame=Frame()
        with patch.object(daily,'_settledDailyEntriesAt',side_effect=daily.ScriptStop('标题未通过双重校验')),patch.object(daily,'_isDailyPage',side_effect=[True,False]),patch.object(daily,'_scrollbar',return_value=(200,250)),patch.object(daily,'_swipe',return_value=(frame,True)),patch.object(daily,'_dailyEntriesAt') as read:
            with self.assertRaisesRegex(daily.ScriptStop,'页面已变化'):daily._observeDailyScanPage(frame)
        read.assert_not_called()
    def test_cancel_or_transport_error_is_not_recovered(self):
        for reason in ('Stop Command Effected','ADB disconnected','not 1280x720'):
            with self.subTest(reason=reason),patch.object(daily,'_settledDailyEntriesAt',side_effect=daily.ScriptStop(reason)),patch.object(daily,'_swipe') as swipe:
                with self.assertRaisesRegex(daily.ScriptStop,reason):daily._observeDailyScanPage(Frame())
            swipe.assert_not_called()
    def test_fast_top_drag_still_proves_endpoint(self):
        frame=Frame();android=Mock(spec=daily.fgoDevice.Android);android.name='127.0.0.1:5555'
        with patch.object(daily.XDetect,'region','CN'),patch.object(daily.fgoDevice.device,'I',android),patch.object(daily,'Detect',return_value=frame),patch.object(daily,'_isDailyPage',return_value=True),patch.object(daily,'_scrollbar',side_effect=[(400,450),(99,149),(99,149)]),patch.object(daily,'_menuSwipe') as drag,patch.object(daily,'_swipe',return_value=(frame,False)) as swipe,patch.object(daily.schedule,'sleep'):
            self.assertEqual(daily._scrollToTop(),(frame,True))
        drag.assert_called_once_with((1258,425),(1258,100));swipe.assert_called_once()
    def test_fast_top_drag_changed_page_stops(self):
        android=Mock(spec=daily.fgoDevice.Android);android.name='device'
        with patch.object(daily.XDetect,'region','CN'),patch.object(daily.fgoDevice.device,'I',android),patch.object(daily,'Detect',return_value=Frame()),patch.object(daily,'_isDailyPage',side_effect=[True,False]),patch.object(daily,'_scrollbar',return_value=(400,450)),patch.object(daily,'_menuSwipe'),patch.object(daily,'_swipe') as swipe,patch.object(daily.schedule,'sleep'):
            with self.assertRaisesRegex(daily.ScriptStop,'页面已变化'):daily._scrollToTop()
        swipe.assert_not_called()
    def test_recovery_at_endpoint_requires_returning_to_that_endpoint(self):
        from daily_index_test_support import World,indexed
        with World().patched() as w:
            real=w.observe;moved=[False]
            def observe(d,n):
                if d.top>=534 and not moved[0]:
                    moved[0]=True;w.top=520;d=w.capture()
                return real(d,n)
            with patch.object(daily,'_observeDailyScanPage',side_effect=observe):result=daily.scanDailyQuestsCN()
        self.assertTrue(moved[0]);self.assertTrue(result['reachedEnd']);self.assertEqual(w.top,99)

if __name__=='__main__':unittest.main()

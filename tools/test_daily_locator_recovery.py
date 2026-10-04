"""Shared normalization and known-target alignment safety; no game input."""
import runpy,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,Mock
import numpy as np
env=runpy.run_path(str(Path(__file__).with_name('test_gui_navigation.py')))
daily=env['daily'];Frame=env['FakeDetect']
import fgoNavigation as nav

class OpenDailyTests(unittest.TestCase):
    def route(self,state):
        with patch.object(daily.XDetect,'region','CN'),patch.object(daily,'Detect',return_value=Frame()),patch.object(nav,'labels',return_value=[]),patch.object(nav,'safeMenuPageCN',return_value=state),patch.object(daily,'confirmedDailyPageCN',return_value=False),patch.object(daily,'_waitDailyNavigationCN'),patch.object(nav,'normalizeToTerminalCN') as normalize,patch.object(daily,'_openDailyFromTerminalCN',return_value={'type':'DailyPage'}) as openPage:
            self.assertEqual(daily.openDailyPageCN(),{'type':'DailyPage'})
        normalize.assert_called_once();openPage.assert_called_once()
    def test_support_page_uses_shared_normalization(self):self.route('FRIEND')
    def test_my_room_uses_shared_normalization(self):self.route('MENU_PAGE')
    def test_confirmed_daily_never_goes_to_terminal(self):
        with patch.object(daily.XDetect,'region','CN'),patch.object(daily,'Detect',return_value=Frame()),patch.object(nav,'labels',return_value=[]),patch.object(nav,'safeMenuPageCN',return_value='DAILY'),patch.object(daily,'confirmedDailyPageCN',return_value=True),patch.object(nav,'normalizeToTerminalCN') as normalize,patch.object(daily,'_openDailyFromTerminalCN') as openPage:
            daily.openDailyPageCN()
        normalize.assert_not_called();openPage.assert_not_called()
    def test_modal_over_daily_is_rejected_by_shared_guard(self):
        with patch.object(daily.XDetect,'region','CN'),patch.object(daily,'Detect',return_value=Frame()),patch.object(nav,'labels',return_value=[]),patch.object(nav,'safeMenuPageCN',return_value='UNSAFE_MODAL'),patch.object(daily,'confirmedDailyPageCN',return_value=False),patch.object(nav,'normalizeToTerminalCN',side_effect=daily.ScriptStop('unsafe modal')),patch.object(daily,'_openDailyFromTerminalCN') as openPage:
            with self.assertRaisesRegex(daily.ScriptStop,'unsafe modal'):daily.openDailyPageCN()
        openPage.assert_not_called()
    def test_unknown_normalization_failure_cannot_open_gate(self):
        with patch.object(daily.XDetect,'region','CN'),patch.object(daily,'Detect',return_value=Frame()),patch.object(nav,'labels',return_value=[]),patch.object(nav,'safeMenuPageCN',return_value='UNKNOWN'),patch.object(daily,'confirmedDailyPageCN',return_value=False),patch.object(daily,'_waitDailyNavigationCN'),patch.object(nav,'normalizeToTerminalCN',side_effect=daily.ScriptStop('UNKNOWN')),patch.object(daily,'_openDailyFromTerminalCN') as openPage:
            with self.assertRaisesRegex(daily.ScriptStop,'UNKNOWN'):daily.openDailyPageCN()
        openPage.assert_not_called()

class DailyLocatorTests(unittest.TestCase):
    def entry(self,y=185,title='每日替换 暗之修炼场 超级'):return daily.DailyQuestEntry(title,'training','超级','',(0,844,y))
    def test_search_uses_verified_overlapping_scan_stride(self):
        a,b=Frame(),Frame();entry=self.entry()
        with patch.object(daily.XDetect,'region','CN'),patch.object(daily,'openDailyPageCN') as opening,patch.object(daily,'_dailyLocatorFrameCN'),patch.object(daily,'_scrollToTop',return_value=(a,True)),patch.object(daily,'_observeDailyScanPage',side_effect=[(a,[]),(b,[entry])]),patch.object(daily,'_scrollbar',return_value=(200,249)),patch.object(daily,'_swipe',return_value=(b,True)) as swipe,patch.object(daily.fgoDevice.device,'touch') as touch:
            self.assertEqual(daily.gotoDailyEntry(entry)['position'],(844,185))
        opening.assert_called_once();swipe.assert_called_once_with(a,False,280);touch.assert_not_called()
    def test_lost_alignment_restores_known_overlap_instead_of_skipping_target(self):
        a,b,c,d,e=[Frame() for _ in range(5)];wanted=self.entry();seen=self.entry(270)
        with patch.object(daily.XDetect,'region','CN'),patch.object(daily,'openDailyPageCN'),patch.object(daily,'_dailyLocatorFrameCN'),patch.object(daily,'_scrollToTop',return_value=(a,True)),patch.object(daily,'_observeDailyScanPage',return_value=(a,[seen])) as search,patch.object(daily,'_dailyEntriesAt',side_effect=[[],[],[],[wanted]]),patch.object(daily,'Detect',side_effect=[b,c,d]),patch.object(daily.schedule,'sleep'),patch.object(daily,'_scrollbar',return_value=(200,249)),patch.object(daily,'_menuSwipe') as align,patch.object(daily,'_swipe',return_value=(e,True)) as restore,patch.object(daily.fgoDevice.device,'touch') as touch:
            self.assertEqual(daily.gotoDailyEntry(wanted)['position'],(844,185))
        search.assert_called_once();align.assert_called_once_with((950,420),(950,335));restore.assert_called_once_with(d,True,60);touch.assert_not_called()
    def test_recovery_never_infers_requested_title_from_other_card(self):
        wrong=self.entry(title='每日替换 暗之修炼场 极级');frame=Frame()
        with patch.object(daily,'_dailyLocatorFrameCN'),patch.object(daily,'_dailyEntriesAt',return_value=[wrong]) as reads,patch.object(daily,'Detect',return_value=frame),patch.object(daily.schedule,'sleep'),patch.object(daily,'_scrollbar',return_value=(200,249)),patch.object(daily,'_swipe',return_value=(frame,True)) as restore:
            with self.assertRaisesRegex(daily.ScriptStop,'未继续滚向末端'):daily._reacquireDailyTargetCN(frame,self.entry(),float('inf'))
        self.assertEqual(reads.call_count,5);self.assertEqual(restore.call_count,2)
        self.assertTrue(all(c.args[1:] == (True,60) for c in restore.call_args_list))
    def test_duplicate_target_stops_before_alignment(self):
        frame=Frame();wanted=self.entry()
        with patch.object(daily.XDetect,'region','CN'),patch.object(daily,'openDailyPageCN'),patch.object(daily,'_dailyLocatorFrameCN'),patch.object(daily,'_scrollToTop',return_value=(frame,True)),patch.object(daily,'_observeDailyScanPage',return_value=(frame,[wanted,self.entry(370)])),patch.object(daily,'_scrollbar',return_value=(200,249)),patch.object(daily,'_menuSwipe') as swipe:
            with self.assertRaisesRegex(daily.ScriptStop,'重复标题'):daily.gotoDailyEntry(wanted)
        swipe.assert_not_called()
    def test_bottom_without_real_target_stops_without_tapping(self):
        frame=Frame()
        with patch.object(daily.XDetect,'region','CN'),patch.object(daily,'openDailyPageCN'),patch.object(daily,'_dailyLocatorFrameCN'),patch.object(daily,'_scrollToTop',return_value=(frame,True)),patch.object(daily,'_observeDailyScanPage',return_value=(frame,[])),patch.object(daily,'_scrollbar',return_value=(525,575)),patch.object(daily.fgoDevice.device,'touch') as touch,patch.object(daily,'_swipe') as swipe:
            with self.assertRaisesRegex(daily.ScriptStop,'列表末端'):daily.gotoDailyEntry(self.entry())
        touch.assert_not_called();swipe.assert_not_called()
    def test_deadline_stops_recovery_before_read_or_swipe(self):
        with patch.object(daily,'_dailyEntriesAt') as read,patch.object(daily,'_swipe') as swipe:
            with self.assertRaisesRegex(daily.ScriptStop,'复核超时'):daily._reacquireDailyTargetCN(Frame(),self.entry(),0)
        read.assert_not_called();swipe.assert_not_called()

class LocatorPageSafetyTests(unittest.TestCase):
    def frame(self,network=False):return SimpleNamespace(im=np.zeros((720,1280,3),np.uint8),isNetworkError=lambda:network)
    def test_network_error_is_not_confirmed(self):
        with patch.object(daily,'confirmedDailyPageCN',return_value=True),patch.object(nav,'labels',return_value=[]),patch.object(nav,'safeMenuPageCN',return_value='DAILY'):
            with self.assertRaisesRegex(daily.ScriptStop,'网络错误'):daily._dailyLocatorFrameCN(self.frame(True))
    def test_wrong_size_is_rejected(self):
        frame=self.frame();frame.im=frame.im[:360]
        with self.assertRaisesRegex(daily.ScriptStop,'尺寸异常'):daily._dailyLocatorFrameCN(frame)
    def test_header_cannot_override_modal(self):
        with patch.object(daily,'confirmedDailyPageCN',return_value=False),patch.object(nav,'labels',return_value=[]),patch.object(nav,'safeMenuPageCN',return_value='UNSAFE_MODAL'):
            with self.assertRaisesRegex(daily.ScriptStop,'危险状态'):daily._dailyLocatorFrameCN(self.frame())
    def test_stop_is_obeyed_before_ocr(self):
        with patch.object(daily.schedule,'checkStop',side_effect=daily.ScriptStop('Stop Command Effected')),patch.object(daily,'_isDailyPage') as header:
            with self.assertRaisesRegex(daily.ScriptStop,'Stop Command'):daily._dailyLocatorFrameCN(self.frame())
        header.assert_not_called()

class NeighbourCropTests(unittest.TestCase):
    def entry(self,title,y):return daily.DailyQuestEntry(title,'unknown','unknown','',(0,947,y))
    def test_a3_a5_interpolate_a4_but_require_real_title_and_ap(self):
        entries=[self.entry('挑战A3',135),self.entry('挑战A5',509)]
        with patch.object(daily.OCR.EN,'ocr_single_line',return_value=('AP40',.99)) as ap,patch.object(daily,'_readDailyTitle',return_value='新挑战 特级') as read:
            found=daily._recoverDailyNeighborsCN(Frame(),entries,[],7)
        self.assertEqual(read.call_count,1);self.assertEqual(read.call_args.args[1],322);ap.assert_called_once()
        self.assertEqual([(e.title,e.discovered_position) for e in found],[('新挑战 特级',(7,947,322))])
    def test_missing_below_one_title_uses_measured_ap_spacing(self):
        entries=[self.entry('挑战A3',150)]
        with patch.object(daily,'_readDailyTitle',return_value='真实的新名称 超级') as read:
            found=daily._recoverDailyNeighborsCN(Frame(),entries,[225,412])
        self.assertEqual(read.call_count,1);self.assertEqual(read.call_args.args[1],337);self.assertEqual(found[0].title,'真实的新名称 超级')
    def test_missing_above_one_title_uses_measured_ap_spacing(self):
        with patch.object(daily,'_readDailyTitle',return_value='真实挑战A4') as read:
            found=daily._recoverDailyNeighborsCN(Frame(),[self.entry('挑战A5',337)],[225,412])
        self.assertEqual(read.call_count,1);self.assertEqual(read.call_args.args[1],150);self.assertEqual(found[0].title,'真实挑战A4')
    def test_no_title_consensus_cannot_invent_a4(self):
        with patch.object(daily,'_readDailyTitle',return_value=None):
            self.assertEqual(daily._recoverDailyNeighborsCN(Frame(),[self.entry('挑战A3',150)],[225,412]),[])
    def test_missing_ap_cannot_invent_a4(self):
        with patch.object(daily.OCR.EN,'ocr_single_line',return_value=('任意文字',.99)),patch.object(daily,'_readDailyTitle') as read:
            self.assertEqual(daily._recoverDailyNeighborsCN(Frame(),[self.entry('挑战A3',135),self.entry('挑战A5',509)],[]),[])
        read.assert_not_called()
    def test_single_anchor_without_measured_spacing_is_not_extrapolated(self):
        with patch.object(daily,'_readDailyTitle') as read:
            self.assertEqual(daily._recoverDailyNeighborsCN(Frame(),[self.entry('挑战A3',150)],[]),[])
        read.assert_not_called()
    def test_shared_scan_and_locator_reader_use_neighbour_recovery(self):
        self.assertIn('_recoverDailyNeighborsCN',daily._dailyEntriesAt.__code__.co_names)
        self.assertIn('_observeDailyScanPage',daily._gotoDailyEntrySequential.__code__.co_names)
if __name__=='__main__':unittest.main()

"""Offline menu false-positive and safe recovery regressions; no private assets."""
import unittest,runpy
from pathlib import Path
from unittest.mock import patch
import numpy as np
env=runpy.run_path(str(Path(__file__).with_name('test_gui_navigation.py')))
from fgoDetect import XDetectCN,XDetectBase,IMG
import fgoNavigation as nav
daily=env['daily'];item=env['item'];Frame=env['FakeDetect']

class ContinueFeatureTests(unittest.TestCase):
    def frame(self,background=255):
        frame=object.__new__(XDetectCN);frame.im=np.full((720,1280,3),background,np.uint8);return frame
    def test_white_background_reproduces_mask_match_but_not_dialog(self):
        frame=self.frame()
        self.assertTrue(frame._compare(frame.tmpl.BATTLECONTINUE,(455,85,835,144)))
        self.assertFalse(frame.isBattleContinue())
    def test_exact_dark_title_remains_continuation(self):
        frame=self.frame(50);pixels=frame.tmpl.BATTLECONTINUE[0];h,w=pixels.shape[:2]
        frame.im[85:85+h,455:455+w]=pixels;self.assertTrue(frame.isBattleContinue())
    def test_title_is_checked_only_inside_original_region(self):
        frame=self.frame();pixels=frame.tmpl.BATTLECONTINUE[0];h,w=pixels.shape[:2]
        frame.im[200:200+h,455:455+w]=pixels;self.assertFalse(frame.isBattleContinue())
    def test_other_regions_keep_original_method(self):
        frame=object.__new__(XDetectBase)
        with patch.object(frame,'_compare',return_value=True) as compare:self.assertTrue(frame.isBattleContinue())
        compare.assert_called_once_with(IMG.BATTLECONTINUE,(704,530,976,618))
    def test_real_confirmation_flag_still_blocks_before_daily_classification(self):
        from types import SimpleNamespace
        with patch.object(nav,'classify') as classify:
            self.assertEqual(nav.safeMenuPageCN(SimpleNamespace(isBattleContinue=lambda:True),[]),'UNSAFE_MODAL');classify.assert_not_called()

class RefreshEntryTests(unittest.TestCase):
    def test_confirmed_daily_refresh_reuses_page_without_terminal_input(self):
        with patch.object(daily.XDetect,'region','CN'),patch.object(daily,'Detect',return_value=Frame()),patch.object(nav,'labels',return_value=[]),patch.object(nav,'safeMenuPageCN',return_value='DAILY'),patch.object(daily,'_isDailyPage',return_value=True),patch.object(daily,'scanDailyQuestsCN',return_value={'complete':True}) as scan,patch.object(nav,'normalizeToTerminalCN') as normalize,patch.object(daily,'openDailyPageCN') as openPage:
            self.assertEqual(daily.refreshDailyQuestsCN(),{'complete':True})
        scan.assert_called_once();normalize.assert_not_called();openPage.assert_not_called()
    def test_modal_over_daily_background_cannot_use_direct_scan(self):
        with patch.object(daily.XDetect,'region','CN'),patch.object(daily,'Detect',return_value=Frame()),patch.object(nav,'labels',return_value=[]),patch.object(nav,'safeMenuPageCN',return_value='UNSAFE_MODAL'),patch.object(nav,'normalizeToTerminalCN',side_effect=daily.ScriptStop('unsafe modal')),patch.object(daily,'scanDailyQuestsCN') as scan:
            with self.assertRaisesRegex(daily.ScriptStop,'unsafe modal'):daily.refreshDailyQuestsCN()
        scan.assert_not_called()
    def test_other_page_uses_shared_normalization(self):
        with patch.object(daily.XDetect,'region','CN'),patch.object(daily,'Detect',return_value=Frame()),patch.object(nav,'labels',return_value=[]),patch.object(nav,'safeMenuPageCN',return_value='GATE'),patch.object(nav,'normalizeToTerminalCN') as normalize,patch.object(daily,'openDailyPageCN') as openPage,patch.object(daily,'scanDailyQuestsCN',return_value={'complete':True}):
            daily.refreshDailyQuestsCN()
        normalize.assert_called_once();openPage.assert_called_once()
    def test_daily_classification_alone_does_not_bypass_header_proof(self):
        with patch.object(daily.XDetect,'region','CN'),patch.object(daily,'Detect',return_value=Frame()),patch.object(nav,'labels',return_value=[]),patch.object(nav,'safeMenuPageCN',return_value='DAILY'),patch.object(daily,'_isDailyPage',return_value=False),patch.object(nav,'normalizeToTerminalCN') as normalize,patch.object(daily,'openDailyPageCN'),patch.object(daily,'scanDailyQuestsCN'):
            daily.refreshDailyQuestsCN()
        normalize.assert_called_once()

class ScanRecoveryTests(unittest.TestCase):
    def test_actual_cn_assassin_training_title_is_accepted_after_two_reads(self):
        title='每日替换暗之修炼场初级'
        spans=[item(title,31,135,240,20),item('AP10',33,205,65,28)]
        with patch.object(daily.OCR.ZHS,'detect_and_ocr',return_value=spans),patch.object(daily.OCR.ZHS,'ocr_single_line',return_value=(title,.98)):
            entries=daily._dailyEntriesAt(Frame())
        self.assertEqual([e.title for e in entries],['每日替换 暗之修炼场 初级'])
        self.assertEqual(entries[0].quest_type,'training')
    def test_new_training_name_is_accepted_only_from_its_real_card(self):
        title='每日替换月之修炼场初级'
        spans=[item(title,31,135,240,20),item('AP10',33,205,65,28)]
        with patch.object(daily.OCR.ZHS,'detect_and_ocr',return_value=spans),patch.object(daily.OCR.ZHS,'ocr_single_line',return_value=(title,.98)):
            entries=daily._dailyEntriesAt(Frame())
        self.assertEqual([e.title for e in entries],['每日替换 月之修炼场 初级'])
    def test_unclassified_future_title_has_no_category_gate(self):
        title='新的每日挑战特别篇'
        spans=[item(title,31,135,240,20),item('AP10',33,205,65,28)]
        with patch.object(daily.OCR.ZHS,'detect_and_ocr',return_value=spans),patch.object(daily.OCR.ZHS,'ocr_single_line',return_value=(title,.98)):
            entries=daily._dailyEntriesAt(Frame())
        self.assertEqual(entries[0].title,title)
        self.assertEqual((entries[0].quest_type,entries[0].difficulty),('unknown','unknown'))
    def test_future_name_without_ap_cannot_be_published(self):
        title='月之修炼场初级'
        with patch.object(daily.OCR.ZHS,'detect_and_ocr',return_value=[item(title,31,135,240,20)]),patch.object(daily.OCR.EN,'ocr_single_line',return_value=('',0)),patch.object(daily.OCR.ZHS,'ocr_single_line') as read:
            self.assertEqual(daily._dailyEntriesAt(Frame()),[])
        read.assert_not_called()
    def test_ambiguous_names_are_never_repaired_from_whitelist(self):
        with patch.object(daily.OCR.ZHS,'ocr_single_line',side_effect=[('术之修炼场上级',.98),('水之修炼场上级',.98),('木之修炼场上级',.98),('土之修炼场上级',.98),('月之修炼场上级',.98)]):
            self.assertIsNone(daily._readDailyTitle(Frame().im,250))
    def test_crop_majority_preserves_arbitrary_new_name(self):
        with patch.object(daily.OCR.ZHS,'ocr_single_line',side_effect=[('月之修炼场上级',.98),('且之修炼场上级',.98),('月之修炼场上级',.98)]):
            self.assertEqual(daily._readDailyTitle(Frame().im,250),'月之修炼场 上级')
    def test_title_reads_change_vertical_context_instead_of_only_upscaling(self):
        with patch.object(daily.OCR.ZHS,'ocr_single_line',return_value=('月之修炼场上级',.98)) as read:
            daily._readDailyTitle(Frame().im,250)
        self.assertEqual([c.args[0].shape[:2] for c in read.call_args_list],[(20,345),(32,345),(28,345)])
    def test_missing_glyph_recovery_still_requires_a_second_complete_read(self):
        reads=[('弓之修炼场上级',.95),('之修炼场上级',.98),('之修炼场上级',.97),('弓之修炼场上级',.9),('引之修炼场上级',.9)]
        with patch.object(daily.OCR.ZHS,'ocr_single_line',side_effect=reads):
            self.assertEqual(daily._readDailyTitle(Frame().im,250),'弓之修炼场 上级')
    def test_two_conflicting_pairs_never_publish_a_title(self):
        reads=[('月之修炼场上级',.95),('土之修炼场上级',.98),('星之修炼场上级',.97),('月之修炼场上级',.9),('土之修炼场上级',.9)]
        with patch.object(daily.OCR.ZHS,'ocr_single_line',side_effect=reads):
            self.assertIsNone(daily._readDailyTitle(Frame().im,250))
    def test_status_labels_cannot_become_quests(self):
        for title in ('推荐等级极级','关卡举办时间剩余1日','AP40','每日任务','初级','之修炼场超级'):
            with self.subTest(title=title):self.assertFalse(daily._valid_daily_title(title))
    def test_separator_typography_does_not_create_phantom_quest(self):
        titles=['每日替换搜集种火<枪·暗篇>超级','每日替换搜集种火<枪暗篇>超级','每日替换搜集种火〈枪・暗篇〉超级']
        entries=[daily.DailyQuestEntry(t,'ember','超级','',(0,940,150)) for t in titles]
        self.assertEqual(len(daily.deduplicateDailyEntries(entries)),1)
        self.assertEqual(daily._format_title(titles[1],'超级'),'每日替换 搜集种火<枪·暗篇> 超级')
    def test_class_order_and_difficulty_remain_distinct(self):
        names=['搜集种火<枪·暗篇>超级','搜集种火<暗·枪篇>超级','搜集种火<枪·暗篇>极级']
        self.assertEqual(len({daily._title_key(t) for t in names}),3)
    def test_ocr_retry_observes_without_any_input(self):
        entry=object();frame=Frame()
        with patch.object(daily,'_dailyEntriesAt',side_effect=[daily.ScriptStop('标题未通过双重校验'),[entry]]) as read,patch.object(daily,'Detect',return_value=frame),patch.object(daily,'_isDailyPage',return_value=True),patch.object(daily.schedule,'sleep'),patch.object(daily.fgoDevice.device,'touch') as touch,patch.object(daily,'_menuSwipe') as swipe:
            self.assertEqual(daily._settledDailyEntriesAt(frame,7),[entry])
        self.assertEqual(read.call_count,2);touch.assert_not_called();swipe.assert_not_called()
    def test_repeated_title_failure_never_returns_partial_list(self):
        with patch.object(daily,'_dailyEntriesAt',side_effect=daily.ScriptStop('标题未通过双重校验')) as read,patch.object(daily,'Detect',return_value=Frame()),patch.object(daily,'_isDailyPage',return_value=True),patch.object(daily.schedule,'sleep'),patch.object(daily.fgoDevice.device,'touch') as touch:
            with self.assertRaises(daily.ScriptStop):daily._settledDailyEntriesAt(Frame())
        self.assertEqual(read.call_count,3);touch.assert_not_called()
    def test_changed_page_during_retry_refuses(self):
        with patch.object(daily,'_dailyEntriesAt',side_effect=daily.ScriptStop('标题未通过双重校验')),patch.object(daily,'Detect',return_value=Frame()),patch.object(daily,'_isDailyPage',return_value=False),patch.object(daily.schedule,'sleep'):
            with self.assertRaisesRegex(daily.ScriptStop,'页面已变化'):daily._settledDailyEntriesAt(Frame())
    def test_non_title_errors_are_not_retried(self):
        with patch.object(daily,'_dailyEntriesAt',side_effect=daily.ScriptStop('not 1280x720')) as read,patch.object(daily,'Detect') as capture:
            with self.assertRaises(daily.ScriptStop):daily._settledDailyEntriesAt(Frame())
        self.assertEqual(read.call_count,1);capture.assert_not_called()
    def test_scan_swipe_overlaps_verified_title_band(self):
        with patch.object(daily,'_menuSwipe') as swipe,patch.object(daily.schedule,'sleep'),patch.object(daily,'Detect',return_value=Frame()):
            daily._swipe(Frame(),False,280)
        swipe.assert_called_once_with((950,490),(950,210))
        self.assertLess(280,520-130)
    def test_default_menu_swipe_coordinates_unchanged(self):
        with patch.object(daily,'_menuSwipe') as swipe,patch.object(daily.schedule,'sleep'),patch.object(daily,'Detect',return_value=Frame()):
            daily._swipe(Frame(),True)
        swipe.assert_called_once_with((950,240),(950,420))
    def test_progressing_large_list_can_complete_after_old_180_second_budget(self):
        frame=Frame();entry=daily.DailyQuestEntry('搜集种火 极级','ember','极级','',(0,940,150))
        with patch.object(daily.XDetect,'region','CN'),patch.object(daily,'Detect',return_value=frame),patch.object(daily,'_isDailyPage',return_value=True),patch.object(daily,'_scrollToTop',return_value=(frame,True)),patch.object(daily,'_dailyEntriesAt',return_value=[entry]),patch.object(daily,'_swipe',return_value=(frame,True)),patch.object(daily,'_scrollbar',side_effect=[(462,575),(462,575),(462,575),(99,213),(99,213),(99,213)]),patch.object(daily.time,'monotonic',side_effect=[0,200,200,400,450]):
            result=daily.scanDailyQuestsCN()
        self.assertTrue(result['complete']);self.assertTrue(result['reachedEnd']);self.assertTrue(result['restoredTop'])

if __name__=='__main__':unittest.main()

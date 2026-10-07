"""Synthetic page structure and cache lifetime regressions; no private images."""
import unittest
from unittest.mock import patch,Mock
from types import SimpleNamespace
from pathlib import Path
import numpy as np
from daily_index_test_support import World,q,indexed
import fgoNavigation as nav

def label(text,x,y,w=140,h=24):return nav.Label(text,(x,y,x+w,y+h),.99)

class Page:
    def __init__(self,rows=(),main=True):
        self.im=np.zeros((720,1280,3),np.uint8)
        self.im[100:150,1253:1264]=255
        self.rows=list(rows);self.main=main
        for name in ('isTurnBegin','isBattleFinished','isBattleDefeated','isApEmpty','isBattleContinue','isSkillCastFailed','isAddFriend','isSummonContinue','isBattleFormation','isChooseFriend','isWeeklyMission','isNetworkError'):
            setattr(self,name,lambda:False)
    def isMainInterface(self):return self.main
    def _crop(self,r):return self.im[r[1]:r[3],r[0]:r[2]]

CLOSE=label('关闭',70,25,80,35)
MENU=label('菜单',1148,633,77,40)
DAILY=[CLOSE,label('每日任务',1060,5,215,55),label('未来新的试炼 特级',780,140,310),label('AP10',795,215,70),MENU]
ROOT=[label('通知',70,25,80,35),label('迦勒底之门',730,375,220,45),label('每日任务',1000,10,210,55),label('活动举办时间 剩余10日',960,277,250),MENU]
GATE=[CLOSE,label('迦勒底之门',1000,5,274,55),label('每日任务',920,216,168,45),MENU]

class DailyPageProofTests(unittest.TestCase):
    def confirmed(self,p):
        with patch.object(q,'_isDailyPage',return_value=True),patch.object(nav,'labels',side_effect=lambda d:d.rows):
            return q.confirmedDailyPageCN(p)
    def test_full_joint_page_proof_succeeds(self):self.assertTrue(self.confirmed(Page(DAILY)))
    def test_false_daily_words_on_terminal_event_banner_are_not_ready(self):
        p=Page(ROOT)
        self.assertFalse(self.confirmed(p))
        with patch.object(q,'_isDailyPage',return_value=True):self.assertEqual(nav.classify(p,p.rows),'ROOT_CATEGORY')
        self.assertEqual(q.dailyNavigationAction([(i.text,i.box) for i in ROOT]),('gate',(840,397)))
    def test_header_and_close_without_actual_card_ap_are_not_daily(self):
        self.assertFalse(self.confirmed(Page(DAILY[:2]+[MENU])))
    def test_no_unique_scrollbar_is_not_daily(self):
        p=Page(DAILY);p.im[100:150,1253:1264]=0
        self.assertFalse(self.confirmed(p))
    def test_ambiguous_scrollbars_are_not_daily(self):
        p=Page(DAILY);p.im[300:350,1253:1264]=255
        self.assertFalse(self.confirmed(p))
    def test_unpaired_ap_cannot_prove_list_structure(self):
        rows=[i for i in DAILY if i.text!='AP10']+[label('AP10',795,420,70)]
        self.assertFalse(self.confirmed(Page(rows)))
    def test_non_main_or_wrong_dimensions_cannot_be_ready(self):
        self.assertFalse(self.confirmed(Page(DAILY,False)))
        p=Page(DAILY);p.im=p.im[:360];self.assertFalse(self.confirmed(p))
    def test_modal_over_real_daily_structure_is_rejected(self):
        self.assertFalse(self.confirmed(Page(DAILY+[label('是否开始关卡？',430,300,420),label('取消',430,500,80)])))

class ContextCacheTests(unittest.TestCase):
    def preserve(self,state):
        with World().patched() as w:
            index=w.calibrated().build();indexed.remember(index)
            indexed._anchors={'real':{'thumb_top':120,'thumb_bottom':160,'local_y':185}}
            before=indexed.cachePath().read_bytes();anchors=dict(indexed._anchors)
            with patch.object(q,'confirmedDailyPageCN',return_value=False),patch.object(q,'_dailyNavigationStateCN',return_value=state):
                with self.assertRaises(indexed.DailyContextError):indexed.safe(w.capture())
            self.assertIs(indexed.currentIndex(),index)
            self.assertEqual(indexed.cachePath().read_bytes(),before)
            self.assertEqual(indexed._anchors,anchors);w.touch.assert_not_called()
    def test_root_does_not_invalidate(self):self.preserve('ROOT_CATEGORY')
    def test_gate_does_not_invalidate(self):self.preserve('GATE')
    def test_event_does_not_invalidate(self):self.preserve('EVENT')
    def test_menu_does_not_invalidate(self):self.preserve('MENU_PAGE')
    def test_unknown_transition_does_not_invalidate(self):self.preserve('UNKNOWN')
    def test_confirmed_daily_geometry_mismatch_hard_invalidates(self):
        with World().patched() as w:
            index=w.calibrated().build();indexed.remember(index);w.height=80
            result=indexed.locate(indexed.entryFromRecord(index.entries[12]),index,indexed.DailyScanMetrics(),float('inf'))
            self.assertIsNone(result);self.assertIsNone(indexed.currentIndex())
            self.assertIn('scrollbar geometry changed',indexed.cachePath().read_text())
    def test_confirmed_daily_order_mismatch_hard_invalidates(self):
        with World().patched() as w:
            index=w.calibrated().build();indexed.remember(index)
            rows=[w.entry(12,185),w.entry(11,370)]
            with patch.object(indexed,'localEntries',return_value=rows):
                self.assertIsNone(indexed.locate(indexed.entryFromRecord(index.entries[12]),index,indexed.DailyScanMetrics(),float('inf')))
            self.assertIsNone(indexed.currentIndex());self.assertIn('title order conflict',indexed.cachePath().read_text())
    def test_normalization_journey_preserves_existing_index_mode(self):
        with World().patched() as w:
            index=w.calibrated().build();indexed.remember(index);before=indexed.cachePath().read_bytes()
            def normalize():
                for state in ('ROOT_CATEGORY','GATE','UNKNOWN'):
                    indexed.dailyContextLost('current page is '+state)
            with patch.object(q,'openDailyPageCN',side_effect=normalize),patch.object(q,'_gotoDailyEntrySequential',side_effect=AssertionError('no fallback')):
                result=indexed.goto(indexed.entryFromRecord(index.entries[12]))
            self.assertEqual(result['mode'],'index');self.assertEqual(result['metrics']['fallbacks'],0)
            self.assertEqual(indexed.cachePath().read_bytes(),before)
    def test_directory_scroll_under_metrics_never_uses_daily_index_guard(self):
        p=Page(GATE[:2]+[MENU]);before=p.im.copy();after=Page(GATE[:2]+[MENU])
        with indexed.measuring(indexed.DailyScanMetrics()),patch.object(nav,'labels',return_value=p.rows),patch.object(nav,'safeMenuPageCN',return_value='GATE'),patch.object(q,'_dailyCapture',return_value=after),patch.object(q,'_swipe_input_only') as swipe,patch.object(indexed,'safe',side_effect=AssertionError('not DAILY')),patch.object(indexed,'invalidateIndex') as invalidate:
            q._swipe(p,True)
        swipe.assert_called_once();invalidate.assert_not_called()

class ScanLeadingEdgeTests(unittest.TestCase):
    def test_quantized_top_without_first_full_card_is_normalized_once(self):
        with World(75).patched() as w:
            w.top=100
            d,entries=indexed._readScanTop(w.capture(),0,float('inf'))
            self.assertEqual(entries[0].title,w.entry(0,140).title)
            self.assertEqual(w.swipes,[(True,100)]);w.touch.assert_not_called()
    def test_missing_leading_title_never_publishes_complete_second_card_as_first(self):
        with World(75).patched() as w:
            w.missing.add(0)
            with self.assertRaisesRegex(q.ScriptStop,'第一张完整卡片'):
                indexed._readScanTop(w.capture(),0,float('inf'))
            self.assertEqual(w.swipes,[(True,100),(True,100)]);self.assertIsNone(indexed.currentIndex())
    def test_visible_first_card_needs_no_extra_top_input(self):
        with World(75).patched() as w:
            _,entries=indexed._readScanTop(w.capture(),0,float('inf'))
            self.assertEqual(entries[0].title,w.entry(0,140).title);self.assertEqual(w.swipes,[])
    def test_mid_list_is_not_allowed_to_use_top_edge_normalization(self):
        with World(75).patched() as w:
            w.top=200
            with self.assertRaisesRegex(q.ScriptStop,'顶部滚动条'):
                indexed._readScanTop(w.capture(),0,float('inf'))
            self.assertEqual(w.swipes,[])

class GenericMenuTests(unittest.TestCase):
    def test_top_bar_counters_do_not_compete_with_right_aligned_header(self):
        p=Page([label('未来普通功能页',950,8,310,50),label('0/75',959,7,66,33),label('3/10',965,49,59,30),MENU])
        with patch.object(nav.OCR.ZHS,'ocr_single_line',return_value=('未来普通功能页',.99)):
            self.assertEqual(nav.safeMenuPageCN(p,p.rows),'MENU_PAGE')
    def test_future_menu_title_uses_structure_not_allowlist(self):
        p=Page([label('未来普通功能页',950,8,310,50),MENU])
        with patch.object(nav.OCR.ZHS,'ocr_single_line',return_value=('未来普通功能页',.99)):
            self.assertEqual(nav.safeMenuPageCN(p,p.rows),'MENU_PAGE')
    def test_header_without_unique_menu_is_not_generic_safe_page(self):
        p=Page([label('未来普通功能页',950,8,310,50)])
        self.assertFalse(nav.confirmedMenuPageCN(p,p.rows))
        p.rows+=[MENU,MENU]
        with self.assertRaises(nav.ScriptStop):nav.confirmedMenuPageCN(p,p.rows)
    def test_header_disagreement_does_not_allow_unknown_page_click(self):
        p=Page([label('未来普通功能页',950,8,310,50),MENU])
        with patch.object(nav.OCR.ZHS,'ocr_single_line',side_effect=[('未来普通功能页',.99),('另一页',.99)]):
            self.assertFalse(nav.confirmedMenuPageCN(p,p.rows))
    def test_formation_and_modal_cannot_use_generic_menu_proof(self):
        p=Page([label('未来普通功能页',950,8,310,50),MENU]);p.isBattleFormation=lambda:True
        self.assertFalse(nav.confirmedMenuPageCN(p,p.rows))
        p.isBattleFormation=lambda:False;p.rows.append(label('是否购买？',450,300,400))
        self.assertFalse(nav.confirmedMenuPageCN(p,p.rows))

class TerminalDirectoryProofTests(unittest.TestCase):
    def test_weak_menu_promoted_only_by_two_scale_local_agreement(self):
        span=SimpleNamespace(text='菜单',score=.792,box=[[1148,633],[1225,633],[1225,673],[1148,673]])
        for answers,expected in ([('通知',.99)]*2+[('菜单',.99)]*2,True),([('通知',.99)]*2+[('菜单',.99),('另一页',.99)],False):
            with patch.object(nav.OCR.ZHS,'detect_and_ocr',return_value=[span]),patch.object(nav.OCR.ZHS,'ocr_single_line',side_effect=answers):
                rows=nav.labels(Page())
            self.assertEqual(bool(nav.unique(rows,'菜单',(1080,590,1280,710))),expected)
    def test_menu_text_margin_recovers_tight_crop_without_threshold_change(self):
        span=SimpleNamespace(text='菜单',score=.792,box=[[1148,633],[1225,633],[1225,673],[1148,673]])
        page=Page();original=page._crop
        with patch.object(page,'_crop',side_effect=original) as crop,patch.object(nav.OCR.ZHS,'detect_and_ocr',return_value=[span]),patch.object(nav.OCR.ZHS,'ocr_single_line',side_effect=[('通知',.99)]*2+[('菜单',.991),('菜单',.990)]):
            rows=nav.labels(page)
        crop.assert_any_call((1138,625,1238,680))
        self.assertGreater(nav.unique(rows,'菜单',(1080,590,1280,710)).score,.98)
    def test_weak_known_title_needs_two_agreeing_local_scales(self):
        rows=[label('通知',70,25,80,35),nav.Label('冬木',(863,224,952,275),.805),MENU]
        p=Page(rows)
        with patch.object(nav.OCR.ZHS,'ocr_single_line',return_value=('冬木',.99)) as read:
            self.assertTrue(nav.terminalHomeCN(p,rows))
        self.assertEqual(read.call_count,2)
    def test_disagreement_or_weak_local_title_does_not_prove_terminal(self):
        rows=[label('通知',70,25,80,35),nav.Label('冬木',(863,224,952,275),.805),MENU]
        for answers in ([('冬木',.99),('另一页',.99)],[('冬木',.84),('冬木',.99)]):
            with patch.object(nav.OCR.ZHS,'ocr_single_line',side_effect=answers):
                self.assertFalse(nav.terminalHomeCN(Page(rows),rows))
    def test_notification_alone_is_not_terminal_home(self):
        rows=[label('通知',70,25,80,35),MENU]
        self.assertFalse(nav.terminalHomeCN(Page(rows),rows))

class VerifiedTransitionTests(unittest.TestCase):
    def test_more_than_three_unknown_frames_wait_read_only_after_verified_tap(self):
        frames=[Page([],False) for _ in range(5)]+[Page(DAILY)]
        with patch.object(q,'_dailyCapture',side_effect=frames),patch.object(nav,'labels',side_effect=lambda d:d.rows),patch.object(q,'_navigationLabels',return_value=[]),patch.object(q,'_dailyNavigationStateCN',side_effect=lambda d:'DAILY' if d.rows else 'UNKNOWN'),patch.object(q,'_isDailyPage',return_value=True),patch.object(q.fgoDevice.device,'touch') as touch:
            result=q._waitDailyNavigationCN(nav.NavigationGuard('DAILY',30),'DAILY')
        self.assertIs(result,frames[-1]);touch.assert_not_called()
    def test_transition_has_hard_budget_and_preserves_index(self):
        clock=[0];p=Page([],False)
        def capture(*a):clock[0]+=5;return p
        with patch.object(q.time,'monotonic',side_effect=lambda:clock[0]),patch.object(q,'_dailyCapture',side_effect=capture),patch.object(q,'confirmedDailyPageCN',return_value=False),patch.object(q.fgoDevice.device,'touch') as touch,patch.object(indexed,'invalidateIndex') as invalidate:
            with self.assertRaisesRegex(q.ScriptStop,'超时'):q._waitDailyNavigationCN(nav.NavigationGuard('DAILY',30),'DAILY',10)
        self.assertLessEqual(clock[0],10);touch.assert_not_called();invalidate.assert_not_called()
    def test_caller_requires_fresh_daily_proof_after_candidate_returns(self):
        p=Page(ROOT)
        with patch.object(q.XDetect,'region','CN'),patch.object(q,'_dailyCapture',return_value=p),patch.object(q,'confirmedDailyPageCN',return_value=False),patch.object(nav,'normalizeToTerminalCN'),patch.object(q,'_openDailyFromTerminalCN',return_value={'type':'DailyPage'}),patch.object(q,'_waitDailyNavigationCN',side_effect=q.ScriptStop('not actually DAILY')) as proof:
            with self.assertRaisesRegex(q.ScriptStop,'not actually DAILY'):q.openDailyPageCN()
        proof.assert_called_once()

if __name__=='__main__':unittest.main()

"""Fixed labels observed on real CN screens; no private screenshot fixtures."""
import unittest
from unittest.mock import patch
from test_battle_cycle import kernel
from fgoDetect import XDetectCN,OCR
from fgoBattleFlow import observeBattleFlow,BattleFlowState as S

class CNResultPageTests(unittest.TestCase):
    def detect(self,labels):
        d=XDetectCN.__new__(XDetectCN)
        d._crop=lambda rect:rect
        d._compare=lambda *a,**k:False
        self.labels=labels
        return d
    def read(self,crop):return self.labels.get(crop,('',0))
    def test_real_bond_page_is_terminal_without_drop_marker(self):
        d=self.detect({(490,20,775,110):('战斗结果',.994),(480,625,815,690):('请点击游戏界面',.978),(75,160,420,215):('与从者的牵',.907)})
        with patch.object(OCR.ZHS,'ocr_single_line',side_effect=self.read):
            self.assertEqual(d.getBattleResultPage(),'BOND');self.assertTrue(d.isBattleFinished())
    def test_real_master_exp_page_is_distinct(self):
        d=self.detect({(490,20,775,110):('战斗结果',.994),(480,625,815,690):('请点击游戏界面',.978),(635,175,860,245):('√获得经验值',.862)})
        with patch.object(OCR.ZHS,'ocr_single_line',side_effect=self.read):self.assertEqual(d.getBattleResultPage(),'MASTER_EXP')
    def test_missing_footer_or_unknown_panel_never_authorizes_result_input(self):
        for footer in [('',0),('请点击游戏界面',.99)]:
            d=self.detect({(490,20,775,110):('战斗结果',.99),(480,625,815,690):footer})
            with patch.object(OCR.ZHS,'ocr_single_line',side_effect=self.read):self.assertIsNone(d.getBattleResultPage())
    def test_real_bright_loading_page_has_positive_producer(self):
        d=self.detect({(520,160,760,225):('小贴士',.939),(900,665,1060,716):('加载中',.858)})
        with patch.object(OCR.ZHS,'ocr_single_line',side_effect=self.read):self.assertTrue(d.isLoading())
    def test_background_animation_without_both_loading_labels_is_not_loading(self):
        d=self.detect({(520,160,760,225):('小贴士',.99)})
        with patch.object(OCR.ZHS,'ocr_single_line',side_effect=self.read):self.assertFalse(d.isLoading())
    def test_loading_progress_signature_ignores_background_animation(self):
        import numpy as np
        d=XDetectCN.__new__(XDetectCN);d.im=np.zeros((720,1280,3),np.uint8)
        with patch.object(d,'isLoading',return_value=True):
            before=d.getLoadingProgressSignature();d.im[:400]=255
            self.assertEqual(before,d.getLoadingProgressSignature())
            d.im[600:660,1150:1200]=255
            self.assertNotEqual(before,d.getLoadingProgressSignature())

class ResultTransitionTests(unittest.TestCase):
    def runPages(self,persistent=False):
        from test_battle_flow import Clock,frame
        from fgoBattleFlow import BattleFlow,BattleCycle,FlowTimeout
        from fgoFlowTrace import FlowTrace
        clock=Clock();pages=['BOND','MASTER_EXP','REWARDS','ADD_FRIEND','CONTINUE'];index=[0];inputs=[]
        def read():
            page=pages[index[0]];d=frame(page if page in {'ADD_FRIEND','CONTINUE'} else 'BATTLE_RESULT')
            d.getBattleResultPage=lambda page=page:page
            return d
        def press(key):
            inputs.append(key)
            if not persistent:index[0]+=1
        flow=BattleFlow(read,clock,clock=clock,trace=FlowTrace(clock=clock));main=kernel.Main();main.press=press
        error=None
        try:BattleCycle(main,flow).settleBattleResult()
        except FlowTimeout as e:error=e
        return flow,inputs,error
    def test_every_positive_result_page_gets_one_input(self):
        flow,inputs,error=self.runPages()
        self.assertIsNone(error);self.assertEqual(inputs,[' ',' ',' ','X'])
        pages=[e for r in flow.trace.records if not r.action for e in r.evidence if e.startswith('result_page=')]
        self.assertEqual(pages,['result_page=BOND','result_page=MASTER_EXP','result_page=REWARDS'])
    def test_persistent_same_page_times_out_without_reclick(self):
        flow,inputs,error=self.runPages(True)
        self.assertIsNotNone(error);self.assertEqual(inputs,[' '])

if __name__=='__main__':unittest.main()

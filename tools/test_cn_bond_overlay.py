"""Regression from local CN bond-level-up OCR; no private pixels/identifiers."""
import unittest
from unittest.mock import patch
from test_battle_cycle import kernel
from test_battle_flow import Clock,frame
from fgoDetect import XDetectCN,OCR
from fgoBattleFlow import BattleFlow,BattleCycle,FlowTimeout

class BondOverlayTests(unittest.TestCase):
    labels={(490,20,775,110):('战斗结果',.994),(480,625,815,690):('请点击游戏界面',.955),
        (75,160,420,215):('与从老春',.693),(460,85,1260,230):('牵纤等级提升',.906),
        (630,275,1100,345):('与从者的牵纤加深了',.857)}
    def page(self,labels):
        d=XDetectCN.__new__(XDetectCN);d._crop=lambda rect:rect;d._compare=lambda *a,**k:False
        with patch.object(OCR.ZHS,'ocr_single_line',side_effect=lambda r:labels.get(r,('',0))):
            page=d.getBattleResultPage();finished=d.isBattleFinished()
        return page,finished
    def test_real_observed_overlay_is_a_distinct_terminal_page(self):
        self.assertEqual(self.page(self.labels),('BOND_LEVEL_UP',True))
    def test_banner_without_fixed_overlay_label_is_not_terminal(self):
        labels=dict(self.labels);labels.pop((630,275,1100,345))
        self.assertEqual(self.page(labels),(None,False))
    def test_result_title_and_footer_are_both_required(self):
        for rect in ((490,20,775,110),(480,625,815,690)):
            labels=dict(self.labels);labels.pop(rect)
            self.assertEqual(self.page(labels),(None,False))
    def test_weak_overlay_label_does_not_authorize_input(self):
        labels=dict(self.labels);labels[(630,275,1100,345)]=('与从者的牵纤加深了',.84)
        self.assertEqual(self.page(labels),(None,False))
    def settle(self,persistent=False):
        pages=['BOND_LEVEL_UP','BOND','MASTER_EXP','REWARDS','ADD_FRIEND','CONTINUE'];index=[0];inputs=[];clock=Clock()
        def read():
            page=pages[index[0]];d=frame(page if page in {'ADD_FRIEND','CONTINUE'} else 'BATTLE_RESULT')
            d.getBattleResultPage=lambda:page;return d
        def press(key):
            inputs.append(key)
            if not persistent:index[0]+=1
        main=kernel.Main();main.press=press;flow=BattleFlow(read,clock,clock=clock);error=None
        try:BattleCycle(main,flow).settleBattleResult()
        except FlowTimeout as e:error=e
        return inputs,error
    def test_overlay_then_original_three_pages_advance_once_each(self):
        inputs,error=self.settle();self.assertIsNone(error);self.assertEqual(inputs,[' ',' ',' ',' ','X'])
    def test_persistent_overlay_stops_without_reclick(self):
        inputs,error=self.settle(True);self.assertIsInstance(error,FlowTimeout);self.assertEqual(inputs,[' '])

if __name__=='__main__':unittest.main()

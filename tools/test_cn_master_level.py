"""Synthetic fixed-label regressions from a local CN master-level screenshot."""
import unittest
from unittest.mock import patch
import test_cn_result_pages as result_tests
from fgoDetect import OCR
from test_battle_cycle import kernel
from test_battle_flow import Clock,frame
from fgoBattleFlow import BattleCycle,BattleFlow,FlowTimeout
from fgoFlowTrace import FlowTrace

class MasterLevelTests(unittest.TestCase):
    detect=result_tests.CNResultPageTests.detect
    read=result_tests.CNResultPageTests.read
    labelsBase={(490,20,775,110):('战斗结果',.978),(480,625,815,690):('请点击游戏界面',.988),
                (500,85,1220,235):('等级提升',.985),(680,270,930,315):('御主等级',.997)}
    def page(self,labels):
        d=self.detect(labels)
        with patch.object(OCR.ZHS,'ocr_single_line',side_effect=self.read):return d.getBattleResultPage()
    def test_master_level_positive(self):self.assertEqual(self.page(self.labelsBase),'MASTER_LEVEL_UP')
    def test_overlay_precedes_background_master_exp(self):
        self.assertEqual(self.page(dict(self.labelsBase)|{(635,175,860,245):('获得经验值',.99)}),'MASTER_LEVEL_UP')
    def test_level_label_alone_is_not_result(self):self.assertIsNone(self.page({(500,85,1220,235):('等级提升',.99)}))
    def test_missing_master_label_is_not_level_overlay(self):
        labels=dict(self.labelsBase);labels.pop((680,270,930,315));self.assertIsNone(self.page(labels))
    def test_unconfirmed_level_overlay_blocks_background_exp(self):
        labels=dict(self.labelsBase);labels.pop((680,270,930,315));labels[(635,175,860,245)]=('获得经验值',.99)
        self.assertIsNone(self.page(labels))
    def test_each_independent_label_is_required(self):
        for rect in self.labelsBase:
            labels=dict(self.labelsBase);labels[rect]=(labels[rect][0],.84)
            with self.subTest(rect=rect):self.assertIsNone(self.page(labels))
    def test_rewards_unchanged(self):
        d=self.detect({})
        with patch.object(d,'_compare',return_value=True):self.assertEqual(d.getBattleResultPage(),'REWARDS')
    def settle(self,pages,persistent=False):
        clock=Clock();index=[0];inputs=[]
        def read():
            page=pages[index[0]];d=frame('CONTINUE' if page=='CONTINUE' else 'BATTLE_RESULT')
            d.getBattleResultPage=lambda:page;return d
        def press(key):
            inputs.append(key)
            if not persistent:index[0]+=1
        flow=BattleFlow(read,clock,clock=clock,trace=FlowTrace(clock=clock));main=kernel.Main();main.press=press
        error=None
        try:BattleCycle(main,flow).settleBattleResult()
        except FlowTimeout as e:error=e
        return inputs,error
    def test_master_level_between_other_result_pages(self):
        inputs,error=self.settle(['BOND','MASTER_LEVEL_UP','MASTER_EXP','REWARDS','CONTINUE'])
        self.assertIsNone(error);self.assertEqual(inputs,[' ']*4)
    def test_persistent_master_level_only_one_input(self):
        inputs,error=self.settle(['MASTER_LEVEL_UP'],True)
        self.assertIsInstance(error,FlowTimeout);self.assertEqual(inputs,[' '])
if __name__=='__main__':unittest.main()

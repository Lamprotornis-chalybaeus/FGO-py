"""Fixed-label regression from a local result overlay; no private pixels."""
import unittest
from unittest.mock import patch
from test_battle_cycle import kernel
from fgoDetect import XDetectCN,OCR

class BondResultContextTests(unittest.TestCase):
    labels={(490,20,775,110):('战斗结果',.99),
            (480,625,815,690):('请点击游戏界面',.80),
            (395,605,820,670):('请点击游戏界面',.913),
            (460,90,1260,225):('牵纤等级提升',.958),
            (630,270,1190,325):('与从者的牵线加深了',.913)}
    def page(self,labels):
        d=XDetectCN.__new__(XDetectCN);d._crop=lambda rect:rect;d._compare=lambda *a,**k:False
        with patch.object(OCR.ZHS,'ocr_single_line',side_effect=lambda r:labels.get(r,('',0))):
            return d.getBattleResultPage()
    def test_observed_context_crop_identifies_overlay(self):
        self.assertEqual(self.page(self.labels),'BOND_LEVEL_UP')
    def test_each_independent_fixed_label_is_required(self):
        for rect in ((490,20,775,110),(395,605,820,670),(460,90,1260,225),(630,270,1190,325)):
            labels=dict(self.labels);labels.pop(rect)
            self.assertIsNone(self.page(labels))
    def test_context_label_below_unchanged_threshold_is_rejected(self):
        for rect in ((395,605,820,670),(460,90,1260,225),(630,270,1190,325)):
            labels=dict(self.labels);labels[rect]=(labels[rect][0],.84)
            self.assertIsNone(self.page(labels))
    def test_context_footer_does_not_create_ordinary_bond_or_exp(self):
        labels=dict(self.labels);labels.pop((460,90,1260,225))
        labels[(75,160,420,215)]=('与从者的牵绊',.99)
        labels[(635,175,860,245)]=('获得经验值',.99)
        self.assertIsNone(self.page(labels))

if __name__=='__main__':unittest.main()

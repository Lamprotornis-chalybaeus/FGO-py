"""Synthetic resource-row geometry; no screenshot or player data."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from test_battle_cycle import kernel
import fgoApRecovery as ap
from fgoDetect import OCR

class ResourceRowTests(unittest.TestCase):
    def target(self,*,kind=0,names=None,held='2个持有',score=.99):
        names=names or [ap.RESOURCE_LABELS[kind]]
        spans=[SimpleNamespace(text=name,box=[[10,166],[140,166],[140,198],[10,198]]) for name in names]
        def crop(r):return np.full((r[3]-r[1],r[2]-r[0],3),1 if r[0]==785 else 2,np.uint8)
        d=SimpleNamespace(_crop=crop)
        def read(image):return (held,.99) if image[0,0,0]==1 else (ap.RESOURCE_LABELS[kind],score)
        with patch.object(ap,'isResourceSelector',return_value=True),patch.object(OCR.ZHS,'detect_and_ocr',return_value=spans),patch.object(OCR.ZHS,'ocr_single_line',side_effect=read):return ap.resourceTarget(d,kind)
    def test_named_gold_row_has_positive_inventory(self):self.assertEqual(self.target(),(650,332))
    def test_every_legal_name_is_explicit(self):
        for kind in range(4):
            with self.subTest(kind=kind):self.assertIsNotNone(self.target(kind=kind))
    def test_quartz_is_not_a_gold_proposal(self):self.assertIsNone(self.target(names=['圣晶石']))
    def test_duplicate_resource_names_are_ambiguous(self):self.assertIsNone(self.target(names=['黄金果实','黄金果实']))
    def test_zero_held_resource_is_not_actionable(self):self.assertIsNone(self.target(held='0个持有'))
    def test_low_confidence_local_read_rejects_proposal(self):self.assertIsNone(self.target(score=.84))
    def test_unknown_inventory_is_not_actionable(self):self.assertIsNone(self.target(held='未能读取'))
if __name__=='__main__':unittest.main()

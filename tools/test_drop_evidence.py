"""Offline regressions for rejecting cross-class cards and conflicting QP reads."""
import unittest,runpy
from pathlib import Path
from unittest.mock import Mock

env=runpy.run_path(str(Path(__file__).with_name('test_ux_polish.py')))
drop=env['drop'];np=env['np']

class ConfirmationTests(unittest.TestCase):
    def test_small_class_region_can_reject_full_card_false_positive(self):
        template=np.full((118,118,3),180,np.uint8);pixels=template.copy();pixels[:36,:36]=140
        score=drop.cv2.minMaxLoc(drop.cv2.matchTemplate(pixels,template,drop.cv2.TM_SQDIFF_NORMED))[0]
        self.assertLess(score,.02)
        self.assertFalse(drop.confirmationMatches(pixels,template,dict(match_region='card',confirmation_regions=[[0,0,36,36]])))
    def test_matching_class_feature_passes(self):
        pixels=np.random.default_rng(42).integers(20,240,(118,118,3),dtype=np.uint8)
        self.assertTrue(drop.confirmationMatches(pixels,pixels,dict(match_region='card',confirmation_regions=[[0,0,36,36]])))
    def test_occluded_class_feature_refuses(self):
        template=np.full((118,118,3),180,np.uint8);pixels=template.copy();pixels[:36,:36]=0
        self.assertFalse(drop.confirmationMatches(pixels,template,dict(match_region='card',confirmation_regions=[[0,0,36,36]])))
    def test_malformed_confirmation_refuses(self):
        pixels=np.full((118,118,3),180,np.uint8)
        for regions in ([],None,[[0,0,119,36]],[[0,0,36]],[[0,0,36.,36]],[[-1,0,36,36]]):
            with self.subTest(regions=regions):self.assertFalse(drop.confirmationMatches(pixels,pixels,dict(match_region='card',confirmation_regions=regions)))
    def test_legacy_template_without_confirmation_is_unchanged(self):
        pixels=np.full((77,77,3),180,np.uint8);self.assertTrue(drop.confirmationMatches(pixels,pixels,{}))

class CurrencyTests(unittest.TestCase):
    def read(self,values):
        ocr=Mock();ocr.ocr_single_line.side_effect=values
        result=drop.readCurrencyAmount(np.zeros((130,118,3),np.uint8),ocr)
        return result,ocr
    def test_valid_original_uses_one_read(self):
        (amount,evidence),ocr=self.read([('+780',.99)])
        self.assertEqual(amount,780);self.assertEqual(ocr.ocr_single_line.call_count,1);self.assertNotIn('checks',evidence)
    def test_invalid_original_four_independent_reads_agree(self):
        (amount,evidence),ocr=self.read([('1+10,000',.91)]+[('+10,000',.93)]*4)
        self.assertEqual(amount,10000);self.assertEqual(evidence['text'],'1+10,000');self.assertEqual(len(evidence['checks']),4)
        self.assertEqual([c.args[0].shape[:2] for c in ocr.ocr_single_line.call_args_list],[(28,98),(20,101),(40,202),(20,105),(40,210)])
    def test_retry_disagreement_keeps_unknown(self):
        (amount,_),_=self.read([('?',.4),('+10,000',.99),('+1,000',.99),('+10,000',.99),('+10,000',.99)])
        self.assertIsNone(amount)
    def test_low_confidence_read_keeps_unknown(self):
        (amount,_),_=self.read([('?',.4)]+[('+10,000',.99)]*3+[('+10,000',.89)])
        self.assertIsNone(amount)
    def test_valid_but_low_confidence_original_can_veto_retry(self):
        (amount,_),_=self.read([('+1,000',.6)]+[('+10,000',.99)]*4)
        self.assertIsNone(amount)
    def test_invalid_prefix_is_never_silently_removed(self):
        (amount,_),_=self.read([('1+10,000',.99)]*5);self.assertIsNone(amount)
    def test_invalid_comma_and_negative_amount_refuse(self):
        for text in ('10,00','-10000','10000 AP','1+10,000'):
            with self.subTest(text=text):self.assertIsNone(drop.parseCurrency(text,.99,.85))

if __name__=='__main__':unittest.main()

"""Offline menu exit proofs and removal of item-recognition hot paths."""
import os,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import numpy as np
APP=Path(__file__).resolve().parents[1]/'FGO-py'
sys.path.insert(0,str(APP));os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
old=os.getcwd();os.chdir(APP)
try:
    import fgoKernel as kernel,fgoNavigation as nav
    from fgoDetect import XDetectBase
finally:os.chdir(old)

class MenuProofTests(unittest.TestCase):
    def frame(self):
        f=Mock();f.im=np.zeros((720,1280,3),np.uint8);f._crop.side_effect=lambda r:f.im[r[1]:r[3],r[0]:r[2]]
        return f
    def header(self,title='达·芬奇工房',score=.97):return nav.Label(title,(951,8,1265,61),score)
    def test_observed_shop_name_has_two_read_proof(self):
        with patch.object(nav.OCR.ZHS,'ocr_single_line',side_effect=[('达·芬奇工房',.96),('达芬奇工房',.97)]):
            self.assertTrue(nav.confirmedMenuPageCN(self.frame(),[self.header()]))
    def test_all_known_menu_headers_require_two_read_proof(self):
        for title in nav.MENU_PAGE_HEADERS_CN:
            with self.subTest(title=title),patch.object(nav.OCR.ZHS,'ocr_single_line',return_value=(title,.97)):
                self.assertTrue(nav.confirmedMenuPageCN(self.frame(),[self.header(title)]))
    def test_disagreement_or_low_read_does_not_authorize_menu(self):
        for reads in ([('达芬奇工房',.99),('商店',.99)],[('达芬奇工房',.84),('达芬奇工房',.99)]):
            with patch.object(nav.OCR.ZHS,'ocr_single_line',side_effect=reads):self.assertFalse(nav.confirmedMenuPageCN(self.frame(),[self.header()]))
    def test_no_template_duplicate_header_or_wrong_band_rejected(self):
        f=self.frame();f.isMainInterface.return_value=False
        with patch.object(nav.OCR.ZHS,'ocr_single_line') as ocr:
            self.assertFalse(nav.confirmedMenuPageCN(f,[self.header()]))
            f.isMainInterface.return_value=True
            self.assertFalse(nav.confirmedMenuPageCN(f,[self.header(),self.header('个人空间')]))
            self.assertFalse(nav.confirmedMenuPageCN(f,[nav.Label('达芬奇工房',(850,160,1000,210),.99)]))
            ocr.assert_not_called()
    def test_purchase_dialog_still_overrides_proven_shop(self):
        f=SimpleNamespace(isMainInterface=lambda:True,isWeeklyMission=lambda:False)
        rows=[self.header(),nav.Label('是否购买？',(400,300,800,350),.99)]
        self.assertEqual(nav.safeMenuPageCN(f,rows),'UNSAFE_MODAL')

class ItemRemovalTests(unittest.TestCase):
    def test_source_and_detect_api_removed(self):
        self.assertFalse((APP/'fgoDrop.py').exists());self.assertFalse((APP/'fgoImage/drop').exists());self.assertFalse((APP/'fgoImage/material').exists())
        self.assertFalse(hasattr(XDetectBase,'getDropResult'));self.assertFalse(hasattr(XDetectBase,'getMaterial'))
    def test_finished_battle_needs_no_item_ocr(self):
        frame=SimpleNamespace(isTurnBegin=lambda:False,isSpecialDropSuspended=lambda:False,isBattleFinished=lambda:True)
        def detect(*a):kernel.Detect.cache=frame;return frame
        battle=kernel.Battle(turnClass=lambda:object())
        with patch.object(kernel,'Detect',side_effect=detect),patch.object(kernel.fgoDevice.device,'perform') as inputs:
            self.assertTrue(battle());inputs.assert_not_called()
        self.assertEqual(set(battle.result),{'type','turn','time','observedDefeated'})
    def test_main_statistics_only_contain_battle_fields(self):
        run=kernel.Main();run.prepare()
        for key in ('material','dropStats','unknownDrops'):self.assertNotIn(key,run.result)

class FriendWaitSafetyTests(unittest.TestCase):
    def invoke(self,frame,clock=None):
        def detect(*a):kernel.Detect.cache=frame;return frame
        guard=SimpleNamespace(steps=lambda:iter(range(2)))
        with patch.object(kernel.XDetect,'region','CN'),patch.object(kernel,'Detect',side_effect=detect),patch.object(kernel.friendImg,'flush',return_value=False),patch.object(nav,'NavigationGuard',return_value=guard),patch.object(kernel.fgoDevice.device,'press') as press,patch.object(kernel.fgoDevice.device,'touch') as touch,patch.object(kernel.fgoDevice.device,'perform') as perform,patch.object(nav,'publish'),patch.object(kernel.time,'monotonic',side_effect=clock or [0]*20):
            try:kernel.Main(friendPolicy='first').chooseFriend();error=None
            except kernel.ScriptStop as e:error=str(e)
        return error,press,touch,perform
    def test_exhausted_observation_never_selects_unconfirmed_friend(self):
        f=SimpleNamespace(isBattleContinue=lambda:False,isChooseFriend=lambda:False,isBattleFormation=lambda:False,isNoFriend=lambda:False)
        error,press,touch,perform=self.invoke(f)
        self.assertIn('未达到预期状态',error);press.assert_not_called();touch.assert_not_called();perform.assert_not_called()
    def test_continue_popup_cannot_be_treated_as_friend_page(self):
        f=SimpleNamespace(isBattleContinue=lambda:True,isChooseFriend=lambda:True)
        error,press,touch,perform=self.invoke(f,[0,0,20])
        self.assertIn('连续出击确认未消失',error);press.assert_not_called();touch.assert_not_called();perform.assert_not_called()
    def test_confirmed_friend_page_keeps_existing_first_policy(self):
        f=SimpleNamespace(isBattleContinue=lambda:False,isChooseFriend=lambda:True)
        error,press,_,_=self.invoke(f);self.assertIsNone(error);press.assert_called_once_with('8')

if __name__=='__main__':unittest.main()

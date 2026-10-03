"""Shared terminal routing safety regressions; no live device input."""
import logging,os,sys,types,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import numpy as np

APP=Path(__file__).resolve().parents[1]/'FGO-py'
sys.path.insert(0,str(APP))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
if 'fgoLogging' not in sys.modules:
    fake=types.ModuleType('fgoLogging');fake.getLogger=logging.getLogger;fake.logMeta=lambda logger:type;fake.logit=lambda *a,**k:lambda f:f
    sys.modules['fgoLogging']=fake
old=os.getcwd();os.chdir(APP)
try:import fgoNavigation as nav
finally:os.chdir(old)

class StandardTerminalTests(unittest.TestCase):
    def test_weak_global_return_requires_agreeing_local_return(self):
        frame=Mock();frame.im=np.zeros((720,1280,3),np.uint8);frame._crop.side_effect=lambda r:frame.im[r[1]:r[3],r[0]:r[2]]
        weak=types.SimpleNamespace(text='返回',score=.799,box=[[76,24],[140,24],[140,59],[76,59]])
        with patch.object(nav.OCR.ZHS,'detect_and_ocr',return_value=[weak]),patch.object(nav.OCR.ZHS,'ocr_single_line',return_value=('返回',.99)):
            found=nav.unique(nav.labels(frame),'返回',(0,0,200,95))
        self.assertEqual(found.box,(70,25,150,60))

    def test_disagreeing_return_is_not_promoted(self):
        frame=Mock();frame.im=np.zeros((720,1280,3),np.uint8);frame._crop.side_effect=lambda r:frame.im[r[1]:r[3],r[0]:r[2]]
        weak=types.SimpleNamespace(text='返回',score=.799,box=[[76,24],[140,24],[140,59],[76,59]])
        with patch.object(nav.OCR.ZHS,'detect_and_ocr',return_value=[weak]),patch.object(nav.OCR.ZHS,'ocr_single_line',side_effect=[('返回',.99),('关闭',.99)]*3):
            self.assertIsNone(nav.unique(nav.labels(frame),'返回',(0,0,200,95)))

    def test_low_local_return_is_not_promoted(self):
        frame=Mock();frame.im=np.zeros((720,1280,3),np.uint8);frame._crop.side_effect=lambda r:frame.im[r[1]:r[3],r[0]:r[2]]
        weak=types.SimpleNamespace(text='返回',score=.799,box=[[76,24],[140,24],[140,59],[76,59]])
        with patch.object(nav.OCR.ZHS,'detect_and_ocr',return_value=[weak]),patch.object(nav.OCR.ZHS,'ocr_single_line',return_value=('返回',.84)):
            self.assertIsNone(nav.unique(nav.labels(frame),'返回',(0,0,200,95)))
    def test_all_return_root_callers_share_terminal_normalization(self):
        guard=nav.NavigationGuard('冬木');frame=object()
        with patch.object(nav,'normalizeToTerminalCN',return_value=frame) as normalize:
            self.assertIs(nav.returnRootCN(guard),frame)
        normalize.assert_called_once_with(guard)

    def observation(self):
        return [patch.object(nav,'Detect',return_value=Mock()),patch.object(nav,'labels',return_value=[]),patch.object(nav,'expandedMenuCN',return_value=None),patch.object(nav.schedule,'sleep')]

    def test_unknown_frame_can_settle_to_proven_home_without_input(self):
        a,b,c,d=self.observation()
        with a as read,b,c,d,patch.object(nav,'safeMenuPageCN',side_effect=['UNKNOWN','ROOT_CATEGORY']),patch.object(nav,'terminalHomeCN',side_effect=[False,True]),patch.object(nav.fgoDevice.device,'touch') as touch:
            nav.returnRootCN()
        self.assertEqual(read.call_count,2);touch.assert_not_called()

    def test_three_unknown_frames_stop_without_input(self):
        a,b,c,d=self.observation()
        with a as read,b,c,d,patch.object(nav,'safeMenuPageCN',return_value='UNKNOWN'),patch.object(nav,'terminalHomeCN',return_value=False),patch.object(nav.fgoDevice.device,'touch') as touch:
            with self.assertRaisesRegex(nav.ScriptStop,'连续三帧'):nav.returnRootCN()
        self.assertEqual(read.call_count,3);touch.assert_not_called()

    def test_unknown_followed_by_modal_stops_immediately(self):
        a,b,c,d=self.observation()
        with a as read,b,c,d,patch.object(nav,'safeMenuPageCN',side_effect=['UNKNOWN','UNSAFE_MODAL']),patch.object(nav,'terminalHomeCN',return_value=False),patch.object(nav.fgoDevice.device,'touch') as touch:
            with self.assertRaisesRegex(nav.ScriptStop,'UNSAFE_MODAL'):nav.returnRootCN()
        self.assertEqual(read.call_count,2);touch.assert_not_called()

    def test_parent_navigation_deadline_is_not_extended(self):
        guard=nav.NavigationGuard('冬木',5);deadline=guard.deadline
        a,b,c,d=self.observation()
        with a,b,c,d,patch.object(nav,'safeMenuPageCN',return_value='ROOT_CATEGORY'),patch.object(nav,'terminalHomeCN',return_value=True):nav.returnRootCN(guard)
        self.assertEqual(guard.deadline,deadline)

    def test_gate_low_global_close_uses_agreeing_local_text(self):
        frame=Mock();frame.im=np.zeros((720,1280,3),np.uint8);frame._crop.side_effect=lambda r:frame.im[r[1]:r[3],r[0]:r[2]]
        header=types.SimpleNamespace(text='迦勒底之门',score=.99,box=[[1000,5],[1270,5],[1270,55],[1000,55]])
        weak=types.SimpleNamespace(text='关闭',score=.72,box=[[75,23],[143,23],[143,62],[75,62]])
        with patch.object(nav.OCR.ZHS,'detect_and_ocr',return_value=[header,weak]),patch.object(nav.OCR.ZHS,'ocr_single_line',return_value=('关闭',.99)):
            items=nav.labels(frame);self.assertEqual(nav.classify(frame,items),'GATE')
        self.assertEqual(nav.unique(items,'关闭',(0,0,200,95)).box,(70,25,150,60))

    def test_disagreeing_local_close_does_not_admit_gate(self):
        frame=Mock();frame.im=np.zeros((720,1280,3),np.uint8);frame._crop.side_effect=lambda r:frame.im[r[1]:r[3],r[0]:r[2]];frame.isWeeklyMission.return_value=False
        header=types.SimpleNamespace(text='迦勒底之门',score=.99,box=[[1000,5],[1270,5],[1270,55],[1000,55]])
        weak=types.SimpleNamespace(text='关闭',score=.72,box=[[75,23],[143,23],[143,62],[75,62]])
        with patch.object(nav.OCR.ZHS,'detect_and_ocr',return_value=[header,weak]),patch.object(nav.OCR.ZHS,'ocr_single_line',side_effect=[('关闭',.99),('通知',.99)]*3):
            self.assertEqual(nav.classify(frame,nav.labels(frame)),'UNKNOWN')

if __name__=='__main__':unittest.main()

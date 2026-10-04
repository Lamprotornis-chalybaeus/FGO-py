"""Support header alone must not authorize the first-row selection input."""
import unittest
from unittest.mock import patch
from test_battle_cycle import kernel
from test_battle_flow import Clock,frame
from fgoBattleFlow import BattleFlow,FlowTimeout
from fgoFlowTrace import FlowTrace
from fgoDetect import XDetectCN,OCR

class SupportReadyTests(unittest.TestCase):
    def test_observed_pair_of_fixed_body_labels(self):
        d=XDetectCN.__new__(XDetectCN);d._crop=lambda r:r
        labels={(235,265,320,310):('从者',.926),(235,318,303,353):('宝具',.995)}
        with patch.object(OCR.ZHS,'ocr_single_line',side_effect=lambda r:labels.get(r,('',0))):
            self.assertTrue(d.isFirstSupportReady())
            labels[(235,318,303,353)]=('宝具',.4)
            self.assertFalse(d.isFirstSupportReady())
    def runChoice(self,ready):
        clock=Clock();state=['FRIEND'];inputs=[]
        def read():
            d=frame(state[0]);d.isFirstSupportReady=lambda:ready(clock.now)
            return d
        flow=BattleFlow(read,clock,clock=clock,trace=FlowTrace(clock=clock))
        def touch(pos,**kwargs):inputs.append((clock.now,pos));state[0]='FORMATION'
        with patch.object(kernel,'schedule',clock),patch.object(kernel.XDetect,'region','CN'),patch.object(kernel.friendImg,'flush',return_value=False),patch.object(kernel.fgoDevice.device,'touch',side_effect=touch):
            try:kernel.Main(friendPolicy='first').chooseFriend(flow);error=None
            except FlowTimeout as e:error=e
        return inputs,error,flow
    def test_header_visible_before_body_has_no_early_input(self):
        inputs,error,_=self.runChoice(lambda t:t>=3)
        self.assertIsNone(error);self.assertEqual(len(inputs),1)
        self.assertGreaterEqual(inputs[0][0],3.4)
    def test_brief_body_label_flicker_does_not_authorize_input(self):
        inputs,error,_=self.runChoice(lambda t:.2<=t<.4 or t>=2)
        self.assertIsNone(error);self.assertEqual(len(inputs),1)
        self.assertGreaterEqual(inputs[0][0],2.4)
    def test_no_body_confirmation_stops_without_any_input(self):
        inputs,error,_=self.runChoice(lambda t:False)
        self.assertIsInstance(error,FlowTimeout);self.assertEqual(inputs,[])

if __name__=='__main__':unittest.main()

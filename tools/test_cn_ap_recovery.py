"""Offline synthetic AP recovery state/consumption regressions; no device I/O."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch,Mock
from test_battle_cycle import kernel
from test_battle_flow import Clock,frame
from fgoBattleFlow import BattleFlow
from fgoFlowTrace import FlowTrace
import fgoApRecovery as ap
from fgoDetect import XDetectCN,OCR

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.guard=patch.object(ap,'_uncertainDevices',set());self.guard.start();self.addCleanup(self.guard.stop)
        self.ready=patch.object(ap,'CONFIRMATION_PRODUCER_READY',True);self.ready.start();self.addCleanup(self.ready.stop)
    def scenario(self,kind=0,budget=1,fail=False,unknown_ap=False):
        clock=Clock();phase=['SELECTOR'];inputs=[]
        def read():
            p=phase[0];d=frame('FORMATION' if p=='DONE' else 'AP_EMPTY' if p=='SELECTOR' else 'UNKNOWN')
            d.phase=p
            def getAp():
                if unknown_ap:raise kernel.ScriptStop('AP unavailable')
                return 5 if p in {'SELECTOR','CONFIRM'} else 86
            d.getAp=getAp
            return d
        def touch(pos,**kwargs):
            inputs.append((pos,kwargs))
            if phase[0]=='SELECTOR':phase[0]='CONFIRM'
            elif phase[0]=='CONFIRM' and not fail:phase[0]='DONE'
        flow=BattleFlow(read,clock,clock=clock,trace=FlowTrace(clock=clock));main=kernel.Main(budget,kind)
        device=SimpleNamespace(touch=touch,swipe=Mock())
        patches=[patch.object(ap,'isResourceSelector',side_effect=lambda d:d.phase=='SELECTOR'),
                 patch.object(ap,'resourceTarget',side_effect=lambda d,k:(650,330) if d.phase=='SELECTOR' else None),
                 patch.object(ap,'confirmation',side_effect=lambda d,k:ap.RecoveryConfirmation(k,(890,570)) if d.phase=='CONFIRM' else None),
                 patch.object(ap,'safeAp',side_effect=lambda d:None if unknown_ap else d.getAp())]
        return main,flow,device,inputs,patches
    def restore(self,scenario):
        main,flow,device,inputs,patches=scenario
        with patches[0],patches[1],patches[2],patches[3]:return ap.restoreApCN(main,flow,device)
    def test_unimplemented_confirmation_disables_live_path_before_any_input(self):
        s=self.scenario()
        with patch.object(ap,'CONFIRMATION_PRODUCER_READY',False):
            with self.assertRaisesRegex(kernel.ScriptStop,'尚未实机验证'):self.restore(s)
        self.assertEqual(s[3],[]);self.assertEqual(s[0].appleTotal,1)
        s[2].swipe.assert_not_called()
    def test_default_confirmation_has_no_guessed_positive_producer(self):
        self.assertIsNone(ap.confirmation(Mock(),0))
    def test_budget_zero_no_input(self):
        s=self.scenario(budget=0);self.assertFalse(self.restore(s));self.assertEqual(s[3],[])
    def test_gold_success_decrements_after_positive_success(self):
        s=self.scenario();self.assertTrue(self.restore(s));self.assertEqual(s[0].appleTotal,0)
        self.assertEqual(s[3],[((650,330),{'duration':.08}),((890,570),{'duration':.08})])
        self.assertTrue(s[0].apRecoveryLog[0]['verified'])
    def test_each_explicit_legal_resource_uses_same_bounded_policy(self):
        for kind in range(4):
            s=self.scenario(kind=kind)
            with self.subTest(kind=kind):self.assertTrue(self.restore(s));self.assertEqual(s[0].appleTotal,0)
    def test_failed_restore_does_not_decrement_or_repeat(self):
        s=self.scenario(fail=True)
        with self.assertRaisesRegex(kernel.ScriptStop,ap.UNVERIFIED):self.restore(s)
        self.assertEqual(s[0].appleTotal,1);self.assertEqual(len(s[3]),2)
    def test_double_invoke_after_uncertain_spend_is_blocked(self):
        s=self.scenario(fail=True)
        for _ in range(2):
            with self.assertRaisesRegex(kernel.ScriptStop,ap.UNVERIFIED):self.restore(s)
        self.assertEqual(len(s[3]),2);self.assertEqual(s[0].appleTotal,1)
    def test_double_invoke_after_success_is_not_another_spend(self):
        s=self.scenario(budget=2);self.assertTrue(self.restore(s))
        with self.assertRaisesRegex(kernel.ScriptStop,ap.UNVERIFIED):self.restore(s)
        self.assertEqual(len(s[3]),2);self.assertEqual(s[0].appleTotal,1)
    def test_new_runner_cannot_repeat_uncertain_device_spend(self):
        s=self.scenario(fail=True)
        with self.assertRaises(kernel.ScriptStop):self.restore(s)
        other=kernel.Main(1,0)
        with self.assertRaisesRegex(kernel.ScriptStop,ap.UNVERIFIED):ap.restoreApCN(other,s[1],s[2])
        self.assertEqual(len(s[3]),2);self.assertEqual(other.appleTotal,1)
    def test_reconnecting_same_named_device_cannot_repeat_uncertain_spend(self):
        s=self.scenario(fail=True);s[2].name='synthetic-device'
        with self.assertRaises(kernel.ScriptStop):self.restore(s)
        with self.assertRaisesRegex(kernel.ScriptStop,ap.UNVERIFIED):ap.ensureNotUncertain(SimpleNamespace(name='synthetic-device'))
    def test_operation_blocks_quartz_before_navigation(self):
        op=kernel.Operation([((1,0,2,0),1)],appleTotal=1,appleKind=4,wait=False)
        with patch.object(kernel.XDetect,'region','CN'),patch.object(kernel,'goto') as goto:
            with self.assertRaisesRegex(kernel.ScriptStop,ap.FORBIDDEN):op()
            goto.assert_not_called()
    def test_success_can_deduct_quest_cost_before_ap_read(self):
        s=self.scenario();original=s[1].reader
        def read():
            d=original()
            if d.phase=='DONE':d.getAp=lambda:1
            return d
        s[1].reader=read;self.assertTrue(self.restore(s));self.assertEqual(s[0].appleTotal,0)
    def test_return_to_quest_ready_requires_numeric_ap_increase(self):
        from fgoBattleFlow import BattleFlowState as S
        s=self.scenario();original=s[1].reader
        def read():
            d=original()
            if d.phase=='DONE':
                d=frame('QUEST_READY');d.phase='DONE';d.getAp=lambda:86
            return d
        s[1].reader=read;self.assertTrue(self.restore(s));self.assertEqual(s[0].appleTotal,0)
    def test_return_to_list_without_ap_increase_is_not_success(self):
        s=self.scenario();original=s[1].reader
        def read():
            d=original()
            if d.phase=='DONE':
                d=frame('QUEST_READY');d.phase='DONE';d.getAp=lambda:5
            return d
        s[1].reader=read
        with self.assertRaisesRegex(kernel.ScriptStop,ap.UNVERIFIED):self.restore(s)
        self.assertEqual(s[0].appleTotal,1);self.assertEqual(len(s[3]),2)
    def test_missing_confirmation_only_selects_once_budget_unchanged(self):
        s=self.scenario()
        s[4][2]=patch.object(ap,'confirmation',return_value=None)
        with self.assertRaisesRegex(kernel.ScriptStop,ap.UNVERIFIED):self.restore(s)
        self.assertEqual(len(s[3]),1);self.assertEqual(s[0].appleTotal,1)
    def test_unknown_ap_uses_positive_formation_proof(self):
        s=self.scenario(unknown_ap=True);self.assertTrue(self.restore(s))
        self.assertIsNone(s[0].apRecoveryLog[0]['afterAP'])
    def test_kind_four_is_forbidden_even_with_zero_budget(self):
        s=self.scenario(kind=4,budget=0)
        with self.assertRaisesRegex(kernel.ScriptStop,ap.FORBIDDEN):self.restore(s)
        self.assertEqual(s[3],[])
    def test_core_prepare_blocks_quartz_before_device_or_navigation(self):
        main=kernel.Main(1,4)
        with patch.object(kernel.XDetect,'region','CN'),patch.object(main,'makeFlow') as make:
            with self.assertRaisesRegex(kernel.ScriptStop,ap.FORBIDDEN):main.prepare()
            make.assert_not_called()
    def test_unrelated_fraction_is_not_logged_as_ap(self):
        d=Mock()
        with patch.object(ap,'label',return_value='队伍消耗'):self.assertIsNone(ap.safeAp(d))
        d.getAp.assert_not_called()
    def test_non_cn_legacy_input_and_budget_unchanged(self):
        main=kernel.Main(1,0)
        with patch.object(kernel.XDetect,'region','JP'),patch.object(kernel.fgoDevice.device,'perform') as perform:
            main.eatApple();perform.assert_called_once_with('WL',(600,1200))
        self.assertEqual(main.appleTotal,0)
    def test_cn_budget_zero_stops_cycle_without_close_or_spend(self):
        from test_battle_cycle import CycleTests,Scenario
        with patch.object(kernel.XDetect,'region','CN'):
            s=Scenario(ap_empty=True);main,flow,error=CycleTests().runScenario(s)
        self.assertIsNone(error);self.assertEqual(s.actions,[('QUEST_READY','8')]);self.assertEqual(main.completionReason,'Ap Empty')
    def test_selector_requires_old_template_and_all_fixed_labels(self):
        labels={(520,32,770,72):('行动力回复',.97),(520,67,780,100):('消耗道具回复行动力',.93),(575,588,707,645):('关闭',.99)}
        d=XDetectCN.__new__(XDetectCN);d._crop=lambda r:r;d.isApEmpty=lambda:True
        with patch.object(OCR.ZHS,'ocr_single_line',side_effect=lambda r:labels.get(r,('',0))):
            self.assertTrue(ap.isResourceSelector(d))
            labels[(520,32,770,72)]=('行动力回复',.84);self.assertFalse(ap.isResourceSelector(d))
    def test_unverified_resource_never_clicked(self):
        s=self.scenario();s[4][1]=patch.object(ap,'resourceTarget',return_value=None)
        with self.assertRaisesRegex(kernel.ScriptStop,'未正向确认指定'):self.restore(s)
        self.assertEqual(s[3],[])
    def test_unstable_resource_never_clicked(self):
        s=self.scenario();s[4][1]=patch.object(ap,'resourceTarget',side_effect=[(650,330),(650,360)])
        with self.assertRaisesRegex(kernel.ScriptStop,'位置不稳定'):self.restore(s)
        self.assertEqual(s[3],[])
if __name__=='__main__':unittest.main()

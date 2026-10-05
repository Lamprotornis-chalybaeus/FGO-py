"""Synthetic event safety/cycle regressions; no private image or device."""
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import test_gui_navigation
from test_gui_navigation import item
import fgoEventProgress as event
import fgoEventCycle as ec
from fgoBattleFlow import BattleFlow,BattleCycle,FlowTimeout
from fgoFlowTrace import FlowTrace
from test_battle_flow import Clock,frame


class ResourceTests(unittest.TestCase):
    def test_quartz_policy_cannot_be_enabled(self):
        with self.assertRaises(ValueError):ec.EventResourcePolicy(allowQuartz=True)
    def test_apple_confirmation_allowed(self):
        ec.QuartzGuard.check([item('恢复AP',400,200),item('黄金果实',400,300)],appleConfirm=True)
    def test_quartz_ap_restore_blocked(self):
        with self.assertRaises(ec.ScriptStop):ec.QuartzGuard.check([item('恢复AP',400,200),item('圣晶石',400,300)],appleConfirm=True)
    def test_quartz_use_confirmation_without_ap_word_is_blocked(self):
        with self.assertRaises(ec.ScriptStop):ec.QuartzGuard.check([item('是否使用圣晶石？',400,200),item('黄金果实',400,300)],appleConfirm=True)
    def test_quartz_revive_blocked(self):
        with self.assertRaises(ec.ScriptStop):ec.QuartzGuard.check([item('复活',400,200),item('Saint Quartz',400,300)])
    def test_mixed_selector_only_explicit_apple(self):
        apple=item('白银果实',400,300)
        labels=[item('AP不足',400,200),apple,item('圣晶石',400,400)]
        ec.QuartzGuard.check(labels,appleOption=apple)
        with self.assertRaises(ec.ScriptStop):ec.QuartzGuard.check(labels)
        with self.assertRaises(ec.ScriptStop):ec.QuartzGuard.check(labels,appleOption=labels[-1])
    def test_mixed_confirmation_never_allowed(self):
        apple=item('黄金果实',400,300)
        with self.assertRaises(ec.ScriptStop):ec.QuartzGuard.check([item('恢复AP 是否使用',400,200),apple,item('圣晶石',400,400)],appleOption=apple)
    def test_low_confidence_quartz_still_blocked(self):
        with self.assertRaises(ec.ScriptStop):ec.QuartzGuard.check([item('恢复AP',400,200),item('圣晶石',400,300,score=.2)],appleConfirm=True)
    def test_quartz_awarded_in_nonresource_story_is_not_consumption(self):
        ec.QuartzGuard.check([item('奖励 圣晶石',400,300)])
    def test_reward_choice_is_not_story_default(self):
        with self.assertRaises(ec.ScriptStop):ec.QuartzGuard.check([item('请选择奖励',400,300)])
    def test_apple_policy_disabled_never_inputs(self):
        runner=object.__new__(ec.EventRunner);runner.policy=ec.EventResourcePolicy(allowApples=False)
        with patch.object(ec.fgoDevice.device,'touch') as touch:
            with self.assertRaises(ec.ScriptStop):runner.restoreAp()
            touch.assert_not_called()


class BoundaryTests(unittest.TestCase):
    def scenario(self,states,boundary):
        clock=Clock();index=[0];inputs=[]
        def read():
            f=frame(states[index[0]])
            f.getBattleResultPage=lambda:'REWARDS' if f.isBattleFinished() else None
            return f
        def press(key):inputs.append(key);index[0]=min(index[0]+1,len(states)-1)
        flow=BattleFlow(read,clock,clock=clock,trace=FlowTrace(clock=clock))
        cycle=BattleCycle(Mock(press=press),flow)
        try:obs=cycle.settleBattleResult(boundary=boundary);error=None
        except ec.ScriptStop as e:obs=None;error=e
        return obs,error,inputs
    def test_result_to_positive_event_boundary(self):
        obs,error,inputs=self.scenario(['BATTLE_RESULT','UNKNOWN'],lambda d:not d.isBattleFinished())
        self.assertIsNone(error);self.assertEqual(obs.state,ec.S.UNKNOWN);self.assertEqual(inputs,[' '])
    def test_unknown_cannot_finish_without_positive_event_proof(self):
        obs,error,inputs=self.scenario(['BATTLE_RESULT','UNKNOWN'],lambda d:False)
        self.assertIsInstance(error,FlowTimeout);self.assertEqual(inputs,[' '])
    def test_positive_callback_does_not_mask_defeat(self):
        obs,error,inputs=self.scenario(['BATTLE_RESULT','DEFEATED'],lambda d:True)
        self.assertIsInstance(error,FlowTimeout);self.assertEqual(inputs,[' '])
    def test_original_continue_boundary_retained(self):
        obs,error,inputs=self.scenario(['BATTLE_RESULT','CONTINUE'],None)
        self.assertIsNone(error);self.assertEqual(obs.state,ec.S.CONTINUE)


class SharedEventCycleTests(unittest.TestCase):
    def test_resume_existing_result_settles_without_counting_another_entry(self):
        clock=Clock();index=[0]
        def readFrame():
            d=frame('BATTLE_RESULT' if index[0]==0 else 'UNKNOWN')
            d.getBattleResultPage=lambda:'REWARDS' if index[0]==0 else None
            return d
        flow=BattleFlow(readFrame,clock,clock=clock,trace=FlowTrace(clock=clock))
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock())
        runner.main.makeFlow=Mock(return_value=flow)
        runner.main.press=lambda key:index.__setitem__(0,1)
        runner.read=lambda:(readFrame(),[],'battle_result' if index[0]==0 else 'event_map')
        runner.eventBoundary=lambda d:not d.isBattleFinished()
        self.assertEqual(runner.runBattle()[2],'event_map')
        self.assertEqual(runner.settledResumes,1)
        self.assertEqual((runner.main.startedBattles,runner.main.completedAttempts),(0,0))
        runner.ledger.append.assert_called_once_with('settlement_resume',nextState='event_map',newBattleEntry=False)
    def runCycle(self,defeated=False):
        from test_battle_cycle import Scenario
        scenario=Scenario(defeated=defeated);scenario.state='FRIEND'
        runner=ec.EventRunner(ec.EventResourcePolicy(allowApples=False),ledger=Mock())
        runner.main.battleClass=scenario.battle
        flow=BattleFlow(scenario.read,scenario,clock=scenario,trace=FlowTrace(clock=scenario))
        names={'FRIEND':'support','FORMATION':'formation','TURN_BEGIN':'battle','BATTLE_RESULT':'battle_result','QUEST_READY':'event_map','CONTINUE':'continue','DEFEATED':'battle_defeated'}
        labels=[item('开始任务',900,550)]
        def read():
            d=scenario.read();d.getAp=lambda:224
            return d,labels,names.get(scenario.state,'unknown')
        runner.read=read
        with patch.object(runner.main,'makeFlow',return_value=flow),patch.object(ec.nav,'labels',return_value=labels),patch.object(ec,'schedule',scenario),patch.object(ec.kernel,'schedule',scenario),patch.object(ec.kernel.XDetect,'region','CN'),patch.object(ec.kernel.friendImg,'flush',return_value=False),patch.object(ec.fgoDevice.device,'touch',side_effect=lambda pos,**kw:scenario.press('8')),patch.object(ec.fgoDevice.device,'press',side_effect=scenario.press):
            try:runner.runBattle();error=None
            except ec.ScriptStop as e:error=e
        return runner,scenario,error
    def test_event_uses_complete_shared_support_formation_battle_settlement(self):
        runner,scenario,error=self.runCycle()
        self.assertIsNone(error)
        self.assertEqual(scenario.actions,[('FRIEND','8'),('FORMATION',' '),('BATTLE_RESULT',' '),('ADD_FRIEND','X'),('CONTINUE','F')])
        self.assertEqual((runner.main.startedBattles,runner.main.completedAttempts,runner.main.wins,runner.main.defeats),(1,1,1,0))
    def test_first_event_defeat_counts_once_and_sends_no_revive(self):
        runner,scenario,error=self.runCycle(True)
        self.assertIsNotNone(error)
        self.assertEqual((runner.main.startedBattles,runner.main.completedAttempts,runner.main.wins,runner.main.defeats),(1,1,0,1))
        self.assertFalse(any(state=='DEFEATED' for state,key in scenario.actions))


class EventContractTests(unittest.TestCase):
    def missionList(self,count=0):
        return [item('任务报酬',699,121,w=89),item('活动道具兑换',1041,125,w=126),item('任务报酬一览',864,185,w=147),item('已达成的任务',629,225,w=158),item(f'{count}/100',828,225,w=83),item('关闭',70,25,w=80),item('可领取',847,260,w=86),item('编号1',1156,276,w=49),item('通关主线关卡第一话',608,312,w=207,score=.84),item('目标进行度',617,353,w=102),item('1/1',609,383,w=36),item('已完成',875,379,w=74)]
    def missionReceipt(self):
        return [item('获得了',592,376,w=95),item('『黄金果实×1』。',533,405,w=236),item('关闭',600,517,w=81,h=46),item('编号1',1156,276,w=49),item('0/100',935,45,w=85)]
    def test_mission_award_receipt_is_not_an_ap_recovery_dialog(self):
        labels=self.missionReceipt();self.assertEqual(event.classifyEventState(labels),'mission_reward_receipt')
        ec.QuartzGuard.check(labels)
        for index in range(4):self.assertIsNone(event.missionRewardReceipt(labels[:index]+labels[index+1:]))
        self.assertIsNone(event.missionRewardReceipt(labels+[item('请选择奖励',400,300)]))
    def test_resumed_mission_award_counts_only_after_proved_increment(self):
        labels=self.missionReceipt();after=[i for i in self.missionList(1) if i.text!='可领取']
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock());runner.touch=Mock()
        runner.read=Mock(return_value=(Mock(),labels,'mission_reward_receipt'));runner.wait=Mock(return_value=(Mock(),after,'mission_list'))
        runner.closeMissionRewardReceipt(None,labels,countResumedClaim=True)
        runner.touch.assert_called_once_with(labels,(640,540),'close_earned_mission_reward')
        self.assertEqual(runner.claimed,1)
    def test_receipt_unlock_tutorial_preserves_increment_proof_and_parent_budget(self):
        labels=self.missionReceipt();after=self.missionList(1)
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock(),clock=lambda:10)
        runner.touch=Mock();runner.read=Mock(return_value=(Mock(),labels,'mission_reward_receipt'))
        tutorial=(Mock(),[], 'event_tutorial');proved=(Mock(),after,'mission_list')
        runner.wait=Mock(side_effect=[tutorial,proved]);runner.advanceTutorial=Mock(return_value=proved)
        runner.closeMissionRewardReceipt(None,labels,countResumedClaim=True)
        runner.advanceTutorial.assert_called_once_with(tutorial[0],tutorial[1],deadline=100)
        self.assertEqual([call.kwargs['deadline'] for call in runner.wait.call_args_list],[100,100])
        self.assertEqual(runner.claimed,1);self.assertEqual(runner.touch.call_count,1)
    def test_receipt_counter_disagreement_cannot_count_a_claim(self):
        labels=self.missionReceipt();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock())
        runner.touch=Mock();runner.read=Mock(return_value=(Mock(),labels,'mission_reward_receipt'));runner.wait=Mock(return_value=(Mock(),self.missionList(0),'mission_list'))
        with self.assertRaises(ec.ScriptStop):runner.closeMissionRewardReceipt(None,labels,countResumedClaim=True)
        self.assertEqual(runner.claimed,0)

    def test_mission_list_requires_its_real_geometry_not_tutorial_embedding(self):
        labels=self.missionList()
        self.assertEqual(event.classifyEventState(labels),'mission_list')
        self.assertEqual(event.findCompletedMissionCard(labels)['mission'],1)
        self.assertIsNone(event.findCompletedMissionCard([i for i in labels if i.text!='已完成']))
        self.assertIsNone(event.findCompletedMissionCard([i for i in labels if i.text!='可领取']))
        self.assertIsNone(event.findCompletedMissionCard([i if i.text!='1/1' else item('0/1',609,383,w=36) for i in labels]))
        self.assertIsNone(event.findCompletedMissionCard(labels+[item('请选择奖励',400,300)]))
        alternate=[i for i in labels if i.text!='任务报酬一览']+[item('全部',1139,227)]
        self.assertEqual(event.classifyEventState(alternate),'mission_list')
        self.assertFalse(event._missionListConfirmed(alternate+[item('关闭',600,517)]))
    def test_mission_claim_defaults_disabled_and_never_inputs(self):
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock());runner.touch=Mock()
        with self.assertRaises(ec.ScriptStop):runner.claimCompletedMission()
        runner.touch.assert_not_called()
    def test_mission_claim_once_requires_three_proofs_and_three_counter_increments(self):
        labels=self.missionList();after=[i for i in self.missionList(1) if i.text!='可领取']
        runner=ec.EventRunner(ec.EventResourcePolicy(),autoClaim=True,ledger=Mock())
        runner.read=Mock(side_effect=[(Mock(),labels,'mission_list')]*3+[(Mock(),after,'mission_list')]*3);runner.touch=Mock()
        self.assertEqual(runner.claimCompletedMission()[2],'mission_list')
        self.assertEqual(runner.claimed,1);self.assertEqual(runner.read.call_count,6)
        runner.touch.assert_called_once_with(labels,(890,272),'claim_completed_event_mission')
    def test_mission_card_ocr_miss_resets_three_frame_confirmation_without_click(self):
        labels=self.missionList();after=[i for i in self.missionList(1) if i.text!='可领取'];clock=Clock()
        runner=ec.EventRunner(ec.EventResourcePolicy(),autoClaim=True,ledger=Mock(),clock=clock)
        runner.read=Mock(side_effect=[(Mock(),labels,'mission_list'),(Mock(),[],'unknown')]+[(Mock(),labels,'mission_list')]*3+[(Mock(),after,'mission_list')]*3);runner.touch=Mock()
        with patch.object(ec,'schedule',clock):runner.claimCompletedMission()
        self.assertEqual(runner.read.call_count,8);self.assertEqual(runner.touch.call_count,1)
    def test_partial_mission_list_background_locks_only_allow_rereading(self):
        labels=[item('关闭',70,25,w=80),item('任务报酬',699,121,w=88),item('活动道具兑换',1041,125,w=126),item('完成任务No.96&通关特定关卡后开放',608,659,w=325)]
        self.assertTrue(event._missionListContext(labels))
        self.assertFalse(event._missionListConfirmed(labels))
        self.assertEqual(event.classifyEventState(labels),'unknown')
        self.assertIsNone(event.findCompletedMissionCard(labels))
        self.assertEqual(event.classifyEventState([item('需要完成任务12才能解锁',400,300)]),'mission_gate')

    def test_generated_close_glyph_requires_both_diagonal_strokes(self):
        import cv2,numpy
        def detector(crop):return Mock(_crop=Mock(return_value=crop))
        crop=numpy.full((31,33,3),240,dtype='uint8')
        cv2.line(crop,(4,3),(28,27),(30,30,30),2);cv2.line(crop,(28,3),(4,27),(30,30,30),2)
        self.assertTrue(ec.tutorialCloseGlyph(detector(crop)))
        for kind in ('empty','solid','single','plus'):
            wrong=numpy.full((31,33,3),240,dtype='uint8')
            if kind=='solid':wrong[3:28,4:29]=30
            if kind=='single':cv2.line(wrong,(4,3),(28,27),(30,30,30),4)
            if kind=='plus':cv2.line(wrong,(4,15),(28,15),(30,30,30),4);cv2.line(wrong,(16,3),(16,27),(30,30,30),4)
            self.assertFalse(ec.tutorialCloseGlyph(detector(wrong)))
    def tutorial(self):
        return [item('点击界面右上方的',304,47,w=229),item('活动报酬按钮',301,79,w=175),item('装备活动限定概念礼装',303,368,w=254),item('推进主线剧情',867,365,w=177),item('前进',1095,651,w=83,h=50),item('完成任务，',734,362),item('达成任务',733,47)]
    def test_event_instructions_are_not_a_mission_unlock_condition(self):
        labels=self.tutorial()
        self.assertEqual(event.findMissionGate(labels),[])
        self.assertEqual(event.classifyEventState(labels),'event_tutorial')
        for index in range(5):self.assertIsNone(event.findEventTutorialNext(labels[:index]+labels[index+1:]))
    def test_event_instruction_forward_is_single_and_stably_proved(self):
        labels=self.tutorial();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock())
        runner.read=Mock(return_value=(Mock(),labels,'event_tutorial'));runner.touch=Mock();runner.wait=Mock(return_value=(None,[],'event_map'))
        runner.advanceTutorial(None,labels);self.assertEqual(runner.read.call_count,2)
        runner.touch.assert_called_once_with(labels,(1136,676),'advance_event_instructions')
        with self.assertRaises(ec.ScriptStop):runner.advanceTutorial(None,labels)
        self.assertEqual(runner.touch.call_count,1)
    def test_second_tutorial_page_is_an_explanation_not_a_claim_control(self):
        labels=[item('任务报酬的领取方法',477,63,w=322),item('点击进度为',772,326,w=159),item('的任务板',1064,329,w=125),item('领取对应报酬',899,369,w=165),item('前进',1096,653,w=81,h=46)]
        self.assertEqual(event.classifyEventState(labels),'event_tutorial')
        self.assertEqual(event.eventTutorialKey(labels),'mission-rewards')
        self.assertIsNone(event.findClaimableMissionReward(labels))
        for index in range(len(labels)):self.assertIsNone(event.findEventTutorialNext(labels[:index]+labels[index+1:]))
    def test_last_tutorial_page_requires_real_close_and_explanatory_structure(self):
        labels=[item('任务列表的显示切换',477,63,w=322),item('列表将进行切换',945,184,w=227),item('每当点击按钮列表中所显示的任务将进行切换',363,593,w=566),item('全部',121,492),item('未开放',348,489),item('可领取',829,493),item('已达成',1073,488),item('x',1219,7,w=54,h=54)]
        self.assertEqual(event.eventTutorialKey(labels),'mission-display')
        self.assertEqual(event.findEventTutorialNext(labels),(1246,34))
        self.assertIsNone(event.findClaimableMissionReward(labels))
        for index in range(len(labels)):self.assertIsNone(event.findEventTutorialNext(labels[:index]+labels[index+1:]))
    def test_post_claim_unlock_instructions_are_not_a_mission_gate(self):
        labels=[item('完成任务后将解锁新任务',443,63,w=388,h=36),item('开放新任务！',985,236,w=168,h=36),item('完成任务不仅可以获得各种奖励，',356,517,w=571,h=40),item('还可以解锁新任务！',427,563,w=373,h=56),item('x',1219,7,w=54,h=54)]
        self.assertEqual(event.classifyEventState(labels),'event_tutorial')
        self.assertEqual(event.eventTutorialKey(labels),'mission-unlock')
        self.assertEqual(event.findEventTutorialNext(labels),(1246,34))
        self.assertFalse(event._missionListConfirmed(labels))
        self.assertIsNone(event.findClaimableMissionReward(labels))
        for index in range(len(labels)):
            self.assertIsNone(event.findEventTutorialNext(labels[:index]+labels[index+1:]))
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock())
        runner.read=Mock(return_value=(Mock(),labels,'event_tutorial'));runner.touch=Mock();runner.wait=Mock(return_value=(None,[],'mission_list'))
        runner.advanceTutorial(None,labels)
        runner.touch.assert_called_once_with(labels,(1246,34),'advance_event_instructions')
        with self.assertRaises(ec.ScriptStop):runner.advanceTutorial(None,labels)
        self.assertEqual(runner.touch.call_count,1)

    def itemDetail(self):
        return [item('概念礼装',1163,63,w=86),item('能力',545,116,w=80),item('详细信息',728,116,w=112),item('持有技能',508,464,w=93),item('关闭',25,26,w=42,h=34)]
    def test_awarded_item_details_only_authorize_positive_close(self):
        labels=self.itemDetail();self.assertEqual(event.classifyEventState(labels),'item_detail')
        for index in range(len(labels)):
            self.assertIsNone(event.findEventItemDetailClose(labels[:index]+labels[index+1:]))
        d=Mock();d._crop.return_value=__import__('numpy').zeros((34,42,3),dtype='uint8')
        with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('关闭',.99)):
            self.assertEqual(event.classifyEventState(ec.itemDetailItems(d,labels[:-1])),'item_detail')
    def test_item_details_close_once_after_three_proofs_without_inventory_action(self):
        labels=self.itemDetail();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock())
        runner.read=Mock(return_value=(Mock(),labels,'item_detail'));runner.touch=Mock();runner.wait=Mock(return_value=(None,[],'event_map'))
        runner.closeItemDetail(None,labels);self.assertEqual(runner.read.call_count,2)
        runner.touch.assert_called_once_with(labels,(46,43),'close_awarded_item_details')
        runner.read=Mock(return_value=(Mock(),labels[:-1],'unknown'));runner.touch.reset_mock()
        with self.assertRaises(ec.ScriptStop):runner.closeItemDetail(None,labels)
        runner.touch.assert_not_called()
    def itemReceipt(self):
        return [item('概念礼装',592,600,w=93),item('生命值',749,609,w=50),item('+200',490,624,w=90),item('请点击游戏界面',507,671,w=269,h=44)]
    def test_ce_receipt_footer_uses_two_strong_reads_without_lowering_threshold(self):
        labels=self.itemReceipt()[:-1];d=Mock();d._crop.return_value=__import__('numpy').zeros((46,270,3),dtype='uint8')
        with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('请点击游戏界面',.99)):
            self.assertEqual(event.classifyEventState(ec.itemReceiptItems(d,labels)),'item_receipt')
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('请点击游戏界面',.99),('请点击游戏界面',.84)]):
            self.assertIsNone(event.findEventItemReceipt(ec.itemReceiptItems(d,labels)))
    def test_ce_receipt_omitted_health_requires_independent_two_scale_read(self):
        labels=[self.itemReceipt()[0],self.itemReceipt()[2]];d=Mock();d._crop.return_value=__import__('numpy').zeros((46,270,3),dtype='uint8')
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('生命值',.99)]*2+[('请点击游戏界面',.99)]*2):
            self.assertEqual(event.classifyEventState(ec.itemReceiptItems(d,labels)),'item_receipt')
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('生命值',.99),('生命值',.84)]):
            self.assertEqual(ec.itemReceiptItems(d,labels),labels)
    def test_automatically_awarded_ce_receipt_needs_all_independent_labels(self):
        labels=self.itemReceipt()
        self.assertEqual(event.classifyEventState(labels),'item_receipt')
        for index in range(len(labels)):
            self.assertIsNone(event.findEventItemReceipt(labels[:index]+labels[index+1:]))
        for forbidden in ('强化','装备','选择','召唤','取消','请选择奖励'):
            self.assertIsNone(event.findEventItemReceipt(labels+[item(forbidden,400,300)]))
    def test_item_receipt_is_dismissed_once_after_three_fresh_proofs(self):
        labels=self.itemReceipt();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock())
        d=Mock(im=__import__('numpy').zeros((720,1280,3),dtype='uint8'))
        runner.read=Mock(return_value=(d,labels,'item_receipt'));runner.touch=Mock();runner.wait=Mock(return_value=(None,[],'event_map'))
        runner.handleRewardReceipt(None,labels)
        self.assertEqual(runner.read.call_count,2)
        runner.touch.assert_called_once_with(labels,(641,693),'dismiss_earned_event_reward_receipt')
        with self.assertRaises(ec.ScriptStop):runner.handleRewardReceipt(None,labels)
        self.assertEqual(runner.touch.call_count,1)
    def test_zero_stat_awarded_ce_is_read_from_its_own_numeric_glyph(self):
        labels=[self.itemReceipt()[0]];d=Mock();d._crop.return_value=__import__('numpy').zeros((46,270,3),dtype='uint8')
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('生命值',.99)]*2+[('0',.99)]*2+[('请点击游戏界面',.99)]*2):
            self.assertEqual(event.classifyEventState(ec.itemReceiptItems(d,labels)),'item_receipt')
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('生命值',.99)]*2+[('+2',.99)]*2):
            self.assertIsNone(event.findEventItemReceipt(ec.itemReceiptItems(d,labels)))
    def storyStart(self):
        return [item('第一话「她是人斩」',472,115,w=328),item('该任务没有战斗',532,300,w=217),item('是否开始任务？',511,475,w=248),item('取消',405,543,w=82,score=.75),item('任务开始',764,544,w=151)]
    def test_story_start_modal_requires_all_joint_evidence(self):
        labels=self.storyStart();d=Mock();d._crop.return_value=__import__('numpy').zeros((48,85,3),dtype='uint8')
        self.assertFalse(event._isStartQuestConfirmation(labels))
        with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('取消',.98)):
            verified=ec.startConfirmationItems(d,labels)
        self.assertEqual(event.classifyEventState(verified),'start_confirmation')
        self.assertEqual(event.findStartQuestConfirmation(verified),(839,556))
        for index in range(len(verified)):
            self.assertIsNone(event.findStartQuestConfirmation(verified[:index]+verified[index+1:]))
    def test_story_start_modal_cannot_promote_weak_or_disagreeing_cancel(self):
        labels=self.storyStart();d=Mock();d._crop.return_value=__import__('numpy').zeros((48,85,3),dtype='uint8')
        for output in ([('取消',.98),('取消',.84)],[('取消',.98),('确定',.98)]):
            with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=output):self.assertFalse(event._isStartQuestConfirmation(ec.startConfirmationItems(d,labels)))
    def test_event_area_list_without_title_stays_context_only_not_node(self):
        labels=[item('关闭',70,25,w=80),item('活动报酬',1127,16),item('APO',783,204),item('无战斗',1139,125),item('关卡举办时间剩余10日',965,236,w=250)]
        self.assertEqual(event.classifyEventState(labels),'event_map')
        self.assertIsNone(event.findNextMainQuest(labels))
        for index in range(len(labels)):
            self.assertNotEqual(event.classifyEventState(labels[:index]+labels[index+1:]),'event_map')
    def test_node_transient_unknown_resets_confirmation_without_input(self):
        labels=[item('第一话「她是人斩」',777,131,w=170),item('关卡举办时间剩余10日',965,236,w=250)]
        clock=Clock();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock(),clock=clock)
        runner.read=Mock(side_effect=[(Mock(),labels,'event_map'),(Mock(),[],'unknown')]+[(Mock(),labels,'event_map')]*3)
        with patch.object(ec,'schedule',clock),patch.object(ec.fgoDevice.device,'touch') as touch:
            self.assertIn('第一话',runner.stableNode()[2]['title']);touch.assert_not_called()
        self.assertEqual(runner.read.call_count,5)
    def test_numbered_event_episode_with_no_battle_is_a_main_node(self):
        labels=[item('第一话「她是人斩」',777,131,w=170),item('无战斗',1139,125),item('AP0',783,204),item('关卡举办时间剩余10日',965,236,w=250)]
        self.assertEqual(event.classifyEventState(labels),'event_map')
        self.assertIn('第一话',event.findNextMainQuest(labels)['title'])
        self.assertIsNone(event.findNextMainQuest(labels+[item('已完成',1050,135)]))
    def test_decorated_episode_title_uses_matching_two_scale_text(self):
        labels=[item('第一话「她是人新」',777,131,w=163,score=.82),item('关卡举办时间剩余10日',965,236,w=250)]
        d=Mock();d._crop.return_value=__import__('numpy').zeros((32,225,3),dtype='uint8')
        with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('第一话「她是人斩」',.86)):
            self.assertIn('人斩',event.findNextMainQuest(ec.mainTitleItems(d,labels))['title'])
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('第一话「她是人斩」',.86),('第一话「她是人新」',.86)]):
            self.assertEqual(ec.mainTitleItems(d,labels),labels)
    def test_decorated_title_read_cannot_promote_a_nonmain_row(self):
        labels=[item('无关自由关卡',777,131,w=163),item('关卡举办时间剩余10日',965,236,w=250)]
        with patch.object(ec.OCR.ZHS,'ocr_single_line') as ocr:
            self.assertEqual(ec.mainTitleItems(Mock(),labels),labels);ocr.assert_not_called()
    def worldMap(self):
        return [item('管理室',70,25,w=80),item('活动报酬',1124,10,w=120),item('已达成的任务',931,12,w=122),item('0/100',1000,45,w=84),item('菜单',1148,633,w=80),item('京都城区',589,403,w=102),item('下一个',583,184,w=114,h=46)]
    def test_world_map_requires_independent_controls_and_main_interface(self):
        labels=self.worldMap()
        self.assertEqual(event.classifyEventState(labels,{'main_interface':True}),'event_world_map')
        self.assertEqual(event.classifyEventState(labels),'unknown')
        for index in (0,1,4):
            self.assertFalse(event.eventWorldMapControls(labels[:index]+labels[index+1:]))
        self.assertEqual(event.classifyEventState([i for j,i in enumerate(labels) if j not in (2,3)],{'main_interface':True}),'event_world_map')
        self.assertEqual(event.findNextEventArea(labels),{'title':'京都城区','position':(640,415)})
        self.assertIsNone(event.findNextMainQuest(labels))
        self.assertIsNone(event.findNextEventArea(labels[:-1]))
    def test_world_map_duplicate_area_or_marker_never_selects(self):
        labels=self.worldMap()
        self.assertIsNone(event.findNextEventArea(labels+[item('别的区域',590,400,w=100)]))
        self.assertIsNone(event.findNextEventArea(labels+[item('下一个',600,200)]))
    def test_world_map_local_arrow_requires_two_strong_matching_reads(self):
        labels=self.worldMap()[:-1];d=Mock();d.isMainInterface.return_value=True
        d._crop.return_value=__import__('numpy').zeros((46,114,3),dtype='uint8')
        with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('下一个',.99)):
            self.assertIsNotNone(event.findNextEventArea(ec.worldMapItems(d,labels)))
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('下一个',.99),('下一个',.84)]*9):
            self.assertIsNone(event.findNextEventArea(ec.worldMapItems(d,labels)))
    def test_world_map_area_requires_three_proofs_then_one_safe_area_touch(self):
        labels=self.worldMap();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock())
        runner.read=Mock(return_value=(Mock(),labels,'event_world_map'));runner.touch=Mock();runner.wait=Mock(return_value=(None,[],'event_map'))
        runner.openNextArea()
        self.assertEqual(runner.read.call_count,3)
        runner.touch.assert_called_once_with(labels,(640,415),'open_next_event_area')
        runner.read=Mock(return_value=(Mock(),labels[:-1],'event_world_map'));runner.touch.reset_mock()
        with self.assertRaises(ec.ScriptStop):runner.openNextArea()
        runner.touch.assert_not_called()
    def receipt(self):
        return [item('任务完成',200,76,w=380),item('获得报酬',716,75,w=387),item('获得 圣晶石×1！',419,491,w=445),item('请点击游戏界面',505,627,w=271)]
    def test_quartz_earned_receipt_is_not_a_resource_consumption_confirmation(self):
        labels=self.receipt()
        self.assertEqual(event.classifyEventState(labels),'reward_receipt')
        ec.QuartzGuard.check(labels)
        for remove in range(4):self.assertIsNone(event.findEventRewardReceipt(labels[:remove]+labels[remove+1:]))
        self.assertIsNone(event.findEventRewardReceipt(labels+[item('请选择奖励',400,400)]))
        with self.assertRaises(ec.ScriptStop):ec.QuartzGuard.check(labels+[item('是否消耗圣晶石恢复AP',400,300)])
    def test_partial_completion_receipt_is_not_a_mission_gate(self):
        self.assertEqual(event.classifyEventState([item('任务完成',200,76,w=380)]),'unknown')
        self.assertEqual(event.classifyEventState([item('需要完成任务12才能解锁',400,300)]),'mission_gate')
    def test_reward_receipt_only_dismisses_once_after_three_proofs(self):
        labels=self.receipt();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock())
        runner.read=Mock(return_value=(Mock(),labels,'reward_receipt'));runner.touch=Mock();runner.wait=Mock(return_value=(None,[],'event_map'))
        runner.handleRewardReceipt(None,labels)
        self.assertEqual(runner.read.call_count,2)
        runner.touch.assert_called_once_with(labels,(640,639),'dismiss_earned_event_reward_receipt')
    def test_earned_reward_summary_accepts_positive_awarded_card_as_next_phase(self):
        labels=self.receipt();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock())
        runner.read=Mock(return_value=(Mock(),labels,'reward_receipt'));runner.touch=Mock();runner.wait=Mock(return_value=(None,[],'item_receipt'))
        self.assertEqual(runner.handleRewardReceipt(None,labels)[2],'item_receipt')
        self.assertIn('item_receipt',runner.wait.call_args.args[0]);runner.touch.assert_called_once()
    def test_receipt_transient_ocr_miss_requires_three_new_positive_reads(self):
        labels=self.receipt();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock())
        runner.read=Mock(side_effect=[(Mock(),labels[:3],'unknown')]+[(Mock(),labels,'reward_receipt')]*3)
        runner.touch=Mock();runner.wait=Mock(return_value=(None,[],'event_map'))
        clock=Clock();runner.clock=clock
        with patch.object(ec,'schedule',clock):runner.handleRewardReceipt(None,labels)
        self.assertEqual(runner.read.call_count,4);runner.touch.assert_called_once()
    def test_capture_reset_and_exhausted_stream_stop_without_any_input(self):
        for failure in (ConnectionResetError('synthetic reset'),StopIteration()):
            runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock(),reader=Mock(side_effect=failure))
            with patch.object(ec.fgoDevice.device,'touch') as touch:
                with self.assertRaises(ec.EventCaptureError):runner.read()
                touch.assert_not_called()
    def test_capture_failure_report_retains_incomplete_stats_and_stops_owner(self):
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock())
        runner.openMap=Mock(side_effect=ec.EventCaptureError('lost capture'));runner.evidence=Mock()
        with patch.object(ec.fgoDevice.device,'touch') as touch:
            result=runner.run(1)
            self.assertEqual(result['state'],'blocked');self.assertEqual(result['captureFailures'],1)
            self.assertEqual(result['stats']['completedAttempts'],0);touch.assert_not_called()
    def partyReview(self):
        return [item('队伍编制',1045,10),item('受限',605,25,w=75),item('拖动修改从者配置。',525,620),item('取消',103,660),item('决定',1130,650)]
    def test_actual_temporary_party_review_overrides_background_formation(self):
        labels=self.partyReview()
        self.assertEqual(event.classifyEventState(labels,{'formation':True}),'formation_review')
        self.assertEqual(event.findTemporaryPartyDecision(labels),(1200,662))
        self.assertIsNone(event.findEventBattleStart(labels))
        self.assertIsNone(event.findTemporaryPartyDecision(labels[1:]))
    def test_temporary_party_decision_requires_three_stable_proofs_and_single_touch(self):
        labels=self.partyReview();runner=ec.EventRunner(ec.EventResourcePolicy(allowTemporaryAutoFormation=True),ledger=Mock())
        runner.read=Mock(return_value=(Mock(),labels,'formation_review'));runner.touch=Mock()
        runner.wait=Mock(return_value=(Mock(),[item('战斗开始',1110,650)],'formation'))
        runner.confirmTemporaryParty(None,labels)
        self.assertEqual(runner.read.call_count,2)
        runner.touch.assert_called_once_with(labels,(1200,662),'confirm_temporary_event_party')
    def autoSettings(self):
        return [item('受限',605,25,w=75),item('自动编成',565,115),item('基于职阶相性考虑的基础上，优先',395,185),item('自动编成攻击力高的从者。',445,220),item('编队方法',250,440),item('取消',315,543),item('详细设定',570,543),item('自动编成',860,544)]
    def test_temporary_auto_party_permission_defaults_off_and_never_inputs(self):
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock())
        self.assertFalse(runner.policy.allowTemporaryAutoFormation)
        with patch.object(ec.fgoDevice.device,'touch') as touch:
            with self.assertRaises(ec.ScriptStop):runner.configureTemporaryParty(None,self.autoSettings(),'formation_settings')
            touch.assert_not_called()
    def test_allowed_temporary_auto_requires_restricted_settings_and_touches_once(self):
        labels=self.autoSettings();runner=ec.EventRunner(ec.EventResourcePolicy(allowTemporaryAutoFormation=True),ledger=Mock())
        runner.read=Mock(return_value=(Mock(),labels,'formation_settings'));runner.touch=Mock()
        runner.wait=Mock(return_value=(Mock(),[labels[0]],'formation'))
        self.assertEqual(runner.configureTemporaryParty(None,labels,'formation_settings')[2],'formation')
        runner.touch.assert_called_once_with(labels,(930,556),'auto_form_isolated_event_party')
        with self.assertRaises(ec.ScriptStop):runner.configureTemporaryParty(None,labels[1:],'formation_settings')
        self.assertEqual(runner.touch.call_count,1)
    def test_temporary_auto_settings_instability_does_not_input(self):
        labels=self.autoSettings();runner=ec.EventRunner(ec.EventResourcePolicy(allowTemporaryAutoFormation=True),ledger=Mock())
        runner.read=Mock(return_value=(Mock(),labels[1:],'formation_settings'));runner.touch=Mock()
        with self.assertRaises(ec.ScriptStop):runner.configureTemporaryParty(None,labels,'formation_settings')
        runner.touch.assert_not_called()
    def test_allowed_special_offer_uses_isolated_party_proof_and_single_game_auto(self):
        labels=self.specialOffer();runner=ec.EventRunner(ec.EventResourcePolicy(allowTemporaryAutoFormation=True),ledger=Mock())
        runner.read=Mock(return_value=(Mock(),labels,'special_formation_offer'));runner.touch=Mock();runner.wait=Mock(return_value=(None,[],'formation'))
        runner.configureSpecialFormation(None,labels)
        runner.touch.assert_called_once_with(labels,(940,602),'auto_form_isolated_event_party')
    def test_auto_formation_settings_cannot_expose_background_start(self):
        labels=[item('自动编成',565,115),item('基于职阶相性考虑的基础上，优先',395,185),item('自动编成攻击力高的从者。',445,220),item('编队方法',250,440),item('战斗开始',1110,650)]
        self.assertEqual(event.classifyEventState(labels,{'formation':True}),'formation_settings')
        self.assertIsNone(event.findEventBattleStart(labels))
        self.assertFalse(event.isEventAutoFormationSettings(labels[1:]))
    def test_empty_restricted_starting_slots_do_not_authorize_start(self):
        labels=[item('受限',604,25,w=75),item('选择',303,288,w=61),item('选择',503,288,w=61),item('战斗开始',1110,650)]
        self.assertTrue(event.isEventIncompleteFormation(labels))
        self.assertIsNone(event.findEventBattleStart(labels))
        self.assertIsNotNone(event.findEventBattleStart([labels[0],labels[-1]]))
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock())
        with patch.object(ec.nav,'labels',return_value=labels),patch.object(ec.fgoDevice.device,'press') as press:
            with self.assertRaises(ec.ScriptStop):runner.main.prepareFormation(Mock())
            press.assert_not_called()
    def test_actual_formation_refusal_overrides_background_start_and_formation(self):
        labels=[item('先发成员不足',530,80),item('先发成员需要凑足3人',460,215),item('才可开始执行任务。',470,255),item('战斗开始',1110,650)]
        self.assertEqual(event.classifyEventState(labels,{'formation':True}),'formation_blocked')
        self.assertFalse(event.isEventFormationBlocked(labels[1:]))
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock())
        with patch.object(ec.nav,'labels',return_value=labels),patch.object(ec.fgoDevice.device,'press') as press:
            with self.assertRaises(ec.ScriptStop):runner.main.prepareFormation(Mock())
            press.assert_not_called()
    def test_failed_skip_departure_is_not_a_completed_story_segment(self):
        labels=[item('是否跳过该段剧情？',450,300,w=350),item('否',430,540,w=45),item('是',805,540,w=45)]
        runner=object.__new__(ec.EventRunner);runner.touch=Mock();runner.waitAfterSkip=Mock(side_effect=FlowTimeout('persistent story'));runner.storySegments=0;runner.ledger=Mock(data={'records':[]})
        with self.assertRaises(FlowTimeout):runner.handleTransition(None,labels,'story_skip_confirmation')
        self.assertEqual(runner.storySegments,0)
        runner.ledger.append.assert_not_called()
    def test_legacy_prebattle_story_pause_never_skips(self):
        runner=object.__new__(ec.EventRunner);runner.storyMode='pause';runner.touch=Mock()
        with self.assertRaises(ec.ScriptStop):runner.handleTransition(None,[],'story_skip_confirmation')
        runner.touch.assert_not_called()
    def specialOffer(self):
        return [item('自动编成执行确认',500,70),item('该关卡为不使用通常编队设置',430,145),item('的特殊关卡。',510,175),item('是否进行自动编队？',490,310),item('不进行自动编成',250,590),item('详细设定',580,590),item('自动编成',870,590)]
    def test_special_event_offer_proves_nonstandard_party_and_only_negative_route(self):
        labels=self.specialOffer()
        self.assertEqual(event.classifyEventState(labels,{'formation':True}),'special_formation_offer')
        self.assertEqual(event.findSpecialFormationDecline(labels),(320,602))
        self.assertIsNone(event.findSpecialFormationDecline(labels[1:]))
    def test_special_event_decline_never_automatically_replaces_party(self):
        labels=self.specialOffer();runner=object.__new__(ec.EventRunner)
        runner.read=Mock(return_value=(Mock(),labels,'special_formation_offer'));runner.touch=Mock();runner.wait=Mock()
        runner.declineSpecialFormation(None,labels)
        runner.touch.assert_called_once_with(labels,(320,602),'decline_special_auto_formation')
    def test_actual_story_skip_yes_no_producer_requires_phrase_and_both_controls(self):
        labels=[item('是否跳过该段剧情？',450,300,w=350),item('否',430,540,w=45),item('是',805,540,w=45,score=.66)]
        d=Mock();d._crop.return_value=__import__('numpy').zeros((57,54,3),dtype='uint8')
        with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('是',.99)):
            verified=ec.skipConfirmationItems(d,labels)
            self.assertEqual(event.classifyEventState(verified),'story_skip_confirmation')
            self.assertEqual(event.findSkipConfirmation(verified),(827,560))
            self.assertEqual(ec.skipConfirmationItems(d,labels[1:]),labels[1:])
        with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('是',.84)):
            self.assertIsNone(event.findSkipConfirmation(ec.skipConfirmationItems(d,labels)))
    def test_resuming_skip_confirmation_does_not_touch_skip_again(self):
        labels=[item('是否跳过该段剧情？',450,300,w=350),item('否',430,540,w=45),item('是',805,540,w=45)]
        runner=object.__new__(ec.EventRunner);runner.touch=Mock();runner.waitAfterSkip=Mock(return_value=(None,[],'support'));runner.storySegments=0;runner.ledger=Mock(data={'records':[]})
        runner.handleTransition(None,labels,'story_skip_confirmation')
        self.assertEqual(runner.touch.call_count,1)
        self.assertEqual(runner.touch.call_args.args[2],'confirm_story_skip')
    def storyWait(self,lines,reference):
        clock=Clock();runner=object.__new__(ec.EventRunner);runner.clock=clock
        d=Mock();d.im=__import__('numpy').ones((720,1280,3),dtype='uint8')*80
        iterator=iter(lines);last=lines[-1]
        def read():return d,[item(next(iterator,last),300,580,w=300)],'story'
        runner.read=read
        with patch.object(ec,'schedule',clock):return runner.waitAfterSkip(reference,deadline=1)
    def test_same_story_after_confirmation_does_not_rearm_skip(self):
        a=ec.storySignature([item('synthetic old dialogue',300,580,w=300)])
        with self.assertRaises(FlowTimeout):self.storyWait(['synthetic old dialogue'],a)
    def test_two_consecutive_story_segments_require_three_stable_new_reads(self):
        a=ec.storySignature([item('synthetic old dialogue',300,580,w=300)])
        self.assertEqual(self.storyWait(['synthetic old dialogue','synthetic new dialogue','synthetic new dialogue','synthetic new dialogue'],a)[2],'story')
    def test_story_signature_one_frame_flicker_does_not_create_episode(self):
        a=ec.storySignature([item('synthetic old dialogue',300,580,w=300)])
        with self.assertRaises(FlowTimeout):self.storyWait(['synthetic new dialogue','synthetic old dialogue'],a)
    def test_unknown_story_control_miss_recovers_by_reading_only(self):
        clock=Clock();runner=object.__new__(ec.EventRunner);runner.clock=clock;runner.read=Mock(side_effect=[(Mock(),[],'unknown'),(Mock(),[],'story')])
        with patch.object(ec,'schedule',clock),patch.object(ec,'startupInfoClose',return_value=None),patch.object(ec.nav,'safeMenuPageCN',return_value='UNKNOWN'),patch.object(ec.nav,'normalizeToTerminalCN') as normalize,patch.object(ec.fgoDevice.device,'touch') as touch:
            self.assertEqual(runner.openMap()[2],'story');normalize.assert_not_called();touch.assert_not_called()
    def test_story_skip_arrow_requires_independent_text_and_dialogue_controls(self):
        labels=[item('跳过|',1150,20,w=85,score=.73),item('自动',1200,620,w=40),item('有人吗，有人在吗？',300,580,w=300)]
        d=Mock();d._crop.return_value=__import__('numpy').zeros((40,65,3),dtype='uint8')
        with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('跳过',.99)):
            verified=ec.storyItems(d,labels)
            self.assertEqual(event.findSkipButton(verified),(1192,40))
            self.assertEqual(event.classifyEventState(verified),'story')
            self.assertEqual(ec.storyItems(d,labels[:1]),labels[:1])
            self.assertIsNotNone(event.findSkipButton(ec.storyItems(d,labels[1:])))
        with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('跳过',.84)):
            self.assertIsNone(event.findSkipButton(ec.storyItems(d,labels)))
    def test_weekly_update_notice_closes_not_opens_mission_panel(self):
        labels=[item('御主任务已更新。',490,280),item('来挑战最新的御主任务吧。',415,315),item('关闭',400,550,w=80),item('前往御主任务界面',720,550)]
        self.assertEqual(ec.weeklyUpdateInfoClose(labels),(440,562))
        self.assertIsNone(ec.weeklyUpdateInfoClose(labels[1:]))
    def test_persistent_startup_notice_does_not_reclick(self):
        labels=[item('御主任务已更新。',490,280),item('来挑战最新的御主任务吧。',415,315),item('关闭',400,550,w=80),item('前往御主任务界面',720,550)]
        clock=Clock();runner=object.__new__(ec.EventRunner);runner.clock=clock
        runner.read=Mock(return_value=(Mock(),labels,'unknown'));runner.touch=Mock()
        with patch.object(ec,'schedule',clock),patch.object(ec,'startupInfoClose',return_value=(440,562)),patch.object(ec.nav,'terminalHomeCN',return_value=False):
            with self.assertRaises(FlowTimeout):runner.openMap()
        runner.touch.assert_called_once()
    def test_sdk_guide_only_closes_verified_corner_not_shop_tiles_or_checkbox(self):
        labels=[item('游玩指引',30,170),item('最新情报',30,245),item('查找攻略',30,320),item('本月不再提示',40,650)]
        d=Mock();d._crop.return_value=__import__('numpy').zeros((54,54,3),dtype='uint8')
        with patch.object(ec.OCR.EN,'ocr_single_line',return_value=('x',.94)):
            self.assertEqual(ec.guideInfoClose(d,labels),(1246,34))
            self.assertIsNone(ec.guideInfoClose(d,labels[:2]))
        with patch.object(ec.OCR.EN,'ocr_single_line',return_value=('x',.84)):
            self.assertIsNone(ec.guideInfoClose(d,labels))
    def test_promotion_description_is_only_dismissible_not_reward_selection(self):
        labels=[item('开幕前夕纪念活动',580,110),item('举办中！',760,140),item('可从5种素材中任选其一',650,240),item('举办时间：2026年10月4日',550,490),item('关闭',600,550,w=80)]
        self.assertEqual(ec.promotionalInfoClose(labels),(640,562))
        ec.QuartzGuard.check(labels,dismissNotice=True)
        with self.assertRaises(ec.ScriptStop):ec.QuartzGuard.check(labels)
        self.assertIsNone(ec.promotionalInfoClose(labels+[item('兑换',800,550)]))
        with self.assertRaises(ec.ScriptStop):ec.QuartzGuard.check([item('请选择奖励',400,300)],dismissNotice=True)
    def test_login_reward_notice_only_dismisses_already_awarded_information(self):
        labels=[item('连续登录奖励',530,120),item('※请在礼物盒中领取。',540,480),item('获得了第1日的登录奖励！',530,455),item('关闭',600,550,w=80)]
        self.assertEqual(ec.loginRewardInfoClose(labels),(640,562))
        self.assertIsNone(ec.loginRewardInfoClose(labels+[item('请选择奖励',400,300)]))
        self.assertIsNone(ec.loginRewardInfoClose(labels[:2]+labels[3:]))
    def test_event_login_notice_does_not_click_summon_advertisement(self):
        labels=[item('开幕纪念登录奖励',530,150),item('请在礼物盒中领取。',540,480),item('已获得第8次的登录奖励！',530,445),item('关闭',600,550,w=80),item('推荐召唤',980,550)]
        self.assertEqual(ec.loginRewardInfoClose(labels),(640,562))
        runner=object.__new__(ec.EventRunner)
        with patch.object(ec.fgoDevice.device,'touch') as touch:
            with self.assertRaises(ec.ScriptStop):runner.touch(labels,(1050,570),'wrong',dismissNotice=True)
            touch.assert_not_called()
    def test_bulletin_title_alone_does_not_authorize_close(self):
        self.assertIsNone(ec.announcementClose(Mock(),[item('游戏公告',550,15)]))
    def test_bulletin_requires_independent_glyph_two_scale(self):
        d=Mock();d._crop.side_effect=lambda box:__import__('numpy').zeros((20,30,3),dtype='uint8')
        labels=[item('游戏公告',550,15),item('X',1220,10,w=50,score=.76)]
        with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('游戏公告',.96)),patch.object(ec.OCR.EN,'ocr_single_line',side_effect=[('x',.86),('x',.87)]):
            self.assertEqual(ec.announcementClose(d,labels),(1245,22))
        with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('游戏公告',.96)),patch.object(ec.OCR.EN,'ocr_single_line',side_effect=[('x',.86),('x',.84)]):
            self.assertIsNone(ec.announcementClose(d,labels))
    def test_ledger_atomic_reload_never_executes_input(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(ec.fgoDevice.device,'touch') as touch:
            path=Path(folder)/'ledger.json';ec.ProgressLedger(path).append('node',title='synthetic')
            loaded=ec.ProgressLedger(path)
            self.assertEqual(loaded.data['records'][0]['title'],'synthetic');touch.assert_not_called()
            self.assertFalse(path.with_suffix('.tmp').exists())
    def test_start_confirmation_requires_phrase_and_unique_controls(self):
        labels=[item('是否开始关卡？',400,200),item('开始',800,500),item('取消',400,500)]
        self.assertTrue(event._isStartQuestConfirmation(labels))
        self.assertFalse(event._isStartQuestConfirmation(labels+[item('开始',900,500)]))
    def test_authorized_confirmation_touches_once_then_observes(self):
        labels=[item('是否开始关卡？',400,200),item('开始',800,500),item('取消',400,500)]
        runner=object.__new__(ec.EventRunner);runner.touch=Mock();runner.wait=Mock(return_value=(None,[],'story'))
        runner.handleTransition(None,labels,'start_confirmation')
        runner.touch.assert_called_once();runner.wait.assert_called_once()
        self.assertNotIn('event_map',runner.wait.call_args.args[0])
    def test_fading_map_cannot_complete_start_wait(self):
        clock=Clock();runner=object.__new__(ec.EventRunner);runner.clock=clock
        fading=Mock();fading.isMainInterface.return_value=True;fading.getAp.return_value=229
        labels=[];runner.read=Mock(return_value=(fading,labels,'event_map'))
        with patch.object(ec,'schedule',clock):
            with self.assertRaises(FlowTimeout):runner.wait({'story','support','formation','battle','ap_empty'},timeout=1)
    def test_map_boundary_requires_three_fresh_hud_captures(self):
        clock=Clock();runner=object.__new__(ec.EventRunner);runner.clock=clock
        d=Mock();d.isMainInterface.return_value=True;d.getAp.return_value=224
        runner.read=Mock(return_value=(d,[],'event_map'))
        with patch.object(ec,'schedule',clock):runner.wait({'event_map'},timeout=1)
        self.assertEqual(runner.read.call_count,3)
    def test_wait_rejects_fading_formation_without_positive_start_control(self):
        clock=Clock();runner=object.__new__(ec.EventRunner);runner.clock=clock
        ready=[item('战斗开始',1110,650)]
        runner.read=Mock(side_effect=[(Mock(),[],'formation'),(Mock(),ready,'formation')])
        with patch.object(ec,'schedule',clock):
            result=runner.wait({'formation'},timeout=1,accept=lambda d,i,s:event.findEventBattleStart(i) is not None)
        self.assertIs(result[1],ready);self.assertEqual(runner.read.call_count,2)
    def test_plain_confirm_not_a_start_producer(self):
        labels=[item('是否购买？',400,200),item('开始',800,500),item('取消',400,500)]
        runner=object.__new__(ec.EventRunner);runner.touch=Mock()
        with self.assertRaises(ec.ScriptStop):runner.handleTransition(None,labels,'start_confirmation')
        runner.touch.assert_not_called()
    def test_actual_node_restriction_does_not_authorize_team_change(self):
        labels=[item('序幕 Goodbye 池田屋',760,130),item('AP5',760,200),item('编制需符合要求',640,220)]
        node=event.findNextMainQuest(labels)
        self.assertTrue(node['restrictions'])
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock())
        self.assertEqual(runner.main.teamIndex,0);self.assertFalse(runner.main.autoFormation)
    def test_unparsed_mission_has_no_invented_requirement(self):
        self.assertIsNone(ec.MissionRequirement.parse('未完成任务条件'))
    def test_explicit_mission_requirement_is_not_quest_mapping(self):
        r=ec.MissionRequirement.parse('任务 12 需要击败 10 个 骷髅')
        self.assertEqual((r.mission,r.kind,r.target,r.count),('12','击败','骷髅',10))
    def test_unapproved_legacy_api_does_not_call_authorized_runner(self):
        with patch.object(ec.EventRunner,'run') as run,patch.object(event.XDetect,'region','JP'):
            event.progress()
            run.assert_not_called()


if __name__=='__main__':unittest.main()


class LedgerIoTests(unittest.TestCase):
    def test_transient_destination_lock_retries_only_file_replace(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'ledger.json';ledger=ec.ProgressLedger(path)
            original=Path.replace;calls=[]
            def replace(p,target):
                calls.append(target)
                if len(calls)<3:raise PermissionError('synthetic destination lock')
                return original(p,target)
            with patch.object(Path,'replace',replace),patch.object(ec.time,'sleep') as sleep:
                ledger.append('node',title='synthetic')
            self.assertEqual(len(calls),3);self.assertEqual(sleep.call_count,2)
            self.assertEqual(len(ec.ProgressLedger(path).data['records']),1)
    def test_persistent_destination_lock_stops_with_previous_ledger_intact(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'ledger.json';ledger=ec.ProgressLedger(path);ledger.append('node',title='old')
            old=path.read_bytes()
            with patch.object(Path,'replace',side_effect=PermissionError('synthetic lock')) as replace,patch.object(ec.time,'sleep'):
                with self.assertRaises(PermissionError):ledger.append('node',title='new')
            self.assertEqual(replace.call_count,5);self.assertEqual(path.read_bytes(),old)
            self.assertTrue(path.with_suffix('.tmp').exists())
    def test_input_ledger_failure_prevents_physical_touch(self):
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock())
        runner.ledger.append.side_effect=PermissionError('synthetic lock')
        with patch.object(ec.fgoDevice,'device',Mock()) as device,patch.object(ec.schedule,'checkStop'):
            with self.assertRaises(PermissionError):runner.touch([], (100,100),'synthetic')
        device.touch.assert_not_called()


class ShortStoryTests(unittest.TestCase):
    def test_short_real_dialogue_with_verified_skip_is_story(self):
        labels=[item('跳过',1160,20,w=65),item('皇都神剑组？',89,580,w=278,h=43)]
        self.assertEqual(event.classifyEventState(labels),'story')
        self.assertIsNotNone(ec.storySignature(labels))
    def test_upper_caption_does_not_supply_dialogue_proof(self):
        labels=[item('跳过',1160,20,w=65),item('皇都神剑组？',89,450,w=278,h=43)]
        self.assertEqual(event.classifyEventState(labels),'unknown')
        self.assertIsNone(ec.storySignature(labels))


class EarnedServantTests(unittest.TestCase):
    def labels(self):
        return [item('Lancer',582,546,w=122,h=39),item('攻击力',471,607,w=76,h=24),item('生命值',741,603,w=73,h=31),item('1382',503,628,w=81,h=32),item('2142',697,629,w=74,h=28),item('请点击游戏界面',505,669,w=271,h=47)]
    def test_observed_earned_card_requires_class_stats_and_footer(self):
        labels=self.labels()
        self.assertEqual(event.classifyEventState(labels),'item_receipt')
        self.assertEqual(event.findEventServantReceipt(labels),(1000,690))
        for index in range(len(labels)):
            self.assertIsNone(event.findEventServantReceipt(labels[:index]+labels[index+1:]))
        self.assertIsNone(event.findEventServantReceipt(labels+[item('召唤',900,500)]))
        self.assertIsNone(event.findEventBattleStart(labels))
    def test_missing_class_and_health_are_verified_at_two_scales(self):
        import numpy
        labels=self.labels()[1:2]+self.labels()[3:];d=Mock(_crop=Mock(return_value=numpy.zeros((32,80,3),dtype='uint8')))
        with patch.object(ec.OCR.EN,'ocr_single_line',return_value=('Lancer',.99)),patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('生命值',.99)):
            self.assertEqual(event.classifyEventState(ec.servantReceiptItems(d,labels)),'item_receipt')
        with patch.object(ec.OCR.EN,'ocr_single_line',side_effect=[('Lancer',.99),('ancer',.99)]):
            self.assertEqual(ec.servantReceiptItems(d,labels),labels)


class TemporaryServantInfoTests(unittest.TestCase):
    def test_actual_passive_notice_has_its_own_joint_producer(self):
        labels=[item('～关于暂时加人状态的从者～',405,129,w=470,h=35),item('活动期间限时加入。',472,305,w=313,h=39),item('在活动中通关特定关卡后',437,395,w=408,h=36),item('即可正式加人。',507,435,w=244,h=42),item('关闭',600,541,w=81,h=46)]
        self.assertEqual(event.classifyEventState(labels),'event_tutorial')
        self.assertEqual(event.eventTutorialKey(labels),'temporary-servant-info')
        self.assertEqual(event.findEventTutorialNext(labels),(640,564))
        for index in range(len(labels)):
            self.assertIsNone(event.findTemporaryServantNoticeClose(labels[:index]+labels[index+1:]))
        self.assertIsNone(event.findTemporaryServantNoticeClose(labels+[item('请选择奖励',500,250)]))
    def test_second_line_inside_real_dialogue_panel_supplies_body_evidence(self):
        labels=[item('跳过',1160,20,w=65),item('啊，',89,587,w=56,h=37),item('我也没打算在这里久留。',89,644,w=372,h=37)]
        self.assertEqual(event.classifyEventState(labels),'story')
        self.assertIsNotNone(ec.storySignature(labels))


class ServantDetailTests(unittest.TestCase):
    def test_actual_servant_information_page_only_proves_close(self):
        labels=[item('能力',545,117,w=80),item('资料',745,116,w=79),item('战斗形象',931,119,w=110),item('语音',1142,116,w=84),item('枪兵',1203,61,w=49),item('持有技能',509,597,w=98),item('关闭',7,25,w=64,h=33)]
        self.assertEqual(event.classifyEventState(labels),'item_detail')
        self.assertEqual(event.findEventItemDetailClose(labels),(39,41))
        for index in range(len(labels)):
            self.assertIsNone(event.findEventItemDetailClose(labels[:index]+labels[index+1:]))
        self.assertIsNone(event.findEventBattleStart(labels))


class LockedQuestMissionTests(unittest.TestCase):
    def labels(self):
        return [item('活动报酬',1127,15,w=116),item('完成任务No.11后开放',831,176,w=198),item('关卡举办时间剩余10日',969,240,w=243),item('AP5',784,204,w=51),item('主线关卡 第三话',780,130,w=220),item('关闭',70,25,w=80),item('菜单',1148,633,w=80),item('任务进行度',924,365,w=81),item('AP40',785,392,w=62)]
    def test_actual_locked_card_is_requirement_not_selectable_next_node(self):
        labels=self.labels()
        self.assertEqual(event.classifyEventState(labels,{'main_interface':True}),'mission_gate')
        self.assertEqual(event.findLockedEventMission(labels)['mission'],11)
        self.assertIsNone(event.findNextMainQuest(labels))
        self.assertIsNone(event.findLockedEventMission(labels+[item('完成任务No.12后开放',850,180)]))
    def test_requirement_menu_is_one_touch_after_three_real_proofs(self):
        labels=self.labels();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock())
        runner.read=Mock(return_value=(Mock(),labels,'mission_gate'));runner.touch=Mock();runner.wait=Mock(return_value=(Mock(),[],'mission_list'))
        runner.openMissionRequirements(None,labels)
        runner.touch.assert_called_once_with(labels,(1185,27),'open_locked_quest_mission_requirements')
        runner.read=Mock(return_value=(Mock(),[],'unknown'));runner.touch.reset_mock()
        clock=Clock();runner.clock=clock
        with patch.object(ec,'schedule',clock),self.assertRaises(ec.ScriptStop):runner.openMissionRequirements(None,labels)
        runner.touch.assert_not_called()


class MissionNavigationTransitionTests(unittest.TestCase):
    def test_verified_menu_input_can_wait_for_its_same_fading_lock_page(self):
        labels=LockedQuestMissionTests().labels();clock=Clock();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock(),clock=clock)
        runner.read=Mock(side_effect=[(Mock(),labels,'mission_gate'),(Mock(),[],'unknown'),(Mock(),[],'mission_list')])
        with patch.object(ec,'schedule',clock):
            result=runner.wait({'mission_list'},blockedIntermediate=lambda d,i,s:event.findLockedEventMission(i) is not None)
        self.assertEqual(result[2],'mission_list');self.assertEqual(runner.read.call_count,3)
    def test_unscoped_mission_blocker_still_stops_immediately(self):
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock());runner.read=Mock(return_value=(Mock(),[],'mission_gate'))
        with self.assertRaises(ec.ScriptStop):runner.wait({'mission_list'})
        self.assertEqual(runner.read.call_count,1)


class MissionScrollbarTests(unittest.TestCase):
    def test_real_geometry_has_exactly_one_bounded_white_thumb(self):
        import numpy
        im=numpy.zeros((720,1280,3),dtype='uint8');im[539:566,1255:1268]=240
        self.assertEqual(ec.missionScrollThumb(im),(539,566))
        im[280:307,1255:1268]=240
        with self.assertRaises(ec.ScriptStop):ec.missionScrollThumb(im)
        with self.assertRaises(ec.ScriptStop):ec.missionScrollThumb(im[:700])
    def test_mission_top_scroll_is_once_after_three_proofs(self):
        import numpy
        im=numpy.zeros((720,1280,3),dtype='uint8');im[539:566,1255:1268]=240
        top=numpy.zeros_like(im);top[267:294,1255:1268]=240
        labels=EventContractTests().missionList()+[item('全部',1137,227,w=56)]
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock())
        runner.read=Mock(side_effect=[(Mock(im=im),labels,'mission_list')]*3+[(Mock(im=top),labels,'mission_list')]*3)
        with patch.object(ec.daily,'_menuSwipe') as swipe:runner.missionListTop()
        swipe.assert_called_once_with((1261,552),(1261,266))
        self.assertEqual(runner.read.call_count,6)
    def test_stationary_mission_scrollbar_stops_without_repeating_input(self):
        import numpy
        im=numpy.zeros((720,1280,3),dtype='uint8');im[539:566,1255:1268]=240
        labels=EventContractTests().missionList()+[item('全部',1137,227,w=56)]
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock());runner.read=Mock(return_value=(Mock(im=im),labels,'mission_list'))
        with patch.object(ec.daily,'_menuSwipe') as swipe,self.assertRaises(ec.ScriptStop):runner.missionListTop()
        self.assertEqual(swipe.call_count,1)


class MissionLookupTests(unittest.TestCase):
    def labels(self):
        labels=[i for i in EventContractTests().missionList() if i.text not in ('编号1','通关主线关卡第一话','目标进行度','1/1','可领取','已完成')]
        return labels+[item('编号11',1145,282,w=65),item('击败20个敌人',607,320,w=250),item('目标进行度',617,364,w=105),item('0/20',605,400,w=70)]
    def test_actual_number_and_condition_progress_are_required(self):
        labels=self.labels();self.assertEqual(event.findMissionCard(labels,11)['condition'],'击败20个敌人')
        self.assertIsNone(event.findMissionCard(labels,12))
        self.assertIsNone(event.findMissionCard(labels+[item('编号11',1145,445)],11))
        self.assertIsNone(event.findMissionCard([i for i in labels if i.text!='0/20'],11))
    def test_seek_existing_card_reads_three_fresh_frames_without_input(self):
        labels=self.labels();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock())
        runner.read=Mock(return_value=(Mock(),labels,'mission_list'))
        with patch.object(ec.daily,'_menuSwipe') as swipe:card=runner.seekMission(11)[3]
        self.assertEqual(card['mission'],11);swipe.assert_not_called();self.assertEqual(runner.read.call_count,3)


class MissionNeighbourAlignmentTests(unittest.TestCase):
    def test_three_row_distance_uses_content_and_still_requires_actual_target(self):
        import numpy
        im=numpy.zeros((720,1280,3),dtype='uint8');im[301:328,1255:1268]=240
        labels=MissionLookupTests().labels();before=[i for i in labels if i.text not in ('编号11','击败20个敌人','目标进行度','0/20')]+[item('编号14',1145,410,w=65)]
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock());runner.wait=Mock(return_value=(Mock(im=im),labels,'mission_list'))
        runner.read=Mock(side_effect=[(Mock(im=im),before,'mission_list')]+[(Mock(im=im),labels,'mission_list')]*3)
        with patch.object(ec.daily,'_menuSwipe') as swipe:result=runner.seekMission(11)
        swipe.assert_called_once_with((1000,400),(1000,550));self.assertEqual(result[3]['mission'],11)
        self.assertEqual(runner.read.call_count,4)
    def test_clipped_predecessor_uses_content_scroll_never_guessed_claim(self):
        import numpy
        im=numpy.zeros((720,1280,3),dtype='uint8');im[301:328,1255:1268]=240
        labels=MissionLookupTests().labels();before=[i for i in labels if i.text not in ('编号11','击败20个敌人','目标进行度','0/20')]+[item('编号12',1145,410,w=65)]
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock());runner.wait=Mock(return_value=(Mock(im=im),labels,'mission_list'))
        runner.read=Mock(side_effect=[(Mock(im=im),before,'mission_list')]+[(Mock(im=im),labels,'mission_list')]*3)
        with patch.object(ec.daily,'_menuSwipe') as swipe:result=runner.seekMission(11)
        swipe.assert_called_once_with((1000,400),(1000,550));self.assertEqual(result[3]['mission'],11)


class MissionProgressCropTests(unittest.TestCase):
    def test_outlined_counter_requires_two_strong_matching_local_reads(self):
        import numpy
        labels=[i if i.text!='0/20' else item('0/20',605,400,w=70,score=.83) for i in MissionLookupTests().labels()]
        d=Mock(_crop=Mock(return_value=numpy.zeros((30,70,3),dtype='uint8')))
        with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('0/20',.97)):
            self.assertEqual(event.findMissionCard(ec.missionProgressItems(d,labels),11)['progress'],'0/20')
        for output in ([('0/20',.97),('0/21',.97)],[('0/20',.97),('0/20',.84)]):
            with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=output):self.assertIsNone(event.findMissionCard(ec.missionProgressItems(d,labels),11))


class MissionConditionIntegrityTests(unittest.TestCase):
    def test_availability_date_alone_cannot_be_a_condition(self):
        labels=[i if i.text!='击败20个敌人' else item('【达成&9月25日17:00后开放下一个主线关卡】',607,320,w=400) for i in MissionLookupTests().labels()]
        self.assertIsNone(event.findMissionCard(labels,11))
    def test_wrapped_exclusion_must_not_be_silently_dropped(self):
        labels=[i if i.text!='击败20个敌人' else item('击败20个敌人（召唤出来的敌人除',607,310,w=400) for i in MissionLookupTests().labels()]
        self.assertIsNone(event.findMissionCard(labels,11))
        labels.append(item('外）',607,334,w=35))
        self.assertIn('除 外',event.findMissionCard(labels,11)['condition'])


class MissionItemInformationTests(unittest.TestCase):
    def labels(self):
        return EventContractTests().missionList()+[item('【灵基再临素材】',525,292,w=227,h=31),item('获得的五节枪的枪头。',480,346,w=306,h=46),item('构造保密。',563,385,w=141,h=32),item('关闭',604,491,w=72,h=40)]
    def test_passive_material_information_cannot_be_a_claim_or_recovery(self):
        labels=self.labels();self.assertEqual(event.classifyEventState(labels),'item_information')
        self.assertFalse(event._missionListConfirmed(labels));self.assertIsNone(event.findCompletedMissionCard(labels))
        self.assertIsNone(event.findMissionItemInfoClose(labels+[item('请选择奖励',500,300)]))
    def test_close_requires_three_proofs_and_never_an_inventory_action(self):
        labels=self.labels();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock());runner.touch=Mock()
        runner.read=Mock(return_value=(Mock(),labels,'item_information'));runner.wait=Mock(return_value=(None,[],'mission_list'))
        runner.closeMissionItemInfo(None,labels)
        runner.touch.assert_called_once_with(labels,(640,511),'close_mission_material_information')


class LockedMapWaitTests(unittest.TestCase):
    def test_expected_locked_map_requires_three_hud_frames_not_immediate_block(self):
        labels=LockedQuestMissionTests().labels();d=Mock();d.isMainInterface.return_value=True;d.getAp.return_value=224
        clock=Clock();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock(),clock=clock);runner.read=Mock(return_value=(d,labels,'mission_gate'))
        with patch.object(ec,'schedule',clock):result=runner.wait({'mission_gate'},accept=lambda d,i,s:event.findLockedEventMission(i) is not None)
        self.assertEqual(result[2],'mission_gate');self.assertEqual(runner.read.call_count,3)


class MissionInfoCropTests(unittest.TestCase):
    def test_text_height_excludes_button_rim_and_requires_matching_strong_reads(self):
        import numpy
        labels=MissionItemInformationTests().labels()
        labels=[i if i.text!='关闭' or i.center[0]<500 else item('关闭',604,491,w=72,h=40,score=.78) for i in labels]
        d=Mock(_crop=Mock(return_value=numpy.zeros((40,100,3),dtype='uint8')))
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('关闭',.996),('关闭',.997)]):
            self.assertEqual(event.classifyEventState(ec.missionInfoItems(d,labels)),'item_information')
        d._crop.assert_called_once_with((590,491,690,531))
        for output in ([('关闭',.99),('取消',.99)],[('关闭',.99),('关闭',.84)]):
            with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=output):
                self.assertIsNone(event.findMissionItemInfoClose(ec.missionInfoItems(d,labels)))


class MissionConditionCropTests(unittest.TestCase):
    def labels(self):
        labels=[i if i.text!='击败20个敌人' else item('击败20个敌人（召唤出来的敌人除',607,310,w=400) for i in MissionLookupTests().labels()]
        return labels+[item('外)',608,334,w=28,h=20,score=.74)]
    def test_complete_exclusion_requires_same_two_scale_tail_not_invented_text(self):
        import numpy
        labels=self.labels();d=Mock(_crop=Mock(return_value=numpy.zeros((20,28,3),dtype='uint8')))
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('外)',.918),('外)',.945)]):
            self.assertIsNotNone(event.findMissionCard(ec.missionConditionItems(d,labels),11))
        d._crop.assert_called_once_with((608,334,636,354))
        for output in ([('外)',.99),('内)',.99)],[('外)',.99),('外)',.84)]):
            with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=output):
                self.assertIsNone(event.findMissionCard(ec.missionConditionItems(d,labels),11))
    def test_without_strong_opening_or_number_no_local_read(self):
        labels=[i for i in self.labels() if i.text!='编号11'];d=Mock()
        self.assertEqual(ec.missionConditionItems(d,labels),labels);d._crop.assert_not_called()


class EventQuestInformationTests(unittest.TestCase):
    def labels(self):
        return LockedQuestMissionTests().labels()+[item('关卡情报',283,101,w=102,h=32),item('可点击「战利品」与「敌人」的图标来切换',260,20,w=385),item('战利品',153,168,w=83),item('敌人',420,165,w=60,h=36),item('关闭',289,647,w=70,h=40)]
    def test_foreground_information_precedes_background_mission_lock(self):
        labels=self.labels();self.assertEqual(event.classifyEventState(labels),'quest_information')
        self.assertEqual(event.findEventQuestEnemyTab(labels),(450,183))
        self.assertIsNone(event.findEventQuestInfoClose(labels+[item('请选择奖励',300,300)]))
        self.assertIsNone(event.findEventQuestInfoClose([i for i in labels if i.text!='关卡情报']))
    def test_weak_enemy_tab_requires_joint_page_and_two_strong_matching_reads(self):
        import numpy
        labels=[i if i.text!='敌人' else item('敌入',420,165,w=60,h=36,score=.73) for i in self.labels()]
        d=Mock(_crop=Mock(return_value=numpy.zeros((30,76,3),dtype='uint8')))
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('敌人',.915),('敌人',.885)]):
            self.assertEqual(event.findEventQuestEnemyTab(ec.questInfoItems(d,labels)),(450,183))
        d._crop.assert_called_once_with((412,168,488,198))
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('敌人',.915),('敌入',.99)]):
            self.assertIsNone(event.findEventQuestEnemyTab(ec.questInfoItems(d,labels)))
    def test_close_once_returns_map_never_starts_quest(self):
        labels=self.labels();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock());runner.touch=Mock()
        runner.read=Mock(return_value=(Mock(),labels,'quest_information'));runner.wait=Mock(return_value=(None,[],'mission_gate'))
        runner.closeQuestInformation(None,labels)
        runner.touch.assert_called_once_with(labels,(324,667),'close_event_quest_information')


class LockedMapSettlementBoundaryTests(unittest.TestCase):
    def test_real_locked_map_is_terminal_boundary_only_with_hud_and_ap(self):
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock());d=Mock();d.isMainInterface.return_value=True;d.getAp.return_value=224
        labels=LockedQuestMissionTests().labels()
        with patch.object(ec,'enrichedEventItems',return_value=labels),patch.object(event,'_detectFlags',return_value={}):
            self.assertTrue(runner.eventBoundary(d))
            d.getAp.return_value=None;self.assertFalse(runner.eventBoundary(d))
            d.getAp.return_value=224;d.isMainInterface.return_value=False;self.assertFalse(runner.eventBoundary(d))
        with patch.object(ec,'enrichedEventItems',return_value=EventQuestInformationTests().labels()),patch.object(event,'_detectFlags',return_value={}):
            self.assertFalse(runner.eventBoundary(d))


class EventQuestInfoTransitionTests(unittest.TestCase):
    def test_missing_instruction_uses_independent_fixed_body_or_waits_readonly(self):
        labels=[i for i in EventQuestInformationTests().labels() if '可点击' not in i.text]
        self.assertEqual(event.classifyEventState(labels),'unknown')
        self.assertIsNone(event.findEventQuestInfoClose(labels))
        labels.append(item('此为过去在此关卡中所遇到过的敌人一览',143,220,w=361))
        self.assertEqual(event.classifyEventState(labels),'quest_information')
        self.assertEqual(event.findEventQuestInfoClose(labels),(324,667))


class EventQuestCloseStabilityTests(unittest.TestCase):
    def test_one_ocr_miss_resets_confirmation_before_single_close(self):
        labels=EventQuestInformationTests().labels();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock());runner.touch=Mock()
        runner.read=Mock(side_effect=[(Mock(),labels,'quest_information'),(Mock(),[],'unknown')]+[(Mock(),labels,'quest_information')]*3)
        runner.wait=Mock(return_value=(None,[],'mission_gate'))
        runner.closeQuestInformation(None,labels);self.assertEqual(runner.read.call_count,5);runner.touch.assert_called_once()
    def test_no_fresh_positive_proof_times_out_without_touch(self):
        labels=EventQuestInformationTests().labels();clock=Clock();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock(),clock=clock)
        runner.touch=Mock();runner.read=Mock(return_value=(Mock(),[],'unknown'))
        with patch.object(ec,'schedule',clock),self.assertRaises(ec.ScriptStop):runner.closeQuestInformation(None,labels)
        runner.touch.assert_not_called()


class QuestCloseCropTests(unittest.TestCase):
    def test_weak_close_two_scale_recovery_keeps_threshold(self):
        import numpy
        labels=[i if i.text!='关闭' or i.center[1]<630 else item('关闭',289,647,w=70,h=40,score=.747) for i in EventQuestInformationTests().labels()]
        d=Mock(_crop=Mock(return_value=numpy.zeros((40,98,3),dtype='uint8')))
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('关闭',.992),('关闭',.995)]):
            self.assertEqual(event.findEventQuestInfoClose(ec.questInfoItems(d,labels)),(324,667))
        d._crop.assert_called_once_with((275,647,373,687))
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('关闭',.992),('关闭',.84)]):
            self.assertIsNone(event.findEventQuestInfoClose(ec.questInfoItems(d,labels)))


class DroppedCeOutlinedZeroTests(unittest.TestCase):
    def labels(self):return [item('概念礼装',589,596,w=98,h=30),item('生命值',745,600,w=60,h=34),item('请点击游戏界面',508,672,w=267,h=40)]
    def test_strong_matching_digit_fallback_recognizes_already_awarded_card(self):
        import numpy
        d=Mock(_crop=Mock(return_value=numpy.zeros((40,100,3),dtype='uint8')))
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('0',.728),('0',.595),('请点击游戏界面',.997),('请点击游戏界面',.998)]),patch.object(ec.OCR.EN,'ocr_single_line',side_effect=[('0',.972),('0',.963)]):
            self.assertEqual(event.classifyEventState(ec.itemReceiptItems(d,self.labels())),'item_receipt')
    def test_digit_disagreement_or_low_score_does_not_create_receipt(self):
        import numpy
        for output in ([('0',.97),('8',.99)],[('0',.97),('0',.84)]):
            d=Mock(_crop=Mock(return_value=numpy.zeros((40,100,3),dtype='uint8')))
            with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('0',.7)),patch.object(ec.OCR.EN,'ocr_single_line',side_effect=output):
                self.assertIsNone(event.findEventItemReceipt(ec.itemReceiptItems(d,self.labels())))


class EventReceiptSettlementResumeTests(unittest.TestCase):
    def test_positive_continue_flag_has_producer(self):
        self.assertEqual(event.classifyEventState([],{'battle_continue':True}),'continue')
    def test_friend_request_or_continue_resumes_shared_settlement_without_entry(self):
        from test_battle_cycle import Scenario
        for initial in ('ADD_FRIEND','CONTINUE'):
            scenario=Scenario();scenario.state=initial
            runner=ec.EventRunner(ec.EventResourcePolicy(allowApples=False),ledger=Mock());runner.clock=scenario
            flow=BattleFlow(scenario.read,scenario,clock=scenario,trace=FlowTrace(clock=scenario))
            runner.main.makeFlow=Mock(return_value=flow);runner.main.battleClass=Mock()
            def read():
                d=scenario.read();d.getAp=lambda:184
                return d,[],{'ADD_FRIEND':'friend_request','CONTINUE':'continue','QUEST_READY':'event_map'}.get(scenario.state,'unknown')
            runner.read=read
            with patch.object(ec,'schedule',scenario),patch.object(ec.fgoDevice.device,'press',side_effect=scenario.press):
                self.assertEqual(runner.runBattle()[2],'event_map')
            runner.main.battleClass.assert_not_called()
            self.assertEqual((runner.main.startedBattles,runner.main.completedAttempts,runner.settledResumes),(0,0,1))
            self.assertEqual(scenario.actions,[('ADD_FRIEND','X'),('CONTINUE','F')] if initial=='ADD_FRIEND' else [('CONTINUE','F')])


class EventFirstClearLoadingTests(unittest.TestCase):
    def scenario(self,limit=None,arrive=25):
        clock=Clock();pressed=[]
        def read():return frame('ADD_FRIEND' if not pressed else 'LOADING' if clock.now<arrive else 'UNKNOWN')
        flow=BattleFlow(read,clock,clock=clock,trace=FlowTrace(clock=clock))
        cycle=BattleCycle(Mock(press=lambda k:pressed.append(k)),flow)
        kwargs={} if limit is None else {'friendCloseTimeout':limit}
        try:result=cycle.settleBattleResult(boundary=lambda d:bool(pressed and clock.now>=arrive),**kwargs);error=None
        except ec.ScriptStop as e:result=None;error=e
        return clock,pressed,result,error
    def test_event_uses_remaining_hard_budget_for_proven_first_clear_loading(self):
        clock,inputs,result,error=self.scenario(60)
        self.assertIsNone(error);self.assertEqual(inputs,['X']);self.assertEqual(result.state,ec.S.UNKNOWN);self.assertGreaterEqual(clock.now,25)
    def test_default_stays_twenty_and_extension_never_exceeds_sixty_hard_limit(self):
        clock,inputs,result,error=self.scenario()
        self.assertIsInstance(error,ec.FlowTimeout);self.assertLess(clock.now,21);self.assertEqual(inputs,['X'])
        clock,inputs,result,error=self.scenario(180,arrive=80)
        self.assertIsInstance(error,ec.FlowTimeout);self.assertLess(clock.now,61);self.assertEqual(inputs,['X'])


class EarnedReceiptGlowTests(unittest.TestCase):
    def labels(self):return [item('任务完成',200,76,w=381,h=111),item('获得报酬',717,76,w=382,h=111),item('获得白银果实×1！',387,491,w=509,h=70,score=.844),item('请点击游戏界面',505,627,w=271,h=44)]
    def test_local_matching_amount_restores_receipt_never_ap_recovery(self):
        import numpy
        d=Mock(_crop=Mock(return_value=numpy.zeros((62,507,3),dtype='uint8')))
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('获得白银果实×1！',.916),('获得白银果实×1！',.915)]):
            labels=ec.earnedReceiptItems(d,self.labels());self.assertEqual(event.classifyEventState(labels),'reward_receipt');ec.QuartzGuard.check(labels)
        d._crop.assert_called_once_with((388,493,895,555))
    def test_missing_header_disagreement_or_wrong_amount_still_block(self):
        import numpy
        labels=self.labels();d=Mock(_crop=Mock(return_value=numpy.zeros((62,507,3),dtype='uint8')))
        for output in ([('获得白银果实×1！',.99),('获得白银果实×2！',.99)],[('获得白银果实×2！',.99),('获得白银果实×2！',.99)],[('获得白银果实×1！',.99),('获得白银果实×1！',.84)]*2):
            with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=output):self.assertIsNone(event.findEventRewardReceipt(ec.earnedReceiptItems(d,labels)))
        d._crop.reset_mock();self.assertEqual(ec.earnedReceiptItems(d,labels[1:]),labels[1:]);d._crop.assert_not_called()


class MissionBottomAlignmentTests(unittest.TestCase):
    def test_visible_target_at_bottom_is_aligned_before_numeric_seek_budget(self):
        labels=MissionLookupTests().labels();bottom=[i for i in labels if i.text not in ('编号11','击败20个敌人','目标进行度','0/20')]+[item('编号11',1145,549,w=65)]
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock());runner.read=Mock(side_effect=[(Mock(),bottom,'mission_list')]*3+[(Mock(),labels,'mission_list')]*3);runner.wait=Mock(return_value=(Mock(),labels,'mission_list'))
        with patch.object(ec.daily,'_menuSwipe') as swipe:result=runner.seekMission(11)
        swipe.assert_called_once_with((1000,550),(1000,400));self.assertEqual(result[3]['mission'],11)
    def test_bottom_identity_changes_no_scroll(self):
        labels=MissionLookupTests().labels();bottom=[i for i in labels if i.text!='编号11']+[item('编号11',1145,549,w=65)]
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock());runner.read=Mock(side_effect=[(Mock(),bottom,'mission_list'),(Mock(),[],'unknown')])
        with patch.object(ec.daily,'_menuSwipe') as swipe,self.assertRaises(ec.ScriptStop):runner.seekMission(11)
        swipe.assert_not_called()

class MissionLostSlashCropTests(unittest.TestCase):
    def test_digit_blob_must_be_reread_with_real_slash_not_split_by_guess(self):
        import numpy
        labels=[i if i.text!='0/20' else item('720',605,400,w=70,score=.89) for i in MissionLookupTests().labels()]
        d=Mock(_crop=Mock(return_value=numpy.zeros((30,70,3),dtype='uint8')))
        with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('7/20',.97)):
            self.assertEqual(event.findMissionCard(ec.missionProgressItems(d,labels),11)['progress'],'7/20')
        with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('720',.99)):
            self.assertIsNone(event.findMissionCard(ec.missionProgressItems(d,labels),11))


class MissionProgressLabelCropTests(unittest.TestCase):
    def test_label_requires_two_matching_strong_reads(self):
        import numpy
        labels=[i if i.text!='目标进行度' else item('目标进行度',617,364,w=105,score=.846) for i in MissionLookupTests().labels()]
        d=Mock(_crop=Mock(return_value=numpy.zeros((26,105,3),dtype='uint8')))
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('目标进行度',.895),('目标进行度',.896)]):
            self.assertIsNotNone(event.findMissionCard(ec.missionProgressItems(d,labels),11))
        for output in ([('目标进行度',.99),('自标进行度',.99)],[('目标进行度',.99),('目标进行度',.84)]):
            with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=output):
                self.assertIsNone(event.findMissionCard(ec.missionProgressItems(d,labels),11))
    def test_no_proved_mission_list_no_crop(self):
        d=Mock();labels=[item('目标进行度',617,364,w=105,score=.846)]
        self.assertEqual(ec.missionProgressItems(d,labels),labels);d._crop.assert_not_called()


class MissionOutlinedFractionTests(unittest.TestCase):
    def test_padded_rim_is_not_stripped_and_tight_pixels_must_agree(self):
        import numpy
        labels=[i if i.text!='0/20' else item('2/4',605,400,w=70,score=.84) for i in MissionLookupTests().labels()]
        d=Mock(_crop=Mock(return_value=numpy.zeros((30,70,3),dtype='uint8')))
        for tight,expected in (([('2/4',.97),('2/4',.94)],True),([('-2/4',.99)]*2,False),([('2/4',.99),('2/3',.99)],False)):
            with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('214',.8)),patch.object(ec.OCR.EN,'ocr_single_line',side_effect=[('-2/4',.95)]*2+tight):
                card=event.findMissionCard(ec.missionProgressItems(d,labels),11)
            self.assertEqual(card is not None,expected)
            if card:self.assertEqual(card['progress'],'2/4')
    def test_real_slash_needs_two_strong_masked_reads(self):
        import numpy
        labels=[i if i.text!='0/20' else item('7112',605,400,w=70,score=.89) for i in MissionLookupTests().labels()]
        d=Mock(_crop=Mock(return_value=numpy.zeros((30,70,3),dtype='uint8')))
        with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('712',.99)),patch.object(ec.OCR.EN,'ocr_single_line',side_effect=[('7/12',.898),('7/12',.911)]):
            self.assertEqual(event.findMissionCard(ec.missionProgressItems(d,labels),11)['progress'],'7/12')
    def test_mask_disagreement_weak_nan_or_missing_slash_never_guesses(self):
        import numpy
        labels=[i if i.text!='0/20' else item('7112',605,400,w=70,score=.89) for i in MissionLookupTests().labels()]
        d=Mock(_crop=Mock(return_value=numpy.zeros((30,70,3),dtype='uint8')))
        for output in ([('7/12',.99),('7/13',.99)],[('7/12',.99),('7/12',.84)],[('7/12',float('nan')),('7/12',.99)],[('712',.99),('712',.99)],[('13/12',.99),('13/12',.99)]):
            with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('712',.99)),patch.object(ec.OCR.EN,'ocr_single_line',side_effect=output*2):
                self.assertIsNone(event.findMissionCard(ec.missionProgressItems(d,labels),11))


class MissionBattleToastTests(unittest.TestCase):
    def test_top_toast_never_proves_mission_list(self):
        labels=[item('编号77 通关10次任意自由关卡',333,17,w=340),item('活动任务',334,64,w=65),item('2/10',424,60),item('与从者的牵绊',90,170),item('请点击游戏界面',480,635)]
        self.assertFalse(event._missionListConfirmed(labels))
        self.assertEqual(event.classifyEventState(labels,{'battle_result':True}),'battle_result')
        self.assertNotEqual(event.classifyEventState(labels),'mission_list')


class LockedBattleMapProofTests(unittest.TestCase):
    def test_locked_battle_map_does_not_depend_on_progress_heading(self):
        labels=[i for i in LockedQuestMissionTests().labels() if i.text!='任务进行度']
        self.assertEqual(event.findLockedEventMission(labels)['mission'],11)
        self.assertEqual(event.classifyEventState(labels,{'main_interface':True}),'mission_gate')
        self.assertIsNone(event.findNextMainQuest(labels))
    def test_independent_map_controls_and_lock_are_required(self):
        labels=[i for i in LockedQuestMissionTests().labels() if i.text!='任务进行度']
        for token in ('关闭','活动报酬','主线关卡 第三话','关卡举办时间剩余10日','完成任务No.11后开放'):
            self.assertIsNone(event.findLockedEventMission([i for i in labels if i.text!=token]))
        self.assertIsNone(event.findLockedEventMission([i for i in labels if not i.text.startswith('AP')]))
        self.assertIsNone(event.findLockedEventMission(labels+[item('主线关卡 第四话',780,132,w=220)]))

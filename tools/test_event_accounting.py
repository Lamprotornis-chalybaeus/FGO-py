"""Entry-linked outcome accounting; synthetic frames, no live device."""
import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import test_event_cycle as cycleTests
ec=cycleTests.ec;event=cycleTests.event
from test_gui_navigation import item

class Ledger:
    def __init__(self,records=()):self.data={'records':list(records)}
    def append(self,kind,**fields):
        row={'kind':kind,**fields};self.data['records'].append(row);return row

class ResourceDefaultsTests(unittest.TestCase):
    def test_default_is_no_apples_and_explicit_permission_is_required(self):
        self.assertFalse(ec.EventResourcePolicy().allowApples)
        self.assertTrue(ec.EventResourcePolicy(allowApples=True).allowApples)
        with self.assertRaises(ValueError):ec.EventResourcePolicy(allowApples=True,allowQuartz=True)
    def test_plain_gui_progress_does_not_inherit_local_permission(self):
        import inspect
        source=inspect.getsource(event.progress)
        self.assertIn('if resourcePolicy is not None:',source)
        self.assertNotIn('allowApples=True',source)
        self.assertIsNone(inspect.signature(event.progress).parameters['resourcePolicy'].default)
    def test_recovered_outcome_cannot_create_entry(self):
        with self.assertRaises(ValueError):ec.RecoveredBattleOutcome(True,'BOND',newEntry=True)

class RecoveredOutcomeTests(unittest.TestCase):
    def test_entry_revalidation_waits_read_only_after_transient_result_miss(self):
        runner=self.runner();good=runner.read.return_value
        runner.read=Mock(return_value=(Mock(),[],'unknown'));runner.wait=Mock(return_value=good);runner.touch=Mock()
        self.assertEqual(runner.battleEntryFrame(),good)
        self.assertEqual(runner.wait.call_args.kwargs['timeout'],15)
        self.assertIn('battle_result',runner.wait.call_args.args[0]);runner.touch.assert_not_called()
    def runner(self,entries=('one',),outcomes=()):
        ledger=Ledger([{'kind':'battle_started','entryId':i,'evidence':'fresh TURN_BEGIN','questKind':'main'} for i in entries]+list(outcomes))
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=ledger)
        frame=Mock();frame.isBattleFinished.return_value=True;frame.getBattleResultPage.return_value='BOND'
        runner.read=Mock(return_value=(frame,[],'battle_result'))
        runner.main.recordCompleted=Mock()
        return runner
    def test_started_unconfirmed_bond_records_one_recovered_win_no_result_fabrication(self):
        runner=self.runner();outcome=runner.recoverBattleOutcome()
        self.assertTrue(outcome.won);self.assertFalse(outcome.newEntry)
        self.assertIsNone(outcome.turns);self.assertIsNone(outcome.battleTime)
        self.assertEqual((runner.newBattleEntries,runner.normalCompletedBattles,runner.recoveredCompletedBattles,runner.eventWins),(1,0,1,1))
        self.assertEqual(runner.read.call_count,3);runner.main.recordCompleted.assert_not_called()
    def test_no_pending_entry_does_not_invent_win(self):
        runner=self.runner(())
        self.assertIsNone(runner.recoverBattleOutcome());runner.read.assert_not_called()
        self.assertEqual(runner.eventWins,0)
    def test_multiple_pending_entries_stop_before_any_input(self):
        runner=self.runner(('one','two'))
        with self.assertRaisesRegex(ec.ScriptStop,'Ambiguous'):runner.recoverBattleOutcome()
        runner.read.assert_not_called();self.assertEqual(runner.eventWins,0)
    def test_same_result_twice_and_restart_never_double_count(self):
        runner=self.runner();runner.recoverBattleOutcome();self.assertIsNone(runner.recoverBattleOutcome())
        restarted=ec.EventRunner(ec.EventResourcePolicy(),ledger=runner.ledger)
        self.assertIsNone(restarted.recoverBattleOutcome())
        self.assertEqual((restarted.newBattleEntries,restarted.recoveredCompletedBattles,restarted.eventWins),(1,1,1))
    def test_terminal_proof_must_be_positive_on_every_fresh_read(self):
        for page in ('BOND','BOND_LEVEL_UP','MASTER_EXP','REWARDS'):
            runner=self.runner();runner.read.return_value[0].getBattleResultPage.return_value=page
            self.assertTrue(runner.recoverBattleOutcome().won)
        runner=self.runner();good=runner.read.return_value
        runner.read.side_effect=[good,(Mock(),[],'unknown')]*4
        with self.assertRaises(ec.ScriptStop):runner.recoverBattleOutcome()
        self.assertEqual(runner.eventWins,0)
    def test_transient_miss_requires_three_new_consecutive_proofs_without_input(self):
        runner=self.runner();good=runner.read.return_value
        runner.read.side_effect=[good,(Mock(),[],'unknown')]+[good]*3
        self.assertTrue(runner.recoverBattleOutcome().won)
        self.assertEqual(runner.read.call_count,5);runner.main.recordCompleted.assert_not_called()
    def test_normal_and_recovered_totals_remain_distinct(self):
        runner=self.runner(('normal','recover'))
        runner.recordEventOutcome('normal',True,'normal',evidence='fresh terminal',turns=4,battleTime=30.)
        runner.recoverBattleOutcome()
        self.assertEqual((runner.normalCompletedBattles,runner.recoveredCompletedBattles,runner.eventWins,runner.eventDefeats),(1,1,2,0))
        self.assertEqual(runner.main.completedAttempts,0)
    def test_duplicate_or_orphan_outcome_is_not_silently_loaded(self):
        record={'kind':'battle_outcome','entryId':'one','mode':'recovered','won':True}
        with self.assertRaises(ValueError):self.runner(('one',),(record,record))
        with self.assertRaises(ValueError):self.runner((),(record,))
    def test_free_entry_confirmed_again_at_turn_is_counted_once(self):
        runner=self.runner(());runner.activeEntryId='free'
        runner.recordEntryStart('start_input_sent',questKind='free');runner.recordEntryStart('fresh TURN_BEGIN',questKind='free')
        self.assertEqual((runner.newBattleEntries,runner.FreeQuestBattles),(1,1))
    def test_real_normal_cycle_feeds_event_counts_without_recovery(self):
        runner,scenario,error=cycleTests.SharedEventCycleTests().runCycle()
        self.assertIsNone(error)
        self.assertEqual((runner.newBattleEntries,runner.normalCompletedBattles,runner.recoveredCompletedBattles,runner.eventWins),(1,1,0,1))

class ExactMissionClaimTests(unittest.TestCase):
    def labels(self):
        base=[i for i in cycleTests.MissionLookupTests().labels() if i.text not in ('击败20个敌人','0/20')]
        return base+[item('击败12个天之力敌人',607,320,w=250),item('12/12',605,400,w=70),item('可领取',850,274),item('已完成',875,400,w=74)]
    def test_claim_exact_number_needs_complete_condition_each_frame(self):
        labels=self.labels();after=cycleTests.EventContractTests().missionList(1)
        runner=ec.EventRunner(ec.EventResourcePolicy(),autoClaim=True,ledger=Ledger());runner.touch=Mock()
        runner.read=Mock(side_effect=[(Mock(),labels,'mission_list')]*3+[(Mock(),after,'mission_list')]*3)
        runner.claimCompletedMission(11)
        runner.touch.assert_called_once();claims=[r for r in runner.records() if r['kind']=='mission_claim']
        self.assertEqual(claims[0]['mission'],11);self.assertTrue(claims[0]['claimed']);self.assertEqual(claims[0]['beforeProgress'],(12,12))
    def test_ornamental_quote_variants_preserve_three_frame_claim_identity(self):
        variants=[]
        for condition in ('击败12个持有『天』属性的敌人','击败12个持有「天」属性的敌人','击败12个持有【天】属性的敌人'):
            variants.append([i for i in self.labels() if not i.text.startswith('击败')]+[item(condition,607,320,w=300)])
        after=cycleTests.EventContractTests().missionList(1)
        runner=ec.EventRunner(ec.EventResourcePolicy(),autoClaim=True,ledger=Ledger());runner.touch=Mock()
        runner.read=Mock(side_effect=[(Mock(),labels,'mission_list') for labels in variants]+[(Mock(),after,'mission_list')]*3)
        runner.claimCompletedMission(11);runner.touch.assert_called_once()
    def test_claim_missing_before_counter_never_touches(self):
        from test_battle_flow import Clock
        clock=Clock();runner=ec.EventRunner(ec.EventResourcePolicy(),autoClaim=True,ledger=Ledger(),clock=clock)
        runner.read=Mock(return_value=(Mock(),self.labels(),'mission_list'));runner.touch=Mock()
        with patch.object(ec.event,'missionCompletedCount',return_value=None),patch.object(ec,'schedule',clock),self.assertRaises(ec.ScriptStop):runner.claimCompletedMission(11)
        runner.touch.assert_not_called()
    def test_truncated_condition_cannot_claim_even_if_counter_complete(self):
        labels=[i for i in self.labels() if not i.text.startswith('击败')]+[item('击败12个天之力敌人(除外',607,320,w=250)]
        from test_battle_flow import Clock
        clock=Clock();runner=ec.EventRunner(ec.EventResourcePolicy(),autoClaim=True,ledger=Ledger(),clock=clock)
        runner.read=Mock(return_value=(Mock(),labels,'mission_list'));runner.touch=Mock()
        with patch.object(ec,'schedule',clock),self.assertRaises(ec.ScriptStop):runner.claimCompletedMission(11)
        runner.touch.assert_not_called()

if __name__=='__main__':unittest.main()


class NodeEvidenceTests(unittest.TestCase):
    def scenario(self,resumed=False,battle=False,locked=False):
        from contextlib import nullcontext
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger())
        labels=cycleTests.LockedQuestMissionTests().labels() if locked else []
        terminal='mission_gate' if locked else 'event_map'
        d=Mock();d.getAp.return_value=144
        runner.openMap=Mock(return_value=(d,[], 'story' if resumed else 'event_map'))
        runner.stableNode=Mock(return_value=(d,[],{'title':'第三话 完整主线标题','position':(900,180),'restrictions':[]}))
        runner.touch=Mock();runner.wait=Mock(side_effect=[(d,[],'support' if battle else 'story'),(d,labels,terminal)] if not resumed else [(d,labels,terminal)])
        def story(*args,**kwargs):runner.storySegments+=1;return d,labels,terminal
        def fought():runner.normalCompletedBattles+=1;runner.eventWins+=1;return d,labels,terminal
        runner.handleTransition=Mock(side_effect=story);runner.runBattle=Mock(side_effect=fought)
        with patch.object(ec.automationOwner,'claim',return_value=nullcontext()):result=runner.run(1)
        return runner,result
    def test_new_clean_story_and_recovered_story_never_mix(self):
        fresh,result=self.scenario();self.assertEqual(result['state'],'limit_reached')
        self.assertEqual((fresh.cleanNodes,fresh.recoveredNodes,fresh.storyNodes),(1,0,1))
        recovered,result=self.scenario(True);self.assertEqual((recovered.cleanNodes,recovered.recoveredNodes,recovered.storyNodes),(0,1,1))
    def test_normal_battle_node_can_end_at_a_positive_locked_map(self):
        runner,result=self.scenario(battle=True,locked=True)
        self.assertEqual((runner.cleanNodes,runner.battleNodes,runner.completed),(1,1,1))
        self.assertEqual(result['state'],'limit_reached');self.assertEqual(runner.touch.call_count,1)


class ReceiptCounterContextTests(unittest.TestCase):
    def test_receipt_can_auto_return_to_map_but_requires_actual_counter(self):
        labels=cycleTests.EventContractTests().missionReceipt();after=cycleTests.EventContractTests().missionList(1)
        mapLabels=[item('关闭',70,25,w=80),item('活动报酬',1124,10,w=120)]
        frame=Mock();frame.isMainInterface.return_value=True
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger());runner.touch=Mock()
        shifted=[item('关闭',70,25,w=80),item('活动报酬',1125,10,w=120)]
        runner.read=Mock(side_effect=[(frame,labels,'mission_reward_receipt')]*2+[(frame,shifted,'event_map'),(frame,mapLabels,'event_map')])
        runner.wait=Mock(side_effect=[(frame,mapLabels,'event_map'),(frame,after,'mission_list')])
        runner.closeMissionRewardReceipt(None,labels,countResumedClaim=True)
        self.assertEqual(runner.touch.call_count,2);self.assertEqual(runner.claimed,1)
        self.assertEqual(runner.touch.call_args.args[2],'reopen_missions_after_claim_map_return')
        self.assertEqual(runner.wait.call_args_list[0].kwargs['deadline'],runner.wait.call_args_list[1].kwargs['deadline'])
    def test_auto_map_without_unique_control_never_reopens_or_counts(self):
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger());runner.touch=Mock()
        runner.wait=Mock(return_value=(Mock(),[],'event_map'))
        with self.assertRaises(ec.ScriptStop):runner.waitMissionClaimIncrement(0)
        runner.touch.assert_not_called();self.assertEqual(runner.claimed,0)
    def test_unlocked_map_with_wrong_counter_does_not_count(self):
        labels=[item('活动报酬',1124,10,w=120)];frame=Mock();frame.isMainInterface.return_value=True
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger());runner.touch=Mock()
        runner.read=Mock(return_value=(frame,labels,'event_map'))
        runner.wait=Mock(side_effect=[(frame,labels,'event_map'),(frame,cycleTests.EventContractTests().missionList(0),'mission_list')])
        with self.assertRaises(ec.ScriptStop):runner.waitMissionClaimIncrement(0)
        runner.touch.assert_called_once();self.assertEqual(runner.claimed,0)
    def test_missing_overlay_counter_uses_proved_parent_not_a_guess(self):
        labels=[i for i in cycleTests.EventContractTests().missionReceipt() if i.text!='0/100']
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger());runner.touch=Mock()
        runner.read=Mock(return_value=(Mock(),labels,'mission_reward_receipt'))
        runner.wait=Mock(return_value=(Mock(),cycleTests.EventContractTests().missionList(1),'mission_list'))
        runner.closeMissionRewardReceipt(None,labels,expectedBeforeCount=0)
        runner.touch.assert_called_once();self.assertEqual(runner.records()[-1]['afterCount'],1)
    def test_real_counter_disagreement_never_closes(self):
        labels=cycleTests.EventContractTests().missionReceipt()
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger());runner.touch=Mock()
        with self.assertRaises(ec.ScriptStop):runner.closeMissionRewardReceipt(None,labels,expectedBeforeCount=1)
        runner.touch.assert_not_called()
    def test_resumed_receipt_records_claim_once_without_claim_input(self):
        labels=cycleTests.EventContractTests().missionReceipt()
        ledger=Ledger([{'kind':'mission_claim_intent','mission':1,'beforeCount':0,'progress':[1,1]}])
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=ledger);runner.touch=Mock()
        runner.read=Mock(return_value=(Mock(),labels,'mission_reward_receipt'))
        runner.wait=Mock(return_value=(Mock(),cycleTests.EventContractTests().missionList(1),'mission_list'))
        runner.closeMissionRewardReceipt(None,labels,countResumedClaim=True)
        with self.assertRaises(ec.ScriptStop):runner.closeMissionRewardReceipt(None,labels,countResumedClaim=True)
        runner.touch.assert_called_once();self.assertEqual(sum(r['kind']=='mission_claim' for r in ledger.data['records']),1)

class EmpiricalMissionMappingTests(unittest.TestCase):
    def runner(self,**changes):
        record=dict(kind='mission_mapping',mission=11,condition='击败12个天之力敌人',quest='实测关卡',before='0/12',after='12/12',sampleBattles=2,source='two actual local experiments',generic=False)
        record.update(changes)
        return ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger([record]))
    def requirement(self,**changes):
        result=dict(mission=11,condition='击败12个天之力敌人',progress='0/12');result.update(changes);return result
    def test_exact_empirical_requirement_finds_mapping_without_input(self):
        runner=self.runner();runner.touch=Mock()
        self.assertEqual(runner.observedMissionMapping(self.requirement())['quest'],'实测关卡');runner.touch.assert_not_called()
    def test_other_mission_attribute_or_total_does_not_inherit_mapping(self):
        runner=self.runner()
        for change in (dict(mission=12),dict(condition='击败12个地之力敌人'),dict(progress='0/20')):
            self.assertIsNone(runner.observedMissionMapping(self.requirement(**change)))
    def test_unproved_or_generic_mapping_is_not_a_solver(self):
        for change in (dict(generic=True),dict(source=''),dict(sampleBattles=0),dict(after='712'),dict(after='0/12')):
            self.assertIsNone(self.runner(**change).observedMissionMapping(self.requirement()))

class MissionHeaderReadTests(unittest.TestCase):
    def labels(self):
        return [i for i in cycleTests.EventContractTests().missionList(2) if i.text!='已达成的任务']+[item('已达成的任务',628,224,w=159,score=.82)]
    def test_local_two_scale_heading_recovers_actual_list_without_lower_threshold(self):
        frame=Mock();frame._crop.return_value=__import__('numpy').zeros((34,159,3),dtype='uint8')
        with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('已达成的任务',.95)) as ocr:
            labels=ec.missionHeaderItems(frame,self.labels())
        self.assertTrue(event._missionListConfirmed(labels));self.assertEqual(ocr.call_count,2)
        self.assertEqual(event.missionCompletedCount(labels),2)
    def test_weak_or_disagreeing_heading_cannot_promote(self):
        frame=Mock();frame._crop.return_value=__import__('numpy').zeros((34,159,3),dtype='uint8')
        for scores in ([('已达成的任务',.95),('已达成的任务',.84)],[('已达成的任务',.95),('未达成的任务',.95)]):
            with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=scores):
                self.assertFalse(event._missionListConfirmed(ec.missionHeaderItems(frame,self.labels())))
    def test_missing_independent_tab_or_modal_does_not_reread(self):
        for labels in ([i for i in self.labels() if i.text!='活动道具兑换'],self.labels()+[item('请选择奖励',400,300)]):
            with patch.object(ec.OCR.ZHS,'ocr_single_line') as ocr:
                self.assertEqual(ec.missionHeaderItems(Mock(),labels),labels);ocr.assert_not_called()

class FormationRestrictionNoticeTests(unittest.TestCase):
    def test_numbered_mission_content_progress_is_valid_even_with_tiny_thumb_change(self):
        before=[item('编号25',1150,320),item('编号26',1150,480)]
        self.assertTrue(ec.missionAnchorProgress(before,[item('编号25',1150,420),item('编号26',1150,580)]))
        self.assertTrue(ec.missionAnchorProgress(before,[item('编号27',1150,320)]))
        self.assertFalse(ec.missionAnchorProgress(before,[item('编号25',1150,321),item('编号26',1150,482)]))
        self.assertFalse(ec.missionAnchorProgress(before,[item('编号27',1150,320,score=.84)]))
    def masterLabels(self):
        return [item('等级提升',556,88,w=584,h=127),item('御主等级',696,267,w=165,h=40),item('行动力上限',708,407,w=140,h=32),item('好友上限',705,445,w=118,h=36),item('行动力已全部回复',705,491,w=227,h=34),item('请点击游戏界面',507,628,w=268,h=44)]
    def test_master_level_up_requires_all_independent_foreground_labels(self):
        labels=self.masterLabels()
        self.assertEqual(event.classifyEventState(labels,{'battle_result':True}),'master_level_up')
        for j in range(len(labels)):self.assertIsNone(event.findMasterLevelUpAdvance(labels[:j]+labels[j+1:]))
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger());runner.touch=Mock();runner.read=Mock(return_value=(Mock(),labels,'master_level_up'));runner.wait=Mock(return_value=(Mock(),[],'battle_result'))
        runner.closeMasterLevelUp(None,labels);runner.touch.assert_called_once_with(labels,(640,650),'dismiss_master_level_up')
        self.assertEqual(runner.newBattleEntries,0);self.assertEqual(runner.apples,{})
    def test_master_level_up_one_unknown_resets_proof_until_three_fresh_complete(self):
        labels=self.masterLabels();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger());runner.touch=Mock()
        runner.read=Mock(side_effect=[(Mock(),[],'unknown')]+[(Mock(),labels,'master_level_up')]*3);runner.wait=Mock(return_value=(Mock(),[],'battle_result'))
        with patch.object(ec.schedule,'sleep'):runner.closeMasterLevelUp(None,labels)
        self.assertEqual(runner.read.call_count,4);runner.touch.assert_called_once()
    def test_master_level_up_deadline_never_touches(self):
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger());runner.clock=Mock(side_effect=[0,15]);runner.touch=Mock()
        with self.assertRaises(ec.ScriptStop):runner.closeMasterLevelUp(None,self.masterLabels())
        runner.touch.assert_not_called()
    def uniformLabels(self):
        return [item('该关卡的魔术礼装会固定为',416,287,w=447,h=37),item('持有的『测试队服』。',433,327,w=371,h=36),item('队伍确认',1045,6,w=226,h=58),item('关闭',600,541,w=81,h=44)]
    def test_fixed_uniform_is_passive_notice_not_skill_failure_or_party_change(self):
        labels=self.uniformLabels()
        self.assertEqual(event.classifyEventState(labels,{'formation':True}),'formation_restriction_notice')
        self.assertEqual(event.findFormationRestrictionNotice(labels)['position'],(640,563))
        for j in range(len(labels)):
            self.assertIsNone(event.findFormationRestrictionNotice(labels[:j]+labels[j+1:]))
    def test_fixed_uniform_notice_closes_once_only_after_three_fresh_proofs(self):
        labels=self.uniformLabels();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger());runner.touch=Mock()
        runner.read=Mock(return_value=(Mock(),labels,'formation_restriction_notice'));runner.wait=Mock(return_value=(Mock(),[],'formation'))
        runner.closeFormationRestrictionNotice(None,labels)
        runner.touch.assert_called_once_with(labels,(640,563),'close_formation_restriction_notice')
        self.assertEqual(runner.newBattleEntries,0)
    def labels(self):
        return [item('编制限制',564,77,w=155,h=40),item('请将河上彦斋',528,211,w=224,h=36),item('设置为首发队员。',489,251,w=282,h=42),item('关闭',601,581,w=79,h=40),item('战斗开始',1108,651,w=120,h=41)]
    def test_actual_joint_notice_overrides_background_formation_and_start(self):
        labels=self.labels()
        self.assertEqual(event.classifyEventState(labels,{'formation':True}),'formation_restriction_notice')
        self.assertIsNone(event.findEventBattleStart(labels))
        for index in range(4):self.assertIsNone(event.findFormationRestrictionNotice(labels[:index]+labels[index+1:]))
    def test_three_fresh_notice_proofs_allow_only_one_close(self):
        labels=self.labels();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger())
        runner.read=Mock(return_value=(Mock(),labels,'formation_restriction_notice'));runner.touch=Mock()
        runner.wait=Mock(return_value=(Mock(),[],'formation'))
        self.assertEqual(runner.closeFormationRestrictionNotice(None,labels)[2],'formation')
        runner.touch.assert_called_once_with(labels,(640,601),'close_formation_restriction_notice')
        self.assertEqual(runner.newBattleEntries,0)
    def test_transient_requirement_or_expired_parent_cannot_close(self):
        labels=self.labels();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger(),clock=lambda:10);runner.touch=Mock()
        runner.read=Mock(return_value=(Mock(),[],'unknown'))
        with self.assertRaises(ec.ScriptStop):runner.closeFormationRestrictionNotice(None,labels)
        with self.assertRaises(ec.FlowTimeout):runner.closeFormationRestrictionNotice(None,labels,deadline=10)
        runner.touch.assert_not_called()
    def test_second_actual_exclusion_notice_is_distinct_instance(self):
        first=self.labels();second=[first[0],first[3],first[4],item('在本关卡中，',528,304,w=193,h=36),item('原田左之助',545,338,w=190,h=44),item('不可编队。',542,373,w=178,h=50)]
        self.assertEqual(event.classifyEventState(second,{'formation':True}),'formation_restriction_notice')
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger());runner.touch=Mock()
        runner.read=Mock(side_effect=[(Mock(),first,'formation_restriction_notice')]*2+[(Mock(),second,'formation_restriction_notice')]*2)
        runner.wait=Mock(side_effect=[(Mock(),second,'formation_restriction_notice'),(Mock(),[],'formation')])
        runner.closeFormationRestrictionNotice(None,first);runner.closeFormationRestrictionNotice(None,second)
        self.assertEqual(runner.touch.call_count,2)
        with self.assertRaises(ec.ScriptStop):runner.closeFormationRestrictionNotice(None,second)
        self.assertEqual(runner.touch.call_count,2)

class ConstrainedPartyReviewTests(unittest.TestCase):
    def labels(self):
        return [item('队伍编制',1044,9,w=224,h=54),item('编成限制',569,17,w=143,h=38),item('请将河上彦斋设置为首发队员。',500,68,w=265,h=23),item('编队限制',93,344,w=75,h=23),item('拖动修改从者配置。',530,622,w=260,h=22),item('取消',103,658,w=74,h=40),item('决定',1133,650,w=104,h=40)]
    def test_new_review_uses_all_three_restriction_proofs_not_one_heading(self):
        labels=self.labels();self.assertIsNotNone(event.findTemporaryPartyDecision(labels))
        self.assertEqual(event.classifyEventState(labels,{'formation':True}),'formation_review')
        for index in (1,2,3):self.assertIsNone(event.findTemporaryPartyDecision(labels[:index]+labels[index+1:]))
    def test_review_without_sent_isolated_auto_formation_never_decides(self):
        runner=ec.EventRunner(ec.EventResourcePolicy(allowTemporaryAutoFormation=True),ledger=Ledger());runner.touch=Mock()
        with self.assertRaisesRegex(ec.ScriptStop,'isolated'):runner.confirmTemporaryParty(None,self.labels())
        runner.touch.assert_not_called()
    def test_proved_isolated_review_decides_once_then_waits_for_formation(self):
        labels=self.labels();runner=ec.EventRunner(ec.EventResourcePolicy(allowTemporaryAutoFormation=True),ledger=Ledger([dict(kind='input',action='auto_form_isolated_event_party')]))
        runner.read=Mock(return_value=(Mock(),labels,'formation_review'));runner.touch=Mock();runner.wait=Mock(return_value=(Mock(),[],'formation'))
        runner.confirmTemporaryParty(None,labels)
        runner.touch.assert_called_once();self.assertEqual(runner.touch.call_args.args[2],'confirm_temporary_event_party')
    def test_weak_decision_only_recovers_after_two_matching_strong_local_reads(self):
        labels=[i for i in self.labels() if i.text!='决定']+[item('决定',1131,651,w=73,h=40,score=.82)]
        frame=Mock();frame._crop.return_value=__import__('numpy').zeros((40,73,3),dtype='uint8')
        self.assertIsNone(event.findTemporaryPartyDecision(labels))
        with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('决定',.95)):
            verified=ec.partyReviewItems(frame,labels)
        self.assertIsNotNone(event.findTemporaryPartyDecision(verified))
        for readings in ([('决定',.95),('决定',.84)],[('决定',.95),('开始',.95)]):
            with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=readings):self.assertEqual(ec.partyReviewItems(frame,labels),labels)
        with patch.object(ec.OCR.ZHS,'ocr_single_line') as ocr:
            self.assertEqual(ec.partyReviewItems(frame,labels[1:]),labels[1:]);ocr.assert_not_called()

class UniformAwardReceiptTests(unittest.TestCase):
    def labels(self):
        return [item('任务完成',199,73,w=384,h=115),item('获得报酬',713,76,w=386,h=111),item('获得浅葱的队服×1！',361,496,w=563,h=61,score=.828),item('请点击游戏界面',505,627,w=271,h=44)]
    def test_one_padded_read_keeps_real_name_amount_and_threshold(self):
        frame=Mock();frame._crop.return_value=__import__('numpy').zeros((61,563,3),dtype='uint8')
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('获得浅葱的队服×1！',.839),('获得浅葱的队服×1！',.838),('获得浅葱的队服×1！',.869),('获得浅葱的队服×1！',.874)]) as ocr:
            labels=ec.earnedReceiptItems(frame,self.labels())
        self.assertEqual(ocr.call_count,4);self.assertIsNotNone(event.findEventRewardReceipt(labels))
        frame._crop.assert_called_with((345,485,940,565))
    def test_padded_name_amount_disagreement_still_blocks(self):
        frame=Mock();frame._crop.return_value=__import__('numpy').zeros((61,563,3),dtype='uint8')
        for second in ([('获得浅葱的队服×2！',.99)]*2,[('获得浅葱的队服×1！',.99),('获得浅葱的队服×1！',.84)]):
            with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('获得浅葱的队服×1！',.839)]*2+second):self.assertIsNone(event.findEventRewardReceipt(ec.earnedReceiptItems(frame,self.labels())))

class AwardedUniformNoticeTests(unittest.TestCase):
    def labels(self):
        return [item('只要装备魔术礼装『浅葱的队服』',350,270,w=540,h=32),item('就能获得更多魔术礼装经验值。',350,308,w=560,h=32),item('装备魔术礼装『浅葱的队服』挑战关卡吧！',270,382,w=720,h=32),item('关闭',600,542,w=80,h=40)]
    def test_passive_explanation_has_its_own_producer_not_equip_action(self):
        labels=self.labels();self.assertEqual(event.classifyEventState(labels,{'main_interface':True}),'event_tutorial')
        self.assertEqual(event.findEventTutorialNext(labels),(640,562));self.assertEqual(event.eventTutorialKey(labels),'awarded-uniform-info')
        for index in range(4):self.assertIsNone(event.findAwardedUniformNoticeClose(labels[:index]+labels[index+1:]))
        self.assertIsNone(event.findAwardedUniformNoticeClose(labels+[item('装备',600,500)]))
    def test_three_fresh_proofs_close_once_and_do_not_change_equipment(self):
        labels=self.labels();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger());runner.touch=Mock()
        runner.read=Mock(return_value=(Mock(),labels,'event_tutorial'));runner.wait=Mock(return_value=(Mock(),[],'event_world_map'))
        self.assertEqual(runner.advanceTutorial(None,labels)[2],'event_world_map')
        runner.touch.assert_called_once_with(labels,(640,562),'advance_event_instructions')
        with self.assertRaises(ec.ScriptStop):runner.advanceTutorial(None,labels)
        self.assertEqual(runner.touch.call_count,1)

class ZoomedWorldMapTests(unittest.TestCase):
    def labels(self):
        return [item('管理室',70,25,w=80),item('活动报酬',1125,13,w=120),item('菜单',1148,633,w=77),item('京都城区',757,260,w=84,h=27)]
    def test_shorter_actual_marker_plaque_separation_still_needs_two_strong_reads(self):
        frame=Mock();frame.isMainInterface.return_value=True;frame._crop.return_value=__import__('numpy').zeros((46,114,3),dtype='uint8')
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('',float('nan'))]*10+[('下一个',.983),('下一个',.978)]):
            labels=ec.worldMapItems(frame,self.labels())
        self.assertEqual(event.findNextEventArea(labels)['title'],'京都城区')
        self.assertEqual(event.classifyEventState(labels,{'main_interface':True}),'event_world_map')
        self.assertIsNone(event.findNextEventArea(self.labels()))
    def test_marker_alone_duplicate_plaque_or_low_score_does_not_authorize_area(self):
        marker=item('下一个',744,80,w=114,h=46)
        labels=self.labels()+[marker]
        self.assertIsNotNone(event.findNextEventArea(labels))
        self.assertIsNone(event.findNextEventArea(labels+[item('别的区域',758,275,w=82)]))
        self.assertIsNone(event.findNextEventArea([marker]))
        self.assertIsNone(event.findNextEventArea(self.labels()+[item('下一个',744,80,w=114,h=46,score=.84)]))
    def test_search_near_top_never_sends_empty_out_of_bounds_crop_to_ocr(self):
        labels=self.labels()[:-1]+[item('京都城区',757,206,w=84,h=27)]
        frame=Mock();frame.isMainInterface.return_value=True
        def crop(rect):
            x,y,r,b=rect;self.assertGreaterEqual(y,0);self.assertLessEqual(b,720)
            return __import__('numpy').zeros((b-y,r-x,3),dtype='uint8')
        frame._crop.side_effect=crop
        with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('',float('nan'))):self.assertEqual(ec.worldMapItems(frame,labels),labels)
        self.assertGreater(frame._crop.call_count,0)
    def test_lower_zoomed_plaque_short_text_band_excludes_arrow_contamination(self):
        labels=self.labels()[:3]+[item('NEW新选组屯所',360,447,w=143,h=22)]
        frame=Mock();frame.isMainInterface.return_value=True;frame._crop.return_value=__import__('numpy').zeros((32,114,3),dtype='uint8')
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('',float('nan'))]*16+[('下一个',.975),('下一个',.970)]):
            verified=ec.worldMapItems(frame,labels)
        self.assertEqual(event.findNextEventArea(verified)['title'],'NEW新选组屯所')
        frame._crop.assert_called_with((376,295,490,327))

class MissionBlockSemanticsTests(unittest.TestCase):
    def test_receipt_completion_fragments_are_not_navigation_requirements(self):
        for text in ('任务完成 获得报酬','完成任务！获得概念礼装','任务已完成获得奖励'):
            labels=[item(text,200,76,w=380)]
            self.assertEqual(event.findMissionGate(labels),[])
            self.assertNotEqual(event.classifyEventState(labels),'mission_gate')
    def test_actual_access_requirement_retained_and_weak_copy_not_promoted(self):
        for text in ('需要完成任务12才能解锁','完成任务No.12后开放','请先完成任务12'):
            self.assertTrue(event.findMissionGate([item(text,400,300)]))
            self.assertFalse(event.findMissionGate([item(text,400,300,score=.84)]))

class NewShinsengumiNoticeTests(unittest.TestCase):
    def labels(self):
        return [item('在「NEW新选组屯所」',430,233,w=400,h=32),item('开放了NEW新选组关卡。',430,272,w=400,h=32),item('穿上『浅葱的队服',430,345,w=350,h=32),item('保护京都的治安吧！',430,383,w=400,h=32),item('关闭',600,542,w=80,h=40)]
    def test_actual_joint_notice_has_a_producer_and_own_episode_key(self):
        labels=self.labels()
        self.assertEqual(event.classifyEventState(labels),'event_tutorial')
        self.assertEqual(event.eventTutorialKey(labels),'new-shinsengumi-unlock-info')
        self.assertEqual(event.findEventTutorialNext(labels),(640,562))
    def test_missing_weak_duplicate_or_action_not_authorized(self):
        labels=self.labels()
        for index in range(len(labels)):
            self.assertIsNone(event.findNewShinsengumiNoticeClose(labels[:index]+labels[index+1:]))
        labels[0]=item('在「NEW新选组屯所」',430,233,w=400,h=32,score=.84)
        self.assertIsNone(event.findNewShinsengumiNoticeClose(labels))
        for extra in (self.labels()[0],item('装备',600,500),item('领取',600,500)):
            self.assertIsNone(event.findNewShinsengumiNoticeClose(self.labels()+[extra]))
    def test_three_fresh_frames_single_close_not_equipment(self):
        labels=self.labels();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger());runner.touch=Mock()
        runner.read=Mock(return_value=(Mock(),labels,'event_tutorial'));runner.wait=Mock(return_value=(Mock(),[],'event_world_map'))
        runner.advanceTutorial(None,labels)
        runner.touch.assert_called_once_with(labels,(640,562),'advance_event_instructions')
        with self.assertRaises(ec.ScriptStop):runner.advanceTutorial(None,labels)
        self.assertEqual(runner.touch.call_count,1)

class LockedAreaBoundaryTests(unittest.TestCase):
    def locked(self):
        return [item('关闭',70,25,w=80),item('活动报酬',1125,12,w=120),item('主线关卡第五话',775,126,w=225),item('无战斗',1139,125),item('完成任务No.23后开放',827,176,w=208),item('AP0',783,204),item('关卡举办时间剩余9日',983,243,w=220)]
    def test_area_wait_accepts_only_jointly_proven_numbered_locked_map(self):
        # Use the real world-map structure without depending on a test class.
        labels=[item('管理室',70,25),item('活动报酬',1125,12,w=120),item('菜单',1148,633),item('京都城区',590,400,w=100),item('下一个',600,175)]
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger());runner.read=Mock(return_value=(Mock(),labels,'event_world_map'));runner.touch=Mock();runner.wait=Mock(return_value=(None,self.locked(),'mission_gate'))
        self.assertEqual(runner.openNextArea()[2],'mission_gate')
        runner.touch.assert_called_once()
        allowed=runner.wait.call_args.args[0];accept=runner.wait.call_args.kwargs['accept']
        self.assertEqual(allowed,{'event_map','mission_gate'})
        self.assertTrue(accept(None,self.locked(),'mission_gate'))
        self.assertFalse(accept(None,[item('需要完成任务23才能解锁',400,300)],'mission_gate'))
    def test_opened_lock_routes_to_exact_requirement_not_node_selection(self):
        from contextlib import nullcontext
        labels=self.locked();runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger());d=Mock()
        runner.openMap=Mock(return_value=(d,[],'event_world_map'));runner.openNextArea=Mock(return_value=(d,labels,'mission_gate'));runner.stableNode=Mock();runner.touch=Mock()
        runner.openMissionRequirements=Mock(return_value=(d,[],'mission_list'))
        card={'mission':23,'condition':'通关指定NEW新选组关卡','progress':'0/1'}
        runner.seekMission=Mock(return_value=(d,[],'mission_list',card));runner.ap=Mock(return_value=139)
        with patch.object(ec.automationOwner,'claim',return_value=nullcontext()):result=runner.run(1)
        self.assertEqual(result['state'],'mission_gate');self.assertEqual(result['requirement'],card)
        self.assertEqual(result['nodes'],0);self.assertEqual(result['newBattleEntries'],0)
        runner.seekMission.assert_called_once_with(23);runner.stableNode.assert_not_called();runner.touch.assert_not_called()

class WrappedMissionFreshReadTests(unittest.TestCase):
    def test_ornamental_quotes_may_vary_but_words_count_and_exclusion_must_agree(self):
        import numpy
        labels=self.labels()
        labels=[item('击败20个『恶』敌人召唤出来的敌人除',607,310,w=400) if i.text.startswith('击败20') else i for i in labels]
        d=Mock(_crop=Mock(return_value=numpy.zeros((20,400,3),dtype='uint8')))
        missing='击败20个『恶』敌人召唤出来的敌人除';full='击败20个『恶』敌人（召唤出来的敌人除'
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[(missing,.92),(missing.replace('』','」'),.92),(full,.92),(full.replace('』','」'),.92)]+[('外)',.91)]*2):
            card=event.findMissionCard(ec.missionConditionItems(d,labels),11)
        self.assertIsNotNone(card);self.assertIn('恶',card['condition']);self.assertIn('召唤出来的敌人除',card['condition'])
    def labels(self):
        labels=cycleTests.MissionConditionCropTests().labels()
        return [item('击败20个敌人召唤出来的敌人除',607,310,w=400) if i.text.startswith('击败20') else i for i in labels]
    def test_missing_parenthesis_read_from_pixels_without_changing_condition(self):
        import numpy
        labels=self.labels();d=Mock(_crop=Mock(return_value=numpy.zeros((20,400,3),dtype='uint8')))
        self.assertIsNone(event.findMissionCard(labels,11))
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('击败20个敌人（召唤出来的敌人除',.91)]*2+[('外)',.91)]*2):
            card=event.findMissionCard(ec.missionConditionItems(d,labels),11)
        self.assertIn('召唤出来的敌人除 外',card['condition'])
    def test_changed_words_weak_or_disagreed_punctuation_not_promoted(self):
        import numpy
        d=Mock(_crop=Mock(return_value=numpy.zeros((20,400,3),dtype='uint8')))
        for output in ([('击败21个敌人（召唤出来的敌人除',.99)]*2,[('击败20个敌人（召唤出来的敌人除',.84)]*2,[('击败20个敌人（召唤出来的敌人除',.99),('击败20个敌人召唤出来的敌人除',.99)]):
            with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=output):self.assertIsNone(event.findMissionCard(ec.missionConditionItems(d,self.labels()),11))
    def test_one_pixel_boundary_alternate_still_needs_two_exact_reads(self):
        import numpy
        d=Mock(_crop=Mock(return_value=numpy.zeros((20,400,3),dtype='uint8')))
        missing='击败20个敌人召唤出来的敌人除';full='击败20个敌人（召唤出来的敌人除'
        for alternate,expected in (([(full,.91)]*2,True),([(full,.91),(missing,.91)],False)):
            with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[(missing,.91)]*2+alternate+[('外)',.91)]*2):
                card=event.findMissionCard(ec.missionConditionItems(d,self.labels()),11)
            self.assertEqual(card is not None,expected)
    def test_one_incomplete_frame_followed_by_three_complete_has_no_scroll(self):
        labels=cycleTests.MissionConditionCropTests().labels();complete=[item(i.text,*i.box[:2],w=i.box[2]-i.box[0],h=i.box[3]-i.box[1]) if i.text=='外)' else i for i in labels]
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger());runner.read=Mock(side_effect=[(Mock(),labels,'mission_list')]+[(Mock(),complete,'mission_list')]*3)
        with patch.object(ec.daily,'_menuSwipe') as swipe:
            card=runner.seekMission(11)[3];swipe.assert_not_called()
        self.assertEqual(card['mission'],11);self.assertEqual(runner.read.call_count,4)
    def test_padded_last_crop_recovers_only_same_words_and_real_punctuation(self):
        import numpy
        d=Mock(_crop=Mock(return_value=numpy.zeros((20,400,3),dtype='uint8')))
        missing='击败20个敌人召唤出来的敌人除';full='击败20个敌人（召唤出来的敌人除'
        for final,expected in (([(full,.92)]*2,True), ([(full,.92),(missing,.92)],False), ([(full.replace('20','21'),.99)]*2,False)):
            with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[(missing,.91)]*4+final+[('外)',.91)]*2):
                card=event.findMissionCard(ec.missionConditionItems(d,self.labels()),11)
            self.assertEqual(card is not None,expected)
    def test_wrapped_pixel_join_proves_full_exclusion_without_inventing_words(self):
        import numpy
        labels=cycleTests.MissionConditionCropTests().labels()
        d=Mock(im=numpy.zeros((720,1280,3),dtype='uint8'),_crop=Mock(return_value=numpy.zeros((20,40,3),dtype='uint8')))
        full='击败20个敌人（召唤出来的敌人除外）'
        for text,expected in ((full,True),(full.replace('20','21'),False),(full.replace('除外','之外'),False)):
            with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('外)',.75)]*2+[(text,.92)]*2):
                card=event.findMissionCard(ec.missionConditionItems(d,labels),11)
            self.assertEqual(card is not None,expected)
    def test_three_incomplete_frames_stop_without_scroll(self):
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger());runner.read=Mock(return_value=(Mock(),self.labels(),'mission_list'))
        with patch.object(ec.daily,'_menuSwipe') as swipe,self.assertRaises(ec.ScriptStop):runner.seekMission(11)
        self.assertEqual(runner.read.call_count,3);swipe.assert_not_called()

class MultiCardReceiptTests(unittest.TestCase):
    def labels(self):
        return cycleTests.EventContractTests().missionReceipt()+[item('编号2',1144,484,w=64)]
    def test_obtained_receipt_with_multiple_background_cards_has_no_guessed_identity(self):
        proof=event.missionRewardReceipt(self.labels())
        self.assertIsNone(proof['mission']);self.assertEqual(proof['visibleMissions'],(1,2))
        self.assertEqual(event.classifyEventState(self.labels()),'mission_reward_receipt')
    def test_unique_pending_claim_supplies_identity_and_only_closes_once(self):
        labels=self.labels();ledger=Ledger([dict(kind='mission_claim_intent',mission=1,beforeCount=0)])
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=ledger);runner.touch=Mock()
        runner.read=Mock(return_value=(Mock(),labels,'mission_reward_receipt'))
        runner.waitMissionClaimIncrement=Mock(return_value=(Mock(),cycleTests.EventContractTests().missionList(1),'mission_list'))
        runner.closeMissionRewardReceipt(None,labels,countResumedClaim=True)
        runner.touch.assert_called_once();self.assertEqual([r['mission'] for r in runner.records() if r['kind']=='mission_claim'],[1])
    def test_multiple_or_no_pending_context_never_closes(self):
        for records in ([],[dict(kind='mission_claim_intent',mission=n,beforeCount=0) for n in (1,2)]):
            runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger(records));runner.touch=Mock()
            with self.assertRaises(ec.ScriptStop):runner.closeMissionRewardReceipt(None,self.labels(),countResumedClaim=True)
            runner.touch.assert_not_called()

class MissionReceiptLabelTests(unittest.TestCase):
    def test_actual_two_scale_label_proof_is_required(self):
        import numpy
        labels=[item(i.text,*i.box[:2],w=i.box[2]-i.box[0],h=i.box[3]-i.box[1],score=.83) if i.text=='获得了' else i for i in cycleTests.EventContractTests().missionReceipt()]
        d=Mock(_crop=Mock(return_value=numpy.zeros((37,95,3),dtype='uint8')))
        with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=[('获得了',.99),('获得了',.99)]):
            self.assertIsNotNone(event.missionRewardReceipt(ec.missionReceiptItems(d,labels)))
        for output in ([('获得了',.99),('使用了',.99)],[('获得了',.84),('获得了',.99)]):
            with patch.object(ec.OCR.ZHS,'ocr_single_line',side_effect=output):self.assertIsNone(event.missionRewardReceipt(ec.missionReceiptItems(d,labels)))

class PostClaimReconciliationTests(unittest.TestCase):
    def test_unique_dismissal_and_three_incremented_counters_recover_without_input(self):
        ledger=Ledger([dict(kind='mission_claim_intent',mission=23,beforeCount=2,progress=[4,4]),dict(kind='mission_receipt_dismiss_intent',mission=23,beforeCount=2,reward='普通道具×5')])
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=ledger);runner.touch=Mock()
        labels=cycleTests.EventContractTests().missionList(3);runner.read=Mock(return_value=(Mock(),labels,'mission_list'))
        runner.reconcilePendingMissionClaim(None,labels);runner.reconcilePendingMissionClaim(None,labels)
        runner.touch.assert_not_called();self.assertEqual(runner.claimed,1);self.assertEqual(runner.read.call_count,3)
    def test_missing_dismissal_or_wrong_counter_never_accounts_claim(self):
        for close,count in ((False,3),(True,2),(True,4)):
            records=[dict(kind='mission_claim_intent',mission=23,beforeCount=2)]
            if close:records.append(dict(kind='mission_receipt_dismiss_intent',mission=23,beforeCount=2,reward='普通道具×5'))
            runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Ledger(records));runner.touch=Mock()
            labels=cycleTests.EventContractTests().missionList(count);runner.read=Mock(return_value=(Mock(),labels,'mission_list'))
            with self.assertRaises(ec.ScriptStop):runner.reconcilePendingMissionClaim(None,labels)
            runner.touch.assert_not_called();self.assertEqual(runner.claimed,0)
    def test_counter_local_read_requires_exact_two_scale_fraction(self):
        import numpy
        labels=[item(i.text,*i.box[:2],w=i.box[2]-i.box[0],h=i.box[3]-i.box[1],score=.84) if i.text=='3/100' else i for i in cycleTests.EventContractTests().missionList(3)]
        d=Mock(_crop=Mock(return_value=numpy.zeros((32,83,3),dtype='uint8')))
        with patch.object(ec.OCR.EN,'ocr_single_line',side_effect=[('3/100',.99)]*2):self.assertEqual(event.missionCompletedCount(ec.missionCounterItems(d,labels)),3)
        for output in ([('3/100',.99),('4/100',.99)],[('3/100',.84)]*2):
            with patch.object(ec.OCR.EN,'ocr_single_line',side_effect=output):self.assertIsNone(event.missionCompletedCount(ec.missionCounterItems(d,labels)))

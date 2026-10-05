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
        runner.read.side_effect=[good,(Mock(),[],'unknown'),good]
        with self.assertRaises(ec.ScriptStop):runner.recoverBattleOutcome()
        self.assertEqual(runner.eventWins,0)
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

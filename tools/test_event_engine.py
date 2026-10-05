"""Synthetic event catalog/learning/campaign contracts; no device or account data."""
import tempfile,unittest
from pathlib import Path
from dataclasses import replace
from unittest.mock import Mock,patch
import test_gui_navigation
from test_gui_navigation import item
import fgoEventEngine as engine
import fgoEventQuest as quest
import fgoEventCampaign as campaign
from fgoSchedule import ScriptStop
import numpy

def entry(title='测试关卡',AP=5,state='NEW',mode='LIST',eventKey='event',area='area'):
    return engine.EventQuestEntry(eventKey,area,title,AP,state,(900,320),'sig',{'mode':mode,'thumb':(95,300)},('icon',))
def card(n=23,cur=0,total=4,condition='击败4个指定敌人（召唤的除外）'):
    return {'mission':n,'condition':condition,'progress':f'{cur}/{total}'}

class ModelTests(unittest.TestCase):
    def test_scope_title_ap_make_distinct_keys(self):
        base=entry()
        for other in (entry(AP=40),entry(eventKey='another'),entry(area='else'),entry(title='别的关卡')):self.assertNotEqual(base.key,other.key)
    def test_locked_main_are_not_candidates(self):
        self.assertFalse(entry(state='LOCKED').available)
        self.assertFalse(replace(entry(),questKind='main').available)
    def test_invalid_ap_state_and_structure_rejected(self):
        for changes in ({'AP':-1},{'AP':True},{'state':'guessed'},{'locator':{'mode':'UNKNOWN'}},{'eventKey':''}):
            with self.assertRaises(ValueError):replace(entry(),**changes)
    def test_private_cache_round_trip_and_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'event-quest-index.json';index=engine.EventQuestIndex('event',path)
            index.add(entry());index.completeAreas.add('area');index.save()
            loaded=engine.EventQuestIndex('event',path)
            self.assertEqual(loaded.entries[entry().key].title,'测试关卡');self.assertIn('area',loaded.completeAreas)
            with self.assertRaises(ValueError):engine.EventQuestIndex('other',path)
    def test_reobservation_preserves_first_seen_and_effects(self):
        index=engine.EventQuestIndex('event');first=replace(entry(),firstSeen=1,observedMissionEffects={'23':3})
        index.add(first);index.add(replace(first,lastVerified=10,firstSeen=8,state='CLEARED'))
        self.assertEqual(index.entries[first.key].firstSeen,1);self.assertEqual(index.entries[first.key].state,'CLEARED')
    def test_fixed_and_until_complete_tasks_are_exclusive(self):
        engine.EventFarmTask('quest',runs=3);engine.EventFarmTask('quest',mission=23,untilComplete=True)
        for args in ({'runs':0},{'runs':True},{'runs':3,'mission':23,'untilComplete':True},{'mission':23},{'untilComplete':True}):
            with self.assertRaises(ValueError):engine.EventFarmTask('quest',**args)
    def test_currency_requires_identity_and_source(self):
        engine.EventCurrency('event token',3,'three stable icon-number frames')
        with self.assertRaises(ValueError):engine.EventCurrency('',3,'unknown')

class LearningTests(unittest.TestCase):
    def test_one_battle_learns_multiple_missions(self):
        db=engine.MissionEvidenceDB('event');before={'23':card(),'27':card(27,2,10,'击败10个其他敌人')}
        after={'23':card(cur=3),'27':card(27,3,10,'击败10个其他敌人')}
        row=db.record(entry(),'one',before,after,won=True,source='observed')
        self.assertEqual(row['deltaVector']['23']['delta'],3);self.assertEqual(row['deltaVector']['27']['delta'],1)
    def test_duplicate_id_not_double_counted(self):
        db=engine.MissionEvidenceDB('event')
        for _ in range(2):db.record(entry(),'one',{'23':card()},{'23':card(cur=3)},won=True,source='observed')
        self.assertEqual(db.effects(23,card()['condition'])[entry().key]['samples'],1)
    def test_conflicting_duplicate_id_stops(self):
        db=engine.MissionEvidenceDB('event');db.record(entry(),'one',{'23':card()},{'23':card(cur=3)},won=True,source='observed')
        with self.assertRaises(ValueError):db.record(entry(),'one',{'23':card()},{'23':card(cur=4)},won=True,source='observed')
    def test_capped_progress_does_not_make_negative(self):
        db=engine.MissionEvidenceDB('event');row=db.record(entry(),'one',{'23':card(cur=4)},{'23':card(cur=4)},won=True,source='observed')
        self.assertEqual(row['deltaVector'],{})
    def test_negative_candidate_not_immediately_repeated(self):
        db=engine.MissionEvidenceDB('event');db.record(entry(),'one',{'23':card()},{'23':card()},won=True,source='observed')
        other=entry(title='另一关卡',AP=40)
        self.assertEqual(db.rank([entry(),other],card()),[other])
    def test_positive_beats_new_low_ap_and_icon_is_only_ranking(self):
        db=engine.MissionEvidenceDB('event');mapped=entry(title='实证高AP',AP=40,state='CLEARED')
        db.record(mapped,'one',{'23':card()},{'23':card(cur=3)},won=True,source='observed')
        self.assertEqual(db.rank([entry(),mapped],card())[0],mapped)
        self.assertNotIn(entry().key,db.effects(23,card()['condition']))
    def test_new_lower_ap_first_without_inferred_attribute(self):
        db=engine.MissionEvidenceDB('event')
        self.assertEqual(db.rank([entry(AP=40),entry(),entry(AP=1,state='CLEARED')],card())[0].AP,5)
        self.assertEqual(db.data['experiments'],[])
    def test_unknown_or_changed_condition_cannot_map(self):
        db=engine.MissionEvidenceDB('event')
        for after in (card(cur=1,condition='另一个条件'),card(cur=1,total=5),card(cur=1,total=0)):
            with self.assertRaises(ValueError):db.record(entry(),'one',{'23':card()},{'23':after},won=True,source='observed')
    def test_missing_after_card_not_negative(self):
        db=engine.MissionEvidenceDB('event');row=db.record(entry(),'one',{'23':card()},{},won=True,source='observed')
        self.assertEqual(row['deltaVector'],{})
    def test_quotation_ocr_variation_does_not_change_condition_semantics(self):
        db=engine.MissionEvidenceDB('event')
        row=db.record(entry(),'one',{'23':card(condition='击败4个「恶」敌人（召唤除外）')},{'23':card(cur=3,condition='击败4个【恶」敌人（召唤除外）')},won=True,source='observed')
        self.assertEqual(row['deltaVector']['23']['delta'],3)
        self.assertNotEqual(engine.conditionKey('大于≥4'),engine.conditionKey('小于≤4'))
    def test_won_unique_outcome_required(self):
        db=engine.MissionEvidenceDB('event')
        for kwargs in ({'entryId':'','won':True},{'entryId':'one','won':False}):
            with self.assertRaises(ValueError):db.record(entry(),kwargs['entryId'],{}, {},won=kwargs['won'],source='observed')
    def test_db_serializes_only_text_numbers_hashes(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'event-mission-evidence.json';db=engine.MissionEvidenceDB('event',path)
            db.record(entry(),'one',{'23':card()},{'23':card(cur=3)},won=True,source='observed')
            loaded=engine.MissionEvidenceDB('event',path)
            self.assertEqual(loaded.effects(23,card()['condition'])[entry().key]['averageDelta'],3)
            self.assertNotIn('image',path.read_text(encoding='utf-8'))

class LocatorTests(unittest.TestCase):
    def runner(self):
        runner=Mock();runner.clock=__import__('time').monotonic;runner.ledger=Mock();return runner
    def test_cached_available_does_not_authorize_missing_fresh_title(self):
        locator=quest.EventQuestLocator(self.runner(),engine.EventQuestIndex('event'));locator.stable=Mock(return_value=(Mock(im=numpy.zeros((720,1280,3),dtype='uint8')),[], 'area',[]));locator.scan=Mock()
        with self.assertRaises(ScriptStop):locator.locate(entry())
        locator.runner.touch.assert_not_called()
    def test_fresh_hit_clicks_actual_position_once(self):
        runner=self.runner();locator=quest.EventQuestLocator(runner,engine.EventQuestIndex('event'));fresh=replace(entry(),screenPosition=(910,330))
        locator.stable=Mock(return_value=(Mock(),['proof'],'area',[fresh]))
        self.assertEqual(locator.locate(entry()),fresh);runner.touch.assert_called_once_with(['proof'],(910,330),'select_indexed_event_free_quest')
    def test_foreign_or_locked_cache_never_reads_or_touches(self):
        runner=self.runner();locator=quest.EventQuestLocator(runner,engine.EventQuestIndex('event'))
        for cached in (entry(eventKey='other'),entry(state='LOCKED')):
            with self.assertRaises(ScriptStop):locator.locate(cached)
        runner.read.assert_not_called();runner.touch.assert_not_called()
    def test_map_requires_adapter_and_fresh_proof_no_cached_touch(self):
        runner=self.runner();index=engine.EventQuestIndex('event')
        with self.assertRaises(ScriptStop):quest.EventQuestLocator(runner,index).locate(entry(mode='MAP'))
        cached=entry(mode='MAP');adapter=Mock(return_value=cached)
        quest.EventQuestLocator(runner,index,mapNavigator=adapter).locate(cached)
        adapter.assert_called_once_with(cached,maxPans=4);runner.touch.assert_not_called()
    def test_map_wrong_fresh_identity_stops(self):
        with self.assertRaises(ScriptStop):quest.EventQuestLocator(self.runner(),engine.EventQuestIndex('event'),mapNavigator=Mock(return_value=entry(title='错误',mode='MAP'))).locate(entry(mode='MAP'))
    def test_actual_scrollbar_and_signature(self):
        im=numpy.zeros((720,1280,3),dtype='uint8');im[96:300,1255:1267]=240
        self.assertEqual(quest.scrollbar(im),(96,300));self.assertEqual(len(quest.viewportSignature(im)),24)
    def test_local_corrected_title_requires_same_area_ap_text_and_full_title_hash(self):
        proof={'areaKey':'area','AP':5,'canonical':'人工确认的完整标题','ocrTexts':['实际OCR错字'],'titleHash':'0'*64,'source':'operator confirmed original full title'}
        self.assertEqual(quest.verifiedTitle('实际OCR错字',5,'area','0'*64,[proof]),proof['canonical'])
        for args in (('别的文本',5,'area','0'*64),('实际OCR错字',40,'area','0'*64),('实际OCR错字',5,'other','0'*64),('实际OCR错字',5,'area','f'*64)):
            self.assertEqual(quest.verifiedTitle(*args,[proof]),args[0])
    def test_conflicting_corrections_stop_and_do_not_click(self):
        proof={'areaKey':'area','AP':5,'canonical':'确认标题','ocrTexts':['实际文本'],'titleHash':'0'*64,'source':'operator'}
        with self.assertRaises(ScriptStop):quest.verifiedTitle('实际文本',5,'area','0'*64,[proof,{**proof,'canonical':'冲突标题'}])
    def test_three_fresh_stable_cards_tolerate_two_pixel_animation(self):
        runner=self.runner();locator=quest.EventQuestLocator(runner,engine.EventQuestIndex('event'))
        locator.view=Mock(side_effect=[(Mock(),[],'area',[entry()]),(Mock(),[],'area',[replace(entry(),screenPosition=(902,320))]),(Mock(),[],'area',[entry()])])
        with patch.object(quest.schedule,'sleep'):locator.stable('area')
        self.assertEqual(locator.view.call_count,3);runner.touch.assert_not_called()
    def test_available_badge_animation_does_not_change_quest_identity(self):
        runner=self.runner();locator=quest.EventQuestLocator(runner,engine.EventQuestIndex('event'))
        locator.view=Mock(side_effect=[(Mock(),[],'area',[entry()]),(Mock(),[],'area',[entry(state='AVAILABLE')]),(Mock(),[],'area',[entry()])])
        with patch.object(quest.schedule,'sleep'):locator.stable('area')
        self.assertEqual(locator.view.call_count,3);runner.touch.assert_not_called()
    def test_local_full_title_pixel_proof_tolerates_translation_but_not_other_pixels(self):
        import cv2
        image=numpy.random.default_rng(7).integers(0,255,(720,1280,3),dtype='uint8')
        with tempfile.TemporaryDirectory() as root:
            cv2.imwrite(str(Path(root)/'proof.png'),image[200:224,780:980])
            self.assertTrue(quest.patchMatch(image,(778,199,982,226),'proof.png',root))
            self.assertFalse(quest.patchMatch(image,(778,299,982,326),'proof.png',root))
            self.assertFalse(quest.patchMatch(image,(778,199,982,226),'../proof.png',root))
            proof={'areaKey':'area','AP':5,'canonical':'confirmed','ocrTexts':['actual'],'titleHash':'0'*64,'titlePatch':'proof.png','source':'operator'}
            self.assertEqual(quest.verifiedTitle('actual',5,'area','f'*64,[proof],image=image,box=(778,199,982,226),proofRoot=root),'confirmed')
            self.assertEqual(quest.verifiedTitle('another OCR substitution',5,'area','f'*64,[proof],image=image,box=(778,199,982,226),proofRoot=root),'confirmed')
            self.assertEqual(quest.verifiedTitle('actual',5,'area','f'*64,[proof],image=image,box=(778,299,982,326),proofRoot=root),'actual')

class CampaignTests(unittest.TestCase):
    def test_solver_rereads_current_mission_without_restarting_top_scan(self):
        runner=Mock();runner.newBattleEntries=0
        c=campaign.EventCampaignRunner(runner,engine.EventQuestIndex('event'),engine.MissionEvidenceDB('event'),engine.EventProfile('event','heading'))
        c.missionMenu=Mock();c.observeMissions=Mock(side_effect=ScriptStop('fresh observation failed'))
        with self.assertRaises(ScriptStop):c.solve({'mission':23})
        c.observeMissions.assert_called_once_with(23,fromTop=False)
        runner.touch.assert_not_called();runner.claimCompletedMission.assert_not_called()
    def test_selected_free_quest_only_allows_its_old_lock_as_read_only_fading_frame(self):
        runner=Mock();runner.newBattleEntries=0;runner.last=(Mock(),['origin'],'mission_gate');runner.wait.side_effect=ScriptStop('end observation')
        c=campaign.EventCampaignRunner(runner,engine.EventQuestIndex('event'),engine.MissionEvidenceDB('event'),engine.EventProfile('event','heading'))
        c.locator.locate=Mock(return_value=entry())
        def proof(items):return {'mission':23} if items==['origin'] else {'mission':24} if items==['different'] else None
        with patch.object(campaign.event,'findLockedEventMission',side_effect=proof),self.assertRaises(ScriptStop):c.battleQuest(entry())
        accepted=runner.wait.call_args.kwargs['blockedIntermediate']
        with patch.object(campaign.event,'findLockedEventMission',side_effect=proof):
            self.assertTrue(accepted(Mock(),['origin'],'mission_gate'))
            self.assertFalse(accepted(Mock(),['different'],'mission_gate'))
            self.assertFalse(accepted(Mock(),[],'unknown'))
        self.assertEqual(runner.wait.call_args.kwargs['timeout'],30);runner.touch.assert_not_called()
    def test_no_next_node_or_ledger_never_proves_completion(self):
        self.assertIsNone(campaign.completeProof([]));self.assertIsNone(campaign.completeProof([item('终幕',500,300)]))
        self.assertEqual(campaign.completeProof([item('活动主线已通关',500,300)]),'活动主线已通关')
    def test_weak_or_reward_choice_cannot_be_complete(self):
        self.assertIsNone(campaign.completeProof([item('活动主线已通关',500,300,score=.84)]))
        self.assertIsNone(campaign.completeProof([item('活动主线已通关',500,300),item('请选择奖励',500,400)]))
    def test_campaign_scope_must_match(self):
        with self.assertRaises(ValueError):campaign.EventCampaignRunner(Mock(),engine.EventQuestIndex('event'),engine.MissionEvidenceDB('other'),engine.EventProfile('event','heading'))
    def test_pipeline_states_and_goal_are_not_all_missions(self):
        self.assertEqual(engine.EventProfile('event','heading').goal,'CLEAR_MAIN_STORY')
        self.assertEqual(len(engine.CampaignState),12)

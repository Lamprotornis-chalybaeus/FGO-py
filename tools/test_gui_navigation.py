import logging
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'FGO-py'
sys.path.insert(0,str(APP))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('PYTHONDONTWRITEBYTECODE','1')

# Keep the regression tests independent of the logging sink and device.
if 'fgoLogging' not in sys.modules:
    fake=types.ModuleType('fgoLogging')
    fake.getLogger=logging.getLogger
    fake.logMeta=lambda logger:type
    fake.logit=lambda logger,transform=None:lambda func:func
    sys.modules['fgoLogging']=fake

oldCwd=os.getcwd()
os.chdir(APP)
try:
    import fgoConst
    import fgoEventProgress as event
    import fgoGuiOperation
    import fgoQuickFarm
    import fgoQuickQuest as daily
    import fgoKernel
finally:
    os.chdir(oldCwd)


class FakeSettings:
    appleTotal=0
    appleKind=0
    friendPolicy='first'
    friendMaxRefresh=2
    wait=True


class FakeRunner:
    def __init__(self,*args,**kwargs):
        self.args=args
        self.kwargs=kwargs
        self.appleTotal=kwargs.get('appleTotal',0)
        self.calls=[]
        self.result={'battle':0,'defeated':0,'turnPerBattle':0,'timePerBattle':0,'material':{}}
    def __call__(self,*args):self.calls.append(args)


class FakeDetect:
    def __init__(self):
        self.im=numpy.zeros((720,1280,3),dtype=numpy.uint8)
    def isChooseFriend(self):return False
    def isBattleFormation(self):return False
    def isTurnBegin(self):return False
    def isBattleFinished(self):return False


def item(text,x,y,w=140,h=24,score=1.0):
    return event.OcrItem(text,(x,y,x+w,y+h),score)


class DailyQuestTests(unittest.TestCase):
    def test_dynamic_title_type_and_difficulty_classification(self):
        screen=numpy.zeros((720,1280,3),dtype=numpy.uint8)
        spans=[
            item('每日替换 搜集种火〈枪·暗篇〉 极级',700,180,360),
            item('剑之修炼场 超级',700,360,260),
            item('打开宝物库之门 上级',700,540,290),
            item('推荐职阶 极级',700,620,200),
        ]
        entries=daily.parseDailyQuestEntries(spans,screen)
        self.assertEqual([(entry.quest_type,entry.difficulty)for entry in entries],[('ember','极级'),('training','超级'),('treasure','上级')])
        self.assertIn('搜集种火',entries[0].title)
        self.assertEqual(entries[0].type,'daily')
        self.assertTrue(entries[0].screenshot_signature)
        self.assertEqual(len(entries[0].discovered_position),3)

    def test_ocr_entries_dedupe_normalized_titles(self):
        entries=[
            daily.DailyQuestEntry('每日替换  搜集种火 极级','ember','极级','a',(0,800,200)),
            daily.DailyQuestEntry('每日替换搜集种火 极级','ember','极级','b',(1,800,200)),
        ]
        self.assertEqual(daily.deduplicateDailyEntries(entries),[entries[0]])

    def test_scan_goes_past_ten_scrolls_until_verified_bottom(self):
        detect=FakeDetect()
        entry=daily.DailyQuestEntry('搜集种火 极级','ember','极级','sig',(0,900,150))
        # Each swipe consumes another scrollbar observation; 12 moves precede
        # the true bottom. Animated background pixels are deliberately ignored.
        thumbs=[]
        for index in range(12):thumbs.extend([(100+index*20,210+index*20),(120+index*20,230+index*20)])
        thumbs.extend([(462,575),(462,575),(462,575),(462,575),(99,213),(99,213),(99,213),(99,213)])
        with patch.object(daily.XDetect,'region','CN'), \
             patch.object(daily,'Detect',return_value=detect), \
             patch.object(daily,'_isDailyPage',return_value=True), \
             patch.object(daily,'_scrollToTop',return_value=(detect,True)) as to_top, \
             patch.object(daily,'_swipe',return_value=(detect,True)) as swipe, \
             patch.object(daily,'_scrollbar',side_effect=thumbs), \
             patch.object(daily,'_dailyEntriesAt',return_value=[entry]):
            result=daily.scanDailyQuestsCN()
        self.assertEqual(swipe.call_count,15)
        self.assertEqual(to_top.call_count,1)
        self.assertTrue(result['reachedEnd'])
        self.assertTrue(result['complete'])
        self.assertEqual(result['screens'],17)
        self.assertEqual(result['entries'],[entry])

    def test_scroll_to_top_uses_thumb_boundary_despite_animation(self):
        detect=FakeDetect()
        with patch.object(daily,'Detect',return_value=detect), \
             patch.object(daily,'_scrollbar',return_value=(99,213)), \
             patch.object(daily,'_swipe',return_value=(detect,True)) as swipe:
            _,at_top=daily._scrollToTop()
        self.assertTrue(at_top)
        swipe.assert_called_once_with(detect,True)

    def test_daily_task_is_a_typed_gui_queue_item(self):
        entry=daily.DailyQuestEntry('搜集种火 极级','ember','极级','sig',(0,900,250))
        task=fgoGuiOperation.QuestTask.daily(entry,5)
        self.assertEqual((task.type,task.target,task.repetitions),('daily',entry,5))

    def test_daily_operation_uses_locator_then_existing_main(self):
        entry=daily.DailyQuestEntry('搜集种火 极级','ember','极级','sig',(0,900,250))
        queue=[fgoGuiOperation.QuestTask.daily(entry,3)]
        runner=FakeRunner()
        with patch.object(daily,'gotoDailyEntry') as locate, patch.object(fgoKernel,'Main',return_value=runner) as main:
            result=fgoGuiOperation.GuiQueueOperation(queue,FakeSettings())()
        locate.assert_called_once_with(entry)
        main.assert_called_once()
        self.assertEqual(runner.calls,[(0,3)])
        self.assertEqual(result['battle'],0)

    def test_legacy_numeric_operation_entry_remains_supported(self):
        quest=(1,2,3,0)
        queue=[(quest,2)]
        runner=FakeRunner()
        with patch.object(fgoKernel,'Operation',return_value=runner) as operation:
            fgoGuiOperation.GuiQueueOperation(queue,FakeSettings())()
        operation.assert_called_once()
        self.assertEqual(operation.call_args.args[0],[(quest,2)])
        self.assertIs(operation.call_args.kwargs['wait'],False)
        self.assertEqual(runner.calls,[()])

    def test_metadata_queue_handoff_does_not_wait_for_total_ap(self):
        quest=(1,0,7,0);queue=[fgoGuiOperation.QuestTask.metadata(quest,20),fgoGuiOperation.QuestTask.metadata((1,0,2,0),20)];before=queue[:];events=[]
        from fgoDetect import XDetectCN
        with patch.object(fgoKernel,'goto',side_effect=lambda q:events.append(('goto',q))), \
             patch.object(fgoKernel.Main,'__call__',side_effect=fgoKernel.ScriptStop('handoff sentinel; no game input')) as main, \
             patch.object(XDetectCN,'getAp',side_effect=AssertionError('must not estimate total queue AP')), \
             patch.object(fgoKernel.schedule,'sleep',side_effect=AssertionError('must not wait for AP')):
            with self.assertRaisesRegex(fgoKernel.ScriptStop,'handoff sentinel'):
                fgoGuiOperation.GuiQueueOperation(queue,FakeSettings(),onNavigation=events.append)()
        main.assert_called_once_with(0,20)
        self.assertIn(('goto',quest),events)
        self.assertTrue(any(isinstance(e,str) and '正在进入关卡' in e for e in events))
        self.assertEqual(queue,before)

class CnApTests(unittest.TestCase):
    def detector(self):
        from fgoDetect import XDetectCN
        d=XDetectCN.__new__(XDetectCN);d.im=numpy.zeros((720,1280,3),numpy.uint8);return d
    def test_current_ap_preserves_overflow_and_maximum_digit_width(self):
        from fgoDetect import OCR
        for text,expected in [('723/70',723),('23/70',23),('0/70',0),('144/144',144),('1072/170',1072)]:
            with self.subTest(text=text),patch.object(OCR.EN,'ocr_single_line',return_value=(text,.96)):
                self.assertEqual(self.detector().getAp(),expected)
    def test_missing_slash_stops_instead_of_dividing_digits(self):
        from fgoDetect import OCR
        with patch.object(OCR.EN,'ocr_single_line',return_value=('72370',.96)):
            with self.assertRaisesRegex(fgoKernel.ScriptStop,'AP识别失败'):self.detector().getAp()
    def test_disagreeing_ap_reads_stop(self):
        from fgoDetect import OCR
        with patch.object(OCR.EN,'ocr_single_line',side_effect=[('723/70',.96),('72/70',.96)]):
            with self.assertRaisesRegex(fgoKernel.ScriptStop,'不一致'):self.detector().getAp()
    def test_uncertain_ap_read_stops(self):
        from fgoDetect import OCR
        with patch.object(OCR.EN,'ocr_single_line',return_value=('723/70',.84)):
            with self.assertRaisesRegex(fgoKernel.ScriptStop,'AP识别失败'):self.detector().getAp()


class EventProgressTests(unittest.TestCase):
    def test_activity_map_detection_uses_generic_map_ui_signals(self):
        screen=[item('关卡举办时间 剩余13日',950,245,270),item('新！',650,100,65),item('序幕「Goodbye 池田屋」',780,120,320),item('AP5',780,200,60)]
        self.assertTrue(event._eventMap(screen))
        self.assertEqual(event.classifyEventState(screen),'event_map')
        self.assertIsNotNone(event.findNextMainQuest(screen))

    def test_prologue_node_can_be_found_when_new_badge_ocr_is_missing(self):
        screen=[item('关卡举办时间 剩余13日',950,245,270),item('序幕「Goodbye 池田屋」',780,120,320),item('AP5',780,200,60)]
        candidate=event.findNextMainQuest(screen)
        self.assertIsNotNone(candidate)
        self.assertIn('序幕',candidate['title'])

    def test_daily_page_is_not_misclassified_as_event_map(self):
        screen=[item('每日任务',1060,5,210,50),item('关卡举办时间 剩余4小时',950,100,270),item('每日替换 搜集种火 初级',780,180,280),item('AP40',780,250,60)]
        self.assertEqual(event.classifyEventState(screen),'daily_quest')

    def test_start_confirmation_stops_without_pressing_start(self):
        detect=FakeDetect()
        screen=[item('是否开始关卡？',500,350,260),item('取消',400,540,80),item('开始',800,540,80)]
        with patch.object(event.XDetect,'region','CN'), \
             patch.object(event,'Detect',return_value=detect), \
             patch.object(event,'_readScreen',return_value=screen), \
             patch.object(event.fgoDevice.device,'touch') as touch:
            result=event.progress()
        self.assertEqual(result['state'],'start_confirmation')
        touch.assert_not_called()

    def test_story_pause_is_default_and_never_calls_skip(self):
        detect=FakeDetect()
        with patch.object(event.XDetect,'region','CN'), \
             patch.object(event,'Detect',return_value=detect), \
             patch.object(event,'_readScreen',return_value=[]), \
             patch.object(event,'_openEventMap',return_value=(detect,[])), \
             patch.object(event,'classifyEventState',return_value='story'), \
             patch.object(event,'_skipStory') as skip, \
             patch.object(event.fgoDevice.device,'touch') as touch:
            result=event.progress()
        self.assertEqual(fgoConst.CONFIG['eventStoryMode'],'pause')
        self.assertEqual(result['state'],'story_paused')
        skip.assert_not_called()
        touch.assert_not_called()

    def test_skip_requires_positive_unique_button_detection(self):
        with patch.object(event,'findSkipButton',return_value=None), patch.object(event.fgoDevice.device,'touch') as touch:
            result=event._skipStory([])
        self.assertEqual(result['state'],'blocked')
        touch.assert_not_called()
        self.assertEqual(event.findSkipButton([item('SKIP',1000,30)]),(1070,42))

    def test_skip_confirmation_requires_positive_text_evidence(self):
        self.assertIsNone(event.findSkipConfirmation([item('确定',700,400),item('取消',500,400)]))
        self.assertEqual(event.findSkipConfirmation([item('是否跳过剧情？',420,300),item('取消',500,400),item('确定',700,400)]),(770,412))

    def test_no_available_main_quest_stops_without_tapping(self):
        detect=FakeDetect()
        with patch.object(event.XDetect,'region','CN'), \
             patch.object(event,'Detect',return_value=detect), \
             patch.object(event,'_readScreen',return_value=[]), \
             patch.object(event,'_openEventMap',return_value=(detect,[])), \
             patch.object(event,'classifyEventState',return_value='event_map'), \
             patch.object(event,'findNextMainQuest',return_value=None), \
             patch.object(event,'findMissionGate',return_value=[]), \
             patch.object(event.fgoDevice.device,'touch') as touch:
            result=event.progress()
        self.assertEqual(result['state'],'no_main_quest')
        touch.assert_not_called()

    def test_mission_gate_stops_without_random_farming_or_claim(self):
        detect=FakeDetect()
        with patch.object(event.XDetect,'region','CN'), \
             patch.object(event,'Detect',return_value=detect), \
             patch.object(event,'_readScreen',return_value=[]), \
             patch.object(event,'_openEventMap',return_value=(detect,[])), \
             patch.object(event,'classifyEventState',return_value='event_map'), \
             patch.object(event,'findNextMainQuest',return_value=None), \
             patch.object(event,'findMissionGate',return_value=['完成任务 No.1']), \
             patch.object(event,'findClaimableMissionReward') as claim, \
             patch.object(event.fgoDevice.device,'touch') as touch:
            result=event.progress(autoClaim=False)
        self.assertEqual(result['state'],'mission_blocked')
        claim.assert_not_called()
        touch.assert_not_called()

    def test_reward_toggle_never_claims_from_unconfirmed_screen(self):
        gate=[item('完成任务 No.1',400,300)]
        result=event._missionRewardGate(gate,True)
        self.assertEqual(result['state'],'mission_blocked')
        self.assertIn('未可靠识别为活动任务列表',result['message'])
        self.assertFalse(event._missionListConfirmed(gate))

    def test_only_completed_reward_row_is_claimable(self):
        eligible=[item('活动任务列表',400,100),item('任务 No.1 已完成',350,300),item('领取',900,300)]
        ineligible=[item('活动任务列表',400,100),item('任务 No.2 进行中',350,300),item('领取',900,300)]
        self.assertTrue(event._missionListConfirmed(eligible))
        self.assertEqual(event.findClaimableMissionReward(eligible),(970,312))
        self.assertIsNone(event.findClaimableMissionReward(ineligible))

    def test_event_battle_reuses_main_friend_picker_and_battle_ai(self):
        detect=FakeDetect();formation=[item('开始任务',900,540)];finished=[]
        battle=Mock(return_value=True);battle.result={'turn':3,'time':42.0,'material':{}}
        main=Mock()
        with patch.object(fgoKernel,'Main',return_value=main) as main_factory, \
             patch.object(event,'_waitClassified',side_effect=[(detect,formation,'formation'),(detect,[],'battle')]), \
             patch.object(fgoKernel,'Battle',return_value=battle) as battle_factory, \
             patch.object(event,'Detect',return_value=detect), \
             patch.object(event,'_readScreen',return_value=finished), \
             patch.object(event,'classifyEventState',return_value='event_map'), \
             patch.object(event.fgoDevice.device,'touch') as touch:
            _,_,result=event._runEventBattle(detect,[], 'support','first',2)
        main_factory.assert_called_once_with(appleTotal=0,appleKind=0,battleClass=battle_factory,friendPolicy='first',friendMaxRefresh=2)
        main.chooseFriend.assert_called_once()
        touch.assert_called_once_with((970,552))
        battle_factory.assert_called_once_with()
        battle.assert_called_once_with()
        self.assertEqual(result['state'],'event_map')
        self.assertEqual(result['battles'],1)


class GuiIntegrationTests(unittest.TestCase):
    def test_daily_entries_populate_the_quest_combo_box(self):
        from types import SimpleNamespace
        from fgoGui import MainWindow

        class ComboBox:
            def __init__(self):self.items=[];self.enabled=False
            def clear(self):self.items.clear()
            def addItem(self,title,data):self.items.append((title,data))
            def setEnabled(self,value):self.enabled=value

        entries=[
            daily.DailyQuestEntry('每日替换 搜集种火 极级','ember','极级','sig',(0,900,250)),
            daily.DailyQuestEntry('剑之修炼场 超级','training','超级','sig2',(1,900,350)),
        ]
        combo=ComboBox()
        MainWindow.populateDailyQuests(SimpleNamespace(CBB_QUEST=combo,dailyEntries=entries,_dailyScanPending=False))
        self.assertEqual([title for title,_ in combo.items],[entry.title for entry in entries])
        self.assertEqual([data for _,data in combo.items],entries)
        self.assertTrue(combo.enabled)

    def test_default_modes_and_event_bounds(self):
        self.assertEqual(fgoQuickFarm.MODES,('current','plan','event'))
        self.assertEqual(fgoConst.CONFIG['eventStoryMode'],'pause')
        self.assertFalse(fgoConst.CONFIG['eventAutoClaimRewards'])
        self.assertEqual(fgoConst.CONFIG['eventProgressLimit'],1)

    def test_generated_main_button_dispatches_quickfarm(self):
        from PySide6.QtWidgets import QApplication,QMainWindow
        from fgoMainWindow import Ui_fgoMainWindow
        app=QApplication.instance() or QApplication([])
        class StubWindow(QMainWindow):
            def __init__(self):super().__init__();self.started=0
            def quickFarm(self):self.started+=1
            def __getattr__(self,name):return lambda *args,**kwargs:None
        window=StubWindow();ui=Ui_fgoMainWindow();ui.setupUi(window)
        ui.BTN_MAIN.click()
        self.assertEqual(window.started,1)
        self.assertEqual(ui.BTN_MAIN.text(),'开始智能周回')
        self.assertEqual(ui.TXT_EVENT_LIMIT.minimum(),1)
        self.assertEqual(ui.TXT_EVENT_LIMIT.maximum(),100)
        self.assertFalse(ui.CKB_EVENT_REWARD.isChecked())
        self.assertEqual(ui.CBB_QUICKMODE.count(),3)
        app.processEvents()


if __name__=='__main__':unittest.main()

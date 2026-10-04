"""Static safety regressions for complete scanning, locating and event UI."""
import runpy
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,Mock,MagicMock
import numpy

env=runpy.run_path(str(Path(__file__).with_name('test_gui_navigation.py')))
daily=env['daily'];event=env['event'];kernel=env['fgoKernel'];operation=env['fgoGuiOperation']
Frame=env['FakeDetect'];item=env['item'];Settings=env['FakeSettings'];Runner=env['FakeRunner']

class FullDailyTests(unittest.TestCase):
    def test_valid_card_with_missing_cn_ap_label_requires_independent_ap_read(self):
        title='打开宝物库之门初级';spans=[item(title,31,135,240,20),item('AP1O',33,205,63,28)]
        with patch.object(daily.OCR.ZHS,'detect_and_ocr',return_value=spans),patch.object(daily.OCR.ZHS,'ocr_single_line',return_value=(title,.98)),patch.object(daily.OCR.EN,'ocr_single_line',return_value=('AP10',.96)):
            self.assertEqual([e.title for e in daily._dailyEntriesAt(Frame())],['打开宝物库之门 初级'])
        with patch.object(daily.OCR.ZHS,'detect_and_ocr',return_value=spans),patch.object(daily.OCR.EN,'ocr_single_line',return_value=('?',.4)):
            self.assertEqual(daily._dailyEntriesAt(Frame()),[])

    def test_daily_rotation_prefix_is_not_a_second_quest(self):
        a=daily.DailyQuestEntry('每日替换 骑之修炼场 超级','training','超级','sig',(0,900,150))
        b=daily.DailyQuestEntry('骑之修炼场 超级','training','超级','sig',(1,900,150))
        self.assertEqual(daily.deduplicateDailyEntries([a,b]),[a])

    def test_broad_ocr_agreement_cannot_bypass_single_line_verification(self):
        spans=[item('每日替换搜集种火<枪·篇>极级',31,135,295,20),item('AP40',33,205,63,28)]
        title='每日替换搜集种火<枪·暗篇>极级'
        with patch.object(daily.OCR.ZHS,'detect_and_ocr',return_value=spans),patch.object(daily.OCR.ZHS,'ocr_single_line',side_effect=[(title,.98),(title,.97),(title,.96)]):
            entries=daily._dailyEntriesAt(Frame())
        self.assertEqual([e.title for e in entries],['每日替换 搜集种火<枪·暗篇> 极级'])

    def test_menu_swipe_uses_standard_adb_with_render_coordinates(self):
        android=Mock(spec=daily.fgoDevice.Android)
        android.name='127.0.0.1:5555';android.display_info={'orientation':0};android.adb=Mock()
        android.scale=2;android.border=(2,0);android.render=(10,20,640,360);android.mutex=MagicMock()
        with patch.object(daily.fgoDevice.device,'I',android),patch.object(daily.fgoDevice.device,'swipe') as swipe:
            daily._menuSwipe((950,540),(950,240))
        android.adb.shell.assert_called_once_with('input touchscreen swipe 487 290 487 140 350');swipe.assert_not_called()

    def test_menu_swipe_preserves_original_transport_for_other_orientation(self):
        android=Mock(spec=daily.fgoDevice.Android);android.name='device';android.display_info={'orientation':1};android.adb=Mock()
        with patch.object(daily.fgoDevice.device,'I',android),patch.object(daily.fgoDevice.device,'swipe') as swipe:
            daily._menuSwipe((950,540),(950,240))
        swipe.assert_called_once_with((950,540),(950,240));android.adb.shell.assert_not_called()

    def test_ap_row_recovers_only_a_twice_verified_actual_title(self):
        title='每日替换骑之修炼场超级'
        spans=[item('母日各换骑之修炼场 超级',31,135,280),item('AP40',33,205,65,28)]
        with patch.object(daily.OCR.ZHS,'detect_and_ocr',return_value=spans),patch.object(daily.OCR.ZHS,'ocr_single_line',side_effect=[(title,.97),(title,.96),(title,.96)]):
            entries=daily._dailyEntriesAt(Frame())
        self.assertEqual([e.title for e in entries],['每日替换 骑之修炼场 超级'])

    def test_forward_reverse_disagreement_does_not_publish_complete_list(self):
        # Reverse passes are retired: a missing actual card still forbids publication.
        from daily_index_test_support import World
        with World().patched() as w:
            w.missing={4};w.local_missing={4}
            with self.assertRaises(daily.ScriptStop):daily.scanDailyQuestsCN()
            w.touch.assert_not_called()

    def test_return_omission_must_be_independently_located_before_publication(self):
        from daily_index_test_support import World
        with World().patched() as w:
            w.missing={4};result=daily.scanDailyQuestsCN()
        self.assertTrue(result['complete']);self.assertEqual(len(result['entries']),25)
        self.assertGreater(result['metrics']['gapRecoveries'],0);self.assertEqual(w.top,99)

    def test_near_top_thumb_is_not_accepted_until_it_stops_moving(self):
        frame=Frame()
        with patch.object(daily,'Detect',return_value=frame),patch.object(daily,'_swipe',return_value=(frame,True)) as swipe,patch.object(daily,'_scrollbar',side_effect=[(104,218),(99,213),(99,213),(99,213)]):
            self.assertTrue(daily._scrollToTop()[1])
        self.assertEqual(swipe.call_count,2)

    def test_unverified_proposals_without_ap_are_not_actionable(self):
        spans=[item('母日各换骑之修炼场 超级',780,170),item('之修炼场 超级',780,340),item('骑之修炼场 超级',780,500,220),item('AP40',780,570)]
        entries=daily.parseDailyQuestEntries(spans,Frame().im,requireCardMetadata=True)
        self.assertEqual([e.title for e in entries],['骑之修炼场 超级'])

    def test_card_requires_its_own_ap_row(self):
        spans=[item('剑之修炼场 极级',780,180,220),item('AP40',780,250),item('骑之修炼场 极级',780,400,220)]
        entries=daily.parseDailyQuestEntries(spans,Frame().im,requireCardMetadata=True)
        self.assertEqual([e.title for e in entries],['剑之修炼场 极级'])

    def test_clipped_title_at_top_is_rejected_even_with_ap(self):
        spans=[item('剑之修炼场 极级',780,105,220),item('AP40',780,180)]
        self.assertEqual(daily.parseDailyQuestEntries(spans,Frame().im,requireCardMetadata=True),[])

    def test_disagreeing_ocr_fails_scan_instead_of_adding_variant(self):
        first=[item('每日替换骑之修炼场 超级',780,220,260),item('AP40',780,300)]
        second=[item('母日各换骑之修炼场 超级',780,220,260),item('AP40',780,300)]
        # OCR coordinates are relative to each requested crop.
        def local(items,x):return [item(i.text,i.box[0]-x,i.box[1]-105,i.box[2]-i.box[0],i.box[3]-i.box[1]) for i in items]
        with patch.object(daily.OCR.ZHS,'detect_and_ocr',side_effect=[local(first,750),local(second,740)]), \
             patch.object(daily.OCR.ZHS,'ocr_single_line',return_value=('',0)):
            with self.assertRaises(daily.ScriptStop):daily._dailyEntriesAt(Frame())

    def test_missing_glyph_can_be_verified_by_two_single_line_reads(self):
        def spans(x,title):return [item(title,781-x,469-105,295,20),item('AP40',784-x,539-105,63,28)]
        title='每日替换搜集种火<枪·暗篇>极级'
        with patch.object(daily.OCR.ZHS,'detect_and_ocr',side_effect=[spans(750,title),spans(740,title.replace('暗',''))]), \
             patch.object(daily.OCR.ZHS,'ocr_single_line',side_effect=[(title,.96),(title,.98),(title,.97)]):
            entries=daily._dailyEntriesAt(Frame())
        self.assertEqual([e.title for e in entries],['每日替换 搜集种火<枪·暗篇> 极级'])

    def test_scrollbar_boundary_ignores_animation_outside_track(self):
        im=numpy.zeros((720,1280,3),dtype=numpy.uint8);im[99:213,1253:1264]=255
        self.assertEqual(daily._scrollbar(im),(99,213))
        im[120:600,650:1120]=255
        self.assertEqual(daily._scrollbar(im),(99,213))
        im[99:213,1253:1264]=0;im[462:575,1253:1264]=255
        self.assertEqual(daily._scrollbar(im),(462,575))

    def test_stalled_scan_aborts_without_partial_result(self):
        from daily_index_test_support import World
        with World().patched() as w:
            w.stalled=True
            with self.assertRaises(daily.ScriptStop):daily.scanDailyQuestsCN()
        self.assertEqual(len(w.swipes),3)

    def test_selected_quest_must_cover_kernel_first_quest_coordinate(self):
        entry=daily.DailyQuestEntry('剑之修炼场 极级','training','极级','sig',(0,880,160))
        with patch.object(daily.XDetect,'region','CN'),patch.object(daily,'Detect',return_value=Frame()), \
             patch.object(daily,'openDailyPageCN'),patch.object(daily,'_dailyLocatorFrameCN'),patch.object(daily,'_scrollbar',return_value=(100,149)),patch.object(daily,'_scrollToTop',return_value=(Frame(),True)), \
             patch.object(daily,'_dailyEntriesAt',return_value=[entry]),patch.object(daily.fgoDevice.device,'touch') as touch:
            self.assertEqual(daily.gotoDailyEntry(entry)['position'],(880,160))
        touch.assert_not_called()

    def test_bottom_card_can_cover_click_position_without_being_at_exact_top(self):
        entry=daily.DailyQuestEntry('打开宝物库之门 极级','treasure','极级','sig',(0,880,215))
        with patch.object(daily.XDetect,'region','CN'),patch.object(daily,'Detect',return_value=Frame()), \
             patch.object(daily,'openDailyPageCN'),patch.object(daily,'_dailyLocatorFrameCN'),patch.object(daily,'_scrollbar',return_value=(100,149)),patch.object(daily,'_scrollToTop',return_value=(Frame(),True)), \
             patch.object(daily,'_dailyEntriesAt',return_value=[entry]),patch.object(daily.fgoDevice.device,'swipe') as swipe:
            self.assertEqual(daily.gotoDailyEntry(entry)['position'],(880,215))
        swipe.assert_not_called()

    def test_locator_failure_preserves_queue(self):
        task=operation.QuestTask.daily(daily.DailyQuestEntry('搜集种火 极级','ember','极级','sig',(0,880,150)),5)
        queue=[task]
        with patch.object(daily,'gotoDailyEntry',side_effect=daily.ScriptStop('locate failed')),patch.object(kernel,'Main') as main:
            with self.assertRaises(daily.ScriptStop):operation.GuiQueueOperation(queue,Settings())()
        self.assertEqual(queue,[task]);main.assert_not_called()

    def test_global_limit_preserves_unfinished_repetitions(self):
        task=operation.QuestTask.daily(daily.DailyQuestEntry('搜集种火 极级','ember','极级','sig',(0,880,150)),5)
        queue=[task];runner=Runner();runner.result['battle']=4
        with patch.object(daily,'gotoDailyEntry'),patch.object(kernel,'Main',return_value=runner):
            result=operation.GuiQueueOperation(queue,Settings())()
        self.assertEqual(result['battle'],4);self.assertEqual(queue[0].repetitions,1)

class EventStateTests(unittest.TestCase):
    def test_event_team_restriction_stops_before_choosing_quest(self):
        screen=[item('关卡举办时间 剩余13日',950,245,270),item('序幕',780,120,120),item('AP5',780,200,60),item('编制需符合要求',640,220,150)]
        with patch.object(event.XDetect,'region','CN'),patch.object(event,'Detect',return_value=Frame()), \
             patch.object(event,'_readScreen',return_value=screen),patch.object(event.fgoDevice.device,'touch') as touch:
            result=event.progress()
        self.assertEqual(result['state'],'blocked');self.assertIn('编队限制',result['message']);touch.assert_not_called()
    def test_transition_wait_does_not_return_the_previous_menu(self):
        with patch.object(event,'Detect',return_value=Frame()),patch.object(event,'_readScreen',return_value=[]), \
             patch.object(event,'classifyEventState',side_effect=['home','event_map']) as classify:
            _,_,state=event._waitClassified(3,exclude=('home',))
        self.assertEqual(state,'event_map');self.assertEqual(classify.call_count,2)
    def test_event_timer_below_banner_is_visible_from_home(self):
        screen=[item('通知',80,20),item('活动举办时间 剩余13日',970,420,240)]
        self.assertIsNotNone(event._eventAnchor(screen))

    def test_clipped_event_banner_is_scrolled_into_view_before_click(self):
        clipped=[item('通知',80,20),item('活动举办时间 剩余13日',970,105,240)]
        full=[item('通知',80,20),item('活动举办时间 剩余13日',970,420,240)]
        with patch.object(event,'Detect',return_value=Frame()),patch.object(event,'_readScreen',return_value=full), \
             patch.object(event.fgoQuickQuest,'_swipe',return_value=(Frame(),True)) as swipe, \
             patch.object(event,'_waitClassified',return_value=(Frame(),[],'event_map')), \
             patch.object(event.fgoDevice.device,'touch') as touch:
            event._openEventMap(Frame(),clipped)
        swipe.assert_called_once();touch.assert_called_once_with((1090,362))

    def test_event_navigation_exits_daily_and_gate_then_taps_banner_not_timer(self):
        frames=[
            [item('关闭',80,20),item('每日任务',1060,5)],
            [item('关闭',80,20),item('迦勒底之门',1020,5)],
            [item('通知',80,20),item('活动举办时间 剩余13日',970,420,240)],
        ]
        with patch.object(event,'Detect',return_value=Frame()),patch.object(event,'_readScreen',side_effect=frames[1:]), \
             patch.object(event,'_waitClassified',return_value=(Frame(),[],'event_map')), \
             patch.object(event.schedule,'sleep'),patch.object(event.fgoDevice.device,'touch') as touch:
            event._openEventMap(Frame(),frames[0])
        self.assertEqual([v.args[0] for v in touch.call_args_list],[(150,32),(150,32),(1090,362)])
    def test_confirmation_precedes_background_support_detection(self):
        screen=[item('是否开始关卡？',500,300),item('取消',400,540),item('开始',800,540)]
        self.assertEqual(event.classifyEventState(screen,{'choose_friend':True}),'start_confirmation')

    def test_daily_card_on_home_does_not_classify_as_daily_page(self):
        screen=[item('每日任务',950,250),item('活动举办时间 剩余13日',950,190)]
        self.assertEqual(event.classifyEventState(screen),'home')

    def test_story_can_resume_into_default_pause_without_clicking(self):
        screen=[item('MENU',800,50),item('这是一段待阅读的剧情文本',400,600)]
        with patch.object(event.XDetect,'region','CN'),patch.object(event,'Detect',return_value=Frame()), \
             patch.object(event,'_readScreen',return_value=screen),patch.object(event.fgoDevice.device,'touch') as touch:
            result=event.progress()
        self.assertEqual(result['state'],'story_paused');touch.assert_not_called()

    def test_ap_defeat_and_friend_request_never_trigger_taps(self):
        for flag in ('ap_empty','defeated','friend_request'):
            with self.subTest(flag=flag),patch.object(event.XDetect,'region','CN'),patch.object(event,'Detect',return_value=Frame()), \
                 patch.object(event,'_readScreen',return_value=[]),patch.object(event,'_detectFlags',return_value={flag:True}), \
                 patch.object(event.fgoDevice.device,'touch') as touch:
                self.assertEqual(event.progress()['state'],'blocked');touch.assert_not_called()

class GuiLayoutTests(unittest.TestCase):
    def test_event_hint_and_status_fit_without_intersecting_controls(self):
        from PySide6.QtWidgets import QApplication,QMainWindow,QGridLayout
        from fgoMainWindow import Ui_fgoMainWindow
        from fgoGui import MainWindow
        app=QApplication.instance() or QApplication([])
        class Stub(QMainWindow):
            def __getattr__(self,name):return lambda *a,**k:None
        window=Stub();ui=Ui_fgoMainWindow();ui.setupUi(window)
        context=SimpleNamespace(**vars(ui),config={})
        MainWindow.quickModeChanged(context,2)
        ui.LBL_EVENT_STATUS.setText('已进入剧情，请阅读完成后继续。未点击跳过。')
        window.resize(710,740);window.show();app.processEvents()
        self.assertIsInstance(ui.LAYOUT_QUICKFARM,QGridLayout)
        for label in (ui.LBL_QUICK_HINT,ui.LBL_EVENT_STATUS):
            self.assertGreaterEqual(label.height(),label.heightForWidth(label.width()))
        self.assertLess(ui.LBL_QUICK_HINT.geometry().bottom(),ui.BTN_MAIN.geometry().top())
        window.close()

if __name__=='__main__':unittest.main()

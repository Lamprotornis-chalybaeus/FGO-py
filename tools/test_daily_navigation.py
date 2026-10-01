"""CN daily navigation safety regressions; no device or game is required."""
import logging
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import call,patch

import numpy

APP=Path(__file__).resolve().parents[1]/'FGO-py'
sys.path.insert(0,str(APP))
if 'fgoLogging' not in sys.modules:
    fake=types.ModuleType('fgoLogging')
    fake.getLogger=logging.getLogger
    fake.logMeta=lambda logger:type
    fake.logit=lambda logger,transform=None:lambda func:func
    sys.modules['fgoLogging']=fake
oldCwd=os.getcwd();os.chdir(APP)
try:import fgoQuickQuest as daily
finally:os.chdir(oldCwd)

# Generic UI labels sampled from the local CN client, without account data.
CLOSE=('关闭',(79,25,140,60))
NOTIFY=('通知',(83,27,135,57))
GATE_CARD=('迦勒底之门',(767,372,979,417))
GATE_HEADER=('迦勒底之门',(1002,6,1274,59))
DAILY_CARD=('每日任务',(921,216,1088,261))
DAILY_HEADER=('每日任务',(1063,4,1273,59))
EVENT=[CLOSE,('关卡举办时间 剩余13日',(968,233,1213,260))]
HOME=[NOTIFY,GATE_CARD]
GATE=[CLOSE,GATE_HEADER,DAILY_CARD]
DAILY=[CLOSE,DAILY_HEADER]

class Frame:
    im=numpy.zeros((720,1280,3),dtype=numpy.uint8)
    def isMainInterface(self):return True


class DailyNavigationTests(unittest.TestCase):
    def runNavigation(self,labels):
        return patch.object(daily,'_navigationLabels',side_effect=labels)

    def test_activity_quest_list_returns_via_close_instead_of_searching_gate(self):
        self.assertEqual(daily.dailyNavigationAction(EVENT),('close',(109,42)))

    def test_root_and_gate_use_distinct_title_regions(self):
        self.assertEqual(daily.dailyNavigationAction(HOME),('gate',(873,394)))
        self.assertEqual(daily.dailyNavigationAction(GATE),('daily',(1004,238)))
        self.assertEqual(daily.dailyNavigationAction(DAILY),('ready',None))

    def test_event_to_daily_touches_only_close_gate_daily(self):
        with patch.object(daily.XDetect,'region','CN'), \
             patch.object(daily,'Detect',return_value=Frame()), \
             self.runNavigation([EVENT,HOME,GATE,DAILY]), \
             patch.object(daily.schedule,'sleep'), \
             patch.object(daily.fgoDevice.device,'touch') as touch, \
             patch.object(daily.fgoDevice.device,'swipe') as swipe:
            self.assertEqual(daily.openDailyPageCN(),{'type':'DailyPage'})
        self.assertEqual(touch.call_args_list,[call((109,42)),call((873,394)),call((1004,238))])
        swipe.assert_not_called()

    def test_already_daily_does_not_touch_a_quest(self):
        with patch.object(daily.XDetect,'region','CN'), \
             patch.object(daily,'Detect',return_value=Frame()), \
             self.runNavigation([DAILY]), \
             patch.object(daily.fgoDevice.device,'touch') as touch:
            daily.openDailyPageCN()
        touch.assert_not_called()

    def test_confirmation_over_daily_background_is_blocked(self):
        labels=DAILY+[('是否开始关卡？',(400,300,850,370)),('取消',(400,500,490,550)),('开始',(800,500,890,550))]
        self.assertEqual(daily.dailyNavigationAction(labels),('blocked',None))
        with patch.object(daily.XDetect,'region','CN'), \
             patch.object(daily,'Detect',return_value=Frame()), \
             self.runNavigation([labels]), \
             patch.object(daily.fgoDevice.device,'touch') as touch:
            with self.assertRaises(daily.ScriptStop):daily.openDailyPageCN()
        touch.assert_not_called()

    def test_unknown_page_and_battle_are_not_navigated(self):
        self.assertEqual(daily.dailyNavigationAction([CLOSE]),('blocked',None))
        with patch.object(daily.XDetect,'region','CN'), \
             patch.object(daily,'Detect',return_value=types.SimpleNamespace(im=Frame.im,isMainInterface=lambda:False)), \
             patch.object(daily,'_navigationLabels') as ocr, \
             patch.object(daily.fgoDevice.device,'touch') as touch:
            with self.assertRaises(daily.ScriptStop):daily.openDailyPageCN()
        ocr.assert_not_called();touch.assert_not_called()

    def test_same_page_after_tap_is_not_clicked_repeatedly(self):
        with patch.object(daily.XDetect,'region','CN'), \
             patch.object(daily,'Detect',return_value=Frame()), \
             patch.object(daily,'_navigationLabels',return_value=HOME), \
             patch.object(daily.schedule,'sleep'), \
             patch.object(daily.fgoDevice.device,'touch') as touch:
            with self.assertRaises(daily.ScriptStop):daily.openDailyPageCN()
        touch.assert_called_once_with((873,394))

    def test_transition_after_verified_close_waits_without_touching_unknown_frame(self):
        hidden=types.SimpleNamespace(im=Frame.im,isMainInterface=lambda:False)
        with patch.object(daily.XDetect,'region','CN'), \
             patch.object(daily,'Detect',side_effect=[Frame(),hidden,Frame(),Frame(),Frame(),Frame()]), \
             self.runNavigation([EVENT,[],HOME,GATE,DAILY]), \
             patch.object(daily.schedule,'sleep'), \
             patch.object(daily.fgoDevice.device,'touch') as touch:
            daily.openDailyPageCN()
        self.assertEqual(touch.call_args_list,[call((109,42)),call((873,394)),call((1004,238))])

    def test_unknown_transition_has_a_three_retry_bound(self):
        with patch.object(daily.XDetect,'region','CN'), \
             patch.object(daily,'Detect',return_value=Frame()), \
             self.runNavigation([EVENT,[],[],[],[]]) as labels, \
             patch.object(daily.schedule,'sleep'), \
             patch.object(daily.fgoDevice.device,'touch') as touch:
            with self.assertRaises(daily.ScriptStop):daily.openDailyPageCN()
        self.assertEqual(labels.call_count,5)
        touch.assert_called_once_with((109,42))

    def test_close_has_three_layer_cap(self):
        with patch.object(daily.XDetect,'region','CN'), \
             patch.object(daily,'Detect',return_value=Frame()), \
             patch.object(daily,'_navigationLabels',return_value=EVENT), \
             patch.object(daily.schedule,'sleep'), \
             patch.object(daily.fgoDevice.device,'touch') as touch:
            with self.assertRaises(daily.ScriptStop):daily.openDailyPageCN()
        self.assertEqual(touch.call_count,3)

    def test_offscreen_gate_scroll_is_bounded_and_never_taps(self):
        with patch.object(daily.XDetect,'region','CN'), \
             patch.object(daily,'Detect',return_value=Frame()), \
             patch.object(daily,'_navigationLabels',return_value=[NOTIFY]), \
             patch.object(daily,'_swipe',return_value=(Frame(),True)) as swipe, \
             patch.object(daily.fgoDevice.device,'touch') as touch:
            with self.assertRaises(daily.ScriptStop):daily.openDailyPageCN()
        self.assertEqual(swipe.call_count,daily.DAILY_NAV_SCROLL_LIMIT)
        touch.assert_not_called()

    def test_duplicate_title_at_top_stops_without_picking_one(self):
        labels=HOME+[('迦勒底之门',(750,170,990,220))]
        with patch.object(daily.XDetect,'region','CN'), \
             patch.object(daily,'Detect',return_value=Frame()), \
             patch.object(daily,'_navigationLabels',return_value=labels), \
             patch.object(daily,'_swipe',return_value=(Frame(),False)), \
             patch.object(daily.fgoDevice.device,'touch') as touch:
            with self.assertRaises(daily.ScriptStop):daily.openDailyPageCN()
        touch.assert_not_called()


if __name__=='__main__':unittest.main()

"""Terminal/Gate entries below pinned quest cards; no private image fixtures."""
import runpy, unittest
from pathlib import Path
from unittest.mock import patch, call

env=runpy.run_path(str(Path(__file__).with_name('test_daily_navigation.py')))
daily=env['daily'];Frame=env['Frame'];HOME=env['HOME'];GATE=env['GATE'];DAILY=env['DAILY']
ROOT_MISSING=[env['NOTIFY']]
GATE_MISSING=[env['CLOSE'],env['GATE_HEADER'],('魔术礼装任务',(779,140,1025,161))]

class EntrySearchTests(unittest.TestCase):
    def runSearch(self,labels,movement,thumbs):
        frame=Frame()
        with patch.object(daily.XDetect,'region','CN'),patch.object(daily,'Detect',return_value=frame),\
             env['DailyNavigationTests']().runNavigation(labels),patch.object(daily.schedule,'sleep'),\
             patch.object(daily,'_scrollbar',side_effect=thumbs),\
             patch.object(daily,'_swipe',side_effect=[(frame,x) for x in movement]) as swipe,\
             patch.object(daily.fgoDevice.device,'touch') as touch:
            error=None
            try:result=daily._openDailyFromTerminalCN()
            except daily.ScriptStop as e:error=e;result=None
        return result,error,swipe.call_args_list,touch.call_args_list,frame

    def test_root_top_without_gate_searches_down_and_opens_only_entries(self):
        result,error,swipes,touches,f=self.runSearch([ROOT_MISSING,ROOT_MISSING,HOME,GATE,DAILY],[False,True],[(99,330)]*2)
        self.assertIsNone(error);self.assertEqual(result,{'type':'DailyPage'})
        self.assertEqual(swipes,[call(f,True),call(f,False)])
        self.assertEqual(touches,[call((873,394)),call((1004,238))])

    def test_gate_top_pinned_costume_quests_do_not_hide_daily_below(self):
        result,error,swipes,touches,f=self.runSearch([GATE_MISSING,GATE_MISSING,GATE,DAILY],[False,True],[(99,330)]*2)
        self.assertIsNone(error);self.assertEqual(result,{'type':'DailyPage'})
        self.assertEqual(swipes,[call(f,True),call(f,False)])
        self.assertEqual(touches,[call((1004,238))])

    def test_stationary_mid_list_is_not_declared_top_and_not_retried(self):
        result,error,swipes,touches,f=self.runSearch([GATE_MISSING],[False],[(250,400)]*2)
        self.assertIsNotNone(error);self.assertEqual(len(swipes),1);self.assertEqual(touches,[])

    def test_absent_entry_at_verified_bottom_stops(self):
        result,error,swipes,touches,f=self.runSearch([GATE_MISSING,GATE_MISSING],[False,False],[(99,330)]*2+[(340,583)]*2)
        self.assertIsNotNone(error);self.assertIn('底部',str(error))
        self.assertEqual(swipes,[call(f,True),call(f,False)]);self.assertEqual(touches,[])

    def test_scrollbar_failure_cannot_authorize_downward_search(self):
        result,error,swipes,touches,f=self.runSearch([GATE_MISSING],[False],[daily.ScriptStop('no scrollbar')])
        self.assertIsNotNone(error);self.assertEqual(len(swipes),1);self.assertEqual(touches,[])

    def test_reverse_direction_search_remains_bounded(self):
        n=daily.DAILY_NAV_SCROLL_LIMIT
        result,error,swipes,touches,f=self.runSearch([GATE_MISSING]*(n+1),[False]+[True]*(n-1),[(99,330)]*2)
        self.assertIsNotNone(error);self.assertEqual(len(swipes),n)
        self.assertEqual(swipes[0],call(f,True));self.assertTrue(all(c==call(f,False) for c in swipes[1:]));self.assertEqual(touches,[])

    def test_popup_after_reversal_does_not_receive_touch_or_another_swipe(self):
        blocked=GATE_MISSING+[('是否开始关卡？',(400,300,850,370))]
        result,error,swipes,touches,f=self.runSearch([GATE_MISSING,blocked],[False],[(99,330)]*2)
        self.assertIsNotNone(error);self.assertEqual(len(swipes),1);self.assertEqual(touches,[])

    def test_duplicate_daily_entry_stops_before_scroll_or_touch(self):
        rows=GATE+[('每日任务',(921,400,1088,450))]
        result,error,swipes,touches,f=self.runSearch([rows],[],[])
        self.assertIsNotNone(error);self.assertEqual(swipes,[]);self.assertEqual(touches,[])

if __name__=='__main__':unittest.main()

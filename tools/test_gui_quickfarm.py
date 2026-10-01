import os,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'FGO-py'))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import fgoQuickFarm

class FakeSchedule:
    def __init__(self):self.calls=[]
    def stopLater(self,*args):self.calls.append(args)

class QuickFarmTests(unittest.TestCase):
    def test_mode_defaults_and_mapping(self):
        self.assertEqual(fgoQuickFarm.modeName(fgoQuickFarm.modeIndex('current')),'current')
        self.assertEqual(fgoQuickFarm.modeName(99),'current')
    def test_battle_limit_one(self):
        schedule=FakeSchedule();fgoQuickFarm.applyBattleLimit(schedule,1)
        self.assertEqual(schedule.calls,[(1,)])
    def test_zero_limit_clears_without_zero_countdown(self):
        schedule=FakeSchedule();fgoQuickFarm.applyBattleLimit(schedule,0)
        self.assertEqual(schedule.calls,[()])
    def test_weekly_feedback_empty(self):
        self.assertIn('未能正确识别',fgoQuickFarm.weeklyMissionFeedback({'quests':[],'recognized':0}))
        self.assertIn('暂不受',fgoQuickFarm.weeklyMissionFeedback({'quests':[],'recognized':2,'completed':0,'supported':0,'unsupported':2}))
        self.assertIn('没有需要处理',fgoQuickFarm.weeklyMissionFeedback({'quests':[],'recognized':2,'completed':2,'supported':0,'unsupported':0}))
    def test_weekly_quests_extend_operation(self):
        operation=[]
        count=fgoQuickFarm.appendWeeklyQuests(operation,{'quests':[((1,2,3,0),2)]})
        self.assertEqual(count,1);self.assertEqual(operation,[((1,2,3,0),2)])
    def test_weekly_report_summary_and_entries(self):
        report={'recognized':7,'completed':4,'supported':2,'unsupported':1,'entries':3,'expectedAp':27,'quests':[]}
        text=fgoQuickFarm.weeklyMissionFeedback(report)
        for expected in ('7 条','已完成：4','可自动求解：2','暂不支持：1','加入 3 项','27'):
            self.assertIn(expected,text)

if __name__=='__main__':unittest.main()

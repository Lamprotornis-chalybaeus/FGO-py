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

if __name__=='__main__':unittest.main()

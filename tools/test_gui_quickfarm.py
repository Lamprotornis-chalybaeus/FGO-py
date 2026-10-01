import os,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'FGO-py'))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import fgoQuickFarm,fgoFriendPolicy

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
    def test_friend_first_policy_selects_first(self):
        self.assertEqual(fgoFriendPolicy.decision('first',False,True,0,2),'first')
    def test_friend_prefer_falls_back_at_refresh_limit(self):
        self.assertEqual(fgoFriendPolicy.decision('prefer',False,True,2,2),'first')
    def test_friend_strict_stops_at_refresh_limit(self):
        self.assertEqual(fgoFriendPolicy.decision('strict',False,True,2,2),'stop')
    def test_strict_can_scan_when_templates_exist(self):
        self.assertTrue(fgoFriendPolicy.canStart('strict',True))
        self.assertFalse(fgoFriendPolicy.canStart('strict',False))
    def test_friend_prefer_refreshes_until_limit(self):
        self.assertEqual(fgoFriendPolicy.decision('prefer',False,True,1,2),'refresh')
        self.assertEqual(fgoFriendPolicy.decision('strict',False,True,1,2),'refresh')
    def test_weekly_report_summary_and_entries(self):
        report={'recognized':7,'completed':4,'supported':2,'unsupported':1,'entries':3,'expectedAp':27,'quests':[]}
        text=fgoQuickFarm.weeklyMissionFeedback(report)
        for expected in ('7 条','已完成：4','可自动求解：2','暂不支持：1','加入 3 项','27'):
            self.assertIn(expected,text)

    def test_daily_navigation_does_not_require_list_end_method(self):
        import importlib,logging,sys,types
        from unittest.mock import patch
        fake=types.ModuleType('fgoLogging')
        fake.getLogger=logging.getLogger
        fake.logMeta=lambda logger:type
        fake.logit=lambda logger,transform=None:lambda func:func
        oldCwd=os.getcwd()
        try:
            os.chdir(ROOT/'FGO-py')
            with patch.dict(sys.modules,{'fgoLogging':fake}):fgoQuickQuest=importlib.import_module('fgoQuickQuest')
        finally:os.chdir(oldCwd)
        positions=iter([None,(700,420)])
        class FakeDetect:
            def isMainInterface(self):return True
            def isQuestListBegin(self):return True
            def findChapter(self,chapter):return next(positions)
        detect=FakeDetect()
        with patch.object(fgoQuickQuest,'Detect',return_value=detect), patch.object(fgoQuickQuest.fgoDevice.device,'touch') as touch, patch.object(fgoQuickQuest.fgoDevice.device,'swipe') as swipe, patch.object(fgoQuickQuest.schedule,'sleep'):
            fgoQuickQuest._open_chapter((0,0))
        touch.assert_called_once_with((700,420))
        swipe.assert_called_once_with((1000,600),(1000,200))
    def test_old_config_gets_safe_defaults(self):
        import json,tempfile,types,logging
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'old-config.json'
            path.write_text(json.dumps({'device':'local'}),encoding='utf-8')
            fake=types.ModuleType('fgoLogging')
            fake.getLogger=logging.getLogger
            sys.modules['fgoLogging']=fake
            from fgoConfig import Config
            config=Config(str(path))
            self.assertEqual(config.quickFarmBattleLimit,1)
            self.assertEqual(config.friendPolicy,'first')
            self.assertEqual(config.friendMaxRefresh,2)
            self.assertEqual(config.eventStoryMode,'pause')
            self.assertFalse(config.eventAutoClaimRewards)
            self.assertEqual(config.eventProgressLimit,1)
    def test_generated_ui_import_and_setup(self):
        from PySide6.QtWidgets import QApplication,QMainWindow
        from fgoMainWindow import Ui_fgoMainWindow
        app=QApplication.instance() or QApplication([])
        class StubWindow(QMainWindow):
            def __getattr__(self,name):return lambda *args,**kwargs:None
        window=StubWindow();ui=Ui_fgoMainWindow();ui.setupUi(window)
        self.assertEqual(ui.CBB_QUICKMODE.count(),3)
        self.assertEqual(ui.TXT_BATTLELIMIT.value(),1)
        self.assertEqual(ui.TXT_FRIENDREFRESH.value(),2)
        self.assertEqual(ui.BTN_MAIN.text(),'开始智能周回')
    def test_uic_output_has_no_generated_drift(self):
        import subprocess,tempfile
        source=ROOT/'FGO-py'/'fgoMainWindow.ui'
        generated=ROOT/'FGO-py'/'fgoMainWindow.py'
        uic=Path(r'C:\FGO-Automation\FGO-py\.venv\Scripts\pyside6-uic.exe')
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'generated.py'
            subprocess.run([str(uic),str(source),'-o',str(output)],check=True,cwd=str(ROOT/'FGO-py'))
            self.assertEqual(generated.read_bytes(),output.read_bytes())

if __name__=='__main__':unittest.main()

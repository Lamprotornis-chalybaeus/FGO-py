"""Offline menu safety, verification evidence, portable paths and compact GUI."""
import unittest,runpy,tempfile,json,os,sys
from pathlib import Path
from unittest.mock import patch,Mock
env=runpy.run_path(str(Path(__file__).with_name('test_ux_polish.py')))
kernel=env['kernel'];APP=env['APP'];np=env['np']
import fgoNavigation as nav,fgoQuickQuest as daily
from fgoPaths import resolvePaths

class TerminalTests(unittest.TestCase):
    def route(self,state):
        frames=[Mock(),Mock()];menu=nav.Label('菜单',(1148,630,1225,674),.99);terminal=nav.Label('终端',(99,620,175,664),.99)
        with patch.object(nav,'Detect',side_effect=frames),patch.object(nav,'labels',return_value=[]),patch.object(nav,'safeMenuPageCN',return_value=state),patch.object(nav,'expandedMenuCN',side_effect=[None,terminal]),patch.object(nav,'terminalHomeCN',return_value=False),patch.object(nav,'unique',side_effect=lambda rows,text,rect:menu if text=='菜单' else None),patch.object(nav.NavigationGuard,'wait',return_value=frames[1]),patch.object(nav,'waitTerminalHomeCN',return_value=frames[1]),patch.object(nav.fgoDevice.device,'touch') as touch:
            nav.normalizeToTerminalCN()
        self.assertEqual([c.args[0] for c in touch.call_args_list],[menu.center,terminal.center])
    def test_normalizes_free_quest(self):self.route('FREE_QUEST')
    def test_normalizes_map(self):self.route('MAP')
    def test_normalizes_event_page(self):self.route('EVENT')
    def test_daily_refresh_runs_normalize_open_scan(self):
        order=[]
        with patch.object(daily.XDetect,'region','CN'),patch.object(daily,'Detect',return_value=object()),patch.object(nav,'labels',return_value=[]),patch.object(nav,'safeMenuPageCN',return_value='GATE'),patch.object(nav,'normalizeToTerminalCN',side_effect=lambda:order.append('terminal')),patch.object(daily,'_openDailyFromTerminalCN',side_effect=lambda:order.append('daily')),patch.object(daily,'scanDailyQuestsCN',side_effect=lambda:order.append('scan') or {'entries':[]}):daily.refreshDailyQuestsCN()
        self.assertEqual(order,['terminal','daily','scan'])
    def reject(self,state):
        with patch.object(nav,'Detect',return_value=Mock()),patch.object(nav,'labels',return_value=[]),patch.object(nav,'safeMenuPageCN',return_value=state),patch.object(nav.fgoDevice.device,'touch') as touch:
            with self.assertRaisesRegex(nav.ScriptStop,state):nav.normalizeToTerminalCN()
        touch.assert_not_called()
    def test_battle_refuses(self):self.reject('UNSAFE_BATTLE_OR_AP')
    def test_modal_refuses(self):self.reject('UNSAFE_MODAL')
    def test_story_or_reward_refuses(self):self.reject('UNSAFE_STORY_OR_REWARD')
    def test_confirmation_template_refuses_before_background_classification(self):
        from types import SimpleNamespace
        with patch.object(nav,'classify') as classify:
            self.assertEqual(nav.safeMenuPageCN(SimpleNamespace(isBattleContinue=lambda:True),[]),'UNSAFE_MODAL');classify.assert_not_called()
    def test_purchase_confirmation_text_refuses(self):
        from types import SimpleNamespace
        items=[nav.Label('是否购买',(450,230,900,270),.99)]
        with patch.object(nav,'classify') as classify:
            self.assertEqual(nav.safeMenuPageCN(SimpleNamespace(),items),'UNSAFE_MODAL');classify.assert_not_called()
    def test_story_skip_text_refuses(self):
        from types import SimpleNamespace
        with patch.object(nav,'classify') as classify:
            self.assertEqual(nav.safeMenuPageCN(SimpleNamespace(),[nav.Label('SKIP',(1000,10,1100,70),.99)]),'UNSAFE_STORY_OR_REWARD');classify.assert_not_called()
    def test_home_needs_directory_in_addition_to_menu(self):
        with patch.object(nav,'classify',return_value='ROOT_CATEGORY'):self.assertFalse(nav.terminalHomeCN(Mock(),[nav.Label('通知',(75,23,143,62),.99)]))
    def test_free_return_uses_independent_local_text_and_ap(self):
        frame=Mock();frame._crop.return_value=np.zeros((40,100,3),np.uint8)
        labels=[nav.Label('关闭',(75,23,143,62),.99)]
        with patch.object(nav.XDetect,'region','CN'),patch.object(nav,'mapChapterConfirmed',return_value=True),patch.object(nav.OCR.ZHS,'ocr_single_line',return_value=('自由关卡',.96)),patch.object(nav.OCR.EN,'ocr_single_line',return_value=('AP4',.96)):self.assertTrue(nav.cnFreeQuestReturn(frame,labels))
    def test_free_return_rejects_daily_event_home_friend_formation(self):
        frame=Mock()
        for items in [[],[nav.Label('关闭',(75,23,143,62),.99),nav.Label('每日任务',(1000,1,1250,80),.99)],[nav.Label('关闭',(75,23,143,62),.99),nav.Label('关卡举办时间',(900,200,1200,230),.99)]]:
            with patch.object(nav.XDetect,'region','CN'):self.assertFalse(nav.cnFreeQuestReturn(frame,items))


class PortableTests(unittest.TestCase):
    def test_frozen_writable_roots_do_not_use_bundle(self):
        p=resolvePaths(True,r'C:\portable\FGO.exe',r'C:\source\fgoPaths.py',r'C:\bundle')
        self.assertEqual(p.configRoot,Path(r'C:\portable\config'));self.assertEqual(p.dataRoot,Path(r'C:\portable'));self.assertEqual(p.logRoot,Path(r'C:\portable\logs'));self.assertEqual(p.resourceRoot,Path(r'C:\bundle'))
    def test_source_paths_do_not_depend_on_working_directory(self):
        p=resolvePaths(False,moduleFile=r'C:\FGO-Automation\FGO-py\FGO-py\fgoPaths.py');self.assertEqual(p.logRoot,Path(r'C:\FGO-Automation\logs'))
    def test_spec_collects_modules_and_uses_onedir(self):
        text=(APP/'fgoBuildCN.spec').read_text(encoding='utf-8');self.assertIn('COLLECT(',text);self.assertIn('console=False',text)
        for name in ('fgoProgress','fgoFriendTemplates','fgoGuiResult','fgoNavigation','fgoEventProgress'):self.assertIn(name,text)
        self.assertNotIn('fgoConfig.json',text)
    def test_pythonw_launcher_does_not_run_cmd(self):
        text=(APP.parents[1]/'start-fgo-py-gui.vbs').read_text(encoding='utf-8');self.assertIn('pythonw.exe',text);self.assertNotIn('cmd.exe',text);self.assertIn('1, False',text)
    def test_build_does_not_bundle_foreign_icu(self):
        text=(APP/'fgoBuildCN.spec').read_text(encoding='utf-8')
        self.assertIn("os.environ['PATH']",text);self.assertIn(".startswith('icu')",text)
    def test_gui_error_handler_keeps_critical_errors_visible(self):
        from fgoGui import GuiLogHandler
        import logging
        lines=[];handler=GuiLogHandler(lines.append)
        handler.emit(logging.LogRecord('fgo',logging.ERROR,__file__,1,'local diagnostic error',(),None))
        self.assertEqual(lines,['[ERROR] local diagnostic error'])

class CompactGuiTests(unittest.TestCase):
    def setUp(self):
        from PySide6.QtWidgets import QApplication
        self.app=QApplication.instance() or QApplication([]);self.old=os.getcwd();os.chdir(APP)
    def tearDown(self):os.chdir(self.old)
    def window(self,config=None):
        from fgoGui import MainWindow
        from fgoConfig import ConfigItem
        from fgoConst import CONFIG
        with patch.object(MainWindow,'initializeDevice'),patch('threading.Thread.start'):return MainWindow(config or ConfigItem(CONFIG))
    def checkSize(self,width,height):
        from PySide6.QtCore import QPoint,QRect
        from PySide6.QtWidgets import QPushButton
        w=self.window();w.resize(width,height);w.show();self.app.processEvents()
        self.assertEqual((w.width(),w.height()),(width,height));self.assertGreaterEqual(w.TXT_LOG.height(),200)
        for button in (w.BTN_MAIN,w.BTN_FRIENDTEMPLATES):self.assertTrue(button.isVisible());self.assertGreater(button.height(),15)
        rects=[QRect(c.mapTo(w,QPoint(0,0)),c.size()) for c in w.findChildren(QPushButton) if c.isVisible()]
        for i,a in enumerate(rects):
            for b in rects[i+1:]:self.assertFalse(a.intersects(b))
        w.close()
    def test_900_620(self):self.checkSize(900,620)
    def test_950_650(self):self.checkSize(950,650)
    def test_1100_720(self):self.checkSize(1100,720)
    def test_event_mode_fits_900_620(self):
        w=self.window();w.CBB_QUICKMODE.setCurrentIndex(2);w.resize(900,620);w.show();self.app.processEvents()
        self.assertEqual(w.height(),620);self.assertGreaterEqual(w.TXT_LOG.height(),200)
        self.assertTrue(w.BTN_MAIN.isVisible());self.assertTrue(w.CBB_EVENT_STORYMODE.isVisible());self.assertLessEqual(w.RUN_CONTROLS.height(),400);w.close()
    def test_geometry_and_splitter_restore(self):
        # Offscreen Qt exposes an 800px-wide virtual screen; restoreGeometry
        # correctly clamps oversized windows to it. Test persistence within it.
        w=self.window();config=w.config;w.resize(740,720);w.show();self.app.processEvents();w.SPLIT_RUN.setSizes([375,260]);before=w.SPLIT_RUN.sizes();w.close()
        other=self.window(config);other.show();self.app.processEvents();self.assertEqual(other.width(),740);self.assertEqual(other.height(),720);self.assertEqual(other.SPLIT_RUN.sizes(),before);other.close()
    def test_failed_scan_keeps_previous_entries(self):
        from PySide6.QtWidgets import QSystemTrayIcon
        w=self.window();entry=daily.DailyQuestEntry('剑之修炼场 极级','training','极级','x',(0,0,0));w.dailyEntries=[entry];w.populateDailyQuests();w.result=None;w._dailyScanPending=True
        w._dailyScanPending=False
        with patch.object(w,'isDeviceAvailable',return_value=True),patch.object(w,'runFunc'):w.refreshDailyQuests()
        w.funcEnd(('Script Stopped: 导航失败',QSystemTrayIcon.MessageIcon.Information));self.assertEqual(w.dailyEntries,[entry]);self.assertEqual(w.CBB_QUEST.count(),1);w.close()
    def test_refresh_disabled_when_any_worker_is_active(self):
        w=self.window();w.funcBegin();self.assertFalse(w.BTN_DAILY_REFRESH.isEnabled())
        with patch.object(w.worker,'is_alive',return_value=True),patch.object(w,'runFunc') as run:w.refreshDailyQuests();run.assert_not_called()
        w.worker=__import__('threading').Thread();w.close()

if __name__=='__main__':unittest.main()

"""Offline regressions for compact CJK layout and saved-size migration."""
import os,runpy,unittest
from pathlib import Path
from unittest.mock import patch

env=runpy.run_path(str(Path(__file__).with_name('test_gui_startup.py')))
gui=env['gui'];ConfigItem=env['ConfigItem'];CONFIG=env['CONFIG'];APP=env['APP']
from PySide6.QtCore import QPoint,QRect
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication,QMainWindow,QPushButton
from fgoGuiResult import RunResultDialog

class CompactWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        # The offscreen plugin has no system font discovery. Use the same CJK
        # font as the real Windows GUI so tofu glyphs cannot hide bad wrapping.
        for name in ('msyh.ttc','msyhbd.ttc'):
            font=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'Fonts'/name
            if font.is_file():QFontDatabase.addApplicationFont(str(font))
    def setUp(self):
        self.old=os.getcwd();os.chdir(APP);self.windows=[]
        self.trayPatch=patch.object(gui.QSystemTrayIcon,'show');self.trayPatch.start()
    def tearDown(self):
        for window in self.windows:window.close();window.deleteLater()
        self.app.processEvents();self.trayPatch.stop();os.chdir(self.old)
    def window(self,config=None):
        with patch.object(gui.MainWindow,'initializeDevice'),patch('threading.Thread.start'):
            window=gui.MainWindow(config or ConfigItem(CONFIG))
        self.windows.append(window);return window
    def assertLayout(self,window):
        self.assertEqual(window.size().toTuple(),(850,580))
        self.assertGreaterEqual(window.TXT_LOG.height(),160)
        bounds=QRect(QPoint(0,0),window.RUN_CONTROLS.size())
        for control in (window.BTN_MAIN,window.BTN_STOP,window.BTN_FRIENDTEMPLATES,window.TXT_APPLE,window.BTN_SCREENSHOT):
            self.assertTrue(control.isVisible())
            self.assertTrue(bounds.contains(QRect(control.mapTo(window.RUN_CONTROLS,QPoint(0,0)),control.size())))
        rectangles=[QRect(b.mapTo(window,QPoint(0,0)),b.size()) for b in window.findChildren(QPushButton) if b.isVisible()]
        for i,rect in enumerate(rectangles):
            for other in rectangles[i+1:]:self.assertFalse(rect.intersects(other))
    def test_constructor_does_not_show_window(self):
        window=self.window();self.assertFalse(window.isVisible());self.assertEqual(window.size().toTuple(),(850,580))
    def test_current_plan_and_event_fit_compact_cjk_layout(self):
        window=self.window()
        for mode in range(3):
            with self.subTest(mode=mode):
                window.CBB_QUICKMODE.setCurrentIndex(mode);window.show();self.app.processEvents();self.assertLayout(window)
                if mode==2:
                    self.assertTrue(window.CBB_EVENT_STORYMODE.isVisible());self.assertTrue(window.CKB_EVENT_REWARD.isVisible())
    def test_larger_windows_keep_at_least_200px_log(self):
        window=self.window();window.show()
        for width,height in ((900,620),(950,650),(1100,720)):
            with self.subTest(size=(width,height)):
                window.resize(width,height);self.app.processEvents();self.assertGreaterEqual(window.TXT_LOG.height(),200)
    def test_old_saved_large_geometry_migrates_once(self):
        old=QMainWindow();old.resize(950,650)
        config=ConfigItem(CONFIG);config.windowGeometry=bytes(old.saveGeometry()).hex();config.guiLayoutVersion=0
        window=self.window(config);window.show();self.app.processEvents();self.assertLayout(window)
        self.assertEqual(config.guiLayoutVersion,gui.MainWindow.GUI_LAYOUT_VERSION)
    def test_user_resize_and_splitter_persist_after_migration(self):
        # Offscreen Qt's virtual screen is 800px wide, so use an in-bounds width
        # when checking Qt's restoreGeometry instead of its screen clamp.
        window=self.window();window.resize(740,700);window.show();self.app.processEvents()
        window.SPLIT_RUN.setSizes([360,250]);before=window.SPLIT_RUN.sizes();config=window.config;window.close()
        restored=self.window(config);restored.show();self.app.processEvents()
        self.assertEqual(restored.size().toTuple(),(740,700));self.assertEqual(restored.SPLIT_RUN.sizes(),before)
    def test_compact_menu_action_resets_only_geometry(self):
        window=self.window();window.show();window.resize(1100,720);window.TXT_APPLE.setValue(0);window.TXT_BATTLELIMIT.setValue(3)
        window.compactWindowAction.trigger();self.app.processEvents();self.assertLayout(window)
        self.assertEqual(window.TXT_APPLE.value(),0);self.assertEqual(window.TXT_BATTLELIMIT.value(),3)
    def test_zero_battle_result_does_not_show_large_empty_table(self):
        dialog=RunResultDialog(dict(battle=0,time=18,material={},dropStats={}),
            'Script Stopped: Navigation failed [RETURN ROOT] 冬木 → 未确认坐标X-A: cannot safely return from UNKNOWN; no blind clicks')
        self.windows.append(dialog);dialog.show();self.app.processEvents()
        self.assertFalse(hasattr(dialog,'table'));self.assertLessEqual(dialog.width(),520);self.assertLessEqual(dialog.height(),300)
        self.assertIn('已进行 0 场',dialog.summaryLabel.text());self.assertTrue(dialog.summaryLabel.wordWrap())

if __name__=='__main__':unittest.main()

"""Offline Qt regressions for visible startup and explicit device selection."""
import logging
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'FGO-py'
sys.path.insert(0,str(APP))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
if 'fgoLogging' not in sys.modules:
    fake=types.ModuleType('fgoLogging')
    fake.getLogger=logging.getLogger
    fake.logMeta=lambda logger:type
    fake.logit=lambda logger,transform=None:lambda func:func
    sys.modules['fgoLogging']=fake
oldCwd=os.getcwd()
os.chdir(APP)
try:
    import fgoGui as gui
    from fgoConfig import ConfigItem
    from fgoConst import CONFIG
finally:os.chdir(oldCwd)

from PySide6.QtCore import Qt,QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialogButtonBox,QInputDialog


class GuiStartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.windows=[]
        self.trayPatch=patch.object(gui.QSystemTrayIcon,'show')
        self.trayPatch.start()
        self.logPatch=patch.object(gui.logger,'exception')
        self.logPatch.start()

    def tearDown(self):
        for window in self.windows:
            window.close()
            window.deleteLater()
        self.app.processEvents()
        self.logPatch.stop()
        self.trayPatch.stop()

    def window(self,saved='/bs5_Rvc64'):
        config=ConfigItem(CONFIG)
        config.device=saved
        window=gui.MainWindow(config)
        self.windows.append(window)
        return window

    def test_constructor_never_opens_selector_or_connects(self):
        with patch.object(gui.MainWindow,'connectDevice') as selector, \
             patch.object(gui.MainWindow,'refreshDailyQuests') as scanner, \
             patch.object(gui.fgoDevice,'Device') as factory, \
             patch.object(gui.QInputDialog,'exec',side_effect=AssertionError('startup modal')):
            window=self.window()
            self.app.processEvents()
        selector.assert_not_called()
        scanner.assert_not_called()
        factory.assert_not_called()
        self.assertEqual(window.LBL_DEVICE.text(),'未连接')

    def test_saved_device_auto_connects_without_selector(self):
        window=self.window();window.show();self.app.processEvents()
        candidate=types.SimpleNamespace(available=True,name='127.0.0.1:5555')
        with patch.object(gui.fgoDevice,'device'), \
             patch.object(gui.fgoDevice,'Device',return_value=candidate) as factory, \
             patch.object(gui.QInputDialog,'exec',side_effect=AssertionError('startup modal')), \
             patch.object(gui.logger,'info') as log:
            self.assertTrue(window.initializeDevice())
            self.assertIs(gui.fgoDevice.device,candidate)
        factory.assert_called_once_with('/bs5_Rvc64')
        log.assert_called_once_with('Auto connected to saved device: %s','/bs5_Rvc64')
        self.assertEqual(window.LBL_DEVICE.text(),'127.0.0.1:5555')
        self.assertTrue(window.isVisible())

    def test_failed_auto_connect_keeps_visible_usable_window(self):
        window=self.window();window.show();self.app.processEvents()
        previous=Mock()
        with patch.object(gui.fgoDevice,'device',previous), \
             patch.object(gui.fgoDevice,'Device',side_effect=RuntimeError('offline')), \
             patch.object(gui.fgoDevice,'setup') as restore, \
             patch.object(gui.QInputDialog,'exec',side_effect=AssertionError('startup modal')):
            self.assertFalse(window.initializeDevice())
            self.assertIs(gui.fgoDevice.device,previous)
        restore.assert_called_once_with(previous)
        self.assertTrue(window.isVisible())
        self.assertTrue(window.BTN_CONNECT.isEnabled())
        self.assertEqual(window.LBL_DEVICE.text(),'未连接')
        self.assertIn('自动连接设备失败',window.statusBar().currentMessage())
        self.assertEqual(window.config.device,'/bs5_Rvc64')

    def test_unavailable_candidate_is_not_installed(self):
        window=self.window();previous=Mock()
        candidate=types.SimpleNamespace(available=False,name=None)
        with patch.object(gui.fgoDevice,'device',previous), \
             patch.object(gui.fgoDevice,'Device',return_value=candidate), \
             patch.object(gui.fgoDevice,'setup') as restore:
            self.assertFalse(window.initializeDevice())
            self.assertIs(gui.fgoDevice.device,previous)
        restore.assert_called_once_with(previous)

    def test_no_saved_device_shows_without_any_modal(self):
        with patch.object(gui.fgoDevice,'Device') as factory, \
             patch.object(gui.QInputDialog,'exec',side_effect=AssertionError('startup modal')):
            window=self.window('');window.show();self.app.processEvents()
            self.assertFalse(window.initializeDevice())
        factory.assert_not_called()
        self.assertTrue(window.isVisible())
        self.assertEqual(window.LBL_DEVICE.text(),'未连接')
        self.assertIn('更改',window.statusBar().currentMessage())
        self.assertEqual(window.windowType(),Qt.WindowType.Window)

    def test_cancel_keeps_window_and_existing_connection(self):
        window=self.window();window.show();self.app.processEvents()
        previous=Mock(available=True,name='existing')
        window.LBL_DEVICE.setText('existing')
        with patch.object(gui.fgoDevice,'device',previous), \
             patch.object(gui.fgoDevice.Device,'enumDevices',return_value=[]), \
             patch.object(gui.QInputDialog,'exec',return_value=0), \
             patch.object(gui.fgoDevice,'Device') as factory:
            self.assertFalse(window.connectDevice())
            self.assertIs(gui.fgoDevice.device,previous)
        factory.assert_not_called()
        self.assertTrue(window.isVisible())
        self.assertEqual(window.LBL_DEVICE.text(),'existing')
        self.assertEqual(window.config.device,'/bs5_Rvc64')

    def test_cancel_without_connection_keeps_unconnected_window(self):
        window=self.window('');window.show();self.app.processEvents()
        with patch.object(gui.fgoDevice.Device,'enumDevices',return_value=[]), \
             patch.object(gui.QInputDialog,'exec',return_value=0):
            self.assertFalse(window.connectDevice())
        self.assertTrue(window.isVisible())
        self.assertEqual(window.LBL_DEVICE.text(),'未连接')

    def test_real_dialog_has_parent_dialog_flags_tab_and_mouse_cancel(self):
        window=self.window();window.show();self.app.processEvents()
        seen={}
        def inspect():
            dialog=QApplication.activeModalWidget()
            seen['isInput']=isinstance(dialog,QInputDialog)
            seen['parent']=dialog.parent() is window
            seen['type']=dialog.windowType()
            seen['modality']=dialog.windowModality()
            seen['saved']=dialog.textValue()
            edit=dialog.findChild(gui.QComboBox).lineEdit()
            edit.setFocus();self.app.processEvents();before=dialog.focusWidget()
            QTest.keyClick(edit,Qt.Key.Key_Tab)
            seen['tabMoved']=dialog.focusWidget() is not before
            buttons=dialog.findChild(QDialogButtonBox)
            QTest.mouseClick(buttons.button(QDialogButtonBox.StandardButton.Cancel),Qt.MouseButton.LeftButton)
        QTimer.singleShot(0,inspect)
        with patch.object(gui.fgoDevice.Device,'enumDevices',return_value=['127.0.0.1:5555']):
            self.assertFalse(window.connectDevice())
        self.assertTrue(seen['isInput'])
        self.assertTrue(seen['parent'])
        self.assertEqual(seen['type'],Qt.WindowType.Dialog)
        self.assertEqual(seen['modality'],Qt.WindowModality.WindowModal)
        self.assertEqual(seen['saved'],'/bs5_Rvc64')
        self.assertTrue(seen['tabMoved'])
        self.assertTrue(window.isVisible())

    def test_real_dialog_escape_cancels_without_reconnecting(self):
        window=self.window();window.show();self.app.processEvents()
        QTimer.singleShot(0,lambda:QTest.keyClick(QApplication.activeModalWidget(),Qt.Key.Key_Escape))
        with patch.object(gui.fgoDevice.Device,'enumDevices',return_value=[]), \
             patch.object(gui.fgoDevice,'Device') as factory:
            self.assertFalse(window.connectDevice())
        factory.assert_not_called()
        self.assertTrue(window.isVisible())

    def test_real_dialog_enter_accepts_and_saves_successful_selection(self):
        window=self.window();window.show();self.app.processEvents()
        candidate=types.SimpleNamespace(available=True,name='127.0.0.1:5555')
        def accept():
            dialog=QApplication.activeModalWidget()
            dialog.setTextValue('127.0.0.1:5555')
            button=dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
            button.setFocus()
            QTest.keyClick(button,Qt.Key.Key_Return)
        QTimer.singleShot(0,accept)
        with patch.object(gui.fgoDevice.Device,'enumDevices',return_value=[]), \
             patch.object(gui.fgoDevice,'Device',return_value=candidate), \
             patch.object(gui.fgoDevice,'device'):
            self.assertTrue(window.connectDevice())
        self.assertEqual(window.config.device,'127.0.0.1:5555')
        self.assertEqual(window.LBL_DEVICE.text(),'127.0.0.1:5555')

    def test_main_shows_before_scheduling_connection_and_entering_event_loop(self):
        sequence=[];pending=[]
        window=Mock()
        window.show.side_effect=lambda:sequence.append('show')
        window.initializeDevice.side_effect=lambda:sequence.append('connect')
        app=Mock()
        def eventLoop():
            sequence.append('event-loop')
            pending[0]()
            return 0
        app.exec.side_effect=eventLoop
        def construct(config):sequence.append('construct');return window
        def schedule(delay,callback):
            self.assertEqual(delay,0)
            sequence.append('schedule')
            pending.append(callback)
        with patch.object(gui,'QApplication',return_value=app), \
             patch.object(gui,'QTranslator'), \
             patch.object(gui,'MainWindow',side_effect=construct), \
             patch.object(gui.QTimer,'singleShot',side_effect=schedule), \
             patch.object(gui.sys,'exit') as exit:
            gui.main(Mock())
        self.assertEqual(sequence,['construct','show','schedule','event-loop','connect'])
        exit.assert_called_once_with(0)

    def test_launcher_has_exactly_one_gui_invocation_and_no_start_wait(self):
        script=(ROOT.parent/'start-fgo-py.cmd').read_text(encoding='utf-8').lower()
        lines=[line.strip() for line in script.splitlines() if line.strip()]
        guiCalls=[line for line in lines if 'fgo.py' in line and 'gui' in line]
        self.assertEqual(len(guiCalls),1)
        self.assertEqual(guiCalls[0],'python "%root%fgo-py\\fgo-py\\fgo.py" gui')
        self.assertNotIn('start /wait',script)
        self.assertLess(script.index('check-adb.cmd'),script.index('fgo.py'))


if __name__=='__main__':unittest.main()

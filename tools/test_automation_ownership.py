import os,sys,unittest,threading,inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
APP=Path(__file__).resolve().parents[1]/'FGO-py';sys.path.insert(0,str(APP));os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
cwd=os.getcwd();os.chdir(APP)
try:import fgoKernel as kernel,fgoGui as gui
finally:os.chdir(cwd)
from fgoAutomation import AutomationOwner,NETWORK_ERROR_EVENT
from fgoConfig import ConfigItem
from fgoConst import CONFIG
from PySide6.QtWidgets import QApplication,QMessageBox

class OwnershipTests(unittest.TestCase):
    def test_owner_reentrant_but_excludes_another_thread(self):
        owner=AutomationOwner();errors=[]
        def other():
            try:
                with owner.claim():self.fail('Second owner acquired active device')
            except kernel.ScriptStop as e:errors.append(e)
        with owner.claim(),owner.claim():
            self.assertTrue(owner.isOwner());t=threading.Thread(target=other);t.start();t.join(2)
        self.assertFalse(owner.isOwner());self.assertEqual(len(errors),1)
    def test_guardian_detects_without_device_inputs(self):
        stop=Mock();stop.wait.side_effect=[False,True]
        cache=SimpleNamespace(isNetworkError=lambda:True)
        NETWORK_ERROR_EVENT.clear()
        with patch.object(kernel.XDetect,'cache',cache),patch.object(kernel.fgoDevice.device,'press') as press,patch.object(kernel.fgoDevice.device,'touch') as touch,patch.object(kernel.fgoDevice.device,'perform') as perform:
            kernel.guardian(stop)
        self.assertTrue(NETWORK_ERROR_EVENT.is_set());NETWORK_ERROR_EVENT.clear()
        press.assert_not_called();touch.assert_not_called();perform.assert_not_called()
        self.assertNotIn('device.press',inspect.getsource(kernel.guardian))
    def test_false_network_event_does_not_authorize_input(self):
        with patch.object(kernel.fgoDevice.device,'press') as press:
            self.assertFalse(kernel.handleNetworkError(SimpleNamespace(isNetworkError=lambda:False)))
        press.assert_not_called()

class GuiWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        with patch.object(gui.MainWindow,'initializeDevice'),patch('threading.Thread.start'):
            self.window=gui.MainWindow(ConfigItem(CONFIG))
    def tearDown(self):
        self.window._runActive=False
        self.window.worker=Mock(is_alive=Mock(return_value=False))
        self.window.close();self.window.deleteLater();self.app.processEvents()
    def test_rapid_duplicate_run_creates_only_one_worker(self):
        thread=Mock();thread.is_alive.return_value=False
        with patch.object(self.window,'isDeviceAvailable',return_value=True),patch.object(gui,'Thread',return_value=thread) as factory:
            self.window.runFunc(lambda:None);self.window.runFunc(lambda:None)
        factory.assert_called_once();thread.start.assert_called_once();self.assertTrue(self.window._runActive)
    def test_thread_start_failure_clears_active(self):
        thread=Mock();thread.is_alive.return_value=False;thread.start.side_effect=RuntimeError('start failed')
        with patch.object(self.window,'isDeviceAvailable',return_value=True),patch.object(gui,'Thread',return_value=thread),patch.object(gui.logger,'exception'):
            self.window.runFunc(lambda:None)
        self.assertFalse(self.window._runActive)
    def test_thread_constructor_failure_clears_active(self):
        with patch.object(self.window,'isDeviceAvailable',return_value=True),patch.object(gui,'Thread',side_effect=RuntimeError('construction failed')),patch.object(gui.logger,'exception'):
            self.window.runFunc(lambda:None)
        self.assertFalse(self.window._runActive)
    def test_quit_uses_timeout_and_refuses_if_worker_alive(self):
        self.window.worker=Mock(is_alive=Mock(return_value=True))
        with patch.object(gui.QMessageBox,'warning',return_value=QMessageBox.StandardButton.Yes),patch.object(gui.QMessageBox,'information') as notice,patch.object(kernel.schedule,'stop') as stop:
            self.assertFalse(self.window.askQuit())
        self.window.worker.join.assert_called_once_with(timeout=5);stop.assert_called_once_with('Quit');notice.assert_called_once()
    def test_worker_retains_owner_through_scheduler_cleanup(self):
        self.window.config['notifyEnable']=False
        thread=Mock();thread.is_alive.return_value=False
        with patch.object(self.window,'isDeviceAvailable',return_value=True),patch.object(gui,'Thread',return_value=thread) as factory:
            self.window.runFunc(lambda:None)
        with patch.object(kernel.schedule,'reset',side_effect=lambda:self.assertTrue(kernel.automationOwner.isOwner())):
            factory.call_args.kwargs['target']()
        self.assertFalse(kernel.automationOwner.isOwner())
    def test_unprepared_main_exposes_zero_statistics(self):
        result=kernel.Main().result
        self.assertEqual([result[k] for k in ('startedBattles','completedAttempts','wins','defeats')],[0]*4)
    def test_completion_clears_active_flag(self):
        self.window.result=None
        self.window._runActive=True;self.window.funcEnd(('Done',gui.QSystemTrayIcon.MessageIcon.Information))
        self.assertFalse(self.window._runActive)

if __name__=='__main__':unittest.main()

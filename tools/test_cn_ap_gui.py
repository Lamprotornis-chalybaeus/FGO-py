"""Old resource configuration is retained and blocked, never remapped to gold."""
import unittest
from unittest.mock import patch
import test_gui_startup as startup
from fgoConst import CONFIG
from fgoConfig import ConfigItem
import fgoApRecovery as ap

class RecoveryGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):startup.GuiStartupTests.setUpClass.__func__(cls)
    setUp=startup.GuiStartupTests.setUp
    tearDown=startup.GuiStartupTests.tearDown
    def window(self,kind):
        config=ConfigItem(CONFIG);config.update({'appleKind':kind})
        with patch.object(startup.gui.MainWindow,'refreshDailyQuests'):
            window=startup.gui.MainWindow(config)
        self.windows.append(window);return window
    def test_old_kind_four_remains_selected_and_stops_without_worker(self):
        with patch.object(startup.gui.fgoKernel.XDetect,'region','CN'),patch.object(startup.gui.QMessageBox,'critical') as critical:
            window=self.window(4)
            self.assertEqual(window.config['appleKind'],4);self.assertEqual(window.CBB_APPLE.currentIndex(),4)
            self.assertEqual(window.operation.appleKind,4);self.assertFalse(window.CBB_APPLE.model().item(4).isEnabled())
            with patch.object(window,'runFunc') as run:
                window.runMain();run.assert_not_called()
            self.assertIn(ap.FORBIDDEN,critical.call_args.args[2]);self.assertEqual(window.config['appleKind'],4)
    def test_explicit_legal_selection_clears_invalid_choice(self):
        with patch.object(startup.gui.fgoKernel.XDetect,'region','CN'):
            window=self.window(4);window.CBB_APPLE.setCurrentIndex(1)
            self.assertTrue(window.validateRecoveryResource());self.assertEqual(window.operation.appleKind,1)
            self.assertEqual(window.config['appleKind'],1)
    def test_non_cn_retains_fifth_item(self):
        with patch.object(startup.gui.fgoKernel.XDetect,'region','JP'):
            window=self.window(4);self.assertTrue(window.CBB_APPLE.model().item(4).isEnabled())
            self.assertTrue(window.validateRecoveryResource())
if __name__=='__main__':unittest.main()

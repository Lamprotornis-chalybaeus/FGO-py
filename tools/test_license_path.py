"""Offline source/portable license lookup and shell-free viewer invocation."""
import os,runpy,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch

env=runpy.run_path(str(Path(__file__).with_name('test_gui_startup.py')))
gui=env['gui']
import fgoPaths

class LicensePathTests(unittest.TestCase):
    def setUp(self):
        self.previous=os.getcwd();self.temp=tempfile.TemporaryDirectory(prefix='FGO license spaces ')
        self.root=Path(self.temp.name)
        self.cwd=[self.root/'Unrelated cwd one',self.root/'Unrelated cwd two']
        for folder in self.cwd:folder.mkdir()
    def tearDown(self):os.chdir(self.previous);self.temp.cleanup()
    def test_source_license_is_in_repo_parent_from_any_cwd(self):
        app=self.root/'Source repo with spaces'/'FGO-py'
        paths=fgoPaths.resolvePaths(False,moduleFile=str(app/'fgoPaths.py'))
        with patch.object(fgoPaths,'paths',paths),patch.object(fgoPaths.sys,'frozen',False,create=True):
            for folder in self.cwd:
                with self.subTest(cwd=str(folder)):
                    os.chdir(folder);target=fgoPaths.licenseFile()
                    self.assertTrue(target.is_absolute());self.assertEqual(target,app.parent/'LICENSE')
    def test_frozen_license_uses_resource_root_not_launch_cwd(self):
        app=self.root/'Portable app with spaces';resources=self.root/'Bundle resource with spaces'
        paths=fgoPaths.resolvePaths(True,executable=str(app/'FGO-py-CN.exe'),bundle=str(resources))
        with patch.object(fgoPaths,'paths',paths),patch.object(fgoPaths.sys,'frozen',True,create=True):
            for folder in self.cwd:
                with self.subTest(cwd=str(folder)):
                    os.chdir(folder);target=fgoPaths.licenseFile()
                    self.assertTrue(target.is_absolute());self.assertEqual(target,resources/'LICENSE')
                    self.assertNotEqual(target,app.parent/'LICENSE')
    def test_real_source_license_exists(self):
        self.assertTrue(fgoPaths.licenseFile(False).is_file())
    def test_viewer_uses_literal_argv_without_shell(self):
        paths=fgoPaths.resolvePaths(True,executable=str(self.root/'Portable app & data'/'FGO-py-CN.exe'),bundle=str(self.root/'Portable app & data'))
        with patch.object(fgoPaths,'paths',paths),patch.object(fgoPaths.sys,'frozen',True,create=True),patch.object(gui.subprocess,'Popen') as viewer,patch.object(gui.os,'system') as shell:
            os.chdir(self.cwd[1]);gui.MainWindow.license(Mock())
        viewer.assert_called_once_with(['notepad.exe',str(paths.resourceRoot/'LICENSE')],shell=False)
        self.assertEqual(len(viewer.call_args.args[0]),2);shell.assert_not_called()

if __name__=='__main__':unittest.main()

"""Strict map revalidation despite transient full-screen OCR omissions."""
import os,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
APP=Path(__file__).resolve().parents[1]/'FGO-py';sys.path.insert(0,str(APP))
old=os.getcwd();os.chdir(APP)
try:import fgoKernel as kernel
finally:os.chdir(old)

class MapSettleTests(unittest.TestCase):
    def test_map_confirmation_uses_fresh_local_read_after_full_ocr_miss(self):
        import fgoNavigation as nav
        frame=SimpleNamespace();guard=nav.NavigationGuard('map');point=(640,350)
        with patch.object(nav,'_read',return_value=(frame,[],'MAP')),patch.object(nav,'mapChapterConfirmed',return_value=True),patch.object(nav,'visibleMapNode',side_effect=[point,None,point]),patch.object(nav,'Detect',return_value=frame),patch.object(nav,'labels',return_value=[]),patch.object(nav.schedule,'sleep'),patch.object(guard,'wait'),patch.object(nav.fgoDevice.device,'touch') as touch:
            nav.locateMapCN((1,0,2,0),guard);touch.assert_called_once_with(point)
    def test_map_missing_marker_remains_bounded_and_never_taps(self):
        import fgoNavigation as nav
        frame=SimpleNamespace();guard=nav.NavigationGuard('map')
        with patch.object(nav,'_read',return_value=(frame,[],'MAP')),patch.object(nav,'mapChapterConfirmed',return_value=True),patch.object(nav,'visibleMapNode',side_effect=[(640,350)]+[None]*6),patch.object(nav,'Detect',return_value=frame),patch.object(nav,'labels',return_value=[]),patch.object(nav.fgoDevice.device,'touch') as touch:
            with self.assertRaisesRegex(kernel.ScriptStop,'marker is missing'):nav.locateMapCN((1,0,2,0),guard)
            touch.assert_not_called()

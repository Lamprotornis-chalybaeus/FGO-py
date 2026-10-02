import unittest
from unittest.mock import patch
import runpy
from pathlib import Path
env=runpy.run_path(str(Path(__file__).with_name('test_ux_polish.py')))
kernel=env['kernel']

class FarmingIdleTests(unittest.TestCase):
    def exercise(self,delay,available=True):
        task=kernel.Farming();sleeps=[]
        def sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps)==2:task.stop=True
        with patch.object(kernel.time,'sleep',side_effect=sleep),patch.object(kernel.fgoDevice.device.__class__,'available',new=property(lambda _:available)),patch.object(task,'run',return_value=delay) as callback:task()
        return sleeps,callback.call_count
    def test_none_callback_remains_idle(self):self.assertEqual(self.exercise(None),([100,30],1))
    def test_numeric_delay_retains_contract(self):self.assertEqual(self.exercise(12),([100,42],1))
    def test_disconnected_does_not_busy_spin(self):self.assertEqual(self.exercise(None,False),([100,30],0))

if __name__=='__main__':unittest.main()

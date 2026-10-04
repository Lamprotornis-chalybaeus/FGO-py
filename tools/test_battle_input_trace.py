"""Physical input journal and whole-battle deadline at the input boundary."""
import os,sys,unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'FGO-py'))
from fgoAutomation import INPUT_OBSERVER
from fgoDevice import Device
from fgoBattleFlow import BattleFlow,BattleFlowState as S,FlowTimeout
from fgoFlowTrace import FlowTrace
from test_battle_flow import Clock,frame
class InputTraceTests(unittest.TestCase):
    def make(self):
        clock=Clock();flow=BattleFlow(lambda:frame('TURN_BEGIN'),clock,clock=clock,trace=FlowTrace(clock=clock));flow.observe()
        device=Device.__new__(Device);device.I=Mock();device.O=device.I
        return clock,flow,device
    def test_turn_input_names_are_recorded_and_forwarded_once(self):
        clock,flow,device=self.make();token=INPUT_OBSERVER.set(flow.deviceInput)
        try:device.press('A');device.touch((400,500));device.swipe((400,600),(400,200))
        finally:INPUT_OBSERVER.reset(token)
        self.assertEqual([r.action for r in flow.trace.records if r.action],["press 'A'",'touch (400, 500)','swipe ((400, 600), (400, 200))'])
        device.I.press.assert_called_once_with('A');device.I.touch.assert_called_once_with((400,500))
        device.I.swipe.assert_called_once_with((400,600),(400,200))
        self.assertEqual(flow.trace.last_physical_input,'swipe ((400, 600), (400, 200))')
    def test_total_deadline_refuses_next_physical_input(self):
        clock,flow,device=self.make();flow.deadline=1;clock.now=1
        token=INPUT_OBSERVER.set(flow.deviceInput)
        try:
            with self.assertRaises(FlowTimeout):device.press('A')
        finally:INPUT_OBSERVER.reset(token)
        device.I.press.assert_not_called()
    def test_no_observer_preserves_existing_device_api(self):
        clock,flow,device=self.make();device.press('8')
        device.I.press.assert_called_once_with('8');self.assertEqual(len(flow.trace.records),1)
    def test_explicit_duration_is_traced_and_forwarded_once(self):
        clock,flow,device=self.make();token=INPUT_OBSERVER.set(flow.deviceInput)
        try:device.press(' ',duration=.08);device.touch((650,300),duration=.08)
        finally:INPUT_OBSERVER.reset(token)
        device.I.press.assert_called_once_with(' ',duration=.08)
        device.I.touch.assert_called_once_with((650,300),duration=.08)
        self.assertEqual(flow.trace.last_physical_input,'touch (650, 300) duration=0.08')
if __name__=='__main__':unittest.main()

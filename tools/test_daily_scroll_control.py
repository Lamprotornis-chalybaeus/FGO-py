"""Regression tests for observed-position daily scrollbar control."""
import time
import unittest
from unittest.mock import patch,PropertyMock

from daily_index_test_support import World,q,indexed
from fgoDailyIndex import DailyScrollResult,DailyScanMetrics


class AdvanceScanTests(unittest.TestCase):
    def run_advance(self,offset):
        w=World();acc=w.calibrated();target=139.
        def quantized_drag(start,end):
            w.drags.append((start,end))
            requested=w.top+(end[1]-start[1])
            w.top=max(99.,min(535.,requested+offset))
        w.drag=quantized_drag
        with w.patched() as world:
            d=world.capture();entries=world.entries(d);metrics=DailyScanMetrics()
            with indexed.measuring(metrics):
                result=indexed.advanceScan(d,entries,acc,time.monotonic()+10,100,target_thumb=target)
            return world,metrics,result

    def test_exact_scan_target_accepts_content_continuity(self):
        w,m,(d,entries,result)=self.run_advance(0)
        self.assertTrue(result.continuity);self.assertAlmostEqual(result.error,0,delta=1)
        self.assertGreater(result.moved,0);self.assertEqual(len(w.drags),1)

    def test_scan_target_four_pixels_off_accepts_real_overlap(self):
        w,m,(d,entries,result)=self.run_advance(4)
        self.assertTrue(result.continuity);self.assertAlmostEqual(result.error,4,delta=1)
        self.assertEqual(len(w.drags),1);self.assertEqual(m.scrollbarDrags,1)

    def test_scan_target_six_pixels_short_accepts_real_overlap(self):
        w,m,(d,entries,result)=self.run_advance(-6)
        self.assertTrue(result.continuity);self.assertAlmostEqual(result.error,-6,delta=1)
        self.assertEqual(len(w.drags),1)

    def test_first_drag_no_move_second_recalculated_drag_moves(self):
        w=World();acc=w.calibrated();calls=[]
        def swallow_first(start,end):
            calls.append((start,end))
            if len(calls)>1:w.drag(start,end)
        with w.patched() as world,patch.object(q,'_menuScrollbarDrag',side_effect=swallow_first):
            d=world.capture();entries=world.entries(d);metrics=DailyScanMetrics()
            with indexed.measuring(metrics):
                d,new,result=indexed.advanceScan(d,entries,acc,time.monotonic()+10,100,target_thumb=112)
            self.assertTrue(result.continuity);self.assertEqual(result.attempts,2)
            self.assertTrue(result.recovered_no_progress);self.assertFalse(result.used_content_fallback)
            self.assertEqual(metrics.noProgressAttempts,1);self.assertEqual(metrics.recoveredNoProgress,1)
            self.assertEqual(len(calls),2);self.assertEqual(len(world.swipes),0);world.touch.assert_not_called()

    def test_two_drag_misses_recover_with_one_content_swipe(self):
        w=World();acc=w.calibrated();calls=[]
        def swallow(start,end):calls.append((start,end))
        with w.patched() as world,patch.object(q,'_menuScrollbarDrag',side_effect=swallow):
            d=world.capture();entries=world.entries(d);metrics=DailyScanMetrics()
            with indexed.measuring(metrics):
                d,new,result=indexed.advanceScan(d,entries,acc,time.monotonic()+10,100,target_thumb=112)
            self.assertTrue(result.continuity);self.assertEqual(result.attempts,3)
            self.assertTrue(result.recovered_no_progress);self.assertTrue(result.used_content_fallback)
            self.assertEqual(metrics.noProgressAttempts,2);self.assertEqual(metrics.contentFallbacks,1)
            self.assertEqual(len(calls),2);self.assertEqual(len(world.swipes),1);world.touch.assert_not_called()

    def test_no_progress_at_confirmed_bottom_returns_endpoint(self):
        w=World();acc=w.calibrated();w.top=533.;prior=w.capture();prior_entries=w.entries(prior)
        acc.add_frame(prior_entries,(533.,573.),999,prior._dailyVerifiedAP,forward=True);w.top=535.
        with w.patched() as world:
            d=world.capture();entries=world.entries(d);metrics=DailyScanMetrics()
            with indexed.measuring(metrics):
                d,new,result=indexed.advanceScan(d,entries,acc,time.monotonic()+10,100,target_thumb=535)
            self.assertTrue(result.reached_endpoint);self.assertEqual(result.moved,0)
            self.assertEqual(len(world.swipes),0);world.touch.assert_not_called()

    def test_first_missed_drag_near_bottom_uses_strict_endpoint_recovery(self):
        w=World();acc=w.calibrated();w.top=533.;prior=w.capture();prior_entries=w.entries(prior)
        acc.add_frame(prior_entries,(533.,573.),999,prior._dailyVerifiedAP,forward=True);calls=[]
        def swallow_once(start,end):
            calls.append((start,end))
            if len(calls)>1:w.drag(start,end)
        with w.patched() as world,patch.object(q,'_menuScrollbarDrag',side_effect=swallow_once):
            d=world.capture();entries=world.entries(d);metrics=DailyScanMetrics()
            with indexed.measuring(metrics):
                d,new,result=indexed.advanceScan(d,entries,acc,time.monotonic()+10,100,target_thumb=535)
            self.assertTrue(result.reached_endpoint);self.assertTrue(result.recovered_no_progress)
            self.assertEqual(metrics.endpointRecoveries,1);self.assertEqual(len(world.swipes),0)
            world.touch.assert_not_called()

    def test_three_no_progress_attempts_fail_without_publishing_partial_scan(self):
        w=World();w.stalled=True;acc=w.calibrated();calls=[]
        with w.patched() as world,patch.object(q,'_menuScrollbarDrag',side_effect=lambda *a:calls.append(a)):
            d=world.capture();entries=world.entries(d);metrics=DailyScanMetrics()
            with indexed.measuring(metrics):
                with self.assertRaisesRegex(q.ScriptStop,'连续三次无进展且未到列表末端'):
                    indexed.advanceScan(d,entries,acc,time.monotonic()+10,100,target_thumb=112)
            self.assertEqual(len(calls),2);self.assertEqual(len(world.swipes),1)
            self.assertEqual(metrics.noProgressAttempts,3);world.touch.assert_not_called()

    def test_content_fallback_must_still_pass_continuity_or_recover(self):
        w=World();acc=w.calibrated();calls=[]
        with w.patched() as world,patch.object(q,'_menuScrollbarDrag',side_effect=lambda *a:calls.append(a)),\
             patch.object(indexed,'_continuous',return_value=False) as continuity:
            d=world.capture();entries=world.entries(d)
            with self.assertRaisesRegex(q.ScriptStop,'相邻屏连续覆盖未恢复'):
                indexed.advanceScan(d,entries,acc,time.monotonic()+10,100,target_thumb=112)
            self.assertGreaterEqual(continuity.call_count,2)
            self.assertGreaterEqual(len(calls),2);self.assertEqual(len(world.swipes),1);world.touch.assert_not_called()

    def test_no_progress_retries_read_and_publish_one_candidate_frame(self):
        w=World();acc=w.calibrated();calls=[];reads=[]
        def swallow_first(start,end):
            calls.append((start,end))
            if len(calls)>1:w.drag(start,end)
        original=indexed._readPage
        def read_once(frame,n):
            reads.append((id(frame.im),n));return original(frame,n)
        with w.patched() as world,patch.object(q,'_menuScrollbarDrag',side_effect=swallow_first),\
             patch.object(indexed,'_readPage',side_effect=read_once):
            d=world.capture();entries=world.entries(d)
            result=indexed.advanceScan(d,entries,acc,time.monotonic()+10,100,target_thumb=112)
            self.assertEqual(len(reads),1);self.assertEqual(reads[0][1],100)
            self.assertEqual(result[2].attempts,2);world.touch.assert_not_called()

    def test_large_skip_recovers_to_last_verified_card(self):
        w=World();acc=w.calibrated();calls=[]
        def skip_then_recover(start,end):
            w.drags.append((start,end));calls.append(1)
            requested=w.top+(end[1]-start[1])
            w.top=299. if len(calls)==1 else max(99.,min(535.,requested))
        w.drag=skip_then_recover
        with w.patched() as world:
            d=world.capture();entries=world.entries(d);metrics=DailyScanMetrics()
            with indexed.measuring(metrics):
                d,new,result=indexed.advanceScan(d,entries,acc,time.monotonic()+10,100,target_thumb=299)
            self.assertEqual(result.mode,'scan-recovery');self.assertTrue(result.continuity)
            self.assertEqual(result.corrections,1);self.assertEqual(metrics.scrollRecoveries,1)
            self.assertEqual(len(world.drags),2);world.touch.assert_not_called()

    def test_page_leaving_daily_after_move_stops(self):
        w=World();acc=w.calibrated()
        with w.patched() as world,patch.object(q,'_isDailyPage',return_value=False):
            d=world.capture();entries=world.entries(d)
            with self.assertRaises(q.ScriptStop):
                indexed.advanceScan(d,entries,acc,time.monotonic()+10,100,target_thumb=120)
            self.assertEqual(len(world.drags),1);world.touch.assert_not_called()


class QuantizedTargetTests(unittest.TestCase):
    def test_eighteenth_screen_accepts_continuous_unreachable_thumb(self):
        w=World(75)  # The index below contains the first 17 observed screens.
        from fgoDailyIndex import DailyScanAccumulator
        index=DailyScanAccumulator(q._title_key)
        tops=[99+8*n for n in range(17)]
        with w.patched() as world:
            for frame,top in enumerate(tops):
                world.top=float(top);d=world.capture();entries=world.entries(d)
                index.add_frame(entries,(top,top+40),frame,getattr(d,'_dailyVerifiedAP',{}),forward=frame>0)
            target=238.4;key=round(target,1);scale=index.scroll_scale
            self.assertIsNotNone(scale);index_absolute=target*scale+185
            # Reproduce the old correction trace: target-3, target+2.7, target-3.
            indexed._thumbHistoryGeometry=40.
            indexed._thumbTargetHistory[key]=[target-3,target+2.7,target-3]
            world.top=float(tops[-1]);d=world.capture();entries=world.entries(d);metrics=DailyScanMetrics()
            with indexed.measuring(metrics):
                d,new,result=indexed.advanceScan(d,entries,index,time.monotonic()+10,17,
                    target_thumb=target,target_absolute_y=index_absolute,target_local_y=185)
            self.assertTrue(result.continuity);self.assertTrue(result.quantized)
            self.assertEqual(result.corrections,0);self.assertEqual(metrics.quantizedAccepts,1)
            self.assertEqual(len(world.drags),1);world.touch.assert_not_called()

    def test_quantized_choice_uses_reachable_position_best_for_content(self):
        w=World();target=238.4;low=target-3;high=target+2.7;scale=w.scale
        with w.patched() as world:
            indexed._thumbHistoryGeometry=40.
            indexed._thumbTargetHistory[round(target,1)]=[low,high,low]
            absolute=target*scale+185;d,result=indexed.seekApprox(target,time.monotonic()+10,
                absolute_y=absolute,scroll_scale=scale,local_y=185)
            self.assertTrue(result.quantized);self.assertEqual(len(world.drags),1)
            self.assertLess(min(abs(d.top-low),abs(d.top-high)),1.5)


class IndexedPositionTests(unittest.TestCase):
    def test_actual_position_is_recomputed_and_small_y_offsets_do_not_micro_adjust(self):
        for y in (190,205):
            with self.subTest(y=y),World().patched() as w:
                index=w.calibrated().build();record=index.entries[12];entry=indexed.entryFromRecord(record)
                def observed_seek(target,deadline,detect=None,**kwargs):
                    w.top=(record.locator.absolute_y-y)/index.scroll_scale
                    frame=w.capture()
                    return frame,DailyScrollResult(target,w.top,w.top-target,w.top-(detect.top if detect else 99),'locate')
                metrics=DailyScanMetrics()
                with patch.object(indexed,'seekApprox',side_effect=observed_seek):
                    result=indexed.locate(entry,index,metrics,time.monotonic()+10)
                self.assertEqual(result['type'],'DailyQuestReady');self.assertEqual(metrics.microAdjustments,0)
                self.assertAlmostEqual(result['predictedY'],y,delta=1);w.touch.assert_not_called()

    def test_actual_y_240_uses_one_content_alignment(self):
        with World().patched() as w:
            index=w.calibrated().build();record=index.entries[12];entry=indexed.entryFromRecord(record)
            def observed_seek(target,deadline,detect=None,**kwargs):
                w.top=(record.locator.absolute_y-240)/index.scroll_scale
                frame=w.capture()
                return frame,DailyScrollResult(target,w.top,w.top-target,w.top-(detect.top if detect else 99),'locate')
            metrics=DailyScanMetrics()
            with patch.object(indexed,'seekApprox',side_effect=observed_seek):
                result=indexed.locate(entry,index,metrics,time.monotonic()+10)
            self.assertEqual(result['type'],'DailyQuestReady');self.assertEqual(metrics.microAdjustments,1)
            self.assertAlmostEqual(result['predictedY'],185,delta=1);w.touch.assert_not_called()

    def test_five_random_start_positions_and_three_item_queue_stay_indexed(self):
        with World().patched() as w,patch.object(type(q.fgoDevice.device),'available',new_callable=PropertyMock,return_value=False):
            index=w.calibrated().build();indexed.remember(index)
            starts=(99,180,260,360,500);positions=(0,6,12,18,24)
            results=[]
            for start,position in zip(starts,positions):
                w.top=float(start);entry=indexed.entryFromRecord(index.entries[position]);results.append(indexed.goto(entry))
            self.assertTrue(all(result['type']=='DailyQuestReady' and result['mode']=='index' for result in results))
            self.assertEqual([r['metrics']['fallbacks'] for r in results],[0]*5)
            self.assertLessEqual(len(w.drags),5);self.assertGreaterEqual(len(w.drags),4);w.touch.assert_not_called()

    def test_three_queue_items_reuse_index_without_top_fallback(self):
        with World().patched() as w,patch.object(type(q.fgoDevice.device),'available',new_callable=PropertyMock,return_value=False):
            index=w.calibrated().build();indexed.remember(index)
            entries=[indexed.entryFromRecord(index.entries[i]) for i in (0,12,24)]
            results=[indexed.goto(entry) for entry in entries]
            self.assertEqual([r['mode'] for r in results],['index']*3)
            self.assertEqual([r['metrics']['fallbacks'] for r in results],[0,0,0])
            w.touch.assert_not_called()


if __name__=='__main__':unittest.main()

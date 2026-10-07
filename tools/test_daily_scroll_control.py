"""Regression tests for observed-position daily scrollbar control."""
import time
import unittest
from unittest.mock import patch,PropertyMock

from daily_index_test_support import World,q,indexed
from fgoDailyIndex import DailyScrollResult,DailyScanMetrics,DailyContinuityResult,DailyScanAccumulator


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
             patch.object(indexed,'verifyScanContinuity',return_value=DailyContinuityResult(False,'FAILED')) as continuity:
            d=world.capture();entries=world.entries(d)
            with self.assertRaisesRegex(q.ScriptStop,'相邻屏连续覆盖未恢复'):
                indexed.advanceScan(d,entries,acc,time.monotonic()+10,100,target_thumb=112)
            self.assertGreaterEqual(continuity.call_count,3)
            self.assertGreaterEqual(len(calls),2)
            self.assertEqual(world.swipes[-2:],[(True,80),(True,100)]);world.touch.assert_not_called()

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

    def test_large_discontinuity_only_uses_two_small_reverse_swipes(self):
        w=World();acc=w.calibrated();calls=[]
        def skip(start,end):
            w.drags.append((start,end));calls.append(1);w.top=299.
        w.drag=skip
        with w.patched() as world:
            d=world.capture();entries=world.entries(d)
            with self.assertRaisesRegex(q.ScriptStop,'相邻屏连续覆盖未恢复'):
                indexed.advanceScan(d,entries,acc,time.monotonic()+10,100,target_thumb=299)
            self.assertEqual(len(world.drags),1)
            self.assertEqual(world.swipes,[(True,80),(True,100)])
            world.touch.assert_not_called()

    def test_bootstrap_frame_three_recovers_transient_title_miss_by_small_reverse_swipe(self):
        w=World();acc=DailyScanAccumulator(q._title_key)
        frames=[
            [w.entry(i,y) for i,y in enumerate((150,330,510))],
            [w.entry(i,y) for i,y in ((1,150),(2,240),(3,330),(4,420),(5,510))],
            [w.entry(i,y) for i,y in enumerate((140,225,310,395,480,565))],
        ]
        frame_tops=(99.,120.,141.)
        for idx,(frame,top) in enumerate(zip(frames,frame_tops)):
            ap={q._title_key(e.title):e.discovered_position[2]+75 for e in frame}
            acc.add_frame(frame,(top,top+40),idx,ap,forward=idx>0)
        self.assertEqual([len(frame) for frame in frames],[3,5,6])
        self.assertTrue(indexed.verifyScanContinuity(frames[0],frames[1],(99,139),(120,160),acc,phase='bootstrap').accepted)
        self.assertTrue(indexed.verifyScanContinuity(frames[1],frames[2],(120,160),(141,181),acc,phase='bootstrap').accepted)
        # Even with an apparent model present, bootstrap itself is title-overlap only.
        acc.scroll_scale=10.;acc.card_pitch=180.
        acc.absolute={q._title_key(e.title):e.discovered_position[2]+99 for e in frames[2]}
        with w.patched() as world,patch.object(indexed,'seekApprox',side_effect=AssertionError('bootstrap must not seek by absolute position')):
            # The actual old screen contains three items. Include the six OCR
            # observations from frame 3 as its old key set to model the report.
            world.top=99.;d=world.capture();world.entries(d);old_entries=frames[2]
            old_keys={q._title_key(e.title) for e in old_entries}
            # Frame 1 OCR misses the true shared boundary title once. The fresh
            # read after the small reverse content swipe sees it again.
            world.hide_once=set(old_keys)
            metrics=DailyScanMetrics()
            d,new_entries,result=indexed.advanceScan(d,old_entries,acc,time.monotonic()+10,3,
                phase='bootstrap',distance=220,metrics=metrics)
            self.assertTrue(result.continuity);self.assertEqual(result.mode,'scan-recovery')
            self.assertEqual(metrics.bootstrapOverlapRecoveries,1);self.assertEqual(metrics.continuityRecoveries,1)
            self.assertTrue(any(q._title_key(e.title) in old_keys for e in new_entries))
            self.assertEqual(world.swipes[0][0],False);self.assertEqual(world.swipes[1],(True,80))
            self.assertEqual(world.drags,[]);world.touch.assert_not_called()

    def test_bootstrap_uses_title_overlap_even_when_absolute_model_exists(self):
        w=World();acc=w.calibrated()
        old=[w.entry(0,250),w.entry(1,437)]
        new=[w.entry(2,250),w.entry(3,437)]
        result=indexed.verifyScanContinuity(old,new,(120.,160.),(140.,180.),acc,phase='bootstrap')
        self.assertFalse(result.accepted);self.assertEqual(result.reason,'FAILED')
        calibrated=indexed.verifyScanContinuity(old,new,(120.,160.),(140.,180.),acc,phase='calibrated')
        self.assertIn(calibrated.reason,('ABSOLUTE_ADJACENCY','FAILED'))

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

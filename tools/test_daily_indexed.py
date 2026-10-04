"""Static indexed menu regressions. Images are generated blank geometry frames."""
import unittest,json,inspect,time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch,Mock,PropertyMock
from daily_index_test_support import World,q,indexed
from fgoDailyIndex import *

class AccumulatorTests(unittest.TestCase):
    def test_cross_position_confirmation(self):
        acc=World().calibrated();self.assertTrue(acc.verified(q._title_key('未来每日挑战05 特级')))
    def test_same_position_does_not_verify(self):
        w=World();acc=DailyScanAccumulator(q._title_key);e=w.entry(1,200)
        for n in range(3):acc.add_frame([e],(100,140),n,{q._title_key(e.title):275})
        self.assertFalse(acc.verified(q._title_key(e.title)))
    def test_same_frame_does_not_verify(self):
        w=World();acc=DailyScanAccumulator(q._title_key);e=w.entry(1,250);key=q._title_key(e.title)
        acc.add_frame([e],(100,140),1,{key:325});acc.add_frame([w.entry(1,200)],(110,150),1,{key:275});self.assertFalse(acc.verified(key))
    def test_explicit_top_edge_recheck(self):
        acc=World().calibrated();self.assertTrue(acc.verified(q._title_key('未来每日挑战00 特级')))
    def test_explicit_bottom_edge_recheck(self):
        acc=World().calibrated();self.assertTrue(acc.verified(q._title_key('未来每日挑战24 特级')))
    def test_a3_a5_gap_is_position_not_name(self):
        w=World();acc=w.calibrated((4,));gaps=acc.gaps();self.assertEqual(len(gaps),1);self.assertAlmostEqual(gaps[0].expected_absolute_y,w.absolute(4),delta=1)
        self.assertFalse(hasattr(gaps[0],'title'))
    def test_multiple_consecutive_missing_slots(self):self.assertEqual(len(World().calibrated((4,5)).gaps()),2)
    def test_gap_prevents_publication(self):
        with self.assertRaises(DailyIndexError):World().calibrated((4,)).build()
    def test_median_scale(self):
        w=World();self.assertAlmostEqual(w.calibrated().scroll_scale,w.scale,delta=.1)
    def test_outlier_scale_filtered(self):
        w=World();acc=w.calibrated();e=w.entry(20,200);key=q._title_key(e.title)
        # Bad scale samples are ignored; contradictory absolute observations remain fail-closed.
        acc.observations_by_title['outlier']=[DailyObservation('outlier',100,140,500,575,100),DailyObservation('outlier',103,143,200,275,101)]
        with self.assertRaises(DailyIndexError):acc.calibrate()
        self.assertAlmostEqual(acc.scroll_scale,w.scale,delta=.1)
    def test_ap_required(self):
        with self.assertRaisesRegex(DailyIndexError,'AP'):DailyScanAccumulator(q._title_key).add_frame([World().entry(0,140)],(99,139),1,{})
    def test_duplicate_title_rejected(self):
        e=World().entry(0,140)
        with self.assertRaisesRegex(DailyIndexError,'duplicate'):DailyScanAccumulator(q._title_key).add_frame([e,e],(99,139),1,{q._title_key(e.title):215})
    def test_reversed_order_rejected(self):
        w=World();acc=DailyScanAccumulator(q._title_key);entries=[w.entry(0,140),w.entry(1,327)];ap={q._title_key(e.title):e.discovered_position[2]+75 for e in entries}
        acc.add_frame(entries,(99,139),1,ap,True)
        with self.assertRaisesRegex(DailyIndexError,'order'):acc.add_frame(list(reversed(entries)),(102,142),2,ap,True)
    def test_locator_preserves_old_discovered_position(self):
        e=World().entry(0,140);self.assertEqual(e.discovered_position,(0,947,140));self.assertIsNone(e.locator)
    def test_future_name_without_whitelist(self):self.assertTrue(q._valid_daily_title('未来特殊每日试炼 特级'))
    def test_new_type_does_not_require_category(self):self.assertEqual(q._quest_type('未来特殊每日试炼 特级'),'unknown')
    def test_index_round_trip_text_numbers_only(self):
        index=World().calibrated().build()
        with TemporaryDirectory() as t:
            p=Path(t)/'index.json';save_index(index,p);self.assertEqual(load_index(p),index);self.assertNotIn('image',p.read_text(encoding='utf-8'))
    def test_geometry_change_invalidates_model(self):self.assertFalse(World().calibrated().build().geometry_matches((99,200)))
    def test_order_conflict_invalidates_model(self):
        index=World().calibrated().build();self.assertFalse(index.order_matches(list(reversed(index.ordered_title_keys[:3]))))
    def test_cache_corruption_is_not_authority(self):
        with TemporaryDirectory() as t:
            p=Path(t)/'index.json';p.write_text('{broken');self.assertIsNone(load_index(p))
    def test_invalidated_cache_not_loaded(self):
        with TemporaryDirectory() as t:
            p=Path(t)/'index.json';p.write_text('{"version":1,"invalidated":true}');self.assertIsNone(load_index(p))
    def test_no_reverse_pass_in_scan(self):self.assertNotIn('_reverifyDailyTitlesCN',inspect.getsource(indexed.scan))

class ScanTests(unittest.TestCase):
    def test_forward_complete_and_restore_top(self):
        with World().patched() as w:
            result=indexed.scan();self.assertEqual(len(result['entries']),w.n);self.assertTrue(result['complete']);self.assertEqual(w.top,99);self.assertFalse(any(w.swipes));w.touch.assert_not_called()
    def test_scan_over_ten_pages(self):
        with World(40).patched() as w:
            result=indexed.scan();self.assertGreater(len(w.swipes)+len(w.drags),10);self.assertEqual(len(result['entries']),40)
    def test_gap_recovered_only_from_real_local_title(self):
        with World().patched() as w:
            w.missing={4};result=indexed.scan();self.assertEqual(len(result['entries']),25);self.assertGreater(result['metrics']['gapRecoveries'],0)
    def test_unreadable_gap_stops_without_click(self):
        with World().patched() as w:
            w.missing={4};w.local_missing={4}
            with self.assertRaises(q.ScriptStop):indexed.scan()
            w.touch.assert_not_called()
    def test_stalled_forward_scan_refuses_partial(self):
        with World().patched() as w:
            w.stalled=True
            with self.assertRaisesRegex(q.ScriptStop,'未向末端'):indexed.scan()
            self.assertEqual(len(w.swipes),3)
    def test_reuses_only_calibration_not_cached_observations(self):
        with World().patched() as w:
            first=indexed.scan();second=indexed.scan();self.assertTrue(second['reusedCalibration']);self.assertEqual(len(second['entries']),w.n)
    def test_edge_targeted_reads_occur(self):
        with World().patched() as w:self.assertGreater(indexed.scan()['metrics']['targetedRechecks'],0)

class LocateTests(unittest.TestCase):
    def setup_index(self,w):
        index=w.calibrated().build();indexed.remember(index);return index
    def test_cached_direct_jump_no_top_scan(self):
        with World().patched() as w:
            index=self.setup_index(w);entry=indexed.entryFromRecord(index.entries[12])
            with patch.object(q,'_scrollToTop',side_effect=AssertionError('no top search')):
                result=indexed.goto(entry)
            self.assertEqual(result['mode'],'index');self.assertEqual(result['metrics']['scrollbarDrags'],1);w.touch.assert_not_called()
    def test_second_queue_item_reuses_index_in_user_order(self):
        with World().patched() as w:
            index=self.setup_index(w);entries=[indexed.entryFromRecord(index.entries[i]) for i in (18,5)]
            with patch.object(q,'_gotoDailyEntrySequential',side_effect=AssertionError('no sequential')):
                results=[indexed.goto(e) for e in entries]
            self.assertEqual([r['entry'].title for r in results],[e.title for e in entries]);self.assertTrue(all(r['mode']=='index' for r in results))
    def test_missing_target_uses_neighbors_but_never_clicks(self):
        with World().patched() as w:
            index=self.setup_index(w);w.local_missing={12}
            with self.assertRaisesRegex(q.ScriptStop,'已定位目标卡槽'):indexed.goto(indexed.entryFromRecord(index.entries[12]))
            w.touch.assert_not_called()
    def test_neighbor_recovers_target_from_fresh_local_ocr(self):
        with World().patched() as w:
            index=self.setup_index(w);local=w.local;calls=[0]
            def transient(d,y,radius=60):
                calls[0]+=1
                return [e for e in local(d,y,radius) if calls[0]>1 or e.title!=index.entries[12].title]
            with patch.object(indexed,'localEntries',side_effect=transient):result=indexed.goto(indexed.entryFromRecord(index.entries[12]))
            self.assertEqual(result['mode'],'neighbor');w.touch.assert_not_called()
    def test_geometry_invalidates_then_controlled_fallback(self):
        with World().patched() as w:
            index=self.setup_index(w);w.height=80
            with patch.object(q,'_gotoDailyEntrySequential',side_effect=q.ScriptStop('fallback sentinel')) as fallback:
                with self.assertRaisesRegex(q.ScriptStop,'fallback sentinel'):indexed.goto(indexed.entryFromRecord(index.entries[12]))
            fallback.assert_called_once()
    def test_fallback_anchor_reused_without_new_scan(self):
        with World().patched() as w,patch.object(type(q.fgoDevice.device),'available',new_callable=PropertyMock,return_value=True):
            e=w.entry(12,185)
            def sequential(entry,opened=False):
                w.top=(w.absolute(12)-185)/w.scale;return dict(type='DailyQuestReady',entry=e,position=(947,185))
            with patch.object(q,'_gotoDailyEntrySequential',side_effect=sequential) as seq:
                first=indexed.goto(e);w.top=99;second=indexed.goto(e)
            self.assertEqual(seq.call_count,1);self.assertEqual(first['mode'],'fallback');self.assertEqual(second['mode'],'index')
    def test_persistent_wrong_header_stops_and_invalidates(self):
        with World().patched() as w:
            self.setup_index(w)
            with patch.object(q,'_isDailyPage',return_value=False):
                with self.assertRaises(q.ScriptStop):indexed.safe(w.capture())
            self.assertIsNone(indexed._cached);w.touch.assert_not_called()
    def test_scrollbar_corrections_are_bounded(self):
        with World().patched() as w,patch.object(q,'_menuScrollbarDrag') as swipe:
            with self.assertRaisesRegex(q.ScriptStop,'有限校正'):indexed.dragTo(300,time.monotonic()+10)
            self.assertEqual(swipe.call_count,3)
    def test_changed_page_never_drags(self):
        with World().patched() as w,patch.object(q,'_dailyLocatorFrameCN',side_effect=q.ScriptStop('modal')):
            with self.assertRaises(q.ScriptStop):indexed.dragTo(300,time.monotonic()+10)
            self.assertEqual(w.drags,[])

class SlotConflictTests(unittest.TestCase):
    def alias(self,w,acc,frame,top):
        cy=round(w.absolute(4)-acc.scroll_scale*top)
        e=q.DailyQuestEntry('误读的每日挑战 特级','unknown','unknown','',(0,947,cy))
        acc.add_frame([e],(top,top+40),frame,{q._title_key(e.title):cy+75});return q._title_key(e.title)
    def test_coincident_different_names_cannot_publish(self):
        w=World();acc=w.calibrated();self.alias(w,acc,200,(w.absolute(4)-200)/acc.scroll_scale)
        self.assertEqual(len(acc.conflicts()),1)
        with self.assertRaisesRegex(DailyIndexError,'conflicting'):acc.build()
    def test_unverified_alias_requires_real_independent_title_rechecks(self):
        with World().patched() as w:
            acc=w.calibrated();key=self.alias(w,acc,200,(w.absolute(4)-200)/acc.scroll_scale);m=DailyScanMetrics()
            with indexed.measuring(m):indexed._targeted(acc,time.monotonic()+20,m)
            self.assertNotIn(key,acc.entries);self.assertEqual(acc.build().entry_count,25);self.assertEqual(m.targetedRechecks,2);w.touch.assert_not_called()
    def test_two_verified_competing_titles_still_stop(self):
        with World().patched() as w:
            acc=w.calibrated();self.alias(w,acc,200,(w.absolute(4)-200)/acc.scroll_scale);self.alias(w,acc,201,(w.absolute(4)-270)/acc.scroll_scale)
            m=DailyScanMetrics()
            with indexed.measuring(m),self.assertRaisesRegex(q.ScriptStop,'标题仍有冲突'):indexed._targeted(acc,time.monotonic()+20,m)
    def test_clipped_coordinates_not_observations(self):
        with self.assertRaisesRegex(DailyIndexError,'clipped'):DailyScanAccumulator(q._title_key).add_frame([World().entry(0,100)],(99,139),1,{})

class VisibleCardTests(unittest.TestCase):
    def test_same_spatial_card_proposals_merge(self):
        w=World();self.assertEqual(len(q._dailyUniqueVisibleCards([w.entry(1,250),w.entry(1,258)])),1)
    def test_identical_names_on_two_real_cards_refuse(self):
        w=World()
        with self.assertRaisesRegex(q.ScriptStop,'不同卡片'):q._dailyUniqueVisibleCards([w.entry(1,200),w.entry(1,387)])
    def test_lower_complete_title_and_ap_visible(self):
        from daily_index_test_support import env
        frame=env['FakeDetect']();item=env['item'];title='未来每日挑战 特级'
        spans=[item(title,25,480,135,20),item('AP20',25,555,60,20)]
        with patch.object(q.OCR.ZHS,'detect_and_ocr',return_value=spans),patch.object(q,'_readDailyTitle',return_value=title):
            entries=q._dailyEntriesAt(frame)
        self.assertEqual(entries[0].discovered_position[2],595);self.assertEqual(frame._dailyVerifiedAP[q._title_key(title)],670)
    def test_transient_thumb_frame_is_read_only_retried(self):
        with World().patched() as w:
            original=q._scrollbar;failed=[False]
            def transient(im):
                if w.drags and not failed[0]:failed[0]=True;raise q.ScriptStop('未唯一识别每日任务滚动条')
                return original(im)
            with patch.object(q,'_scrollbar',side_effect=transient):d=indexed.dragTo(300,time.monotonic()+10)
            self.assertTrue(failed[0]);self.assertEqual(len(w.drags),1);w.touch.assert_not_called()

class PhysicalGeometryTests(unittest.TestCase):
    def test_small_thumb_change_with_large_local_change_is_independent(self):
        w=World();acc=DailyScanAccumulator(q._title_key);key=q._title_key(w.entry(0,200).title)
        acc.add_frame([w.entry(0,240)],(110,150),1,{key:315})
        acc.add_frame([w.entry(0,200)],(111,151),2,{key:275})
        self.assertTrue(acc.verified(key))
    def test_gain_learned_from_observed_real_movement(self):
        w=World();original=w.drag
        def reduced(a,b):
            w.drags.append((a,b));w.top=max(99,min(535,w.top+(b[1]-a[1])*.93))
        w.drag=reduced
        with w.patched():
            d=indexed.dragTo(300,time.monotonic()+10)
            self.assertLessEqual(abs(d.top-300),1.5);self.assertLessEqual(len(w.drags),3)
    def test_thumb_geometry_change_stops_after_one_input(self):
        w=World()
        def changed(a,b):w.drags.append((a,b));w.top=300;w.height=80
        w.drag=changed
        with w.patched():
            with self.assertRaisesRegex(q.ScriptStop,'几何'):indexed.dragTo(300,time.monotonic()+10)
            self.assertEqual(len(w.drags),1)
    def test_top_pixel_quantization_is_accepted_only_at_boundary(self):
        with World().patched() as w:
            w.top=98;self.assertIsNotNone(indexed.dragTo(99,time.monotonic()+10));self.assertEqual(w.drags,[])
    def test_held_scrollbar_gesture_is_one_input_and_stays_in_track(self):
        from airtest.core.android.android import Android as AirAndroid
        android=Mock(spec=q.fgoDevice.Android);android.name='device';android.display_info={'orientation':0}
        android.scale=1;android.border=(0,0);android.render=(0,0,1280,720)
        from unittest.mock import MagicMock
        android.mutex=MagicMock()
        with patch.object(q.fgoDevice.device,'I',android),patch.object(AirAndroid,'swipe_along') as swipe:
            q._menuScrollbarDrag((1258,123),(1258,119))
        swipe.assert_called_once();points=swipe.call_args.args[1]
        self.assertTrue(all(x==1258 and 100<=y<=574 for x,y in points));self.assertEqual(points[-1],points[-2])
    def test_ocr_instrumentation_restores_on_failure(self):
        old=q.OCR.ZHS.ocr_single_line;m=DailyScanMetrics()
        with self.assertRaises(RuntimeError):
            with indexed.measuring(m):raise RuntimeError('sentinel')
        self.assertIs(q.OCR.ZHS.ocr_single_line,old);self.assertIsNone(indexed._metrics.get())
    def test_local_read_uses_actual_ap_and_title(self):
        frame=env_frame=__import__('types').SimpleNamespace(im=__import__('numpy').zeros((720,1280,3),dtype=__import__('numpy').uint8))
        item=__import__('daily_index_test_support').env['item'];title='未来的新型每日挑战 特级'
        spans=[item(title,25,50,135,20),item('AP20',25,125,60,20)]
        with patch.object(q.OCR.ZHS,'detect_and_ocr',return_value=spans),patch.object(q,'_readDailyTitle',return_value=title):
            entries=indexed.localEntries(frame,200)
        self.assertEqual([e.title for e in entries],[title]);self.assertEqual(frame._dailyVerifiedAP[q._title_key(title)],275)
    def test_local_read_without_ap_never_publishes_title(self):
        import numpy
        frame=__import__('types').SimpleNamespace(im=numpy.zeros((720,1280,3),dtype=numpy.uint8))
        item=__import__('daily_index_test_support').env['item']
        with patch.object(q.OCR.ZHS,'detect_and_ocr',return_value=[item('未来新的每日挑战 特级',25,50,135,20)]),patch.object(q.OCR.EN,'ocr_single_line',return_value=('',0)),patch.object(q,'_readDailyTitle') as title:
            self.assertEqual(indexed.localEntries(frame,200),[])
        title.assert_not_called()

class FinalScanEvidenceTests(unittest.TestCase):
    def test_local_ap_row_recovers_actual_title_without_title_proposal(self):
        import numpy
        from types import SimpleNamespace
        item=__import__('daily_index_test_support').env['item']
        frame=SimpleNamespace(im=numpy.zeros((720,1280,3),dtype=numpy.uint8))
        actual='未来新增每日挑战 特级'
        with patch.object(q.OCR.ZHS,'detect_and_ocr',return_value=[item('AP20',25,125,60,20)]),patch.object(q,'_readDailyTitle',return_value=actual) as title:
            entries=indexed.localEntries(frame,200)
        self.assertEqual([e.title for e in entries],[actual]);title.assert_called_once_with(frame.im,200)
        self.assertEqual(frame._dailyVerifiedAP[q._title_key(actual)],275)
    def test_ap_only_unreadable_title_does_not_fill_from_index(self):
        import numpy
        from types import SimpleNamespace
        item=__import__('daily_index_test_support').env['item']
        frame=SimpleNamespace(im=numpy.zeros((720,1280,3),dtype=numpy.uint8))
        with patch.object(q.OCR.ZHS,'detect_and_ocr',return_value=[item('AP20',25,125,60,20)]),patch.object(q,'_readDailyTitle',return_value=None):
            self.assertEqual(indexed.localEntries(frame,200),[])
        self.assertEqual(frame._dailyVerifiedAP,{})
    def test_independent_ap_column_backreads_top_card_omitted_by_navigation(self):
        from daily_index_test_support import env
        frame=env['FakeDetect']();item=env['item'];actual='未来每日任务 特级'
        frame._dailyNavigationImage=frame.im;frame._dailyNavigationLabels=[]
        ap=__import__('types').SimpleNamespace(text='AP5',box=(800,205,855,225),score=.99)
        with patch.object(q,'_dailyAPSpans',return_value=[ap]),patch.object(q,'_readDailyTitle',return_value=actual):
            entries=q._dailyEntriesAt(frame)
        self.assertEqual([e.title for e in entries],[actual]);self.assertEqual(entries[0].discovered_position[2],140)
    def test_final_return_rechecks_top_without_separate_edge_trip(self):
        with World().patched() as w:
            seen=[];original=indexed._targeted
            def targeted(acc,deadline,metrics,d=None,top_key=None):
                seen.append(top_key);return original(acc,deadline,metrics,d,top_key)
            with patch.object(indexed,'_targeted',side_effect=targeted):result=indexed.scan()
            self.assertTrue(result['complete']);self.assertEqual(seen,[q._title_key(w.entry(0,140).title)])
            self.assertEqual(w.top,99);w.touch.assert_not_called()

if __name__=='__main__':unittest.main()

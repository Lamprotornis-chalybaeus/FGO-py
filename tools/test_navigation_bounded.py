"""Offline navigation/dispatch safety regressions; never connect to a device."""
import ast,logging,os,sys,types,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import numpy
APP=Path(__file__).resolve().parents[1]/'FGO-py';sys.path.insert(0,str(APP))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
if 'fgoLogging' not in sys.modules:
    fake=types.ModuleType('fgoLogging');fake.getLogger=logging.getLogger;fake.logMeta=lambda logger:type;fake.logit=lambda logger,*args,**kwargs:lambda func:func
    sys.modules['fgoLogging']=fake
old=os.getcwd();os.chdir(APP)
try:
    import fgoNavigation as nav
    import fgoKernel,fgoGuiOperation,fgoReishift
finally:os.chdir(old)

def label(text,x=900,y=180):return nav.Label(text,(x-40,y-15,x+40,y+15),.99)
class Frame:
    im=numpy.zeros((720,1280,3),numpy.uint8)
    def isMainInterface(self):return True
    def isWeeklyMission(self):return False
    def _loc(self,*args):return(.01,0,(0,0),(0,0))
    def findChapter(self,*args):return(1100,180)

class NavigationTests(unittest.TestCase):
    def test_deadline(self):
        guard=nav.NavigationGuard('winter',1)
        with patch.object(nav.time,'monotonic',return_value=guard.deadline+1):
            with self.assertRaisesRegex(nav.ScriptStop,'timeout'):guard.check()
    def test_no_progress(self):
        guard=nav.NavigationGuard('scroll')
        for _ in range(3):guard.progress(('same',))
        with self.assertRaisesRegex(nav.ScriptStop,'no progress'):guard.progress(('same',))
    def test_transition_limit(self):
        with self.assertRaisesRegex(nav.ScriptStop,'transitions'):list(nav.NavigationGuard('route',max_steps=2).steps())
    def test_inherited_budget(self):
        @nav.boundedNavigation(1)
        def inner():return nav.NavigationGuard('child',200).deadline
        with patch.object(nav.time,'monotonic',return_value=10):self.assertEqual(inner(),11)
    def test_unique_winter(self):self.assertEqual(nav.unique([label('冬木')],'冬木',(640,95,1230,580)).text,'冬木')
    def test_duplicate_winter_stops(self):
        with self.assertRaisesRegex(nav.ScriptStop,'ambiguous'):nav.unique([label('冬木'),label('冬木',900,400)],'冬木',(640,95,1230,580))
    def test_fuzzy_winter_not_used(self):self.assertIsNone(nav.unique([label('冬未')],'冬木',(640,95,1230,580)))
    def test_menu_only_is_not_home(self):self.assertEqual(nav.classify(Frame(),[label('菜单',1180,650)]),'UNKNOWN')
    def test_event_menu_is_not_home(self):
        items=[label('关闭',110,40),label('关卡举办时间 剩余13日',1060,240),label('序幕',850,150)]
        self.assertEqual(nav.classify(Frame(),items),'EVENT')
    def test_free_menu_is_not_home(self):self.assertEqual(nav.classify(Frame(),[label('关闭',110,40),label('自由关卡',815,180)]),'FREE_QUEST')
    def test_root_needs_header_and_menu(self):
        self.assertEqual(nav.classify(Frame(),[label('通知',110,40)]),'ROOT_CATEGORY')
        d=Frame();d.isMainInterface=lambda:False
        self.assertEqual(nav.classify(d,[label('通知',110,40)]),'UNKNOWN')
    def test_modal_overrides_home(self):self.assertEqual(nav.classify(Frame(),[label('通知',110,40),label('是否开始关卡',640,350)]),'BLOCKED')
    def test_fuyuki_identity_uses_prefix_and_exact_era(self):
        frame=Frame();frame._crop=lambda rect:frame.im[rect[1]:rect[3],rect[0]:rect[2]]
        items=[label('管理室',110,40),label('燃烧污染都市各木',1080,28)]
        with patch.object(nav.OCR.ZHS,'ocr_single_line',side_effect=[('燃烧污染都市',.94),('燃烧污染都市',.95),('D.2004',.93),('D.2004',.94)]):
            self.assertEqual(nav.classify(frame,items),'MAP')
            self.assertTrue(nav.mapChapterConfirmed(frame,items,(1,0)))
            self.assertFalse(nav.mapChapterConfirmed(frame,items,(1,1)))
    def test_wrong_era_does_not_confirm_fuyuki(self):
        frame=Frame();frame._crop=lambda rect:frame.im[rect[1]:rect[3],rect[0]:rect[2]]
        items=[label('管理室',110,40),label('燃烧污染都市各木',1080,28)]
        with patch.object(nav.OCR.ZHS,'ocr_single_line',side_effect=[('燃烧污染都市',.94),('燃烧污染都市',.95),('D.2005',.93),('D.2005',.94)]):
            self.assertEqual(nav.classify(frame,items),'UNKNOWN')
            self.assertFalse(nav.mapChapterConfirmed(frame,items,(1,0)))
    def test_header_double_read_disagreement_stops(self):
        frame=Frame();frame._crop=lambda rect:frame.im[rect[1]:rect[3],rect[0]:rect[2]]
        with patch.object(nav.OCR.ZHS,'ocr_single_line',side_effect=[('燃烧污染都市',.94),('燃烧污染城市',.95),('D.2004',.93),('D.2004',.94)]):
            self.assertFalse(nav.confirmedFuyukiHeaderCN(frame,[label('燃烧污染都市各木',1080,28)]))
    def test_other_chapter_header_cannot_be_fuyuki(self):
        frame=Frame()
        with patch.object(nav.OCR.ZHS,'ocr_single_line') as ocr:
            self.assertFalse(nav.mapChapterConfirmed(frame,[label('邪龙百年战争奥尔良',1080,28)],(1,0)))
            ocr.assert_not_called()
    def test_fixed_header_does_not_replace_return_control(self):
        with patch.object(nav,'confirmedFuyukiHeaderCN',return_value=True):
            self.assertEqual(nav.classify(Frame(),[label('燃烧污染都市各木',1080,28)]),'UNKNOWN')
    def test_map_pan_uses_verified_same_chapter_anchor(self):
        with patch.object(nav,'visibleMapNode',return_value=(640,360)),patch.object(nav,'mapCamera') as atlas:
            camera=nav.visibleMapCameraCN(Frame(),[],(1,0))
            numpy.testing.assert_array_equal(camera,fgoReishift.place[(1,0,0)].coord)
            atlas.assert_not_called()
    def test_map_pan_without_verified_node_keeps_atlas_guard(self):
        with patch.object(nav,'visibleMapNode',return_value=None),patch.object(nav,'mapCamera',side_effect=nav.ScriptStop('atlas match unreliable')):
            with self.assertRaisesRegex(nav.ScriptStop,'atlas match unreliable'):nav.visibleMapCameraCN(Frame(),[],(1,0))
    def test_missing_chapter_at_bottom_stops(self):
        frame=Frame();items=[label('通知',110,40)]
        with patch.object(nav,'returnRootCN',return_value=frame),patch.object(nav,'_read',return_value=(frame,items,'ROOT_CATEGORY')),patch.object(nav,'_scroll',side_effect=[(frame,items,'ROOT_CATEGORY',True),(frame,items,'ROOT_CATEGORY',True)]):
            with self.assertRaisesRegex(nav.ScriptStop,'列表底部'):nav.gotoChapterCN((1,0))
    def test_chapter_enters_only_verified_map(self):
        frame=Frame();root=[label('通知',110,40),label('冬木')];mapped=[label('管理室',110,40),label('燃烧污染都市 冬木',1050,30)]
        with patch.object(nav,'returnRootCN',return_value=frame),patch.object(nav,'_read',return_value=(frame,root,'ROOT_CATEGORY')),patch.object(nav,'_tapTransition',return_value=(frame,mapped,'MAP')) as tap:
            self.assertIs(nav.gotoChapterCN((1,0)),frame);tap.assert_called_once()
    def test_chapter_template_is_optional_with_verified_title(self):
        frame=Frame();frame.findChapter=lambda *args:None
        root=[label('通知',110,40),label('冬木'),label('特异点F',950,110)];mapped=[label('管理室',110,40),label('燃烧污染都市冬木',1050,30)]
        with patch.object(nav,'returnRootCN',return_value=frame),patch.object(nav,'_read',return_value=(frame,root,'ROOT_CATEGORY')),patch.object(nav.OCR.ZHS,'ocr_single_line',return_value=('冬木',.99)),patch.object(nav,'_tapTransition',return_value=(frame,mapped,'MAP')):
            self.assertIs(nav.gotoChapterCN((1,0)),frame)
    def test_scroll_top_and_bottom_probe(self):
        import fgoQuickQuest
        frame=Frame()
        for top,thumb in ((True,(95,220)),(False,(460,580))):
            guard=nav.NavigationGuard('boundary')
            with patch.object(nav,'scrollbar',return_value=thumb),patch.object(nav,'_read',return_value=(frame,[],'ROOT_CATEGORY')),patch.object(fgoQuickQuest,'_menuSwipe'),patch.object(nav.schedule,'sleep'):
                *_,end=nav._scroll(guard,frame,[],top);self.assertTrue(end);self.assertEqual(guard.boundary,'top' if top else 'bottom')
    def test_middle_scroll_stalls(self):
        import fgoQuickQuest
        frame=Frame();guard=nav.NavigationGuard('middle')
        with patch.object(nav,'scrollbar',return_value=(200,350)),patch.object(nav,'_read',return_value=(frame,[],'ROOT_CATEGORY')),patch.object(fgoQuickQuest,'_menuSwipe'),patch.object(nav.schedule,'sleep'):
            nav._scroll(guard,frame,[],False);nav._scroll(guard,frame,[],False)
            with self.assertRaisesRegex(nav.ScriptStop,'no progress'):nav._scroll(guard,frame,[],False)
    def test_map_no_progress_stops(self):
        import fgoQuickQuest
        frame=Frame();items=[label('管理室',110,40),label('燃烧污染都市冬木',1050,30)]
        with patch.object(nav,'_read',return_value=(frame,items,'MAP')),patch.object(nav,'visibleMapNode',return_value=None),patch.object(nav,'mapCamera',return_value=numpy.array((2000,1500))),patch.object(fgoQuickQuest,'_menuSwipe'),patch.object(nav.schedule,'sleep'):
            with self.assertRaisesRegex(nav.ScriptStop,'camera did not move'):nav.locateMapCN((1,0,0,0),nav.NavigationGuard('map'))
    def test_free_list_no_progress_stops(self):
        import fgoQuickQuest
        frame=Frame();items=[label('关闭',110,40),label('自由关卡',815,400),label('AP4',810,440)]
        with patch.object(nav,'_read',return_value=(frame,items,'FREE_QUEST')),patch.object(nav,'scrollbar',return_value=(200,300)),patch.object(fgoQuickQuest,'_menuSwipe'),patch.object(nav.schedule,'sleep'):
            with self.assertRaisesRegex(nav.ScriptStop,'no progress'):nav.locateFreeListCN((1,0,2,0),nav.NavigationGuard('free'))
    def test_free_card_needs_ap(self):self.assertEqual(nav.freeCards([label('自由关卡',815,180)]),[])
    def test_map_prefix_does_not_relax_coordinate(self):
        self.assertEqual(nav.mapLabelKey('末确认坐标X-C'),nav.mapLabelKey('未确认坐标X-C'))
        self.assertNotEqual(nav.mapLabelKey('未确认坐标X-D'),nav.mapLabelKey('未确认坐标X-C'))
    def test_unknown_current_quest_stops_without_touch(self):
        with patch.object(nav.XDetect,'region','CN'),patch.object(nav,'Detect',return_value=Frame()),patch.object(nav,'labels',return_value=[label('通知',110,40)]),patch.object(nav.fgoDevice.device,'touch') as touch:
            with self.assertRaisesRegex(nav.ScriptStop,'前置检查'):nav.checkCurrentQuest()
            touch.assert_not_called()
    def test_kernel_goto_failure_retains_task(self):
        op=fgoKernel.Operation([((1,0,2,0),20)],wait=False)
        with patch.object(fgoKernel,'goto',side_effect=nav.ScriptStop('Navigation failed')):
            with self.assertRaises(nav.ScriptStop):op()
        self.assertEqual(op,[((1,0,2,0),20)])
    def test_goto_success_precedes_battle_phase(self):
        events=[];op=fgoKernel.Operation([((1,0,2,0),1)],wait=False)
        with patch.object(fgoKernel,'goto',side_effect=lambda target:events.append(('goto',target))),patch.object(fgoKernel.Main,'__call__',side_effect=lambda *args:events.append(('main',args))):op()
        self.assertEqual(events[0],('goto',(1,0,2,0)));self.assertEqual(events[1][0],'main')
        self.assertEqual(op,[((1,0,2,0),1)])
    def test_queue_navigation_only_keeps_order_and_times(self):
        from types import SimpleNamespace
        queue=[fgoGuiOperation.QuestTask.metadata((1,0,7,0),20),fgoGuiOperation.QuestTask.metadata((1,0,2,0),20)];before=queue[:];messages=[]
        op=fgoGuiOperation.GuiQueueOperation(queue,SimpleNamespace(),navigationOnly=True,onNavigation=messages.append)
        with patch.object(fgoKernel,'goto',return_value={'type':'FreeQuestReady'}) as goto,patch.object(fgoKernel,'Main') as main:
            op();goto.assert_called_once_with((1,0,7,0));main.assert_not_called()
        self.assertEqual(queue,before);self.assertIn('1/2 冬木 → 变动坐标点0号',messages[0]);self.assertIn('20场',messages[0])
    def test_gui_has_thread_safe_navigation_signal(self):
        source=(APP/'fgoGui.py').read_text(encoding='utf-8')
        self.assertIn('signalNavigation=Signal(str)',source);self.assertIn('onNavigation=self.signalNavigation.emit',source)
    def test_legacy_special_maps_cn_stop_before_input(self):
        with patch.object(nav.XDetect,'region','CN'),patch.object(nav.fgoDevice.device,'touch') as touch:
            for route in (fgoReishift.Mictlan((3,7,0),0,(800,500)),fgoReishift.OrdaelCall((5,0,0),0)):
                with self.assertRaisesRegex(nav.ScriptStop,'unverified'):route()
            touch.assert_not_called()
    def test_legacy_reishift_has_no_visual_while(self):
        tree=ast.parse((APP/'fgoReishift.py').read_text(encoding='utf-8'))
        self.assertFalse(any(isinstance(node,ast.While) for node in ast.walk(tree)))
    def test_unverified_cn_mutation_helpers_stop_before_touch(self):
        with patch.object(nav.XDetect,'region','CN'),patch.object(nav.fgoDevice.device,'touch') as touch:
            for func in (fgoKernel.fpSummon,fgoKernel.mail,fgoKernel.synthesis,fgoKernel.lottery,fgoKernel.dailyFpSummon,fgoKernel.dailyStorySummon,fgoKernel.summonHistory):
                with self.assertRaisesRegex(nav.ScriptStop,'禁止自动执行'):func()
            touch.assert_not_called()
    def test_weekly_is_guarded(self):
        tree=ast.parse((APP/'fgoKernel.py').read_text(encoding='utf-8'))
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_weeklyMissionDetailed')
        self.assertFalse(any(isinstance(n,ast.While) for n in ast.walk(node)))
        source=ast.get_source_segment((APP/'fgoKernel.py').read_text(encoding='utf-8'),node)
        self.assertIn('NavigationGuard',source);self.assertIn('guard.progress',source)
    def test_cn_weekly_current_brackets_and_unquoted_task(self):
        from fgoDetect import XDetectCN
        with patch.object(XDetectCN.ocr,'ocrArea',return_value=['击败3个持有「中立」属性的敌人','目标进行度','3/3','已完成','完成本周所有的御主任务','目标进行度','2/6','击败15个持有『秩序』属性的敌人','5/15']),patch.object(XDetectCN,'_weeklyMission',numpy.zeros((1,1,3),numpy.uint8),create=True):
            result=XDetectCN.saveWeeklyMissionDetailed()
        self.assertEqual(len(result['tasks']),3)
        self.assertEqual(result['tasks'][0],(['中立'],True,0))
        self.assertEqual(result['tasks'][1][2],4)
        self.assertEqual(result['tasks'][2],(['秩序'],True,10))
    def test_cn_weekly_invalid_progress_is_not_generated(self):
        from fgoDetect import XDetectCN
        with patch.object(XDetectCN.ocr,'ocrArea',return_value=['击败持有「秩序」属性的敌人','15/5']),patch.object(XDetectCN,'_weeklyMission',numpy.zeros((1,1,3),numpy.uint8),create=True):result=XDetectCN.saveWeeklyMissionDetailed()
        self.assertEqual(result['tasks'],[]);self.assertEqual(result['malformed'],1)
    def test_weekly_incomplete_inventory_never_generates_queue(self):
        import fgoQuickQuest
        guard=nav.NavigationGuard('weekly');frame=Frame()
        with patch.object(nav,'Detect',return_value=frame),patch.object(nav,'classify',return_value='WEEKLY'),patch.object(nav,'_thumbAt',return_value=(263,664)),patch.object(nav,'weeklyRowsAt',return_value=[]),patch.object(nav.OCR.EN,'ocr_single_line',return_value=('1/7',.99)),patch.object(fgoQuickQuest,'_menuSwipe'),patch.object(nav.schedule,'sleep'):
            with self.assertRaisesRegex(nav.ScriptStop,'count mismatch'):nav.readWeeklyRowsCN(guard)
    def test_weekly_key_keeps_material_identity(self):
        self.assertEqual(nav._weeklyKey('活动甲中重新累计获得战利品【汤豆腐】50个'),nav._weeklyKey('活动乙中重新累计获得利品『汤豆腐』50个'))
        self.assertNotEqual(nav._weeklyKey('重新累计获得战利品【汤豆腐】50个'),nav._weeklyKey('重新累计获得战利品【散寿司】50个'))
    def test_weekly_key_ignores_only_fixed_exclusion_annotation(self):
        self.assertEqual(nav._weeklyKey('击败15个持有「人」之力的敌人（战斗中被召唤出来成的敌人除外）'),nav._weeklyKey('击败15个持有「人」之力的敌人（战斗中被召唤出来的敌人除外）'))
        self.assertNotEqual(nav._weeklyKey('击败15个持有「人」之力的敌人'),nav._weeklyKey('击败15个持有「天」之力的敌人'))
    def test_friend_refresh_and_scroll_bounded(self):
        source=(APP/'fgoKernel.py').read_text(encoding='utf-8');tree=ast.parse(source)
        main=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Main');method=next(n for n in main.body if isinstance(n,ast.FunctionDef) and n.name=='chooseFriend')
        self.assertFalse(any(isinstance(n,ast.While) for n in ast.walk(method)))
        text=ast.get_source_segment(source,method);self.assertIn('maxRefresh',text);self.assertIn('scrollGuard.progress',text)
    def test_daily_scanner_remains_deadline_guarded(self):
        import fgoQuickQuest
        source=(APP/'fgoQuickQuest.py').read_text(encoding='utf-8');tree=ast.parse(source)
        for method in ('scanDailyQuestsCN','gotoDailyEntry','_scrollToTop'):
            node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==method)
            self.assertTrue(all('deadline' in ast.unparse(n.test) for n in ast.walk(node) if isinstance(n,ast.While)))
        self.assertEqual(fgoQuickQuest.DAILY_SCROLL_TIMEOUT,180)

if __name__=='__main__':unittest.main()

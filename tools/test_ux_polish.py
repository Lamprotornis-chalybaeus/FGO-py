"""Offline safety, exact progress, drop observability and local template regressions."""
import sys,os,time,tempfile,json,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import cv2,numpy as np
APP=Path(__file__).resolve().parents[1]/'FGO-py';sys.path.insert(0,str(APP));os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
old=os.getcwd();os.chdir(APP)
try:
    import fgoKernel as kernel,fgoGuiOperation as queueModule,fgoDrop as drop
    from fgoProgress import BattleCompleted,formatProgress
    from fgoFriendTemplates import FriendTemplateStore,chooseOnScreen
finally:os.chdir(old)

class SimulatedRunner:
    stopAt=None;outcomes=None
    def __init__(self,data,**kwargs):
        self.times=data[0][1];self.callback=kwargs['onProgress'];self.appleTotal=kwargs['appleTotal'];self.count=0;self.defeats=0
    @property
    def result(self):return dict(battle=self.count,completedAttempts=self.count,defeated=self.defeats,turnPerBattle=3,timePerBattle=12,material={'EvilBone':self.count-self.defeats},dropStats={'occupied_slots':self.count*2,'recognized_slots':self.count,'unknown_slots':self.count},unknownDrops=[{'slot':2}]*self.count)
    def __call__(self):
        for i in range(self.times):
            won=self.outcomes[i] if self.outcomes else True;self.count+=1;self.defeats+=not won
            self.callback(BattleCompleted(self.count,self.count,self.defeats,3,12,won,self.result,dict(material={'EvilBone':1} if won else {},dropStats={'unknown_slots':1})))
            if self.stopAt and self.count>=self.stopAt:raise kernel.ScriptStop('test safe stop')

class ProgressTests(unittest.TestCase):
    def setUp(self):SimulatedRunner.stopAt=None;SimulatedRunner.outcomes=None
    def settings(self):return SimpleNamespace(appleTotal=0,appleKind=0,friendPolicy='first',friendMaxRefresh=0,wait=True)
    def runQueue(self,counts,limit=40):
        q=[queueModule.QuestTask.metadata((1,0,i,0),n) for i,n in enumerate(counts)];events=[]
        run=queueModule.GuiQueueOperation(q,self.settings(),onProgress=events.append,runLimit=limit)
        with patch.object(kernel,'Operation',SimulatedRunner):
            try:run()
            except kernel.ScriptStop:pass
        return q,events,run
    def test_each_completed_attempt_immediately_updates(self):
        q,events,_=self.runQueue([20]);self.assertEqual([e.task_attempted for e in events if e.battle],list(range(1,21)));self.assertEqual(q,[])
    def test_twenty_plan_remains_thirteen_after_seven(self):
        SimulatedRunner.stopAt=7;q,events,_=self.runQueue([20,20]);p=events[-1]
        self.assertEqual((q[0].repetitions,q[1].repetitions),(13,20));self.assertEqual((p.task_remaining,p.run_remaining,p.queue_remaining),(13,33,33))
    def test_global_ten_is_distinct_from_queue_forty(self):
        SimulatedRunner.stopAt=7;_,events,_=self.runQueue([20,20],10);self.assertEqual((events[-1].run_remaining,events[-1].queue_remaining),(3,33))
    def test_limit_zero_displays_unlimited(self):
        _,events,_=self.runQueue([1],0);self.assertIsNone(events[-1].run_remaining);self.assertIn('/不限',formatProgress(events[-1]))
    def test_multiple_tasks_keep_run_count(self):
        _,events,run=self.runQueue([2,3],10);p=events[-1];self.assertEqual((p.task_index,p.task_count,p.task_attempted,p.run_attempted,p.queue_remaining),(2,2,3,5,0));self.assertEqual(run.result['material']['EvilBone'],5)
    def test_defeat_is_attempt_and_separate_from_win(self):
        SimulatedRunner.outcomes=[True,False];_,events,_=self.runQueue([2]);self.assertEqual((events[-1].run_attempted,events[-1].wins,events[-1].defeats),(2,1,1))
    def test_restart_uses_remaining_plan(self):
        SimulatedRunner.stopAt=7;q,_,_=self.runQueue([20]);SimulatedRunner.stopAt=None;events=[]
        with patch.object(kernel,'Operation',SimulatedRunner):queueModule.GuiQueueOperation(q,self.settings(),onProgress=events.append)()
        self.assertEqual(events[-1].task_planned,13);self.assertEqual(q,[])
    def test_started_but_not_completed_keeps_plan(self):
        class Interrupted(SimulatedRunner):
            @property
            def result(self):return super().result|dict(battle=1,completedAttempts=0)
            def __call__(self):raise kernel.ScriptStop('interrupted before result')
        q=[queueModule.QuestTask.metadata((1,0,2,0),20)]
        with patch.object(kernel,'Operation',Interrupted):
            with self.assertRaises(kernel.ScriptStop):queueModule.GuiQueueOperation(q,self.settings())()
        self.assertEqual(q[0].repetitions,20)
    def test_drop_totals_not_double_counted(self):
        _,_,run=self.runQueue([2,3]);self.assertEqual((run.result['dropStats']['occupied_slots'],run.result['dropStats']['unknown_slots']),(10,5));self.assertEqual(len(run.result['unknownDrops']),5)
    def test_worker_owns_queue_mutation(self):
        ids=[];q=[queueModule.QuestTask.metadata((1,0,2,0),2)];run=queueModule.GuiQueueOperation(q,self.settings(),onProgress=lambda p:ids.append(threading.get_ident()))
        with patch.object(kernel,'Operation',SimulatedRunner):
            t=threading.Thread(target=run);t.start();t.join(5);self.assertFalse(t.is_alive())
        self.assertTrue(ids);self.assertTrue(all(i==t.ident for i in ids))
    def test_kernel_event_precedes_stop_later_and_follows_result_input(self):
        order=[]
        class Frame:
            def isMainInterface(self):return False
            def isBattleContinue(self):return False
            def isSkillCastFailed(self):return False
            def isTurnBegin(self):return True
        class FakeBattle:
            turn=3
            def __call__(self):order.append('battle');return True
            @property
            def result(self):return dict(turn=3,time=12,material={})
        def detect(*args):kernel.Detect.cache=frame;return frame
        frame=Frame();run=kernel.Main(battleClass=FakeBattle,onProgress=lambda e:order.append('progress'))
        with patch.object(kernel,'Detect',side_effect=detect),patch.object(kernel.fgoDevice.device,'perform',side_effect=lambda *a:order.append('result inputs')),patch.object(kernel.schedule,'checkStopLater',side_effect=kernel.ScriptStop('limit')):
            with self.assertRaises(kernel.ScriptStop):run()
        self.assertEqual(order,['battle','result inputs','progress']);self.assertEqual(run.completedAttempts,1)

class DropTests(unittest.TestCase):
    def image(self,slots):
        im=np.full((720,1280,3),5,np.uint8)
        for i in slots:
            x,y,r,b=drop.slotRect(i);im[y:b,x:r]=130
        return im
    def test_unrecognized_occupied_slots_remain_unknown(self):
        r=drop.detect(self.image([0,1,2]),[],False);self.assertEqual((r.occupied_slots,r.recognized_slots,r.unknown_slots),(3,0,3));self.assertEqual(len(r.unknown_crops),3)
    def test_empty_slots_are_not_invented(self):self.assertEqual(drop.detect(self.image([]),[],False).occupied_slots,0)
    def test_first_slot_is_observed_as_currency_separately(self):
        from fgoDetect import OCR
        im=self.image([0]);x,y,r,b=drop.slotRect(0,True)
        with patch.object(OCR.EN,'ocr_single_line',return_value=('+7,400',.95)):result=drop.detect(im,[('QP',im[y:b,x:r].copy(),'currency')],False)
        self.assertEqual(result.recognized,{});self.assertEqual(result.currency,{'QP':7400});self.assertEqual(result.recognized_slots,1)
    def test_ambiguous_match_stays_unknown(self):
        im=self.image([1]);x,y,r,b=drop.slotRect(1,True);icon=im[y:b,x:r].copy();result=drop.detect(im,[('A',icon,'material'),('B',icon,'material')],False);self.assertEqual(result.unknown_slots,1)
    def test_recognized_and_unknown_sum_to_occupied(self):
        im=self.image([1,2]);x,y,r,b=drop.slotRect(1,True);result=drop.detect(im,[('A',im[y:b,x:r].copy(),'material')],False);self.assertEqual(result.occupied_slots,result.recognized_slots+result.unknown_slots)
    def test_debug_off_creates_no_files(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(drop,'debugRoot',Path(directory)):drop.detect(self.image([1]),[],False);self.assertEqual(list(Path(directory).iterdir()),[])
    def test_debug_saves_all_slots_and_detection(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(drop,'debugRoot',Path(directory)):
            r=drop.detect(self.image([1]),[],True);folder=Path(r.debug_dir);self.assertTrue((folder/'result.png').exists());self.assertEqual(len(list(folder.glob('slot-*.png'))),21);self.assertEqual(json.loads((folder/'detection.json').read_text())['unknown_slots'],1)
    def test_incomplete_analysis_remains_visible(self):self.assertTrue(drop.mergeStats({},dict(incomplete=True,errors=['failed']))['incomplete'])

class FriendTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.store=FriendTemplateStore(self.temp.name);self.a=self.store.add(np.full((20,20,3),100,np.uint8),'A');self.b=self.store.add(np.full((20,20,3),150,np.uint8),'B')
    def tearDown(self):self.temp.cleanup()
    def test_explicit_priority_over_filename_order(self):
        rows=self.store.entries()
        for r in rows:r['priority']=1 if r['file']==self.b else 2
        self.store.save(rows);self.store.flush();self.assertEqual(self.store.orderedItems()[0][0],self.b)
    def test_disabled_template_not_matched(self):
        rows=self.store.entries()
        for r in rows:
            if r['file']==self.a:r['enabled']=False
        self.store.save(rows);self.store.flush();self.assertNotIn(self.a,dict(self.store.items()))
    def test_same_screen_uses_highest_priority(self):
        self.store.flush();first=self.store.orderedItems()[0][0];d=SimpleNamespace(findFriend=lambda image:(500,200));self.assertEqual(chooseOnScreen(d,self.store)[0],first)
    def test_private_templates_are_git_ignored(self):
        import subprocess
        repo=APP.parent
        for file in ('FGO-py/fgoImage/friend/local/private.png','FGO-py/fgoImage/friend/templates.json','FGO-py/fgoImage/drop/local/private.png'):
            self.assertEqual(subprocess.run(['git','-c',f'safe.directory={repo.as_posix()}','check-ignore','-q',file],cwd=repo).returncode,0)
    def test_empty_name_is_rejected(self):
        with self.assertRaises(ValueError):self.store.add(np.ones((20,20,3),np.uint8),' ')

class FriendFlowTests(unittest.TestCase):
    def invoke(self,policy,limit,matched=False):
        from unittest.mock import Mock
        frame=SimpleNamespace(isChooseFriend=lambda:True,isBattleFormation=lambda:False,isNoFriend=lambda:False,
            isFriendListEnd=lambda:True,findFriend=lambda image:(500,220) if matched else None)
        store=Mock();store.flush.return_value=True;store.orderedItems.return_value=[('confirmed',object())]
        def detect(*args):kernel.Detect.cache=frame;return frame
        run=kernel.Main(friendPolicy=policy,friendMaxRefresh=limit)
        with patch.object(kernel,'friendImg',store),patch.object(kernel,'Detect',side_effect=detect),patch.object(kernel.fgoDevice.device,'press') as press,patch.object(kernel.fgoDevice.device,'perform') as perform,patch.object(kernel.fgoDevice.device,'touch') as touch,patch.object(kernel.schedule,'sleep'):
            try:result=run.chooseFriend();error=None
            except kernel.ScriptStop as e:result=None;error=str(e)
        return result,error,press,perform,touch,store
    def test_refresh_zero_still_checks_matching_template(self):
        result,error,press,refresh,touch,store=self.invoke('prefer',0,True)
        self.assertEqual(result,'confirmed');self.assertIsNone(error);refresh.assert_not_called();press.assert_not_called();touch.assert_called_once_with((500,220));store.orderedItems.assert_called()
    def test_prefer_fallback_only_after_current_list_scan(self):
        _,error,press,refresh,_,store=self.invoke('prefer',0)
        self.assertIsNone(error);store.orderedItems.assert_called();press.assert_called_once_with('8');refresh.assert_not_called()
    def test_strict_stops_after_scan_with_zero_refresh(self):
        _,error,press,refresh,_,store=self.invoke('strict',0)
        self.assertIn('未找到符合模板的助战',error);store.orderedItems.assert_called();press.assert_not_called();refresh.assert_not_called()
    def test_refresh_budget_two_is_bounded(self):
        _,error,press,refresh,_,_=self.invoke('strict',2)
        self.assertIn('刷新 2 次',error);self.assertEqual(refresh.call_count,2);press.assert_not_called()

class AdditionalTests(unittest.TestCase):
    def test_observed_stop_defeat_does_not_corrupt_upstream_averages(self):
        class StoppedRunner(SimulatedRunner):
            outcomes=[True]*9+[False];stopAt=None
            @property
            def result(self):
                original=super().result
                return original|dict(defeated=0,progressDefeats=self.defeats,turnPerBattle=3*(self.count-self.defeats)/self.count if self.count else 0,timePerBattle=12*(self.count-self.defeats)/self.count if self.count else 0)
        q=[queueModule.QuestTask.metadata((1,0,2,0),10)];run=queueModule.GuiQueueOperation(q,ProgressTests().settings())
        with patch.object(kernel,'Operation',StoppedRunner):run()
        self.assertEqual((run.result['battle'],run.result['defeated']),(10,1));self.assertAlmostEqual(run.result['turnPerBattle'],3);self.assertAlmostEqual(run.result['timePerBattle'],12)
    def test_cn_friend_header_fallback_requires_all_three_controls(self):
        from fgoDetect import XDetectCN,XDetectBase,OCR
        frame=object.__new__(XDetectCN);frame.im=np.zeros((720,1280,3),np.uint8)
        with patch.object(XDetectBase,'isChooseFriend',return_value=False),patch.object(OCR.ZHS,'ocr_single_line',side_effect=[('助战选择',.97),('返回',.95),('列表更新',.94)]):self.assertTrue(frame.isChooseFriend())
    def test_cn_friend_fallback_rejects_formation_and_low_confidence(self):
        from fgoDetect import XDetectCN,XDetectBase,OCR
        frame=object.__new__(XDetectCN);frame.im=np.zeros((720,1280,3),np.uint8)
        for read in [('队伍确认',.99),('助战选择',.6)]:
            with patch.object(XDetectBase,'isChooseFriend',return_value=False),patch.object(OCR.ZHS,'ocr_single_line',return_value=read):self.assertFalse(frame.isChooseFriend())
    def test_gui_event_updates_queue_without_timer_guessing(self):
        from PySide6.QtWidgets import QApplication
        from fgoGui import MainWindow
        from fgoConfig import Config
        from fgoProgress import BattleProgress
        app=QApplication.instance() or QApplication([]);old=os.getcwd();os.chdir(APP)
        try:
            with patch.object(MainWindow,'initializeDevice'),patch('threading.Thread.start'):w=MainWindow(Config())
            actual=[queueModule.QuestTask.metadata((1,0,2,0),20)];w.operation.extend(actual)
            event=BattleProgress(1,1,'冬木 → X-C',20,7,13,7,40,33,13,7,0,(queueModule.QuestTask.metadata((1,0,2,0),13),))
            with patch.object(w.worker,'is_alive',return_value=True):
                w.signalProgress.emit(event)
                self.assertIn('13×',w.LST_QUEST.item(0).text());self.assertEqual(w.operation[0].repetitions,20)
                self.assertFalse(w.timer.isActive())
            w.close()
        finally:os.chdir(old)
    def test_drop_debug_write_failure_does_not_erase_unknown(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(drop,'debugRoot',Path(directory)),patch.object(drop.cv2,'imwrite',return_value=False):
            result=drop.detect(DropTests().image([1]),[],True)
        self.assertEqual(result.unknown_slots,1);self.assertTrue(result.errors)
    def test_immediate_defeat_stop_records_outcome_without_revive(self):
        events=[]
        class Frame:
            def isMainInterface(self):return False
            def isBattleContinue(self):return False
            def isSkillCastFailed(self):return False
            def isTurnBegin(self):return True
        class Lost:
            defeated=False
            def __call__(self):self.defeated=True;raise kernel.ScriptStop('Battle Defeated')
            @property
            def result(self):return dict(turn=12,time=100,material={})
        frame=Frame()
        def detect(*args):kernel.Detect.cache=frame;return frame
        run=kernel.Main(battleClass=Lost,onProgress=events.append)
        with patch.object(kernel,'Detect',side_effect=detect),patch.object(kernel.fgoDevice.device,'perform') as inputs:
            with self.assertRaisesRegex(kernel.ScriptStop,'Battle Defeated'):run()
            inputs.assert_not_called()
        self.assertEqual((run.battleCount,run.defeated),(1,0)) # Original engine counters stay intact.
        self.assertEqual((events[0].completed,events[0].defeats,events[0].won),(1,1,False))
        self.assertEqual((run.result['progressWins'],run.result['progressDefeats']),(0,1))
    def test_retained_kernel_event_is_not_changed_by_later_stats(self):
        events=[];run=kernel.Main(onProgress=events.append);run.prepare();run.completedAttempts=1;run.battleCount=1
        run.dropStats={'unknown_slots':1,'debug_dirs':['first']}
        result=dict(turn=3,time=12,material={},dropStats={'unknown_slots':1})
        run.emitCompleted(True,result);run.dropStats['debug_dirs'].append('second');result['dropStats']['unknown_slots']=5
        self.assertEqual(events[0].result['dropStats']['debug_dirs'],['first']);self.assertEqual(events[0].battle_result['dropStats']['unknown_slots'],1)
    def test_current_progress_distinguishes_run_limit(self):
        from fgoProgress import currentProgress
        p=currentProgress(BattleCompleted(7,7,1,3,12,True,{}),10)
        self.assertEqual((p.run_remaining,p.wins,p.defeats),(3,6,1));self.assertIsNone(p.task_remaining)
    def test_currency_uncertain_amount_is_disclosed(self):
        from fgoDetect import OCR
        im=DropTests().image([0]);x,y,r,b=drop.slotRect(0,True)
        with patch.object(OCR.EN,'ocr_single_line',return_value=('?',.4)):result=drop.detect(im,[('QP',im[y:b,x:r].copy(),'currency')],False)
        self.assertEqual(result.currency,{});self.assertEqual(result.stats['currency_amount_unknown'],1)
    def test_navigation_does_not_restore_initial_remaining(self):
        from PySide6.QtWidgets import QApplication
        from fgoGui import MainWindow
        from fgoConfig import Config
        from fgoProgress import BattleProgress
        app=QApplication.instance() or QApplication([])
        old=os.getcwd();os.chdir(APP)
        try:
            with patch.object(MainWindow,'initializeDevice'),patch('threading.Thread.start'):w=MainWindow(Config())
            p=BattleProgress(1,2,'冬木 → X-C',20,7,13,7,10,3,33,7,0)
            w.showProgress(p);w.showNavigation('初始计划20场\n正在选择助战')
            self.assertIn('剩 13',w.LBL_WEEKLY_STATUS.text());self.assertIn('队列剩 33',w.LBL_WEEKLY_STATUS.text());w.close()
        finally:os.chdir(old)

class LayoutTests(unittest.TestCase):
    def test_progress_log_includes_currency_and_unknown_not_empty_material(self):
        from PySide6.QtWidgets import QApplication,QSystemTrayIcon
        from fgoGui import MainWindow
        from fgoConfig import Config
        from fgoProgress import BattleProgress
        app=QApplication.instance() or QApplication([]);old=os.getcwd();os.chdir(APP)
        try:
            with patch.object(MainWindow,'initializeDevice'),patch('threading.Thread.start'):w=MainWindow(Config())
            result=dict(material={},dropStats=dict(currency={'QP':780},unknown_slots=2,currency_amount_unknown=1))
            b=BattleCompleted(1,1,0,3,12,True,result,result)
            p=BattleProgress(1,1,'冬木 → X-C',3,1,2,1,3,2,2,1,0,battle=b,result=result)
            w.showProgress(p);log=w.TXT_LOG.toPlainText()
            self.assertIn('本场：QP×780，未知格×2',log);self.assertIn('货币数量未确认×1',log)
            w.funcBegin();self.assertFalse(w.CBB_APPLE.isEnabled());self.assertFalse(w.CBB_QUICKMODE.isEnabled())
            from PySide6.QtWidgets import QSystemTrayIcon
            w.result=None
            w.funcEnd(('Done',QSystemTrayIcon.MessageIcon.Information));w.close()
        finally:os.chdir(old)
    def test_splitter_log_and_controls_fit_720p(self):
        from PySide6.QtWidgets import QApplication,QMainWindow,QPushButton
        from fgoGui import MainWindow
        from fgoConfig import Config
        app=QApplication.instance() or QApplication([])
        old=os.getcwd();os.chdir(APP)
        try:
            with patch.object(MainWindow,'initializeDevice'),patch('threading.Thread.start'):w=MainWindow(Config())
        finally:os.chdir(old)
        ui=w;w.resize(900,680);w.show();app.processEvents()
        self.assertGreaterEqual(ui.TXT_LOG.height(),200);self.assertEqual(ui.SPLIT_RUN.count(),2)
        controls=[ui.BTN_MAIN,ui.BTN_STOP,ui.BTN_QUESTADD,ui.BTN_QUESTCLEAR]
        for button in controls:self.assertFalse(button.geometry().isEmpty())
        from PySide6.QtCore import QPoint,QRect
        controls=w.findChildren(QPushButton)
        rectangles=[QRect(c.mapTo(w,QPoint(0,0)),c.size()) for c in controls if c.isVisible()]
        for i,a in enumerate(rectangles):
            for b in rectangles[i+1:]:self.assertFalse(a.intersects(b),'visible buttons overlap')
        logHeight=ui.TXT_LOG.height();w.resize(900,800);app.processEvents();self.assertGreaterEqual(ui.TXT_LOG.height()-logHeight,110)
        w.resize(900,680);app.processEvents()
        self.assertLessEqual(w.height(),680);w.close()
    def test_result_is_scrollable_and_discloses_unknown(self):
        from PySide6.QtWidgets import QApplication
        from fgoGuiResult import RunResultDialog
        app=QApplication.instance() or QApplication([]);dialog=RunResultDialog(dict(type='Main',battle=3,material={f'item{i}':i for i in range(50)},dropStats={'unknown_slots':3}));dialog.show();app.processEvents();self.assertEqual(dialog.table.rowCount(),50);self.assertIn('未识别项未计入',dialog.unknownLabel.text());self.assertFalse(dialog.debugButton.isVisible());self.assertGreater(dialog.table.verticalScrollBar().maximum(),0);dialog.close()

if __name__=='__main__':unittest.main()

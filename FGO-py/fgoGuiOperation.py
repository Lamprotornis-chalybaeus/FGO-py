from dataclasses import dataclass
import time
import fgoKernel
import fgoQuickQuest
import fgoNavigation
from fgoSchedule import schedule
from fgoProgress import BattleProgress

@dataclass(frozen=True)
class QuestTask:
    type:str
    target:object
    repetitions:int=1
    @classmethod
    def metadata(cls,quest,repetitions=1):return cls('metadata',tuple(quest),int(repetitions))
    @classmethod
    def daily(cls,entry,repetitions=1):return cls('daily',entry,int(repetitions))

class GuiQueueOperation:
    """GUI-only adapter; Kernel.Operation and CLI command forms remain numeric/metadata-only."""
    def __init__(self,queue,settings,battleClass=None,navigationOnly=False,onNavigation=None,onProgress=None,runLimit=0):
        self.queue=queue
        self.settings=settings
        self.battleClass=battleClass or fgoKernel.Battle
        self.navigationOnly=navigationOnly
        self.onNavigation=onNavigation
        self.onProgress=onProgress
        self.runLimit=max(0,int(runLimit))
        self._start=0
        self._battle=0
        self._defeated=0
        self._turns=0
        self._battleTime=0.0
    @property
    def result(self):
        successes=max(0,self._battle-self._defeated)
        return {'type':'Main','time':time.time()-self._start if self._start else 0,'battle':self._battle,'defeated':self._defeated,'turnPerBattle':self._turns/successes if successes else 0,'timePerBattle':self._battleTime/successes if successes else 0}
    def _record(self,runner):
        result=runner.result
        self._battle+=result.get('completedAttempts',result['battle']);self._defeated+=result.get('progressDefeats',result['defeated'])
        successes=max(0,result['battle']-result['defeated'])
        self._turns+=result['turnPerBattle']*successes
        self._battleTime+=result['timePerBattle']*successes
        self.settings.appleTotal=runner.appleTotal
    def __call__(self):
        self._start=time.time()
        self._battle=self._defeated=self._turns=0;self._battleTime=0
        total=len(self.queue);index=0
        while self.queue:
            index+=1
            task=self.queue[0]
            if isinstance(task,QuestTask):kind,target,times=task.type,task.target,task.repetitions
            else:
                target,times=task;kind='metadata'
            if kind not in ('daily','metadata'):raise fgoKernel.ScriptStop(f'未知 GUI 队列任务类型：{kind}')
            title=target.title if kind=='daily' else f'{fgoNavigation.questTitle(target[:2])} → {fgoNavigation.questTitle(target)}'
            context=f'当前任务：{index}/{total} {title}；剩余计划：{times}场'
            def notify(message):
                if self.onNavigation:self.onNavigation(f'{context}\n{message}')
            base=(self._battle,self._defeated,self._turns,self._battleTime)
            reported=0
            def progress(event):
                nonlocal reported
                reported=event.completed
                self._battle=base[0]+event.completed
                self._defeated=base[1]+event.defeats
                # Upstream averages use its original defeated counter. A
                # separately observed immediate-stop defeat must not change
                # the denominator used to reconstruct those totals.
                successes=max(0,event.result['battle']-event.result.get('defeated',event.defeats))
                self._turns=base[2]+event.result['turnPerBattle']*successes
                self._battleTime=base[3]+event.result['timePerBattle']*successes
                remaining=max(0,times-reported) if times else None
                if isinstance(task,QuestTask):self.queue[0]=QuestTask(task.type,task.target,remaining or 0)
                else:self.queue[0]=(task[0],remaining or 0)
                # Keep the zero row until the worker moves to the next task.
                future=[t.repetitions if isinstance(t,QuestTask) else t[1] for t in self.queue[1:]]
                queueLeft=None if remaining is None or any(not n for n in future) else remaining+sum(future)
                p=BattleProgress(index,total,title,times,reported,remaining,self._battle,self.runLimit,max(0,self.runLimit-self._battle) if self.runLimit else None,queueLeft,self._battle-self._defeated,self._defeated,tuple(self.queue),event,dict(self.result))
                if self.onProgress:self.onProgress(p)
            if self.onProgress:
                counts=[t.repetitions if isinstance(t,QuestTask) else t[1] for t in self.queue]
                self.onProgress(BattleProgress(index,total,title,times,0,times or None,self._battle,self.runLimit,max(0,self.runLimit-self._battle) if self.runLimit else None,sum(counts) if all(counts) else None,self._battle-self._defeated,self._defeated,tuple(self.queue),None,dict(self.result)))
            notify('正在开始导航…')
            if self.navigationOnly:
                with fgoNavigation.feedback(notify):
                    ready=fgoQuickQuest.gotoDailyEntry(target) if kind=='daily' else fgoKernel.goto(target)
                return ready
            if kind=='daily':
                with fgoNavigation.feedback(notify):fgoQuickQuest.gotoDailyEntry(target)
                runner=fgoKernel.Main(appleTotal=self.settings.appleTotal,appleKind=self.settings.appleKind,battleClass=self.battleClass,friendPolicy=self.settings.friendPolicy,friendMaxRefresh=self.settings.friendMaxRefresh,onProgress=progress)
                try:runner(0,times or None)
                finally:self._recordProgress(runner,task,times,reported)
            elif kind=='metadata':
                runner=fgoKernel.Operation([(tuple(target),times)],appleTotal=self.settings.appleTotal,appleKind=self.settings.appleKind,battleClass=self.battleClass,friendPolicy=self.settings.friendPolicy,friendMaxRefresh=self.settings.friendMaxRefresh,wait=False,onProgress=progress)
                try:
                    with fgoNavigation.feedback(notify):runner()
                finally:self._recordProgress(runner,task,times,reported)
            else:raise fgoKernel.ScriptStop(f'未知 GUI 队列任务类型：{kind}')
            # AP shortage or an early stop must not silently consume the rest of
            # this task or move on to another quest.
            if not times or runner.result['battle']<times:return self.result
        return self.result
    def _recordProgress(self,runner,task,times,reported=0):
        # Old mock/custom runners without events retain their legacy result path.
        count=runner.result.get('completedAttempts',runner.result['battle'])
        if not reported:self._record(runner)
        self.settings.appleTotal=runner.appleTotal
        remaining=max(0,times-count) if times else 0
        if times and not remaining:self.queue.pop(0)
        elif isinstance(task,QuestTask):self.queue[0]=QuestTask(task.type,task.target,remaining)
        else:self.queue[0]=(task[0],remaining)

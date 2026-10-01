from dataclasses import dataclass
import time
import fgoKernel
import fgoQuickQuest
from fgoSchedule import schedule

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
    def __init__(self,queue,settings,battleClass=None):
        self.queue=queue
        self.settings=settings
        self.battleClass=battleClass or fgoKernel.Battle
        self._start=0
        self._battle=0
        self._defeated=0
        self._turns=0
        self._battleTime=0.0
        self._material={}
    @property
    def result(self):
        successes=max(0,self._battle-self._defeated)
        return {'type':'Main','time':time.time()-self._start if self._start else 0,'battle':self._battle,'defeated':self._defeated,'turnPerBattle':self._turns/successes if successes else 0,'timePerBattle':self._battleTime/successes if successes else 0,'material':dict(self._material)}
    def _record(self,runner):
        result=runner.result
        self._battle+=result['battle'];self._defeated+=result['defeated']
        successes=max(0,result['battle']-result['defeated'])
        self._turns+=result['turnPerBattle']*successes
        self._battleTime+=result['timePerBattle']*successes
        for name,count in result['material'].items():self._material[name]=self._material.get(name,0)+count
        self.settings.appleTotal=runner.appleTotal
    def __call__(self):
        self._start=time.time()
        self._battle=self._defeated=self._turns=0;self._battleTime=0;self._material={}
        while self.queue:
            task=self.queue.pop(0)
            if isinstance(task,QuestTask):kind,target,times=task.type,task.target,task.repetitions
            else:
                target,times=task;kind='metadata'
            if kind=='daily':
                fgoQuickQuest.gotoDailyEntry(target)
                runner=fgoKernel.Main(appleTotal=self.settings.appleTotal,appleKind=self.settings.appleKind,battleClass=self.battleClass,friendPolicy=self.settings.friendPolicy,friendMaxRefresh=self.settings.friendMaxRefresh)
                try:runner(0,times or None)
                finally:self._record(runner)
            elif kind=='metadata':
                runner=fgoKernel.Operation([(tuple(target),times)],appleTotal=self.settings.appleTotal,appleKind=self.settings.appleKind,battleClass=self.battleClass,friendPolicy=self.settings.friendPolicy,friendMaxRefresh=self.settings.friendMaxRefresh,wait=self.settings.wait)
                try:runner()
                finally:self._record(runner)
            else:raise fgoKernel.ScriptStop(f'未知 GUI 队列任务类型：{kind}')
        return self.result

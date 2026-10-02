"""Plain Python events. Emitted after result processing, never from a timer."""
from dataclasses import dataclass,field
from copy import deepcopy

@dataclass(frozen=True)
class BattleCompleted:
    completed:int
    attempted:int
    defeats:int
    turns:int
    seconds:float
    won:bool
    result:dict=field(default_factory=dict)
    battle_result:dict=field(default_factory=dict)

@dataclass(frozen=True)
class BattleProgress:
    task_index:int
    task_count:int
    task_name:str
    task_planned:int
    task_attempted:int
    task_remaining:object
    run_attempted:int
    run_limit:int
    run_remaining:object
    queue_remaining:object
    wins:int
    defeats:int
    queue:tuple=()
    battle:object=None
    result:dict=field(default_factory=dict)

def formatProgress(p):
    left=lambda n:'不限' if n is None else str(n)
    return (f'任务 {p.task_index}/{p.task_count}：{p.task_name}\n'
            f'本项 {p.task_attempted}/{p.task_planned or "不限"}，剩 {left(p.task_remaining)}\n'
            f'本次 {p.run_attempted}/{p.run_limit or "不限"}，剩 {left(p.run_remaining)}；队列剩 {left(p.queue_remaining)}\n'
            f'胜 {p.wins} / 负 {p.defeats}')

def currentProgress(event,limit=0):
    """Adapt current-quest farming without reading Qt controls in the worker."""
    limit=max(0,int(limit))
    return BattleProgress(1,1,'当前关卡',0,event.completed,None,event.completed,limit,
        max(0,limit-event.completed) if limit else None,None,event.completed-event.defeats,
        event.defeats,(),event,deepcopy(event.result))

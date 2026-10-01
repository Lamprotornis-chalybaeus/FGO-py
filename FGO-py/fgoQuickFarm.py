MODES=('current','daily','plan')

def modeIndex(mode):
    try:return MODES.index(mode)
    except ValueError:return 0

def modeName(index):return MODES[index] if 0<=index<len(MODES) else MODES[0]

def applyBattleLimit(schedule,limit):
    limit=max(0,int(limit))
    if limit:schedule.stopLater(limit)
    else:schedule.stopLater()

def appendWeeklyQuests(operation,report):
    quests=list(report.get('quests',()))
    operation.extend(quests)
    return len(quests)

def weeklyMissionFeedback(report):
    recognized=int(report.get('recognized',0))
    completed=int(report.get('completed',0))
    supported=int(report.get('supported',0))
    unsupported=int(report.get('unsupported',0))
    entries=int(report.get('entries',len(report.get('quests',()))))
    ap=int(report.get('expectedAp',0))
    if report.get('recognitionError') or recognized==0 and completed==0:
        return '未能正确识别每周任务，请查看诊断日志。'
    if entries==0 and supported==0 and unsupported:
        return f'存在任务，但这些任务类型暂不受 FGO-py 自动每周任务支持。识别到 {recognized} 条，已完成 {completed} 条，不支持 {unsupported} 条。'
    if entries==0 and supported==0:
        return f'当前没有需要处理的受支持每周任务。识别到 {recognized} 条，已完成 {completed} 条。'
    return f'读取到 {recognized} 条每周任务\n已完成：{completed}\n可自动求解：{supported}\n暂不支持：{unsupported}\n已向计划关卡队列加入 {entries} 项\n预计 AP：{ap}'

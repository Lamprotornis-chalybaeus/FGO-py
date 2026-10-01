import fgoDevice
from fgoDetect import Detect,XDetect
from fgoSchedule import ScriptStop,schedule

def _open_chapter(chapter):
    for _ in range(30):
        detect=Detect(.4)
        if detect.isMainInterface():break
    else:
        raise ScriptStop('等待关卡导航界面超时')
    for _ in range(10):
        detect=Detect(.4)
        if detect.isQuestListBegin():break
        fgoDevice.device.swipe((1000,200),(1000,600))
    else:
        raise ScriptStop('无法确认章节列表起始位置，已停止每日任务导航')
    for _ in range(20):
        detect=Detect(.4)
        if pos:=detect.findChapter(chapter):
            fgoDevice.device.touch(pos)
            schedule.sleep(.8)
            return
        fgoDevice.device.swipe((1000,600),(1000,200))
    raise ScriptStop(f'章节模板 {chapter} 搜索超限，已停止每日任务导航')

def openDailyPageCN():
    """Open the CN daily-quest list without selecting or starting a battle."""
    if XDetect.region!='CN':
        raise ScriptStop('每日任务快捷入口仅适配简体中文服务器')
    if not Detect(0,1).isMainInterface():
        raise ScriptStop('请先将游戏返回主界面，再打开每日任务页')
    # Upstream metadata templates 0 and 0-0 identify the Chaldea Gate and
    # Daily Quest cards; search is bounded and stops on an unexpected screen.
    _open_chapter((0,))
    _open_chapter((0,0))
    return {'type':'DailyPage'}

from fgoDetect import Detect,XDetect
from fgoReishift import reishift
from fgoSchedule import ScriptStop

def openDailyPageCN():
    """Open the CN daily-quest list without selecting or starting a battle."""
    if XDetect.region!='CN':
        raise ScriptStop('每日任务快捷入口仅适配简体中文服务器')
    if not Detect(0,1).isMainInterface():
        raise ScriptStop('请先将游戏返回主界面，再打开每日任务页')
    # Existing metadata templates (0 and 0-0) identify the Chaldea Gate and
    # its Daily Quest card. This intentionally stops at the quest list.
    reishift((0,0))
    return {'type':'DailyPage'}

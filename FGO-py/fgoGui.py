import os,sys,time,platform,logging,subprocess
from threading import Thread
from PySide6.QtCore import Qt,QLocale,QTranslator,QTimer,Signal,QSignalBlocker,QByteArray
from PySide6.QtGui import QAction,QIcon
from PySide6.QtWidgets import QApplication,QInputDialog,QMainWindow,QMenu,QMessageBox,QSystemTrayIcon,QSpinBox,QComboBox,QCheckBox
from matplotlib import pyplot
from fgoProgress import formatProgress,currentProgress
from fgoGuiResult import RunResultDialog
from fgoPaths import licenseFile
from fgoGuiFriendTemplates import FriendTemplateDialog
import fgoDevice
import fgoKernel
import fgoQuickFarm,fgoQuickQuest,fgoFriendPolicy,fgoEventProgress,fgoGuiOperation
from fgoMainWindow import Ui_fgoMainWindow
from fgoGuiTeamup import Teamup
from fgoMetadata import quest
logger=fgoKernel.getLogger('Gui')
pyplot.ion()

class GuiLogHandler(logging.Handler):
    def __init__(self,send):super().__init__(logging.INFO);self.send=send;self.previous=None
    def emit(self,record):
        text=f'[{"导航" if record.name=="fgo.Navigation" else record.levelname}] {record.getMessage()}'
        if text!=self.previous:
            self.previous=text
            try:self.send(text)
            except RuntimeError:logging.getLogger('fgo').removeHandler(self)

class MainWindow(QMainWindow,Ui_fgoMainWindow):
    COMPACT_SIZE=(850,580)
    GUI_LAYOUT_VERSION=2
    signalFuncBegin=Signal()
    signalFuncEnd=Signal(object)
    signalNavigation=Signal(str)
    signalProgress=Signal(object)
    signalLog=Signal(str)
    def __init__(self,config,parent=None):
        super().__init__(parent)
        self.color={
            Qt.ColorScheme.Light:lambda x:f'<font color="#{x:06X}">',
            Qt.ColorScheme.Dark:lambda x:f'<font color="#{x^0xFFFFFF:06X}">',
        }.get(QApplication.styleHints().colorScheme(),lambda _:'')
        self.setupUi(self)
        if platform.system()=='Darwin':self.setStyleSheet("QWidget{font-family:\"PingFang SC\";font-size:15px}")
        self.setWindowIcon(QIcon('fgoIcon.ico'))
        self.TRAY=QSystemTrayIcon(self)
        self.TRAY.setIcon(QIcon('fgoIcon.ico'))
        self.TRAY.setToolTip('FGO-py')
        self.MENU_TRAY=QMenu(self)
        self.MENU_TRAY_QUIT=QAction(self.tr('退出'),self.MENU_TRAY)
        self.MENU_TRAY.addAction(self.MENU_TRAY_QUIT)
        self.MENU_TRAY_FORCEQUIT=QAction(self.tr('强制退出'),self.MENU_TRAY)
        self.MENU_TRAY.addAction(self.MENU_TRAY_FORCEQUIT)
        self.TRAY.setContextMenu(self.MENU_TRAY)
        self.TRAY.show()
        self.TRAY.activated.connect(lambda reason:self.show()if reason==QSystemTrayIcon.ActivationReason.Trigger else None)
        self.MENU_TRAY_QUIT.triggered.connect(lambda:QApplication.quit()if self.askQuit()else None)
        self.MENU_TRAY_FORCEQUIT.triggered.connect(QApplication.quit)
        self.signalFuncBegin.connect(self.funcBegin)
        self.signalFuncEnd.connect(self.funcEnd)
        self.signalNavigation.connect(self.showNavigation)
        self.signalProgress.connect(self.showProgress)
        self.signalLog.connect(self.appendLog)
        self.SPLIT_RUN.setChildrenCollapsible(False)
        self.SPLIT_RUN.setStretchFactor(0,0);self.SPLIT_RUN.setStretchFactor(1,1)
        self.SPLIT_RUN.setSizes([350,170])
        self._queueSnapshot=()
        self._lastProgress=None
        self.LBL_WEEKLY_STATUS.setMaximumHeight(88)
        self._logHandler=GuiLogHandler(self.signalLog.emit)
        logging.getLogger('fgo').addHandler(self._logHandler)
        self.operation=fgoKernel.Operation()
        self.dailyEntries=[]
        self._dailyScanPending=False
        self.chapter=sorted({i[:2]for i in quest})
        self._chapterData=[fgoQuickQuest.DAILY_CATEGORY]
        with QSignalBlocker(self.CBB_CHAPTER):
            self.CBB_CHAPTER.addItem('每日任务',fgoQuickQuest.DAILY_CATEGORY)
            for chapter in self.chapter:
                self.CBB_CHAPTER.addItem(QApplication.translate('quest','-'.join(str(j)for j in chapter)),chapter)
                self._chapterData.append(chapter)
            if len(self._chapterData)>1:self.CBB_CHAPTER.setCurrentIndex(1)
        self.CBB_CHAPTER.currentIndexChanged.connect(self.chapterChanged)
        self.BTN_DAILY_REFRESH.clicked.connect(self.refreshDailyQuests)
        self.worker=Thread()
        self.config=config
        self.resize(*self.COMPACT_SIZE)
        self.compactWindowAction=QAction('紧凑窗口',self)
        self.compactWindowAction.setStatusTip('恢复紧凑窗口和日志分隔条；字体及系统显示缩放保持不变。')
        self.MENU_CONTROL.addAction(self.compactWindowAction)
        self.compactWindowAction.triggered.connect(self.compactWindow)
        self.CBB_EVENT_STORYMODE.setItemData(0,fgoEventProgress.EVENT_STORY_PAUSE)
        self.CBB_EVENT_STORYMODE.setItemData(1,fgoEventProgress.EVENT_STORY_SKIP)
        self.CBB_EVENT_STORYMODE.setCurrentIndex(1 if self.config.get('eventStoryMode','pause')=='skip' else 0)
        self.CBB_EVENT_STORYMODE.currentIndexChanged.connect(self.eventStoryModeChanged)
        self.CKB_EVENT_REWARD.setChecked(bool(self.config.get('eventAutoClaimRewards',False)))
        self.CKB_EVENT_REWARD.toggled.connect(lambda value:self.config.__setitem__('eventAutoClaimRewards',value))
        self.TXT_EVENT_LIMIT.setValue(max(1,min(100,int(self.config.get('eventProgressLimit',1)))))
        self.TXT_EVENT_LIMIT.valueChanged.connect(lambda value:self.config.__setitem__('eventProgressLimit',value))
        for key,ui,callback in(
            ('teamIndex',self.TXT_TEAM,lambda x:setattr(fgoKernel.Main,'teamIndex',x)),
            (False,self.CKB_TEAM,lambda x:setattr(fgoKernel.Main,'autoFormation',x)),
            ('stopOnDefeated',self.MENU_SETTINGS_DEFEATED,fgoKernel.schedule.stopOnDefeated),
            ('stopOnKizunaReisou',self.MENU_SETTINGS_KIZUNAREISOU,fgoKernel.schedule.stopOnKizunaReisou),
            ('closeToTray',self.MENU_CONTROL_TRAY,None),
            ('stayOnTop',self.MENU_CONTROL_STAYONTOP,lambda x:(self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,x),self.show())),
            ('notifyEnable',self.MENU_CONTROL_NOTIFY,None),
            (0,self.CBB_APPLE,lambda x:setattr(self.operation,'appleKind',x)),
            ('quickFarmBattleLimit',self.TXT_BATTLELIMIT,None),
            ('friendMaxRefresh',self.TXT_FRIENDREFRESH,None),
            (0,self.TXT_APPLE,lambda x:setattr(self.operation,'appleTotal',x)),
        ):
            value=self.config.get(key,key)
            getattr(ui,{QAction:'toggled',QCheckBox:'toggled',QSpinBox:'valueChanged',QComboBox:'currentIndexChanged'}[type(ui)])[type(value)].connect(lambda x,task=((lambda x,key=key:self.config.__setitem__(key,x),)if key else())+((lambda x,callback=callback:callback(x),)if callable(callback)else()):[i(x)for i in task])
            getattr(ui,{QAction:'setChecked',QCheckBox:'setChecked',QSpinBox:'setValue',QComboBox:'setCurrentIndex'}[type(ui)])(value)
        self.CBB_QUICKMODE.setCurrentIndex(fgoQuickFarm.modeIndex(self.config.get('quickFarmMode','current')))
        self.CBB_QUICKMODE.currentIndexChanged.connect(self.quickModeChanged)
        self.quickModeChanged(self.CBB_QUICKMODE.currentIndex())
        self.CBB_FRIENDPOLICY.setCurrentIndex(fgoFriendPolicy.policyIndex(self.config.get('friendPolicy','first')))
        self.CBB_FRIENDPOLICY.currentIndexChanged.connect(self.friendPolicyChanged)
        self.friendPolicyChanged(self.CBB_FRIENDPOLICY.currentIndex())
        self.timer=QTimer(self)
        self.timer.timeout.connect(self.flush)
        self.notifier=[]
        self.LBL_DEVICE.setText(self.tr('未连接'))
        self.chapterChanged(self.CBB_CHAPTER.currentIndex(),autoScan=False)
        # Restore after mode-specific controls have their final visibility.
        for widgetName,key in (('window','windowGeometry'),('splitter','splitterState')):
            try:
                value=bytes.fromhex(config.get(key,''))
                if value:(self.restoreGeometry if widgetName=='window' else self.SPLIT_RUN.restoreState)(QByteArray(value))
            except (ValueError,TypeError):logger.warning('Ignored invalid saved GUI geometry')
        safe=self.minimumSizeHint();self.resize(max(self.width(),safe.width()),max(self.height(),safe.height()))
        # Saved geometry from the earlier large layout otherwise defeats a new
        # default. Migrate once; subsequent user resizing remains persistent.
        if config.get('guiLayoutVersion',0)<self.GUI_LAYOUT_VERSION:
            self.compactWindow()
        self.config['guiLayoutVersion']=self.GUI_LAYOUT_VERSION
    def compactWindow(self):
        if self.isVisible():self.showNormal()
        else:self.setWindowState(Qt.WindowState.WindowNoState)
        safe=self.minimumSizeHint()
        self.resize(max(self.COMPACT_SIZE[0],safe.width()),max(self.COMPACT_SIZE[1],safe.height()))
        self.SPLIT_RUN.setSizes([350,170])
    def keyPressEvent(self,key):
        if self.MENU_CONTROL_MAPKEY.isChecked()and not key.modifiers()&~Qt.KeyboardModifier.KeypadModifier:
            try:fgoDevice.device.press(chr(key.nativeVirtualKey()))
            except KeyError:pass
            except Exception as e:logger.critical(e)
    def closeEvent(self,event):
        if self.config.closeToTray:
            self.hide()
            return event.ignore()
        if self.askQuit():return event.accept()
        event.ignore()
    def askQuit(self):
        if self.worker.is_alive():
            if QMessageBox.warning(self,'FGO-py',self.tr('战斗正在进行,确认关闭?'),QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return False
            self.signalFuncEnd.disconnect(None)
            fgoKernel.schedule.stop('Quit')
            self.worker.join()
            self.funcEnd(('Quit',QSystemTrayIcon.MessageIcon.Information))
        self.TRAY.hide()
        self.config['windowGeometry']=bytes(self.saveGeometry()).hex()
        self.config['splitterState']=bytes(self.SPLIT_RUN.saveState()).hex()
        logging.getLogger('fgo').removeHandler(self._logHandler)
        return True
    def isDeviceAvailable(self):
        if not fgoDevice.device.available:
            self.LBL_DEVICE.setText(self.tr('未连接'))
            QMessageBox.critical(self,'FGO-py',self.tr('未连接设备'))
            return False
        return True
    def runFunc(self,func):
        if not self.isDeviceAvailable():return
        def f():
            try:
                self.result=None
                self.signalFuncBegin.emit()
                self.result=func()
            except fgoKernel.ScriptStop as e:
                logger.critical(e)
                msg=(str(e),QSystemTrayIcon.MessageIcon.Warning)
            except BaseException as e:
                logger.exception(e)
                msg=(repr(e),QSystemTrayIcon.MessageIcon.Critical)
            else:msg=('Done',QSystemTrayIcon.MessageIcon.Information)
            finally:
                self.result=getattr(func,'result',self.result)
                self.signalFuncEnd.emit(msg)
                fgoKernel.fuse.reset()
                fgoKernel.schedule.reset()
                if self.config.notifyEnable and not all(success:=[i(msg[0])for i in self.notifier]):logger.critical(f'Notify post failed {success.count(False)} of {len(success)}')
        self.worker=Thread(target=f,name=f'{getattr(func,"__qualname__",repr(func).replace(" ",""))}')
        self.worker.start()
    def flush(self):
        self.TXT_APPLE.setValue(self.operation.appleTotal)
        cur=self.LST_QUEST.currentRow()
        self.LST_QUEST.clear()
        rows=[]
        for index,task in enumerate(self._queueSnapshot if self.worker.is_alive() else tuple(self.operation),1):
            if isinstance(task,fgoGuiOperation.QuestTask):
                target,times=task.target,task.repetitions
                if task.type=='daily':chapter='每日任务';title=target.title
                elif task.type=='metadata':chapter=QApplication.translate('quest','-'.join(str(part)for part in target[:2]));title=QApplication.translate('quest','-'.join(str(part)for part in target))
                else:chapter=task.type;title=str(target)
            else:
                target,times=task
                chapter=QApplication.translate('quest','-'.join(str(part)for part in target[:2]))
                title=QApplication.translate('quest','-'.join(str(part)for part in target))
            rows.append(f'{index}. {times}× {chapter} == {title}')
        self.LST_QUEST.addItems(rows)
        self.LST_QUEST.setCurrentRow(cur)
    def showProgress(self,p):
        self._lastProgress=p
        self._queueSnapshot=p.queue
        self.LBL_WEEKLY_STATUS.setText(formatProgress(p))
        self.flush()
        self.TXT_LOG.appendPlainText('[任务] '+formatProgress(p).replace('\n','；'))
        if p.battle:
            b=p.battle
            self.TXT_LOG.appendPlainText(f'[战斗] 第{p.run_attempted}场完成：{b.turns}回合，{int(b.seconds)//60}:{int(b.seconds)%60:02}；累计胜{p.wins} 负{p.defeats}')
    def showNavigation(self,message):
        self.LBL_WEEKLY_STATUS.setText(formatProgress(self._lastProgress) if self._lastProgress else message)
        line='[导航] '+message.split('\n')[-1]
        self.appendLog(line)
    def appendLog(self,line):
        if getattr(self,'_lastLog',None)!=line:
            self.TXT_LOG.appendPlainText(line);self._lastLog=line
    def currentProgressCallback(self):
        limit=self.TXT_BATTLELIMIT.value()
        return lambda event:self.signalProgress.emit(currentProgress(event,limit))
    def funcBegin(self):
        self._lastProgress=None;self._lastNavigation=None
        for control in (self.CBB_QUICKMODE,self.TXT_TEAM,self.CKB_TEAM,self.CBB_APPLE,self.TXT_APPLE,self.CBB_FRIENDPOLICY,self.TXT_FRIENDREFRESH,self.BTN_CONNECT):control.setEnabled(False)
        for control in (self.BTN_QUESTADD,self.BTN_QUESTREMOVE,self.BTN_QUESTUP,self.BTN_QUESTDOWN,self.BTN_QUESTCLEAR,self.BTN_FRIENDTEMPLATES,self.TXT_TIMES,self.TXT_BATTLELIMIT):control.setEnabled(False)
        self.BTN_MAIN.setEnabled(False)
        self.BTN_BATTLE.setEnabled(False)
        self.BTN_CLASSIC.setEnabled(False)
        self.BTN_PAUSE.setEnabled(True)
        self.BTN_PAUSE.setChecked(False)
        self.BTN_STOP.setEnabled(True)
        self.BTN_STOPLATER.setEnabled(True)
        self.BTN_QUESTLOAD.setEnabled(False)
        self.BTN_DAILY_REFRESH.setEnabled(False)
        self.CBB_CHAPTER.setEnabled(False)
        self.CBB_QUEST.setEnabled(False)
        self.MENU_SCRIPT.setEnabled(False)
        self.timer.start(500)
    def funcEnd(self,msg):
        for control in (self.CBB_QUICKMODE,self.TXT_TEAM,self.CKB_TEAM,self.CBB_APPLE,self.TXT_APPLE,self.CBB_FRIENDPOLICY,self.TXT_FRIENDREFRESH,self.BTN_CONNECT):control.setEnabled(True)
        for control in (self.BTN_QUESTADD,self.BTN_QUESTREMOVE,self.BTN_QUESTUP,self.BTN_QUESTDOWN,self.BTN_QUESTCLEAR,self.BTN_FRIENDTEMPLATES,self.TXT_TIMES,self.TXT_BATTLELIMIT):control.setEnabled(True)
        if msg[0]!='Done' and ('Navigation failed' in msg[0] or '导航' in msg[0] or '前置检查' in msg[0]):self.LBL_WEEKLY_STATUS.setText(msg[0])
        self.BTN_MAIN.setEnabled(True)
        self.BTN_BATTLE.setEnabled(True)
        self.BTN_CLASSIC.setEnabled(True)
        self.BTN_PAUSE.setEnabled(False)
        self.BTN_STOP.setEnabled(False)
        self.BTN_STOPLATER.setChecked(False)
        self.BTN_STOPLATER.setEnabled(False)
        self.BTN_QUESTLOAD.setEnabled(True)
        self.BTN_DAILY_REFRESH.setEnabled(True)
        self.CBB_CHAPTER.setEnabled(True)
        self.CBB_QUEST.setEnabled(self.CBB_CHAPTER.currentData()!=fgoQuickQuest.DAILY_CATEGORY or bool(self.dailyEntries))
        self.MENU_SCRIPT.setEnabled(True)
        self.timer.stop()
        self.flush()
        if self._dailyScanPending:
            self._dailyScanPending=False
            if isinstance(self.result,dict) and self.result.get('type')=='DailyQuestScan':
                self.dailyEntries=list(self.result['entries'])
                if self.CBB_CHAPTER.currentData()==fgoQuickQuest.DAILY_CATEGORY:self.populateDailyQuests()
                status=f'已完整扫描 {self.result["screens"]} 屏，校验 {len(self.dailyEntries)} 项每日任务；已返回顶部。'
                self.LBL_WEEKLY_STATUS.setText(status)
            elif msg[0]!='Done':self.LBL_WEEKLY_STATUS.setText(msg[0])
        if self.LBL_WEEKLY_STATUS.text()=='正在读取每周任务……' and not(isinstance(self.result,dict)and self.result.get('type')=='WeeklyMission'):
            self.LBL_WEEKLY_STATUS.setText('每周任务读取未完成，请查看诊断日志。')
        QApplication.alert(self)
        self.TRAY.showMessage('FGO-py',*msg)
        match self.result:
            case{'type':'EventProgress'}:
                self.LBL_EVENT_STATUS.setText(self.result.get('message','活动状态已更新。'))
                if self.result.get('state') in ('story_paused','mission_blocked','blocked','combat_ready','start_confirmation','battle_defeated'):
                    QMessageBox.information(self,'FGO-py',self.result.get('message','活动推进已暂停。'))
            case{'type':'WeeklyMission'}:
                feedback=fgoQuickFarm.weeklyMissionFeedback(self.result)
                self.LBL_WEEKLY_STATUS.setText(feedback)
                QMessageBox.information(self,'FGO-py',feedback)
            case{'type':'Battle'}|{'type':'Main'}:
                RunResultDialog(self.result,msg[0],self).exec()
            case{'type':'SummonHistory'}:QMessageBox.information(self,'FGO-py',f'''
<h2>{msg[0].split(':',1)[0]}</h2>
{self.tr('获取到')}{self.color(0x006400)}{self.result['value']}</font>{self.tr('条抽卡记录')},{self.tr('图片保存至')}</br>
{self.color(0x7030A0)}{self.result['file']}</font>
''')
            case{'type':'Bench'}:QMessageBox.information(self,'FGO-py',f'''
<h2>{msg[0].split(':',1)[0]}</h2>
{', '.join(f'{self.tr(i)} {self.result[j]:.2f}ms'for i,j in(('点击','touch'),('截图','screenshot')))}
''')
        self.flush()
    def _connectDevice(self,text):
        previous=fgoDevice.device
        try:
            candidate=fgoDevice.Device(text)
            if not candidate.available:raise RuntimeError('Device is not available')
        except Exception:
            # Device construction installs its screenshot source; keep the old
            # detector and connection when the replacement cannot be used.
            fgoDevice.setup(previous)
            raise
        fgoDevice.device=candidate
        self.LBL_DEVICE.setText(candidate.name)
        self.MENU_CONTROL_MAPKEY.setChecked(False)
        self.statusBar().clearMessage()
    def initializeDevice(self):
        saved=self.config.device.strip()
        if not saved:
            self.LBL_DEVICE.setText(self.tr('未连接'))
            self.statusBar().showMessage(self.tr('未保存设备，请点击“更改”选择设备'))
            return False
        try:self._connectDevice(saved)
        except Exception:
            logger.exception('Auto connection to saved device failed: %s',saved)
            self.LBL_DEVICE.setText(self.tr('未连接'))
            self.statusBar().showMessage(self.tr('自动连接设备失败，请点击“更改”重新选择设备'))
            return False
        logger.info('Auto connected to saved device: %s',saved)
        return True
    def connectDevice(self):
        dialog=QInputDialog(self)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setWindowTitle('FGO-py')
        dialog.setLabelText(self.tr('选择或填写一个设备'))
        saved=self.config.device
        try:devices=list(fgoDevice.Device.enumDevices())
        except Exception:
            logger.exception('Device enumeration failed')
            devices=[]
        if saved and saved not in devices:devices.insert(0,saved)
        dialog.setComboBoxItems(devices)
        dialog.setComboBoxEditable(True)
        dialog.setTextValue(saved)
        if not dialog.exec():return False
        text=dialog.textValue().replace(' ','')
        if not text:
            self.statusBar().showMessage(self.tr('设备不能为空，请点击“更改”重新选择设备'))
            return False
        try:self._connectDevice(text)
        except Exception:
            logger.exception('Device connection failed: %s',text)
            self.statusBar().showMessage(self.tr('连接设备失败，请点击“更改”重新选择设备'))
            return False
        self.config.device=text
        return True
    def quickModeChanged(self,index):
        mode=fgoQuickFarm.modeName(index)
        self.config['quickFarmMode']=mode
        eventMode=mode=='event'
        self.BTN_MAIN.setText('开始活动推进' if eventMode else '开始智能周回')
        self.BTN_MAIN.setStatusTip('只沿活动主线推进；遇到剧情默认暂停。' if eventMode else '按“当前关卡周回”或左侧“计划关卡队列”开始智能周回。')
        self.LBL_QUICK_HINT.setText({
            'current':'将游戏停在目标 Free Quest 列表；当前首位可见关卡为周回目标。',
            'plan':'左侧次数是每项计划场数，右侧上限是本次合计场数。选择关卡后点“+”加入队列。',
            'event':'依次推进当前活动主线；遇到剧情暂停，任务条件阻挡时停止。',
        }[mode])
        self.LBL_BATTLELIMIT.setVisible(not eventMode)
        self.TXT_BATTLELIMIT.setVisible(not eventMode)
        for widget in (self.LBL_EVENT_STORYMODE,self.CBB_EVENT_STORYMODE,self.LBL_EVENT_LIMIT,self.TXT_EVENT_LIMIT,self.CKB_EVENT_REWARD,self.LBL_EVENT_STATUS):widget.setVisible(eventMode)
    def eventStoryModeChanged(self,index):
        mode=self.CBB_EVENT_STORYMODE.itemData(index) or fgoEventProgress.EVENT_STORY_PAUSE
        self.config['eventStoryMode']=mode
        self.CBB_EVENT_STORYMODE.setStatusTip('默认模式：检测到剧情立即暂停，请阅读后返回活动地图再启动。' if mode==fgoEventProgress.EVENT_STORY_PAUSE else '只有 OCR 唯一识别 SKIP/跳过按钮及确认弹窗后才会操作；识别失败就停止。')
    def chapterChanged(self,index,autoScan=True):
        if index<0:return
        self.CBB_QUEST.clear()
        data=self._chapterData[index]
        isDaily=data==fgoQuickQuest.DAILY_CATEGORY
        self.BTN_DAILY_REFRESH.setVisible(isDaily)
        self.CBB_QUEST.setEnabled(not isDaily)
        if isDaily:
            self.populateDailyQuests()
            if autoScan and not self.dailyEntries and not self._dailyScanPending:QTimer.singleShot(0,self.refreshDailyQuests)
        else:
            self.quest=[item for item in quest if item[:2]==data]
            self.CBB_QUEST.addItems(QApplication.translate('quest','-'.join(str(j)for j in item))for item in self.quest)
    def populateDailyQuests(self):
        self.CBB_QUEST.clear()
        for entry in self.dailyEntries:self.CBB_QUEST.addItem(entry.title,entry)
        self.CBB_QUEST.setEnabled(bool(self.dailyEntries) and not self._dailyScanPending)
    def refreshDailyQuests(self):
        if self.worker.is_alive() or self._dailyScanPending or not self.isDeviceAvailable():return
        self._dailyScanPending=True
        self.CBB_QUEST.setEnabled(False)
        self.LBL_WEEKLY_STATUS.setText('正在校验每日任务卡片，扫描至列表末端后返回顶部……')
        def scan():
            import fgoNavigation
            with fgoNavigation.feedback(self.signalNavigation.emit):return fgoQuickQuest.refreshDailyQuestsCN()
        self.runFunc(scan)
    def quickFarm(self):
        if not self.isDeviceAvailable():return
        mode=fgoQuickFarm.modeName(self.CBB_QUICKMODE.currentIndex())
        self.operation.friendPolicy=self.config.get('friendPolicy','first')
        self.operation.friendMaxRefresh=self.TXT_FRIENDREFRESH.value()
        if mode=='event':
            self.LBL_EVENT_STATUS.setText('正在识别当前活动状态……')
            self.runFunc(lambda:fgoEventProgress.progress(self.TXT_EVENT_LIMIT.value(),self.CBB_EVENT_STORYMODE.currentData() or 'pause',self.CKB_EVENT_REWARD.isChecked(),self.operation.friendPolicy,self.operation.friendMaxRefresh))
            return
        fgoQuickFarm.applyBattleLimit(fgoKernel.schedule,self.TXT_BATTLELIMIT.value())
        if mode=='current':
            operation=fgoKernel.Operation(appleTotal=self.operation.appleTotal,appleKind=self.operation.appleKind,battleClass=fgoKernel.Battle,friendPolicy=self.operation.friendPolicy,friendMaxRefresh=self.operation.friendMaxRefresh,onProgress=self.currentProgressCallback())
        else:
            if not self.operation:
                QMessageBox.information(self,'FGO-py','计划关卡队列为空。请先添加关卡。')
                return
            operation=fgoGuiOperation.GuiQueueOperation(self.operation,self.operation,onNavigation=self.signalNavigation.emit,onProgress=self.signalProgress.emit,runLimit=self.TXT_BATTLELIMIT.value())
        self.runFunc(operation)
    def friendPolicyChanged(self,index):
        policy=fgoFriendPolicy.policyName(index)
        self.config['friendPolicy']=policy
        tips={
            'first':'任意：选择当前助战列表首位，不扫描模板。',
            'prefer':'模板优先：按显式优先级查找；达到刷新上限后选择首位。',
            'strict':'模板严格：只接受模板匹配；达到刷新上限后停止。',
        }
        self.CBB_FRIENDPOLICY.setStatusTip(tips[policy])
    def openFriendTemplates(self):FriendTemplateDialog(fgoKernel.friendImg,self).exec()
    def runMain(self):
        self.operation.battleClass=fgoKernel.Battle
        if self.operation:self.runFunc(fgoGuiOperation.GuiQueueOperation(self.operation,self.operation,self.operation.battleClass,onNavigation=self.signalNavigation.emit,onProgress=self.signalProgress.emit,runLimit=self.TXT_BATTLELIMIT.value()))
        else:self.runFunc(fgoKernel.Main(self.operation.appleTotal,self.operation.appleKind,fgoKernel.Battle,self.operation.friendPolicy,self.operation.friendMaxRefresh,onProgress=self.currentProgressCallback()))
    def runBattle(self):self.runFunc(fgoKernel.Battle())
    def runClassic(self):
        if not Teamup(self).exec():return
        battleClass=lambda:fgoKernel.Battle(fgoKernel.ClassicTurn)
        if self.operation:self.runFunc(fgoGuiOperation.GuiQueueOperation(self.operation,self.operation,battleClass,onNavigation=self.signalNavigation.emit,onProgress=self.signalProgress.emit,runLimit=self.TXT_BATTLELIMIT.value()))
        else:self.runFunc(fgoKernel.Main(self.operation.appleTotal,self.operation.appleKind,battleClass,self.operation.friendPolicy,self.operation.friendMaxRefresh,onProgress=self.currentProgressCallback()))
    def pause(self,x):
        if not x and not self.isDeviceAvailable():return self.BTN_PAUSE.setChecked(True)
        fgoKernel.schedule.pause()
    def stop(self):fgoKernel.schedule.stop('Stop Command Effected')
    def stopLater(self,x):
        if x:
            num,ok=QInputDialog.getInt(self,'FGO-py',self.tr('剩余的战斗数量'),1,1,1919810,1)
            if ok:fgoKernel.schedule.stopLater(num)
            else:self.BTN_STOPLATER.setChecked(False)
        else:fgoKernel.schedule.stopLater()
    def screenshot(self):
        if not self.isDeviceAvailable():return
        try:
            chk=fgoKernel.XDetect()
            backend=pyplot.get_current_fig_manager()
            backend.set_window_title(time.strftime(f'Screenshot_%Y-%m-%d_%H.%M.%S.{round(chk.time*1000)%1000:03}',time.localtime(chk.time)))
            backend.toolbar.save_figure=lambda:(backend.window.close(),chk.save())
            pyplot.imshow(chk.im[...,::-1])
            pyplot.show()
        except Exception as e:logger.exception(e)
    def explorerHere(self):os.startfile('.')
    def runFpSummon(self):self.runFunc(fgoKernel.fpSummon)
    def runLottery(self):self.runFunc(fgoKernel.lottery)
    def runMail(self):self.runFunc(fgoKernel.mail)
    def runSynthesis(self):self.runFunc(fgoKernel.synthesis)
    def runSummonHistory(self):self.runFunc(fgoKernel.summonHistory)
    def expBall(self):
        QMessageBox.information(self,'FGO-py',f'''
{self.tr('搓丸子是一个基于FGO-py的独立项目')}<br/>
<a href="https://github.com/hgjazhgj/FGO-ExpBall">FGO-ExpBall</a><br/>
{self.tr('你看见了这个弹窗,说明你已经能够运行FGO-py了')}<br/>
{self.tr('那么,无需任何其他配置,你可以直接运行FGO-ExpBall')}''')
    def mapKey(self,x):self.MENU_CONTROL_MAPKEY.setChecked(x and self.isDeviceAvailable())
    def invoke169(self):
        if not self.isDeviceAvailable():return
        fgoDevice.device.invoke169()
    def revoke169(self):
        if not self.isDeviceAvailable():return
        fgoDevice.device.revoke169()
    def bench(self):
        if not self.isDeviceAvailable():return
        self.runFunc(fgoKernel.bench)
    def exec(self):
        s=QApplication.clipboard().text()
        if QMessageBox.information(self,'FGO-py',s,QMessageBox.StandardButton.Ok|QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Ok:return
        try:exec(s)
        except BaseException as e:logger.exception(e)
    def questQuery(self,index):self.chapterChanged(index)
    def questAdd(self):
        index=self.CBB_QUEST.currentIndex()
        if index<0:return
        times=self.TXT_TIMES.value()
        if self._chapterData[self.CBB_CHAPTER.currentIndex()]==fgoQuickQuest.DAILY_CATEGORY:
            entry=self.CBB_QUEST.currentData()
            if entry is None:
                QMessageBox.information(self,'FGO-py','每日任务尚未扫描。请先刷新列表。')
                return
            task=fgoGuiOperation.QuestTask.daily(entry,times)
        else:task=fgoGuiOperation.QuestTask.metadata(self.quest[index],times)
        self.operation.append(task)
        self.flush()
    def questRemove(self):
        if(cur:=self.LST_QUEST.currentRow())>=len(self.operation):return
        del self.operation[cur]
        self.flush()
    def questClear(self):
        self.operation.clear()
        self.flush()
    def questUp(self):
        if(cur:=self.LST_QUEST.currentRow())<=0 or cur>=len(self.operation):return
        self.operation[cur],self.operation[cur-1]=self.operation[cur-1],self.operation[cur]
        self.LST_QUEST.setCurrentRow(cur-1)
        self.flush()
    def questDown(self):
        if(cur:=self.LST_QUEST.currentRow())>=len(self.operation)-1:return
        self.operation[cur],self.operation[cur+1]=self.operation[cur+1],self.operation[cur]
        self.LST_QUEST.setCurrentRow(cur+1)
        self.flush()
    def questLoad(self):
        self.LBL_WEEKLY_STATUS.setText('正在读取每周任务……')
        def load():
            report=fgoKernel.weeklyMissionDetailed()
            tasks=[fgoGuiOperation.QuestTask.metadata(quest,times) for quest,times in report.get('quests',())]
            self.operation.extend(tasks)
            report['entries']=len(tasks)
            return report
        self.runFunc(load)
    def about(self):QMessageBox.about(self,'FGO-py - About',f'''
<h2>FGO-py</h2>
{self.tr('全自动免配置跨平台开箱即用的FGO助手')}
<table border="0">
  <tr><td>{self.tr('当前版本')}</td><td>{fgoKernel.__version__}</td></tr>
  <tr><td>{self.tr('作者')}</td><td><a href="https://github.com/hgjazhgj">hgjazhgj</a></td></tr>
  <tr><td>{self.tr('项目主页')}</td><td><a href="https://fgo-py.hgjazhgj.top/">https://fgo-py.hgjazhgj.top/</a></td></tr>
  <tr><td>{self.tr('QQ群')}</td><td>932481680({self.tr('请按readme指引操作')})</td></tr>
</table>
<!-- 都看到这里了真的不考虑资瓷一下吗... -->
{self.tr('这是我的')}<font color="#00A0E8">{self.tr('支付宝')}</font>/<font color="#22AB38">{self.tr('微信')}</font>{self.tr('收款码和Monero地址')}<br/>{self.tr('请给我打钱')}<br/>
<img height="116" width="116" src="data:image/bmp;base64,Qk2yAAAAAAAAAD4AAAAoAAAAHQAAAB0AAAABAAEAAAAAAHQAAAB0EgAAdBIAAAAAAAAAAAAA6KAAAP///wABYWKofU/CKEV/ZtBFXEMwRbiQUH2a5yABj+Uo/zf3AKDtsBjeNa7YcUYb2MrQ04jEa/Ioh7TO6BR150Djjo3ATKgPmGLjdfDleznImz0gcA19mxD/rx/4AVVUAH2zpfBFCgUQRSgtEEVjdRB9/R3wATtkAA=="/>
<img height="116" width="116" src="data:image/bmp;base64,Qk2yAAAAAAAAAD4AAAAoAAAAHQAAAB0AAAABAAEAAAAAAHQAAAB0EgAAdBIAAAAAAAAAAAAAOKsiAP///wABNLhYfVLBqEUYG0hFcn7gRS8QAH2Pd2ABQiVY/x1nMFWzcFhidNUwaXr3GEp1khDJzDfAuqx06ChC9hhPvmIQMJX3SCZ13ehlXB9IVtJQUAQreqj/jv/4AVVUAH0iFfBFuxUQRRAlEEX2fRB9Wl3wAdBsAA=="/>
<table border="0"><tr>
  <td><img height="148" width="148" src="data:image/bmp;base64,Qk1mAQAAAAAAAD4AAAAoAAAAJQAAACUAAAABAAEAAAAAACgBAAB0EgAAdBIAAAAAAAAAAAAAAAAAAP///wABNpugAAAAAH0Q2oL4AAAARb1nmkAAAABFZnR3IAAAAEXpv9AwAAAAfZSA10AAAAABXdMVYAAAAP8qTsdQAAAAMd998EgAAACighiQeAAAAFCt3LiwAAAAo3aTXIAAAACAQzl8SAAAAEehYzFgAAAAcZ0FlEAAAACmEjZXoAAAAD2l77w4AAAAvy27zoAAAAD4P5FWQAAAAEYVS3VwAAAAyXKhYYAAAACvQwA4OAAAALyhfNNwAAAAhuODSLAAAABIC/+BMAAAABpa6jMwAAAA6TltfQAAAAATihl8wAAAACzQ8IxIAAAA/zQAZ/gAAAABVVVUAAAAAH0qre3wAAAARXxupRAAAABFiJ3tEAAAAEUGtG0QAAAAfWa6DfAAAAABsL3cAAAAAA=="/></td>
  <td><font face="Courier New">42Cnr V9Tuz E1jiS<br/>2ucGw tzN8g F6o4y<br/>9SkHs X1eZE vtiDf<br/>4QcL1 NXvfZ PhDu7<br/>LYStW rbsQM 9UUGW<br/>nqXgh ManMB dqjEW<br/>5oaDY</font></td>
</tr></table>
<a href="https://github.com/sponsors/hgjazhgj/">GitHub Sponsor</a><br/>
<a href="https://patreon.com/hgjazhgj">Patreon</a><br/>
<a href="https://paypal.me/hgjazhgjpp">Paypal</a><br/>
{self.tr('B站大会员每月')}<a href="https://account.bilibili.com/account/big/myPackage">{self.tr('领')}</a>{self.tr('5B币券')}<a href="https://space.bilibili.com/2632341">{self.tr('充电')}</a>
''')
    def license(self):subprocess.Popen(['notepad.exe',str(licenseFile())],shell=False)

def main(config):
    app=QApplication(sys.argv)
    app.setStyle('Fusion')
    translator=QTranslator()
    translator.load(QLocale(),'fgoI18n','.')
    app.installTranslator(translator)
    myWin=MainWindow(config)
    myWin.show()
    QTimer.singleShot(0,myWin.initializeDevice)
    sys.exit(app.exec())

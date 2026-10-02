# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'fgoMainWindow.ui'
##
## Created by: Qt User Interface Compiler version 6.11.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFormLayout,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QMenu,
    QMenuBar, QPlainTextEdit, QPushButton, QSizePolicy,
    QSpinBox, QSplitter, QStatusBar, QVBoxLayout,
    QWidget)

class Ui_fgoMainWindow(object):
    def setupUi(self, fgoMainWindow):
        if not fgoMainWindow.objectName():
            fgoMainWindow.setObjectName(u"fgoMainWindow")
        fgoMainWindow.setFocusPolicy(Qt.StrongFocus)
        fgoMainWindow.setStyleSheet(u"QWidget{font-family:\"Microsoft YaHei UI\";font-size:14px}")
        fgoMainWindow.resize(900, 680)
        self.MENU_ABOUT_ABOUT = QAction(fgoMainWindow)
        self.MENU_ABOUT_ABOUT.setObjectName(u"MENU_ABOUT_ABOUT")
        self.MENU_FILE_EXPLORER = QAction(fgoMainWindow)
        self.MENU_FILE_EXPLORER.setObjectName(u"MENU_FILE_EXPLORER")
        self.MENU_CONTROL_STAYONTOP = QAction(fgoMainWindow)
        self.MENU_CONTROL_STAYONTOP.setObjectName(u"MENU_CONTROL_STAYONTOP")
        self.MENU_CONTROL_STAYONTOP.setCheckable(True)
        self.MENU_SCRIPT_FPSUMMON = QAction(fgoMainWindow)
        self.MENU_SCRIPT_FPSUMMON.setObjectName(u"MENU_SCRIPT_FPSUMMON")
        self.MENU_SCRIPT_SYNTHESIS = QAction(fgoMainWindow)
        self.MENU_SCRIPT_SYNTHESIS.setObjectName(u"MENU_SCRIPT_SYNTHESIS")
        self.MENU_SCRIPT_SUMMONHISTORY = QAction(fgoMainWindow)
        self.MENU_SCRIPT_SUMMONHISTORY.setObjectName(u"MENU_SCRIPT_SUMMONHISTORY")
        self.MENU_SCRIPT_EXPBALL = QAction(fgoMainWindow)
        self.MENU_SCRIPT_EXPBALL.setObjectName(u"MENU_SCRIPT_EXPBALL")
        self.MENU_CONTROL_MAPKEY = QAction(fgoMainWindow)
        self.MENU_CONTROL_MAPKEY.setObjectName(u"MENU_CONTROL_MAPKEY")
        self.MENU_CONTROL_MAPKEY.setCheckable(True)
        self.MENU_SCRIPT_LOTTERY = QAction(fgoMainWindow)
        self.MENU_SCRIPT_LOTTERY.setObjectName(u"MENU_SCRIPT_LOTTERY")
        self.MENU_SCRIPT_MAILFILTER = QAction(fgoMainWindow)
        self.MENU_SCRIPT_MAILFILTER.setObjectName(u"MENU_SCRIPT_MAILFILTER")
        self.MENU_CONTROL_BENCH = QAction(fgoMainWindow)
        self.MENU_CONTROL_BENCH.setObjectName(u"MENU_CONTROL_BENCH")
        self.MENU_CONTROL_EXEC = QAction(fgoMainWindow)
        self.MENU_CONTROL_EXEC.setObjectName(u"MENU_CONTROL_EXEC")
        self.MENU_SETTINGS_DEFEATED = QAction(fgoMainWindow)
        self.MENU_SETTINGS_DEFEATED.setObjectName(u"MENU_SETTINGS_DEFEATED")
        self.MENU_SETTINGS_DEFEATED.setCheckable(True)
        self.MENU_SETTINGS_KIZUNAREISOU = QAction(fgoMainWindow)
        self.MENU_SETTINGS_KIZUNAREISOU.setObjectName(u"MENU_SETTINGS_KIZUNAREISOU")
        self.MENU_SETTINGS_KIZUNAREISOU.setCheckable(True)
        self.MENU_SETTINGS_SPECIALDROP = QAction(fgoMainWindow)
        self.MENU_SETTINGS_SPECIALDROP.setObjectName(u"MENU_SETTINGS_SPECIALDROP")
        self.MENU_SETTINGS_SPECIALDROP.setCheckable(True)
        self.MENU_ABOUT_LICENSE = QAction(fgoMainWindow)
        self.MENU_ABOUT_LICENSE.setObjectName(u"MENU_ABOUT_LICENSE")
        self.MENU_FILE_QUIT = QAction(fgoMainWindow)
        self.MENU_FILE_QUIT.setObjectName(u"MENU_FILE_QUIT")
        self.MENU_CONTROL_TRAY = QAction(fgoMainWindow)
        self.MENU_CONTROL_TRAY.setObjectName(u"MENU_CONTROL_TRAY")
        self.MENU_CONTROL_TRAY.setCheckable(True)
        self.MENU_CONTROL_169_INVOKE = QAction(fgoMainWindow)
        self.MENU_CONTROL_169_INVOKE.setObjectName(u"MENU_CONTROL_169_INVOKE")
        self.MENU_CONTROL_169_REVOKE = QAction(fgoMainWindow)
        self.MENU_CONTROL_169_REVOKE.setObjectName(u"MENU_CONTROL_169_REVOKE")
        self.MENU_CONTROL_NOTIFY = QAction(fgoMainWindow)
        self.MENU_CONTROL_NOTIFY.setObjectName(u"MENU_CONTROL_NOTIFY")
        self.MENU_CONTROL_NOTIFY.setCheckable(True)
        self.widget = QWidget(fgoMainWindow)
        self.widget.setObjectName(u"widget")
        self.verticalLayout = QVBoxLayout(self.widget)
        self.verticalLayout.setSpacing(3)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(6, 6, 6, 6)
        self.SPLIT_RUN = QSplitter(self.widget)
        self.SPLIT_RUN.setObjectName(u"SPLIT_RUN")
        self.SPLIT_RUN.setOrientation(Qt.Vertical)
        self.RUN_CONTROLS = QWidget(self.SPLIT_RUN)
        self.RUN_CONTROLS.setObjectName(u"RUN_CONTROLS")
        self.RUN_CONTROLS.setMinimumSize(QSize(0, 390))
        self.LAYOUT_TOP = QVBoxLayout(self.RUN_CONTROLS)
        self.LAYOUT_TOP.setSpacing(3)
        self.LAYOUT_TOP.setObjectName(u"LAYOUT_TOP")
        self.LAYOUT_TOP.setContentsMargins(0, 0, 0, 0)
        self.LAYOUT_MAIN = QHBoxLayout()
        self.LAYOUT_MAIN.setSpacing(3)
        self.LAYOUT_MAIN.setObjectName(u"LAYOUT_MAIN")
        self.LAYOUT_QUEST = QVBoxLayout()
        self.LAYOUT_QUEST.setSpacing(3)
        self.LAYOUT_QUEST.setObjectName(u"LAYOUT_QUEST")
        self.LAYOUT_QUEST.setAlignment(Qt.AlignTop)
        self.LBL_QUEUE_TITLE = QLabel(self.RUN_CONTROLS)
        self.LBL_QUEUE_TITLE.setObjectName(u"LBL_QUEUE_TITLE")

        self.LAYOUT_QUEST.addWidget(self.LBL_QUEUE_TITLE)

        self.LAYOUT_QUESTSELECT = QFormLayout()
        self.LAYOUT_QUESTSELECT.setObjectName(u"LAYOUT_QUESTSELECT")
        self.LAYOUT_QUESTSELECT.setLabelAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.LAYOUT_QUESTSELECT.setVerticalSpacing(3)
        self.CBB_CHAPTER = QComboBox(self.RUN_CONTROLS)
        self.CBB_CHAPTER.setObjectName(u"CBB_CHAPTER")

        self.LAYOUT_QUESTSELECT.setWidget(0, QFormLayout.ItemRole.FieldRole, self.CBB_CHAPTER)

        self.LBL_CHAPTER = QLabel(self.RUN_CONTROLS)
        self.LBL_CHAPTER.setObjectName(u"LBL_CHAPTER")

        self.LAYOUT_QUESTSELECT.setWidget(0, QFormLayout.ItemRole.LabelRole, self.LBL_CHAPTER)

        self.LBL_QUEST = QLabel(self.RUN_CONTROLS)
        self.LBL_QUEST.setObjectName(u"LBL_QUEST")

        self.LAYOUT_QUESTSELECT.setWidget(1, QFormLayout.ItemRole.LabelRole, self.LBL_QUEST)

        self.CBB_QUEST = QComboBox(self.RUN_CONTROLS)
        self.CBB_QUEST.setObjectName(u"CBB_QUEST")

        self.LAYOUT_QUESTSELECT.setWidget(1, QFormLayout.ItemRole.FieldRole, self.CBB_QUEST)

        self.LBL_TIMES = QLabel(self.RUN_CONTROLS)
        self.LBL_TIMES.setObjectName(u"LBL_TIMES")

        self.LAYOUT_QUESTSELECT.setWidget(2, QFormLayout.ItemRole.LabelRole, self.LBL_TIMES)

        self.TXT_TIMES = QSpinBox(self.RUN_CONTROLS)
        self.TXT_TIMES.setObjectName(u"TXT_TIMES")
        self.TXT_TIMES.setContextMenuPolicy(Qt.NoContextMenu)
        self.TXT_TIMES.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.TXT_TIMES.setMaximum(114514)
        self.TXT_TIMES.setValue(1)

        self.LAYOUT_QUESTSELECT.setWidget(2, QFormLayout.ItemRole.FieldRole, self.TXT_TIMES)


        self.LAYOUT_QUEST.addLayout(self.LAYOUT_QUESTSELECT)

        self.BTN_DAILY_REFRESH = QPushButton(self.RUN_CONTROLS)
        self.BTN_DAILY_REFRESH.setObjectName(u"BTN_DAILY_REFRESH")

        self.LAYOUT_QUEST.addWidget(self.BTN_DAILY_REFRESH)

        self.LAYOUT_QUESTADD = QHBoxLayout()
        self.LAYOUT_QUESTADD.setSpacing(3)
        self.LAYOUT_QUESTADD.setObjectName(u"LAYOUT_QUESTADD")
        self.BTN_QUESTADD = QPushButton(self.RUN_CONTROLS)
        self.BTN_QUESTADD.setObjectName(u"BTN_QUESTADD")

        self.LAYOUT_QUESTADD.addWidget(self.BTN_QUESTADD)

        self.BTN_QUESTREMOVE = QPushButton(self.RUN_CONTROLS)
        self.BTN_QUESTREMOVE.setObjectName(u"BTN_QUESTREMOVE")

        self.LAYOUT_QUESTADD.addWidget(self.BTN_QUESTREMOVE)


        self.LAYOUT_QUEST.addLayout(self.LAYOUT_QUESTADD)

        self.LAYOUT_QUESTMOVE = QHBoxLayout()
        self.LAYOUT_QUESTMOVE.setSpacing(3)
        self.LAYOUT_QUESTMOVE.setObjectName(u"LAYOUT_QUESTMOVE")
        self.BTN_QUESTUP = QPushButton(self.RUN_CONTROLS)
        self.BTN_QUESTUP.setObjectName(u"BTN_QUESTUP")

        self.LAYOUT_QUESTMOVE.addWidget(self.BTN_QUESTUP)

        self.BTN_QUESTDOWN = QPushButton(self.RUN_CONTROLS)
        self.BTN_QUESTDOWN.setObjectName(u"BTN_QUESTDOWN")

        self.LAYOUT_QUESTMOVE.addWidget(self.BTN_QUESTDOWN)

        self.BTN_QUESTCLEAR = QPushButton(self.RUN_CONTROLS)
        self.BTN_QUESTCLEAR.setObjectName(u"BTN_QUESTCLEAR")

        self.LAYOUT_QUESTMOVE.addWidget(self.BTN_QUESTCLEAR)


        self.LAYOUT_QUEST.addLayout(self.LAYOUT_QUESTMOVE)

        self.BTN_QUESTLOAD = QPushButton(self.RUN_CONTROLS)
        self.BTN_QUESTLOAD.setObjectName(u"BTN_QUESTLOAD")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.BTN_QUESTLOAD.sizePolicy().hasHeightForWidth())
        self.BTN_QUESTLOAD.setSizePolicy(sizePolicy)

        self.LAYOUT_QUEST.addWidget(self.BTN_QUESTLOAD)

        self.LBL_WEEKLY_STATUS = QLabel(self.RUN_CONTROLS)
        self.LBL_WEEKLY_STATUS.setObjectName(u"LBL_WEEKLY_STATUS")
        self.LBL_WEEKLY_STATUS.setWordWrap(True)

        self.LAYOUT_QUEST.addWidget(self.LBL_WEEKLY_STATUS)

        self.LST_QUEST = QListWidget(self.RUN_CONTROLS)
        self.LST_QUEST.setObjectName(u"LST_QUEST")
        self.LST_QUEST.setMinimumSize(QSize(0, 48))

        self.LAYOUT_QUEST.addWidget(self.LST_QUEST)


        self.LAYOUT_MAIN.addLayout(self.LAYOUT_QUEST)

        self.LAYOUT_LAUNCH = QVBoxLayout()
        self.LAYOUT_LAUNCH.setSpacing(3)
        self.LAYOUT_LAUNCH.setObjectName(u"LAYOUT_LAUNCH")
        self.LAYOUT_LAUNCH.setAlignment(Qt.AlignTop)
        self.GRP_QUICKFARM = QGroupBox(self.RUN_CONTROLS)
        self.GRP_QUICKFARM.setObjectName(u"GRP_QUICKFARM")
        self.LAYOUT_QUICKFARM = QGridLayout(self.GRP_QUICKFARM)
        self.LAYOUT_QUICKFARM.setObjectName(u"LAYOUT_QUICKFARM")
        self.LAYOUT_QUICKFARM.setVerticalSpacing(3)
        self.LBL_QUICKMODE = QLabel(self.GRP_QUICKFARM)
        self.LBL_QUICKMODE.setObjectName(u"LBL_QUICKMODE")

        self.LAYOUT_QUICKFARM.addWidget(self.LBL_QUICKMODE, 0, 0, 1, 1)

        self.CBB_QUICKMODE = QComboBox(self.GRP_QUICKFARM)
        self.CBB_QUICKMODE.addItem("")
        self.CBB_QUICKMODE.addItem("")
        self.CBB_QUICKMODE.addItem("")
        self.CBB_QUICKMODE.setObjectName(u"CBB_QUICKMODE")

        self.LAYOUT_QUICKFARM.addWidget(self.CBB_QUICKMODE, 0, 1, 1, 1)

        self.LBL_BATTLELIMIT = QLabel(self.GRP_QUICKFARM)
        self.LBL_BATTLELIMIT.setObjectName(u"LBL_BATTLELIMIT")

        self.LAYOUT_QUICKFARM.addWidget(self.LBL_BATTLELIMIT, 1, 0, 1, 1)

        self.TXT_BATTLELIMIT = QSpinBox(self.GRP_QUICKFARM)
        self.TXT_BATTLELIMIT.setObjectName(u"TXT_BATTLELIMIT")
        self.TXT_BATTLELIMIT.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.TXT_BATTLELIMIT.setMaximum(1000)
        self.TXT_BATTLELIMIT.setValue(1)

        self.LAYOUT_QUICKFARM.addWidget(self.TXT_BATTLELIMIT, 1, 1, 1, 1)

        self.LBL_QUICK_HINT = QLabel(self.GRP_QUICKFARM)
        self.LBL_QUICK_HINT.setObjectName(u"LBL_QUICK_HINT")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.LBL_QUICK_HINT.sizePolicy().hasHeightForWidth())
        self.LBL_QUICK_HINT.setSizePolicy(sizePolicy1)
        self.LBL_QUICK_HINT.setTextFormat(Qt.PlainText)
        self.LBL_QUICK_HINT.setWordWrap(True)

        self.LAYOUT_QUICKFARM.addWidget(self.LBL_QUICK_HINT, 2, 0, 1, 2)

        self.BTN_MAIN = QPushButton(self.GRP_QUICKFARM)
        self.BTN_MAIN.setObjectName(u"BTN_MAIN")
        self.BTN_MAIN.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.LAYOUT_QUICKFARM.addWidget(self.BTN_MAIN, 3, 0, 1, 2)

        self.LBL_EVENT_STORYMODE = QLabel(self.GRP_QUICKFARM)
        self.LBL_EVENT_STORYMODE.setObjectName(u"LBL_EVENT_STORYMODE")

        self.LAYOUT_QUICKFARM.addWidget(self.LBL_EVENT_STORYMODE, 4, 0, 1, 1)

        self.CBB_EVENT_STORYMODE = QComboBox(self.GRP_QUICKFARM)
        self.CBB_EVENT_STORYMODE.addItem("")
        self.CBB_EVENT_STORYMODE.addItem("")
        self.CBB_EVENT_STORYMODE.setObjectName(u"CBB_EVENT_STORYMODE")

        self.LAYOUT_QUICKFARM.addWidget(self.CBB_EVENT_STORYMODE, 4, 1, 1, 1)

        self.LBL_EVENT_LIMIT = QLabel(self.GRP_QUICKFARM)
        self.LBL_EVENT_LIMIT.setObjectName(u"LBL_EVENT_LIMIT")

        self.LAYOUT_QUICKFARM.addWidget(self.LBL_EVENT_LIMIT, 5, 0, 1, 1)

        self.TXT_EVENT_LIMIT = QSpinBox(self.GRP_QUICKFARM)
        self.TXT_EVENT_LIMIT.setObjectName(u"TXT_EVENT_LIMIT")
        self.TXT_EVENT_LIMIT.setMinimum(1)
        self.TXT_EVENT_LIMIT.setMaximum(100)
        self.TXT_EVENT_LIMIT.setValue(1)

        self.LAYOUT_QUICKFARM.addWidget(self.TXT_EVENT_LIMIT, 5, 1, 1, 1)

        self.CKB_EVENT_REWARD = QCheckBox(self.GRP_QUICKFARM)
        self.CKB_EVENT_REWARD.setObjectName(u"CKB_EVENT_REWARD")

        self.LAYOUT_QUICKFARM.addWidget(self.CKB_EVENT_REWARD, 6, 0, 1, 2)

        self.LBL_EVENT_STATUS = QLabel(self.GRP_QUICKFARM)
        self.LBL_EVENT_STATUS.setObjectName(u"LBL_EVENT_STATUS")
        sizePolicy1.setHeightForWidth(self.LBL_EVENT_STATUS.sizePolicy().hasHeightForWidth())
        self.LBL_EVENT_STATUS.setSizePolicy(sizePolicy1)
        self.LBL_EVENT_STATUS.setTextFormat(Qt.PlainText)
        self.LBL_EVENT_STATUS.setWordWrap(True)

        self.LAYOUT_QUICKFARM.addWidget(self.LBL_EVENT_STATUS, 7, 0, 1, 2)

        self.LAYOUT_QUICKFARM.setColumnStretch(1, 1)

        self.LAYOUT_LAUNCH.addWidget(self.GRP_QUICKFARM)

        self.LAYOUT_INFO = QFormLayout()
        self.LAYOUT_INFO.setObjectName(u"LAYOUT_INFO")
        self.LAYOUT_INFO.setLabelAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.LAYOUT_INFO.setVerticalSpacing(3)
        self.LBL_TEAM = QLabel(self.RUN_CONTROLS)
        self.LBL_TEAM.setObjectName(u"LBL_TEAM")

        self.LAYOUT_INFO.setWidget(0, QFormLayout.ItemRole.LabelRole, self.LBL_TEAM)

        self.LAYOUT_INFO_TEAM = QHBoxLayout()
        self.LAYOUT_INFO_TEAM.setSpacing(3)
        self.LAYOUT_INFO_TEAM.setObjectName(u"LAYOUT_INFO_TEAM")
        self.TXT_TEAM = QSpinBox(self.RUN_CONTROLS)
        self.TXT_TEAM.setObjectName(u"TXT_TEAM")
        sizePolicy.setHeightForWidth(self.TXT_TEAM.sizePolicy().hasHeightForWidth())
        self.TXT_TEAM.setSizePolicy(sizePolicy)
        self.TXT_TEAM.setContextMenuPolicy(Qt.NoContextMenu)
        self.TXT_TEAM.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.TXT_TEAM.setMaximum(15)

        self.LAYOUT_INFO_TEAM.addWidget(self.TXT_TEAM)

        self.CKB_TEAM = QCheckBox(self.RUN_CONTROLS)
        self.CKB_TEAM.setObjectName(u"CKB_TEAM")

        self.LAYOUT_INFO_TEAM.addWidget(self.CKB_TEAM)


        self.LAYOUT_INFO.setLayout(0, QFormLayout.ItemRole.FieldRole, self.LAYOUT_INFO_TEAM)

        self.LBL_APPLE = QLabel(self.RUN_CONTROLS)
        self.LBL_APPLE.setObjectName(u"LBL_APPLE")
        self.LBL_APPLE.setMaximumSize(QSize(16777215, 28))

        self.LAYOUT_INFO.setWidget(1, QFormLayout.ItemRole.LabelRole, self.LBL_APPLE)

        self.LAYOUT_INFO_APPLE = QHBoxLayout()
        self.LAYOUT_INFO_APPLE.setSpacing(3)
        self.LAYOUT_INFO_APPLE.setObjectName(u"LAYOUT_INFO_APPLE")
        self.CBB_APPLE = QComboBox(self.RUN_CONTROLS)
        self.CBB_APPLE.addItem("")
        self.CBB_APPLE.addItem("")
        self.CBB_APPLE.addItem("")
        self.CBB_APPLE.addItem("")
        self.CBB_APPLE.addItem("")
        self.CBB_APPLE.setObjectName(u"CBB_APPLE")

        self.LAYOUT_INFO_APPLE.addWidget(self.CBB_APPLE)

        self.TXT_APPLE = QSpinBox(self.RUN_CONTROLS)
        self.TXT_APPLE.setObjectName(u"TXT_APPLE")
        sizePolicy.setHeightForWidth(self.TXT_APPLE.sizePolicy().hasHeightForWidth())
        self.TXT_APPLE.setSizePolicy(sizePolicy)
        self.TXT_APPLE.setContextMenuPolicy(Qt.NoContextMenu)
        self.TXT_APPLE.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.TXT_APPLE.setMaximum(114514)

        self.LAYOUT_INFO_APPLE.addWidget(self.TXT_APPLE)


        self.LAYOUT_INFO.setLayout(1, QFormLayout.ItemRole.FieldRole, self.LAYOUT_INFO_APPLE)

        self.LBL_CURRENTDEVICE = QLabel(self.RUN_CONTROLS)
        self.LBL_CURRENTDEVICE.setObjectName(u"LBL_CURRENTDEVICE")

        self.LAYOUT_INFO.setWidget(2, QFormLayout.ItemRole.LabelRole, self.LBL_CURRENTDEVICE)

        self.LAYOUT_DEVICE = QHBoxLayout()
        self.LAYOUT_DEVICE.setSpacing(3)
        self.LAYOUT_DEVICE.setObjectName(u"LAYOUT_DEVICE")
        self.LBL_DEVICE = QLabel(self.RUN_CONTROLS)
        self.LBL_DEVICE.setObjectName(u"LBL_DEVICE")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.LBL_DEVICE.sizePolicy().hasHeightForWidth())
        self.LBL_DEVICE.setSizePolicy(sizePolicy2)

        self.LAYOUT_DEVICE.addWidget(self.LBL_DEVICE)

        self.BTN_CONNECT = QPushButton(self.RUN_CONTROLS)
        self.BTN_CONNECT.setObjectName(u"BTN_CONNECT")
        self.BTN_CONNECT.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.LAYOUT_DEVICE.addWidget(self.BTN_CONNECT)


        self.LAYOUT_INFO.setLayout(2, QFormLayout.ItemRole.FieldRole, self.LAYOUT_DEVICE)

        self.LBL_FRIENDPOLICY = QLabel(self.RUN_CONTROLS)
        self.LBL_FRIENDPOLICY.setObjectName(u"LBL_FRIENDPOLICY")

        self.LAYOUT_INFO.setWidget(3, QFormLayout.ItemRole.LabelRole, self.LBL_FRIENDPOLICY)

        self.CBB_FRIENDPOLICY = QComboBox(self.RUN_CONTROLS)
        self.CBB_FRIENDPOLICY.addItem("")
        self.CBB_FRIENDPOLICY.addItem("")
        self.CBB_FRIENDPOLICY.addItem("")
        self.CBB_FRIENDPOLICY.setObjectName(u"CBB_FRIENDPOLICY")

        self.LAYOUT_INFO.setWidget(3, QFormLayout.ItemRole.FieldRole, self.CBB_FRIENDPOLICY)

        self.LBL_FRIENDREFRESH = QLabel(self.RUN_CONTROLS)
        self.LBL_FRIENDREFRESH.setObjectName(u"LBL_FRIENDREFRESH")

        self.LAYOUT_INFO.setWidget(4, QFormLayout.ItemRole.LabelRole, self.LBL_FRIENDREFRESH)

        self.TXT_FRIENDREFRESH = QSpinBox(self.RUN_CONTROLS)
        self.TXT_FRIENDREFRESH.setObjectName(u"TXT_FRIENDREFRESH")
        self.TXT_FRIENDREFRESH.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)
        self.TXT_FRIENDREFRESH.setMaximum(10)
        self.TXT_FRIENDREFRESH.setValue(2)

        self.LAYOUT_INFO.setWidget(4, QFormLayout.ItemRole.FieldRole, self.TXT_FRIENDREFRESH)

        self.BTN_FRIENDTEMPLATES = QPushButton(self.RUN_CONTROLS)
        self.BTN_FRIENDTEMPLATES.setObjectName(u"BTN_FRIENDTEMPLATES")

        self.LAYOUT_INFO.setWidget(5, QFormLayout.ItemRole.SpanningRole, self.BTN_FRIENDTEMPLATES)


        self.LAYOUT_LAUNCH.addLayout(self.LAYOUT_INFO)

        self.LAYOUT_FUNC = QHBoxLayout()
        self.LAYOUT_FUNC.setSpacing(3)
        self.LAYOUT_FUNC.setObjectName(u"LAYOUT_FUNC")
        self.LAYOUT_FUNCBATTLE = QVBoxLayout()
        self.LAYOUT_FUNCBATTLE.setSpacing(3)
        self.LAYOUT_FUNCBATTLE.setObjectName(u"LAYOUT_FUNCBATTLE")
        self.BTN_BATTLE = QPushButton(self.RUN_CONTROLS)
        self.BTN_BATTLE.setObjectName(u"BTN_BATTLE")

        self.LAYOUT_FUNCBATTLE.addWidget(self.BTN_BATTLE)

        self.BTN_CLASSIC = QPushButton(self.RUN_CONTROLS)
        self.BTN_CLASSIC.setObjectName(u"BTN_CLASSIC")

        self.LAYOUT_FUNCBATTLE.addWidget(self.BTN_CLASSIC)


        self.LAYOUT_FUNC.addLayout(self.LAYOUT_FUNCBATTLE)

        self.LAYOUT_FUNCCONTROL = QVBoxLayout()
        self.LAYOUT_FUNCCONTROL.setSpacing(3)
        self.LAYOUT_FUNCCONTROL.setObjectName(u"LAYOUT_FUNCCONTROL")
        self.BTN_PAUSE = QPushButton(self.RUN_CONTROLS)
        self.BTN_PAUSE.setObjectName(u"BTN_PAUSE")
        self.BTN_PAUSE.setEnabled(False)
        self.BTN_PAUSE.setCheckable(True)

        self.LAYOUT_FUNCCONTROL.addWidget(self.BTN_PAUSE)

        self.BTN_STOP = QPushButton(self.RUN_CONTROLS)
        self.BTN_STOP.setObjectName(u"BTN_STOP")
        self.BTN_STOP.setEnabled(False)

        self.LAYOUT_FUNCCONTROL.addWidget(self.BTN_STOP)


        self.LAYOUT_FUNC.addLayout(self.LAYOUT_FUNCCONTROL)

        self.LAYOUT_FUNCAPPOINT = QVBoxLayout()
        self.LAYOUT_FUNCAPPOINT.setSpacing(3)
        self.LAYOUT_FUNCAPPOINT.setObjectName(u"LAYOUT_FUNCAPPOINT")
        self.BTN_SCREENSHOT = QPushButton(self.RUN_CONTROLS)
        self.BTN_SCREENSHOT.setObjectName(u"BTN_SCREENSHOT")

        self.LAYOUT_FUNCAPPOINT.addWidget(self.BTN_SCREENSHOT)

        self.BTN_STOPLATER = QPushButton(self.RUN_CONTROLS)
        self.BTN_STOPLATER.setObjectName(u"BTN_STOPLATER")
        self.BTN_STOPLATER.setEnabled(False)
        self.BTN_STOPLATER.setCheckable(True)

        self.LAYOUT_FUNCAPPOINT.addWidget(self.BTN_STOPLATER)


        self.LAYOUT_FUNC.addLayout(self.LAYOUT_FUNCAPPOINT)


        self.LAYOUT_LAUNCH.addLayout(self.LAYOUT_FUNC)


        self.LAYOUT_MAIN.addLayout(self.LAYOUT_LAUNCH)


        self.LAYOUT_TOP.addLayout(self.LAYOUT_MAIN)

        self.SPLIT_RUN.addWidget(self.RUN_CONTROLS)
        self.TXT_LOG = QPlainTextEdit(self.SPLIT_RUN)
        self.TXT_LOG.setObjectName(u"TXT_LOG")
        self.TXT_LOG.setReadOnly(True)
        self.TXT_LOG.setMaximumBlockCount(2000)
        self.TXT_LOG.setMinimumSize(QSize(0, 200))
        self.SPLIT_RUN.addWidget(self.TXT_LOG)

        self.verticalLayout.addWidget(self.SPLIT_RUN)

        fgoMainWindow.setCentralWidget(self.widget)
        self.MENU = QMenuBar(fgoMainWindow)
        self.MENU.setObjectName(u"MENU")
        self.MENU_ABOUT = QMenu(self.MENU)
        self.MENU_ABOUT.setObjectName(u"MENU_ABOUT")
        self.MENU_FILE = QMenu(self.MENU)
        self.MENU_FILE.setObjectName(u"MENU_FILE")
        self.MENU_SCRIPT = QMenu(self.MENU)
        self.MENU_SCRIPT.setObjectName(u"MENU_SCRIPT")
        self.MENU_CONTROL = QMenu(self.MENU)
        self.MENU_CONTROL.setObjectName(u"MENU_CONTROL")
        self.MENU_CONTROL_169 = QMenu(self.MENU_CONTROL)
        self.MENU_CONTROL_169.setObjectName(u"MENU_CONTROL_169")
        self.MENU_SETTINGS = QMenu(self.MENU)
        self.MENU_SETTINGS.setObjectName(u"MENU_SETTINGS")
        fgoMainWindow.setMenuBar(self.MENU)
        self.STATUS = QStatusBar(fgoMainWindow)
        self.STATUS.setObjectName(u"STATUS")
        fgoMainWindow.setStatusBar(self.STATUS)
        QWidget.setTabOrder(self.CBB_CHAPTER, self.CBB_QUEST)
        QWidget.setTabOrder(self.CBB_QUEST, self.BTN_DAILY_REFRESH)
        QWidget.setTabOrder(self.BTN_DAILY_REFRESH, self.TXT_TIMES)
        QWidget.setTabOrder(self.TXT_TIMES, self.BTN_QUESTADD)
        QWidget.setTabOrder(self.BTN_QUESTADD, self.BTN_QUESTREMOVE)
        QWidget.setTabOrder(self.BTN_QUESTREMOVE, self.BTN_QUESTUP)
        QWidget.setTabOrder(self.BTN_QUESTUP, self.BTN_QUESTDOWN)
        QWidget.setTabOrder(self.BTN_QUESTDOWN, self.BTN_QUESTCLEAR)
        QWidget.setTabOrder(self.BTN_QUESTCLEAR, self.CBB_QUICKMODE)
        QWidget.setTabOrder(self.CBB_QUICKMODE, self.TXT_BATTLELIMIT)
        QWidget.setTabOrder(self.TXT_BATTLELIMIT, self.BTN_MAIN)
        QWidget.setTabOrder(self.BTN_MAIN, self.CBB_EVENT_STORYMODE)
        QWidget.setTabOrder(self.CBB_EVENT_STORYMODE, self.TXT_EVENT_LIMIT)
        QWidget.setTabOrder(self.TXT_EVENT_LIMIT, self.CKB_EVENT_REWARD)
        QWidget.setTabOrder(self.CKB_EVENT_REWARD, self.TXT_TEAM)
        QWidget.setTabOrder(self.TXT_TEAM, self.CKB_TEAM)
        QWidget.setTabOrder(self.CKB_TEAM, self.CBB_APPLE)
        QWidget.setTabOrder(self.CBB_APPLE, self.TXT_APPLE)
        QWidget.setTabOrder(self.TXT_APPLE, self.CBB_FRIENDPOLICY)
        QWidget.setTabOrder(self.CBB_FRIENDPOLICY, self.TXT_FRIENDREFRESH)
        QWidget.setTabOrder(self.TXT_FRIENDREFRESH, self.BTN_FRIENDTEMPLATES)
        QWidget.setTabOrder(self.BTN_FRIENDTEMPLATES, self.BTN_CONNECT)
        QWidget.setTabOrder(self.BTN_CONNECT, self.BTN_QUESTLOAD)
        QWidget.setTabOrder(self.BTN_QUESTLOAD, self.BTN_BATTLE)
        QWidget.setTabOrder(self.BTN_BATTLE, self.BTN_CLASSIC)
        QWidget.setTabOrder(self.BTN_CLASSIC, self.BTN_PAUSE)
        QWidget.setTabOrder(self.BTN_PAUSE, self.BTN_STOP)
        QWidget.setTabOrder(self.BTN_STOP, self.BTN_SCREENSHOT)
        QWidget.setTabOrder(self.BTN_SCREENSHOT, self.BTN_STOPLATER)

        self.MENU.addAction(self.MENU_FILE.menuAction())
        self.MENU.addAction(self.MENU_SCRIPT.menuAction())
        self.MENU.addAction(self.MENU_SETTINGS.menuAction())
        self.MENU.addAction(self.MENU_CONTROL.menuAction())
        self.MENU.addAction(self.MENU_ABOUT.menuAction())
        self.MENU_ABOUT.addAction(self.MENU_ABOUT_ABOUT)
        self.MENU_ABOUT.addAction(self.MENU_ABOUT_LICENSE)
        self.MENU_FILE.addAction(self.MENU_FILE_EXPLORER)
        self.MENU_SCRIPT.addAction(self.MENU_SCRIPT_FPSUMMON)
        self.MENU_SCRIPT.addAction(self.MENU_SCRIPT_LOTTERY)
        self.MENU_SCRIPT.addAction(self.MENU_SCRIPT_MAILFILTER)
        self.MENU_SCRIPT.addAction(self.MENU_SCRIPT_SYNTHESIS)
        self.MENU_SCRIPT.addAction(self.MENU_SCRIPT_SUMMONHISTORY)
        self.MENU_SCRIPT.addAction(self.MENU_SCRIPT_EXPBALL)
        self.MENU_CONTROL.addAction(self.MENU_CONTROL_STAYONTOP)
        self.MENU_CONTROL.addAction(self.MENU_CONTROL_TRAY)
        self.MENU_CONTROL.addSeparator()
        self.MENU_CONTROL.addAction(self.MENU_CONTROL_MAPKEY)
        self.MENU_CONTROL.addAction(self.MENU_CONTROL_169.menuAction())
        self.MENU_CONTROL.addAction(self.MENU_CONTROL_NOTIFY)
        self.MENU_CONTROL.addSeparator()
        self.MENU_CONTROL.addAction(self.MENU_CONTROL_BENCH)
        self.MENU_CONTROL.addAction(self.MENU_CONTROL_EXEC)
        self.MENU_CONTROL_169.addAction(self.MENU_CONTROL_169_INVOKE)
        self.MENU_CONTROL_169.addAction(self.MENU_CONTROL_169_REVOKE)
        self.MENU_SETTINGS.addAction(self.MENU_SETTINGS_DEFEATED)
        self.MENU_SETTINGS.addAction(self.MENU_SETTINGS_KIZUNAREISOU)
        self.MENU_SETTINGS.addAction(self.MENU_SETTINGS_SPECIALDROP)

        self.retranslateUi(fgoMainWindow)
        self.BTN_CLASSIC.clicked.connect(fgoMainWindow.runClassic)
        self.BTN_FRIENDTEMPLATES.clicked.connect(fgoMainWindow.openFriendTemplates)
        self.BTN_MAIN.clicked.connect(fgoMainWindow.quickFarm)
        self.BTN_SCREENSHOT.clicked.connect(fgoMainWindow.screenshot)
        self.BTN_PAUSE.clicked["bool"].connect(fgoMainWindow.pause)
        self.BTN_STOP.clicked.connect(fgoMainWindow.stop)
        self.BTN_CONNECT.clicked.connect(fgoMainWindow.connectDevice)
        self.MENU_FILE_EXPLORER.triggered.connect(fgoMainWindow.explorerHere)
        self.MENU_ABOUT_ABOUT.triggered.connect(fgoMainWindow.about)
        self.MENU_SCRIPT_FPSUMMON.triggered.connect(fgoMainWindow.runFpSummon)
        self.MENU_SCRIPT_SYNTHESIS.triggered.connect(fgoMainWindow.runSynthesis)
        self.MENU_SCRIPT_SUMMONHISTORY.triggered.connect(fgoMainWindow.runSummonHistory)
        self.MENU_SCRIPT_EXPBALL.triggered.connect(fgoMainWindow.expBall)
        self.MENU_CONTROL_MAPKEY.triggered["bool"].connect(fgoMainWindow.mapKey)
        self.BTN_STOPLATER.clicked["bool"].connect(fgoMainWindow.stopLater)
        self.MENU_SCRIPT_LOTTERY.triggered.connect(fgoMainWindow.runLottery)
        self.MENU_SCRIPT_MAILFILTER.triggered.connect(fgoMainWindow.runMail)
        self.MENU_CONTROL_BENCH.triggered.connect(fgoMainWindow.bench)
        self.MENU_CONTROL_EXEC.triggered.connect(fgoMainWindow.exec)
        self.MENU_SETTINGS_SPECIALDROP.triggered.connect(fgoMainWindow.stopOnSpecialDrop)
        self.MENU_ABOUT_LICENSE.triggered.connect(fgoMainWindow.license)
        self.MENU_CONTROL_169_INVOKE.triggered.connect(fgoMainWindow.invoke169)
        self.MENU_CONTROL_169_REVOKE.triggered.connect(fgoMainWindow.revoke169)
        self.BTN_BATTLE.clicked.connect(fgoMainWindow.runBattle)
        self.BTN_QUESTADD.clicked.connect(fgoMainWindow.questAdd)
        self.BTN_QUESTCLEAR.clicked.connect(fgoMainWindow.questClear)
        self.BTN_QUESTLOAD.clicked.connect(fgoMainWindow.questLoad)
        self.BTN_QUESTREMOVE.clicked.connect(fgoMainWindow.questRemove)
        self.CBB_CHAPTER.currentIndexChanged.connect(fgoMainWindow.questQuery)
        self.BTN_QUESTUP.clicked.connect(fgoMainWindow.questUp)
        self.BTN_QUESTDOWN.clicked.connect(fgoMainWindow.questDown)

        self.CBB_APPLE.setCurrentIndex(0)

    # setupUi

    def retranslateUi(self, fgoMainWindow):
        fgoMainWindow.setWindowTitle(QCoreApplication.translate("fgoMainWindow", u"FGO-py - hgjazhgj", None))
        self.MENU_ABOUT_ABOUT.setText(QCoreApplication.translate("fgoMainWindow", u"\u5173\u4e8eFGO-py", None))
        self.MENU_FILE_EXPLORER.setText(QCoreApplication.translate("fgoMainWindow", u"\u8d44\u6e90\u7ba1\u7406\u5668", None))
        self.MENU_CONTROL_STAYONTOP.setText(QCoreApplication.translate("fgoMainWindow", u"\u7a97\u53e3\u7f6e\u9876", None))
        self.MENU_SCRIPT_FPSUMMON.setText(QCoreApplication.translate("fgoMainWindow", u"\u62bd\u53cb\u60c5", None))
#if QT_CONFIG(statustip)
        self.MENU_SCRIPT_FPSUMMON.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u5148\u62bd\u4e00\u53d1\u53cb\u60c5\u5341\u8fde,\u5728\u7ed3\u7b97\u754c\u9762\u8fd0\u884c\u672c\u529f\u80fd", None))
#endif // QT_CONFIG(statustip)
        self.MENU_SCRIPT_SYNTHESIS.setText(QCoreApplication.translate("fgoMainWindow", u"\u5f3a\u5316", None))
#if QT_CONFIG(statustip)
        self.MENU_SCRIPT_SYNTHESIS.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u5728\u9009\u62e9\u4e86\u5f3a\u5316\u5bf9\u8c61\u672a\u9009\u62e9\u5f3a\u5316\u6750\u6599\u7684\u754c\u9762\u8fd0\u884c\u672c\u529f\u80fd", None))
#endif // QT_CONFIG(statustip)
        self.MENU_SCRIPT_SUMMONHISTORY.setText(QCoreApplication.translate("fgoMainWindow", u"\u53ec\u5524\u8bb0\u5f55", None))
#if QT_CONFIG(statustip)
        self.MENU_SCRIPT_SUMMONHISTORY.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u7edf\u8ba1\u5bfc\u51fa\u53ec\u5524\u8bb0\u5f55,\u5728\u62bd\u5361\u8bb0\u5f55\u9875\u9762\u8fd0\u884c", None))
#endif // QT_CONFIG(statustip)
        self.MENU_SCRIPT_EXPBALL.setText(QCoreApplication.translate("fgoMainWindow", u"\u6413\u4e38\u5b50", None))
#if QT_CONFIG(statustip)
        self.MENU_SCRIPT_EXPBALL.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u628a\u82e5\u5e72\u5f20\u4f4e\u661f\u793c\u88c5\u5408\u5e76\u6210\u4e00\u4e2a", None))
#endif // QT_CONFIG(statustip)
        self.MENU_CONTROL_MAPKEY.setText(QCoreApplication.translate("fgoMainWindow", u"\u52a0\u8f7d\u6309\u952e\u6620\u5c04", None))
        self.MENU_SCRIPT_LOTTERY.setText(QCoreApplication.translate("fgoMainWindow", u"\u62bd\u5956\u6c60", None))
        self.MENU_SCRIPT_MAILFILTER.setText(QCoreApplication.translate("fgoMainWindow", u"\u6e05\u7406\u90ae\u7bb1", None))
        self.MENU_CONTROL_BENCH.setText(QCoreApplication.translate("fgoMainWindow", u"Bench", None))
        self.MENU_CONTROL_EXEC.setText(QCoreApplication.translate("fgoMainWindow", u"Execute", None))
        self.MENU_SETTINGS_DEFEATED.setText(QCoreApplication.translate("fgoMainWindow", u"\u6218\u8d25\u64a4\u9000\u65f6\u7ec8\u6b62\u6218\u6597", None))
        self.MENU_SETTINGS_KIZUNAREISOU.setText(QCoreApplication.translate("fgoMainWindow", u"\u83b7\u5f97\u7f81\u7eca\u793c\u88c5\u65f6\u7ec8\u6b62\u6218\u6597", None))
        self.MENU_SETTINGS_SPECIALDROP.setText(QCoreApplication.translate("fgoMainWindow", u"\u82e5\u5e72\u7279\u6b8a\u6389\u843d\u540e\u7ec8\u6b62\u6218\u6597", None))
        self.MENU_ABOUT_LICENSE.setText(QCoreApplication.translate("fgoMainWindow", u"\u4f7f\u7528\u8bb8\u53ef", None))
        self.MENU_FILE_QUIT.setText(QCoreApplication.translate("fgoMainWindow", u"\u9000\u51fa", None))
        self.MENU_CONTROL_TRAY.setText(QCoreApplication.translate("fgoMainWindow", u"\u5173\u95ed\u5230\u6258\u76d8", None))
        self.MENU_CONTROL_169_INVOKE.setText(QCoreApplication.translate("fgoMainWindow", u"\u8c03\u6574\u4e3a16:9", None))
        self.MENU_CONTROL_169_REVOKE.setText(QCoreApplication.translate("fgoMainWindow", u"\u6062\u590d\u539f\u5206\u8fa8\u7387", None))
        self.MENU_CONTROL_NOTIFY.setText(QCoreApplication.translate("fgoMainWindow", u"\u6d88\u606f\u63a8\u9001", None))
        self.LBL_QUEUE_TITLE.setText(QCoreApplication.translate("fgoMainWindow", u"\u8ba1\u5212\u5173\u5361\u961f\u5217", None))
#if QT_CONFIG(statustip)
        self.LBL_QUEUE_TITLE.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u8fd9\u91cc\u53ea\u5217\u51fa\u7531\u7ae0\u8282/\u5173\u5361\u9009\u62e9\u5668\u6216\u6bcf\u5468\u4efb\u52a1\u5206\u6790\u52a0\u5165\u7684\u8ba1\u5212\u4efb\u52a1\u3002", None))
#endif // QT_CONFIG(statustip)
#if QT_CONFIG(statustip)
        self.CBB_CHAPTER.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u666e\u901a\u7ae0\u8282\u53ea\u5305\u542b\u5df2\u89e3\u9501\u5730\u56fe\u4e0a\u7684\u81ea\u7531\u5173\u5361\uff0c\u4e0d\u4f1a\u81ea\u52a8\u63a8\u8fdb\u4e3b\u7ebf\u5267\u60c5\u3002", None))
#endif // QT_CONFIG(statustip)
        self.LBL_CHAPTER.setText(QCoreApplication.translate("fgoMainWindow", u"\u7ae0\u8282 / \u5206\u7c7b", None))
        self.LBL_QUEST.setText(QCoreApplication.translate("fgoMainWindow", u"\u5173\u5361", None))
        self.LBL_TIMES.setText(QCoreApplication.translate("fgoMainWindow", u"\u6b21\u6570", None))
#if QT_CONFIG(statustip)
        self.TXT_TIMES.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u52a0\u5165\u5173\u5361\u961f\u5217\u540e\u751f\u6548,0\u4e3a\u4e0d\u9650\u5236\u6b21\u6570", None))
#endif // QT_CONFIG(statustip)
        self.BTN_DAILY_REFRESH.setText(QCoreApplication.translate("fgoMainWindow", u"\u5237\u65b0\u6bcf\u65e5\u4efb\u52a1\u5217\u8868", None))
#if QT_CONFIG(statustip)
        self.BTN_DAILY_REFRESH.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u6eda\u52a8\u5230\u5217\u8868\u672b\u7aef\uff0c\u6821\u9a8c\u5b8c\u6574\u5361\u7247\u540e\u8fd4\u56de\u9876\u90e8\uff1b\u4e0d\u4f1a\u8fdb\u5165\u5173\u5361\u3002", None))
#endif // QT_CONFIG(statustip)
#if QT_CONFIG(statustip)
        self.BTN_QUESTADD.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u65b0\u589e", None))
#endif // QT_CONFIG(statustip)
        self.BTN_QUESTADD.setText(QCoreApplication.translate("fgoMainWindow", u"+", None))
#if QT_CONFIG(statustip)
        self.BTN_QUESTREMOVE.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u5220\u9664", None))
#endif // QT_CONFIG(statustip)
        self.BTN_QUESTREMOVE.setText(QCoreApplication.translate("fgoMainWindow", u"-", None))
#if QT_CONFIG(statustip)
        self.BTN_QUESTUP.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u4e0a\u79fb", None))
#endif // QT_CONFIG(statustip)
        self.BTN_QUESTUP.setText(QCoreApplication.translate("fgoMainWindow", u"\u2191", None))
#if QT_CONFIG(statustip)
        self.BTN_QUESTDOWN.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u4e0b\u79fb", None))
#endif // QT_CONFIG(statustip)
        self.BTN_QUESTDOWN.setText(QCoreApplication.translate("fgoMainWindow", u"\u2193", None))
#if QT_CONFIG(statustip)
        self.BTN_QUESTCLEAR.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u6e05\u7a7a", None))
#endif // QT_CONFIG(statustip)
        self.BTN_QUESTCLEAR.setText(QCoreApplication.translate("fgoMainWindow", u"\u00d7", None))
        self.BTN_QUESTLOAD.setText(QCoreApplication.translate("fgoMainWindow", u"\u5206\u6790\u6bcf\u5468\u4efb\u52a1\u5e76\u52a0\u5165\u961f\u5217", None))
        self.LBL_WEEKLY_STATUS.setText("")
#if QT_CONFIG(statustip)
        self.LST_QUEST.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u5173\u5361\u961f\u5217", None))
#endif // QT_CONFIG(statustip)
        self.GRP_QUICKFARM.setTitle(QCoreApplication.translate("fgoMainWindow", u"\u5feb\u901f\u5468\u56de", None))
        self.LBL_QUICKMODE.setText(QCoreApplication.translate("fgoMainWindow", u"\u6a21\u5f0f", None))
        self.CBB_QUICKMODE.setItemText(0, QCoreApplication.translate("fgoMainWindow", u"\u5f53\u524d\u5173\u5361\u5468\u56de", None))
        self.CBB_QUICKMODE.setItemText(1, QCoreApplication.translate("fgoMainWindow", u"\u8ba1\u5212\u5173\u5361\u961f\u5217", None))
        self.CBB_QUICKMODE.setItemText(2, QCoreApplication.translate("fgoMainWindow", u"\u6d3b\u52a8\u63a8\u8fdb", None))

        self.LBL_BATTLELIMIT.setText(QCoreApplication.translate("fgoMainWindow", u"\u573a\u6570\u4e0a\u9650", None))
#if QT_CONFIG(statustip)
        self.TXT_BATTLELIMIT.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u672c\u6b21\u8fd0\u884c\u6240\u6709\u961f\u5217\u9879\u5408\u8ba1\u7684\u573a\u6570\u4e0a\u9650\uff1b\u5de6\u4fa7\u6b21\u6570\u9650\u5236\u5355\u9879\u30020 \u8868\u793a\u4e0d\u8bbe\u603b\u4e0a\u9650\uff0c\u4ecd\u53d7\u5355\u9879\u6b21\u6570\u548c AP \u9650\u5236\u3002", None))
#endif // QT_CONFIG(statustip)
        self.LBL_QUICK_HINT.setText(QCoreApplication.translate("fgoMainWindow", u"\u628a\u6e38\u620f\u505c\u5728\u76ee\u6807\u5173\u5361\u5217\u8868\uff0c\u5e76\u8ba9\u76ee\u6807\u5173\u5361\u6392\u5728\u9996\u4f4d\u3002\u6bcf\u65e5\u4efb\u52a1\u8bf7\u5148\u624b\u52a8\u9009\u62e9\u79cd\u7c7b\u548c\u96be\u5ea6\u3002", None))
#if QT_CONFIG(statustip)
        self.BTN_MAIN.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u6309\u6240\u9009\u6a21\u5f0f\u5f00\u59cb\u667a\u80fd\u5468\u56de\u6216\u5b89\u5168\u6d3b\u52a8\u63a8\u8fdb\u3002", None))
#endif // QT_CONFIG(statustip)
        self.BTN_MAIN.setText(QCoreApplication.translate("fgoMainWindow", u"\u5f00\u59cb\u667a\u80fd\u5468\u56de", None))
        self.LBL_EVENT_STORYMODE.setText(QCoreApplication.translate("fgoMainWindow", u"\u5267\u60c5\u5904\u7406", None))
        self.CBB_EVENT_STORYMODE.setItemText(0, QCoreApplication.translate("fgoMainWindow", u"\u9047\u5230\u5267\u60c5\u6682\u505c", None))
        self.CBB_EVENT_STORYMODE.setItemText(1, QCoreApplication.translate("fgoMainWindow", u"\u81ea\u52a8\u8df3\u8fc7\u5267\u60c5", None))

        self.LBL_EVENT_LIMIT.setText(QCoreApplication.translate("fgoMainWindow", u"\u63a8\u8fdb\u4e0a\u9650", None))
#if QT_CONFIG(statustip)
        self.TXT_EVENT_LIMIT.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u6700\u591a\u63a8\u8fdb 1 \u5230 100 \u4e2a\u5267\u60c5\u8282\u70b9\uff1b\u4e0d\u5141\u8bb8\u65e0\u9650\u63a8\u8fdb\u3002", None))
#endif // QT_CONFIG(statustip)
        self.CKB_EVENT_REWARD.setText(QCoreApplication.translate("fgoMainWindow", u"\u81ea\u52a8\u9886\u53d6\u5df2\u5b8c\u6210\u6d3b\u52a8\u4efb\u52a1\u5956\u52b1", None))
#if QT_CONFIG(statustip)
        self.CKB_EVENT_REWARD.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u4ec5\u5728 OCR \u660e\u786e\u786e\u8ba4\u4efb\u52a1\u5df2\u5b8c\u6210\u4e14\u6309\u94ae\u4e3a\u9886\u53d6\u65f6\u64cd\u4f5c\uff1b\u4e0d\u8d2d\u4e70\u3001\u4e0d\u5151\u6362\u3001\u4e0d\u5904\u7406\u9009\u62e9\u5956\u52b1\u3002", None))
#endif // QT_CONFIG(statustip)
        self.LBL_EVENT_STATUS.setText("")
        self.LBL_TEAM.setText(QCoreApplication.translate("fgoMainWindow", u"\u7f16\u961f", None))
#if QT_CONFIG(statustip)
        self.TXT_TEAM.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u6240\u9009\u7f16\u961f\u5728\u961f\u4f0d\u7f16\u6210\u754c\u9762\u7684\u4f4d\u7f6e,\u4ece\u5de6\u5230\u53f31-10,0\u4e3a\u4e0d\u5207\u6362\u7f16\u961f", None))
#endif // QT_CONFIG(statustip)
        self.CKB_TEAM.setText(QCoreApplication.translate("fgoMainWindow", u"\u81ea\u52a8\u7f16\u961f", None))
        self.LBL_APPLE.setText(QCoreApplication.translate("fgoMainWindow", u"\u82f9\u679c", None))
        self.CBB_APPLE.setItemText(0, QCoreApplication.translate("fgoMainWindow", u"\u91d1", None))
        self.CBB_APPLE.setItemText(1, QCoreApplication.translate("fgoMainWindow", u"\u94f6", None))
        self.CBB_APPLE.setItemText(2, QCoreApplication.translate("fgoMainWindow", u"\u9752", None))
        self.CBB_APPLE.setItemText(3, QCoreApplication.translate("fgoMainWindow", u"\u94dc", None))
        self.CBB_APPLE.setItemText(4, QCoreApplication.translate("fgoMainWindow", u"\u5f69", None))

#if QT_CONFIG(statustip)
        self.CBB_APPLE.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u8981\u5403\u7684\u82f9\u679c\u79cd\u7c7b", None))
#endif // QT_CONFIG(statustip)
#if QT_CONFIG(statustip)
        self.TXT_APPLE.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u8981\u5403\u7684\u82f9\u679c\u6570\u91cf", None))
#endif // QT_CONFIG(statustip)
        self.LBL_CURRENTDEVICE.setText(QCoreApplication.translate("fgoMainWindow", u"\u8bbe\u5907", None))
#if QT_CONFIG(statustip)
        self.BTN_CONNECT.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u8fde\u63a5\u5230\u8bbe\u5907", None))
#endif // QT_CONFIG(statustip)
        self.BTN_CONNECT.setText(QCoreApplication.translate("fgoMainWindow", u"\u66f4\u6539", None))
        self.LBL_FRIENDPOLICY.setText(QCoreApplication.translate("fgoMainWindow", u"\u52a9\u6218\u7b56\u7565", None))
        self.CBB_FRIENDPOLICY.setItemText(0, QCoreApplication.translate("fgoMainWindow", u"\u4efb\u610f\uff08\u9996\u4f4d\uff09", None))
        self.CBB_FRIENDPOLICY.setItemText(1, QCoreApplication.translate("fgoMainWindow", u"\u6a21\u677f\u4f18\u5148", None))
        self.CBB_FRIENDPOLICY.setItemText(2, QCoreApplication.translate("fgoMainWindow", u"\u6a21\u677f\u4e25\u683c", None))

        self.LBL_FRIENDREFRESH.setText(QCoreApplication.translate("fgoMainWindow", u"\u5237\u65b0\u4e0a\u9650", None))
#if QT_CONFIG(statustip)
        self.TXT_FRIENDREFRESH.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"0 \u8868\u793a\u53ea\u626b\u63cf\u5f53\u524d\u52a9\u6218\u5217\u8868\uff0c\u4e0d\u4e3b\u52a8\u5237\u65b0\uff1b\u6700\u5927\u4e3a 10 \u6b21\u3002", None))
#endif // QT_CONFIG(statustip)
#if QT_CONFIG(statustip)
        self.BTN_FRIENDTEMPLATES.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u672c\u673a\u6a21\u677f\u4f18\u5148\u7ea7\u3001\u542f\u7528\u72b6\u6001\u4e0e\u622a\u56fe\u5236\u4f5c\u3002", None))
#endif // QT_CONFIG(statustip)
        self.BTN_FRIENDTEMPLATES.setText(QCoreApplication.translate("fgoMainWindow", u"\u7ba1\u7406\u52a9\u6218\u6a21\u677f", None))
#if QT_CONFIG(statustip)
        self.BTN_BATTLE.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u5b8c\u6210\u5f53\u524d\u6218\u6597", None))
#endif // QT_CONFIG(statustip)
        self.BTN_BATTLE.setText(QCoreApplication.translate("fgoMainWindow", u"\u5b8c\u6210\u6218\u6597", None))
#if QT_CONFIG(statustip)
        self.BTN_CLASSIC.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u57fa\u4e8e\u7ecf\u5178\u6218\u6597\u7684\u6e05\u7a7a\u4f53\u529b", None))
#endif // QT_CONFIG(statustip)
        self.BTN_CLASSIC.setText(QCoreApplication.translate("fgoMainWindow", u"\u9648\u5e74\u8001\u809d", None))
#if QT_CONFIG(statustip)
        self.BTN_PAUSE.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u6682\u505c/\u7ee7\u7eed\u6218\u6597", None))
#endif // QT_CONFIG(statustip)
        self.BTN_PAUSE.setText(QCoreApplication.translate("fgoMainWindow", u"\u6302\u8d77\u6218\u6597", None))
#if QT_CONFIG(statustip)
        self.BTN_STOP.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u7acb\u523b\u7ec8\u6b62\u6218\u6597", None))
#endif // QT_CONFIG(statustip)
        self.BTN_STOP.setText(QCoreApplication.translate("fgoMainWindow", u"\u7ec8\u6b62\u6218\u6597", None))
#if QT_CONFIG(statustip)
        self.BTN_SCREENSHOT.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u68c0\u67e5\u622a\u56fe\u786e\u5b9a\u8fde\u63a5\u5efa\u7acb", None))
#endif // QT_CONFIG(statustip)
        self.BTN_SCREENSHOT.setText(QCoreApplication.translate("fgoMainWindow", u"\u68c0\u67e5\u622a\u56fe", None))
#if QT_CONFIG(statustip)
        self.BTN_STOPLATER.setStatusTip(QCoreApplication.translate("fgoMainWindow", u"\u5728\u5b8c\u6210\u82e5\u5e72\u573a\u6218\u6597\u540e\u7ec8\u6b62\u6218\u6597", None))
#endif // QT_CONFIG(statustip)
        self.BTN_STOPLATER.setText(QCoreApplication.translate("fgoMainWindow", u"\u9884\u7ea6\u7ec8\u6b62", None))
        self.TXT_LOG.setPlaceholderText(QCoreApplication.translate("fgoMainWindow", u"\u5b9e\u65f6\u8fd0\u884c\u65e5\u5fd7", None))
        self.MENU_ABOUT.setTitle(QCoreApplication.translate("fgoMainWindow", u"\u5173\u4e8e", None))
        self.MENU_FILE.setTitle(QCoreApplication.translate("fgoMainWindow", u"\u6587\u4ef6", None))
        self.MENU_SCRIPT.setTitle(QCoreApplication.translate("fgoMainWindow", u"\u7a0b\u5e8f", None))
        self.MENU_CONTROL.setTitle(QCoreApplication.translate("fgoMainWindow", u"\u63a7\u5236", None))
        self.MENU_CONTROL_169.setTitle(QCoreApplication.translate("fgoMainWindow", u"\u5168\u9762\u5c4f\u9002\u914d", None))
        self.MENU_SETTINGS.setTitle(QCoreApplication.translate("fgoMainWindow", u"\u8bbe\u7f6e", None))
    # retranslateUi


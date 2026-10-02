"""Scrollable run summary; unknown drops are always explicitly disclosed."""
from pathlib import Path
import os
from fgoDrop import templateIconPath
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QTableWidget,QTableWidgetItem,QHeaderView,QPushButton,QApplication

def duration(seconds):
    seconds=max(0,int(seconds));return f'{seconds//3600}:{seconds//60%60:02}:{seconds%60:02}'

class RunResultDialog(QDialog):
    def __init__(self,result,message='Done',parent=None):
        super().__init__(parent);self.setWindowTitle('周回结果');self.resize(580,480);layout=QVBoxLayout(self)
        attempts=result.get('battle',1);defeats=result.get('progressDefeats',result.get('defeated',int(result.get('observedDefeated',False))));wins=result.get('progressWins',attempts-defeats)
        summary=(f'{message}\n已进行 {attempts} 场；胜 {wins} / 负 {defeats}\n总耗时 {duration(result.get("time",0))}；平均回合 {result.get("turnPerBattle",result.get("turn",0)):.1f}；平均耗时 {duration(result.get("timePerBattle",result.get("time",0)))}')
        label=QLabel(summary);label.setWordWrap(True);layout.addWidget(label)
        self.table=QTableWidget(0,3);self.table.setHorizontalHeaderLabels(['图标','名称','数量']);self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch);self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);layout.addWidget(self.table,1)
        stats=result.get('dropStats',{});items=dict(result.get('material',{}));items.update(stats.get('currency',{}));self.table.setRowCount(len(items))
        for row,(name,count) in enumerate(items.items()):
            icon=QTableWidgetItem();path=templateIconPath(name)
            if path:icon.setIcon(QIcon(str(path)))
            self.table.setItem(row,0,icon);self.table.setItem(row,1,QTableWidgetItem(QApplication.translate('material',name)));self.table.setItem(row,2,QTableWidgetItem(str(count)))
        unknown=stats.get('unknown_slots',len(result.get('unknownDrops',[])));self.unknownLabel=QLabel(f'未识别掉落：{unknown} 格。未识别项未计入上述数量。'+('\n掉落诊断失败，结果可能不完整。' if stats.get('incomplete') or stats.get('errors') else ''));self.unknownLabel.setWordWrap(True);layout.addWidget(self.unknownLabel)
        folders=[Path(p) for p in stats.get('debug_dirs',[]) if Path(p).is_dir()]
        if stats.get('currency_amount_unknown'):self.unknownLabel.setText(self.unknownLabel.text()+f'\n另有 {stats["currency_amount_unknown"]} 格货币金额无法确认，未计入表格数量。')
        self.debugButton=QPushButton('打开掉落诊断目录');self.debugButton.setVisible(bool(folders));layout.addWidget(self.debugButton)
        if folders:self.debugButton.clicked.connect(lambda:os.startfile(str(folders[0].parent)))
        close=QPushButton('关闭');close.clicked.connect(self.accept);layout.addWidget(close)

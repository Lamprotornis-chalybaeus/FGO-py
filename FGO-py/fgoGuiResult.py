"""Compact battle summary. Item recognition is removed from this local build."""
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QPushButton

def duration(seconds):
    seconds=max(0,int(seconds));return f'{seconds//3600}:{seconds//60%60:02}:{seconds%60:02}'

class RunResultDialog(QDialog):
    def __init__(self,result,message='Done',parent=None):
        super().__init__(parent);self.setWindowTitle('周回结果');layout=QVBoxLayout(self)
        attempts=result.get('completedAttempts',result.get('battle',1));defeats=result.get('progressDefeats',result.get('defeated',int(result.get('observedDefeated',False))));wins=result.get('progressWins',attempts-defeats)
        summary=(f'{message}\n已进行 {attempts} 场；胜 {wins} / 负 {defeats}\n总耗时 {duration(result.get("time",0))}；平均回合 {result.get("turnPerBattle",result.get("turn",0)):.1f}；平均耗时 {duration(result.get("timePerBattle",result.get("time",0)))}')
        self.summaryLabel=QLabel(summary);self.summaryLabel.setWordWrap(True);layout.addWidget(self.summaryLabel)
        close=QPushButton('关闭');close.clicked.connect(self.accept);layout.addWidget(close)
        self.resize(520,220)

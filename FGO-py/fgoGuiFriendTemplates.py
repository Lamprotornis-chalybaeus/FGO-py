from pathlib import Path
import os,cv2,numpy as np
from PySide6.QtCore import Qt,QRect,QPoint
from PySide6.QtGui import QPixmap,QImage,QIcon
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QFileDialog,QLabel,QLineEdit,QDialogButtonBox,QMessageBox,QRubberBand)
import fgoDevice
from fgoDetect import XDetect

def pixmap(image):
    rgb=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
    return QPixmap.fromImage(QImage(rgb.data,rgb.shape[1],rgb.shape[0],rgb.strides[0],QImage.Format.Format_RGB888).copy())

class CropLabel(QLabel):
    def __init__(self,image):
        super().__init__();self.image=image;self.setPixmap(pixmap(image).scaled(900,507,Qt.AspectRatioMode.KeepAspectRatio));self.setFixedSize(self.pixmap().size());self.band=QRubberBand(QRubberBand.Shape.Rectangle,self);self.begin=None;self.rect=QRect()
    def mousePressEvent(self,event):
        self.begin=event.position().toPoint();self.band.setGeometry(QRect(self.begin,QPoint()));self.band.show()
    def mouseMoveEvent(self,event):
        if self.begin is not None:self.band.setGeometry(QRect(self.begin,event.position().toPoint()).normalized().intersected(self.rectForImage()))
    def mouseReleaseEvent(self,event):
        self.rect=self.band.geometry();self.begin=None
    def rectForImage(self):return QRect(0,0,self.width(),self.height())
    def selected(self):
        r=self.rect;x=round(r.x()*1280/self.width());y=round(r.y()*720/self.height());right=round((r.x()+r.width())*1280/self.width());bottom=round((r.y()+r.height())*720/self.height())
        if right-x<12 or bottom-y<12 or not (13<=x<right<=1233 and 166<=y<bottom<=710):raise ValueError('请框选助战列表内可点击的区域，避开顶部和底部按钮')
        return self.image[y:bottom,x:right].copy()

class ScreenshotTemplateDialog(QDialog):
    def __init__(self,image,parent=None):
        super().__init__(parent);self.setWindowTitle('框选助战模板');layout=QVBoxLayout(self);layout.addWidget(QLabel('请亲自框选可点击的助战区域，并填写你确认的姓名。程序不会判断从者身份。'));self.crop=CropLabel(image);layout.addWidget(self.crop);self.name=QLineEdit();self.name.setPlaceholderText('例如：阿尔托莉雅·Caster');layout.addWidget(self.name);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
    def validate(self):
        try:self.selected=self.crop.selected();assert self.name.text().strip(),'请填写模板名称'
        except Exception as e:QMessageBox.warning(self,'无法保存',str(e));return
        self.accept()

class FriendTemplateDialog(QDialog):
    def __init__(self,store,parent=None):
        super().__init__(parent);self.store=store;self.setWindowTitle('管理助战模板（仅本机）');self.resize(820,480);layout=QVBoxLayout(self);self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['启用','优先级','名称','文件','预览']);self.table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.Stretch);layout.addWidget(self.table);bar=QHBoxLayout();layout.addLayout(bar)
        for title,callback in [('添加',self.addFile),('从当前助战页添加',self.fromScreen),('删除',self.remove),('启用/禁用',self.toggle),('上移',lambda:self.move(-1)),('下移',lambda:self.move(1)),('打开目录',lambda:os.startfile(str(store.root)))]:
            button=QPushButton(title);button.clicked.connect(callback);bar.addWidget(button)
        close=QPushButton('关闭');close.clicked.connect(self.accept);layout.addWidget(close);self.reload()
    def reload(self):
        self.rows=self.store.entries();self.table.setRowCount(len(self.rows))
        for i,row in enumerate(self.rows):
            for j,value in enumerate(['是' if row['enabled'] else '否',row['priority'],row['name'],row['file'],'']):
                item=QTableWidgetItem(str(value));item.setFlags(item.flags()&~Qt.ItemFlag.ItemIsEditable);self.table.setItem(i,j,item)
            self.table.item(i,4).setIcon(QIcon(str(self.store.root/row['file'])));self.table.setRowHeight(i,50)
    def persist(self):
        for i,row in enumerate(self.rows,1):row['priority']=i
        self.store.save(self.rows);self.reload()
    def toggle(self):
        i=self.table.currentRow()
        if i>=0:self.rows[i]['enabled']=not self.rows[i]['enabled'];self.persist()
    def move(self,step):
        i=self.table.currentRow();j=i+step
        if 0<=i<len(self.rows) and 0<=j<len(self.rows):self.rows[i],self.rows[j]=self.rows[j],self.rows[i];self.persist();self.table.selectRow(j)
    def remove(self):
        i=self.table.currentRow()
        if i<0:return
        if QMessageBox.question(self,'删除模板','删除此本机模板文件？')!=QMessageBox.StandardButton.Yes:return
        (self.store.root/self.rows[i]['file']).unlink();self.rows.pop(i);self.persist()
    def addFile(self):
        path,_=QFileDialog.getOpenFileName(self,'添加本机助战图片',str(self.store.root),'PNG (*.png)')
        if not path:return
        from PySide6.QtWidgets import QInputDialog
        name,ok=QInputDialog.getText(self,'模板名称','请填写你确认的姓名')
        if ok:
            try:self.store.add(cv2.imread(path),name);self.reload()
            except Exception as e:QMessageBox.warning(self,'添加失败',str(e))
    def fromScreen(self):
        if getattr(self.parent(),'worker',None) and self.parent().worker.is_alive():QMessageBox.warning(self,'请先停止','运行时不能修改模板');return
        try:
            d=XDetect()
            if not d.isChooseFriend():raise ValueError('当前游戏不是已确认的助战列表')
            dialog=ScreenshotTemplateDialog(d.im,self)
            if dialog.exec():self.store.add(dialog.selected,dialog.name.text());self.reload()
        except Exception as e:QMessageBox.warning(self,'无法添加',str(e))

"""Synthetic geometry only; no game images, names, device or account data."""
from contextlib import ExitStack,contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch,Mock
import runpy
import numpy as np

env=runpy.run_path(str(Path(__file__).with_name('test_gui_navigation.py')))
q=env['daily']
import fgoDailyIndexed as indexed
from fgoDailyIndex import DailyScanAccumulator

class World:
    def __init__(self,n=25):
        self.n=n;self.top=99.;self.height=40.;self.scale=(n-1)*187/(535-99)
        self.frames={};self.missing=set();self.local_missing=set();self.stalled=False;self.drags=[];self.swipes=[];self.full_calls=0
    def absolute(self,i):return 140+self.scale*99+i*187
    def entry(self,i,y):return q.DailyQuestEntry(f'未来每日挑战{i:02d} 特级','unknown','unknown','',(0,947,round(y)))
    def capture(self,*args,**kwargs):
        frame=SimpleNamespace(im=np.zeros((720,1280,3),dtype=np.uint8),top=self.top)
        self.frames[id(frame.im)]=frame;return frame
    def entries(self,d,n=0,**kwargs):
        self.full_calls+=1
        result=[self.entry(i,self.absolute(i)-self.scale*d.top) for i in range(self.n)
                if i not in self.missing and 130<=self.absolute(i)-self.scale*d.top<=580]
        d._dailyVerifiedAP={q._title_key(e.title):e.discovered_position[2]+75 for e in result}
        return result
    def observe(self,d,n):return d,self.entries(d,n)
    def local(self,d,y,radius=60):
        result=[self.entry(i,self.absolute(i)-self.scale*d.top) for i in range(self.n)
                if i not in self.local_missing and 130<=self.absolute(i)-self.scale*d.top<=580 and abs(self.absolute(i)-self.scale*d.top-y)<=radius]
        d._dailyVerifiedAP={**getattr(d,'_dailyVerifiedAP',{}),**{q._title_key(e.title):e.discovered_position[2]+75 for e in result}}
        return result
    def swipe(self,d,up,distance=180):
        self.swipes.append(up)
        if not self.stalled:self.top=max(99,min(535,self.top+(-distance if up else distance)/self.scale))
    def drag(self,start,end):
        self.drags.append((start,end))
        if not self.stalled:
            self.top=max(99,min(535,self.top+(end[1]-start[1]) if start[0]==1258 else self.top+(start[1]-end[1])/self.scale))
    @contextmanager
    def patched(self,**extra):
        with TemporaryDirectory() as temp,ExitStack() as stack:
            objects=[(q.XDetect,'region','CN'),(q,'Detect',self.capture),(q,'_isDailyPage',lambda d:True),
                (q,'confirmedDailyPageCN',lambda d,*a:True),
                (q,'_dailyLocatorFrameCN',lambda d:None),(q,'_scrollbar',lambda im:(self.frames[id(im)].top,self.frames[id(im)].top+self.height)),
                (q,'_observeDailyScanPage',self.observe),(q,'_dailyEntriesAt',self.entries),(q,'_swipe_input_only',self.swipe),
                (q,'_menuSwipe',self.drag),(q,'_menuScrollbarDrag',self.drag),(q,'openDailyPageCN',lambda:None),(q.schedule,'sleep',lambda *a:None),
                (indexed,'localEntries',self.local),(indexed,'cachePath',lambda:Path(temp)/'daily-index.json'),
                (indexed,'_cached',None),(indexed,'_invalid',False),(indexed,'_anchors',{}),(indexed,'_dragGain',1.),(indexed,'_dragSamples',[])]
            objects.append((indexed,'_thumbTargetHistory',{}))
            objects.append((indexed,'_thumbHistoryGeometry',None))
            for obj,key,value in objects:stack.enter_context(patch.object(obj,key,value))
            self.touch=stack.enter_context(patch.object(q.fgoDevice.device,'touch'))
            yield self
    def calibrated(self,exclude=()):
        acc=DailyScanAccumulator(q._title_key)
        for f,top in enumerate([*range(99,536,10),535,99]):
            entries=[self.entry(i,self.absolute(i)-self.scale*top) for i in range(self.n)
                     if i not in exclude and 130<=self.absolute(i)-self.scale*top<=580]
            acc.add_frame(entries,(top,top+40),f,{q._title_key(e.title):e.discovered_position[2]+75 for e in entries})
        acc.edge_rechecks.update((q._title_key(self.entry(0,140).title),q._title_key(self.entry(self.n-1,140).title)))
        return acc

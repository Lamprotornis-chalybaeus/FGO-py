"""Local, explicit friend priorities. No automatic servant identity guesses."""
from pathlib import Path
import json,uuid,cv2,numpy as np

class FriendTemplateStore:
    def __init__(self,path):
        self.root=Path(path).resolve();self.config=self.root/'templates.json';self.data={};self.images={}
    def entries(self):
        data=json.loads(self.config.read_text(encoding='utf-8')) if self.config.exists() else {}
        files=sorted(list(self.root.glob('*.png'))+list((self.root/'local').glob('*.png')))
        rows=[]
        for index,path in enumerate(files,1):
            key=path.relative_to(self.root).as_posix();info=data.get(key,{})
            rows.append({'file':key,'name':info.get('name',path.stem),'priority':int(info.get('priority',index)),'enabled':bool(info.get('enabled',True))})
        return sorted(rows,key=lambda row:(row['priority'],row['file']))
    def save(self,rows):
        self.root.mkdir(parents=True,exist_ok=True)
        temp=self.config.with_suffix('.json.tmp');temp.write_text(json.dumps({r['file']:{k:r[k] for k in ('name','priority','enabled')} for r in rows},ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(self.config)
    def add(self,image,name):
        if not str(name).strip():raise ValueError('请填写模板名称')
        if image is None or not image.size:raise ValueError('请选择有效截图区域')
        path=self.root/'local'/f'{uuid.uuid4().hex}.png';path.parent.mkdir(parents=True,exist_ok=True)
        if not cv2.imwrite(str(path),image):raise ValueError('模板图片保存失败')
        rows=self.entries();key=path.relative_to(self.root).as_posix()
        for row in rows:
            if row['file']==key:row.update(name=str(name).strip(),priority=max([r['priority'] for r in rows if r['file']!=key],default=0)+1)
        self.save(rows);return key
    def flush(self):
        self.data={};self.images={}
        for row in self.entries():
            if not row['enabled']:continue
            pixels=cv2.imread(str(self.root/row['file']))
            if pixels is None:continue
            self.data[row['file']]=row;self.images[row['file']]=(pixels,np.max(pixels,axis=2)>>1)
        return self
    def __bool__(self):return bool(self.images)
    def items(self):return self.images.items()
    def orderedItems(self):return list(self.images.items())

def chooseOnScreen(detect,store):
    for file,image in store.orderedItems():
        if point:=detect.findFriend(image):return file,point
    return None

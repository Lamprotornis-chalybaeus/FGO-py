"""Observable drop slots; private screenshots are written only with debug enabled."""
from dataclasses import dataclass,field,asdict
from pathlib import Path
import json,time,re,cv2,numpy as np
from fgoLogging import getLogger
from fgoPaths import paths
logger=getLogger('Drop')
debug=False
debugRoot=paths.logRoot/'drops'

@dataclass
class DropResult:
    recognized:dict=field(default_factory=dict)
    occupied_slots:int=0
    recognized_slots:int=0
    unknown_slots:int=0
    unknown_crops:list=field(default_factory=list)
    currency:dict=field(default_factory=dict)
    currency_amount_unknown:int=0
    slots:list=field(default_factory=list)
    debug_dir:str=''
    errors:list=field(default_factory=list)
    @property
    def stats(self):return dict(occupied_slots=self.occupied_slots,recognized_slots=self.recognized_slots,unknown_slots=self.unknown_slots,currency=dict(self.currency),currency_amount_unknown=self.currency_amount_unknown,debug_dirs=[self.debug_dir] if self.debug_dir else [],errors=list(self.errors))

def templates():
    from fgoMetadata import materialImg
    out=[(name,image,'material') for name,image in materialImg if image is not None]
    root=paths.dataRoot/'fgoImage'/'drop'
    for manifest in sorted(root.glob('**/*.json')):
        try:
            info=json.loads(manifest.read_text(encoding='utf-8'))
            image=manifest.with_suffix('.png')
            pixels=cv2.imread(str(image))
            if pixels is not None and verifiedManifest(info):
                row=(info['name'],pixels,info.get('category','local'))
                out.append(row+(info,) if info.get('match_region')=='card' or info.get('dropped_qp') else row)
        except Exception as e:logger.warning(f'Ignored invalid drop manifest {manifest.name}: {e}')
    return out

def verifiedManifest(info):
    if not info.get('verified') or not info.get('name'):return False
    if info.get('verification')=='external':
        evidence=info.get('evidence',{})
        return bool(evidence.get('visual',{}).get('passed') and evidence.get('visual',{}).get('reference_url') and evidence.get('semantic',{}).get('passed') and evidence.get('semantic',{}).get('source_url'))
    return True # Existing manually confirmed local and legacy manifests.

def templateIconPath(name):
    if name in ('baseQP','droppedQP'):name='QP'
    root=paths.dataRoot/'fgoImage'
    legacy=root/'material'/f'{name}.png'
    if legacy.is_file():return legacy
    for manifest in sorted((root/'drop').glob('**/*.json')):
        try:
            info=json.loads(manifest.read_text(encoding='utf-8'));pixels=manifest.with_suffix('.png')
            if verifiedManifest(info) and info.get('name')==name and pixels.is_file():return pixels
        except (OSError,ValueError):continue
    return None

def currencyLabel(name):
    return {'baseQP':'基础QP','droppedQP':'敌人掉落QP'}.get(name,name)

def slotRect(i,inner=False):
    if inner:return(176+i%7*137,110+i//7*142,253+i%7*137,187+i//7*142)
    return(155+i%7*137,87+i//7*142,273+i%7*137,217+i//7*142)

def occupied(crop):
    # Result overlay is dark; item cards have a continuous illuminated frame.
    # Unknown cards are retained independently of template matches.
    return bool(crop.size and np.mean(crop.max(axis=2)>90)>.025)

def confirmationMatches(pixels,template,info):
    """Require fixed class features in addition to the full card match."""
    if 'confirmation_regions' not in info:return True
    regions=info['confirmation_regions']
    if info.get('match_region')!='card' or not isinstance(regions,list) or not regions:return False
    for rect in regions:
        if not isinstance(rect,(list,tuple)) or len(rect)!=4 or any(type(v) is not int for v in rect):return False
        x,y,r,b=rect
        if not (0<=x<r<=min(pixels.shape[1],template.shape[1]) and 0<=y<b<=min(pixels.shape[0],template.shape[0])):return False
        score=float(cv2.minMaxLoc(cv2.matchTemplate(pixels[y:b,x:r],template[y:b,x:r],cv2.TM_SQDIFF_NORMED))[0])
        if not np.isfinite(score) or score>=.02:return False
    return True

def parseCurrency(text,confidence,threshold):
    number=re.fullmatch(r'\+?\s*(\d{1,3}(?:,\d{3})+|\d+)',str(text).strip())
    return int(number[1].replace(',','')) if number and float(confidence)>=threshold else None

def readCurrencyAmount(crop,ocr):
    """Retry only rejected amounts; every independent read must agree."""
    def read(rect,scale=1):
        x,y,r,b=rect;pixels=crop[y:b,x:r]
        if scale!=1:pixels=cv2.resize(pixels,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC)
        text,confidence=ocr.ocr_single_line(pixels)
        return dict(text=str(text),confidence=float(confidence),rect=list(rect),scale=scale)
    evidence=read((15,91,113,119));amount=parseCurrency(evidence['text'],evidence['confidence'],.85)
    if amount is not None:return amount,evidence
    checks=[read(rect,scale) for rect in ((14,96,115,116),(12,96,117,116)) for scale in (1,2)]
    amounts=[parseCurrency(check['text'],check['confidence'],.90) for check in checks]
    evidence['checks']=checks
    # A syntactically valid original read may veto an inconsistent retry.
    original=parseCurrency(evidence['text'],evidence['confidence'],0)
    if None not in amounts and len(set(amounts))==1 and original in (None,amounts[0]):
        evidence['method']='four_read_agreement';return amounts[0],evidence
    return None,evidence

def detect(image,candidates=None,saveDebug=None):
    if image.shape!=(720,1280,3):raise ValueError('drop screenshot must be 1280x720')
    result=DropResult();candidates=templates() if candidates is None else candidates
    for i in range(21):
        x,y,r,b=slotRect(i);crop=image[y:b,x:r]
        if not occupied(crop):continue
        result.occupied_slots+=1
        x0,y0,x1,y1=slotRect(i,True);icon=image[y0:y1,x0:x1];matches=[]
        for candidate in candidates:
            name,template,category=candidate[:3];info=candidate[3] if len(candidate)>3 else {}
            if category=='currency' and i!=0 and not info.get('dropped_qp'):continue
            if i==0 and category!='currency':continue
            pixels=crop[:118,:118] if info.get('match_region')=='card' else icon
            if template.shape[0]>pixels.shape[0] or template.shape[1]>pixels.shape[1]:continue
            score=float(cv2.minMaxLoc(cv2.matchTemplate(pixels,template,cv2.TM_SQDIFF_NORMED))[0])
            if np.isfinite(score) and score<.02 and confirmationMatches(pixels,template,info):matches.append((name,score,category))
        identities={name for name,_,_ in matches}
        row={'slot':i,'rect':slotRect(i),'inner_rect':slotRect(i,True),'matches':[(n,s) for n,s,_ in matches],'name':None}
        if len(identities)==1:
            name,score,category=min(matches,key=lambda m:m[1]);row.update(name=name,score=score,category=category)
            if category=='currency':
                currencyName='baseQP' if name=='QP' and i==0 else 'droppedQP' if name=='QP' else name
                # Currency amount is separate from the legacy material dict.
                from fgoDetect import OCR
                amount,row['amount_ocr']=readCurrencyAmount(crop,OCR.EN)
                if amount is not None:
                    result.currency[currencyName]=result.currency.get(currencyName,0)+amount
                    if name=='QP':result.currency['QP']=result.currency.get('QP',0)+amount
                else:row['amount_unknown']=True;result.currency_amount_unknown+=1
            else:result.recognized[name]=result.recognized.get(name,0)+1
            result.recognized_slots+=1
        else:
            result.unknown_slots+=1;result.unknown_crops.append({'slot':i,'rect':slotRect(i),'reason':'ambiguous' if matches else 'no template'})
        result.slots.append(row)
    assert result.occupied_slots==result.recognized_slots+result.unknown_slots
    if debug if saveDebug is None else saveDebug:
        try:
            folder=debugRoot/(time.strftime('%Y%m%d-%H%M%S')+f'-{time.time_ns()%1000000000:09}');folder.mkdir(parents=True)
            def save(name,pixels):
                if not cv2.imwrite(str(folder/name),pixels):raise OSError('failed to save '+name)
            result.debug_dir=str(folder);save('result.png',image)
            for i in range(21):
                x,y,r,b=slotRect(i);save(f'slot-{i:02}.png',image[y:b,x:r])
            for unknown in result.unknown_crops:unknown['path']=str(folder/f'slot-{unknown["slot"]:02}.png')
            (folder/'detection.json').write_text(json.dumps(asdict(result),ensure_ascii=False,indent=2),encoding='utf-8')
        except Exception as e:result.errors.append('debug save: '+str(e));logger.exception('Drop debug save failed')
    logger.info(f'occupied={result.occupied_slots} recognized={result.recognized_slots} unknown={result.unknown_slots}; material={result.recognized}; currency={result.currency}')
    return result

def mergeStats(total,part):
    if part.get('incomplete'):total['incomplete']=True
    for key in ('occupied_slots','recognized_slots','unknown_slots','currency_amount_unknown'):total[key]=total.get(key,0)+part.get(key,0)
    for key in ('debug_dirs','errors'):total.setdefault(key,[]).extend(part.get(key,[]))
    for name,count in part.get('currency',{}).items():total.setdefault('currency',{})[name]=total.get('currency',{}).get(name,0)+count
    return total

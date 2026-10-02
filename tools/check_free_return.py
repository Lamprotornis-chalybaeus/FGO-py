"""Offline CN Free Quest boundary check; accepts only saved screenshots."""
import argparse,os,sys
from pathlib import Path
app=Path(__file__).resolve().parents[1]/'FGO-py'
sys.path.insert(0,str(app));os.chdir(app)
import cv2,numpy as np
from fgoDetect import XDetect,XDetectCN
import fgoNavigation as nav
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--expect-free',action='append',default=[])
parser.add_argument('--expect-other',action='append',default=[])
args=parser.parse_args();XDetect.region='CN'
if not args.expect_free and not args.expect_other:parser.error('Provide saved screenshot paths')
for expected,files in ((True,args.expect_free),(False,args.expect_other)):
    for file in files:
        frame=object.__new__(XDetectCN)
        frame.im=cv2.imdecode(np.frombuffer(Path(file).read_bytes(),np.uint8),cv2.IMREAD_COLOR)
        assert frame.im is not None and frame.im.shape==(720,1280,3),file
        # Deliberately reproduce the missing global Free Quest OCR label.
        items=[i for i in nav.labels(frame) if '自由关卡' not in nav.compact(i.text)]
        found=nav.cnFreeQuestReturn(frame,items)
        print(f'{file}: fallback={found}, expected={expected}',flush=True)
        assert found==expected,file

import logging,platform,os,time,sys,threading
from logging.handlers import RotatingFileHandler
from fgoPaths import paths
from copy import copy
from functools import wraps
from inspect import isfunction
from fgoConst import VERSION
if platform.system()=='Windows':(lambda k:k.SetConsoleMode(k.GetStdHandle(-11),7))(__import__('ctypes').windll.kernel32) # -11:STD_OUTPUT_HANDLE, 7:ENABLE_VIRTUAL_TERMINAL_PROCESSING
monoFormatter=logging.Formatter('[%(asctime)s][%(levelname)s]<%(name)s> %(message)s')
if os.getenv('NO_COLOR'):
    def color(*_,**__):return''
    coloredFormatter=monoFormatter
else:
    def color(c=None,f='38'):return'\033[0m'if c is None else f'\033[{f};2;{c>>16&0xFF};{c>>8&0xFF};{c&0xFF}m'
    coloredFormatter=type('ColoredFormatter',(logging.Formatter,),{'__init__':lambda self,*args,**kwargs:logging.Formatter.__init__(self,*args,**kwargs),'format':lambda self,record:((lambda record:(setattr(record,'levelname','\033[{}m[{}]'.format({'DEBUG':'37','INFO':'34','WARNING':'33','CRITICAL':'35','ERROR':'31'}.get(record.levelname,'0'),record.levelname)),logging.Formatter.format(self,record))[-1])(copy(record)))})('\033[32m[%(asctime)s]%(levelname)s\033[36m<%(name)s>\033[0m %(message)s')
paths.logRoot.mkdir(parents=True,exist_ok=True)
(paths.dataRoot/'fgoLog').mkdir(parents=True,exist_ok=True)
for fileHandler in (logging.FileHandler(paths.dataRoot/time.strftime('fgoLog/Log_%Y-%m-%d_%H.%M.%S.txt'),encoding='utf-8'),RotatingFileHandler(paths.logRoot/'fgo-py.log',maxBytes=5*1024*1024,backupCount=3,encoding='utf-8')):
    fileHandler.setFormatter(monoFormatter);fileHandler.setLevel(logging.DEBUG);logging.root.addHandler(fileHandler)
logger=logging.getLogger('fgo')
def _uncaught(kind,error,trace):logger.error('Uncaught exception',exc_info=(kind,error,trace))
sys.excepthook=_uncaught
threading.excepthook=lambda args:_uncaught(args.exc_type,args.exc_value,args.exc_traceback)
(logger.setLevel(logging.DEBUG),logger.addHandler((lambda handler:(handler.setFormatter(coloredFormatter),handler.setLevel(logging.INFO),handler)[-1])(logging.StreamHandler())))
def hijack(name):(lambda handler:(handler.setLevel(logging.INFO),handler.setFormatter(coloredFormatter)))((lambda logger:(logger.setLevel(logging.DEBUG),logger)[-1])(logging.getLogger(name)).handlers[0])
import airtest.core.android
hijack('airtest')
import pponnxcr
hijack('pponnxcr')
def getLogger(name):return logging.getLogger('fgo.'+name)
def logit(logger,level=logging.DEBUG,transform=lambda x:repr(x)[:256]):return lambda func:wraps(func)(lambda*args,**kwargs:(lambda x:(logger.log(level,' '.join((func.__name__,transform(x)))),x)[-1]if x is not None else x)(func(*args,**kwargs)))
def logMeta(logger):return lambda name,bases,attrs:type(name,bases,{i:logit(logger)(j)if i[0]!='_'and isfunction(j)else j.__class__(logit(logger)(j.__func__))if i[0]!='_'and isinstance(j,(classmethod,staticmethod))else j for i,j in attrs.items()})
logger.critical(f'FGO-py {VERSION} PID {os.getpid()}')

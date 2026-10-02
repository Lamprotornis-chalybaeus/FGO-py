import argparse,os,sys
from fgoConst import VERSION
from fgoPaths import initialize,paths

initialize()
try:
    with open(paths.appRoot.parent/'.git'/'HEAD',encoding='utf-8')as f:head=f.read().strip()
except OSError:head='master' if getattr(sys,'frozen',False) else ''
import fgoLogging

parser=argparse.ArgumentParser(description=f'FGO-py {VERSION}')
parser.add_argument('entrypoint',help='Program entry point (default: %(default)s)',type=str.lower,choices=['gui','cli','web'],default='gui'if head.endswith('master')else'cli',nargs='?')
parser.add_argument('-v','--version',help='Show FGO-py version',action='version',version=VERSION)
parser.add_argument('-l','--loglevel',help='Change the console log level (default: %(default)s)',type=str.upper,choices=['DEBUG','INFO','WARNING','CRITICAL','ERROR'],default='INFO')
parser.add_argument('-c','--config',help='Config file path (default: %(default)s)',type=str,default='fgoConfig.json')
parser.add_argument('-r','--readonly',help='Do not save configuration file on exit',action='store_false')
parser.add_argument('--no-color',help='Disable colored console output',action='store_true')
parser.add_argument('--self-check',help='Check local portable data/imports without operating the game',action='store_true')
arg=parser.parse_args()
if arg.self_check:
    from fgoDiagnostics import selfCheck
    selfCheck()
    sys.exit(0)

if arg.no_color:os.environ['NO_COLOR']='1'

match arg.entrypoint:
    case'gui':from fgoGui import main
    case'cli':from fgoCli import main
    case'web':from fgoWebServer import main

fgoLogging.logger.handlers[-1].setLevel(arg.loglevel)

from fgoConfig import Config
config=Config(arg.config)
if not config.runOnce:config.runOnce=VERSION
elif config.runOnce!=VERSION:
    from fgoRunOnce import runOnce
    if runOnce(config):
        config.runOnce=VERSION
        config.save()
        sys.exit()
    config.runOnce=VERSION

if not config.farming:
    from fgoKernel import farming
    farming.stop=True

try:main(config)
except Exception as e:fgoLogging.logger.exception(e)
finally:
    if arg.readonly:config.save()

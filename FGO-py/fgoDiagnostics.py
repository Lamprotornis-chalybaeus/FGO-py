"""Local portable smoke check: files and imports only, no device operations."""
import importlib,json,sys,time
from pathlib import Path
from fgoPaths import paths

def selfCheck():
    from fgoConst import VERSION
    from fgoLogging import getLogger
    modules=('fgoProgress','fgoFriendTemplates','fgoGuiFriendTemplates',
             'fgoGuiResult','fgoNavigation','fgoQuickQuest','fgoEventProgress')
    loaded={name:importlib.import_module(name).__file__ for name in modules}
    import fgoKernel
    fgoKernel.farming.stop=True
    from fgoFriendTemplates import FriendTemplateStore
    from fgoConfig import Config
    config=Config()
    report=dict(version=VERSION,frozen=bool(getattr(sys,'frozen',False)),
                paths={key:str(value) for key,value in vars(paths).items()},
                modules=loaded,drop_recognition=False,
                friend_templates=len(FriendTemplateStore(paths.dataRoot/'fgoImage'/'friend').flush().images),
                saved_device=config.device,battles=0,device_operations=0)
    file=paths.logRoot/'self-check.json'
    file.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    getLogger('Diagnostics').info('Local self-check saved: %s',file)
    return report

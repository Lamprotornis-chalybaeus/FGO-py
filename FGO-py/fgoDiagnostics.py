"""Local portable smoke check: files and imports only, no device operations."""
import importlib,json,sys,time
from pathlib import Path
from fgoPaths import paths

def selfCheck():
    from fgoConst import VERSION
    from fgoLogging import getLogger
    modules=('fgoDrop','fgoProgress','fgoFriendTemplates','fgoGuiFriendTemplates',
             'fgoGuiResult','fgoNavigation','fgoQuickQuest','fgoEventProgress')
    loaded={name:importlib.import_module(name).__file__ for name in modules}
    import fgoKernel,fgoDrop
    fgoKernel.farming.stop=True
    from fgoFriendTemplates import FriendTemplateStore
    from fgoConfig import Config
    config=Config()
    templates=fgoDrop.templates()
    report=dict(version=VERSION,frozen=bool(getattr(sys,'frozen',False)),
                paths={key:str(value) for key,value in vars(paths).items()},
                modules=loaded,drop_templates=len(templates),
                local_drop_names=sorted({r[0] for r in templates if r[2]!='material'}),
                friend_templates=len(FriendTemplateStore(paths.dataRoot/'fgoImage'/'friend').flush().images),
                saved_device=config.device,battles=0,device_operations=0)
    file=paths.logRoot/'self-check.json'
    file.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    getLogger('Diagnostics').info('Local self-check saved: %s',file)
    return report

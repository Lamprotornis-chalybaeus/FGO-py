# Local onedir adaptation of upstream fgoBuild.spec; upstream file stays intact.
from pathlib import Path
import subprocess,os,sys
from PyInstaller.utils.hooks import collect_data_files

app=Path(SPECPATH).resolve();repo=app.parent
tracked=subprocess.check_output(['git','-c',f'safe.directory={repo.as_posix()}','ls-files','FGO-py/fgoImage'],cwd=repo,text=True).splitlines()
datas=[(str(repo/file),str(Path(file).parent.relative_to('FGO-py'))) for file in tracked]
datas.extend((str(file),'.') for file in app.glob('*.qm'))
datas.extend((str(file),'.') for file in app.glob('*.ts'))
datas.extend([(str(app/'fgoIcon.ico'),'.'),(str(app/'fgoTeamup.ini'),'.'),(str(repo/'LICENSE'),'.')])
for package in ('airtest','pponnxcr','pulp'):datas.extend(collect_data_files(package))
modules=['fgoDrop','fgoProgress','fgoFriendTemplates','fgoGuiFriendTemplates','fgoGuiResult','fgoNavigation','fgoQuickQuest','fgoEventProgress','fgoPaths']
originalPath=os.environ.get('PATH','')
# DLL discovery must not inherit Codex's unrelated Poppler/ICU toolchain.
# Qt uses Windows' native unversioned ICU API, not Poppler's versioned ICU.
os.environ['PATH']=os.pathsep.join([str(repo/'.venv'/'Scripts'),sys.base_prefix,
    str(Path(os.environ['SystemRoot'])/'System32'),os.environ['SystemRoot']])
try:
    a=Analysis([str(app/'fgo.py')],pathex=[str(app)],datas=datas,binaries=[],hiddenimports=modules,hookspath=[],runtime_hooks=[],excludes=['IPython','pytest'],noarchive=False)
finally:os.environ['PATH']=originalPath
a.binaries=[row for row in a.binaries if not Path(row[0]).name.lower().startswith('icu')]
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='FGO-py-CN',console=False,contents_directory='.',icon=str(app/'fgoIcon.ico'),upx=False,disable_windowed_traceback=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='FGO-py-CN')

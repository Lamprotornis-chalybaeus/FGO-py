"""Absolute application/resource and writable roots for source and portable builds."""
from dataclasses import dataclass
from pathlib import Path
import os,sys

@dataclass(frozen=True)
class AppPaths:
    appRoot:Path
    resourceRoot:Path
    configRoot:Path
    dataRoot:Path
    logRoot:Path

def resolvePaths(frozen=None,executable=None,moduleFile=None,bundle=None):
    frozen=getattr(sys,'frozen',False) if frozen is None else frozen
    source=Path(moduleFile or __file__).resolve().parent
    app=Path(executable or sys.executable).resolve().parent if frozen else source
    resources=Path(bundle or getattr(sys,'_MEIPASS',app)).resolve() if frozen else source
    return AppPaths(app,resources,app/'config' if frozen else app,app,
                    app/'logs' if frozen else app.parents[1]/'logs')

paths=resolvePaths()

def configFile(file='fgoConfig.json'):
    p=Path(file)
    return p if p.is_absolute() else paths.configRoot/p

def licenseFile(frozen=None):
    frozen=getattr(sys,'frozen',False) if frozen is None else frozen
    return (paths.resourceRoot if frozen else paths.appRoot.parent)/'LICENSE'

def initialize():
    # This local onedir uses contents_directory='.'; legacy relative read-only
    # assets therefore resolve through appRoot regardless of the launch cwd.
    for directory in (paths.configRoot,paths.logRoot,paths.dataRoot/'fgoLog',paths.dataRoot/'fgoTemp',paths.dataRoot/'fgoImage'/'friend'/'local'):
        directory.mkdir(parents=True,exist_ok=True)
    os.chdir(paths.appRoot)
    for name in ('stdout','stderr'):
        if getattr(sys,name) is None:setattr(sys,name,open(paths.logRoot/'console.log','a',encoding='utf-8',buffering=1))

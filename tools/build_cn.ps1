param([string]$DistRoot='C:\FGO-Automation\dist',[switch]$CopyLocalTemplates)
$ErrorActionPreference='Stop'
$DistRoot=[IO.Path]::GetFullPath($DistRoot)
$ExpectedOutput=[IO.Path]::GetFullPath((Join-Path $DistRoot 'FGO-py-CN'))
if (!(($ExpectedOutput).StartsWith($DistRoot.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)) -or (Split-Path -Leaf $ExpectedOutput) -ne 'FGO-py-CN') {throw 'Invalid managed build output'}
$ProjectRoot=Split-Path -Parent $PSScriptRoot
$PythonPath=Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$SpecPath=Join-Path $ProjectRoot 'FGO-py\fgoBuildCN.spec'
$PortableRoot=Join-Path $DistRoot 'FGO-py-CN'
# COLLECT recreates its output. Preserve existing portable user data first.
$BackupRoot=Join-Path $ProjectRoot ('build\user-data-'+[guid]::NewGuid().ToString('N'))
$WritablePaths=@('config','logs','fgoLog','fgoTemp','fgoImage\friend\local','fgoImage\drop\local','fgoImage\friend\templates.json')
foreach ($RelativePath in $WritablePaths) {
    $ExistingPath=Join-Path $PortableRoot $RelativePath
    if (Test-Path -LiteralPath $ExistingPath) {
        $BackupPath=Join-Path $BackupRoot $RelativePath
        New-Item -ItemType Directory -Path (Split-Path -Parent $BackupPath) -Force | Out-Null
        Copy-Item -LiteralPath $ExistingPath -Destination $BackupPath -Recurse -Force
    }
}
& $PythonPath -m PyInstaller --noconfirm --distpath $DistRoot --workpath (Join-Path $ProjectRoot 'build\cn') $SpecPath
if ($LASTEXITCODE -ne 0) {throw 'PyInstaller build failed'}
$PortableRoot=Join-Path $DistRoot 'FGO-py-CN'
foreach ($Folder in @('logs','config','fgoLog','fgoTemp','fgoImage\friend\local','fgoImage\drop\local')) {New-Item -ItemType Directory -Path (Join-Path $PortableRoot $Folder) -Force | Out-Null}
foreach ($RelativePath in $WritablePaths) {
    $SavedPath=Join-Path $BackupRoot $RelativePath
    $TargetPath=Join-Path $PortableRoot $RelativePath
    if (Test-Path -LiteralPath $SavedPath -PathType Container) {Copy-Item -Path (Join-Path $SavedPath '*') -Destination $TargetPath -Recurse -Force}
    elseif (Test-Path -LiteralPath $SavedPath -PathType Leaf) {Copy-Item -LiteralPath $SavedPath -Destination $TargetPath -Force}
}
$ConfigPath=Join-Path $PortableRoot 'config\fgoConfig.json'
if (!(Test-Path -LiteralPath $ConfigPath)) {
    $SafeDefaults=@{device='/bs5_Rvc64';farming=$false;closeToTray=$false;dropDebug=$false}
    [IO.File]::WriteAllText($ConfigPath,($SafeDefaults|ConvertTo-Json),[Text.UTF8Encoding]::new($false))
}
if ($CopyLocalTemplates) {
    foreach ($RelativePath in @('fgoImage\friend\local','fgoImage\drop\local','fgoImage\friend\templates.json')) {
        $SourcePath=Join-Path $ProjectRoot ('FGO-py\'+$RelativePath)
        $TargetPath=Join-Path $PortableRoot $RelativePath
        if (Test-Path -LiteralPath $SourcePath -PathType Container) {Copy-Item -Path (Join-Path $SourcePath '*') -Destination $TargetPath -Recurse -Force}
        elseif (Test-Path -LiteralPath $SourcePath -PathType Leaf) {Copy-Item -LiteralPath $SourcePath -Destination $TargetPath -Force}
    }
}
Write-Output $PortableRoot

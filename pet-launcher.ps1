param(
    [string]$DataDir,[string]$PythonExe,
    [switch]$Install,[switch]$Uninstall,
    [switch]$CreateDesktop,[switch]$RemoveDesktop,
    [switch]$CheckOnly
)
$ErrorActionPreference='Stop'
$pythonExe=if ($PythonExe) { $PythonExe } elseif ($env:AGENT_PET_PYTHON) { $env:AGENT_PET_PYTHON } else { Join-Path $PSScriptRoot '.venv/Scripts/python.exe' }
if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) { throw 'Install requirements into .venv first, or set AGENT_PET_PYTHON.' }
if ($DataDir) { $env:AGENT_PET_DATA_DIR=$DataDir }
$env:PYTHONDONTWRITEBYTECODE='1'
if ($CheckOnly) {
    & $pythonExe -X utf8 (Join-Path $PSScriptRoot 'run.py') --check
    exit $LASTEXITCODE
}
$pathsText=& $pythonExe -X utf8 (Join-Path $PSScriptRoot 'maintenance.py') --paths
if ($LASTEXITCODE -ne 0) { throw 'Invalid data directory.' }
$paths=($pathsText -join "`n") | ConvertFrom-Json
$DataDir=[string]$paths.data
if ($Install -or $Uninstall -or $CreateDesktop -or $RemoveDesktop) {
    $linkPath=if ($Install -or $Uninstall) { [string]$paths.startup } else { [string]$paths.desktop }
    if ($Uninstall -or $RemoveDesktop) {
        if (Test-Path -LiteralPath $linkPath) { Remove-Item -LiteralPath $linkPath }
        exit 0
    }
    $shell=New-Object -ComObject WScript.Shell
    $shortcut=$shell.CreateShortcut($linkPath)
    $shortcut.TargetPath=(Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe')
    $shortcut.Arguments='-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "'+$PSCommandPath+'" -DataDir "'+$DataDir+'" -PythonExe "'+$pythonExe+'"'
    $shortcut.WorkingDirectory=$PSScriptRoot
    $shortcut.Description='Agent Desktop Pet'
    $shortcut.Save()
    exit 0
}
# This is the only cache removal path; Python verifies the exact profile path,
# refuses reparse points and waits for the old process without terminating it.
& $pythonExe -X utf8 (Join-Path $PSScriptRoot 'maintenance.py') --pending-cache
if ($LASTEXITCODE -ne 0) { throw 'Cache restart was not safe; request preserved.' }
& $pythonExe -X utf8 (Join-Path $PSScriptRoot 'run.py') --check
if ($LASTEXITCODE -ne 0) { throw 'Complete the preflight requirements before starting.' }
New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
$runFile=Join-Path $PSScriptRoot 'run.py'
$pythonw=Join-Path ([System.IO.Path]::GetDirectoryName($pythonExe)) 'pythonw.exe'
if (Test-Path -LiteralPath $pythonw) { $pythonExe=$pythonw }
Start-Process -FilePath $pythonExe -ArgumentList @('-X','utf8',('"'+$runFile+'"')) -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $DataDir 'launcher-out.log') -RedirectStandardError (Join-Path $DataDir 'launcher-error.log')

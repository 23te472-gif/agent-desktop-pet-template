# Launcher used by the settings UI, shortcuts and optional startup entry.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonExe = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw 'Run 安装依赖.cmd before using the background launcher.'
}
# A cache restart waits for the requesting instance to close first.
$requestFile = Join-Path $PSScriptRoot 'clear-cache.request'
if (Test-Path -LiteralPath $requestFile) {
    $requestPid = 0
    if ([int]::TryParse((Get-Content -LiteralPath $requestFile -Raw).Trim(), [ref]$requestPid)) {
        Wait-Process -Id $requestPid -Timeout 20 -ErrorAction SilentlyContinue
        if (Get-Process -Id $requestPid -ErrorAction SilentlyContinue) { throw 'Pet is still closing.' }
    } else { throw 'Invalid cache restart request.' }
    $cacheTarget = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '.webview2'))
    $expectedTarget = [System.IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\') + '\.webview2'
    if ($cacheTarget -ne $expectedTarget) { throw 'Cache target validation failed.' }
    if (Test-Path -LiteralPath $cacheTarget) {
        if ((Get-Item -LiteralPath $cacheTarget).Attributes -band [System.IO.FileAttributes]::ReparsePoint) { throw 'Refusing linked cache folder.' }
        Remove-Item -LiteralPath $cacheTarget -Recurse -Force
    }
    Remove-Item -LiteralPath $requestFile -Force
}
Start-Process -FilePath $pythonExe -ArgumentList @('run.py') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden

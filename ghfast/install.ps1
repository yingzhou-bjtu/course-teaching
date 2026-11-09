<#
.SYNOPSIS
    Windows 一行安装：powershell -ExecutionPolicy Bypass -File .\install.ps1
.DESCRIPTION
    找到 Python 3.8+，把 ghfast 安装到 %USERPROFILE%\.local\bin，并生成 ghfast.cmd。
#>
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$candidates = @("python", "python3", "py")
$exe = $null
foreach ($c in $candidates) {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd) { $exe = $cmd.Source; break }
}
if (-not $exe) {
    Write-Error "需要 Python 3.8+（未找到 python / python3 / py）。安装：winget install Python.Python.3.12"
    exit 1
}

& $exe -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Python 版本过低，需要 3.8+"
    exit 1
}

& $exe ghfast.py install @args
exit $LASTEXITCODE

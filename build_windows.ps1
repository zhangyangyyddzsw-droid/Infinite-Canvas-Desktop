param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $ProjectRoot ".venv-desktop"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $PythonExe)) {
    python -m venv $VenvDir
}

& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -r (Join-Path $ProjectRoot "requirements-desktop.txt")
& $PythonExe -m PyInstaller --noconfirm --clean (Join-Path $ProjectRoot "InfiniteCanvas.spec")

$AppExe = Join-Path $ProjectRoot "dist\InfiniteCanvas\InfiniteCanvas.exe"
if (-not (Test-Path -LiteralPath $AppExe)) {
    throw "Desktop build did not produce $AppExe"
}
Write-Host "Desktop build ready: $AppExe"

if (-not $SkipInstaller) {
    $Iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($Iscc) {
        $AppVersion = (Get-Content -Raw (Join-Path $ProjectRoot "VERSION")).Trim()
        & $Iscc.Source "/DMyAppVersion=$AppVersion" (Join-Path $ProjectRoot "installer\InfiniteCanvas.iss")
    } else {
        Write-Warning "Inno Setup was not found. The portable desktop build is complete; installer generation was skipped."
    }
}

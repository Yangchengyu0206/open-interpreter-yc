#Requires -Version 5.1
<#
.SYNOPSIS
  One-click deploy: create .venv with uv and install this project (editable).

.PARAMETER FreshVenv
  Remove existing .venv before creating a new one.

.PARAMETER SkipTavily
  Do not install tavily-python (installed by default).

.PARAMETER NoInstallUv
  Fail immediately if uv is not found; do not auto-download.
#>
param(
    [switch]$FreshVenv,
    [switch]$SkipTavily,
    [switch]$NoInstallUv
)

Set-StrictMode -Off

# ---------- 1. Locate project root ----------
$scriptPath = $null
if ($PSCommandPath)                        { $scriptPath = $PSCommandPath }
elseif ($MyInvocation.MyCommand.Path)      { $scriptPath = $MyInvocation.MyCommand.Path }

if ($scriptPath) {
    $scriptDir = Split-Path -Parent $scriptPath
    $candidate = Split-Path -Parent $scriptDir
} else {
    $scriptDir = $null
    $candidate = $null
}

if ($candidate -and (Test-Path (Join-Path $candidate "pyproject.toml"))) {
    $Root = $candidate
} elseif ($scriptDir -and (Test-Path (Join-Path $scriptDir "pyproject.toml"))) {
    $Root = $scriptDir
} else {
    $Root = (Get-Location).Path
}

if (-not $Root -or -not (Test-Path -LiteralPath $Root)) {
    Write-Host "[ERR] Cannot locate project root (pyproject.toml). Please cd into the project first."
    exit 1
}
Set-Location -LiteralPath $Root

# ---------- 2. Python version ----------
$PyTag = if ($env:OI_UV_PYTHON) { $env:OI_UV_PYTHON } else { "3.11" }

# ---------- 3. Path constants ----------
$venvPath = Join-Path $Root ".venv"
$pyExe    = Join-Path $venvPath "Scripts\python.exe"

Write-Host ""
Write-Host "============================================================"
Write-Host " open-interpreter-yc -- uv one-click deploy"
Write-Host "============================================================"
Write-Host " Root    : $Root"
Write-Host " .venv   : $venvPath"
Write-Host " Python  : $PyTag"
Write-Host "============================================================"
Write-Host ""

# ---------- 4. Ensure uv is available ----------
function _HaveUv { return [bool](Get-Command uv -ErrorAction SilentlyContinue) }

function _AddUvPaths {
    $candidates = @(
        (Join-Path $env:USERPROFILE ".local\bin"),
        (Join-Path $env:USERPROFILE ".cargo\bin"),
        (Join-Path $env:LOCALAPPDATA "Programs\uv")
    )
    foreach ($p in $candidates) {
        if ($p -and (Test-Path -LiteralPath $p)) {
            if ($env:Path -notlike "*$p*") {
                $env:Path = "$p;$env:Path"
            }
        }
    }
}

_AddUvPaths

if (-not (_HaveUv)) {
    if ($NoInstallUv) {
        Write-Host "[ERR] uv not found and -NoInstallUv was specified."
        Write-Host "      Install uv manually and add it to PATH, then retry."
        exit 1
    }
    Write-Host "[*] uv not found -- running official install script (needs internet) ..."
    try {
        & powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    } catch {
        Write-Host "[ERR] Auto-install failed: $_"
        Write-Host "      Install uv manually. See docs/DEPLOY_UV.md"
        exit 1
    }
    _AddUvPaths
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath    = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path    = "$machinePath;$userPath"
    _AddUvPaths
}

if (-not (_HaveUv)) {
    Write-Host "[ERR] uv still not found after install. Please restart PowerShell and retry."
    exit 1
}

Write-Host "[*] uv version: $(& uv --version 2>&1)"

# ---------- 5. Remove existing venv if -FreshVenv ----------
if ($FreshVenv -and (Test-Path -LiteralPath $venvPath)) {
    Write-Host "[*] -FreshVenv: removing existing .venv ..."
    Remove-Item -LiteralPath $venvPath -Recurse -Force
}

# ---------- 6. Install requested Python ----------
Write-Host "[*] uv python install $PyTag ..."
& uv python install $PyTag
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    Write-Host "[WARN] uv python install exited $LASTEXITCODE (may already be installed; continuing)."
}

# ---------- 7. Create venv ----------
if (Test-Path -LiteralPath $venvPath) {
    Write-Host "[*] .venv already exists; using --allow-existing (add -FreshVenv to rebuild)."
    & uv venv --python $PyTag --allow-existing $venvPath
} else {
    Write-Host "[*] Creating .venv ..."
    & uv venv --python $PyTag $venvPath
}
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    Write-Host "[ERR] uv venv failed (exit $LASTEXITCODE)."
    exit 1
}

# ---------- 8. Verify python.exe exists ----------
if (-not $pyExe -or -not (Test-Path -LiteralPath $pyExe)) {
    Write-Host "[ERR] After venv creation, python.exe not found at: $pyExe"
    exit 1
}

# ---------- 9. Upgrade pip ----------
Write-Host "[*] uv pip install -U pip ..."
& uv pip install -U pip --python $pyExe
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    Write-Host "[WARN] pip upgrade exited $LASTEXITCODE (continuing)."
}

# ---------- 10. Install project (editable) ----------
Write-Host "[*] uv pip install -e . ..."
& uv pip install -e $Root --python $pyExe
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    Write-Host "[ERR] Project install failed (exit $LASTEXITCODE)."
    exit 1
}

# ---------- 11. Install tavily-python ----------
if (-not $SkipTavily) {
    Write-Host "[*] uv pip install tavily-python ..."
    & uv pip install tavily-python --python $pyExe
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        Write-Host "[WARN] tavily-python exited $LASTEXITCODE (optional; continuing)."
    }
}

# ---------- 12. Done ----------
Write-Host ""
Write-Host "[OK] Deploy complete!"
Write-Host ""
Write-Host "     Next steps:"
Write-Host "       A) Double-click start.bat  --> choose [1] Run"
Write-Host "       B) Or in this terminal:"
Write-Host "            .\.venv\Scripts\Activate.ps1"
Write-Host "            interpreter"
Write-Host ""
exit 0

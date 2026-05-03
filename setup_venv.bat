@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [*] Checking Python 3.12 launcher "py -3.12" ...
py -3.12 -c "import sys; exit(0 if sys.version_info[:2]==(3,12) else 1)" 2>nul
if errorlevel 1 (
  echo [X] 找不到 Python 3.12。
  echo     請安裝: https://www.python.org/downloads/
  echo     安裝時勾選 「Add Python to PATH」，並確認「Install launcher for all users」。
  echo     若已裝但仍失敗，在 PowerShell 執行: py -0p   確認有 3.12。
  pause
  exit /b 1
)

echo [*] Creating virtual environment ".venv" ...
if exist ".venv\" rmdir /s /q ".venv"
py -3.12 -m venv .venv
if errorlevel 1 (
  echo [X] venv creation failed.
  pause
  exit /b 1
)

echo [*] Upgrading pip ...
".venv\Scripts\python.exe" -m pip install -U pip
if errorlevel 1 (
  echo [X] pip upgrade failed.
  pause
  exit /b 1
)

echo [*] Installing open-interpreter in editable mode...
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 (
  echo [X] pip install failed.
  pause
  exit /b 1
)

echo.
echo [OK] Done. Virtual env is at: %CD%\.venv
echo      Run interpreter:  run_local.bat
echo      Or manually:
echo        .venv\Scripts\activate
echo        interpreter --profile hf_router.py
echo.
pause

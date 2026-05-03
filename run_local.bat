@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\interpreter.exe" (
  echo [X] 找不到 .venv 或 interpreter，請先雙擊執行 setup_venv.bat
  pause
  exit /b 1
)

echo.
echo 請輸入 HuggingFace HF_TOKEN（貼上後按 Enter；留空則使用已設定的系統環境變數 HF_TOKEN）
set /p HF_TOKEN_INPUT=HF_TOKEN: 

if not "%HF_TOKEN_INPUT%"=="" (
  set "HF_TOKEN=%HF_TOKEN_INPUT%"
)

if "%HF_TOKEN%"=="" (
  echo [X] 未提供 Token，請重新執行並貼上 HF_TOKEN，或在 Windows 先設定使用者環境變數 HF_TOKEN。
  pause
  exit /b 1
)

echo.
".venv\Scripts\interpreter.exe" --profile hf_router_skills.py

pause

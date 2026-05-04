@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

REM 傳入參數範例（選用）：
REM   Deploy-OneClick.cmd -FreshVenv
REM   Deploy-OneClick.cmd -SkipTavily
REM   Deploy-OneClick.cmd -NoInstallUv

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\deploy_uv_oneclick.ps1" %*
set "EC=%ERRORLEVEL%"
echo.
if not "%EC%"=="0" (
    echo [FAIL] 部署失敗，錯誤碼 %EC%。
    pause
    exit /b %EC%
)
echo 視窗將於 5 秒後關閉；若要保留日誌請按任意鍵。
timeout /t 5 /nobreak >nul
exit /b 0

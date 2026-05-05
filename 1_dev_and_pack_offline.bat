@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo Online Machine: Build and Pack (Offline)
echo ========================================
echo.

where docker >nul 2>&1
if errorlevel 1 (
    echo [ERR] docker command not found.
    pause
    exit /b 1
)

docker version >nul 2>&1
if errorlevel 1 (
    echo [ERR] Docker daemon is not running.
    echo       Please start Docker Desktop first.
    pause
    exit /b 1
)

set "IMAGE_TAG=open-interpreter-yc"
set "TAR_NAME=open_interpreter_yc_image.tar"

echo [Step A] Build image: %IMAGE_TAG%
docker build -t "%IMAGE_TAG%" "."
if errorlevel 1 (
    echo [ERR] Build failed.
    pause
    exit /b 1
)
echo [OK] Build complete.
echo.

set /p "PACK=Step B: Export image for offline deploy? (y/n): "
if /i not "!PACK!"=="y" (
    echo Skip export.
    pause
    exit /b 0
)

echo.
echo [Step C] Export image to %TAR_NAME%
if exist "%TAR_NAME%" del /f /q "%TAR_NAME%" >nul 2>&1
docker save -o "%TAR_NAME%" "%IMAGE_TAG%"
if errorlevel 1 (
    echo [ERR] docker save failed.
    pause
    exit /b 1
)

echo [OK] %TAR_NAME% created.
for %%A in ("%TAR_NAME%") do echo      Size: %%~zA bytes
echo.
echo Copy these files to offline machine:
echo   - %TAR_NAME%
echo   - .env
echo   - start.bat / manage.bat (optional helper scripts)
echo.
echo Then run: 2_offline_deploy.bat
echo.
pause
exit /b 0


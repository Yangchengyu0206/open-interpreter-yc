@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo Offline Machine: Deploy Script
echo ========================================
echo.

set "IMAGE_TAG=open-interpreter-yc"
set "TAR_NAME=open_interpreter_yc_image.tar"
set "CTR_NAME=oi-yc"
set "PROFILE=env_driven.py"

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

echo Check required files...
if not exist "%TAR_NAME%" (
    echo [ERR] Missing %TAR_NAME%.
    echo       Copy it from the online machine first.
    pause
    exit /b 1
)
echo [OK] %TAR_NAME% found.

if not exist ".env" (
    echo [WARN] .env not found.
    echo       You can still run, but model/keys may be missing.
)
echo.

echo [Step A] Load image from tar...
docker load -i "%TAR_NAME%"
if errorlevel 1 (
    echo [ERR] docker load failed.
    pause
    exit /b 1
)
echo [OK] Image loaded.
echo.

echo [Step B] Verify image...
docker images | findstr /i "%IMAGE_TAG%"
echo.

echo [Step C] Start container (interactive)...
echo          Command: interpreter --profile %PROFILE%
docker rm -f "%CTR_NAME%" >nul 2>&1

set "_ENV="
if exist ".env" set "_ENV=--env-file "".env"""

if not exist "workspace" mkdir "workspace" >nul 2>&1

docker run -it --name "%CTR_NAME%" --rm !_ENV! -v "%cd%\workspace:/workspace" -w /workspace "%IMAGE_TAG%" interpreter --profile %PROFILE%
set "EC=!ERRORLEVEL!"
echo.
if not "!EC!"=="0" (
    echo [WARN] Container exited with code !EC!.
    echo        Check .env settings and profile values.
) else (
    echo [OK] Session finished.
)
echo.
pause
exit /b 0


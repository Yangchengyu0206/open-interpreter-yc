@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

set "ROOT=%~dp0"
set "IMAGE_TAG=open-interpreter-yc"
set "CTR_NAME=oi-yc"
set "OI_PROFILE=env_driven.py"

REM Load .env and local_tokens.bat
if exist "%ROOT%local_tokens.bat" call "%ROOT%local_tokens.bat"

:MENU
cls
echo ============================================================
echo  Open Interpreter YC  --  Docker Launcher
echo ============================================================
echo.
echo  Image  : %IMAGE_TAG%
echo  Profile: %OI_PROFILE%
if defined HF_TOKEN (
    echo  HF_TOKEN     : !HF_TOKEN:~0,8!...
) else (
    echo  HF_TOKEN     : NOT SET
)
if defined TAVILY_API_KEY (
    echo  Tavily       : !TAVILY_API_KEY:~0,8!...
) else (
    echo  Tavily       : NOT SET
)
echo.
echo  [1] Build image
echo  [2] Run ^(interactive -it^)
echo  [3] Run ^(detached^)
echo  [4] Stop / remove container
echo  [5] View logs
echo  [6] Enter container shell
echo  [7] Build + Run ^(rebuild and run^)
echo  [8] Docker advanced menu ^(manage.bat^)
echo  [9] Export image ^(.tar for offline use^)
echo  [0] Exit
echo.

docker --version >nul 2>&1
if !errorlevel! neq 0 (
    echo  [WARN] Docker not running.
)

set /p "C=Enter 0-9: "
if "!C!"=="" goto MENU
if "!C!"=="1" goto BUILD
if "!C!"=="2" goto RUN_IT
if "!C!"=="3" goto RUN_DETACHED
if "!C!"=="4" goto STOP
if "!C!"=="5" goto LOGS
if "!C!"=="6" goto SHELL
if "!C!"=="7" goto REBUILD_RUN
if "!C!"=="8" goto MANAGE
if "!C!"=="9" goto EXPORT
if "!C!"=="0" goto END
goto MENU

REM ---------------------------------------------------------------------------
:BUILD
echo.
echo [*] Building %IMAGE_TAG% ...
docker build -t "%IMAGE_TAG%" "%ROOT%."
if !errorlevel! equ 0 (echo [OK] Build complete) else (echo [FAIL] Build failed)
pause & goto MENU

REM ---------------------------------------------------------------------------
:RUN_IT
echo.
echo [*] Interactive run (Ctrl+D or type exit to quit)
call :ENV_ARGS
if defined WORKDIR (
    echo     WORKDIR: "%WORKDIR%" to /workspace
    docker run -it --rm !_ENV! -v "%WORKDIR%:/workspace" -w /workspace "%IMAGE_TAG%" interpreter --profile %OI_PROFILE%
) else (
    docker run -it --rm !_ENV! -v "%ROOT%workspace:/workspace" -w /workspace "%IMAGE_TAG%" interpreter --profile %OI_PROFILE%
)
goto MENU

REM ---------------------------------------------------------------------------
:RUN_DETACHED
echo.
echo [*] Starting detached container %CTR_NAME% ...
docker rm -f "%CTR_NAME%" 2>nul
call :ENV_ARGS
if defined WORKDIR (
    docker run -d --name "%CTR_NAME%" !_ENV! -v "%WORKDIR%:/workspace" -w /workspace "%IMAGE_TAG%" interpreter --profile %OI_PROFILE%
) else (
    docker run -d --name "%CTR_NAME%" !_ENV! -v "%ROOT%workspace:/workspace" -w /workspace "%IMAGE_TAG%" interpreter --profile %OI_PROFILE%
)
if !errorlevel! equ 0 (
    echo [OK] Started
    docker ps --filter "name=%CTR_NAME%"
) else (
    echo [FAIL]
)
pause & goto MENU

REM ---------------------------------------------------------------------------
:STOP
echo.
echo [*] Stopping and removing %CTR_NAME% ...
docker stop "%CTR_NAME%" 2>nul
docker rm "%CTR_NAME%" 2>nul
echo [OK]
pause & goto MENU

REM ---------------------------------------------------------------------------
:LOGS
echo.
echo [*] logs -f (Ctrl+C to stop)
docker logs -f "%CTR_NAME%"
goto MENU

REM ---------------------------------------------------------------------------
:SHELL
echo.
echo [*] Enter container shell ...
docker exec -it "%CTR_NAME%" /bin/bash
if !errorlevel! neq 0 docker exec -it "%CTR_NAME%" /bin/sh
goto MENU

REM ---------------------------------------------------------------------------
:REBUILD_RUN
echo.
echo [*] Build + interactive run ...
docker build -t "%IMAGE_TAG%" "%ROOT%."
if !errorlevel! neq 0 ( echo [FAIL] Build failed & pause & goto MENU )
call :ENV_ARGS
if defined WORKDIR (
    docker run -it --rm !_ENV! -v "%WORKDIR%:/workspace" -w /workspace "%IMAGE_TAG%" interpreter --profile %OI_PROFILE%
) else (
    docker run -it --rm !_ENV! -v "%ROOT%workspace:/workspace" -w /workspace "%IMAGE_TAG%" interpreter --profile %OI_PROFILE%
)
goto MENU

REM ---------------------------------------------------------------------------
:MANAGE
if exist "%ROOT%manage.bat" (
    call "%ROOT%manage.bat"
) else (
    echo [ERR] manage.bat not found.
    pause
)
goto MENU

REM ---------------------------------------------------------------------------
:EXPORT
echo.
set /p "EXPORT_PATH=Export path (Enter = open-interpreter-yc.tar): "
if "!EXPORT_PATH!"=="" set "EXPORT_PATH=%ROOT%open-interpreter-yc.tar"
docker save -o "!EXPORT_PATH!" "%IMAGE_TAG%"
if !errorlevel! equ 0 (
    echo [OK] !EXPORT_PATH!
    for %%A in ("!EXPORT_PATH!") do echo Size: %%~zA bytes
) else echo [FAIL]
pause & goto MENU

REM ---------------------------------------------------------------------------
:END
echo Bye.
endlocal
exit /b 0

REM ---------------------------------------------------------------------------
:ENV_ARGS
set "_ENV="
if exist "%ROOT%.env" set "_ENV=!_ENV! --env-file ""%ROOT%.env"""
if defined HF_TOKEN if /I not "!HF_TOKEN!"=="PASTE_HF_TOKEN" set "_ENV=!_ENV! -e HF_TOKEN=!HF_TOKEN!"
if defined TAVILY_API_KEY if /I not "!TAVILY_API_KEY!"=="PASTE_TAVILY_KEY" set "_ENV=!_ENV! -e TAVILY_API_KEY=!TAVILY_API_KEY!"
if defined CUSTOM_SKILLS_DIR set "_ENV=!_ENV! -e CUSTOM_SKILLS_DIR=!CUSTOM_SKILLS_DIR!"
goto :eof

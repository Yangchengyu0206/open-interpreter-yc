@echo off
REM Do NOT use UTF-8 with chcp 65001 here: cmd.exe parses this file in OEM/PRC before run;
REM parentheses in echo MUST be escaped as ^(^) or omitted to avoid bogus blocks.
setlocal EnableDelayedExpansion
cd /d "%~dp0"
chcp 65001 >nul

REM Put secrets in local_tokens.bat - keep out of git
if exist "local_tokens.bat" call local_tokens.bat

set "IMAGE_TAG=open-interpreter-yc"
set "CTR_NAME=oi-yc-dev"
set "OI_PROFILE=hf_router.py"

:MAIN
cls
echo ========================================
echo Open Interpreter YC - Docker helper
echo ========================================
echo.
echo Working dir : %cd%
echo Image tag   : %IMAGE_TAG%
echo Profile     : %OI_PROFILE%
if defined CTR_NAME echo Container : %CTR_NAME%
echo.

docker --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Docker not installed or not running.
    pause
    exit /b 1
)

if not defined HF_TOKEN (
    echo [WARN] HF_TOKEN not set ^(HF Router needs Hugging Face token^).
    echo        Use env, local_tokens.bat, or menu 12 / .env loaders in run_local.bat
    echo.
)

echo Commands:
echo   [1]  Build image
echo   [2]  Run REPL interactive - docker run -it --rm
echo   [3]  Run REPL detached  - docker run -d named %CTR_NAME%
echo   [4]  Stop/remove detached container %CTR_NAME%
echo   [5]  docker logs -f %CTR_NAME%
echo   [6]  docker exec shell ^(bash/sh^)
echo   [7]  docker ps - list containers
echo   [8]  docker images tag + docker system df
echo   [9]  docker build ^& detached run ^(rebuild restart^)
echo   [10] docker system prune -f
echo   [11] docker save tarball
echo   [12] Session: set HF_TOKEN, profile, WORKDIR ^(memory only^)
echo   [0]  Exit
echo.

set /p choice="Enter 0-12: "
if "!choice!"=="" goto MAIN

if "!choice!"=="1" goto BUILD
if "!choice!"=="2" goto RUN_INTERACTIVE
if "!choice!"=="3" goto RUN_DETACHED
if "!choice!"=="4" goto STOPCTR
if "!choice!"=="5" goto LOGS
if "!choice!"=="6" goto SHELLCTR
if "!choice!"=="7" goto PS
if "!choice!"=="8" goto IMAGESDF
if "!choice!"=="9" goto REBUILD_DETACHED
if "!choice!"=="10" goto PRUNE
if "!choice!"=="11" goto EXPORT_IMG
if "!choice!"=="12" goto ENV_SESSION
if "!choice!"=="0" goto END
goto MAIN

:BUILD
echo.
echo [1] Building %IMAGE_TAG% ...
docker build -t "%IMAGE_TAG%" .
if !errorlevel! equ 0 (echo [OK] Build ok) else (echo [FAIL] Build failed)
goto PAUSE

:RUN_INTERACTIVE
echo.
echo [2] Interactive run - Ctrl+C exits container.
call :DOCKER_ENV_ARGS

if defined WORKDIR (
    echo WORKDIR: "%WORKDIR%" to /workspace
    docker run -it --rm !ENV_ARGS! -v "%WORKDIR%:/workspace" -w /workspace "%IMAGE_TAG%" interpreter --profile %OI_PROFILE%
) else (
    docker run -it --rm !ENV_ARGS! "%IMAGE_TAG%" interpreter --profile %OI_PROFILE%
)
goto MAIN

:RUN_DETACHED
echo.
echo [3] Detached container: %CTR_NAME%
call :DOCKER_ENV_ARGS
docker rm -f "%CTR_NAME%" 2>nul

if defined WORKDIR (
    echo WORKDIR: "%WORKDIR%" to /workspace
    docker run -d --name "%CTR_NAME%" !ENV_ARGS! -v "%WORKDIR%:/workspace" -w /workspace "%IMAGE_TAG%" interpreter --profile %OI_PROFILE%
) else (
    docker run -d --name "%CTR_NAME%" !ENV_ARGS! "%IMAGE_TAG%" interpreter --profile %OI_PROFILE%
)
if !errorlevel! equ 0 (
    echo [OK] Started.
    timeout /t 2 /nobreak >nul
    docker ps --filter "name=%CTR_NAME%"
) else (
    echo [FAIL] Start failed.
)
goto PAUSE

:STOPCTR
echo.
echo [4] Stop/remove %CTR_NAME%
docker stop "%CTR_NAME%" 2>nul
docker rm "%CTR_NAME%" 2>nul
if !errorlevel! equ 0 (echo [OK]) else (echo [INFO] Gone or absent)
goto PAUSE

:LOGS
echo.
echo [5] logs -f ^(Ctrl+C to stop^)
docker logs -f "%CTR_NAME%"
goto MAIN

:SHELLCTR
echo.
echo [6] exec bash or sh ...
docker exec -it "%CTR_NAME%" /bin/bash
if !errorlevel! neq 0 (
    docker exec -it "%CTR_NAME%" /bin/sh
)
goto MAIN

:PS
echo.
echo [7] docker ps -a filtered:
docker ps -a --filter "ancestor=%IMAGE_TAG%"
echo ---- all ---- 
docker ps
goto PAUSE

:IMAGESDF
echo.
echo [8] images + df
docker images "%IMAGE_TAG%"
echo.
docker system df
goto PAUSE

:REBUILD_DETACHED
echo.
echo [9] build + detached...
docker build -t "%IMAGE_TAG%" .
if !errorlevel! neq 0 goto PAUSE_FAIL
docker rm -f "%CTR_NAME%" 2>nul
call :DOCKER_ENV_ARGS
if defined WORKDIR (
    docker run -d --name "%CTR_NAME%" !ENV_ARGS! -v "%WORKDIR%:/workspace" -w /workspace "%IMAGE_TAG%" interpreter --profile %OI_PROFILE%
) else (
    docker run -d --name "%CTR_NAME%" !ENV_ARGS! "%IMAGE_TAG%" interpreter --profile %OI_PROFILE%
)
if !errorlevel! equ 0 (
    echo [OK]
    docker ps --filter "name=%CTR_NAME%"
) else echo [FAIL]
goto PAUSE

:PAUSE_FAIL
echo [FAIL] Build failed.
goto PAUSE

:PRUNE
echo.
echo [10] docker system prune -f
echo Stopped containers unused networks dangling images cache.
set /p confirm="Type y Enter to continue : "
if /i "!confirm!"=="y" (
    docker system prune -f
    echo [OK]
) else echo Cancelled.
goto PAUSE

:EXPORT_IMG
echo.
echo [11] docker save
set /p EXPORT_PATH="Tar path ^(Enter for open-interpreter-yc.tar^): "
if "!EXPORT_PATH!"=="" set "EXPORT_PATH=open-interpreter-yc.tar"
docker save -o "!EXPORT_PATH!" "%IMAGE_TAG%"
if !errorlevel! equ 0 (
    echo [OK] !EXPORT_PATH!
    for %%A in ("!EXPORT_PATH!") do echo bytes: %%~zA
) else echo [FAIL]
goto PAUSE

:ENV_SESSION
echo.
echo [12] session vars only - hf Router token etc.
set "HF_PREVIEW="
if defined HF_TOKEN (
    set "HF_PREVIEW=!HF_TOKEN!"
    echo HF_TOKEN preview: !HF_PREVIEW:~0,12!...(hidden^)
) else (
    echo HF_TOKEN: empty
)
set /p HF_TOKEN_NEW="HF_TOKEN - Enter skips: "
if not "!HF_TOKEN_NEW!"=="" set "HF_TOKEN=!HF_TOKEN_NEW!"
set /p OI_PROFILE_NEW="profile e.g. hf_router_skills.py - Enter skips: "
if not "!OI_PROFILE_NEW!"=="" set "OI_PROFILE=!OI_PROFILE_NEW!"
set /p WORKDIR_NEW="WORKDIR Host path bind - Enter skips: "
if not "!WORKDIR_NEW!"=="" set "WORKDIR=!WORKDIR_NEW!"
echo [OK] Updated for this CMD window only.
goto PAUSE

:PAUSE
echo.
pause
goto MAIN

:END
echo.
echo Bye.
exit /b 0

:DOCKER_ENV_ARGS
set "ENV_ARGS="
if exist "%CD%\.env" set "ENV_ARGS=!ENV_ARGS! --env-file ""%CD%\.env"""
if defined HF_TOKEN set "ENV_ARGS=!ENV_ARGS! -e HF_TOKEN=!HF_TOKEN!"
if defined TAVILY_API_KEY set "ENV_ARGS=!ENV_ARGS! -e TAVILY_API_KEY=!TAVILY_API_KEY!"
if defined CUSTOM_SKILLS_DIR set "ENV_ARGS=!ENV_ARGS! -e CUSTOM_SKILLS_DIR=!CUSTOM_SKILLS_DIR!"
goto :eof

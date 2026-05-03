@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

set "ROOT=%~dp0"
set "VENV=%ROOT%.venv"
set "PY=%VENV%\Scripts\python.exe"
set "INTR=%VENV%\Scripts\interpreter.exe"
set "PROFILE=hf_router_skills.py"

REM --- Load .env via Python (handles LF/CRLF, spaces, quoting) ---
call :load_dotenv
if exist "%ROOT%local_tokens.bat" call "%ROOT%local_tokens.bat"

:MENU
cls
echo ============================================================
echo  Open Interpreter YC  --  start.bat
echo ============================================================
echo.
echo  [1] Run  (local venv)
echo  [2] Setup / rebuild venv
echo  [3] Install / update tavily-python
echo  [4] Docker build + run
echo  [5] Docker menu (manage.bat)
echo  [0] Exit
echo.
if exist "%PY%" (
    echo  venv     : OK
) else (
    echo  venv     : NOT FOUND -- run option 2 first
)
if defined HF_TOKEN (
    echo  HF_TOKEN : !HF_TOKEN:~0,8!...
) else (
    echo  HF_TOKEN : NOT SET
)
if defined TAVILY_API_KEY (
    echo  Tavily   : !TAVILY_API_KEY:~0,8!...
) else (
    echo  Tavily   : NOT SET
)
echo.
set /p "C=Enter 0-5: "
if "!C!"=="" goto MENU
if "!C!"=="1" goto RUN
if "!C!"=="2" goto SETUP
if "!C!"=="3" goto TAVILY
if "!C!"=="4" goto DOCKER
if "!C!"=="5" goto MANAGE
if "!C!"=="0" goto END
goto MENU

REM ---------------------------------------------------------------------------
:RUN
echo.
if not exist "%PY%" (
    echo [ERR] .venv not found. Run option 2 first.
    pause & goto MENU
)
if not defined HF_TOKEN (
    set /p "HF_TOKEN=HF_TOKEN (paste here, or press Enter to abort): "
    if "!HF_TOKEN!"=="" (
        echo [ERR] HF_TOKEN required.
        pause & goto MENU
    )
)
echo [*] Token check:
echo     HF_TOKEN       = !HF_TOKEN:~0,12!...
if defined TAVILY_API_KEY (
    echo     TAVILY_API_KEY = !TAVILY_API_KEY:~0,12!...
) else (
    echo     TAVILY_API_KEY = NOT SET
)
echo.
echo [*] Starting Open Interpreter ...
echo     Profile : %PROFILE%
echo     Ctrl+D or type 'exit' to quit.
echo.
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if exist "%INTR%" (
    "%INTR%" --profile "%PROFILE%"
) else (
    "%PY%" -m interpreter.terminal_interface.start_terminal_interface --profile "%PROFILE%"
)
goto MENU

REM ---------------------------------------------------------------------------
:SETUP
echo.
echo [*] Looking for Python 3.9-3.12 ...
set "RUNPY="
py -3.12 --version >nul 2>&1 && set "RUNPY=py -3.12"
if not defined RUNPY (
    py -3.11 --version >nul 2>&1 && set "RUNPY=py -3.11"
)
if not defined RUNPY (
    py -3.10 --version >nul 2>&1 && set "RUNPY=py -3.10"
)
if not defined RUNPY (
    py -3.9 --version >nul 2>&1 && set "RUNPY=py -3.9"
)
if not defined RUNPY (
    echo [ERR] Python 3.9-3.12 not found. Install from python.org
    pause & goto MENU
)
echo [*] Using: !RUNPY!

if exist "%VENV%\Scripts\python.exe" (
    echo.
    echo [WARN] .venv already exists.
    set /p "REC=Type Y to delete and rebuild, other key to cancel: "
    if /i "!REC!"=="Y" (
        echo [*] Removing .venv ...
        rmdir /s /q "%VENV%"
    ) else (
        echo Cancelled.
        pause & goto MENU
    )
)

echo [*] Creating .venv ...
!RUNPY! -m venv "%VENV%"
if errorlevel 1 ( echo [ERR] venv creation failed. & pause & goto MENU )

echo [*] Upgrading pip ...
"%PY%" -m pip install -U pip -q

echo [*] Installing open-interpreter (editable) ...
"%PY%" -m pip install -e "%ROOT%." -q
if errorlevel 1 ( echo [ERR] install failed. & pause & goto MENU )

echo [*] Installing tavily-python ...
"%PY%" -m pip install tavily-python -q

echo.
echo [OK] Setup complete. Run option 1 to start.
pause & goto MENU

REM ---------------------------------------------------------------------------
:TAVILY
echo.
if not exist "%PY%" ( echo [ERR] No venv. Run option 2 first. & pause & goto MENU )
echo [*] Installing/updating tavily-python ...
"%PY%" -m pip install -U tavily-python
echo [OK] Done.
pause & goto MENU

REM ---------------------------------------------------------------------------
:DOCKER
echo.
docker --version >nul 2>&1
if errorlevel 1 ( echo [ERR] Docker not running. & pause & goto MENU )
if not defined HF_TOKEN (
    echo [ERR] HF_TOKEN not set.
    pause & goto MENU
)
echo [*] Docker build ...
docker build -t open-interpreter-yc "%ROOT%."
if errorlevel 1 ( echo [ERR] Build failed. & pause & goto MENU )
echo [*] Docker run ...
docker run -it --rm --env-file "%ROOT%.env" -e HF_TOKEN=!HF_TOKEN! open-interpreter-yc
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
:load_dotenv
REM Use Python to parse .env (handles LF/CRLF and edge cases)
set "_DOTENV_SH="
set "_DOTENV_PY=%ROOT%scripts\emit_dotenv_for_cmd.py"
if exist "%PY%" (
    for /f "delims=" %%F in ('"%PY%" "!_DOTENV_PY!" 2^>nul') do set "_DOTENV_SH=%%F"
)
if not defined _DOTENV_SH (
    for /f "delims=" %%F in ('py -3 "!_DOTENV_PY!" 2^>nul') do set "_DOTENV_SH=%%F"
)
if not defined _DOTENV_SH (
    for /f "delims=" %%F in ('python "!_DOTENV_PY!" 2^>nul') do set "_DOTENV_SH=%%F"
)
if defined _DOTENV_SH if exist "!_DOTENV_SH!" (
    call "!_DOTENV_SH!"
    del "!_DOTENV_SH!" >nul 2>&1
)
set "_DOTENV_SH="
set "_DOTENV_PY="
goto :eof

:END
echo Bye.
endlocal
exit /b 0
@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: ========================================
:: 在下面 HF_TOKEN= 後面貼入你的 Token
:: ========================================
set HF_TOKEN=貼在這裡

:: ========================================
:: 掛載本機資料夾：把 WORKDIR 改成你的路徑，
:: 並刪掉下面那行開頭的 rem（只刪 rem，保留 set）
:: 容器內請在 /workspace 下工作（對應你的本機資料夾）
:: ========================================
rem set WORKDIR=C:\Users\CHENG\Desktop\我的專案

docker build -t open-interpreter-yc .

if defined WORKDIR (
  docker run -it --rm -e HF_TOKEN=%HF_TOKEN% -v "%WORKDIR%:/workspace" -w /workspace open-interpreter-yc
) else (
  docker run -it --rm -e HF_TOKEN=%HF_TOKEN% open-interpreter-yc
)

pause

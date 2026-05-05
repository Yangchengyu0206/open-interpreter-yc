# Open-Interpreter-YC 單一路徑部署流程

這份文件把你目前方案整成一條龍，分成兩種：

- 本機 venv 跑（推薦先用）
- Docker 跑（公司機常用）

---

## 0) 先準備一次

1. 進專案根目錄（有 `pyproject.toml`、`Deploy-OneClick.cmd`）。
2. 準備設定：
   - 建議把金鑰放在 `local_tokens.bat`（不要 commit）。
   - 或放 `.env`。

---

## 1) 本機 venv 一條龍（最短路徑）

### Step A. 一鍵部署

雙擊：

`Deploy-OneClick.cmd`

可選參數：

- `-FreshVenv`：重建 `.venv`
- `-SkipTavily`：不安裝 `tavily-python`
- `-NoInstallUv`：找不到 `uv` 時不自動安裝

### Step B. 啟動

雙擊：

`start.bat`

依選單操作（目前檔案顯示為 Docker 導向選單）。

---

## 2) Docker 一條龍（公司端常用）

雙擊：

`start.bat`

建議順序：

1. `Build image`
2. `Run (互動式 -it)` 或 `Run (背景 detached)`

進階管理在：

`manage.bat`

---

## 3) 目前設定重點（依現況）

- `start.bat` 預設 profile：`env_driven.py`
- `manage.bat` 預設 profile：`env_driven.py`
- `Deploy-OneClick.cmd` 會呼叫：`scripts/deploy_uv_oneclick.ps1`

---

## 4) 團隊標準操作（建議統一）

### 新機器第一次

1. `Deploy-OneClick.cmd`
2. `start.bat` -> Build image
3. `start.bat` -> Run

### 平常使用

1. `start.bat` -> Run

### 程式更新後

1. `start.bat` -> Build image
2. `start.bat` -> Run

---

## 5) 常見卡點與快速判斷

- 雙擊閃退：改從 `cmd` 執行，保留輸出。
- 內網 SSL 問題：`Deploy-OneClick.cmd` 已設 `UV_NATIVE_TLS=1`。
- profile 跑錯：檢查 `start.bat`/`manage.bat` 的 `OI_PROFILE`。


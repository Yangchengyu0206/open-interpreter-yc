# 使用 uv 部署與執行 open-interpreter-yc（Windows 為主）

本文說明如何用 **[uv](https://docs.astral.sh/uv/)** 固定 **Python 版本**、建立 **虛擬環境**、安裝本專案並執行 **`interpreter`**。適合內網與「每人本機 skills」情境；**不**取代你自訂的 API 金鑰與 profile 設定。

---

## 0. 一鍵部署（Windows，雙擊）

1. 在檔案總管開啟專案根目錄。
2. 雙擊 **`Deploy-OneClick.cmd`**。
   - 若本機尚無 `uv`，腳本會嘗試執行官方線上安裝（需可連線）；**內網／離線**請先依 §1 手動安裝 `uv` 並加入 `PATH`，再執行 **`Deploy-OneClick.cmd -NoInstallUv`**。
3. 完成後用 **`start.bat`** 選 **[1]** 執行（與既有選單一致）。

**進階參數**（加在 `Deploy-OneClick.cmd` 後方，或改執行 `.\scripts\deploy_uv_oneclick.ps1`）：

- **`-FreshVenv`**：刪除既有 `.venv` 後重建。
- **`-SkipTavily`**：不安裝 `tavily-python`（預設會裝，與 `start.bat` 的「選項 2」一致）。
- **`-NoInstallUv`**：找不到 `uv` 時不要自動下載安裝，直接失敗。

環境變數 **`OI_UV_PYTHON`**：覆寫預設 Python 版本字串（預設 **`3.11`**）。

---

## 1. 安裝 uv（每台機器一次）

**PowerShell（官方建議）：**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

安裝後重新開啟終端機，確認：

```powershell
uv --version
```

**完全離線／不允許抓 install script 時**：請從內網軟體庫取得 **uv 的 Windows 執行檔** 或 zip，解壓後把目錄加入 `PATH`（由 IT 提供路徑與更新流程）。

---

## 2. 固定 Python 版本（建議全團隊同一小版本）

本專案 `pyproject.toml` 宣告 **`>=3.9,<3.13`**；**部署上建議鎖一版**（例如 **3.11**），避免二進位依賴在不同小版本間不一致。

由 uv 下載並管理該版本（需能連到 Python 官方或你設定的鏡像；離線見 §6）：

```powershell
uv python install 3.11
```

查看已安裝的解釋器：

```powershell
uv python list
```

---

## 3. 取得專案原始碼

```powershell
cd C:\work
git clone <你的內網或本機 open-interpreter-yc 倉庫 URL>
cd open-interpreter-yc
```

若無 git，改為解壓 zip 到同一層級即可。

---

## 4. 建立虛擬環境（專案內 `.venv`）

在 **專案根目錄**（有 `pyproject.toml` 的那一層）：

```powershell
uv venv --python 3.11 .venv
```

啟用虛擬環境（**之後每次開終端都要先啟用**）：

```powershell
.\.venv\Scripts\Activate.ps1
```

若執行原則被擋，可改用：

```powershell
.\.venv\Scripts\activate.bat
```

---

## 5. 安裝本專案（可編輯模式，開發 fork 最常用）

仍在專案根目錄、且 **venv 已啟用**：

```powershell
uv pip install -U pip
uv pip install -e .
```

這會依 `pyproject.toml` 安裝依賴，並註冊主程式 **`interpreter`** / **`i`**（與 Poetry 的 `[tool.poetry.scripts]` 一致）。

**若只想裝「發行用 wheel」**（同事不開發時）：

```powershell
uv pip install C:\path\to\open_interpreter-0.4.3-py3-none-any.whl
```

（wheel 檔名以你實際 build 為準。）

---

## 6. 內網／離線：指定套件索引（可選）

若不能連公網 PyPI，由 IT 提供 **內部 index URL**，每次安裝前設定（PowerShell 當次視窗）：

```powershell
$env:UV_INDEX_URL = "https://your-internal-pypi/simple"
uv pip install -e .
```

或寫入 **使用者／系統環境變數** 持久化（依公司規範）。實際變數名請對照你們鏡像與 uv 版本文件（亦可能使用 `PIP_INDEX_URL` 等相容方式）。

**離線目錄**（預先下載 wheel 到資料夾）可搭配：

```powershell
uv pip install --no-index --find-links C:\wheels -e .
```

（`C:\wheels` 改為你方實際路徑。）

---

## 7. 設定 API 金鑰與執行

啟用 venv 後，依你使用的模型設定環境變數，例如：

```powershell
$env:OPENAI_API_KEY = "sk-..."
interpreter
```

或使用 profile：

```powershell
interpreter -p hf_router_skills
```

（profile 檔名依 `interpreter/terminal_interface/profiles/defaults/` 與你自備 profile 而定。）

**Python 內嵌呼叫：**

```powershell
python -c "from interpreter import interpreter; interpreter.chat('你好', display=False)"
```

---

## 8. 建議給同事的「最短操作清單」

1. 安裝 uv（§1）  
2. `uv python install 3.11`（§2）  
3. `cd` 到專案根目錄 → `uv venv --python 3.11 .venv`（§4）  
4. `.\.venv\Scripts\Activate.ps1`  
5. `uv pip install -e .`（§5）  
6. 設金鑰 → `interpreter`（§7）

---

## 9. 與 Poetry 的關係

本倉庫仍以 **Poetry 格式** 維護 `pyproject.toml`。日常可：

- **開發**：本機已裝 Poetry 者仍可用 `poetry install`；  
- **部署／同事機**：用 **uv** 依 §4～§5 即可，**不必**強迫所有人安裝 Poetry。

發行物若要 **wheel**：可在 build 機執行 `poetry build`，再把產出的 `.whl` 給同事用 `uv pip install xxx.whl` 安裝。

---

## 10. 版本檢查（可選，寫進自訂啟動腳本）

若要在啟動前強制 Python 小版本：

```python
import sys
assert sys.version_info[:2] == (3, 11), "請使用 Python 3.11 與文件一致"
```

（數字改為你們實際鎖定的版本。）

---

## 參考連結

- uv 文件：<https://docs.astral.sh/uv/>  
- Open Interpreter 設定總覽：<https://docs.openinterpreter.com/settings/all-settings>

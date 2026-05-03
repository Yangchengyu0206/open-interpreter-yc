import os
from pathlib import Path

from interpreter import interpreter

# =============================================================================
# hf_router_skills 在幹嘛？（沒有 REST 端點、沒有「Tool API」要你自己寫）
#
# 1) Skills 是「一整包 .py」被 OI 丟進「同一個長駐的 Python Kernel」連在一起執行一次，
#    所以你寫的 def xxx(): 會變成那個環境裡的「全域函式」，不是對外開 HTTP。
#
# 2) LLM 「怎麼呼叫」這些函式？
#    它跟一般 OI 一樣：在回覆裡輸出 ```python … ``` 區塊，OI 替你執行那段程式；
#    區塊裡可以寫 result = example_echo_agent("問題")，就等於呼叫你的 skill。
#    （若模型走 function-call 模式，本質仍是請模型產出要執行的程式碼，不是你去註冊 URL。）
#
# 3) 外部 skill 放哪？
#    預設：專案根目錄下的 custom_skills/*.py。
#    若要用別的資料夾：啟動前設環境變數 CUSTOM_SKILLS_DIR=絕對路徑，
#    或直接把下面 interpreter.computer.skills.path = r"D:\...\你的資料夾" 寫死。
#
# 4) 與 LangChain 「Tool」的比較：LangChain Tool 若在 skill 檔案裡用 Python 建好，
#    仍可再包一個 def my_turn(...): 裡面 graph.invoke(...) 給模型用程式碼去叫。
# =============================================================================

# --- 與 hf_router 相同：HF Router + DeepSeek ---
interpreter.llm.model = "openai/deepseek-ai/DeepSeek-V4-Pro:novita"
interpreter.llm.api_base = "https://router.huggingface.co/v1"
interpreter.llm.api_key = os.environ["HF_TOKEN"]
interpreter.llm.temperature = 0

interpreter.computer.import_computer_api = True
interpreter.auto_run = False

_REPO_ROOT = Path(__file__).resolve().parents[4]
_EXTERNAL = os.environ.get("CUSTOM_SKILLS_DIR")
if _EXTERNAL:
    _SKILLS_DIR = Path(_EXTERNAL).expanduser().resolve()
else:
    _SKILLS_DIR = _REPO_ROOT / "custom_skills"
_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

interpreter.computer.skills.path = str(_SKILLS_DIR)
interpreter.computer.import_skills = True

interpreter.custom_instructions = """
此環境已在啟動時載入 `computer.skills.path` 目錄內全部 `*.py`（可含 LangChain / LangGraph；依賴需已安裝在同一 Python 環境）。

使用方式：
- 可先執行程式：`print(computer.skills.list())` 會列出「檔案名對應到的可呼叫名稱（顯示成 xxx.py 變 xxx()）」；實際呼叫時請用你的函式名，例如 `example_echo_agent(\"...\")`。
- 處理使用者需求時：在 markdown 的 ```python ``` 區塊中直接呼叫那些函式，把回傳值當結果解釋給使用者——不需要也不存在另外的 HTTP endpoint。

將主要代理邏輯寫在 skill 資料夾的函式裡；保持對話仍以 Open Interpreter 執行程式碼為主。
""".strip()

try:
    interpreter.computer.skills.import_skills()
except Exception as e:
    interpreter.display_message(
        f"`custom_skills` 預載入失敗（請檢查該資料夾內 .py 語法與依賴）: {e}"
    )
else:
    interpreter.computer._has_imported_skills = True

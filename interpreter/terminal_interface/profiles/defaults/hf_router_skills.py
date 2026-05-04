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
interpreter.llm.model = "openai/google/gemma-4-31B-it:novita"
interpreter.llm.api_base = "https://router.huggingface.co/v1"
_hf_token = (
    os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN") or ""
).strip()
if not _hf_token:
    raise RuntimeError(
        "HF Router 需要 Hugging Face Hub token：請設定 HF_TOKEN "
        "或 HUGGINGFACE_HUB_TOKEN（Docker：-e HF_TOKEN=... ，勿將金鑰寫進程式碼）。"
    )
interpreter.llm.api_key = _hf_token
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
## Available Skills (pre-loaded in Python kernel)

The following functions are already defined in the kernel — call them directly in python code blocks:

- `web_search(query, max_results=5)` — search the web via Tavily, returns formatted results
- `web_search_with_answer(query)` — search + AI-summarized answer with sources
- `example_echo_agent(user_text)` — echo stub for testing

**IMPORTANT — Code block rules:**
1. NEVER put punctuation (。，！？、) or any non-code text inside a code block.
2. Code blocks must contain ONLY valid code. No prose, no Chinese characters, no trailing punctuation.
3. For web searches or real-time information, always use `web_search()` or `web_search_with_answer()` — do NOT use curl, requests to search engines, or computer.browser.search.

Example of correct usage:
```python
result = web_search("台南現在天氣")
print(result)
```
""".strip()

try:
    interpreter.computer.skills.import_skills()
except Exception as e:
    interpreter.display_message(
        f"`custom_skills` 預載入失敗（請檢查該資料夾內 .py 語法與依賴）: {e}"
    )
else:
    interpreter.computer._has_imported_skills = True

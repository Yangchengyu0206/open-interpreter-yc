import json
import os
from pathlib import Path

from interpreter import interpreter

# ── 公司內部 LLM（寫死端點與模型）──────────────────────────────────────────────
_ENDPOINT = "https://llm.ai.himax.com.tw/v1"
_MODEL    = "openai/gpt-oss-120b"   # LiteLLM openai/ 前綴 = OpenAI 相容格式

# ── Keys：只從環境變數讀（請在 local_tokens.bat 設定）────────────────────────────
# local_tokens.bat 範例：
#   set "API_KEY=your-company-key"
#   set "TAVILY_API_KEY=tvly-xxxx"
_api_key    = "3e2fc0f6-77a7-4279-a1f0-53c53b5450bd"  # 公司 LLM key
_tavily_key = ""  # 填入你的 Tavily key，例如 "tvly-xxxxxx"

# ── LLM 設定 ─────────────────────────────────────────────────────────────────
interpreter.llm.model       = _MODEL
interpreter.llm.api_base    = _ENDPOINT
interpreter.llm.api_key     = _api_key
interpreter.llm.temperature = 0
interpreter.llm.context_window = 32000
interpreter.llm.max_tokens     = 4096

interpreter.computer.import_computer_api = True
interpreter.auto_run = False

# ── Skills 路徑 ───────────────────────────────────────────────────────────────
_REPO_ROOT  = Path(__file__).resolve().parents[4]
_EXTERNAL   = os.environ.get("CUSTOM_SKILLS_DIR")
_SKILLS_DIR = Path(_EXTERNAL).expanduser().resolve() if _EXTERNAL else _REPO_ROOT / "custom_skills"
_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

interpreter.computer.skills.path = str(_SKILLS_DIR)
interpreter.computer.import_skills = True

# ── 把 Tavily key 直接注入 IPython kernel ─────────────────────────────────────
# 原因：kernel 是獨立子程序，只繼承啟動當下的 os.environ 快照；
# 在 kernel 裡跑這行才能確保 web_search.py 的 os.environ.get(...) 讀得到。
if _tavily_key:
    _inject = f"import os; os.environ['TAVILY_API_KEY'] = {json.dumps(_tavily_key)}"
    interpreter.computer.run("python", _inject)

# ── 載入 skills ───────────────────────────────────────────────────────────────
_tavily_status = "OK" if _tavily_key else "未設定 → web_search 無法使用，請在 local_tokens.bat 加入 TAVILY_API_KEY"
interpreter.custom_instructions = f"""
## LLM
公司內部 LLM：{_MODEL}（{_ENDPOINT}）

## Available Skills
- `web_search(query, max_results=5)` — Tavily 網路搜尋  [{_tavily_status}]
- `web_search_with_answer(query)` — 搜尋 + AI 摘要  [{_tavily_status}]

**規則：程式碼區塊內只放合法程式碼，不放中文或標點。**
""".strip()

try:
    interpreter.computer.skills.import_skills()
except Exception as e:
    interpreter.display_message(
        f"`custom_skills` 預載入失敗（請檢查語法與依賴）: {e}"
    )
else:
    interpreter.computer._has_imported_skills = True

"""
env_driven.py — 統一由環境變數驅動的 Open Interpreter profile

所有設定從 .env（或 docker run -e / docker compose env_file）讀取，
不需要修改程式碼即可切換 LLM provider、開關 skills、調整安全模式等。

設定速查：
  LLM_PROVIDER        = company | hf          (預設 company)
  LLM_MODEL           公司端點模型名
  LLM_API_BASE        公司端點 URL
  LLM_API_KEY         公司端點 API key
  HF_TOKEN            HuggingFace Hub token
  HF_MODEL            HF Router 模型名
  LLM_TEMPERATURE     0~2（預設 0）
  LLM_CONTEXT_WINDOW  context 長度（token）
  LLM_MAX_TOKENS      最大輸出 token
  OI_AUTO_RUN         true/false（預設 false）
  OI_SAFE_MODE        off / ask / auto（預設 off）
  OI_OFFLINE          true/false（預設 false）
  OI_VERBOSE          true/false（預設 false）
  OI_MAX_OUTPUT       程式輸出字元上限（預設 2800）
  OI_CONVERSATION_HISTORY  true/false（預設 true）
  OI_IMPORT_SKILLS    true/false（預設 true）
  CUSTOM_SKILLS_DIR   自訂 skills 目錄絕對路徑（選填）
  TAVILY_API_KEY      Tavily 搜尋 API key（選填）
"""
import json
import os
from pathlib import Path

from interpreter import interpreter

# TLS bypass is handled centrally in interpreter/core/llm/llm.py at import time.

# ── LLM Provider ──────────────────────────────────────────────────────────────
_provider = os.environ.get("LLM_PROVIDER", "company").strip().lower()

if _provider == "hf":
    _hf_token = (
        os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN") or ""
    ).strip()
    if not _hf_token:
        raise RuntimeError(
            "LLM_PROVIDER=hf 需設定 HF_TOKEN 環境變數\n"
            "  .env：HF_TOKEN=hf_xxx\n"
            "  Docker：-e HF_TOKEN=hf_xxx"
        )
    interpreter.llm.model   = os.environ.get("HF_MODEL", "openai/deepseek-ai/DeepSeek-V4-Pro:novita")
    interpreter.llm.api_base = "https://router.huggingface.co/v1"
    interpreter.llm.api_key  = _hf_token
else:
    # 預設：公司內部 LLM
    interpreter.llm.model    = os.environ.get("LLM_MODEL",    "openai/gpt-oss-120b")
    interpreter.llm.api_base = os.environ.get("LLM_API_BASE", "https://llm.ai.himax.com.tw/v1")
    interpreter.llm.api_key  = os.environ.get("LLM_API_KEY",  "3e2fc0f6-77a7-4279-a1f0-53c53b5450bd")

# ── LLM 共用參數 ──────────────────────────────────────────────────────────────
interpreter.llm.temperature = float(os.environ.get("LLM_TEMPERATURE", "0"))

_ctx = os.environ.get("LLM_CONTEXT_WINDOW")
if _ctx:
    interpreter.llm.context_window = int(_ctx)

_max_tok = os.environ.get("LLM_MAX_TOKENS")
if _max_tok:
    interpreter.llm.max_tokens = int(_max_tok)

# ── 執行行為 ──────────────────────────────────────────────────────────────────
interpreter.auto_run             = os.environ.get("OI_AUTO_RUN",             "false").lower() == "true"
interpreter.safe_mode            = os.environ.get("OI_SAFE_MODE",            "off")
interpreter.offline              = os.environ.get("OI_OFFLINE",              "false").lower() == "true"
interpreter.verbose              = os.environ.get("OI_VERBOSE",              "false").lower() == "true"
interpreter.max_output           = int(os.environ.get("OI_MAX_OUTPUT",       "2800"))
interpreter.conversation_history = os.environ.get("OI_CONVERSATION_HISTORY", "true").lower() == "true"

interpreter.computer.import_computer_api = True

# ── Skills ────────────────────────────────────────────────────────────────────
_import_skills = os.environ.get("OI_IMPORT_SKILLS", "true").lower() == "true"

_profile_file = globals().get("__file__")
if _profile_file:
    _REPO_ROOT = Path(_profile_file).resolve().parents[4]
else:
    # Profile .py is exec()'d by OI loader; __file__ can be missing in that path.
    # In Docker and local launcher we run from repo root, so fallback to cwd.
    _REPO_ROOT = Path.cwd()
_external   = os.environ.get("CUSTOM_SKILLS_DIR")
_skills_dir = Path(_external).expanduser().resolve() if _external else _REPO_ROOT / "custom_skills"
_skills_dir.mkdir(parents=True, exist_ok=True)

interpreter.computer.skills.path  = str(_skills_dir)
interpreter.computer.import_skills = _import_skills

# ── Tavily key 注入 IPython kernel ────────────────────────────────────────────
# kernel 是獨立子程序，需在此明確注入，否則 web_search.py 讀不到
_tavily_key = os.environ.get("TAVILY_API_KEY", "").strip()
if _tavily_key:
    _inject = f"import os; os.environ['TAVILY_API_KEY'] = {json.dumps(_tavily_key)}"
    interpreter.computer.run("python", _inject)

# ── Custom instructions ────────────────────────────────────────────────────────
_tavily_status  = "OK" if _tavily_key  else "未設定 → web_search 無法使用"
_skills_status  = "已載入" if _import_skills else "關閉"

interpreter.custom_instructions = f"""
## LLM
Provider: {_provider.upper()} — {interpreter.llm.model}
Endpoint: {interpreter.llm.api_base}

## Available Skills [{_skills_status}]
- `web_search(query, max_results=5)` — Tavily 網路搜尋  [{_tavily_status}]
- `web_search_with_answer(query)`    — 搜尋 + AI 摘要   [{_tavily_status}]

## 設定摘要
auto_run={interpreter.auto_run} | safe_mode={interpreter.safe_mode} | offline={interpreter.offline}

**規則：程式碼區塊內只放合法程式碼，不放中文或標點。**
""".strip()

# ── 載入 skills ───────────────────────────────────────────────────────────────
if _import_skills:
    try:
        interpreter.computer.skills.import_skills()
    except Exception as e:
        interpreter.display_message(f"`custom_skills` 預載入失敗（請檢查語法與依賴）: {e}")
    else:
        interpreter.computer._has_imported_skills = True

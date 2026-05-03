import os
from interpreter import interpreter

interpreter.llm.model = "openai/deepseek-ai/DeepSeek-V4-Pro:novita"
interpreter.llm.api_base = "https://router.huggingface.co/v1"

# 從環境變數讀取 token；HF Router 需 Hub token（細粒度權限須開「Inference」）
_hf = (os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN") or "").strip()
if not _hf:
    raise RuntimeError(
        "HF Router 需要 Hugging Face Hub token：請設定環境變數 HF_TOKEN "
        "(或 HUGGINGFACE_HUB_TOKEN)。Docker: -e HF_TOKEN=..."
    )
interpreter.llm.api_key = _hf
interpreter.llm.temperature = 0

interpreter.computer.import_computer_api = True
interpreter.auto_run = False

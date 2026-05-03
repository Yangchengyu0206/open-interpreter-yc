import os
from interpreter import interpreter

# 從環境變數讀取 API key，不寫死在程式碼裡
interpreter.llm.model = "openai/deepseek-ai/DeepSeek-V4-Pro:novita"
interpreter.llm.api_base = "https://router.huggingface.co/v1"
interpreter.llm.api_key = os.environ["HF_TOKEN"]
interpreter.llm.temperature = 0

interpreter.computer.import_computer_api = True
interpreter.auto_run = False

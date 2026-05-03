FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --no-cache-dir -e .

# 使用 hf_router.py profile，api_key 從環境變數 HF_TOKEN 讀取
CMD ["interpreter", "--profile", "hf_router.py"]

FROM python:3.12-slim

WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    git \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 先複製 requirements.txt 並安裝依賴（利用 Docker 快取層）
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Needed for `interpreter --server` in detached mode.
RUN pip install --no-cache-dir fastapi uvicorn

# 複製原始碼並以 no-deps 安裝套件本身
COPY . .
RUN pip install --no-cache-dir -e . --no-deps

# 啟動命令（預設使用公司內部 LLM profile）
CMD ["interpreter", "--profile", "env_driven.py"]

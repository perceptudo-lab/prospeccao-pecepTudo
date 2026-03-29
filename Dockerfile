FROM python:3.11-slim

WORKDIR /app

# Dependencias de sistema para Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium --with-deps

COPY . .

# Criar directorio de output
RUN mkdir -p output/leads output/conversas

EXPOSE 5001

# Default: agente atendente (webhook server)
CMD ["python", "main.py", "agente", "--port", "5001"]

# Tek imaj, iki kullanim:
#   web  (Cloud Run servisi) : varsayilan komut
#   isci (Cloud Run Job)     : komut "python -m saas.isci"
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright PORT=8080 \
    SAAS_ORTAM=bulut SAAS_DEPO=supabase SAAS_TETIK=cloudrun \
    AJAN_YZ_SAGLAYICI=openai AJAN_AI_GORSEL=0

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt requirements-saas.txt ./
RUN pip install --no-cache-dir -r requirements-saas.txt \
    && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY . .
RUN useradd --create-home --uid 10001 ajan && chown -R ajan /app /ms-playwright
USER ajan

CMD ["sh", "-c", "exec uvicorn saas.web:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]

# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    JACARE_PUBLIC_MODE=true \
    JACARE_PUBLIC_DATA_DIR=/app/demo/public \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    XDG_CACHE_HOME=/tmp/jacare-cache \
    XDG_CONFIG_HOME=/tmp/jacare-config

WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir -r requirements.txt . \
    && groupadd --gid 10001 jacare \
    && useradd --uid 10001 --gid 10001 --no-create-home jacare \
    && mkdir -p /app/public-data \
    && chown 10001:10001 /app/public-data

COPY app/ ./app/
COPY demo/public/ ./demo/public/
COPY config/ ./config/
COPY .streamlit/config.toml ./.streamlit/config.toml
USER 10001:10001
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3)"
CMD ["python", "-m", "streamlit", "run", "app/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--server.fileWatcherType=none", "--browser.gatherUsageStats=false"]

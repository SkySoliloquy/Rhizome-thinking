FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser

WORKDIR /app

RUN pip install --no-cache-dir hatchling
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir ".[stage2]"

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

RUN mkdir -p /app/storage && chown -R appuser:appuser /app

USER appuser
EXPOSE 8000

ENV STORAGE_DIR=/app/storage
ENV CHROMA_PERSIST_DIR=/app/storage/chroma

CMD ["uvicorn", "rhizome.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

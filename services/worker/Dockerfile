# ---- builder stage -------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps required by some Python packages (e.g. sentence-transformers)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY shared/pyproject.toml shared/
COPY services/worker/pyproject.toml services/worker/

RUN pip install --upgrade pip && \
    pip install --no-cache-dir \
        "celery[redis]>=5.3" \
        "pydantic-settings>=2.2" \
        "structlog>=24.1" \
        "sentence-transformers>=2.7" \
        "pypdf>=4.0" \
        "python-docx>=1.1" \
        "pandas>=2.0" \
        "sqlalchemy[asyncio]>=2.0" \
        "asyncpg>=0.29" \
        "opentelemetry-sdk>=1.24" \
        "opentelemetry-exporter-otlp>=1.24" \
        "opentelemetry-instrumentation-celery>=0.45b0"

# ---- runtime stage --------------------------------------------------------
FROM python:3.11-slim AS runtime

WORKDIR /app

# Non-root user for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source
COPY shared/ ./shared/
COPY services/worker/ ./services/worker/

# FAISS data mount point
RUN mkdir -p /data/faiss && chown appuser:appgroup /data/faiss

USER appuser

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

CMD ["celery", "-A", "services.worker.src.main", "worker", "--loglevel=info", "--concurrency=4"]

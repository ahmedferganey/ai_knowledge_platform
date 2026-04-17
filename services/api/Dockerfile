FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/services/api/src

WORKDIR /app

RUN useradd --create-home --shell /usr/sbin/nologin appuser

COPY services/api/pyproject.toml ./services/api/pyproject.toml
COPY services/api/src ./services/api/src

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ./services/api

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

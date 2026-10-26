FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV APP_ENVIRONMENT=production
ENV APP_ENABLE_DOCS=false

RUN addgroup --system app && adduser --system --ingroup app --home /app app

WORKDIR /app

COPY --chown=app:app pyproject.toml README.md ./
COPY --chown=app:app app ./app

RUN pip install --no-cache-dir --no-compile .

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--log-level", "warning"]

FROM mirror.ccs.tencentyun.com/library/python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app \
    && mkdir -p /app/media/uploads \
    && chown -R app:app /app/media

COPY pyproject.toml alembic.ini THIRD_PARTY_NOTICES.md ./
COPY alembic ./alembic
COPY app ./app

ARG PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple
RUN pip install --index-url "$PIP_INDEX_URL" .

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

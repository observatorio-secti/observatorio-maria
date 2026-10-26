FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN pip install --no-cache-dir "poetry>=2,<3"

# Dependências primeiro, para aproveitar o cache das camadas.
COPY pyproject.toml poetry.lock poetry.toml README.md ./
RUN poetry install --only main --no-root

COPY src ./src
RUN poetry install --only main

COPY alembic.ini ./
COPY migrations ./migrations
COPY catalog ./catalog

RUN useradd --create-home --uid 1000 maria && chown -R maria /app
USER maria

EXPOSE 8000

# Aplica as migrações antes de subir a API.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn observatorio_maria.app:app --host 0.0.0.0 --port 8000 --proxy-headers"]

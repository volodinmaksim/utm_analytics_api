FROM python:3.12-slim

ENV POETRY_VERSION=1.8.3 \
    POETRY_VIRTUALENVS_CREATE=false \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN pip install "poetry==$POETRY_VERSION"

COPY pyproject.toml poetry.lock* ./

# ВАЖНО: без --only main
RUN poetry install --no-interaction --no-ansi

COPY . .

EXPOSE 8000
CMD ["python", "run.py"]
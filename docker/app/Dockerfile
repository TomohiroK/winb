FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# psycopg2-binary, xgboost, scikit-learn, numpy, pandas, lxml は
# いずれも wheel 配布のため apt 経由のビルドツール不要

COPY pyproject.toml README.md /app/
COPY src/ /app/src/

RUN pip install --upgrade pip && pip install -e ".[dev]"

COPY scripts/ /app/scripts/
COPY tests/ /app/tests/

CMD ["python", "-c", "import winb; print(f'WinB {winb.__version__} ready')"]

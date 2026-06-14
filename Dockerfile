FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

RUN pip install --no-cache-dir poetry

WORKDIR /app

COPY pyproject.toml poetry.lock README.md ./
RUN poetry install --no-root --only main \
 && pip install --no-cache-dir "streamlit>=1.30" "pandas>=2.0"

COPY app ./app
COPY data ./data
COPY web ./web

EXPOSE 8501

CMD ["streamlit", "run", "web/streamlit_app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]

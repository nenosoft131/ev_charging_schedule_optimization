FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies using pip directly to avoid Poetry architecture issues
RUN pip install --no-cache-dir "pydantic>=2.13.4" "streamlit>=1.30" "pandas>=2.0"

COPY app ./app
COPY data ./data
COPY web ./web

EXPOSE 8501

CMD ["streamlit", "run", "web/streamlit_app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
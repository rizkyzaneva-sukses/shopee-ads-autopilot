FROM python:3.11-slim

LABEL maintainer="rizkyzaneva-sukses"

# Prevent Python from writing .pyc files & enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install libpq-dev for psycopg2-binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (cache-friendly layer order)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Remove build deps
RUN apt-get purge -y --auto-remove gcc && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY run.py .
COPY autopilot/ autopilot/
COPY shopee_connector/ shopee_connector/
COPY scripts/ scripts/

# Create data directory for SQLite fallback & tokens
RUN mkdir -p /app/data/tokens

# Default environment
ENV AUTOPILOT_DB=/app/data/autopilot.db \
    SHOPEE_TOKEN_DIR=*** \
    HOST=0.0.0.0 \
    PORT=80

EXPOSE 80

CMD ["python", "run.py"]

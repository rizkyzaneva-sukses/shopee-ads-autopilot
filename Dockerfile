FROM python:3.11-slim

LABEL maintainer="rizkyzaneva-sukses"

# Prevent Python from writing .pyc files & enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (cache-friendly layer order)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY run.py .
COPY autopilot/ autopilot/
COPY shopee_connector/ shopee_connector/
COPY scripts/ scripts/

# Create data directory for SQLite & tokens
RUN mkdir -p /app/data

# Default environment
ENV AUTOPILOT_DB=/app/data/autopilot.db \
    SHOPEE_TOKEN_DIR=/app/data/tokens \
    HOST=0.0.0.0 \
    PORT=8765

RUN mkdir -p /app/data/tokens

EXPOSE 8765

VOLUME ["/app/data"]

CMD ["python", "run.py"]

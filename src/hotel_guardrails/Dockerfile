# =============================================================================
# Hotel Guardrails API Server - Railway Deployment
# =============================================================================
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY src/hotel_guardrails/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/common /app/src/common
COPY src/hotel_guardrails /app/src/hotel_guardrails
COPY src/retrievers /app/src/retrievers
COPY src/agent/hotel_tools.py /app/src/agent/hotel_tools.py
COPY src/agent/hotel_prompt.yaml /app/src/agent/hotel_prompt.yaml
COPY src/agent/__init__.py /app/src/agent/__init__.py
COPY data/hotel /app/data/hotel

# Create empty __init__.py files
RUN touch /app/src/__init__.py

# Expose port
EXPOSE 8081

# Health check (simple endpoint for faster startup)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8081/healthz || exit 1

# Run the server - Railway sets PORT env var
CMD ["sh", "-c", "uvicorn src.hotel_guardrails.server:app --host 0.0.0.0 --port ${PORT:-8081}"]

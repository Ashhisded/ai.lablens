# Dockerfile for LabLens
# Multi-stage not needed — single slim image keeps things simple and small.
# Cloud Run injects the PORT environment variable (default 8080).

FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create a non-root user for security
RUN addgroup --system lablens && adduser --system --ingroup lablens lablens

WORKDIR /app

# Install dependencies (no dev tools, no cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the application source
COPY app/ ./app/

# Switch to non-root user
USER lablens

# Expose the port Cloud Run will use
EXPOSE 8080

# Health check (Cloud Run also polls /health)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8080}/health')"

# Start Uvicorn, binding to 0.0.0.0 and the PORT env var
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]

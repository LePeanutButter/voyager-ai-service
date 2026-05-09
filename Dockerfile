# syntax=docker/dockerfile:1
# BuildKit: caché de wheels pip entre builds (--mount=type=cache). DOCKER_BUILDKIT=1 (por defecto en Docker Desktop).
# Multi-stage build for Tourism Assistant AI Microservice
# Stage 1: Build stage with all dependencies
FROM python:3.11-slim as builder

# Set environment variables (sin PIP_NO_CACHE_DIR: queremos reutilizar el volumen de caché montado abajo)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Stage 2: Production stage with minimal dependencies
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app"

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create application directory
WORKDIR /app

# Copy application code
COPY app/ ./app/
COPY README.md ./
COPY docker/entrypoint-ai.sh /docker/entrypoint-ai.sh

# Quitar CRLF si el repo se editó en Windows (evita "exec …: no such file or directory" en el shebang).
# Artefactos sklearn en runtime (entrypoint entrena si el volumen está vacío)
RUN sed -i 's/\r$//' /docker/entrypoint-ai.sh && \
    chmod +x /docker/entrypoint-ai.sh && \
    mkdir -p /app/logs /app/data /app/models /app/app/ml/models && \
    chown -R appuser:appuser /app /docker/entrypoint-ai.sh

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/docker/entrypoint-ai.sh"]
# Default command (sobrescribible con docker compose run ... bash)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

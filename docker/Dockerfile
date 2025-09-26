# Multi-stage Dockerfile for production deployment
FROM python:3.12.2-slim as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Production stage
FROM python:3.12.2-slim as production

WORKDIR /app

# Security: Create non-root user
RUN groupadd --gid 1001 appuser && \
    useradd --no-create-home --uid 1001 --gid appuser --shell /bin/false appuser

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels and install
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache /wheels/* && rm -rf /wheels

# Copy application code
COPY --chown=appuser:appuser ./src /app/src
COPY --chown=appuser:appuser ./locales /app/locales
COPY --chown=appuser:appuser ./migrations /app/migrations

# Security hardening
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

EXPOSE 8080

# Use exec form for proper signal handling
CMD ["python", "-m", "src.bot"]
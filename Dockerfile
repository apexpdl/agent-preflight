FROM python:3.12-slim AS base

LABEL maintainer="Apex Poudel"
LABEL description="Preflight Execution Firewall for AI Agents"
LABEL version="2.0.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
COPY agent_preflight/ agent_preflight/
COPY trust_kernel/ trust_kernel/

RUN pip install -e ".[server]"

# Create non-root user
RUN groupadd -r preflight && useradd -r -g preflight -d /app preflight && \
    chown -R preflight:preflight /app

USER preflight

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "trust_kernel.api:create_trustkernel_api", "--host", "0.0.0.0", "--port", "8000", "--factory"]

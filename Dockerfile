# 🚀 MCP SDK Multi-stage Dockerfile
# Optimized for development, testing, and production

# 📦 Base stage - Install system dependencies
FROM python:3.12-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster package management
RUN pip install uv

# Set workspace
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen

# 🔧 Development stage
FROM base as development
ENV ENVIRONMENT=development

# Install development dependencies
RUN uv sync --frozen --dev

# Copy source code
COPY . .

# Install pre-commit hooks
RUN uv run pre-commit install

# Expose port for development server
EXPOSE 8000

# Default command for development (serve docs)
CMD ["uv", "run", "mkdocs", "serve", "--host", "0.0.0.0"]

# 🧪 Test stage
FROM development as test
ENV ENVIRONMENT=test

# Run comprehensive tests
RUN uv run pytest tests/ -v --cov=mcp_sdk --cov-report=term-missing --cov-fail-under=80

# 🚀 Production stage
FROM base as production
ENV ENVIRONMENT=production

# Install only production dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY mcp_sdk/ ./mcp_sdk/
COPY README.md ./

# Create non-root user for security
RUN groupadd -r mcpuser && useradd -r -g mcpuser -m mcpuser

# Change ownership to non-root user
RUN chown -R mcpuser:mcpuser /app

# Switch to non-root user
USER mcpuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD uv run python -c "import mcp_sdk; print('✅ MCP SDK is healthy')" || exit 1

# Expose port for MCP server
EXPOSE 8000

# Default command
CMD ["uv", "run", "python", "-m", "mcp_sdk"]

# 🏷️ Labels for metadata
LABEL org.opencontainers.image.title="MCP SDK" \
      org.opencontainers.image.description="Autonomous Reality Orchestration Platform" \
      org.opencontainers.image.vendor="MCP SDK Community" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/mcp-sdk/mcp-sdk" \
      org.opencontainers.image.version="0.1.0"

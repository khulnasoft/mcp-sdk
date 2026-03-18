#!/bin/bash
# Development setup script for MCP SDK
# This script sets up a complete development environment

set -e

echo "🚀 Setting up MCP SDK development environment..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "🐍 Creating virtual environment..."
    uv venv
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "📚 Installing dependencies..."
uv pip install -e ".[dev,docs]"

# Set up pre-commit hooks
echo "🪝 Setting up pre-commit hooks..."
uv pre-commit install

# Create development configuration
echo "⚙️ Creating development configuration..."
cat > .env << EOF
# Development environment variables
ENVIRONMENT=development
LOG_LEVEL=debug
PYTHONPATH=$(pwd)

# Database (for testing)
DATABASE_URL=sqlite:///./test.db

# Redis (for testing)
REDIS_URL=redis://localhost:6379/0

# MCP Server
MCP_HOST=localhost
MCP_PORT=8080
EOF

# Run initial tests to verify setup
echo "🧪 Running initial tests..."
uv pytest tests/ -v --tb=short

# Run code quality checks
echo "🔍 Running code quality checks..."
ruff check mcp_sdk/ tests/ --no-fix
ruff format --check mcp_sdk/ tests/

echo "✅ Development environment setup complete!"
echo ""
echo "🎯 Next steps:"
echo "  1. Activate the environment: source .venv/bin/activate"
echo "  2. Run tests: uv pytest tests/"
echo "  3. Start development server: make docs"
echo "  4. Run examples: make run-a2a"
echo ""
echo "📖 For more information, see the README.md file."

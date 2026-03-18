#!/bin/bash
# Setup pre-commit hooks for MCP SDK

set -e

echo "🚀 Setting up pre-commit hooks for MCP SDK..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Please install uv first."
    echo "   Visit: https://github.com/astral-sh/uv"
    exit 1
fi

# Check if pre-commit is installed
if ! command -v pre-commit &> /dev/null; then
    echo "📦 Installing pre-commit..."
    uv pip install pre-commit
fi

# Install pre-commit hooks
echo "🔧 Installing pre-commit hooks..."
pre-commit install

# Install commit-msg hook for conventional commits
echo "📝 Installing commit message hook..."
pre-commit install --hook-type commit-msg

# Run pre-commit on all files to ensure everything is clean
echo "🧹 Running pre-commit on all files..."
pre-commit run --all-files

echo "✅ Pre-commit hooks setup complete!"
echo ""
echo "📋 What's been configured:"
echo "   • Code formatting (black, ruff)"
echo "   • Import sorting (isort)"
echo "   • Type checking (mypy)"
echo "   • Security scanning (bandit, detect-secrets)"
echo "   • Documentation checks (pydocstyle)"
echo "   • File quality checks (trailing spaces, YAML/JSON validation)"
echo "   • Commit message validation (conventional commits)"
echo ""
echo "🎯 Pre-commit hooks will now run automatically on each commit."
echo "   To run manually: pre-commit run --all-files"
echo "   To skip hooks: git commit --no-verify"

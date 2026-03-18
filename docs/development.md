# Development Guide

This guide covers contributing to the MCP SDK, including setup, development workflow, and best practices.

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Code Style and Quality](#code-style-and-quality)
- [Testing](#testing)
- [Documentation](#documentation)
- [Plugin Development](#plugin-development)
- [Release Process](#release-process)
- [Debugging Tips](#debugging-tips)

## Development Setup

### Prerequisites

- **Python**: 3.11 or higher
- **uv**: Modern Python package manager (recommended)
- **Git**: Version control
- **Docker**: Container runtime (optional)
- **Node.js**: 18+ (for frontend components, if applicable)

### Quick Setup

```bash
# Clone the repository
git clone https://github.com/your-org/mcp-sdk.git
cd mcp-sdk

# Run the setup script
./scripts/setup-dev.sh

# Or manual setup
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev,docs]"
```

### Development Environment

```bash
# Install pre-commit hooks
uv pre-commit install

# Verify installation
make test
make lint
make docs

# Start development server
make dev
```

### IDE Configuration

#### VS Code

Create `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": "./.venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.ruffEnabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests/"],
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true,
        ".pytest_cache": true,
        ".mypy_cache": true
    }
}
```

Create `.vscode/launch.json`:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Debug MCP Server",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/mcp_sdk/main.py",
            "args": ["--debug", "--port", "8080"],
            "console": "integratedTerminal",
            "env": {
                "MCP_DEBUG": "true",
                "MCP_OBS_LOG_LEVEL": "DEBUG"
            }
        }
    ]
}
```

#### PyCharm

1. Open the project directory
2. Configure Python interpreter to use `.venv`
3. Enable `ruff` and `mypy` inspections
4. Configure pytest as the test runner

## Project Structure

```
mcp-sdk/
├── mcp_sdk/                 # Main package
│   ├── agents/             # Agent framework
│   ├── client/             # MCP client implementation
│   ├── core/               # Core components
│   │   ├── config.py       # Configuration management
│   │   ├── error_handling.py
│   │   ├── monitoring.py   # Monitoring and metrics
│   │   ├── performance.py  # Performance optimization
│   │   ├── plugin_manager.py
│   │   ├── protocol.py     # MCP protocol implementation
│   │   └── retry.py        # Retry mechanisms
│   ├── plugins/            # Built-in plugins
│   ├── security/           # Security components
│   ├── server/             # MCP server implementation
│   ├── tools/              # Tool registry
│   └── transport/          # Transport layers
├── plugins/                # External plugins
├── tests/                  # Test suite
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   └── fixtures/          # Test fixtures
├── docs/                  # Documentation
├── scripts/               # Development scripts
├── examples/              # Example applications
└── mkdocs.yml            # Documentation configuration
```

### Core Components

#### `mcp_sdk/core/`

- **`config.py`**: Configuration management with environment variable support
- **`protocol.py`**: MCP protocol implementation and server capabilities
- **`plugin_manager.py`**: Plugin discovery, loading, and lifecycle management
- **`monitoring.py`**: Metrics collection, health checks, and performance tracking
- **`performance.py`**: Caching, connection pooling, and optimization features
- **`error_handling.py`**: Custom exceptions and error handling utilities
- **`retry.py`**: Retry mechanisms with exponential backoff

#### `mcp_sdk/agents/`

- **`base.py`**: Base agent class and agent lifecycle management
- **`a2a.py`**: Agent-to-Agent interaction patterns
- **`b2b.py`**: Business-to-Business agent patterns
- **`b2c.py`**: Business-to-Consumer agent patterns

#### `mcp_sdk/security/`

- **`auth.py`**: Authentication and authorization system
- **`middleware.py`**: Security middleware for HTTP and WebSocket

## Development Workflow

### 1. Create a Feature Branch

```bash
# Create and checkout a new branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/issue-number-description
```

### 2. Make Changes

```bash
# Make your changes
# ...

# Run tests frequently
make test

# Check code quality
make lint
make type-check

# Run specific tests
uv pytest tests/unit/test_specific_module.py
```

### 3. Commit Changes

```bash
# Stage changes
git add .

# Commit with conventional commit message
git commit -m "feat: add new authentication middleware"

# For bug fixes
git commit -m "fix: resolve memory leak in plugin manager"

# For documentation
git commit -m "docs: update API reference for security module"
```

### 4. Push and Create Pull Request

```bash
# Push to your fork
git push origin feature/your-feature-name

# Create pull request on GitHub
# Include description and testing instructions
```

### Commit Message Convention

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat(auth): add JWT token refresh mechanism

Implement automatic token refresh with configurable
expiry time and retry logic.

Closes #123
```

```
fix(plugin): resolve memory leak in plugin manager

Plugin manager was not properly cleaning up resources
when plugins were unloaded, causing memory leaks.

Fixes #456
```

## Code Style and Quality

### Code Formatting

We use **Black** for code formatting:

```bash
# Format code
make format

# Or manually
uv run black mcp_sdk/ tests/
uv run isort mcp_sdk/ tests/
```

### Linting

We use **Ruff** for linting:

```bash
# Run linter
make lint

# Or manually
uv run ruff check mcp_sdk/ tests/

# Fix auto-fixable issues
uv run ruff check --fix mcp_sdk/ tests/
```

### Type Checking

We use **MyPy** for type checking:

```bash
# Run type checker
make type-check

# Or manually
uv run mypy mcp_sdk/
```

### Pre-commit Hooks

Pre-commit hooks ensure code quality:

```bash
# Install hooks
uv pre-commit install

# Run hooks manually
uv pre-commit run --all-files
```

### Code Quality Standards

1. **Type Annotations**: All public functions must have type hints
2. **Docstrings**: All public classes and functions must have docstrings
3. **Error Handling**: Use proper error handling with custom exceptions
4. **Logging**: Use structured logging with `structlog`
5. **Testing**: Write tests for all new functionality

#### Example Code Style

```python
"""
Module docstring describing the purpose of this module.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from pydantic import BaseModel

from mcp_sdk.core.error_handling import handle_errors

logger = structlog.get_logger(__name__)


class ExampleModel(BaseModel):
    """Example model with proper type hints and validation.
    
    Attributes:
        name: The name of the example
        value: The value associated with the example
    """
    
    name: str
    value: int


@handle_errors("EXAMPLE_OPERATION")
async def example_function(param: str, config: dict[str, Any]) -> ExampleModel:
    """Example function with proper documentation and error handling.
    
    Args:
        param: The input parameter
        config: Configuration dictionary
        
    Returns:
        ExampleModel: The processed result
        
    Raises:
        ValueError: If the parameter is invalid
    """
    logger.info("Processing example", param=param)
    
    if not param:
        raise ValueError("Parameter cannot be empty")
    
    # Process the parameter
    result = ExampleModel(name=param, value=len(param))
    
    logger.info("Example processed successfully", result=result.dict())
    return result
```

## Testing

### Test Structure

```
tests/
├── unit/                   # Unit tests
│   ├── test_config.py
│   ├── test_protocol.py
│   └── test_agents.py
├── integration/            # Integration tests
│   ├── test_mcp_protocol.py
│   ├── test_agent_lifecycle.py
│   └── test_plugin_system.py
├── fixtures/              # Test fixtures
│   ├── sample_config.yaml
│   └── test_data.json
└── conftest.py            # Pytest configuration
```

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
uv pytest tests/unit/test_config.py

# Run with coverage
uv pytest --cov=mcp_sdk --cov-report=html

# Run integration tests only
uv pytest tests/integration/

# Run with specific markers
uv pytest -m "not slow"
uv pytest -m "integration"
```

### Writing Tests

#### Unit Tests

```python
# tests/unit/test_example.py
import pytest
from unittest.mock import AsyncMock, patch

from mcp_sdk.core.example import ExampleModel, example_function


class TestExampleModel:
    """Test cases for ExampleModel."""
    
    def test_model_creation(self):
        """Test model creation with valid data."""
        model = ExampleModel(name="test", value=42)
        assert model.name == "test"
        assert model.value == 42
    
    def test_model_validation(self):
        """Test model validation."""
        with pytest.raises(ValueError):
            ExampleModel(name="", value=42)


class TestExampleFunction:
    """Test cases for example_function."""
    
    @pytest.mark.asyncio
    async def test_function_success(self):
        """Test successful function execution."""
        result = await example_function("test", {})
        assert result.name == "test"
        assert result.value == 4
    
    @pytest.mark.asyncio
    async def test_function_error(self):
        """Test function error handling."""
        with pytest.raises(ValueError, match="Parameter cannot be empty"):
            await example_function("", {})
    
    @pytest.mark.asyncio
    @patch("mcp_sdk.core.example.logger")
    async def test_function_logging(self, mock_logger):
        """Test function logging."""
        await example_function("test", {})
        
        mock_logger.info.assert_called()
        # Verify log calls
```

#### Integration Tests

```python
# tests/integration/test_protocol_integration.py
import pytest
from mcp_sdk.core.protocol import MCPProtocol
from mcp_sdk.client.session import MCPClientSession


@pytest.mark.asyncio
class TestProtocolIntegration:
    """Integration tests for MCP protocol."""
    
    async def test_tool_lifecycle(self):
        """Test complete tool lifecycle."""
        # Create protocol with test tool
        protocol = MCPProtocol("test-server", "1.0.0")
        
        @protocol.tool("test_tool", "Test tool")
        async def test_tool(message: str) -> str:
            return f"Processed: {message}"
        
        # Start server (in background)
        server_task = asyncio.create_task(protocol.serve())
        
        try:
            # Connect client
            client = MCPClientSession("http://localhost:8080")
            await client.initialize()
            
            # List tools
            tools = await client.list_tools()
            assert any(t.name == "test_tool" for t in tools.tools)
            
            # Call tool
            result = await client.call_tool("test_tool", {"message": "hello"})
            assert "Processed: hello" in result.content[0].text
            
        finally:
            server_task.cancel()
```

### Test Fixtures

```python
# tests/conftest.py
import pytest
import tempfile
from pathlib import Path

@pytest.fixture
async def temp_config_file():
    """Create a temporary configuration file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
        environment: testing
        debug: true
        database:
          url: "sqlite:///:memory:"
        """)
        yield Path(f.name)
    
    # Cleanup
    Path(f.name).unlink()

@pytest.fixture
async def mock_protocol():
    """Create a mock MCP protocol for testing."""
    protocol = MCPProtocol("test-server", "1.0.0")
    
    @protocol.tool("echo", "Echo tool")
    async def echo_tool(message: str) -> str:
        return f"Echo: {message}"
    
    return protocol
```

### Test Markers

Use pytest markers to categorize tests:

```python
# Mark slow tests
@pytest.mark.slow
async def test_slow_operation():
    await asyncio.sleep(10)

# Mark integration tests
@pytest.mark.integration
async def test_database_integration():
    pass

# Mark tests that require external services
@pytest.mark.requires_external
async def test_api_call():
    pass
```

## Documentation

### Documentation Structure

```
docs/
├── index.md              # Homepage
├── user-guide.md         # User guide
├── api-reference.md      # API reference
├── examples.md           # Code examples
├── deployment.md         # Deployment guide
├── troubleshooting.md    # Troubleshooting
├── development.md        # Development guide
└── roadmap.md           # Project roadmap
```

### Writing Documentation

#### Markdown Format

Use standard Markdown with extensions:

```markdown
# Heading

## Subheading

### Code Examples

```python
# Code block with syntax highlighting
def example():
    return "Hello, World!"
```

### Tables

| Column 1 | Column 2 |
|----------|----------|
| Value 1  | Value 2  |

### Notes and Warnings

!!! note
    This is a note.

!!! warning
    This is a warning.

!!! tip
    This is a tip.
```

#### API Documentation

Document all public APIs:

```python
def example_function(param1: str, param2: int = 42) -> str:
    """Example function with comprehensive docstring.
    
    Args:
        param1: The first parameter (required)
        param2: The second parameter (optional, defaults to 42)
        
    Returns:
        A formatted string combining the parameters
        
    Raises:
        ValueError: If param1 is empty
        TypeError: If param1 is not a string
        
    Example:
        >>> example_function("hello", 100)
        'hello-100'
        
    Note:
        This function is used throughout the codebase for
        demonstrating proper documentation practices.
    """
    return f"{param1}-{param2}"
```

### Building Documentation

```bash
# Build documentation
make docs

# Serve documentation locally
make docs-serve

# Or manually
uv run mkdocs serve --host 0.0.0.0
```

## Plugin Development

### Creating a Plugin

1. **Create Plugin Directory**:

```bash
mkdir plugins/my_plugin
cd plugins/my_plugin
```

2. **Create Plugin Manifest**:

```yaml
# manifest.yaml
name: my_plugin
version: 1.0.0
description: My custom plugin
main: __init__.py
dependencies: []
capabilities: [tools, resources]
config:
  api_key:
    type: string
    description: API key for external service
    required: true
  timeout:
    type: integer
    description: Request timeout in seconds
    default: 30
```

3. **Implement Plugin**:

```python
# __init__.py
from mcp_sdk.core.plugin import MCPPlugin
from mcp_sdk.core.registry import PluginRegistry

class MyPlugin(MCPPlugin):
    """My custom plugin implementation."""
    
    @property
    def name(self) -> str:
        return "my_plugin"
    
    async def on_activate(self, protocol):
        """Initialize plugin."""
        self.api_key = protocol.config.get("my_plugin_api_key")
        await super().on_activate(protocol)
    
    def register_tools(self, registry: PluginRegistry):
        """Register plugin tools."""
        
        async def my_tool(param: str) -> str:
            """Plugin tool implementation."""
            return f"Processed by plugin: {param}"
        
        registry.register_tool(
            "my_plugin.tool",
            my_tool,
            {"description": "A tool from my plugin"}
        )
```

4. **Test Plugin**:

```python
# tests/test_my_plugin.py
import pytest
from mcp_sdk.core.plugin_manager import PluginManager
from mcp_sdk.core.registry import PluginRegistry

@pytest.mark.asyncio
async def test_my_plugin():
    """Test plugin loading and functionality."""
    registry = PluginRegistry()
    manager = PluginManager(registry, plugin_dirs=["./plugins"])
    
    # Load plugin
    plugins = await manager.load_all()
    assert "my_plugin" in plugins
    
    # Test tool
    result = await registry.call_tool("my_plugin.tool", {"param": "test"})
    assert "Processed by plugin" in result
```

### Plugin Best Practices

1. **Error Handling**: Handle all errors gracefully
2. **Configuration**: Validate configuration on activation
3. **Resource Management**: Clean up resources on deactivation
4. **Logging**: Use structured logging for debugging
5. **Testing**: Write comprehensive tests for all functionality

## Release Process

### Version Management

We use [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

1. **Update Version**:
   ```bash
   # Update version in pyproject.toml
   # Update version in mcp_sdk/__init__.py
   ```

2. **Update Changelog**:
   ```bash
   # Add changes to CHANGELOG.md
   ```

3. **Run Full Test Suite**:
   ```bash
   make test
   make lint
   make type-check
   ```

4. **Build Documentation**:
   ```bash
   make docs
   ```

5. **Create Release Tag**:
   ```bash
   git tag -a v1.2.3 -m "Release version 1.2.3"
   git push origin v1.2.3
   ```

6. **Build and Publish**:
   ```bash
   # Build package
   uv build
   
   # Publish to PyPI
   uv publish
   ```

### Automated Releases

GitHub Actions can automate releases:

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install uv
          uv pip install -e ".[dev]"
      
      - name: Run tests
        run: make test
      
      - name: Build package
        run: uv build
      
      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: uv publish
```

## Debugging Tips

### Enable Debug Mode

```bash
# Environment variable
export MCP_DEBUG=true

# Or in code
from mcp_sdk.core.config import ConfigContext

with ConfigContext(debug=True):
    # Your code here
    pass
```

### Use Debugger

```python
# Add breakpoints
import pdb; pdb.set_trace()

# Or use ipdb (better IPython integration)
import ipdb; ipdb.set_trace()

# For async code
import asyncio
import ipdb

async def debug_async():
    await ipdb.asyncio.aenter()
    # Your async code here
```

### Memory Profiling

```python
# Profile memory usage
import tracemalloc

tracemalloc.start()

# Your code here

# Get memory statistics
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

for stat in top_stats[:10]:
    print(stat)
```

### Performance Profiling

```python
# Profile function performance
import cProfile
import pstats

def profile_function():
    pr = cProfile.Profile()
    pr.enable()
    
    # Your code here
    
    pr.disable()
    stats = pstats.Stats(pr)
    stats.sort_stats('cumulative')
    stats.print_stats(10)

profile_function()
```

### Logging Debug Information

```python
import structlog

logger = structlog.get_logger(__name__)

# Add debug logging
logger.debug("Processing request", 
           request_id="123", 
           user_id="456",
           operation="process_data")

# Log exceptions with context
try:
    risky_operation()
except Exception as e:
    logger.error("Operation failed", 
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True)
```

### Common Debugging Scenarios

#### Plugin Loading Issues

```python
# Debug plugin loading
async def debug_plugin_loading():
    registry = PluginRegistry()
    manager = PluginManager(registry, plugin_dirs=["./plugins"])
    
    # Discover plugins
    discovered = await manager.discover()
    print(f"Discovered plugins: {[p.name for p in discovered]}")
    
    # Try loading each plugin
    for plugin in discovered:
        try:
            loaded = await manager.load_plugin(plugin.name)
            print(f"Loaded plugin: {plugin.name}")
        except Exception as e:
            print(f"Failed to load {plugin.name}: {e}")
            import traceback
            traceback.print_exc()
```

#### Configuration Issues

```python
# Debug configuration
from mcp_sdk.core.config import get_config

def debug_config():
    config = get_config()
    
    print("Configuration:")
    print(f"  Environment: {config.environment}")
    print(f"  Debug: {config.debug}")
    print(f"  Database URL: {config.get_database_url()}")
    print(f"  Redis URL: {config.get_redis_url()}")
    
    # Validate configuration
    try:
        config.validate()
        print("Configuration is valid")
    except Exception as e:
        print(f"Configuration error: {e}")
```

This development guide should help you get started with contributing to the MCP SDK. For more specific questions, don't hesitate to reach out to the community or create an issue on GitHub.

# Pre-commit Hooks

This document explains the pre-commit configuration and how to use it effectively in the MCP SDK project.

## Overview

Pre-commit hooks are automated checks that run before each commit to ensure code quality, security, and consistency. The MCP SDK uses a comprehensive pre-commit setup that includes:

- **Code formatting** (black, ruff)
- **Import sorting** (isort)
- **Type checking** (mypy)
- **Security scanning** (bandit, detect-secrets)
- **Documentation checks** (pydocstyle)
- **File quality checks** (YAML/JSON validation, trailing spaces)
- **Commit message validation** (conventional commits)

## Setup

### Automatic Setup

The easiest way to set up pre-commit hooks is to run:

```bash
make dev
```

This will:
1. Install development dependencies
2. Install pre-commit hooks
3. Run the setup script to configure everything

### Manual Setup

If you prefer to set up manually:

```bash
# Install pre-commit
uv pip install pre-commit

# Install hooks
pre-commit install

# Install commit message hook
pre-commit install --hook-type commit-msg

# Run on all files initially
pre-commit run --all-files
```

## Configuration

### Main Configuration File

The pre-commit configuration is in `.pre-commit-config.yaml`. Key sections:

```yaml
repos:
  # Built-in hooks for basic checks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    
  # Python formatting
  - repo: https://github.com/psf/black
    
  # Import sorting
  - repo: https://github.com/pycqa/isort
    
  # Python linting
  - repo: https://github.com/astral-sh/ruff-pre-commit
    
  # Type checking
  - repo: https://github.com/pre-commit/mirrors-mypy
    
  # Security scanning
  - repo: https://github.com/PyCQA/bandit
    
  # Documentation
  - repo: https://github.com/pycqa/pydocstyle
```

### Tool Configuration

Each tool is configured in `pyproject.toml`:

```toml
[tool.black]
line-length = 100
target-version = ["py311"]

[tool.isort]
profile = "black"
line_length = 100

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true

[tool.bandit]
exclude_dirs = ["tests", "docs", "examples"]
```

## Available Hooks

### Code Quality Hooks

#### Black (Code Formatting)
- **Purpose**: Ensures consistent code formatting
- **Files**: All Python files
- **Config**: Line length 100, Python 3.11+ target

#### Ruff (Linting & Formatting)
- **Purpose**: Fast Python linter and formatter
- **Files**: All Python files
- **Config**: Comprehensive rule set with auto-fix

#### isort (Import Sorting)
- **Purpose**: Sorts imports consistently
- **Files**: All Python files
- **Config**: Black-compatible profile

#### MyPy (Type Checking)
- **Purpose**: Static type analysis
- **Files**: Source code (excludes tests, docs, examples)
- **Config**: Strict mode with ignore missing imports

### Security Hooks

#### Bandit (Security Linter)
- **Purpose**: Finds common security issues
- **Files**: Source code (excludes tests)
- **Config**: Custom skips for specific rules

#### detect-secrets (Secret Detection)
- **Purpose**: Prevents committing secrets
- **Files**: All files
- **Config**: Baseline file for known false positives

### Documentation Hooks

#### pydocstyle (Docstring Checking)
- **Purpose**: Ensures docstring quality
- **Files**: Source code
- **Config**: Google convention with specific ignores

### File Quality Hooks

#### Basic File Checks
- **Trailing whitespace**: Removes trailing spaces
- **End-of-file-fixer**: Ensures files end with newline
- **YAML/JSON validation**: Validates configuration files
- **Merge conflict markers**: Detects unresolved conflicts

#### Executable Checks
- **Shebang validation**: Ensures scripts have proper shebangs
- **Executable permissions**: Checks executable files have shebangs

### Commit Message Hooks

#### commitizen (Commit Message Validation)
- **Purpose**: Enforces conventional commit format
- **Stage**: commit-msg
- **Format**: `type(scope): description`

## Usage

### Daily Workflow

1. **Make changes to code**
2. **Stage changes**: `git add .`
3. **Commit**: `git commit -m "feat: add new feature"`
4. **Pre-commit hooks run automatically**

### Manual Hook Execution

Run hooks manually without committing:

```bash
# Run all hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run black --files mcp_sdk/example.py

# Run hooks on staged files only
pre-commit run
```

### Skipping Hooks

If you need to skip hooks (not recommended):

```bash
git commit --no-verify -m "commit message"
```

### Updating Hooks

Update hook versions:

```bash
# Update to latest versions
pre-commit autoupdate

# Update and run on all files
make pre-commit-update
```

## Hook Details

### Black Formatting

```bash
# Manual formatting
black mcp_sdk/ tests/ examples/

# Check formatting without changing files
black --check mcp_sdk/ tests/ examples/
```

### Ruff Linting

```bash
# Run linter
ruff check mcp_sdk/ tests/

# Auto-fix issues
ruff check --fix mcp_sdk/ tests/

# Format with ruff
ruff format mcp_sdk/ tests/
```

### MyPy Type Checking

```bash
# Run type checking
mypy mcp_sdk/

# Check specific file
mypy mcp_sdk/core/protocol.py

# Strict mode (as configured)
mypy --strict mcp_sdk/
```

### Bandit Security

```bash
# Run security scan
bandit -r mcp_sdk/

# With configuration file
bandit -c pyproject.toml -r mcp_sdk/

# Specific severity level
bandit -r mcp_sdk/ -ll
```

### Secret Detection

```bash
# Scan for secrets
detect-secrets scan --baseline .secrets.baseline

# Update baseline
detect-secrets scan --baseline .secrets.baseline --update baseline
```

## Troubleshooting

### Common Issues

#### Hook Fails on Commit

1. **Check the error message** for specific issues
2. **Run hooks manually** to see full output:
   ```bash
   pre-commit run --all-files
   ```
3. **Fix issues** and try again

#### MyPy Import Errors

1. **Install type stubs**:
   ```bash
   uv pip install types-PyYAML types-redis types-requests
   ```
2. **Update configuration** if needed
3. **Use `# type: ignore`** for problematic imports

#### Secret Detection False Positives

1. **Update baseline**:
   ```bash
   detect-secrets scan --baseline .secrets.baseline --update baseline
   ```
2. **Add exceptions** to configuration

#### Performance Issues

1. **Exclude large files** from hooks
2. **Use `--files`** to run on specific files
3. **Consider caching** for expensive operations

### Configuration Issues

#### Hook Not Running

1. **Check installation**: `pre-commit --version`
2. **Reinstall hooks**: `pre-commit install`
3. **Check git hooks directory**: `.git/hooks/`

#### Configuration Not Applied

1. **Validate YAML**: `pre-commit validate-config`
2. **Check file paths** in configuration
3. **Verify tool versions** are compatible

## Best Practices

### Commit Message Format

Use conventional commits:

```
feat: add new authentication middleware
fix: resolve memory leak in plugin manager
docs: update API reference
test: add integration tests for agent lifecycle
refactor: simplify configuration management
```

### Code Quality

1. **Write tests** for new functionality
2. **Add type hints** to all public functions
3. **Write docstrings** following Google convention
4. **Follow naming conventions** (snake_case for variables, PascalCase for classes)

### Security

1. **Never commit secrets** or API keys
2. **Use environment variables** for configuration
3. **Run security scans** regularly
4. **Review dependencies** for vulnerabilities

### Performance

1. **Run hooks on specific files** when possible
2. **Use caching** for expensive operations
3. **Keep configuration minimal** but effective
4. **Update hooks regularly** for improvements

## Integration with CI/CD

### GitHub Actions

The pre-commit hooks integrate with CI/CD:

```yaml
- name: Run pre-commit
  run: |
    pre-commit run --all-files
```

### Makefile Integration

Use Makefile targets:

```bash
make pre-commit      # Run all hooks
make pre-commit-update # Update and run
make lint           # Run linting only
make format         # Format code only
```

## Contributing

When contributing to the MCP SDK:

1. **Set up pre-commit hooks** before making changes
2. **Run hooks manually** before committing
3. **Fix all hook failures** before pushing
4. **Update configuration** if adding new tools
5. **Document changes** in this guide

## Resources

- [Pre-commit Documentation](https://pre-commit.com/)
- [Black Documentation](https://black.readthedocs.io/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [MyPy Documentation](https://mypy.readthedocs.io/)
- [Bandit Documentation](https://bandit.readthedocs.io/)
- [Conventional Commits](https://www.conventionalcommits.org/)

This pre-commit setup ensures consistent code quality and security across the MCP SDK project.

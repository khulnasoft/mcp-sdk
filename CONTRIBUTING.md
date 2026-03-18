# Contributing to MCP SDK

## Commit Message Guidelines

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification for commit messages.

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Code formatting (no functional changes)
- **refactor**: Code refactoring
- **test**: Adding or updating tests
- **chore**: Build process, dependency updates, etc.

### Scope

The scope indicates the area of the codebase affected:
- `core`: Core MCP functionality
- `agents`: Agent management and orchestration
- `plugins`: Plugin system
- `auth`: Authentication and authorization
- `geospatial`: Geospatial features
- `myceloom`: Myceloom protocol
- `docs`: Documentation
- `tests`: Test infrastructure
- `build`: Build and deployment

### Examples

```
feat(core): add MCP protocol message parsing

Implement comprehensive message parsing for the MCP protocol
including support for request/response patterns and error handling.

Closes #123
```

```
fix(agents): resolve memory leak in agent lifecycle

Fixed memory leak where agent instances were not being properly
garbage collected after shutdown.

Fixes #456
```

```
docs(readme): update installation instructions

Added Docker installation method and updated Python version
requirements for better compatibility.
```

### Setup Git Commit Template

```bash
git config commit.template .gitmessage
```

This will automatically load the commit message template when you run `git commit`.

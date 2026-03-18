# API Reference

This document provides comprehensive API reference for the MCP SDK.

## Table of Contents

- [Core Components](#core-components)
- [Agent Framework](#agent-framework)
- [MCP Protocol](#mcp-protocol)
- [Security](#security)
- [Plugin System](#plugin-system)
- [Configuration](#configuration)
- [Monitoring](#monitoring)
- [Performance](#performance)

## Core Components

### MCPConfig

Main configuration class for the MCP SDK.

```python
from mcp_sdk.core.config import MCPConfig, get_config

# Get global configuration
config = get_config()

# Load from environment
config = MCPConfig.from_env(".env")

# Load from file
config = MCPConfig.from_file(Path("config.yaml"))

# Access configuration sections
db_config = config.database
auth_config = config.auth
server_config = config.server
```

#### Configuration Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `environment` | `Environment` | `DEVELOPMENT` | Application environment |
| `debug` | `bool` | `False` | Enable debug mode |
| `database` | `DatabaseConfig` | - | Database configuration |
| `redis` | `RedisConfig` | - | Redis configuration |
| `auth` | `AuthConfig` | - | Authentication configuration |
| `server` | `ServerConfig` | - | Server configuration |
| `observability` | `ObservabilityConfig` | - | Monitoring configuration |

### Error Handling

Comprehensive error handling with custom exceptions.

```python
from mcp_sdk.core.error_handling import (
    MCPException,
    AuthenticationError,
    AuthorizationError,
    handle_errors,
    error_context,
)

# Custom exceptions
try:
    # Your code here
    raise AuthenticationError("Invalid credentials")
except AuthenticationError as e:
    print(f"Authentication failed: {e}")

# Error handling decorator
@handle_errors("OPERATION_ERROR")
async def risky_operation():
    # Automatically handles and logs errors
    pass

# Error context
async with error_context("user_operation", {"user_id": "123"}):
    # Operations here get automatic error context
    pass
```

### Retry Mechanisms

Built-in retry logic with exponential backoff.

```python
from mcp_sdk.core.retry import (
    retry_async,
    RetryConfig,
    CircuitBreaker,
)

# Retry configuration
retry_config = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=10.0,
    exponential_base=2.0,
    jitter=True,
)

# Retry decorator
@retry_async(retry_config)
async def unstable_operation():
    # Will be retried on failure
    pass

# Circuit breaker
breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=30.0,
    expected_exception=ConnectionError,
)

async with breaker:
    # Operation will fail fast if circuit is open
    await unstable_operation()
```

## Agent Framework

### BaseAgent

Base class for all agent types.

```python
from mcp_sdk.agents.base import BaseAgent, AgentMessage, AgentContext, AgentResponse

class MyAgent(BaseAgent):
    AGENT_TYPE = "custom_agent"
    
    def __init__(self, name: str, **kwargs):
        super().__init__(name, **kwargs)
    
    async def handle_message(
        self, 
        message: AgentMessage, 
        context: AgentContext
    ) -> AgentResponse:
        """Handle incoming messages."""
        return AgentResponse(
            success=True,
            data=f"Processed: {message.content}",
            agent_id=self.id,
            context=context
        )
    
    def get_capabilities(self) -> list[str]:
        """Return agent capabilities."""
        return ["message_processing", "custom_capability"]
```

#### Agent Lifecycle

```python
# Create agent
agent = MyAgent("my-agent", description="A custom agent")

# Start agent
await agent.start()

# Check state
assert agent.state == AgentState.READY
assert agent.is_running

# Process message
message = AgentMessage(
    sender_id="user",
    recipient_id=agent.id,
    content="Hello"
)
context = AgentContext(user_id="123")
response = await agent.handle_message(message, context)

# Stop agent
await agent.stop()
```

#### Agent States

| State | Description |
|-------|-------------|
| `INITIALIZING` | Agent is starting up |
| `READY` | Agent is ready to process messages |
| `BUSY` | Agent is currently processing |
| `ERROR` | Agent encountered an error |
| `SHUTTING_DOWN` | Agent is stopping |
| `SHUTDOWN` | Agent is stopped |

### Agent Types

#### A2AAgent (Agent-to-Agent)

```python
from mcp_sdk.agents.a2a import A2AAgent

class AgentA(A2AAgent):
    async def handle_message(self, message, context):
        # Handle messages from other agents
        return AgentResponse(data={"reply": "Message received"})

class AgentB(A2AAgent):
    async def handle_message(self, message, context):
        # Process and potentially forward to other agents
        return AgentResponse(data={"status": "processed"})
```

#### B2CAgent (Business-to-Consumer)

```python
from mcp_sdk.agents.b2c import B2CAgent

class SupportBot(B2CAgent):
    async def handle_message(self, message, context):
        # Handle customer interactions
        return AgentResponse(
            data={"reply": "How can I help you today?"},
            metadata={"support_ticket": context.metadata.get("ticket_id")}
        )
```

#### B2BAgent (Business-to-Business)

```python
from mcp_sdk.agents.b2b import B2BAgent

class PartnerAgent(B2BAgent):
    def __init__(self, name: str, tenant_id: str, **kwargs):
        super().__init__(name, tenant_id=tenant_id, **kwargs)
    
    async def handle_message(self, message, context):
        # Verify tenant access
        if context.tenant_id != self.tenant_id:
            return AgentResponse(
                success=False,
                error="Tenant access denied"
            )
        
        return AgentResponse(data={"status": "authorized"})
```

## MCP Protocol

### MCPProtocol

Main protocol handler for MCP servers.

```python
from mcp_sdk.core.protocol import MCPProtocol
from mcp_sdk.types import Tool, Resource, Prompt

# Create protocol instance
protocol = MCPProtocol(
    name="my-server",
    version="1.0.0",
    config=config
)

# Register tools
@protocol.tool("calculator", "Perform calculations")
async def calculator(operation: str, a: float, b: float) -> float:
    if operation == "add":
        return a + b
    elif operation == "multiply":
        return a * b
    else:
        raise ValueError(f"Unsupported operation: {operation}")

# Register resources
@protocol.resource("data://items/*")
async def get_item_data(uri: str) -> str:
    item_id = uri.split("/")[-1]
    return f"Data for item {item_id}"

# Register prompts
@protocol.prompt("summary", "Generate a summary")
async def summary_prompt() -> str:
    return "Please provide a concise summary of the given content."

# Start server
await protocol.serve()
```

### Protocol Handlers

#### Tool Registration

```python
@protocol.tool(
    name="tool_name",
    description="Tool description",
    input_schema={
        "type": "object",
        "properties": {
            "param1": {"type": "string"},
            "param2": {"type": "integer", "default": 42}
        },
        "required": ["param1"]
    }
)
async def my_tool(param1: str, param2: int = 42) -> str:
    return f"Result: {param1} + {param2}"
```

#### Resource Registration

```python
@protocol.resource("resource://path/*")
async def resource_handler(uri: str) -> str:
    # Handle resource requests
    return f"Resource content for {uri}"

@protocol.resource("api://data/{id}")
async def api_resource(id: str) -> dict:
    # Return structured data
    return {"id": id, "data": "example"}
```

#### Prompt Registration

```python
@protocol.prompt("prompt_name", "Prompt description")
async def prompt_handler() -> str:
    return "This is a prompt template with {placeholder}."

@protocol.prompt("dynamic/{type}")
async def dynamic_prompt(type: str) -> str:
    return f"Generate a {type} response."
```

### Client Usage

```python
from mcp_sdk.client.session import MCPClientSession

# Connect to server
client = MCPClientSession("http://localhost:8080")
await client.initialize()

# List tools
tools = await client.list_tools()
print(f"Available tools: {[t.name for t in tools.tools]}")

# Call tool
result = await client.call_tool("calculator", {
    "operation": "add",
    "a": 5,
    "b": 3
})
print(f"Result: {result.content[0].text}")

# List resources
resources = await client.list_resources()
for resource in resources.resources:
    data = await client.read_resource(resource.uri)
    print(f"{resource.uri}: {data.contents[0].text}")

# List prompts
prompts = await client.list_prompts()
for prompt in prompts.prompts:
    prompt_data = await client.get_prompt(prompt.name)
    print(f"{prompt.name}: {prompt_data.messages[0].content.text}")
```

## Security

### Authentication

```python
from mcp_sdk.security.auth import SecurityManager, get_security_manager

# Get security manager
security = get_security_manager()

# Create user
user = await security.create_user(
    username="john_doe",
    email="john@example.com",
    password="secure_password",
    roles=["user"]
)

# Authenticate
user, token = await security.authenticate("john_doe", "secure_password")
print(f"Access token: {token}")
```

### Authorization

```python
from mcp_sdk.security.auth import require_permission

# Protect functions with permissions
@require_permission("read", "users")
async def get_user_data(user_id: str):
    # Only users with read:users permission can access
    return {"user_id": user_id, "data": "sensitive"}

# Check permissions manually
has_permission = await security.authz_manager.check_permission(
    user, "write", "posts"
)
```

### Middleware

```python
from mcp_sdk.security.middleware import (
    AuthenticationMiddleware,
    AuthorizationMiddleware,
    require_auth,
    require_permission,
)
from fastapi import FastAPI

app = FastAPI()

# Add authentication middleware
app.add_middleware(AuthenticationMiddleware)

# Protect routes
@app.get("/admin")
@require_auth
@require_permission("admin")
async def admin_endpoint():
    return {"message": "Admin access granted"}

@app.get("/user")
@require_auth
async def user_endpoint():
    return {"message": "User access granted"}
```

### JWT Handling

```python
# Validate token
token_info = await security.auth_manager.validate_token(token)

# Refresh token
new_token = await security.auth_manager.refresh_token(refresh_token)

# Revoke token
await security.auth_manager.revoke_token(refresh_token)
```

## Plugin System

### Creating Plugins

```python
from mcp_sdk.core.plugin import MCPPlugin
from mcp_sdk.core.registry import PluginRegistry

class MyPlugin(MCPPlugin):
    @property
    def name(self) -> str:
        return "my_plugin"
    
    async def on_activate(self, protocol):
        """Initialize plugin."""
        self.protocol = protocol
        await super().on_activate(protocol)
    
    def register_tools(self, registry: PluginRegistry):
        """Register plugin tools."""
        
        async def plugin_tool(message: str) -> str:
            return f"Plugin processed: {message}"
        
        registry.register_tool(
            "my_plugin.tool",
            plugin_tool,
            {"description": "A tool from my plugin"}
        )
```

### Plugin Manager

```python
from mcp_sdk.core.plugin_manager import PluginManager
from mcp_sdk.core.registry import PluginRegistry

# Create plugin manager
registry = PluginRegistry()
plugin_manager = PluginManager(registry, plugin_dirs=["./plugins"])

# Load all plugins
plugins = await plugin_manager.load_all()

# Load specific plugin
plugin = await plugin_manager.load_plugin("my_plugin")

# Unload plugin
await plugin_manager.unload_plugin("my_plugin")

# Get plugin status
status = await plugin_manager.get_plugin_status("my_plugin")
```

### Tool Registration

```python
# Register tool with metadata
registry.register_tool(
    "tool_name",
    tool_function,
    {
        "description": "Tool description",
        "parameters": {
            "param1": {"type": "string", "required": True},
            "param2": {"type": "integer", "default": 42}
        },
        "plugin_name": "my_plugin"
    }
)

# Call tool
result = await registry.call_tool("tool_name", {"param1": "value"})
```

## Configuration

### Environment Variables

```bash
# Database
MCP_DB_URL=postgresql://user:pass@localhost/db
MCP_DB_POOL_SIZE=20

# Redis
MCP_REDIS_URL=redis://localhost:6379/0
MCP_REDIS_MAX_CONNECTIONS=50

# Authentication
MCP_AUTH_SECRET_KEY=your-secret-key
MCP_AUTH_ALGORITHM=HS256
MCP_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Server
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=8080
MCP_SERVER_WORKERS=4

# Observability
MCP_OBS_LOG_LEVEL=INFO
MCP_OBS_ENABLE_TRACING=true
MCP_OBS_METRICS_PORT=9090
```

### Configuration Files

#### YAML Configuration

```yaml
# config.yaml
environment: production
debug: false

database:
  url: postgresql://user:pass@localhost/db
  pool_size: 20
  echo: false

redis:
  url: redis://localhost:6379/0
  max_connections: 50

auth:
  secret_key: your-secret-key
  algorithm: HS256
  access_token_expire_minutes: 30

server:
  host: 0.0.0.0
  port: 8080
  workers: 4

observability:
  log_level: INFO
  enable_tracing: true
  metrics_port: 9090

features:
  auth_enabled: true
  monitoring_enabled: true
  caching_enabled: true
```

#### Loading Configuration

```python
from mcp_sdk.core.config import MCPConfig

# Load from file
config = MCPConfig.from_file(Path("config.yaml"))

# Load with environment overrides
config = MCPConfig.from_env(".env")

# Create configuration context
with ConfigContext(debug=True, log_level="DEBUG"):
    # Temporary configuration changes
    pass
```

### Feature Flags

```python
from mcp_sdk.core.config import is_feature_enabled, get_feature_flag

# Check if feature is enabled
if is_feature_enabled("experimental_features"):
    # Use experimental features
    pass

# Get feature flag with default
if get_feature_flag("new_ui", default=False):
    # Use new UI
    pass
```

## Monitoring

### Metrics Collection

```python
from mcp_sdk.core.monitoring import get_monitoring, monitor_operation

# Get monitoring instance
monitoring = get_monitoring()
await monitoring.start()

# Monitor operations
@monitor_operation("process_data", operation_type="batch")
async def process_data(data):
    # Operation is automatically tracked
    return processed_data

# Manual metrics
monitoring.metrics.increment("requests_total", tags={"endpoint": "/api"})
monitoring.metrics.gauge("active_connections", 42)
monitoring.metrics.timing("operation_duration", 0.123)
```

### Health Checks

```python
from mcp_sdk.core.monitoring import HealthMonitor, HealthCheck

# Create health monitor
health_monitor = HealthMonitor()

# Add health checks
async def check_database():
    # Check database connectivity
    return True

async def check_memory():
    # Check memory usage
    import psutil
    return psutil.virtual_memory().percent < 90

health_monitor.add_check(HealthCheck("database", check_database))
health_monitor.add_check(HealthCheck("memory", check_memory))

# Start monitoring
await health_monitor.start_monitoring()

# Check health
health_status = await health_monitor.check_health()
print(f"System health: {health_status['status']}")
```

### Performance Tracking

```python
# Performance context manager
async with monitoring.performance.track_operation("api_call"):
    # Track operation performance
    result = await some_api_call()

# Get performance metrics
metrics = monitoring.get_system_metrics()
print(f"Total requests: {metrics['counters']['operation_api_call_calls']}")
```

## Performance

### Caching

```python
from mcp_sdk.core.performance import get_performance_optimizer, cached

# Get performance optimizer
optimizer = get_performance_optimizer()
await optimizer.start()

# Cache decorator
@cached("my_cache", ttl=timedelta(hours=1))
async def expensive_operation(param: str) -> str:
    # Result will be cached for 1 hour
    return f"Processed {param}"

# Manual caching
async with optimizer.cached_operation("temp_cache", "key"):
    result = await expensive_computation()
    # Result is automatically cached
```

### Connection Pooling

```python
from mcp_sdk.core.performance import pooled_connection

# Database connection pool
@pooled_connection("database")
async def execute_query(conn, query: str):
    return await conn.fetch(query)

# HTTP connection pool
@pooled_connection("http")
async def make_request(session, url: str):
    async with session.get(url) as response:
        return await response.json()
```

### Rate Limiting

```python
from mcp_sdk.core.performance import rate_limited

# Rate limit decorator
@rate_limited("api_calls", tokens=1)
async def api_endpoint():
    # Limited to 1 token per call
    return "Response"

# Manual rate limiting
async with optimizer.rate_limited("uploads", tokens=5):
    # Consume 5 tokens from rate limiter
    await upload_file()
```

### Load Balancing

```python
from mcp_sdk.core.performance import get_performance_optimizer

# Register load balancer
balancer = optimizer.register_load_balancer(
    "api_servers",
    strategy="least_connections"
)

# Add targets
balancer.add_target("http://server1:8080")
balancer.add_target("http://server2:8080")
balancer.add_target("http://server3:8080")

# Get best target
target = await balancer.get_target()

# Record request statistics
await balancer.record_request(target, success=True, response_time=0.123)
```

## Type Hints

The MCP SDK provides comprehensive type hints throughout the codebase.

```python
from typing import Any, Dict, List, Optional
from mcp_sdk.agents.base import BaseAgent, AgentMessage, AgentContext, AgentResponse
from mcp_sdk.types import Tool, Resource, Prompt

def process_message(
    agent: BaseAgent,
    message: AgentMessage,
    context: AgentContext
) -> AgentResponse:
    """Type-hinted function signature."""
    return AgentResponse(
        success=True,
        data="processed",
        agent_id=agent.id,
        context=context
    )

async def handle_tools(
    tools: List[Tool],
    registry: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Async function with type hints."""
    pass
```

## Exceptions

### Custom Exceptions

```python
from mcp_sdk.core.error_handling import (
    MCPException,
    AuthenticationError,
    AuthorizationError,
    PluginError,
    AgentError,
)

# Raise custom exceptions
try:
    # Some operation
    pass
except ValidationError as e:
    raise AgentError(f"Agent validation failed: {e}")

# Handle specific exceptions
try:
    await risky_operation()
except AuthenticationError:
    # Handle authentication failure
    pass
except AuthorizationError:
    # Handle authorization failure
    pass
except MCPException as e:
    # Handle general MCP errors
    pass
```

## Utilities

### Logging

```python
import structlog

# Get structured logger
logger = structlog.get_logger(__name__)

# Structured logging
logger.info("Processing request", 
           request_id="123", 
           user_id="456",
           operation="process_data")

# Error logging
logger.error("Processing failed",
             request_id="123",
             error=str(exception),
             error_type=type(exception).__name__)
```

### Context Managers

```python
from mcp_sdk.core.config import ConfigContext
from mcp_sdk.security.auth import SecurityContext

# Configuration context
with ConfigContext(debug=True, log_level="DEBUG"):
    # Temporary debug mode
    pass

# Security context
async with SecurityContext(security, token) as user:
    # Authenticated operation
    result = await protected_operation(user)
```

This API reference provides comprehensive documentation for all major components of the MCP SDK. For more detailed examples and tutorials, see the [User Guide](user-guide.md).

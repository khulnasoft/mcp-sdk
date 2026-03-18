# MCP SDK User Guide

This guide helps you get started with the MCP SDK, from basic concepts to advanced usage patterns.

## Table of Contents

- [Introduction](#introduction)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
- [Building Your First Agent](#building-your-first-agent)
- [Working with Plugins](#working-with-plugins)
- [MCP Protocol Integration](#mcp-protocol-integration)
- [Security and Authentication](#security-and-authentication)
- [Monitoring and Debugging](#monitoring-and-debugging)
- [Best Practices](#best-practices)
- [Examples](#examples)

## Introduction

The MCP SDK is a comprehensive framework for building Model Context Protocol (MCP) applications. It provides:

- **Agent Framework**: Build intelligent agents with lifecycle management
- **Plugin System**: Extensible architecture for custom functionality
- **MCP Protocol**: Full implementation of the Model Context Protocol
- **Security**: Built-in authentication and authorization
- **Monitoring**: Comprehensive observability and metrics

### What is MCP?

The Model Context Protocol (MCP) enables AI models to interact with external tools, resources, and prompts in a standardized way. MCP SDK makes it easy to build MCP-compliant servers and clients.

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/mcp-sdk.git
cd mcp-sdk

# Set up development environment
./scripts/setup-dev.sh

# Or install directly
pip install mcp-sdk
```

### Your First MCP Server

```python
from mcp_sdk.core.protocol import MCPProtocol

# Create an MCP protocol instance
protocol = MCPProtocol("my-first-agent", "1.0.0")

# Register a tool
@protocol.tool("echo", "Echo back the input message")
async def echo_tool(message: str) -> str:
    return f"Echo: {message}"

# Register a resource
@protocol.resource("greeting://hello")
async def greeting_resource() -> str:
    return "Hello, World!"

# Register a prompt
@protocol.prompt("greeting", "A simple greeting prompt")
async def greeting_prompt() -> str:
    return "Please provide a friendly greeting."

# Start the server
if __name__ == "__main__":
    import asyncio
    asyncio.run(protocol.serve())
```

### Running the Server

```bash
# Start the server
python my_server.py

# Or using the CLI
mcp-sdk serve --name my-first-agent --port 8080
```

## Core Concepts

### Agents

Agents are the primary building blocks in MCP SDK. They represent autonomous entities that can:

- Process messages and requests
- Execute tools and access resources
- Maintain state and memory
- Interact with other agents

### Protocol

The MCP Protocol layer handles:
- Tool registration and execution
- Resource management
- Prompt handling
- Client-server communication

### Plugins

Plugins extend functionality by:
- Adding new tools and resources
- Integrating external services
- Providing custom capabilities
- Enhancing security and monitoring

### Security

Security features include:
- JWT-based authentication
- Role-based access control (RBAC)
- API rate limiting
- Security headers and auditing

## Building Your First Agent

### Basic Agent

```python
from mcp_sdk.agents.base import BaseAgent, AgentMessage, AgentContext, AgentResponse
from mcp_sdk.core.config import MCPConfig

class MyAgent(BaseAgent):
    """A simple agent that processes messages."""
    
    AGENT_TYPE = "message_processor"
    
    async def handle_message(
        self, 
        message: AgentMessage, 
        context: AgentContext
    ) -> AgentResponse:
        """Handle incoming messages."""
        
        # Process the message
        processed_content = f"Processed: {message.content}"
        
        return AgentResponse(
            success=True,
            data=processed_content,
            agent_id=self.id,
            context=context
        )
    
    def get_capabilities(self) -> list[str]:
        """Return agent capabilities."""
        return ["message_processing", "echo"]

# Create and start the agent
async def main():
    agent = MyAgent("my-agent", description="A simple message processor")
    
    try:
        await agent.start()
        print(f"Agent {agent.name} started with ID: {agent.id}")
        
        # Process a message
        message = AgentMessage(
            sender_id="user",
            recipient_id=agent.id,
            content="Hello, Agent!"
        )
        context = AgentContext()
        
        response = await agent.handle_message(message, context)
        print(f"Response: {response.data}")
        
    finally:
        await agent.stop()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### Advanced Agent with Memory

```python
from mcp_sdk.memory.store import MemoryStore
from mcp_sdk.rules.engine import RuleEngine
from mcp_sdk.tools.registry import ToolRegistry

class AdvancedAgent(BaseAgent):
    """An agent with memory, rules, and tools."""
    
    AGENT_TYPE = "advanced_agent"
    
    def __init__(self, name: str, **kwargs):
        # Initialize with memory, rules, and tools
        super().__init__(
            name,
            memory=MemoryStore(),
            rule_engine=RuleEngine(),
            tools=ToolRegistry(),
            **kwargs
        )
    
    async def handle_message(
        self, 
        message: AgentMessage, 
        context: AgentContext
    ) -> AgentResponse:
        """Handle messages with memory and rules."""
        
        # Store message in memory
        await self.memory.store(
            f"message_{message.id}",
            {
                "content": message.content,
                "sender": message.sender_id,
                "timestamp": message.timestamp.isoformat()
            }
        )
        
        # Apply rules
        rule_result = await self.rule_engine.evaluate(
            agent=self,
            message=message,
            context=context
        )
        
        if not rule_result.allowed:
            return AgentResponse(
                success=False,
                error="Message blocked by rules",
                agent_id=self.id,
                context=context
            )
        
        # Process with tools if available
        if "process" in self.tools.list_tools():
            result = await self.tools.call_tool("process", {
                "content": message.content,
                "rules": rule_result.actions
            })
            processed_content = result
        else:
            processed_content = f"Processed: {message.content}"
        
        return AgentResponse(
            success=True,
            data=processed_content,
            agent_id=self.id,
            context=context,
            metadata={"rule_actions": rule_result.actions}
        )
```

## Working with Plugins

### Creating a Plugin

```python
from mcp_sdk.core.plugin import MCPPlugin
from mcp_sdk.core.registry import PluginRegistry

class WeatherPlugin(MCPPlugin):
    """A plugin for weather information."""
    
    def __init__(self):
        super().__init__()
        self.api_key = None
    
    @property
    def name(self) -> str:
        return "weather"
    
    async def on_activate(self, protocol):
        """Initialize the plugin."""
        self.api_key = protocol.config.get("weather_api_key")
        await super().on_activate(protocol)
    
    def register_tools(self, registry: PluginRegistry):
        """Register weather tools."""
        
        async def get_weather(city: str) -> str:
            """Get current weather for a city."""
            # Mock implementation
            return f"Weather in {city}: 22°C, Sunny"
        
        registry.register_tool(
            "weather.get_current",
            get_weather,
            {
                "description": "Get current weather for a city",
                "parameters": {
                    "city": {
                        "type": "string",
                        "description": "City name"
                    }
                }
            }
        )
        
        async def get_forecast(city: str, days: int = 5) -> str:
            """Get weather forecast."""
            return f"Forecast for {city}: Sunny for next {days} days"
        
        registry.register_tool(
            "weather.get_forecast",
            get_forecast,
            {
                "description": "Get weather forecast",
                "parameters": {
                    "city": {"type": "string"},
                    "days": {"type": "integer", "default": 5}
                }
            }
        )
```

### Using Plugins

```python
from mcp_sdk.core.plugin_manager import PluginManager
from mcp_sdk.core.registry import PluginRegistry

async def main():
    # Create plugin manager
    registry = PluginRegistry()
    plugin_manager = PluginManager(registry)
    
    # Load plugins
    await plugin_manager.load_all()
    
    # Create protocol with plugins
    protocol = MCPProtocol("weather-agent", "1.0.0")
    protocol.plugins = plugin_manager
    
    # Register a custom tool that uses plugin
    @protocol.tool("weather_summary", "Get weather summary")
    async def weather_summary(city: str) -> str:
        # Use plugin tools
        current = await registry.call_tool("weather.get_current", {"city": city})
        forecast = await registry.call_tool("weather.get_forecast", {"city": city})
        
        return f"Current: {current}\nForecast: {forecast}"
    
    # Start the server
    await protocol.serve()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## MCP Protocol Integration

### Client Usage

```python
from mcp_sdk.client.session import MCPClientSession

async def use_mcp_client():
    # Connect to MCP server
    client = MCPClientSession("http://localhost:8080")
    await client.initialize()
    
    # List available tools
    tools = await client.list_tools()
    print(f"Available tools: {[tool.name for tool in tools.tools]}")
    
    # Call a tool
    result = await client.call_tool("echo", {"message": "Hello from client"})
    print(f"Tool result: {result.content[0].text}")
    
    # List resources
    resources = await client.list_resources()
    print(f"Available resources: {[res.uri for res in resources.resources]}")
    
    # Read a resource
    resource_data = await client.read_resource("greeting://hello")
    print(f"Resource data: {resource_data.contents[0].text}")
    
    # List prompts
    prompts = await client.list_prompts()
    print(f"Available prompts: {[prompt.name for prompt in prompts.prompts]}")
    
    # Get a prompt
    prompt_data = await client.get_prompt("greeting")
    print(f"Prompt: {prompt_data.messages[0].content.text}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(use_mcp_client())
```

### Advanced Protocol Features

```python
from mcp_sdk.core.protocol import MCPProtocol
from mcp_sdk.types import ServerCapabilities

# Create protocol with custom capabilities
capabilities = ServerCapabilities(
    tools=True,
    resources=True,
    prompts=True,
    logging=True,
    sampling=True  # Enable sampling
)

protocol = MCPProtocol(
    "advanced-agent",
    "1.0.0",
    capabilities=capabilities
)

# Add middleware
@protocol.middleware
async def logging_middleware(request, next_handler):
    """Log all requests."""
    print(f"Processing request: {request}")
    response = await next_handler(request)
    print(f"Response: {response}")
    return response

# Add startup/shutdown hooks
@protocol.on_startup
async def startup_hook():
    """Run on server startup."""
    print("Server starting up...")

@protocol.on_shutdown
async def shutdown_hook():
    """Run on server shutdown."""
    print("Server shutting down...")
```

## Security and Authentication

### Setting up Authentication

```python
from mcp_sdk.security.auth import SecurityManager
from mcp_sdk.security.middleware import AuthenticationMiddleware

# Create security manager
security = SecurityManager(
    secret_key="your-secret-key",
    token_expiry_hours=24
)

# Create users
await security.create_user(
    username="admin",
    email="admin@example.com",
    password="secure-password",
    roles=["admin"]
)

await security.create_user(
    username="user",
    email="user@example.com",
    password="user-password",
    roles=["user"]
)

# Authenticate
user, token = await security.authenticate("admin", "secure-password")
print(f"Access token: {token}")
```

### Protecting Endpoints

```python
from mcp_sdk.security.middleware import require_auth, require_permission

# Apply authentication middleware
app.add_middleware(AuthenticationMiddleware)

# Protect routes
@app.get("/admin")
@require_auth
@require_permission("admin")
async def admin_endpoint(request):
    return {"message": "Admin access granted"}

@app.get("/user")
@require_auth
async def user_endpoint(request):
    return {"message": "User access granted"}
```

### Using JWT Tokens

```python
import requests

# Login to get token
response = requests.post("http://localhost:8080/auth/login", json={
    "username": "admin",
    "password": "secure-password"
})

token = response.json()["access_token"]

# Use token in requests
headers = {"Authorization": f"Bearer {token}"}
response = requests.get("http://localhost:8080/tools", headers=headers)
print(response.json())
```

## Monitoring and Debugging

### Enabling Monitoring

```python
from mcp_sdk.core.monitoring import get_monitoring, monitor_operation

# Get monitoring instance
monitoring = get_monitoring()
await monitoring.start()

# Monitor operations
@monitor_operation("process_message", agent_type="my_agent")
async def process_message(message):
    # Your processing logic here
    return result

# Get metrics
metrics = monitoring.get_system_metrics()
print(f"Total operations: {metrics['counters']['operation_process_message_calls']}")
```

### Health Checks

```python
from mcp_sdk.core.monitoring import HealthMonitor

# Create health monitor
health_monitor = HealthMonitor()

# Add health checks
async def check_database():
    # Check database connectivity
    return True

async def check_memory():
    # Check memory usage
    import psutil
    memory_percent = psutil.virtual_memory().percent
    return memory_percent < 90

health_monitor.add_check(HealthCheck("database", check_database))
health_monitor.add_check(HealthCheck("memory", check_memory))

# Start monitoring
await health_monitor.start_monitoring()

# Check health
health_status = await health_monitor.check_health()
print(f"System health: {health_status['status']}")
```

### Debugging

```python
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Use structured logging
logger = structlog.get_logger(__name__)

async def process_message(message):
    logger.info("Processing message", message_id=message.id)
    
    try:
        result = await do_processing(message)
        logger.info("Message processed successfully", 
                   message_id=message.id, 
                   result_size=len(result))
        return result
    except Exception as e:
        logger.error("Message processing failed", 
                    message_id=message.id, 
                    error=str(e))
        raise
```

## Best Practices

### Performance

1. **Use Async/Await**: Always use async operations for I/O-bound tasks
2. **Connection Pooling**: Reuse database and HTTP connections
3. **Caching**: Cache frequently accessed data
4. **Batch Operations**: Process multiple items together when possible

```python
# Good: Use async operations
async def fetch_data(urls):
    tasks = [fetch_url(url) for url in urls]
    return await asyncio.gather(*tasks)

# Good: Use connection pooling
import aiohttp
connector = aiohttp.TCPConnector(limit=100, limit_per_host=10)
```

### Security

1. **Validate Input**: Always validate and sanitize user input
2. **Use HTTPS**: Always use TLS in production
3. **Principle of Least Privilege**: Grant minimal necessary permissions
4. **Regular Updates**: Keep dependencies updated

```python
# Good: Input validation
from pydantic import BaseModel

class MessageRequest(BaseModel):
    content: str
    max_length: int = 1000
    
    @validator('content')
    def validate_content(cls, v):
        if len(v) > 1000:
            raise ValueError('Content too long')
        return v
```

### Error Handling

1. **Structured Errors**: Use consistent error formats
2. **Logging**: Log errors with context
3. **Graceful Degradation**: Fail gracefully when possible
4. **Retry Logic**: Implement retry for transient failures

```python
# Good: Structured error handling
from mcp_sdk.core.error_handling import handle_errors

@handle_errors("PROCESS_ERROR")
async def process_data(data):
    try:
        result = await expensive_operation(data)
        return result
    except TemporaryError as e:
        logger.warning("Temporary failure, will retry", error=str(e))
        raise
    except PermanentError as e:
        logger.error("Permanent failure", error=str(e))
        return None
```

### Testing

1. **Unit Tests**: Test individual components
2. **Integration Tests**: Test component interactions
3. **Mock External Dependencies**: Use mocks for external services
4. **Test Coverage**: Aim for high test coverage

```python
# Good: Test with mocks
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_agent_message_processing():
    # Arrange
    agent = MyAgent("test-agent")
    mock_memory = AsyncMock()
    agent.memory = mock_memory
    
    message = AgentMessage(
        sender_id="user",
        recipient_id=agent.id,
        content="test"
    )
    
    # Act
    response = await agent.handle_message(message, AgentContext())
    
    # Assert
    assert response.success is True
    assert "test" in response.data
    mock_memory.store.assert_called_once()
```

## Examples

### Complete Web API Example

```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer
from mcp_sdk.core.protocol import MCPProtocol
from mcp_sdk.security.auth import SecurityManager
from mcp_sdk.security.middleware import AuthenticationMiddleware

# Create FastAPI app
app = FastAPI(title="MCP SDK API")

# Create MCP protocol
protocol = MCPProtocol("api-agent", "1.0.0")

# Add tools
@protocol.tool("calculate", "Perform calculations")
async def calculate(operation: str, a: float, b: float) -> float:
    if operation == "add":
        return a + b
    elif operation == "multiply":
        return a * b
    else:
        raise ValueError(f"Unsupported operation: {operation}")

# Add security
security = SecurityManager()
app.add_middleware(AuthenticationMiddleware, security_manager=security)

# API endpoints
@app.post("/auth/login")
async def login(username: str, password: str):
    user, token = await security.authenticate(username, password)
    return {"access_token": token, "token_type": "bearer"}

@app.post("/tools/{tool_name}")
async def call_tool(tool_name: str, arguments: dict, auth_info=Depends(AuthenticationMiddleware)):
    try:
        result = await protocol._call_tool(tool_name, arguments)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/tools")
async def list_tools(auth_info=Depends(AuthenticationMiddleware)):
    return await protocol._list_tools()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

### Multi-Agent System

```python
from mcp_sdk.agents.base import BaseAgent
from mcp_sdk.agents.orchestrator import OrchestratorAgent

class WorkerAgent(BaseAgent):
    """A worker agent that processes tasks."""
    
    AGENT_TYPE = "worker"
    
    async def handle_message(self, message, context):
        # Process task
        result = await self.process_task(message.content)
        
        return AgentResponse(
            success=True,
            data=result,
            agent_id=self.id,
            context=context
        )
    
    async def process_task(self, task_data):
        # Implement task processing logic
        return f"Processed: {task_data}"

# Create multi-agent system
async def main():
    # Create orchestrator
    orchestrator = OrchestratorAgent("orchestrator")
    
    # Create worker agents
    workers = [WorkerAgent(f"worker-{i}") for i in range(3)]
    
    # Start all agents
    await orchestrator.start()
    for worker in workers:
        await worker.start()
    
    # Register workers with orchestrator
    for worker in workers:
        await orchestrator.register_worker(worker)
    
    # Distribute tasks
    tasks = ["task-1", "task-2", "task-3", "task-4", "task-5"]
    for task in tasks:
        await orchestrator.distribute_task(task)
    
    # Wait for completion
    await asyncio.sleep(5)
    
    # Shutdown
    for worker in workers:
        await worker.stop()
    await orchestrator.stop()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

This user guide provides a comprehensive introduction to using the MCP SDK. Start with the basic examples and gradually explore more advanced features as you become familiar with the framework.

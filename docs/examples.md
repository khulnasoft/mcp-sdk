# Examples

This document provides practical examples for using the MCP SDK in various scenarios.

## Table of Contents

- [Quick Start Examples](#quick-start-examples)
- [Agent Examples](#agent-examples)
- [Plugin Examples](#plugin-examples)
- [Security Examples](#security-examples)
- [Performance Examples](#performance-examples)
- [Integration Examples](#integration-examples)
- [Advanced Examples](#advanced-examples)

## Quick Start Examples

### Basic MCP Server

```python
# basic_server.py
from mcp_sdk.core.protocol import MCPProtocol

# Create protocol instance
protocol = MCPProtocol("basic-server", "1.0.0")

# Register a simple tool
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

if __name__ == "__main__":
    import asyncio
    asyncio.run(protocol.serve())
```

### Running the Server

```bash
# Install dependencies
pip install mcp-sdk

# Run the server
python basic_server.py

# Or use the CLI
mcp-sdk serve --name basic-server --port 8080
```

### Client Example

```python
# client_example.py
import asyncio
from mcp_sdk.client.session import MCPClientSession

async def main():
    # Connect to the server
    client = MCPClientSession("http://localhost:8080")
    await client.initialize()
    
    # List available tools
    tools = await client.list_tools()
    print("Available tools:")
    for tool in tools.tools:
        print(f"  - {tool.name}: {tool.description}")
    
    # Call the echo tool
    result = await client.call_tool("echo", {"message": "Hello from client!"})
    print(f"Tool result: {result.content[0].text}")
    
    # Read the greeting resource
    resource_data = await client.read_resource("greeting://hello")
    print(f"Resource data: {resource_data.contents[0].text}")
    
    # Get the greeting prompt
    prompt_data = await client.get_prompt("greeting")
    print(f"Prompt: {prompt_data.messages[0].content.text}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Agent Examples

### Simple Message Processor

```python
# message_processor.py
from mcp_sdk.agents.base import BaseAgent, AgentMessage, AgentContext, AgentResponse

class MessageProcessor(BaseAgent):
    """A simple agent that processes messages."""
    
    AGENT_TYPE = "message_processor"
    
    async def handle_message(
        self, 
        message: AgentMessage, 
        context: AgentContext
    ) -> AgentResponse:
        """Process incoming messages."""
        
        # Process the message content
        processed_content = message.content.upper()
        
        return AgentResponse(
            success=True,
            data=f"Processed: {processed_content}",
            agent_id=self.id,
            context=context,
            metadata={
                "original_length": len(message.content),
                "processed_length": len(processed_content)
            }
        )
    
    def get_capabilities(self) -> list[str]:
        """Return agent capabilities."""
        return ["message_processing", "text_transformation"]

# Usage example
async def main():
    # Create and start the agent
    agent = MessageProcessor("text-processor", description="Text processing agent")
    
    try:
        await agent.start()
        print(f"Agent started: {agent.name} (ID: {agent.id})")
        
        # Process a message
        message = AgentMessage(
            sender_id="user",
            recipient_id=agent.id,
            content="Hello, Agent!"
        )
        context = AgentContext(user_id="user123")
        
        response = await agent.handle_message(message, context)
        print(f"Response: {response.data}")
        print(f"Metadata: {response.metadata}")
        
    finally:
        await agent.stop()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### Agent with Memory

```python
# memory_agent.py
from mcp_sdk.agents.base import BaseAgent, AgentMessage, AgentContext, AgentResponse
from mcp_sdk.memory.store import MemoryStore

class MemoryAgent(BaseAgent):
    """An agent with persistent memory."""
    
    AGENT_TYPE = "memory_agent"
    
    def __init__(self, name: str, **kwargs):
        super().__init__(name, **kwargs)
        self.memory = MemoryStore()
    
    async def handle_message(
        self, 
        message: AgentMessage, 
        context: AgentContext
    ) -> AgentResponse:
        """Handle messages with memory."""
        
        # Store the message in memory
        await self.memory.store(
            f"message_{message.id}",
            {
                "content": message.content,
                "sender": message.sender_id,
                "timestamp": message.timestamp.isoformat()
            }
        )
        
        # Retrieve conversation history
        history = await self.memory.retrieve("conversation_history")
        if not history:
            history = []
        
        # Add current message to history
        history.append({
            "role": "user",
            "content": message.content,
            "timestamp": message.timestamp.isoformat()
        })
        
        # Update history in memory
        await self.memory.store("conversation_history", history)
        
        # Generate response based on history
        message_count = len(history)
        response_text = f"I remember {message_count} messages. Last one was: '{message.content}'"
        
        return AgentResponse(
            success=True,
            data=response_text,
            agent_id=self.id,
            context=context,
            metadata={"message_count": message_count}
        )
    
    def get_capabilities(self) -> list[str]:
        return ["memory", "conversation_tracking"]

# Usage
async def main():
    agent = MemoryAgent("memory-bot", description="Agent with memory")
    
    try:
        await agent.start()
        await agent.memory.initialize()
        
        # Send multiple messages
        messages = [
            "Hello, I'm John",
            "How are you?",
            "What's my name?"
        ]
        
        for msg in messages:
            message = AgentMessage(
                sender_id="user",
                recipient_id=agent.id,
                content=msg
            )
            context = AgentContext(user_id="john")
            
            response = await agent.handle_message(message, context)
            print(f"User: {msg}")
            print(f"Agent: {response.data}")
            print()
    
    finally:
        await agent.memory.cleanup()
        await agent.stop()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### Multi-Agent System

```python
# multi_agent_system.py
from mcp_sdk.agents.base import BaseAgent, AgentMessage, AgentContext, AgentResponse
import asyncio

class WorkerAgent(BaseAgent):
    """A worker agent that processes tasks."""
    
    AGENT_TYPE = "worker"
    
    def __init__(self, name: str, specialty: str, **kwargs):
        super().__init__(name, **kwargs)
        self.specialty = specialty
    
    async def handle_message(
        self, 
        message: AgentMessage, 
        context: AgentContext
    ) -> AgentResponse:
        """Process tasks based on specialty."""
        
        task_data = message.content
        processed_data = f"[{self.specialty}] Processed: {task_data}"
        
        return AgentResponse(
            success=True,
            data=processed_data,
            agent_id=self.id,
            context=context,
            metadata={"specialty": self.specialty}
        )
    
    def get_capabilities(self) -> list[str]:
        return [self.specialty, "task_processing"]

class OrchestratorAgent(BaseAgent):
    """An orchestrator that distributes tasks to workers."""
    
    AGENT_TYPE = "orchestrator"
    
    def __init__(self, name: str, **kwargs):
        super().__init__(name, **kwargs)
        self.workers = []
    
    def register_worker(self, worker: BaseAgent):
        """Register a worker agent."""
        self.workers.append(worker)
    
    async def handle_message(
        self, 
        message: AgentMessage, 
        context: AgentContext
    ) -> AgentResponse:
        """Distribute tasks to appropriate workers."""
        
        task = message.content
        results = []
        
        # Send task to all workers
        for worker in self.workers:
            worker_message = AgentMessage(
                sender_id=self.id,
                recipient_id=worker.id,
                content=task
            )
            worker_context = AgentContext(
                user_id=context.user_id,
                correlation_id=context.correlation_id
            )
            
            try:
                response = await worker.handle_message(worker_message, worker_context)
                results.append(response.data)
            except Exception as e:
                results.append(f"Error from {worker.name}: {str(e)}")
        
        return AgentResponse(
            success=True,
            data=f"Task completed. Results: {results}",
            agent_id=self.id,
            context=context,
            metadata={"worker_count": len(self.workers)}
        )
    
    def get_capabilities(self) -> list[str]:
        return ["orchestration", "task_distribution"]

# Usage
async def main():
    # Create orchestrator
    orchestrator = OrchestratorAgent("orchestrator", description="Task orchestrator")
    
    # Create workers with different specialties
    workers = [
        WorkerAgent("text-worker", specialty="text", description="Text processing worker"),
        WorkerAgent("data-worker", specialty="data", description="Data analysis worker"),
        WorkerAgent("api-worker", specialty="api", description="API integration worker")
    ]
    
    # Register workers with orchestrator
    for worker in workers:
        orchestrator.register_worker(worker)
    
    # Start all agents
    all_agents = [orchestrator] + workers
    
    for agent in all_agents:
        await agent.start()
    
    try:
        # Send a task to the orchestrator
        task_message = AgentMessage(
            sender_id="client",
            recipient_id=orchestrator.id,
            content="Process customer data"
        )
        context = AgentContext(user_id="client123")
        
        response = await orchestrator.handle_message(task_message, context)
        print(f"Orchestrator response: {response.data}")
        
    finally:
        # Stop all agents
        for agent in reversed(all_agents):
            await agent.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

## Plugin Examples

### Simple Plugin

```python
# plugins/weather/__init__.py
from mcp_sdk.core.plugin import MCPPlugin
from mcp_sdk.core.registry import PluginRegistry
import random

class WeatherPlugin(MCPPlugin):
    """A simple weather plugin."""
    
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
        
        async def get_current_weather(city: str) -> str:
            """Get current weather for a city."""
            # Mock implementation - in real app, call weather API
            conditions = ["Sunny", "Cloudy", "Rainy", "Snowy"]
            temperature = random.randint(-10, 35)
            condition = random.choice(conditions)
            
            return f"Weather in {city}: {temperature}°C, {condition}"
        
        async def get_forecast(city: str, days: int = 5) -> str:
            """Get weather forecast."""
            forecasts = []
            for i in range(days):
                temp = random.randint(-10, 35)
                condition = random.choice(["Sunny", "Cloudy", "Rainy"])
                forecasts.append(f"Day {i+1}: {temp}°C, {condition}")
            
            return f"Weather forecast for {city}:\n" + "\n".join(forecasts)
        
        # Register tools
        registry.register_tool(
            "weather.get_current",
            get_current_weather,
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
        
        registry.register_tool(
            "weather.get_forecast",
            get_forecast,
            {
                "description": "Get weather forecast",
                "parameters": {
                    "city": {"type": "string"},
                    "days": {
                        "type": "integer",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10
                    }
                }
            }
        )

# Plugin manifest
# plugins/weather/manifest.yaml
name: weather
version: 1.0.0
description: Weather information plugin
main: __init__.py
dependencies: []
capabilities: [tools]
config:
  weather_api_key:
    type: string
    description: Weather API key
    required: false
```

### Using the Plugin

```python
# weather_server.py
from mcp_sdk.core.protocol import MCPProtocol
from mcp_sdk.core.plugin_manager import PluginManager
from mcp_sdk.core.registry import PluginRegistry

async def main():
    # Create plugin manager
    registry = PluginRegistry()
    plugin_manager = PluginManager(registry, plugin_dirs=["./plugins"])
    
    # Load plugins
    await plugin_manager.load_all()
    
    # Create protocol with plugins
    protocol = MCPProtocol("weather-server", "1.0.0")
    
    # Register a tool that uses plugin functionality
    @protocol.tool("weather_summary", "Get comprehensive weather summary")
    async def weather_summary(city: str) -> str:
        """Get weather summary using plugin tools."""
        
        # Get current weather
        current_result = await registry.call_tool("weather.get_current", {"city": city})
        current = current_result
        
        # Get forecast
        forecast_result = await registry.call_tool("weather.get_forecast", {
            "city": city,
            "days": 3
        })
        forecast = forecast_result
        
        return f"Current Weather:\n{current}\n\nForecast:\n{forecast}"
    
    # Start the server
    await protocol.serve()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### Database Plugin

```python
# plugins/database/__init__.py
from mcp_sdk.core.plugin import MCPPlugin
from mcp_sdk.core.registry import PluginRegistry
import sqlite3
import json
from typing import Any, Dict, List

class DatabasePlugin(MCPPlugin):
    """Database operations plugin."""
    
    @property
    def name(self) -> str:
        return "database"
    
    async def on_activate(self, protocol):
        """Initialize database connection."""
        self.db_path = protocol.config.get("database_path", "data.db")
        await super().on_activate(protocol)
    
    def register_tools(self, registry: PluginRegistry):
        """Register database tools."""
        
        async def execute_query(query: str, params: List[Any] = None) -> str:
            """Execute a database query."""
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                if query.strip().upper().startswith("SELECT"):
                    results = cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    
                    # Format results as JSON
                    rows = []
                    for row in results:
                        row_dict = dict(zip(columns, row))
                        rows.append(row_dict)
                    
                    result = json.dumps(rows, indent=2)
                else:
                    conn.commit()
                    result = f"Query executed successfully. {cursor.rowcount} rows affected."
                
                conn.close()
                return result
                
            except Exception as e:
                return f"Database error: {str(e)}"
        
        async def create_table(table_name: str, schema: Dict[str, str]) -> str:
            """Create a new table."""
            columns = []
            for col_name, col_type in schema.items():
                columns.append(f"{col_name} {col_type}")
            
            query = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(columns)})"
            return await execute_query(query)
        
        async def insert_data(table_name: str, data: Dict[str, Any]) -> str:
            """Insert data into a table."""
            columns = list(data.keys())
            placeholders = ["?" for _ in columns]
            values = list(data.values())
            
            query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
            return await execute_query(query, values)
        
        # Register tools
        registry.register_tool(
            "database.execute_query",
            execute_query,
            {
                "description": "Execute a database query",
                "parameters": {
                    "query": {"type": "string"},
                    "params": {
                        "type": "array",
                        "items": {"type": "any"},
                        "default": []
                    }
                }
            }
        )
        
        registry.register_tool(
            "database.create_table",
            create_table,
            {
                "description": "Create a new table",
                "parameters": {
                    "table_name": {"type": "string"},
                    "schema": {
                        "type": "object",
                        "additionalProperties": {"type": "string"}
                    }
                }
            }
        )
        
        registry.register_tool(
            "database.insert_data",
            insert_data,
            {
                "description": "Insert data into a table",
                "parameters": {
                    "table_name": {"type": "string"},
                    "data": {"type": "object"}
                }
            }
        )
```

## Security Examples

### Authentication Setup

```python
# auth_setup.py
from mcp_sdk.security.auth import SecurityManager

async def setup_authentication():
    """Set up users and roles."""
    
    # Create security manager
    security = SecurityManager(
        secret_key="your-super-secret-key-here",
        token_expiry_hours=24
    )
    
    # Create roles and permissions
    await security.authz_manager.create_permission(
        "read_users", "Read user data", "users", "read"
    )
    await security.authz_manager.create_permission(
        "write_users", "Write user data", "users", "write"
    )
    await security.authz_manager.create_permission(
        "admin_access", "Administrative access", "*", "*"
    )
    
    # Create roles
    await security.authz_manager.create_role(
        "admin", "System administrator", ["admin_access"]
    )
    await security.authz_manager.create_role(
        "user", "Regular user", ["read_users"]
    )
    await security.authz_manager.create_role(
        "moderator", "Content moderator", ["read_users", "write_users"]
    )
    
    # Create users
    admin_user = await security.create_user(
        username="admin",
        email="admin@example.com",
        password="admin_secure_password",
        roles=["admin"]
    )
    
    regular_user = await security.create_user(
        username="john_doe",
        email="john@example.com",
        password="user_secure_password",
        roles=["user"]
    )
    
    moderator_user = await security.create_user(
        username="moderator",
        email="mod@example.com",
        password="mod_secure_password",
        roles=["moderator"]
    )
    
    print("Authentication setup complete!")
    print(f"Created users: admin, john_doe, moderator")
    
    return security

# Usage
if __name__ == "__main__":
    import asyncio
    asyncio.run(setup_authentication())
```

### Protected API Server

```python
# protected_server.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer
from mcp_sdk.core.protocol import MCPProtocol
from mcp_sdk.security.auth import SecurityManager, get_security_manager
from mcp_sdk.security.middleware import (
    AuthenticationMiddleware,
    AuthorizationMiddleware,
    require_auth,
    require_permission
)

# Create FastAPI app
app = FastAPI(title="Protected MCP API")

# Create security manager
security = get_security_manager()

# Add authentication middleware
app.add_middleware(AuthenticationMiddleware, security_manager=security)

# Create MCP protocol
protocol = MCPProtocol("protected-server", "1.0.0")

# Register protected tools
@protocol.tool("admin_only", "Admin-only tool")
async def admin_tool(data: str) -> str:
    return f"Admin processed: {data}"

@protocol.tool("user_tool", "Regular user tool")
async def user_tool(message: str) -> str:
    return f"User message: {message}"

# API endpoints
@app.post("/auth/login")
async def login(username: str, password: str):
    """Authenticate user and return token."""
    try:
        user, token = await security.authenticate(username, password)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "roles": user.roles
            }
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.get("/me")
@require_auth
async def get_current_user(auth_info):
    """Get current user information."""
    return auth_info

@app.post("/tools/admin")
@require_auth
@require_permission("admin_access")
async def call_admin_tool(arguments: dict, auth_info):
    """Call admin-only tool."""
    try:
        result = await protocol._call_tool("admin_only", arguments)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/tools/user")
@require_auth
async def call_user_tool(arguments: dict, auth_info):
    """Call user tool."""
    try:
        result = await protocol._call_tool("user_tool", arguments)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/tools")
@require_auth
async def list_tools(auth_info):
    """List available tools."""
    return await protocol._list_tools()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

### Client with Authentication

```python
# authenticated_client.py
import asyncio
import requests
from mcp_sdk.client.session import MCPClientSession

class AuthenticatedMCPClient:
    """MCP client with authentication support."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.token = None
    
    async def login(self, username: str, password: str) -> str:
        """Login and get access token."""
        response = requests.post(f"{self.base_url}/auth/login", json={
            "username": username,
            "password": password
        })
        
        if response.status_code == 200:
            data = response.json()
            self.token = data["access_token"]
            return self.token
        else:
            raise Exception(f"Login failed: {response.text}")
    
    def get_headers(self) -> dict:
        """Get authorization headers."""
        if not self.token:
            raise Exception("Not authenticated")
        
        return {"Authorization": f"Bearer {self.token}"}
    
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a tool with authentication."""
        headers = self.get_headers()
        response = requests.post(
            f"{self.base_url}/tools/{tool_name}",
            json=arguments,
            headers=headers
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Tool call failed: {response.text}")
    
    async def list_tools(self) -> dict:
        """List available tools."""
        headers = self.get_headers()
        response = requests.get(
            f"{self.base_url}/tools",
            headers=headers
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to list tools: {response.text}")

# Usage
async def main():
    client = AuthenticatedMCPClient("http://localhost:8080")
    
    try:
        # Login as regular user
        await client.login("john_doe", "user_secure_password")
        print("Logged in as regular user")
        
        # List available tools
        tools = await client.list_tools()
        print(f"Available tools: {[tool['name'] for tool in tools['tools']]}")
        
        # Call user tool (should succeed)
        result = await client.call_tool("user_tool", {"message": "Hello"})
        print(f"User tool result: {result}")
        
        # Try to call admin tool (should fail)
        try:
            result = await client.call_tool("admin_only", {"data": "test"})
            print("Admin tool succeeded (unexpected)")
        except Exception as e:
            print(f"Admin tool failed (expected): {e}")
        
        # Login as admin
        await client.login("admin", "admin_secure_password")
        print("Logged in as admin")
        
        # Call admin tool (should succeed)
        result = await client.call_tool("admin_only", {"data": "test"})
        print(f"Admin tool result: {result}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Performance Examples

### Caching Example

```python
# caching_example.py
from mcp_sdk.core.performance import get_performance_optimizer, cached
from datetime import timedelta
import time
import asyncio

# Get performance optimizer
optimizer = get_performance_optimizer()
await optimizer.start()

# Example with cached decorator
@cached("expensive_operations", ttl=timedelta(minutes=5))
async def expensive_computation(x: int, y: int) -> int:
    """Simulate an expensive computation."""
    print(f"Performing expensive computation for {x} + {y}")
    await asyncio.sleep(2)  # Simulate slow operation
    return x + y

# Manual caching example
async def manual_caching_example():
    """Example of manual cache usage."""
    
    # First call - will compute
    start_time = time.time()
    result1 = await expensive_computation(5, 3)
    duration1 = time.time() - start_time
    print(f"First call: {result1} (took {duration1:.2f}s)")
    
    # Second call - will use cache
    start_time = time.time()
    result2 = await expensive_computation(5, 3)
    duration2 = time.time() - start_time
    print(f"Second call: {result2} (took {duration2:.2f}s)")
    
    # Different parameters - will compute again
    start_time = time.time()
    result3 = await expensive_computation(10, 20)
    duration3 = time.time() - start_time
    print(f"Different params: {result3} (took {duration3:.2f}s)")

# Cache statistics
async def cache_stats():
    """Show cache statistics."""
    cache_stats = optimizer.cache.get_stats()
    print(f"Cache statistics: {cache_stats}")

# Usage
async def main():
    await manual_caching_example()
    await cache_stats()

if __name__ == "__main__":
    asyncio.run(main())
```

### Rate Limiting Example

```python
# rate_limiting_example.py
from mcp_sdk.core.performance import get_performance_optimizer, rate_limited
import asyncio
import time

# Get performance optimizer
optimizer = get_performance_optimizer()

# Register rate limiter (10 requests per minute, burst of 3)
rate_limiter = optimizer.register_rate_limiter("api_calls", rate=10/60, burst=3)

# Example with rate limiting decorator
@rate_limited("api_calls", tokens=1)
async def api_call(endpoint: str) -> str:
    """Simulate an API call."""
    print(f"Making API call to {endpoint}")
    await asyncio.sleep(0.1)  # Simulate network latency
    return f"Response from {endpoint}"

# Manual rate limiting
async def manual_rate_limiting():
    """Example of manual rate limiting."""
    
    print("Testing rate limiting (10 requests per minute, burst of 3)...")
    
    # First 3 calls should succeed immediately (burst)
    for i in range(3):
        start_time = time.time()
        try:
            result = await api_call(f"endpoint-{i}")
            duration = time.time() - start_time
            print(f"Call {i+1}: SUCCESS (took {duration:.3f}s)")
        except Exception as e:
            print(f"Call {i+1}: FAILED - {e}")
    
    # Next calls should be rate limited
    for i in range(3, 8):
        start_time = time.time()
        try:
            result = await api_call(f"endpoint-{i}")
            duration = time.time() - start_time
            print(f"Call {i+1}: SUCCESS (took {duration:.3f}s)")
        except Exception as e:
            print(f"Call {i+1}: FAILED - {e}")
        
        # Small delay between attempts
        await asyncio.sleep(1)

# Usage
async def main():
    await optimizer.start()
    await manual_rate_limiting()

if __name__ == "__main__":
    asyncio.run(main())
```

## Integration Examples

### FastAPI Integration

```python
# fastapi_integration.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mcp_sdk.core.protocol import MCPProtocol
from mcp_sdk.core.monitoring import get_monitoring
import uvicorn

# Create FastAPI app
app = FastAPI(title="MCP SDK FastAPI Integration")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create MCP protocol
protocol = MCPProtocol("fastapi-server", "1.0.0")

# Register tools
@protocol.tool("calculate", "Perform mathematical calculations")
async def calculate(operation: str, a: float, b: float) -> float:
    """Perform calculations."""
    if operation == "add":
        return a + b
    elif operation == "subtract":
        return a - b
    elif operation == "multiply":
        return a * b
    elif operation == "divide":
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
    else:
        raise ValueError(f"Unsupported operation: {operation}")

@protocol.tool("process_text", "Process text data")
async def process_text(text: str, operation: str = "uppercase") -> str:
    """Process text."""
    if operation == "uppercase":
        return text.upper()
    elif operation == "lowercase":
        return text.lower()
    elif operation == "reverse":
        return text[::-1]
    else:
        raise ValueError(f"Unsupported operation: {operation}")

# API endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "MCP SDK FastAPI Integration", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": time.time()}

@app.get("/tools")
async def list_tools():
    """List available tools."""
    try:
        result = await protocol._list_tools()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tools/{tool_name}")
async def call_tool(tool_name: str, arguments: dict):
    """Call a specific tool."""
    try:
        result = await protocol._call_tool(tool_name, arguments)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/resources")
async def list_resources():
    """List available resources."""
    try:
        result = await protocol._list_resources()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/resources/{resource_uri:path}")
async def read_resource(resource_uri: str):
    """Read a resource."""
    try:
        result = await protocol._read_resource(resource_uri)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/prompts")
async def list_prompts():
    """List available prompts."""
    try:
        result = await protocol._list_prompts()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/prompts/{prompt_name}")
async def get_prompt(prompt_name: str, arguments: dict = None):
    """Get a prompt."""
    try:
        if arguments:
            result = await protocol._get_prompt(prompt_name, arguments)
        else:
            result = await protocol._get_prompt(prompt_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Metrics endpoint
@app.get("/metrics")
async def get_metrics():
    """Get application metrics."""
    monitoring = get_monitoring()
    return monitoring.get_system_metrics()

if __name__ == "__main__":
    import time
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

### WebSocket Integration

```python
# websocket_integration.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from mcp_sdk.core.protocol import MCPProtocol
from mcp_sdk.security.middleware import WebSocketSecurityMiddleware
import json
import asyncio

# Create FastAPI app
app = FastAPI(title="MCP SDK WebSocket Integration")

# Create MCP protocol
protocol = MCPProtocol("websocket-server", "1.0.0")

# Register tools
@protocol.tool("echo", "Echo back the message")
async def echo_tool(message: str) -> str:
    return f"Echo: {message}"

@protocol.tool("status", "Get server status")
async def status_tool() -> dict:
    return {
        "status": "running",
        "uptime": "1h 23m",
        "active_connections": 5
    }

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
    
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    # Create security middleware for WebSocket
    security = WebSocketSecurityMiddleware()
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message["type"] == "auth":
                # Handle authentication
                token = message.get("token")
                if token:
                    try:
                        auth_info = await security.authenticate_websocket(websocket, token)
                        await manager.send_personal_message(
                            json.dumps({"type": "auth_success", "user": auth_info}),
                            websocket
                        )
                    except Exception as e:
                        await manager.send_personal_message(
                            json.dumps({"type": "auth_error", "error": str(e)}),
                            websocket
                        )
                else:
                    await manager.send_personal_message(
                        json.dumps({"type": "auth_error", "error": "No token provided"}),
                        websocket
                    )
            
            elif message["type"] == "call_tool":
                # Handle tool calls
                tool_name = message["tool"]
                arguments = message.get("arguments", {})
                
                try:
                    result = await protocol._call_tool(tool_name, arguments)
                    response = {
                        "type": "tool_result",
                        "tool": tool_name,
                        "result": result.dict()
                    }
                except Exception as e:
                    response = {
                        "type": "tool_error",
                        "tool": tool_name,
                        "error": str(e)
                    }
                
                await manager.send_personal_message(json.dumps(response), websocket)
            
            elif message["type"] == "list_tools":
                # List tools
                try:
                    result = await protocol._list_tools()
                    response = {
                        "type": "tools_list",
                        "tools": [tool.dict() for tool in result.tools]
                    }
                except Exception as e:
                    response = {
                        "type": "error",
                        "error": str(e)
                    }
                
                await manager.send_personal_message(json.dumps(response), websocket)
            
            else:
                # Unknown message type
                await manager.send_personal_message(
                    json.dumps({"type": "error", "error": "Unknown message type"}),
                    websocket
                )
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# HTML client for testing
@app.get("/")
async def get_client():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>MCP WebSocket Client</title>
    </head>
    <body>
        <h1>MCP WebSocket Client</h1>
        <div>
            <input type="text" id="tokenInput" placeholder="Enter auth token">
            <button onclick="authenticate()">Authenticate</button>
        </div>
        <div>
            <input type="text" id="toolInput" placeholder="Tool name">
            <input type="text" id="argsInput" placeholder="Arguments (JSON)">
            <button onclick="callTool()">Call Tool</button>
        </div>
        <div>
            <button onclick="listTools()">List Tools</button>
        </div>
        <div>
            <h3>Messages:</h3>
            <pre id="messages"></pre>
        </div>
        
        <script>
            const ws = new WebSocket('ws://localhost:8000/ws');
            const messages = document.getElementById('messages');
            
            ws.onmessage = function(event) {
                const message = JSON.parse(event.data);
                messages.textContent += JSON.stringify(message, null, 2) + '\\n';
            };
            
            function authenticate() {
                const token = document.getElementById('tokenInput').value;
                ws.send(JSON.stringify({type: 'auth', token: token}));
            }
            
            function callTool() {
                const tool = document.getElementById('toolInput').value;
                const argsText = document.getElementById('argsInput').value;
                const args = argsText ? JSON.parse(argsText) : {};
                ws.send(JSON.stringify({type: 'call_tool', tool: tool, arguments: args}));
            }
            
            function listTools() {
                ws.send(JSON.stringify({type: 'list_tools'}));
            }
        </script>
    </body>
    </html>
    """)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Advanced Examples

### Custom Transport Layer

```python
# custom_transport.py
from mcp_sdk.core.protocol import MCPProtocol
from mcp_sdk.transport.base import BaseTransport
import asyncio
import json

class CustomTransport(BaseTransport):
    """Custom transport implementation."""
    
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.server = None
        self.clients = set()
    
    async def start(self, protocol):
        """Start the custom transport."""
        self.protocol = protocol
        
        def handle_client(reader, writer):
            """Handle individual client connections."""
            self.clients.add(writer)
            
            try:
                while True:
                    data = await reader.read(1024)
                    if not data:
                        break
                    
                    message = json.loads(data.decode())
                    
                    # Process message through protocol
                    if message["method"] == "tools/call":
                        result = await protocol._call_tool(
                            message["params"]["name"],
                            message["params"]["arguments"]
                        )
                        response = {"result": result.dict()}
                    else:
                        response = {"error": "Unsupported method"}
                    
                    # Send response
                    response_data = json.dumps(response).encode()
                    writer.write(response_data)
                    await writer.drain()
            
            except Exception as e:
                print(f"Client error: {e}")
            finally:
                self.clients.remove(writer)
                writer.close()
        
        # Start server
        self.server = await asyncio.start_server(
            handle_client,
            self.host,
            self.port
        )
        
        print(f"Custom transport listening on {self.host}:{self.port}")
    
    async def stop(self):
        """Stop the custom transport."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        # Close all client connections
        for client in self.clients:
            client.close()
        
        self.clients.clear()

# Usage
async def main():
    # Create protocol
    protocol = MCPProtocol("custom-transport-server", "1.0.0")
    
    # Register tools
    @protocol.tool("custom_tool", "A tool for custom transport")
    async def custom_tool(message: str) -> str:
        return f"Custom transport received: {message}"
    
    # Create and start custom transport
    transport = CustomTransport("localhost", 9999)
    await transport.start(protocol)
    
    try:
        # Keep server running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        await transport.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

### Multi-Protocol Server

```python
# multi_protocol_server.py
from mcp_sdk.core.protocol import MCPProtocol
from mcp_sdk.transport.http import HTTPTransport
from mcp_sdk.transport.websocket import WebSocketTransport
from mcp_sdk.transport.stdio import StdioTransport
import asyncio

class MultiProtocolServer:
    """Server supporting multiple transport protocols."""
    
    def __init__(self, name: str, version: str):
        self.protocol = MCPProtocol(name, version)
        self.transports = []
        
        # Register tools
        self._register_tools()
    
    def _register_tools(self):
        """Register server tools."""
        
        @self.protocol.tool("server_info", "Get server information")
        async def server_info() -> dict:
            return {
                "name": self.protocol.server_name,
                "version": self.protocol.server_version,
                "transports": [type(t).__name__ for t in self.transports],
                "uptime": "1h 23m"
            }
        
        @self.protocol.tool("transport_test", "Test transport functionality")
        async def transport_test(message: str) -> str:
            return f"Transport test successful: {message}"
    
    def add_http_transport(self, host: str = "0.0.0.0", port: int = 8080):
        """Add HTTP transport."""
        transport = HTTPTransport(host, port)
        self.transports.append(transport)
        return transport
    
    def add_websocket_transport(self, host: str = "0.0.0.0", port: int = 8081):
        """Add WebSocket transport."""
        transport = WebSocketTransport(host, port)
        self.transports.append(transport)
        return transport
    
    def add_stdio_transport(self):
        """Add stdio transport."""
        transport = StdioTransport()
        self.transports.append(transport)
        return transport
    
    async def start(self):
        """Start all transports."""
        print(f"Starting multi-protocol server: {self.protocol.server_name}")
        
        # Start all transports
        for transport in self.transports:
            await transport.start(self.protocol)
            print(f"Started {type(transport).__name__} transport")
        
        print("All transports started. Server is running...")
    
    async def stop(self):
        """Stop all transports."""
        print("Stopping all transports...")
        
        for transport in self.transports:
            await transport.stop()
        
        print("Server stopped.")

# Usage
async def main():
    # Create multi-protocol server
    server = MultiProtocolServer("multi-protocol-server", "1.0.0")
    
    # Add multiple transports
    server.add_http_transport(port=8080)
    server.add_websocket_transport(port=8081)
    # server.add_stdio_transport()  # Uncomment for stdio support
    
    try:
        # Start server
        await server.start()
        
        # Keep running
        while True:
            await asyncio.sleep(1)
    
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await server.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

These examples demonstrate various ways to use the MCP SDK in real-world scenarios. From simple servers to complex multi-agent systems with authentication and performance optimization, these examples provide practical starting points for your own implementations.

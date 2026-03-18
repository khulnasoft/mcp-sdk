# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with the MCP SDK.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Configuration Problems](#configuration-problems)
- [Agent Issues](#agent-issues)
- [MCP Protocol Issues](#mcp-protocol-issues)
- [Plugin Problems](#plugin-problems)
- [Security Issues](#security-issues)
- [Performance Issues](#performance-issues)
- [Database Issues](#database-issues)
- [Network Issues](#network-issues)
- [Memory Issues](#memory-issues)
- [Logging and Debugging](#logging-and-debugging)

## Installation Issues

### Package Not Found

**Problem**: `pip install mcp-sdk` fails with package not found error.

**Solutions**:
```bash
# Install from the local directory
pip install -e .

# Or install directly from git
pip install git+https://github.com/your-org/mcp-sdk.git

# Using uv (recommended)
uv pip install -e .
```

### Dependency Conflicts

**Problem**: Installation fails due to conflicting dependencies.

**Solutions**:
```bash
# Create fresh virtual environment
python -m venv mcp-sdk-env
source mcp-sdk-env/bin/activate  # On Windows: mcp-sdk-env\Scripts\activate

# Clean install
pip install --upgrade pip
pip install mcp-sdk

# Using uv
uv venv
source .venv/bin/activate
uv pip install mcp-sdk
```

### Missing System Dependencies

**Problem**: Installation fails with system-level dependency errors.

**Solutions**:
```bash
# On Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3-dev build-essential

# On CentOS/RHEL
sudo yum install python3-devel gcc

# On macOS
xcode-select --install
brew install python3
```

## Configuration Problems

### Invalid Configuration

**Problem**: Application fails to start with configuration validation errors.

**Diagnosis**:
```python
from mcp_sdk.core.config import get_config

try:
    config = get_config()
    config.validate()
except ValueError as e:
    print(f"Configuration error: {e}")
```

**Common Issues**:
```bash
# Check environment variables
env | grep MCP_

# Validate configuration file
python -c "
from mcp_sdk.core.config import MCPConfig
config = MCPConfig.from_file('config.yaml')
config.validate()
print('Configuration is valid')
"
```

### Missing Environment Variables

**Problem**: Required environment variables are not set.

**Solution**:
```bash
# Create .env file
cat > .env << EOF
MCP_AUTH_SECRET_KEY=your-secret-key-here
MCP_DB_URL=postgresql://user:pass@localhost/db
MCP_REDIS_URL=redis://localhost:6379/0
EOF

# Load environment variables
export $(cat .env | xargs)
```

### Database Connection Issues

**Problem**: Cannot connect to database.

**Diagnosis**:
```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

async def test_db_connection():
    try:
        engine = create_async_engine("postgresql://user:pass@localhost/db")
        async with engine.connect() as conn:
            result = await conn.execute("SELECT 1")
            print("Database connection successful")
    except Exception as e:
        print(f"Database connection failed: {e}")

asyncio.run(test_db_connection())
```

**Solutions**:
```bash
# Check if database is running
pg_isready -h localhost -p 5432

# Test connection with psql
psql -h localhost -U user -d db

# Check database URL format
echo $MCP_DB_URL
```

## Agent Issues

### Agent Won't Start

**Problem**: Agent fails to start with initialization errors.

**Diagnosis**:
```python
from mcp_sdk.agents.base import BaseAgent

class TestAgent(BaseAgent):
    AGENT_TYPE = "test"
    
    async def handle_message(self, message, context):
        return AgentResponse(success=True, data="test")

# Test agent creation
try:
    agent = TestAgent("test-agent")
    print("Agent created successfully")
except Exception as e:
    print(f"Agent creation failed: {e}")
```

**Common Solutions**:
```python
# Check agent dependencies
from mcp_sdk.memory.store import MemoryStore
from mcp_sdk.rules.engine import RuleEngine
from mcp_sdk.tools.registry import ToolRegistry

# Initialize components separately
memory = MemoryStore()
await memory.initialize()

rules = RuleEngine()
tools = ToolRegistry()
await tools.initialize()

# Create agent with initialized components
agent = TestAgent(
    "test-agent",
    memory=memory,
    rule_engine=rules,
    tools=tools
)
```

### Agent State Issues

**Problem**: Agent gets stuck in unexpected state.

**Diagnosis**:
```python
# Check agent state
print(f"Agent state: {agent.state}")
print(f"Is running: {agent.is_running}")

# Check state transitions
if agent.state == AgentState.ERROR:
    print("Agent is in error state")
    # Check logs for error details
```

**Solutions**:
```python
# Reset agent state
await agent.restart()

# Force stop and restart
await agent.stop()
await agent.start()
```

### Message Processing Failures

**Problem**: Agent fails to process messages.

**Diagnosis**:
```python
# Test message processing
message = AgentMessage(
    sender_id="test",
    recipient_id=agent.id,
    content="test message"
)
context = AgentContext()

try:
    response = await agent.handle_message(message, context)
    print(f"Response: {response}")
except Exception as e:
    print(f"Message processing failed: {e}")
    import traceback
    traceback.print_exc()
```

## MCP Protocol Issues

### Server Won't Start

**Problem**: MCP server fails to start.

**Diagnosis**:
```python
from mcp_sdk.core.protocol import MCPProtocol

try:
    protocol = MCPProtocol("test-server", "1.0.0")
    print("Protocol created successfully")
except Exception as e:
    print(f"Protocol creation failed: {e}")
```

**Common Issues**:
```python
# Check port availability
import socket

def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        result = s.connect_ex(('localhost', port))
        return result == 0

print(f"Port 8080 available: {not check_port(8080)}")
```

### Tool Registration Failures

**Problem**: Tools fail to register or execute.

**Diagnosis**:
```python
# Check registered tools
@protocol.tool("test_tool", "Test tool")
async def test_tool(param: str) -> str:
    return f"Processed: {param}"

# List tools
try:
    tools = await protocol._list_tools()
    print(f"Registered tools: {[t.name for t in tools.tools]}")
except Exception as e:
    print(f"Failed to list tools: {e}")

# Test tool execution
try:
    result = await protocol._call_tool("test_tool", {"param": "test"})
    print(f"Tool result: {result}")
except Exception as e:
    print(f"Tool execution failed: {e}")
```

### Client Connection Issues

**Problem**: MCP client cannot connect to server.

**Diagnosis**:
```python
from mcp_sdk.client.session import MCPClientSession

async def test_connection():
    try:
        client = MCPClientSession("http://localhost:8080")
        await client.initialize()
        print("Client connected successfully")
        
        # Test basic operation
        tools = await client.list_tools()
        print(f"Available tools: {len(tools.tools)}")
        
    except Exception as e:
        print(f"Client connection failed: {e}")

asyncio.run(test_connection())
```

**Solutions**:
```bash
# Check if server is running
curl http://localhost:8080/health

# Check network connectivity
telnet localhost 8080

# Check firewall settings
sudo ufw status
```

## Plugin Problems

### Plugin Won't Load

**Problem**: Plugin fails to load during discovery.

**Diagnosis**:
```python
from mcp_sdk.core.plugin_manager import PluginManager
from mcp_sdk.core.registry import PluginRegistry

async def test_plugin_loading():
    registry = PluginRegistry()
    plugin_manager = PluginManager(registry, plugin_dirs=["./plugins"])
    
    try:
        # Discover plugins
        discovered = await plugin_manager.discover()
        print(f"Discovered plugins: {[p.name for p in discovered]}")
        
        # Load plugins
        loaded = await plugin_manager.load_all()
        print(f"Loaded plugins: {list(loaded.keys())}")
        
    except Exception as e:
        print(f"Plugin loading failed: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test_plugin_loading())
```

**Common Issues**:
```bash
# Check plugin directory structure
ls -la plugins/

# Check plugin manifest
cat plugins/your_plugin/manifest.yaml

# Check plugin syntax
python -m py_compile plugins/your_plugin/__init__.py
```

### Plugin Tool Registration Failures

**Problem**: Plugin tools fail to register.

**Diagnosis**:
```python
# Check plugin tool registration
async def check_plugin_tools():
    registry = PluginRegistry()
    plugin_manager = PluginManager(registry)
    
    await plugin_manager.load_all()
    
    # List all registered tools
    tools = registry.list_tools()
    print(f"Registered tools: {tools}")
    
    # Try to call plugin tool
    try:
        result = await registry.call_tool("plugin.tool_name", {})
        print(f"Tool result: {result}")
    except Exception as e:
        print(f"Tool call failed: {e}")

asyncio.run(check_plugin_tools())
```

### Plugin Dependency Issues

**Problem**: Plugin dependencies are not resolved.

**Solutions**:
```yaml
# plugins/your_plugin/manifest.yaml
name: your_plugin
version: 1.0.0
dependencies:
  - base_plugin: ">=1.0.0"
  - auth_plugin: ">=2.0.0"
```

```python
# Check dependency resolution
async def check_dependencies():
    plugin_manager = PluginManager(registry)
    
    # Load with dependency resolution
    try:
        loaded = await plugin_manager.load_all()
        print("Dependencies resolved successfully")
    except Exception as e:
        print(f"Dependency resolution failed: {e}")

asyncio.run(check_dependencies())
```

## Security Issues

### Authentication Failures

**Problem**: Users cannot authenticate.

**Diagnosis**:
```python
from mcp_sdk.security.auth import SecurityManager

async def test_authentication():
    security = SecurityManager()
    
    try:
        # Create test user
        user = await security.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            roles=["user"]
        )
        
        # Test authentication
        auth_user, token = await security.authenticate("testuser", "testpass123")
        print(f"Authentication successful: {auth_user.username}")
        
        # Test token validation
        token_info = await security.auth_manager.validate_token(token)
        print(f"Token valid for user: {token_info.username}")
        
    except Exception as e:
        print(f"Authentication failed: {e}")

asyncio.run(test_authentication())
```

### Authorization Issues

**Problem**: Users cannot access protected resources.

**Diagnosis**:
```python
async def test_authorization():
    security = SecurityManager()
    
    # Create user with limited permissions
    user = await security.create_user(
        username="limited_user",
        email="limited@example.com",
        password="testpass123",
        roles=["user"]  # No admin role
    )
    
    # Check permissions
    has_admin = await security.authz_manager.check_permission(
        user, "admin_access"
    )
    print(f"User has admin access: {has_admin}")
    
    has_read = await security.authz_manager.check_permission(
        user, "read", "users"
    )
    print(f"User has read access: {has_read}")

asyncio.run(test_authorization())
```

### JWT Token Issues

**Problem**: JWT tokens are invalid or expired.

**Diagnosis**:
```python
import jwt
from datetime import datetime, timedelta

# Decode JWT token manually
def decode_token(token: str, secret_key: str):
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
        print(f"Token payload: {payload}")
        
        # Check expiration
        exp = datetime.fromtimestamp(payload["exp"])
        if exp < datetime.now():
            print("Token has expired")
        else:
            print("Token is valid")
            
    except jwt.ExpiredSignatureError:
        print("Token has expired")
    except jwt.InvalidTokenError as e:
        print(f"Invalid token: {e}")

# Usage
decode_token("your_jwt_token", "your_secret_key")
```

## Performance Issues

### Slow Response Times

**Problem**: API responses are slow.

**Diagnosis**:
```python
import time
from mcp_sdk.core.monitoring import get_monitoring

async def measure_performance():
    monitoring = get_monitoring()
    await monitoring.start()
    
    # Measure operation time
    start_time = time.time()
    result = await some_slow_operation()
    duration = time.time() - start_time
    
    print(f"Operation took {duration:.3f} seconds")
    
    # Check metrics
    metrics = monitoring.get_system_metrics()
    print(f"Total operations: {metrics.get('counters', {})}")

asyncio.run(measure_performance())
```

**Optimization Strategies**:
```python
# Enable caching
from mcp_sdk.core.performance import cached, get_performance_optimizer

optimizer = get_performance_optimizer()
await optimizer.start()

@cached("slow_operations", ttl=timedelta(minutes=5))
async def cached_operation(param: str) -> str:
    # This will be cached
    return await expensive_computation(param)

# Use connection pooling
@pooled_connection("database")
async def optimized_db_query(conn, query: str):
    return await conn.fetch(query)
```

### Memory Leaks

**Problem**: Memory usage increases over time.

**Diagnosis**:
```python
import psutil
import os

def check_memory_usage():
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    
    print(f"RSS memory: {memory_info.rss / 1024 / 1024:.2f} MB")
    print(f"VMS memory: {memory_info.vms / 1024 / 1024:.2f} MB")
    
    # Check for memory leaks
    if memory_info.rss > 500 * 1024 * 1024:  # 500MB
        print("Warning: High memory usage detected")

# Monitor memory over time
import asyncio

async def monitor_memory():
    for i in range(10):
        check_memory_usage()
        await asyncio.sleep(60)  # Check every minute

asyncio.run(monitor_memory())
```

**Solutions**:
```python
# Clean up resources properly
class ResourceManager:
    async def cleanup(self):
        # Close connections
        await self.db_pool.close()
        
        # Clear caches
        await self.cache.clear()
        
        # Stop background tasks
        for task in self.background_tasks:
            task.cancel()

# Use weak references for caches
import weakref

cache = weakref.WeakValueDictionary()
```

### High CPU Usage

**Problem**: CPU usage is consistently high.

**Diagnosis**:
```python
import psutil
import time

def monitor_cpu():
    process = psutil.Process(os.getpid())
    
    while True:
        cpu_percent = process.cpu_percent()
        print(f"CPU usage: {cpu_percent}%")
        
        if cpu_percent > 80:
            print("Warning: High CPU usage")
            # Get thread information
            threads = process.threads()
            print(f"Active threads: {len(threads)}")
        
        time.sleep(5)

# Run in separate thread
import threading
threading.Thread(target=monitor_cpu, daemon=True).start()
```

## Database Issues

### Connection Pool Exhaustion

**Problem**: Database connection pool is exhausted.

**Diagnosis**:
```python
from mcp_sdk.core.config import get_config

def check_db_config():
    config = get_config()
    db_config = config.database
    
    print(f"Pool size: {db_config.pool_size}")
    print(f"Max overflow: {db_config.max_overflow}")
    print(f"Pool timeout: {db_config.pool_timeout}")

check_db_config()
```

**Solutions**:
```python
# Increase pool size
MCP_DB_POOL_SIZE=20
MCP_DB_MAX_OVERFLOW=30

# Or in configuration
database:
  pool_size: 20
  max_overflow: 30
  pool_timeout: 60
```

### Slow Queries

**Problem**: Database queries are slow.

**Diagnosis**:
```python
# Enable query logging
MCP_DB_ECHO=true

# Or in code
from sqlalchemy import event
from sqlalchemy.engine import Engine

@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, params, context, executemany):
    context._query_start_time = time.time()

@event.listens_for(Engine, "after_cursor_execute")
def receive_after_cursor_execute(conn, cursor, statement, params, context, executemany):
    total = time.time() - context._query_start_time
    if total > 1.0:  # Log slow queries
        print(f"Slow query ({total:.3f}s): {statement}")
```

**Optimization**:
```python
# Add database indexes
CREATE INDEX idx_user_email ON users(email);
CREATE INDEX idx_message_created ON messages(created_at);

# Use connection pooling
@pooled_connection("database")
async def optimized_query(conn, query: str):
    return await conn.fetch(query)
```

## Network Issues

### Connection Timeouts

**Problem**: Connections timeout frequently.

**Diagnosis**:
```python
import asyncio
import aiohttp

async def test_connectivity():
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get("http://localhost:8080/health") as response:
                print(f"Health check: {response.status}")
    except asyncio.TimeoutError:
        print("Connection timeout")
    except Exception as e:
        print(f"Connection failed: {e}")

asyncio.run(test_connectivity())
```

**Solutions**:
```python
# Increase timeout values
MCP_SERVER_TIMEOUT=60

# Or in configuration
server:
  timeout: 60
  keepalive: 5

# Use retry logic
@retry_async(RetryConfig(max_attempts=3, base_delay=1.0))
async def resilient_operation():
    return await some_network_operation()
```

### Port Conflicts

**Problem**: Server cannot bind to port.

**Diagnosis**:
```bash
# Check what's using the port
lsof -i :8080
netstat -tulpn | grep :8080

# Check if port is available
python -c "
import socket
s = socket.socket()
result = s.connect_ex(('localhost', 8080))
print('Port available' if result != 0 else 'Port in use')
s.close()
"
```

**Solutions**:
```bash
# Kill process using the port
sudo kill -9 $(lsof -t -i:8080)

# Or use different port
MCP_SERVER_PORT=8081
```

## Memory Issues

### Out of Memory Errors

**Problem**: Application crashes with out of memory errors.

**Diagnosis**:
```python
import gc
import tracemalloc

def check_memory():
    # Enable memory tracing
    tracemalloc.start()
    
    # Get memory usage
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics('lineno')
    
    print("Top memory allocations:")
    for stat in top_stats[:10]:
        print(stat)

check_memory()
```

**Solutions**:
```python
# Limit cache sizes
MCP_PERF_CACHE_MAX_SIZE=1000

# Use generators instead of lists
def process_large_dataset():
    for item in large_dataset:
        yield process_item(item)

# Clear caches periodically
async def cleanup_caches():
    optimizer = get_performance_optimizer()
    await optimizer.cache.clear()
```

### Memory Fragmentation

**Problem**: Memory usage increases even after garbage collection.

**Diagnosis**:
```python
import gc
import objgraph

def analyze_memory():
    # Force garbage collection
    gc.collect()
    
    # Find memory leaks
    objgraph.show_most_common_types(limit=20)
    
    # Find reference cycles
    objgraph.show_backrefs([obj], max_depth=10)

analyze_memory()
```

## Logging and Debugging

### Enable Debug Logging

**Problem**: Need more detailed logging for debugging.

**Solution**:
```bash
# Set debug log level
MCP_OBS_LOG_LEVEL=DEBUG

# Or in configuration
observability:
  log_level: DEBUG
  enable_tracing: true
```

```python
# Configure structured logging
import structlog

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

logger = structlog.get_logger(__name__)
```

### Enable Performance Monitoring

**Solution**:
```python
from mcp_sdk.core.monitoring import get_monitoring

# Enable monitoring
monitoring = get_monitoring()
await monitoring.start()

# Add custom metrics
monitoring.metrics.increment("custom_counter")
monitoring.metrics.gauge("custom_gauge", 42)
monitoring.metrics.timing("custom_timing", 1.23)
```

### Use Debug Mode

**Solution**:
```bash
# Enable debug mode
MCP_DEBUG=true

# Or in code
from mcp_sdk.core.config import ConfigContext

with ConfigContext(debug=True):
    # Your code here
    pass
```

### Common Debugging Commands

```bash
# Check application status
curl http://localhost:8080/health

# Check metrics
curl http://localhost:9090/metrics

# Check configuration
python -c "
from mcp_sdk.core.config import get_config
config = get_config()
print(config)
"

# Test database connection
python -c "
import asyncio
from mcp_sdk.core.config import get_config
config = get_config()
print(f'Database URL: {config.get_database_url()}')
"

# Check loaded plugins
python -c "
import asyncio
from mcp_sdk.core.plugin_manager import PluginManager
from mcp_sdk.core.registry import PluginRegistry

async def check_plugins():
    registry = PluginRegistry()
    manager = PluginManager(registry)
    loaded = await manager.load_all()
    print(f'Loaded plugins: {list(loaded.keys())}')

asyncio.run(check_plugins())
"
```

## Getting Help

If you're still experiencing issues:

1. **Check the logs**: Look for error messages in the application logs
2. **Enable debug mode**: Set `MCP_DEBUG=true` for more detailed logging
3. **Check GitHub Issues**: Search for similar issues in the repository
4. **Create a minimal reproduction**: Create a simple script that reproduces the issue
5. **Include system information**: Python version, OS, and dependency versions
6. **Provide error details**: Full error messages and stack traces

### Reporting Issues

When reporting issues, include:

```bash
# System information
python --version
pip list | grep mcp-sdk

# Configuration
env | grep MCP_

# Error logs
tail -f logs/app.log

# Health check
curl http://localhost:8080/health
```

This troubleshooting guide should help you resolve most common issues with the MCP SDK. For more complex problems, don't hesitate to reach out to the community or create an issue on GitHub.

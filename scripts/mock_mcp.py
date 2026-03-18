import sys
import types

m = types.ModuleType('mcp')
m.server = types.ModuleType('mcp.server')
m.server.models = types.ModuleType('mcp.server.models')
m.client = types.ModuleType('mcp.client')
m.client.session = types.ModuleType('mcp.client.session')
m.types = types.ModuleType('mcp.types')
sys.modules['mcp'] = m
sys.modules['mcp.server'] = m.server
sys.modules['mcp.server.models'] = m.server.models
sys.modules['mcp.client'] = m.client
sys.modules['mcp.client.session'] = m.client.session
sys.modules['mcp.types'] = m.types

class Stub:
    def __init__(self, *a, **k): pass
    def __getattr__(self, name): return Stub

m.Server = Stub
m.ClientSession = Stub
m.server.models.InitializationOptions = Stub
m.types.Tool = Stub
m.types.TextContent = Stub
m.types.ImageContent = Stub
m.types.EmbeddedResource = Stub
m.types.LoggingLevel = Stub
m.types.Resource = Stub
m.types.ResourceContents = Stub


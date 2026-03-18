import sys
import types


# 1. Simple but effective mocking of 'mcp'
class Stub:
    def __init__(self, *args, **kwargs):
        pass
    def __getattr__(self, name):
        # Avoid recursion on special attributes used by python/pytest
        if name.startswith('__') and name.endswith('__'):
            raise AttributeError(name)
        return Stub()
    def __call__(self, *args, **kwargs):
        return Stub()

mcp = types.ModuleType('mcp')
mcp.server = types.ModuleType('mcp.server')
mcp.server.models = types.ModuleType('mcp.server.models')
mcp.client = types.ModuleType('mcp.client')
mcp.client.session = types.ModuleType('mcp.client.session')
mcp.types = types.ModuleType('mcp.types')

# Populate with Stub for everything
for module in [mcp, mcp.server, mcp.server.models, mcp.client, mcp.client.session, mcp.types]:
    # This is a bit hacky but works for the imports
    class LocalStub(Stub): pass
    module.Stub = LocalStub
    # We want any 'from mcp.types import X' to work
    # We can use a __getattr__ on the module if it's Python 3.7+

# Use a custom Module class to handle dynamic imports
class MockModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith('__'): return super().__getattr__(name)
        return Stub()

def create_mock_module(name):
    m = MockModule(name)
    sys.modules[name] = m
    return m

create_mock_module('mcp')
create_mock_module('mcp.server')
create_mock_module('mcp.server.models')
create_mock_module('mcp.client')
create_mock_module('mcp.client.session')
create_mock_module('mcp.types')

# 2. Run Pytest
import os

import pytest

conftest_path = "tests/conftest.py"
conftest_bak = "tests/conftest.py.bak"
moved = False

if os.path.exists(conftest_path):
    os.rename(conftest_path, conftest_bak)
    moved = True

try:
    print("🚀 Starting Architectural Verification Tests (MockModule)...")
    exit_code = pytest.main([
        'tests/test_inference.py',
        'tests/test_context.py',
        'tests/test_geospatial.py',
        'tests/test_loop.py',
        '-v',
        '-c', '/dev/null'
    ])
    sys.exit(exit_code)
finally:
    if moved and os.path.exists(conftest_bak):
        if os.path.exists(conftest_path):
            os.remove(conftest_path)
        os.rename(conftest_bak, conftest_path)

import asyncio
import os
import sys

# Ensure we can import from the current playbooksy
sys.path.insert(0, os.path.abspath("."))

from mcp_sdk.core.protocol import MCPProtocol
from mcp_sdk.plugins.active_inference import ActiveInferencePlugin
from mcp_sdk.plugins.anomaly import AnomalyPlugin
from mcp_sdk.plugins.context import ContextPlugin
from mcp_sdk.plugins.geospatial import GeospatialPlugin
from mcp_sdk.plugins.security import SecurityPlugin
from mcp_sdk.plugins.thinking import ThinkingPlugin


async def smoke_test():
    print("--- 🚀 MCP SDK Plugin Architecture: Mega Smoke Test ---")

    # 1. Initialize Protocol
    protocol = MCPProtocol(name="aro-platform")
    print(f"Protocol initialized: {protocol.name}")

    # 2. Load Plugins
    plugins_to_load = [
        GeospatialPlugin,
        SecurityPlugin,
        ActiveInferencePlugin,
        ContextPlugin,
        AnomalyPlugin,
        ThinkingPlugin
    ]

    print(f"Loading {len(plugins_to_load)} plugins...")
    for plugin_cls in plugins_to_load:
        plugin = await protocol.load_plugin(plugin_cls)
        print(f"  ✅ {plugin.name} v{plugin.version} loaded")

    # 3. Verify Combined Tool Registry
    tools = list(protocol._tools.keys())
    print(f"\nTotal Registered Tools ({len(tools)}):")
    for t in sorted(tools):
        print(f"  - {t}")

    # Assertions
    expected_tools = [
        "geo_query_region",
        "security_scan_text",
        "inference_predict",
        "context_add",
        "anomaly_check",
        "thinking_step"
    ]
    for et in expected_tools:
        assert et in tools, f"Missing expected tool: {et}"

    print("\n✅ All core plugin tools verified")

    # 4. Verify Middleware
    print("\nVerifying middleware chain...")
    assert len(protocol._middleware) >= 1
    print(f"  ✅ Middleware count: {len(protocol._middleware)}")

    print("\n--- ✨ ALL SYSTEMS GO: PLUGIN ARCHITECTURE VERIFIED ---")

if __name__ == "__main__":
    asyncio.run(smoke_test())

import pytest

from mcp_sdk.server.fastmcp import FastMCP

pytestmark = pytest.mark.anyio


async def test_list_tools_returns_all_tools():
    mcp = FastMCP("TestTools")

    # Create 100 tools with unique names
    num_tools = 100
    for i in range(num_tools):

        @mcp_sdk.tool(name=f"tool_{i}")
        def dummy_tool_func():
            f"""Tool number {i}"""
            return i

        globals()[f"dummy_tool_{i}"] = (
            dummy_tool_func  # Keep reference to avoid garbage collection
        )

    # Get all tools
    tools = await mcp_sdk.list_tools()

    # Verify we get all tools
    assert len(tools) == num_tools, f"Expected {num_tools} tools, but got {len(tools)}"

    # Verify each tool is unique and has the correct name
    tool_names = [tool.name for tool in tools]
    expected_names = [f"tool_{i}" for i in range(num_tools)]
    assert sorted(tool_names) == sorted(
        expected_names
    ), "Tool names don't match expected names"

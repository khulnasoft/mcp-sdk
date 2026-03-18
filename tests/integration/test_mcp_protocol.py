"""
Integration Tests for MCP Protocol
==================================
End-to-end testing of MCP protocol functionality.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
import pytest_asyncio

from mcp_sdk.core.config import MCPConfig
from mcp_sdk.core.protocol import MCPProtocol
from mcp_sdk.types import (
    CallToolResult,
    GetPromptResult,
    ListPromptsResult,
    ListResourcesResult,
    ListToolsResult,
    ReadResourceResult,
)


@pytest_asyncio.fixture
async def mcp_protocol():
    """Create a test MCP protocol instance."""
    config = MCPConfig(
        server_name="test-server",
        server_version="1.0.0",
    )
    protocol = MCPProtocol("test-agent", "1.0.0", config)

    # Register test tools
    @protocol.tool("test_echo", "Echo the input", {"type": "object", "properties": {"message": {"type": "string"}}})
    async def test_echo(message: str) -> str:
        return f"Echo: {message}"

    @protocol.tool("test_error", "Intentionally throw an error")
    async def test_error() -> None:
        raise ValueError("Test error")

    # Register test resources
    @protocol.resource("test://data/*")
    async def test_data(uri: str) -> str:
        return f"Data for {uri}"

    # Register test prompts
    @protocol.prompt("test_prompt", "A test prompt")
    async def test_prompt() -> str:
        return "This is a test prompt"

    return protocol


@pytest.mark.asyncio
class TestMCPProtocolIntegration:
    """Integration tests for MCP protocol."""

    async def test_list_tools(self, mcp_protocol: MCPProtocol) -> None:
        """Test listing available tools."""
        result = await mcp_protocol._list_tools()

        assert isinstance(result, ListToolsResult)
        assert len(result.tools) >= 2  # test_echo and test_error

        tool_names = [tool.name for tool in result.tools]
        assert "test_echo" in tool_names
        assert "test_error" in tool_names

        # Check tool schemas
        echo_tool = next(t for t in result.tools if t.name == "test_echo")
        assert echo_tool.description == "Echo the input"
        assert "message" in echo_tool.inputSchema["properties"]

    async def test_call_tool_success(self, mcp_protocol: MCPProtocol) -> None:
        """Test successful tool execution."""
        result = await mcp_protocol._call_tool("test_echo", {"message": "Hello"})

        assert isinstance(result, CallToolResult)
        assert len(result.content) == 1
        assert result.content[0].text == "Echo: Hello"
        assert result.content[0].type == "text"

    async def test_call_tool_not_found(self, mcp_protocol: MCPProtocol) -> None:
        """Test calling a non-existent tool."""
        with pytest.raises(Exception) as exc_info:
            await mcp_protocol._call_tool("non_existent_tool", {})

        assert "not found" in str(exc_info.value).lower()

    async def test_call_tool_error(self, mcp_protocol: MCPProtocol) -> None:
        """Test tool that raises an error."""
        with pytest.raises(Exception) as exc_info:
            await mcp_protocol._call_tool("test_error", {})

        assert "Test error" in str(exc_info.value)

    async def test_list_resources(self, mcp_protocol: MCPProtocol) -> None:
        """Test listing available resources."""
        result = await mcp_protocol._list_resources()

        assert isinstance(result, ListResourcesResult)
        assert len(result.resources) >= 1

        resource_names = [res.name for res in result.resources]
        assert "test://data/*" in resource_names

    async def test_read_resource(self, mcp_protocol: MCPProtocol) -> None:
        """Test reading a resource."""
        result = await mcp_protocol._read_resource("test://data/example")

        assert isinstance(result, ReadResourceResult)
        assert len(result.contents) == 1
        assert result.contents[0].text == "Data for test://data/example"
        assert result.contents[0].uri == "test://data/example"

    async def test_read_resource_not_found(self, mcp_protocol: MCPProtocol) -> None:
        """Test reading a non-existent resource."""
        with pytest.raises(Exception) as exc_info:
            await mcp_protocol._read_resource("non://existent/resource")

        assert "not found" in str(exc_info.value).lower()

    async def test_list_prompts(self, mcp_protocol: MCPProtocol) -> None:
        """Test listing available prompts."""
        result = await mcp_protocol._list_prompts()

        assert isinstance(result, ListPromptsResult)
        assert len(result.prompts) >= 1

        prompt_names = [p.name for p in result.prompts]
        assert "test_prompt" in prompt_names

    async def test_get_prompt(self, mcp_protocol: MCPProtocol) -> None:
        """Test getting a prompt."""
        result = await mcp_protocol._get_prompt("test_prompt")

        assert isinstance(result, GetPromptResult)
        assert len(result.messages) >= 1
        assert "This is a test prompt" in result.messages[0].content.text

    async def test_get_prompt_not_found(self, mcp_protocol: MCPProtocol) -> None:
        """Test getting a non-existent prompt."""
        with pytest.raises(Exception) as exc_info:
            await mcp_protocol._get_prompt("non_existent_prompt")

        assert "not found" in str(exc_info.value).lower()

    async def test_concurrent_tool_calls(self, mcp_protocol: MCPProtocol) -> None:
        """Test concurrent tool execution."""
        tasks = [
            mcp_protocol._call_tool("test_echo", {"message": f"Message {i}"})
            for i in range(10)
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        for i, result in enumerate(results):
            assert isinstance(result, CallToolResult)
            assert result.content[0].text == f"Echo: Message {i}"

    async def test_tool_with_complex_arguments(self, mcp_protocol: MCPProtocol) -> None:
        """Test tool execution with complex arguments."""
        @mcp_protocol.tool("complex_tool", "Tool with complex args")
        async def complex_tool(
            text: str,
            number: int,
            flag: bool = False,
            items: list[str] | None = None
        ) -> dict[str, Any]:
            return {
                "text": text,
                "number": number,
                "flag": flag,
                "items": items or [],
            }

        args = {
            "text": "test",
            "number": 42,
            "flag": True,
            "items": ["a", "b", "c"]
        }

        result = await mcp_protocol._call_tool("complex_tool", args)

        assert isinstance(result, CallToolResult)
        # Parse the JSON result from text content
        result_data = json.loads(result.content[0].text)
        assert result_data["text"] == "test"
        assert result_data["number"] == 42
        assert result_data["flag"] is True
        assert result_data["items"] == ["a", "b", "c"]


@pytest.mark.asyncio
class TestMCPProtocolErrorHandling:
    """Test error handling in MCP protocol."""

    async def test_tool_timeout_handling(self, mcp_protocol: MCPProtocol) -> None:
        """Test handling of tool timeouts."""
        @mcp_protocol.tool("slow_tool", "Tool that takes too long")
        async def slow_tool() -> str:
            await asyncio.sleep(5)  # Longer than typical timeout
            return "Done"

        # This should handle timeout gracefully
        with pytest.raises(asyncio.TimeoutError):
            async with asyncio.timeout(1.0):
                await mcp_protocol._call_tool("slow_tool", {})

    async def test_malformed_tool_arguments(self, mcp_protocol: MCPProtocol) -> None:
        """Test handling of malformed tool arguments."""
        # Test with missing required arguments
        with pytest.raises(Exception):
            await mcp_protocol._call_tool("test_echo", {})  # Missing 'message'

    async def test_resource_access_control(self, mcp_protocol: MCPProtocol) -> None:
        """Test resource access control."""
        @mcp_protocol.resource("restricted://secret/*")
        async def restricted_resource(uri: str) -> str:
            # Simulate access control
            if "admin" not in uri:
                raise PermissionError("Access denied")
            return "Secret data"

        # Should succeed
        result = await mcp_protocol._read_resource("restricted://secret/admin")
        assert result.contents[0].text == "Secret data"

        # Should fail
        with pytest.raises(PermissionError):
            await mcp_protocol._read_resource("restricted://secret/user")


@pytest.mark.asyncio
class TestMCPProtocolPerformance:
    """Performance tests for MCP protocol."""

    async def test_large_payload_handling(self, mcp_protocol: MCPProtocol) -> None:
        """Test handling of large payloads."""
        large_text = "x" * 10000  # 10KB payload

        result = await mcp_protocol._call_tool("test_echo", {"message": large_text})

        assert isinstance(result, CallToolResult)
        assert result.content[0].text == f"Echo: {large_text}"

    async def test_high_frequency_operations(self, mcp_protocol: MCPProtocol) -> None:
        """Test high-frequency operations."""
        import time

        start_time = time.perf_counter()

        # Perform 100 operations
        tasks = [
            mcp_protocol._call_tool("test_echo", {"message": f"msg_{i}"})
            for i in range(100)
        ]

        await asyncio.gather(*tasks)

        duration = time.perf_counter() - start_time

        # Should complete within reasonable time (adjust threshold as needed)
        assert duration < 10.0  # 10 seconds for 100 operations
        print(f"Completed 100 operations in {duration:.2f}s")

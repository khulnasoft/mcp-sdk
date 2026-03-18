"""
gRPC Client for Polyglot Delegation
====================================
Bridges the Python SDK to the high-performance Rust Core.
Delegates heavy inference and spatial tasks to avoid GIL contention.
"""

from __future__ import annotations

import json
from typing import Any

import grpc
import structlog

from mcp_sdk.core.generated import plugin_pb2, plugin_pb2_grpc

logger = structlog.get_logger(__name__)


class RustCoreClient:
    """
    Client for interacting with the Rust-based Sovereign Reality Engine.
    """

    def __init__(self, address: str = "localhost:50051") -> None:
        self.address = address
        self._channel = grpc.insecure_channel(address)
        self._stub = plugin_pb2_grpc.PluginServiceStub(self._channel)

    def call_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Delegates a tool call to the Rust Core via gRPC.
        """
        logger.info("Delegating tool to Rust Core", tool=tool_name)

        request = plugin_pb2.ToolRequest(tool_name=tool_name, input_json=json.dumps(params))

        try:
            response = self._stub.CallTool(request)
            if response.success:
                return json.loads(response.output_json)
            else:
                return {"error": response.error_message}
        except Exception as e:
            logger.error("gRPC call failed", error=str(e))
            return {"error": str(e)}

    def close(self) -> None:
        self._channel.close()

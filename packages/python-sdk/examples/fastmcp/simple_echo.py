"""
FastMCP Echo Server
"""

from mcp_sdk.server.fastmcp import FastMCP

# Create server
mcp = FastMCP("Echo Server")


@mcp_sdk.tool()
def echo(text: str) -> str:
    """Echo the input text"""
    return text

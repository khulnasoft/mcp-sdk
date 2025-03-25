"""
FastMCP Desktop Example

A simple example that exposes the desktop directory as a resource.
"""

from pathlib import Path

from mcp_sdk.server.fastmcp import FastMCP

# Create server
mcp = FastMCP("Demo")


@mcp_sdk.resource("dir://desktop")
def desktop() -> list[str]:
    """List the files in the user's desktop"""
    desktop = Path.home() / "Desktop"
    return [str(f) for f in desktop.iterdir()]


@mcp_sdk.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

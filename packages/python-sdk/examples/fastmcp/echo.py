"""
FastMCP Echo Server
"""

from mcp_sdk.server.fastmcp import FastMCP

# Create server
mcp = FastMCP("Echo Server")


@mcp_sdk.tool()
def echo_tool(text: str) -> str:
    """Echo the input text"""
    return text


@mcp_sdk.resource("echo://static")
def echo_resource() -> str:
    return "Echo!"


@mcp_sdk.resource("echo://{text}")
def echo_template(text: str) -> str:
    """Echo the input text"""
    return f"Echo: {text}"


@mcp_sdk.prompt("echo")
def echo_prompt(text: str) -> str:
    return text

"""
Example: MCP Protocol Server
==============================
A complete MCP server exposing tools, resources, and prompts.
Compatible with Claude Desktop and any MCP client.
"""

import asyncio

from mcp_sdk.core import MCPProtocol
from mcp_sdk.tools.registry import ToolRegistry

# ------------------------------------------------------------------ #
#  Create protocol server                                              #
# ------------------------------------------------------------------ #

protocol = MCPProtocol(
    name="example-mcp-server",
    version="1.0.0",
)

tool_registry = ToolRegistry()


# ------------------------------------------------------------------ #
#  Register Tools                                                      #
# ------------------------------------------------------------------ #


@protocol.tool("search_database", description="Search the internal knowledge database")
async def search_database(query: str, limit: int = 10) -> dict:
    """Search the internal knowledge database for relevant documents."""
    # Simulated results
    return {
        "query": query,
        "hits": [
            {"id": f"doc-{i}", "title": f"Document about {query} #{i}", "score": 0.9 - i * 0.1}
            for i in range(min(limit, 5))
        ],
        "total": 42,
    }


@protocol.tool("get_user_profile", description="Get user profile by ID")
async def get_user_profile(user_id: str) -> dict:
    """Retrieve a user profile from the platform."""
    return {
        "id": user_id,
        "name": "Alice Example",
        "email": "alice@example.com",
        "tier": "premium",
        "agent_access": ["a2a", "b2c"],
    }


@protocol.tool("send_notification", description="Send a notification to a user")
async def send_notification(user_id: str, message: str, channel: str = "email") -> dict:
    """Send a notification through the specified channel."""
    return {
        "sent": True,
        "user_id": user_id,
        "channel": channel,
        "message_preview": message[:50] + "..." if len(message) > 50 else message,
    }


@protocol.tool("list_agents", description="List all available agents")
async def list_agents(agent_type: str = "") -> dict:
    """List agents registered on this platform."""
    from mcp_sdk.agents.registry import AgentRegistry

    registry = AgentRegistry.global_registry()
    agents = registry.find_by_type(agent_type) if agent_type else registry.list_all()
    return {
        "agents": [a.to_dict() for a in agents],
        "count": len(agents),
    }


# ------------------------------------------------------------------ #
#  Register Resources                                                  #
# ------------------------------------------------------------------ #


@protocol.resource("agent://", name="Agents", description="Agent definitions")
async def get_agent_resource(uri: str) -> str:
    """Return agent metadata as JSON."""
    import json

    agent_id = uri.replace("agent://", "")
    return json.dumps({"agent_id": agent_id, "status": "active"})


@protocol.resource("config://", name="Configuration", description="Platform configuration")
async def get_config_resource(uri: str) -> str:
    """Return platform configuration."""
    import json

    return json.dumps({"version": "0.1.0", "env": "development", "features": ["a2a", "b2b"]})


# ------------------------------------------------------------------ #
#  Register Prompts                                                    #
# ------------------------------------------------------------------ #


@protocol.prompt("agent_system_prompt", description="System prompt for an agent persona")
async def agent_system_prompt(persona: str = "assistant", domain: str = "general") -> str:
    """Generate a system prompt for an agent."""
    return (
        f"You are {persona}, an intelligent AI agent specialized in {domain}. "
        f"You operate within the MCP Agent Platform and have access to tools for "
        f"searching, user management, and cross-agent communication. "
        f"Always be helpful, accurate, and concise."
    )


@protocol.prompt("user_onboarding", description="Onboarding prompt for new users")
async def user_onboarding_prompt(user_name: str = "there") -> str:
    return (
        f"Hello {user_name}! Welcome to the MCP Agent Platform. "
        f"I'm here to help you get started. You can ask me to:\n"
        f"- Search our knowledge base\n"
        f"- Connect with specialist agents\n"
        f"- Set up automated workflows\n"
        f"What would you like to do first?"
    )


# ------------------------------------------------------------------ #
#  Lifecycle hooks                                                     #
# ------------------------------------------------------------------ #


@protocol.on_startup
async def on_startup() -> None:
    print("🚀 MCP Server starting up...")


@protocol.on_shutdown
async def on_shutdown() -> None:
    print("🛑 MCP Server shutting down...")


# ------------------------------------------------------------------ #
#  Entry point                                                         #
# ------------------------------------------------------------------ #


async def main() -> None:
    """Run the MCP server over stdio for use with Claude Desktop."""
    await protocol.serve_stdio()


if __name__ == "__main__":
    asyncio.run(main())

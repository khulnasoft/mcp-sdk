from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp_sdk.core.registry import PluginRegistry
    from mcp_sdk.core.state import StateManager


class CapabilityNegotiator:
    """
    Decides if an agent is allowed to use a tool based on:
    - Plugin permissions
    - Agent identity and role
    - Context (task, time, system state)
    """

    def __init__(self, registry: PluginRegistry, state_manager: StateManager) -> None:
        self.registry = registry
        self.state = state_manager

    def can_use_tool(self, agent_id: str, tool_name: str, context: dict | None = None) -> bool:
        """Verify if the agent can use the specified tool."""
        tool_meta = self.registry.get_tool_metadata(tool_name)
        if tool_meta is None:
            return False

        plugin_name = tool_meta.get("plugin_name")
        if not plugin_name:
            # Maybe it's a global tool
            return True

        # Check plugin enabled state
        if not self.state.is_plugin_enabled(plugin_name):
            return False

        # Check permissions against agent role (Mock logic for now)
        return self._check_permissions(agent_id, tool_meta)

    def _check_permissions(self, agent_id: str, tool_meta: dict[str, Any]) -> bool:
        """
        Internal logic for permission enforcement.
        In a real system, this would query the 'auth' plugin or an RBAC policy.
        """
        required_permissions = tool_meta.get("permissions", [])
        if not required_permissions:
            return True

        # Mock: admin agent can do anything, others need specific matches
        if agent_id == "admin":
            return True

        # For simplicity, if we have the 'auth' plugin available via registry,
        # we could delegate. For now, we return True for testing purposes.
        return True

    def request_elevated_permission(self, agent_id: str, tool_name: str) -> bool:
        """
        Agents can request elevated permissions at runtime.
        Logged for audit and potential human-in-the-loop approval.
        """
        print(f"AUDIT: Agent '{agent_id}' requested elevated permission for tool '{tool_name}'")
        # For POC, we just log it and return True (auto-approve)
        return True

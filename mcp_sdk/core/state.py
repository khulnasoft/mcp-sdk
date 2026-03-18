"""
Persistent State Management for MCP SDK
=======================================
Handles saving and loading plugin settings (enabled/disabled, etc.).
"""

import json
from pathlib import Path
from typing import Any


class StateManager:
    """
    Manages persistent state in a JSON file.
    Default path: ~/.mcp/plugins.json
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load state from disk."""
        if self.path.exists():
            try:
                with open(self.path) as f:
                    self._data = json.load(f)
            except (OSError, json.JSONDecodeError):
                self._data = {}
        else:
            self._data = {}

    def save(self) -> None:
        """Save current state to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=4)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from state."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in state and save."""
        self._data[key] = value
        self.save()

    def is_plugin_enabled(self, name: str) -> bool:
        """Check if a plugin is enabled. Defaults to True if not set."""
        plugin_states = self.get("plugins", {})
        return plugin_states.get(name, {}).get("enabled", True)

    def set_plugin_enabled(self, name: str, enabled: bool) -> None:
        """Set the enabled status for a plugin."""
        plugin_states = self.get("plugins", {})
        if name not in plugin_states:
            plugin_states[name] = {}
        plugin_states[name]["enabled"] = enabled
        self.set("plugins", plugin_states)

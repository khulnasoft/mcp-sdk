"""
Agent Registry
==============
Central registry for discovering, registering, and resolving agents.
Supports capability-based lookup and tag filtering.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from mcp_sdk.core.exceptions import AgentAlreadyExistsError, AgentNotFoundError

logger = structlog.get_logger(__name__)


class AgentRegistry:
    """
    Thread-safe, async-native agent registry.

    Agents register themselves here and can be resolved by ID, name,
    type, capability, or tag.

    Example::

        registry = AgentRegistry()
        registry.register(my_agent)

        agent = registry.get("agent-id-or-name")
        agents = registry.find_by_capability("search")
    """

    def __init__(self) -> None:
        self._agents: dict[str, Any] = {}  # id -> agent
        self._name_index: dict[str, str] = {}  # name -> id
        self._type_index: dict[str, set[str]] = {}  # type -> {ids}
        self._capability_index: dict[str, set[str]] = {}  # capability -> {ids}
        self._tag_index: dict[str, set[str]] = {}  # tag -> {ids}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ #
    #  Registration                                                        #
    # ------------------------------------------------------------------ #

    async def register(self, agent: Any) -> None:
        """Register an agent instance."""
        async with self._lock:
            agent_id = agent.id
            if agent_id in self._agents:
                raise AgentAlreadyExistsError(agent_id)

            self._agents[agent_id] = agent
            self._name_index[agent.name] = agent_id

            # Type index
            atype = agent.AGENT_TYPE
            self._type_index.setdefault(atype, set()).add(agent_id)

            # Capability index
            for cap in agent.get_capabilities():
                self._capability_index.setdefault(cap, set()).add(agent_id)

            # Tag index
            for tag in agent.metadata.tags:
                self._tag_index.setdefault(tag, set()).add(agent_id)

            logger.info("Agent registered", agent_id=agent_id, name=agent.name, type=atype)

    async def unregister(self, agent_id: str) -> None:
        """Remove an agent from the registry."""
        async with self._lock:
            if agent_id not in self._agents:
                raise AgentNotFoundError(agent_id)

            agent = self._agents.pop(agent_id)
            self._name_index.pop(agent.name, None)

            # Clean up indexes
            for idx in (self._type_index, self._capability_index, self._tag_index):
                for ids in idx.values():
                    ids.discard(agent_id)

            logger.info("Agent unregistered", agent_id=agent_id)

    # ------------------------------------------------------------------ #
    #  Lookup                                                              #
    # ------------------------------------------------------------------ #

    def get(self, agent_id: str) -> Any:
        """Get agent by ID. Raises AgentNotFoundError if not found."""
        if agent_id in self._agents:
            return self._agents[agent_id]
        # Try name lookup
        if agent_id in self._name_index:
            return self._agents[self._name_index[agent_id]]
        raise AgentNotFoundError(agent_id)

    def get_by_name(self, name: str) -> Any:
        """Get agent by name."""
        if name not in self._name_index:
            raise AgentNotFoundError(name)
        return self._agents[self._name_index[name]]

    def find_by_type(self, agent_type: str) -> list[Any]:
        """Return all agents of a given type."""
        ids = self._type_index.get(agent_type, set())
        return [self._agents[i] for i in ids if i in self._agents]

    def find_by_capability(self, capability: str) -> list[Any]:
        """Return all agents supporting a given capability."""
        ids = self._capability_index.get(capability, set())
        return [self._agents[i] for i in ids if i in self._agents]

    def find_by_tag(self, tag: str) -> list[Any]:
        """Return all agents with a given tag."""
        ids = self._tag_index.get(tag, set())
        return [self._agents[i] for i in ids if i in self._agents]

    def list_all(self) -> list[Any]:
        """Return all registered agents."""
        return list(self._agents.values())

    def count(self) -> int:
        """Return the number of registered agents."""
        return len(self._agents)

    # ------------------------------------------------------------------ #
    #  Class-level global registry                                         #
    # ------------------------------------------------------------------ #

    _global: AgentRegistry | None = None

    @classmethod
    def global_registry(cls) -> AgentRegistry:
        """Return the process-level singleton registry."""
        if cls._global is None:
            cls._global = cls()
        return cls._global

    def __repr__(self) -> str:
        return f"AgentRegistry(count={self.count()})"

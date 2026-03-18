"""
Metadata Plugin
===============
Exposes data source catalogs and semantic metadata registries as MCP tools.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from mcp_sdk.core.plugin import MCPPlugin
from mcp_sdk.core.registry import PluginRegistry
from mcp_sdk.plugins.metadata.registry import (
    ColumnMetadata,
    DataSource,
    MetadataRegistry,
    SourceType,
    TableMetadata,
)


class MetadataPlugin(MCPPlugin):
    """MCP Plugin for harvesting and discovering geospatial metadata."""

    def __init__(self, name: str = "metadata") -> None:
        self._name = name
        self.registry = MetadataRegistry()
        self._tools_dict: dict[str, dict[str, Any]] = {}

    @property
    def name(self) -> str:
        return self._name

    def register_tools(self, registry: PluginRegistry) -> None:
        """Register MCP tools with the registry."""
        registry.register_tool(
            name=f"{self.name}.register_source",
            func=self.register_source,
            metadata={
                "description": "Register a new geospatial data source (Postgres, BigQuery, Snowflake)",
                "tags": ["metadata", "data", "admin"],
            },
        )
        registry.register_tool(
            name=f"{self.name}.harvest_source",
            func=self.harvest_source,
            metadata={
                "description": "Harvest structural and semantic metadata from a registered source",
                "tags": ["metadata", "data", "admin"],
            },
        )
        registry.register_tool(
            name=f"{self.name}.search_metadata",
            func=self.search_metadata,
            metadata={
                "description": "Search for tables and schemas matching a query",
                "tags": ["metadata", "search", "data"],
            },
        )
        registry.register_tool(
            name=f"{self.name}.get_table_info",
            func=self.get_table_info,
            metadata={
                "description": "Get detailed metadata for a specific table",
                "tags": ["metadata", "details", "data"],
            },
        )
        registry.register_tool(
            name=f"{self.name}.list_sources",
            func=self.list_sources,
            metadata={
                "description": "List all registered data sources",
                "tags": ["metadata", "list", "data"],
            },
        )

    def register_source(
        self, name: str, source_type: str, description: str = "", connection_uri: str = ""
    ) -> str:
        """Helper to register a source."""
        source = DataSource(
            name=name,
            type=SourceType(source_type.lower()),
            description=description,
            connection_uri=connection_uri,
        )
        return self.registry.register_source(source)

    async def harvest_source(self, source_id: str) -> int:
        """Harvest metadata from a source."""
        return await self.registry.harvest_source(source_id)

    def search_metadata(self, query: str) -> list[dict[str, Any]]:
        """Search metadata."""
        tables = self.registry.search_tables(query)
        return [t.model_dump(exclude={"columns", "source_id"}) for t in tables]

    def get_table_info(self, table_id: str) -> dict[str, Any] | None:
        """Get table info."""
        table = self.registry.get_table(table_id)
        return table.model_dump() if table else None

    def list_sources(self) -> list[dict[str, Any]]:
        """List all sources."""
        return [s.model_dump() for s in self.registry.list_sources()]

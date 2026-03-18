"""
Semantic Metadata Registry
==========================
Harmonises disparate geospatial data sources into a unified catalog.
"""

from __future__ import annotations

import uuid
from enum import StrEnum

import structlog
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, inspect

logger = structlog.get_logger(__name__)


class SourceType(StrEnum):
    POSTGRES = "postgres"
    POSTGIS = "postgis"
    BIGQUERY = "bigquery"
    SNOWFLAKE = "snowflake"
    SQLITE = "sqlite"
    MOCK = "mock"


class ColumnMetadata(BaseModel):
    name: str
    data_type: str
    description: str = ""
    semantic_type: str = ""
    tags: list[str] = Field(default_factory=list)
    primary_key: bool = False


class TableMetadata(BaseModel):
    table_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    schema_name: str = "public"
    description: str = ""
    columns: list[ColumnMetadata] = Field(default_factory=list)
    source_id: str
    tags: list[str] = Field(default_factory=list)


class DataSource(BaseModel):
    source_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    type: SourceType
    connection_uri: str = ""  # In production, this should be fetched from a secure vault
    description: str = ""


class SQLAlchemyHarvester:
    """Introspects SQL databases using SQLAlchemy."""

    @staticmethod
    def harvest(source_id: str, connection_uri: str) -> list[TableMetadata]:
        tables = []
        try:
            # We use a short-lived engine for harvesting
            engine = create_engine(connection_uri)
            inspector = inspect(engine)

            for table_name in inspector.get_table_names():
                cols = []
                for col in inspector.get_columns(table_name):
                    cols.append(
                        ColumnMetadata(
                            name=col["name"],
                            data_type=str(col["type"]),
                            primary_key=col.get("primary", False),
                        )
                    )

                tables.append(
                    TableMetadata(
                        name=table_name, columns=cols, source_id=source_id, tags=["auto-harvested"]
                    )
                )
            return tables
        except Exception as e:
            logger.error("SQLAlchemy harvesting failed", error=str(e))
            return []


class MetadataRegistry:
    def __init__(self) -> None:
        self._sources: dict[str, DataSource] = {}
        self._tables: dict[str, TableMetadata] = {}

    def register_source(self, source: DataSource) -> str:
        self._sources[source.source_id] = source
        return source.source_id

    def add_table(self, table: TableMetadata) -> str:
        self._tables[table.table_id] = table
        return table.table_id

    async def harvest_source(self, source_id: str) -> int:
        source = self._sources.get(source_id)
        if not source:
            raise ValueError("Source not found")

        logger.info("Harvesting source", source_id=source_id, type=source.type)

        if source.connection_uri and source.type in (
            SourceType.POSTGRES,
            SourceType.POSTGIS,
            SourceType.SQLITE,
        ):
            # Real Harvester
            harvested_tables = SQLAlchemyHarvester.harvest(source_id, source.connection_uri)
            for table in harvested_tables:
                self.add_table(table)
            return len(harvested_tables)
        else:
            # Fallback to Mock / Manual
            return 0

    def list_tables(self, source_id: str | None = None) -> list[TableMetadata]:
        if source_id:
            return [t for t in self._tables.values() if t.source_id == source_id]
        return list(self._tables.values())

    def to_summary(self) -> str:
        summary = f"Metadata Registry Summary ({len(self._sources)} sources)\n"
        for s in self._sources.values():
            tables = self.list_tables(s.source_id)
            summary += f"- {s.name} ({s.type}): {len(tables)} tables\n"
        return summary

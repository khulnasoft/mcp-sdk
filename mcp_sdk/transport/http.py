"""
HTTP Transport — FastAPI SSE Server
=====================================
Serves the MCP protocol over HTTP/SSE for web clients.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


def create_http_app(mcp_server: Any, server_name: str) -> FastAPI:
    """Create a FastAPI app wrapping an MCP server for HTTP transport."""

    app = FastAPI(
        title=f"MCP Agent — {server_name}",
        description="Model Context Protocol Agent Platform HTTP Transport",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "server": server_name}

    @app.get("/mcp/tools")
    async def list_tools() -> JSONResponse:
        """List all registered MCP tools."""
        try:
            tools = await mcp_server.list_tools()
            return JSONResponse(
                {"tools": [t.model_dump() if hasattr(t, "model_dump") else str(t) for t in tools]}
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post("/mcp/tools/{tool_name}")
    async def call_tool(tool_name: str, request: Request) -> JSONResponse:
        """Invoke an MCP tool via HTTP."""
        body = await request.json()
        try:
            result = await mcp_server.call_tool(tool_name, body)
            return JSONResponse({"result": result})
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/mcp/resources")
    async def list_resources() -> JSONResponse:
        try:
            resources = await mcp_server.list_resources()
            return JSONResponse({"resources": [str(r) for r in resources]})
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    return app

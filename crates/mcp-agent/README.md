## Testing stdio transport

```bash
cargo run -p mcp-agent --example stdio
```

## Testing SSE transport

1. Start the MCP gateway in one terminal: `fastmcp run -t sse echo.py`
2. Run the agent example in new terminal: `cargo run -p mcp-agent --example sse`


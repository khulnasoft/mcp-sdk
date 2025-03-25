# Model Context Protocol Examples

This directory contains examples demonstrating how to use the Model Context Protocol (MCP) Rust SDK.

## Structure

- `clients/`: Examples of MCP clients
- `servers/`: Examples of MCP servers
- `macros/`: Examples of MCP macros

## Running Client Examples

The client examples demonstrate different ways to connect to MCP servers.

Before running the examples, ensure you have `uv` installed. You can find the installation instructions [here](https://github.com/astral-sh/uv).

### Available Examples

You can run the examples in two ways:

#### Option 1: From the examples/clients directory

```bash
cd examples/clients
cargo run --example clients
cargo run --example sse
cargo run --example stdio
cargo run --example stdio_integration
```

#### Option 2: From the root directory

```bash
cargo run -p mcp-agent-examples --example clients
cargo run -p mcp-agent-examples --example sse
cargo run -p mcp-agent-examples --example stdio
cargo run -p mcp-agent-examples --example stdio_integration
```

## Running Server Examples

The server examples demonstrate how to implement MCP servers.

### Available Examples

You can run the server examples in two ways:

#### Option 1: From the examples/servers directory

```bash
cd examples/servers
cargo run --example counter-server
```

#### Option 2: From the root directory

```bash
cargo run -p mcp-gateway-examples --example counter-server
```

## Running Macros Examples

The macros examples demonstrate how to use the MCP macros to create tools.

### Available Examples

You can run the macros examples in two ways:

#### Option 1: From the examples/codegen directory

```bash
cd examples/codegen
cargo run --example calculator
```

#### Option 2: From the root directory

```bash
cargo run -p mcp-codegen-examples --example calculator
```

## Notes

- Some examples may require additional setup or running both client and server components.
- The server examples use standard I/O for communication, so they can be connected to client examples using stdio transport.
- For SSE examples, you may need to run a separate SSE server or use a compatible MCP server implementation.

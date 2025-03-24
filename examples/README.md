# Model Context Protocol Examples

This directory contains examples demonstrating how to use the Model Context Protocol (MCP) Rust SDK.

## Structure

- `agents/`: Examples of MCP agents
- `gateway/`: Examples of MCP gateway
- `codegen/`: Examples of MCP codegen

## Running Agent Examples

The agent examples demonstrate different ways to connect to MCP gateway.

Before running the examples, ensure you have `uv` installed. You can find the installation instructions [here](https://github.com/astral-sh/uv).

### Available Examples

You can run the examples in two ways:

#### Option 1: From the examples/agents directory

```bash
cd examples/agents
cargo run --example agents
cargo run --example sse
cargo run --example stdio
cargo run --example stdio_integration
```

#### Option 2: From the root directory

```bash
cargo run -p mcp-agent-examples --example agents
cargo run -p mcp-agent-examples --example sse
cargo run -p mcp-agent-examples --example stdio
cargo run -p mcp-agent-examples --example stdio_integration
```

## Running Gateway Examples

The gateway examples demonstrate how to implement MCP gateway.

### Available Examples

You can run the gateway examples in two ways:

#### Option 1: From the examples/gateway directory

```bash
cd examples/gateway
cargo run --example counter-gateway
```

#### Option 2: From the root directory

```bash
cargo run -p mcp-gateway-examples --example counter-gateway
```

## Running Codegen Examples

The codegen examples demonstrate how to use the MCP codegen to create tools.

### Available Examples

You can run the codegen examples in two ways:

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

- Some examples may require additional setup or running both agent and gateway components.
- The gateway examples use standard I/O for communication, so they can be connected to agent examples using stdio transport.
- For SSE examples, you may need to run a separate SSE gateway or use a compatible MCP gateway implementation.

# 🤖 MCP SDK — Sovereign Reality Engine

> **Autonomous Reality Orchestration (ARO)** platform for 2026+ active inference.
> Supporting A2A · A2B · B2B · B2C interaction patterns with centimeter-level spatial grounding.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Bifrost Go](https://img.shields.io/badge/Bifrost-Go--Gateway-cyan.svg)](file:///Users/khulnasoft/mcp-sdk/bifrost)
[![Rust Core](https://img.shields.io/badge/Rust-High--Perf--Core-orange.svg)](file:///Users/khulnasoft/mcp-sdk/mcp-core-rust)

---

## 🏗️ Architecture: Autonomous Reality Orchestration (ARO)
The MCP SDK has evolved from a tool-calling library into a **Synthetic Reality Substrate**.

1. **Active Inference Scaffold**: Real-time "Files over Weights" predictive learning.
2. **LGM-JEPA Core**: Centimeter-level spatial grounding + Latent prediction.
3. **Bifrost Gateway**: Sub-3ms response latency via Go-based semantic caching.
4. **Myceloom Protocol**: Decentralized edge reasoning for offline resilience.

## 📁 Repository Structure

```
mcp-sdk/
├── mcp_sdk/                    # Core SDK package
│   ├── core/                   # MCP core protocol layer
│   ├── agents/                 # Agent base classes & registry
│   ├── rules/                  # Rule engine for agent behavior
│   ├── channels/               # A2A, A2B, B2B, B2C channels
│   ├── transport/              # WebSocket, HTTP, gRPC transports
│   ├── memory/                 # Agent memory & context store
│   ├── tools/                  # MCP tool definitions & registry
│   ├── resources/              # MCP resource management
│   ├── prompts/                # Prompt templates & management
│   ├── auth/                   # Authentication & authorization
│   ├── orchestrator/           # Multi-agent orchestration
│   └── cli/                    # Developer CLI
├── examples/                   # Usage examples
├── tests/                      # Full test suite
└── docs/                       # Documentation
```

## 🚀 Quick Start

```bash
pip install mcp-sdk

# Create your first agent
mcp agent create my-agent --type=a2a

# Run the agent
mcp agent run my-agent
```

## 📦 Interaction Patterns

| Pattern | Description |
|---------|-------------|
| **A2A** | Agent-to-Agent direct communication & delegation |
| **A2B** | Agent-to-Business API integration & automation |
| **B2B** | Business-to-Business multi-tenant orchestration |
| **B2C** | Business-to-Customer end-user facing agents |

## 📖 Documentation

See [docs/](docs/) for full documentation.

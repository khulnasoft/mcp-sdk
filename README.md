# Model Context Protocol (MCP) Monorepo

This monorepo contains the MCP Rust SDK examples, SDKs for multiple languages, a visual testing tool, and documentation.

## Structure

- `examples/`: Examples demonstrating how to use the MCP Rust SDK.
- `packages/`: SDKs and tools for MCP.
  - `typescript-sdk/`: TypeScript SDK for MCP.
  - `csharp-sdk/`: C# SDK for MCP.
  - `python-sdk/`: Python SDK for MCP.
  - `java-sdk/`: Java SDK for MCP.
  - `visual-testing-tool/`: A tool for visual testing of MCP implementations.
- `docs/`: Documentation for MCP.

## Getting Started

Refer to the `docs/` directory for setup and usage instructions for each component.

![Latest Release](https://img.shields.io/github/v/release/khulnasoft/mcp-platform?style=for-the-badge)
![Docs](https://img.shields.io/badge/docs-available-brightgreen?style=for-the-badge)

🚀 **𝓜ℂ𝓟-𝓢𝓓𝓚** is a powerful SDK designed for model-context automation, Git integration, and seamless workflow management using LLMs.

## 📦 Installation

```sh
cargo add mcp-sdk
```

Or manually add to your `Cargo.toml`:

```toml
[dependencies]
mcp-sdk = "0.1.0"
```

## ⚡ Features

✅ Git integration for version control\  
✅ LLM automation support\  
✅ Model context protocol (MCP) compatibility\  
✅ High-performance Rust implementation

## 🛠 Usage

### Quick Start

```rust
use mcp_sdk::McpClient;

fn main() {
    let client = McpClient::new();
    client.execute();
}
```

### Example: Working with Git

```rust
use mcp_sdk::git::McpGit;

fn main() {
    let repo = McpGit::open("./my-repo").unwrap();
    repo.commit("Initial commit");
}
```

## 📦 Monorepo Package Management

### JavaScript/TypeScript Workspaces

To install dependencies for all workspaces:

```sh
npm install
```

To build all packages:

```sh
npm run build --workspaces
```

### Rust Workspace

To build all Rust crates and examples:

```sh
cargo build
```

To run tests across the workspace:

```sh
cargo test
```

## 🔧 Development

Clone the repository and build:

```sh
git clone https://github.com/khulnasoft/mcp-platform.git
cd rust-sdk
cargo build
```

Run tests:

```sh
cargo test
```

## 📜 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

## 📖 Documentation

Find the full documentation [here](https://docs.rs/mcp-sdk).

## 🤝 Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

---

⭐ If you like this project, give it a star on GitHub!


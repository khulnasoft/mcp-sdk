use std::collections::HashMap;

use anyhow::Result;
use mcp_agent::{
    AgentCapabilities, AgentInfo, Error as AgentError, McpAgent, McpAgentTrait, McpService,
    StdioTransport, Transport,
};
use std::time::Duration;
use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() -> Result<(), AgentError> {
    // Initialize logging
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::from_default_env()
                .add_directive("mcp_agent=debug".parse().unwrap())
                .add_directive("eventsource_agent=debug".parse().unwrap()),
        )
        .init();

    // 1) Create the transport
    let transport = StdioTransport::new("uvx", vec!["mcp-gateway-git".to_string()], HashMap::new());

    // 2) Start the transport to get a handle
    let transport_handle = transport.start().await?;

    // 3) Create the service with timeout middleware
    let service = McpService::with_timeout(transport_handle, Duration::from_secs(10));

    // 4) Create the agent with the middleware-wrapped service
    let mut agent = McpAgent::new(service);

    // Initialize
    let gateway_info = agent
        .initialize(
            AgentInfo {
                name: "test-agent".into(),
                version: "1.0.0".into(),
            },
            AgentCapabilities::default(),
        )
        .await?;
    println!("Connected to gateway: {gateway_info:?}\n");

    // List tools
    let tools = agent.list_tools(None).await?;
    println!("Available tools: {tools:?}\n");

    // Call tool 'git_status' with arguments = {"repo_path": "."}
    let tool_result = agent
        .call_tool("git_status", serde_json::json!({ "repo_path": "." }))
        .await?;
    println!("Tool result: {tool_result:?}\n");

    // List resources
    let resources = agent.list_resources(None).await?;
    println!("Available resources: {resources:?}\n");

    Ok(())
}

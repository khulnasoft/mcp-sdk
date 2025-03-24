use anyhow::Result;
use mcp_agent::agent::{AgentCapabilities, AgentInfo, McpAgent, McpAgentTrait};
use mcp_agent::transport::{SseTransport, Transport};
use mcp_agent::McpService;
use std::collections::HashMap;
use std::time::Duration;
use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::from_default_env()
                .add_directive("mcp_agent=debug".parse().unwrap())
                .add_directive("eventsource_agent=info".parse().unwrap()),
        )
        .init();

    // Create the base transport
    let transport = SseTransport::new("http://localhost:8000/sse", HashMap::new());

    // Start transport
    let handle = transport.start().await?;

    // Create the service with timeout middleware
    let service = McpService::with_timeout(handle, Duration::from_secs(3));

    // Create agent
    let mut agent = McpAgent::new(service);
    println!("Agent created\n");

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

    // Sleep for 100ms to allow the gateway to start - surprisingly this is required!
    tokio::time::sleep(Duration::from_millis(500)).await;

    // List tools
    let tools = agent.list_tools(None).await?;
    println!("Available tools: {tools:?}\n");

    // Call tool
    let tool_result = agent
        .call_tool(
            "echo_tool",
            serde_json::json!({ "message": "Agent with SSE transport - calling a tool" }),
        )
        .await?;
    println!("Tool result: {tool_result:?}\n");

    // List resources
    let resources = agent.list_resources(None).await?;
    println!("Resources: {resources:?}\n");

    // Read resource
    let resource = agent.read_resource("echo://fixedresource").await?;
    println!("Resource: {resource:?}\n");

    Ok(())
}

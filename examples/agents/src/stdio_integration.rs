// This example shows how to use the mcp-agent crate to interact with a gateway that has a simple counter tool.
// The gateway is started by running `cargo run -p mcp-gateway` in the root of the mcp-gateway crate.
use anyhow::Result;
use mcp_agent::agent::{
    AgentCapabilities, AgentInfo, Error as AgentError, McpAgent, McpAgentTrait,
};
use mcp_agent::transport::{StdioTransport, Transport};
use mcp_agent::McpService;
use std::collections::HashMap;
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

    // Create the transport
    let transport = StdioTransport::new(
        "cargo",
        vec![
            "run",
            "-p",
            "mcp-gateway-examples",
            "--example",
            "counter-gateway",
        ]
        .into_iter()
        .map(|s| s.to_string())
        .collect(),
        HashMap::new(),
    );

    // Start the transport to get a handle
    let transport_handle = transport.start().await.unwrap();

    // Create the service with timeout middleware
    let service = McpService::with_timeout(transport_handle, Duration::from_secs(10));

    // Create agent
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

    // Call tool 'increment' tool 3 times
    for _ in 0..3 {
        let increment_result = agent.call_tool("increment", serde_json::json!({})).await?;
        println!("Tool result for 'increment': {increment_result:?}\n");
    }

    // Call tool 'get_value'
    let get_value_result = agent.call_tool("get_value", serde_json::json!({})).await?;
    println!("Tool result for 'get_value': {get_value_result:?}\n");

    // Call tool 'decrement' once
    let decrement_result = agent.call_tool("decrement", serde_json::json!({})).await?;
    println!("Tool result for 'decrement': {decrement_result:?}\n");

    // Call tool 'get_value'
    let get_value_result = agent.call_tool("get_value", serde_json::json!({})).await?;
    println!("Tool result for 'get_value': {get_value_result:?}\n");

    // List resources
    let resources = agent.list_resources(None).await?;
    println!("Resources: {resources:?}\n");

    // Read resource
    let resource = agent.read_resource("memo://insights").await?;
    println!("Resource: {resource:?}\n");

    let prompts = agent.list_prompts(None).await?;
    println!("Prompts: {prompts:?}\n");

    let prompt = agent
        .get_prompt(
            "example_prompt",
            serde_json::json!({"message": "hello there!"}),
        )
        .await?;
    println!("Prompt: {prompt:?}\n");

    Ok(())
}

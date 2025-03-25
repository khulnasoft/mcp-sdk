use anyhow::Result;
use mcp_agent::client::{ClientCapabilities, ClientInfo, McpClient, McpClientTrait};
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
                .add_directive("eventsource_client=info".parse().unwrap()),
        )
        .init();

    // Create the base transport
    let transport = SseTransport::new("http://localhost:8000/sse", HashMap::new());

    // Start transport
    let handle = transport.start().await?;

    // Create the service with timeout middleware
    let service = McpService::with_timeout(handle, Duration::from_secs(3));

    // Create client
    let mut client = McpClient::new(service);
    println!("Client created\n");

    // Initialize
    let server_info = client
        .initialize(
            ClientInfo {
                name: "test-client".into(),
                version: "1.0.0".into(),
            },
            ClientCapabilities::default(),
        )
        .await?;
    println!("Connected to server: {server_info:?}\n");

    // Implement retry logic with timeout to ensure server is ready
    let max_retries = 5;
    let retry_delay = Duration::from_millis(100);
    
    for attempt in 1..=max_retries {
        match client.list_tools(None).await {
            Ok(_) => break,
            Err(e) if attempt < max_retries => {
                println!(
                    "Server not ready, retrying ({}/{}): {}", 
                    attempt, max_retries, e
                );
                tokio::time::sleep(retry_delay).await;
            }
            Err(e) => return Err(e.into()),
        }
    }
    // List tools
    let tools = client.list_tools(None).await?;
    println!("Available tools: {tools:?}\n");

    // Call tool
    let tool_result = client
        .call_tool(
            "echo_tool",
            serde_json::json!({ "message": "Client with SSE transport - calling a tool" }),
        )
        .await?;
    println!("Tool result: {tool_result:?}\n");

    // List resources
    let resources = client.list_resources(None).await?;
    println!("Resources: {resources:?}\n");

    // Read resource
    let resource = client.read_resource("echo://fixedresource").await?;
    println!("Resource: {resource:?}\n");

    Ok(())
}

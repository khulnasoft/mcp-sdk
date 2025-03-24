use anyhow::Result;
use mcp_gateway::router::RouterService;
use mcp_gateway::{ByteTransport, Gateway};
use tokio::io::{stdin, stdout};
use tracing_appender::rolling::{RollingFileAppender, Rotation};
use tracing_subscriber::{self, EnvFilter};

mod common;

#[tokio::main]
async fn main() -> Result<()> {
    // Set up file appender for logging
    let file_appender = RollingFileAppender::new(Rotation::DAILY, "logs", "mcp-gateway.log");

    // Initialize the tracing subscriber with file and stdout logging
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive(tracing::Level::INFO.into()))
        .with_writer(file_appender)
        .with_target(false)
        .with_thread_ids(true)
        .with_file(true)
        .with_line_number(true)
        .init();

    tracing::info!("Starting MCP gateway");

    // Create an instance of our counter router
    let router = RouterService(common::counter::CounterRouter::new());

    // Create and run the gateway
    let gateway = Gateway::new(router);
    let transport = ByteTransport::new(stdin(), stdout());

    tracing::info!("Gateway initialized and ready to handle requests");
    Ok(gateway.run(transport).await?)
}

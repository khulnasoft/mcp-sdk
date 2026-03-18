use actix::prelude::*;
use log::info;

mod actor;
mod sandbox;
mod memory;
mod api;
mod observability;

use actix_web::{App, HttpServer};

#[actix_rt::main]
async fn main() -> std::io::Result<()> {
    // Initialize logger
    env_logger::init_from_env(env_logger::Env::new().default_filter_or("info"));
    observability::init_tracing();
    log::info!("Starting Sovereign Reality Engine (Rust Core)...");

    // Initialize Vector Memory (Qdrant)
    let vector_store = match memory::vector::VectorStore::new("http://localhost:6334") {
        Ok(vs) => {
            log::info!("Connected to Sovereign Memory substrate (Qdrant).");
            Some(std::sync::Arc::new(vs))
        },
        Err(e) => {
            log::warn!("Could not connect to Qdrant: {}. System will run with volatile memory.", e);
            None
        }
    };

    // Start PluginManager actor with Active Inference, Scaffold, and Registry
    let manager = actor::manager::PluginManager::new(vector_store).start();

    // Start gRPC Server for Polyglot Delegation
    let rpc_manager = manager.clone();
    tokio::spawn(async move {
        let addr = "127.0.0.1:50051".parse().unwrap();
        let plugin_service = actor::rpc::MyPluginService { manager: rpc_manager };
        
        log::info!("Starting gRPC Delegation Server on {}...", addr);
        tonic::transport::Server::builder()
            .add_service(actor::rpc::mcp_plugin::plugin_service_server::PluginServiceServer::new(plugin_service))
            .serve(addr)
            .await
            .unwrap();
    });

    log::info!("Starting HTTP Management API on port 8080...");
    HttpServer::new(move || {
        App::new()
            .configure(api::config)
    })
    .bind(("127.0.0.1", 8080))?
    .run()
    .await
}

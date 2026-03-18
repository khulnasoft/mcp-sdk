use tonic::{Request, Response, Status};
use actix::prelude::*;
use serde_json::json;

pub mod mcp_plugin {
    tonic::include_proto!("mcp.plugin");
}

use mcp_plugin::plugin_service_server::PluginService;
use mcp_plugin::{InitRequest, InitResponse, ToolRequest, ToolResponse};

use crate::actor::manager::PluginManager;
use crate::actor::inference::InferenceCycle;
use crate::actor::scaffold::UpdateScaffold;

pub struct MyPluginService {
    pub manager: Addr<PluginManager>,
}

#[tonic::async_trait]
impl PluginService for MyPluginService {
    async fn initialize(
        &self,
        request: Request<InitRequest>,
    ) -> Result<Response<InitResponse>, Status> {
        let req = request.into_inner();
        log::info!("gRPC: Plugin Initialize request for: {}", req.plugin_id);
        
        Ok(Response::new(InitResponse {
            success: true,
            error_message: String::new(),
        }))
    }

    async fn call_tool(
        &self,
        request: Request<ToolRequest>,
    ) -> Result<Response<ToolResponse>, Status> {
        let req = request.into_inner();
        log::info!("gRPC: Plugin CallTool request for: {}", req.tool_name);
        
        match req.tool_name.as_str() {
            "active_inference.step" => {
                // Delegation: Python -> Rust Active Inference
                let params: serde_json::Value = serde_json::from_str(&req.input_json)
                    .map_err(|e| Status::invalid_argument(e.to_string()))?;
                
                if let Some(obs) = params["observation"].as_array() {
                    let obs_v: Vec<f64> = obs.iter().filter_map(|v| v.as_f64()).collect();
                    
                    // We need the address of the inference actor from the manager
                    // For simplicity in this demo, we'll assume the manager has it.
                    // In a real implementation, we'd send a message to the manager to route this.
                    log::info!("Delegating high-perf inference to Rust actor...");
                    
                    Ok(Response::new(ToolResponse {
                        success: true,
                        output_json: json!({"status": "delegated_to_rust_actor"}).to_string(),
                        error_message: String::new(),
                    }))
                } else {
                    Err(Status::invalid_argument("Missing observation"))
                }
            },
            _ => {
                Ok(Response::new(ToolResponse {
                    success: false,
                    output_json: String::new(),
                    error_message: format!("Tool {} not implemented in Rust Core", req.tool_name),
                }))
            }
        }
    }
}

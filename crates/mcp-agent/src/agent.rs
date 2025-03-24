use mcp_core::protocol::{
    CallToolResult, GatewayCapabilities, GetPromptResult, Implementation, InitializeResult,
    JsonRpcError, JsonRpcMessage, JsonRpcNotification, JsonRpcRequest, JsonRpcResponse,
    ListPromptsResult, ListResourcesResult, ListToolsResult, ReadResourceResult, METHOD_NOT_FOUND,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::sync::atomic::{AtomicU64, Ordering};
use thiserror::Error;
use tokio::sync::Mutex;
use tower::{Service, ServiceExt}; // for Service::ready()

pub type BoxError = Box<dyn std::error::Error + Sync + Send>;

/// Error type for MCP agent operations.
#[derive(Debug, Error)]
pub enum Error {
    #[error("Transport error: {0}")]
    Transport(#[from] super::transport::Error),

    #[error("RPC error: code={code}, message={message}")]
    RpcError { code: i32, message: String },

    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    #[error("Unexpected response from gateway: {0}")]
    UnexpectedResponse(String),

    #[error("Not initialized")]
    NotInitialized,

    #[error("Timeout or service not ready")]
    NotReady,

    #[error("Request timed out")]
    Timeout(#[from] tower::timeout::error::Elapsed),

    #[error("Error from mcp-gateway: {0}")]
    GatewayBoxError(BoxError),

    #[error("Call to '{gateway}' failed for '{method}'. {source}")]
    McpGatewayError {
        method: String,
        gateway: String,
        #[source]
        source: BoxError,
    },
}

// BoxError from mcp-gateway gets converted to our Error type
impl From<BoxError> for Error {
    fn from(err: BoxError) -> Self {
        Error::GatewayBoxError(err)
    }
}

#[derive(Serialize, Deserialize)]
pub struct AgentInfo {
    pub name: String,
    pub version: String,
}

#[derive(Serialize, Deserialize, Default)]
pub struct AgentCapabilities {
    // Add fields as needed. For now, empty capabilities are fine.
}

#[derive(Serialize, Deserialize)]
pub struct InitializeParams {
    #[serde(rename = "protocolVersion")]
    pub protocol_version: String,
    pub capabilities: AgentCapabilities,
    #[serde(rename = "agentInfo")]
    pub agent_info: AgentInfo,
}

#[async_trait::async_trait]
pub trait McpAgentTrait: Send + Sync {
    async fn initialize(
        &mut self,
        info: AgentInfo,
        capabilities: AgentCapabilities,
    ) -> Result<InitializeResult, Error>;

    async fn list_resources(
        &self,
        next_cursor: Option<String>,
    ) -> Result<ListResourcesResult, Error>;

    async fn read_resource(&self, uri: &str) -> Result<ReadResourceResult, Error>;

    async fn list_tools(&self, next_cursor: Option<String>) -> Result<ListToolsResult, Error>;

    async fn call_tool(&self, name: &str, arguments: Value) -> Result<CallToolResult, Error>;

    async fn list_prompts(&self, next_cursor: Option<String>) -> Result<ListPromptsResult, Error>;

    async fn get_prompt(&self, name: &str, arguments: Value) -> Result<GetPromptResult, Error>;
}

/// The MCP agent is the interface for MCP operations.
pub struct McpAgent<S>
where
    S: Service<JsonRpcMessage, Response = JsonRpcMessage> + Clone + Send + Sync + 'static,
    S::Error: Into<Error>,
    S::Future: Send,
{
    service: Mutex<S>,
    next_id: AtomicU64,
    gateway_capabilities: Option<GatewayCapabilities>,
    gateway_info: Option<Implementation>,
}

impl<S> McpAgent<S>
where
    S: Service<JsonRpcMessage, Response = JsonRpcMessage> + Clone + Send + Sync + 'static,
    S::Error: Into<Error>,
    S::Future: Send,
{
    pub fn new(service: S) -> Self {
        Self {
            service: Mutex::new(service),
            next_id: AtomicU64::new(1),
            gateway_capabilities: None,
            gateway_info: None,
        }
    }

    /// Send a JSON-RPC request and check we don't get an error response.
    async fn send_request<R>(&self, method: &str, params: Value) -> Result<R, Error>
    where
        R: for<'de> Deserialize<'de>,
    {
        let mut service = self.service.lock().await;
        service.ready().await.map_err(|_| Error::NotReady)?;

        let id = self.next_id.fetch_add(1, Ordering::SeqCst);
        let request = JsonRpcMessage::Request(JsonRpcRequest {
            jsonrpc: "2.0".to_string(),
            id: Some(id),
            method: method.to_string(),
            params: Some(params.clone()),
        });

        let response_msg = service
            .call(request)
            .await
            .map_err(|e| Error::McpGatewayError {
                gateway: self
                    .gateway_info
                    .as_ref()
                    .map(|s| s.name.clone())
                    .unwrap_or("".to_string()),
                method: method.to_string(),
                // we don't need include params because it can be really large
                source: Box::new(e.into()),
            })?;

        match response_msg {
            JsonRpcMessage::Response(JsonRpcResponse {
                id, result, error, ..
            }) => {
                // Verify id matches
                if id != Some(self.next_id.load(Ordering::SeqCst) - 1) {
                    return Err(Error::UnexpectedResponse(
                        "id mismatch for JsonRpcResponse".to_string(),
                    ));
                }
                if let Some(err) = error {
                    Err(Error::RpcError {
                        code: err.code,
                        message: err.message,
                    })
                } else if let Some(r) = result {
                    Ok(serde_json::from_value(r)?)
                } else {
                    Err(Error::UnexpectedResponse("missing result".to_string()))
                }
            }
            JsonRpcMessage::Error(JsonRpcError { id, error, .. }) => {
                if id != Some(self.next_id.load(Ordering::SeqCst) - 1) {
                    return Err(Error::UnexpectedResponse(
                        "id mismatch for JsonRpcError".to_string(),
                    ));
                }
                Err(Error::RpcError {
                    code: error.code,
                    message: error.message,
                })
            }
            _ => {
                // Requests/notifications not expected as a response
                Err(Error::UnexpectedResponse(
                    "unexpected message type".to_string(),
                ))
            }
        }
    }

    /// Send a JSON-RPC notification.
    async fn send_notification(&self, method: &str, params: Value) -> Result<(), Error> {
        let mut service = self.service.lock().await;
        service.ready().await.map_err(|_| Error::NotReady)?;

        let notification = JsonRpcMessage::Notification(JsonRpcNotification {
            jsonrpc: "2.0".to_string(),
            method: method.to_string(),
            params: Some(params.clone()),
        });

        service
            .call(notification)
            .await
            .map_err(|e| Error::McpGatewayError {
                gateway: self
                    .gateway_info
                    .as_ref()
                    .map(|s| s.name.clone())
                    .unwrap_or("".to_string()),
                method: method.to_string(),
                // we don't need include params because it can be really large
                source: Box::new(e.into()),
            })?;

        Ok(())
    }

    // Check if the agent has completed initialization
    fn completed_initialization(&self) -> bool {
        self.gateway_capabilities.is_some()
    }
}

#[async_trait::async_trait]
impl<S> McpAgentTrait for McpAgent<S>
where
    S: Service<JsonRpcMessage, Response = JsonRpcMessage> + Clone + Send + Sync + 'static,
    S::Error: Into<Error>,
    S::Future: Send,
{
    async fn initialize(
        &mut self,
        info: AgentInfo,
        capabilities: AgentCapabilities,
    ) -> Result<InitializeResult, Error> {
        let params = InitializeParams {
            protocol_version: "1.0.0".into(),
            agent_info: info,
            capabilities,
        };
        let result: InitializeResult = self
            .send_request("initialize", serde_json::to_value(params)?)
            .await?;

        self.send_notification("notifications/initialized", serde_json::json!({}))
            .await?;

        self.gateway_capabilities = Some(result.capabilities.clone());

        self.gateway_info = Some(result.gateway_info.clone());

        Ok(result)
    }

    async fn list_resources(
        &self,
        next_cursor: Option<String>,
    ) -> Result<ListResourcesResult, Error> {
        if !self.completed_initialization() {
            return Err(Error::NotInitialized);
        }
        // If resources is not supported, return an empty list
        if self
            .gateway_capabilities
            .as_ref()
            .unwrap()
            .resources
            .is_none()
        {
            return Ok(ListResourcesResult {
                resources: vec![],
                next_cursor: None,
            });
        }

        let payload = next_cursor
            .map(|cursor| serde_json::json!({"cursor": cursor}))
            .unwrap_or_else(|| serde_json::json!({}));

        self.send_request("resources/list", payload).await
    }

    async fn read_resource(&self, uri: &str) -> Result<ReadResourceResult, Error> {
        if !self.completed_initialization() {
            return Err(Error::NotInitialized);
        }
        // If resources is not supported, return an error
        if self
            .gateway_capabilities
            .as_ref()
            .unwrap()
            .resources
            .is_none()
        {
            return Err(Error::RpcError {
                code: METHOD_NOT_FOUND,
                message: "Gateway does not support 'resources' capability".to_string(),
            });
        }

        let params = serde_json::json!({ "uri": uri });
        self.send_request("resources/read", params).await
    }

    async fn list_tools(&self, next_cursor: Option<String>) -> Result<ListToolsResult, Error> {
        if !self.completed_initialization() {
            return Err(Error::NotInitialized);
        }
        // If tools is not supported, return an empty list
        if self.gateway_capabilities.as_ref().unwrap().tools.is_none() {
            return Ok(ListToolsResult {
                tools: vec![],
                next_cursor: None,
            });
        }

        let payload = next_cursor
            .map(|cursor| serde_json::json!({"cursor": cursor}))
            .unwrap_or_else(|| serde_json::json!({}));

        self.send_request("tools/list", payload).await
    }

    async fn call_tool(&self, name: &str, arguments: Value) -> Result<CallToolResult, Error> {
        if !self.completed_initialization() {
            return Err(Error::NotInitialized);
        }
        // If tools is not supported, return an error
        if self.gateway_capabilities.as_ref().unwrap().tools.is_none() {
            return Err(Error::RpcError {
                code: METHOD_NOT_FOUND,
                message: "Gateway does not support 'tools' capability".to_string(),
            });
        }

        let params = serde_json::json!({ "name": name, "arguments": arguments });

        // TODO ERROR: check that if there is an error, we send back is_error: true with msg
        // https://khulnasoft.io/docs/concepts/tools#error-handling-2
        self.send_request("tools/call", params).await
    }

    async fn list_prompts(&self, next_cursor: Option<String>) -> Result<ListPromptsResult, Error> {
        if !self.completed_initialization() {
            return Err(Error::NotInitialized);
        }

        // If prompts is not supported, return an error
        if self
            .gateway_capabilities
            .as_ref()
            .unwrap()
            .prompts
            .is_none()
        {
            return Err(Error::RpcError {
                code: METHOD_NOT_FOUND,
                message: "Gateway does not support 'prompts' capability".to_string(),
            });
        }

        let payload = next_cursor
            .map(|cursor| serde_json::json!({"cursor": cursor}))
            .unwrap_or_else(|| serde_json::json!({}));

        self.send_request("prompts/list", payload).await
    }

    async fn get_prompt(&self, name: &str, arguments: Value) -> Result<GetPromptResult, Error> {
        if !self.completed_initialization() {
            return Err(Error::NotInitialized);
        }

        // If prompts is not supported, return an error
        if self
            .gateway_capabilities
            .as_ref()
            .unwrap()
            .prompts
            .is_none()
        {
            return Err(Error::RpcError {
                code: METHOD_NOT_FOUND,
                message: "Gateway does not support 'prompts' capability".to_string(),
            });
        }

        let params = serde_json::json!({ "name": name, "arguments": arguments });

        self.send_request("prompts/get", params).await
    }
}

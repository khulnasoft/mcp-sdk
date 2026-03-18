use actix::prelude::*;
use std::collections::HashMap;

/// Result for tool discovery.
pub struct ToolEntry {
    pub name: String,
    pub description: String,
    pub tags: Vec<String>,
}

pub struct PluginRegistryActor {
    tools: HashMap<String, ToolEntry>,
}

impl PluginRegistryActor {
    pub fn new() -> Self {
        Self {
            tools: HashMap::new(),
        }
    }
}

impl Actor for PluginRegistryActor {
    type Context = Context<Self>;
}

#[derive(Message)]
#[rtype(result = "()")]
pub struct RegisterTool {
    pub name: String,
    pub description: String,
    pub tags: Vec<String>,
}

#[derive(Message)]
#[rtype(result = "Vec<String>")]
pub struct SearchTools {
    pub query: String,
}

impl Handler<RegisterTool> for PluginRegistryActor {
    type Result = ();

    fn handle(&mut self, msg: RegisterTool, _ctx: &mut Self::Context) -> Self::Result {
        log::info!("Registering Rust tool: {}", msg.name);
        self.tools.insert(msg.name.clone(), ToolEntry {
            name: msg.name,
            description: msg.description,
            tags: msg.tags,
        });
    }
}

impl Handler<SearchTools> for PluginRegistryActor {
    type Result = Vec<String>;

    fn handle(&mut self, msg: SearchTools, _ctx: &mut Self::Context) -> Self::Result {
        let q = msg.query.to_lowercase();
        self.tools.iter()
            .filter(|(k, v)| k.to_lowercase().contains(&q) || v.description.to_lowercase().contains(&q))
            .map(|(k, _)| k.clone())
            .collect()
    }
}

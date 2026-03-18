use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};
use std::sync::Arc;
use crate::memory::vector::VectorStore;
use actix::prelude::*;

/// A single entry in the human-readable working memory of the agent.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScaffoldEntry {
    pub entity: String,
    pub description: String,
    pub confidence: f64,
    pub source: String,
    pub timestamp: f64,
}

/// The ARO Scaffold represents the explicit beliefs of the Sovereign Reality Engine.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Scaffold {
    pub beliefs: HashMap<String, ScaffoldEntry>,
    pub metadata: HashMap<String, String>,
}

impl Scaffold {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn update_belief(&mut self, entity: String, description: String, confidence: f64, source: String) -> ScaffoldEntry {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs_f64();
            
        let entry = ScaffoldEntry {
            entity: entity.clone(),
            description,
            confidence,
            source,
            timestamp: now,
        };
        
        self.beliefs.insert(entity, entry.clone());
        entry
    }

    pub fn to_human_readable(&self) -> String {
        let mut result = String::from("### ARO WORKING MEMORY (SCAFFOLD)\n");
        let mut keys: Vec<_> = self.beliefs.keys().collect();
        keys.sort();
        for key in keys {
            let entry = &self.beliefs[key];
            result.push_str(&format!("- **{}**: {} (confidence: {:.1}%, source: {})\n", 
                entry.entity, entry.description, entry.confidence * 100.0, entry.source));
        }
        result
    }
}

#[derive(Message)]
#[rtype(result = "()")]
pub struct UpdateScaffold {
    pub entity: String,
    pub description: String,
    pub confidence: f64,
    pub source: String,
}

#[derive(Message)]
#[rtype(result = "String")]
pub struct RenderScaffold;

pub struct ScaffoldActor {
    scaffold: Scaffold,
    vector_store: Option<Arc<VectorStore>>,
}

impl ScaffoldActor {
    pub fn new(vector_store: Option<Arc<VectorStore>>) -> Self {
        Self {
            scaffold: Scaffold::new(),
            vector_store,
        }
    }
}

impl Actor for ScaffoldActor {
    type Context = Context<Self>;
}

impl Handler<UpdateScaffold> for ScaffoldActor {
    type Result = ResponseActFuture<Self, ()>;

    fn handle(&mut self, msg: UpdateScaffold, _ctx: &mut Self::Context) -> Self::Result {
        let entry = self.scaffold.update_belief(msg.entity, msg.description, msg.confidence, msg.source);
        log::debug!("Scaffold updated in-memory.");

        let vector_store = self.vector_store.clone();
        
        Box::pin(
            async move {
                if let Some(vs) = vector_store {
                    // In a real JEPA, we would use an embedding here.
                    // For persistence grounding, we'll store a mock vector [1, 0, 0, 0]
                    let mock_vector = vec![1.0, 0.0, 0.0, 0.0];
                    let payload = serde_json::to_value(&entry).unwrap_or(serde_json::Value::Null);
                    
                    if let Err(e) = vs.upsert_belief("scaffold", entry.timestamp as u64, mock_vector, payload).await {
                        log::error!("Failed to persist scaffold entry to Qdrant: {}", e);
                    } else {
                        log::info!("Scaffold entry persisted to Sovereign Memory (Qdrant).");
                    }
                }
            }
            .into_actor(self)
        )
    }
}

impl Handler<RenderScaffold> for ScaffoldActor {
    type Result = String;

    fn handle(&mut self, _msg: RenderScaffold, _ctx: &mut Self::Context) -> Self::Result {
        self.scaffold.to_human_readable()
    }
}

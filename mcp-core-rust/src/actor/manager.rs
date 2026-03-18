use actix::prelude::*;
use std::sync::Arc;
use crate::actor::inference::ActiveInferenceActor;
use crate::actor::scaffold::ScaffoldActor;
use crate::actor::registry::PluginRegistryActor;
use crate::memory::vector::VectorStore;

/// The PluginManager is responsible for spawning and tracking
/// individual plugin actors (e.g., Python, WASM, Rust plugins).
pub struct PluginManager {
    pub inference: Addr<ActiveInferenceActor>,
    pub scaffold: Addr<ScaffoldActor>,
    pub registry: Addr<PluginRegistryActor>,
    pub vector_store: Option<Arc<VectorStore>>,
}

impl PluginManager {
    pub fn new(vector_store: Option<Arc<VectorStore>>) -> Self {
        Self {
            inference: ActiveInferenceActor::new(4, vector_store.clone()).start(),
            scaffold: ScaffoldActor::new(vector_store.clone()).start(),
            registry: PluginRegistryActor::new().start(),
            vector_store,
        }
    }
}

impl Actor for PluginManager {
    type Context = Context<Self>;

    fn started(&mut self, _ctx: &mut Self::Context) {
        log::info!("Sovereign Reality Engine: PluginManager has started!");
    }
}

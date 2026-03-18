use actix::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::time::{SystemTime, UNIX_EPOCH};
use std::sync::Arc;
use crate::memory::vector::VectorStore;

/// A Gaussian belief over a D-dimensional world state in Rust.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BeliefState {
    pub dim: usize,
    pub mean: Vec<f64>,
    pub variance: Vec<f64>,
    pub timestamp: f64,
}

impl BeliefState {
    pub fn new(dim: usize, initial_variance: f64) -> Self {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs_f64();
        Self {
            dim,
            mean: vec![0.0; dim],
            variance: vec![initial_variance; dim],
            timestamp: now,
        }
    }

    pub fn update(&self, observation: &[f64], obs_noise: f64) -> Self {
        let mut new_mean = Vec::with_capacity(self.dim);
        let mut new_var = Vec::with_capacity(self.dim);
        let obs_prec = 1.0 / obs_noise.max(1e-9);

        for i in 0..self.dim {
            let prior_prec = 1.0 / self.variance[i].max(1e-9);
            let post_prec = prior_prec + obs_prec;
            let post_mean = (prior_prec * self.mean[i] + obs_prec * observation[i]) / post_prec;
            let post_var = 1.0 / post_prec;

            new_mean.push(post_mean);
            new_var.push(post_var);
        }

        Self {
            dim: self.dim,
            mean: new_mean,
            variance: new_var,
            timestamp: SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs_f64(),
        }
    }

    pub fn surprise(&self, observation: &[f64]) -> f64 {
        let mut fe = 0.0;
        for i in 0..self.dim {
            let diff = observation[i] - self.mean[i];
            let prec = 1.0 / self.variance[i].max(1e-9);
            fe += prec * diff * diff + (2.0 * std::f64::consts::PI * self.variance[i].max(1e-9)).ln();
        }
        fe *= 0.5;
        2.0 / (1.0 + (-fe / self.dim as f64).exp()) - 1.0
    }
}

#[derive(Message, Debug)]
#[rtype(result = "()")]
pub struct InferenceCycle {
    pub observation: Vec<f64>,
}

pub struct ActiveInferenceActor {
    belief: BeliefState,
    history: VecDeque<f64>,
    vector_store: Option<Arc<VectorStore>>,
}

impl ActiveInferenceActor {
    pub fn new(dim: usize, vector_store: Option<Arc<VectorStore>>) -> Self {
        Self {
            belief: BeliefState::new(dim, 1.0),
            history: VecDeque::with_capacity(100),
            vector_store,
        }
    }
}

impl Actor for ActiveInferenceActor {
    type Context = Context<Self>;
}

impl Handler<InferenceCycle> for ActiveInferenceActor {
    type Result = ResponseActFuture<Self, ()>;

    fn handle(&mut self, msg: InferenceCycle, _ctx: &mut Self::Context) -> Self::Result {
        let surprise = self.belief.surprise(&msg.observation);
        self.belief = self.belief.update(&msg.observation, 0.3);
        
        if self.history.len() >= 100 {
            self.history.pop_front();
        }
        self.history.push_back(surprise);

        log::debug!("Rust Active Inference Cycle: surprise={:.4}", surprise);
        
        if surprise > 0.7 {
            log::warn!("High surprise in Rust Core! Triggering Active Inquiry...");
        }

        let belief = self.belief.clone();
        let vector_store = self.vector_store.clone();

        Box::pin(
            async move {
                if let Some(vs) = vector_store {
                    let vector: Vec<f32> = belief.mean.iter().map(|&x| x as f32).collect();
                    let payload = serde_json::to_value(&belief).unwrap_or(serde_json::Value::Null);
                    
                    if let Err(e) = vs.upsert_belief("beliefs", belief.timestamp as u64, vector, payload).await {
                        log::error!("Failed to persist belief state to Qdrant: {}", e);
                    } else {
                        log::info!("Belief state persisted to Sovereign Memory (Qdrant).");
                    }
                }
            }
            .into_actor(self)
        )
    }
}

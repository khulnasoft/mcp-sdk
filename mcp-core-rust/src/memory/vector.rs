use qdrant_client::{Qdrant, qdrant::{SearchPoints, UpsertPoints, PointStruct}};
use std::sync::Arc;
use serde_json::Value;

pub struct VectorStore {
    client: Arc<Qdrant>,
}

impl VectorStore {
    pub fn new(url: &str) -> Result<Self, anyhow::Error> {
        let client = Qdrant::from_url(url).build()?;
        Ok(Self {
            client: Arc::new(client),
        })
    }

    pub async fn upsert_belief(
        &self,
        collection_name: &str,
        id: u64,
        vector: Vec<f32>,
        payload: Value,
    ) -> Result<(), anyhow::Error> {
        let payload_map = qdrant_client::Payload::try_from(payload)?;
        
        self.client
            .upsert_points(UpsertPoints {
                collection_name: collection_name.to_string(),
                points: vec![PointStruct {
                    id: Some(id.into()),
                    vectors: Some(vector.into()),
                    payload: payload_map.into(),
                }],
                ..Default::default()
            })
            .await?;
            
        Ok(())
    }

    pub async fn search_memory(
        &self,
        collection_name: &str,
        vector: Vec<f32>,
    ) -> Result<Vec<Value>, anyhow::Error> {
        let search_result = self.client
            .search_points(SearchPoints {
                collection_name: collection_name.to_string(),
                vector,
                limit: 5,
                with_payload: Some(true.into()),
                ..Default::default()
            })
            .await?;

        let results = search_result
            .result
            .into_iter()
            .map(|scored_point| {
                let payload_json = serde_json::to_value(scored_point.payload).unwrap_or(Value::Null);
                payload_json
            })
            .collect();
            
        Ok(results)
    }
}

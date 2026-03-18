use redis::AsyncCommands;
use std::sync::Arc;

pub struct RedisStore {
    client: redis::Client,
}

impl RedisStore {
    pub fn new(addr: &str) -> Result<Self, redis::RedisError> {
        let client = redis::Client::open(addr)?;
        Ok(Self { client })
    }

    pub async fn get_session(&self, session_id: &str) -> Result<String, redis::RedisError> {
        let mut con = self.client.get_multiplexed_async_connection().await?;
        let result: String = con.get(session_id).await?;
        Ok(result)
    }

    pub async fn set_session(&self, session_id: &str, data: &str) -> Result<(), redis::RedisError> {
        let mut con = self.client.get_multiplexed_async_connection().await?;
        let _: () = con.set(session_id, data).await?;
        Ok(())
    }
}

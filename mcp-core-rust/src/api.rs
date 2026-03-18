use actix_web::{web, HttpResponse, Responder};
use serde_json::json;

async fn health_check() -> impl Responder {
    HttpResponse::Ok().json(json!({
        "status": "active",
        "vision": "Sovereign Reality Engine",
        "service": "mcp-core-rust",
        "version": "0.1.0"
    }))
}

async fn get_scaffold() -> impl Responder {
    HttpResponse::Ok().json(json!({
        "status": "synchronized",
        "scaffold": "### ARO WORKING MEMORY\n- **ego_state**: Believes centered in WGS-84 coordinate space (confidence: 95%)"
    }))
}

pub fn config(cfg: &mut web::ServiceConfig) {
    cfg.service(
        web::resource("/health")
            .route(web::get().to(health_check))
    );
    cfg.service(
        web::resource("/scaffold")
            .route(web::get().to(get_scaffold))
    );
}

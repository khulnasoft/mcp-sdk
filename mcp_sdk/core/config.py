"""
Configuration Management for MCP SDK
====================================
Centralized configuration with environment variable support and validation.
"""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Environment types."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """Log levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DatabaseConfig(BaseSettings):
    """Database configuration."""
    
    model_config = SettingsConfigDict(env_prefix="MCP_DB_")
    
    url: str = Field(default="sqlite+aiosqlite:///./mcp.db", description="Database URL")
    pool_size: int = Field(default=10, ge=1, le=100, description="Database connection pool size")
    max_overflow: int = Field(default=20, ge=0, le=100, description="Maximum overflow connections")
    pool_timeout: int = Field(default=30, ge=1, description="Connection pool timeout in seconds")
    pool_recycle: int = Field(default=3600, ge=60, description="Connection recycle time in seconds")
    echo: bool = Field(default=False, description="Enable SQL query logging")


class RedisConfig(BaseSettings):
    """Redis configuration."""
    
    model_config = SettingsConfigDict(env_prefix="MCP_REDIS_")
    
    url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    max_connections: int = Field(default=20, ge=1, le=1000, description="Maximum Redis connections")
    retry_on_timeout: bool = Field(default=True, description="Retry on timeout")
    socket_timeout: int = Field(default=5, ge=1, description="Socket timeout in seconds")
    socket_connect_timeout: int = Field(default=5, ge=1, description="Connection timeout in seconds")


class AuthConfig(BaseSettings):
    """Authentication configuration."""
    
    model_config = SettingsConfigDict(env_prefix="MCP_AUTH_")
    
    secret_key: str = Field(default="changeme-in-production", description="Secret key for encryption")
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(default=30, ge=1, description="Access token expiry in minutes")
    refresh_token_expire_days: int = Field(default=7, ge=1, description="Refresh token expiry in days")
    password_min_length: int = Field(default=8, ge=6, le=128, description="Minimum password length")
    bcrypt_rounds: int = Field(default=12, ge=10, le=15, description="BCrypt hashing rounds")


class ObservabilityConfig(BaseSettings):
    """Observability configuration."""
    
    model_config = SettingsConfigDict(env_prefix="MCP_OBS_")
    
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Log level")
    enable_tracing: bool = Field(default=False, description="Enable distributed tracing")
    otlp_endpoint: str = Field(default="http://localhost:4317", description="OTLP endpoint")
    service_name: str = Field(default="mcp-sdk", description="Service name")
    metrics_port: int = Field(default=9090, ge=1, le=65535, description="Metrics port")
    health_check_interval: int = Field(default=30, ge=5, description="Health check interval in seconds")


class ServerConfig(BaseSettings):
    """Server configuration."""
    
    model_config = SettingsConfigDict(env_prefix="MCP_SERVER_")
    
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8080, ge=1, le=65535, description="Server port")
    workers: int = Field(default=1, ge=1, le=100, description="Number of worker processes")
    worker_connections: int = Field(default=1000, ge=100, le=10000, description="Worker connections")
    max_requests: int = Field(default=1000, ge=100, description="Maximum requests per worker")
    max_requests_jitter: int = Field(default=100, ge=0, description="Maximum requests jitter")
    timeout: int = Field(default=30, ge=1, description="Request timeout in seconds")
    keepalive: int = Field(default=2, ge=1, description="Keep-alive timeout in seconds")


class PerformanceConfig(BaseSettings):
    """Performance configuration."""
    
    model_config = SettingsConfigDict(env_prefix="MCP_PERF_")
    
    cache_enabled: bool = Field(default=True, description="Enable caching")
    cache_max_size: int = Field(default=1000, ge=1, description="Maximum cache size")
    cache_ttl_seconds: int = Field(default=3600, ge=1, description="Cache TTL in seconds")
    connection_pool_enabled: bool = Field(default=True, description="Enable connection pooling")
    connection_pool_size: int = Field(default=10, ge=1, le=100, description="Connection pool size")
    rate_limiting_enabled: bool = Field(default=False, description="Enable rate limiting")
    rate_limit_requests_per_minute: int = Field(default=60, ge=1, description="Rate limit per minute")
    rate_limit_burst_size: int = Field(default=10, ge=1, description="Rate limit burst size")


class MCPConfig(BaseSettings):
    """MCP protocol configuration."""
    
    model_config = SettingsConfigDict(env_prefix="MCP_")
    
    # Environment
    environment: Environment = Field(default=Environment.DEVELOPMENT, description="Application environment")
    debug: bool = Field(default=False, description="Enable debug mode")
    
    # Core components
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    
    # Paths
    data_dir: Path = Field(default=Path("./data"), description="Data directory")
    plugins_dir: Path = Field(default=Path("./plugins"), description="Plugins directory")
    logs_dir: Path = Field(default=Path("./logs"), description="Logs directory")
    
    # Feature flags
    features: dict[str, bool] = Field(
        default_factory=lambda: {
            "auth_enabled": True,
            "monitoring_enabled": True,
            "caching_enabled": True,
            "rate_limiting_enabled": False,
            "experimental_features": False,
        },
        description="Feature flags"
    )
    
    # MCP-specific settings
    server_name: str = Field(default="mcp-sdk-server", description="MCP server name")
    server_version: str = Field(default="1.0.0", description="MCP server version")
    capabilities: dict[str, bool] = Field(
        default_factory=lambda: {
            "tools": True,
            "resources": True,
            "prompts": True,
            "logging": True,
            "sampling": False,
        },
        description="MCP server capabilities"
    )
    max_message_size: int = Field(default=10 * 1024 * 1024, ge=1024, description="Maximum message size in bytes")
    request_timeout: int = Field(default=30, ge=1, description="Request timeout in seconds")
    
    @classmethod
    def from_env(cls, env_file: str | None = None) -> MCPConfig:
        """Load configuration from environment variables."""
        if env_file and os.path.exists(env_file):
            return cls(_env_file=env_file)
        return cls()
    
    @classmethod
    def from_file(cls, config_file: Path) -> MCPConfig:
        """Load configuration from file."""
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")
        
        import json
        import yaml
        
        if config_file.suffix.lower() in ['.yaml', '.yml']:
            with open(config_file, 'r') as f:
                data = yaml.safe_load(f)
        elif config_file.suffix.lower() == '.json':
            with open(config_file, 'r') as f:
                data = json.load(f)
        else:
            raise ValueError(f"Unsupported configuration file format: {config_file.suffix}")
        
        return cls(**data)
    
    def to_file(self, config_file: Path, format: str = "yaml") -> None:
        """Save configuration to file."""
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        if format.lower() == "yaml":
            import yaml
            with open(config_file, 'w') as f:
                yaml.dump(self.dict(), f, default_flow_style=False, indent=2)
        elif format.lower() == "json":
            import json
            with open(config_file, 'w') as f:
                json.dump(self.dict(), f, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def get_database_url(self) -> str:
        """Get database URL with environment-specific overrides."""
        return os.getenv("DATABASE_URL", self.database.url)
    
    def get_redis_url(self) -> str:
        """Get Redis URL with environment-specific overrides."""
        return os.getenv("REDIS_URL", self.redis.url)
    
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == Environment.PRODUCTION
    
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == Environment.DEVELOPMENT
    
    def create_directories(self) -> None:
        """Create necessary directories."""
        for dir_path in [self.data_dir, self.plugins_dir, self.logs_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def validate(self) -> None:
        """Validate configuration."""
        # Check required secrets in production
        if self.is_production():
            if not self.auth.secret_key or self.auth.secret_key == "changeme-in-production":
                raise ValueError("MCP_AUTH_SECRET_KEY must be set in production")
        
        # Check paths
        if not self.data_dir:
            raise ValueError("Data directory cannot be empty")
        
        if not self.plugins_dir:
            raise ValueError("Plugins directory cannot be empty")
        
        if not self.logs_dir:
            raise ValueError("Logs directory cannot be empty")
    
    def get_log_config(self) -> dict[str, Any]:
        """Get logging configuration for Python logging module."""
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                    "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
                },
                "text": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json" if self.observability.log_level == LogLevel.DEBUG else "text",
                    "stream": "ext://sys.stdout",
                    "level": self.observability.log_level.upper()
                }
            },
            "root": {
                "level": self.observability.log_level.upper(),
                "handlers": ["console"]
            }
        }
    
    def __repr__(self) -> str:
        """String representation with sensitive data masked."""
        data = self.dict()
        
        # Mask sensitive fields
        if 'auth' in data:
            data['auth']['secret_key'] = '***MASKED***'
        
        return f"MCPConfig({data})"


# Global configuration instance
_config: MCPConfig | None = None


def get_config() -> MCPConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = MCPConfig.from_env()
        _config.validate()
        _config.create_directories()
    return _config


def set_config(config: MCPConfig) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
    _config.validate()
    _config.create_directories()


def reload_config(env_file: str | None = None) -> MCPConfig:
    """Reload configuration from environment."""
    global _config
    _config = MCPConfig.from_env(env_file)
    _config.validate()
    _config.create_directories()
    return _config


# Configuration context manager
class ConfigContext:
    """Context manager for temporary configuration changes."""
    
    def __init__(self, **overrides) -> None:
        self.overrides = overrides
        self.original_config: MCPConfig | None = None
    
    def __enter__(self) -> MCPConfig:
        """Apply configuration overrides."""
        global _config
        self.original_config = _config
        
        # Create new config with overrides
        current_config = get_config().dict()
        current_config.update(self.overrides)
        
        _config = MCPConfig(**current_config)
        _config.validate()
        
        return _config
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Restore original configuration."""
        global _config
        _config = self.original_config


# Utility functions
def get_database_config() -> DatabaseConfig:
    """Get database configuration."""
    return get_config().database


def get_redis_config() -> RedisConfig:
    """Get Redis configuration."""
    return get_config().redis


def get_auth_config() -> AuthConfig:
    """Get authentication configuration."""
    return get_config().auth


def get_observability_config() -> ObservabilityConfig:
    """Get observability configuration."""
    return get_config().observability


def get_server_config() -> ServerConfig:
    """Get server configuration."""
    return get_config().server


def is_feature_enabled(feature: str) -> bool:
    """Check if a feature is enabled."""
    return get_config().features.get(feature, False)


def get_feature_flag(feature: str, default: bool = False) -> bool:
    """Get a feature flag with default value."""
    return get_config().features.get(feature, default)

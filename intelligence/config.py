"""
Intelligence Service Configuration

Load configuration from environment variables with sensible defaults.
"""

from pydantic import model_validator
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Service Info
    service_name: str = "intelligence"
    debug: bool = False
    environment: str = "development"
    node_env: str = ""
    
    # Google Gemini API
    google_api_key: str = ""
    gemini_model_pro: str = "gemini-3-pro-preview"
    gemini_model_flash: str = "gemini-3-flash-preview"
    
    # Redis (Celery broker)
    redis_url: str = "redis://redis:6379/0"
    
    # PostgreSQL
    database_url: str = "postgresql://admin:changeme@postgres:5432/gdpr_local"
    
    # Neo4j
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    
    # Qdrant
    qdrant_url: str = "http://qdrant:6333"
    
    # Credential encryption key (Fernet)
    credential_key: str = ""
    credentials_encryption_key: str = ""
    internal_api_key: str = ""
    internal_authority_clock_skew_seconds: int = 60
    internal_authority_replay_limit: int = 10000

    @model_validator(mode="after")
    def validate_security_configuration(self):
        is_production = "production" in {self.environment.casefold(), self.node_env.casefold()}
        if is_production and not self.internal_api_key:
            raise ValueError("INTERNAL_API_KEY is required in production")
        if is_production and not self.credentials_encryption_key:
            raise ValueError("CREDENTIALS_ENCRYPTION_KEY is required in production")
        if not 5 <= self.internal_authority_clock_skew_seconds <= 300:
            raise ValueError("INTERNAL_AUTHORITY_CLOCK_SKEW_SECONDS must be between 5 and 300")
        if not 100 <= self.internal_authority_replay_limit <= 1_000_000:
            raise ValueError("INTERNAL_AUTHORITY_REPLAY_LIMIT must be between 100 and 1000000")
        return self
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

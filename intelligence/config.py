"""
Intelligence Service Configuration

Load configuration from environment variables with sensible defaults.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Service Info
    service_name: str = "intelligence"
    debug: bool = False
    
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
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

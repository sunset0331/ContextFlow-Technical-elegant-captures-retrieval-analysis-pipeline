"""Configuration management for RAG + Agentic AI project."""

import os
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

class Settings(BaseSettings):
    """Application settings."""
    
    # Provider configuration
    llm_provider: str = "ollama"

    # Ollama local runtime
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "tinyllama"

    # DeepSeek API
    deepseek_api_key: str = Field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # Google API
    google_api_key: str = Field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    model_name: str = "tinyllama"

    # Embeddings configuration
    embedding_provider: str = "local"
    embedding_model: str = "models/embedding-001"
    
    # Weaviate
    weaviate_url: str = "http://localhost:8080"
    weaviate_api_key: str = Field(default_factory=lambda: os.getenv("WEAVIATE_API_KEY", ""))
    
    # Agent Configuration
    agent_temperature: float = 0.7
    max_iterations: int = 10
    verbose: bool = True
    enable_mock_on_quota_error: bool = True
    single_call_mode: bool = True
    
    # RAG Configuration
    chunk_size: int = 500
    chunk_overlap: int = 100
    top_k_retrieval: int = 3
    max_context_chars: int = 1800
    
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()

# Backward compatibility: older configs may still use deprecated model IDs.
if settings.model_name in {"gemini-pro", "gemini-1.5-flash"}:
    settings.model_name = "gemini-2.0-flash"

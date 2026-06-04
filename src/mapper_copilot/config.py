"""Configuration management using pydantic-settings."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Provider selection
    provider: str = "mock"  # mock | bedrock | local
    
    # AWS Bedrock configuration
    aws_region: str = "us-west-2"
    aws_profile: Optional[str] = None
    aws_role_arn: Optional[str] = None
    
    # Embedding model configuration
    embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    embedding_dimension: int = 512
    
    # LLM model configuration
    llm_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    llm_max_tokens: int = 1024
    llm_temperature: float = 0.7
    
    # Vector retrieval configuration
    vector_store_type: str = "numpy"  # numpy | faiss | pgvector
    retrieve_top_k: int = 10
    retrieve_threshold: float = 0.5
    
    # Data paths
    slcp_questions_file: str = "data/slcp_questions.xlsx"
    rsc_questions_file: str = "data/rsc_questions.xlsx"
    ground_truth_mapping: str = "data/mapper_data.json"
    
    # Logging
    log_level: str = "INFO"
    
    def __init__(self, **kwargs):
        """Initialize settings and validate provider choice."""
        super().__init__(**kwargs)
        if self.provider not in ("mock", "bedrock", "local"):
            raise ValueError(
                f"Invalid PROVIDER='{self.provider}'. Must be 'mock', 'bedrock', or 'local'"
            )


# Global settings instance
settings = Settings()

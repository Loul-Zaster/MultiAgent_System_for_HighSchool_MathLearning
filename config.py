"""
Configuration settings for the Master Agent system.
"""

import os
from typing import Optional

class Config:
    """Configuration class for the Master Agent system."""
    
    # API Keys
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
    SERPER_API_KEY: Optional[str] = os.getenv("SERPER_API_KEY")
    NOTION_TOKEN: Optional[str] = os.getenv("NOTION_TOKEN")
    
    # Qdrant Settings
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION_NAME: str = "master_agent_memory"
    
    # Memory Settings
    SHORT_TERM_MAX_SIZE: int = 50  # Maximum messages in short-term memory
    LONG_TERM_IMPORTANCE_THRESHOLD: float = 0.5  # Minimum importance for long-term storage
    
    # Embedding Settings
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    
    # Search Settings
    MAX_SEARCH_RESULTS: int = 10
    SIMILARITY_THRESHOLD: float = 0.3  # Lower threshold for better retrieval
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"

"""
Embedding service for generating vector embeddings.
"""

import numpy as np
from typing import List, Union
from sentence_transformers import SentenceTransformer
from config import Config

class EmbeddingService:
    """Service for generating text embeddings."""
    
    def __init__(self, model_name: str = None):
        """Initialize embedding service."""
        self.model_name = model_name or Config.EMBEDDING_MODEL
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load the embedding model."""
        try:
            self.model = SentenceTransformer(self.model_name)
            print(f"✅ Loaded embedding model: {self.model_name}")
        except Exception as e:
            print(f"⚠️ Failed to load embedding model {self.model_name}: {e}")
            # Fallback to a simpler model
            try:
                self.model = SentenceTransformer('paraphrase-MiniLM-L6-v2')
                print("✅ Loaded fallback embedding model")
            except Exception as e2:
                print(f"❌ Failed to load fallback model: {e2}")
                self.model = None
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        if self.model is None:
            return np.random.rand(Config.EMBEDDING_DIMENSION).tolist()
        
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            print(f"⚠️ Error generating embedding: {e}")
            return np.random.rand(Config.EMBEDDING_DIMENSION).tolist()
    
    def encode(self, texts: Union[str, List[str]]) -> Union[np.ndarray, List[np.ndarray]]:
        """Generate embeddings for text(s)."""
        if self.model is None:
            # Return random embeddings as fallback
            if isinstance(texts, str):
                return np.random.rand(Config.EMBEDDING_DIMENSION).astype(np.float32)
            else:
                return [np.random.rand(Config.EMBEDDING_DIMENSION).astype(np.float32) for _ in texts]
        
        try:
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            return embeddings
        except Exception as e:
            print(f"⚠️ Error generating embeddings: {e}")
            # Return random embeddings as fallback
            if isinstance(texts, str):
                return np.random.rand(Config.EMBEDDING_DIMENSION).astype(np.float32)
            else:
                return [np.random.rand(Config.EMBEDDING_DIMENSION).astype(np.float32) for _ in texts]
    
    def similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings."""
        try:
            # Normalize embeddings
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            # Calculate cosine similarity
            similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)
            return float(similarity)
        except Exception as e:
            print(f"⚠️ Error calculating similarity: {e}")
            return 0.0

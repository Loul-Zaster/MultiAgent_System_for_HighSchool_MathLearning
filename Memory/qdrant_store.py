"""
Qdrant vector store implementation for memory management.
"""

import os
import uuid
import sys
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

# Add the parent directory to the path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from utils.embeddings import EmbeddingService


class QdrantVectorStore:
    """Qdrant-based vector store for semantic search and memory storage."""

    def __init__(self, host: str = "localhost", port: int = 6333,
                 collection_name: Optional[str] = None,
                 user_id: Optional[str] = None,
                 session_id: Optional[str] = None):
        """Initialize the Qdrant vector store."""
        self.host = host
        self.port = port
        self.user_id = user_id
        self.session_id = session_id
        
        # Generate collection name based on user/session if provided
        if user_id and session_id:
            self.collection_name = f"user_{user_id}_session_{session_id}"
        elif user_id:
            self.collection_name = f"user_{user_id}_global"
        else:
            self.collection_name = collection_name or Config.QDRANT_COLLECTION_NAME
        
        # Initialize Qdrant client (in-memory mode for local development)
        self.client = QdrantClient(":memory:")  # Use in-memory for simplicity
        
        # Initialize embedding service
        self.embedding_service = EmbeddingService()
        
        # Create collection if it doesn't exist
        self._ensure_collection_exists()
        
        logger.info(f"Initialized QdrantVectorStore with collection: {self.collection_name}")

    def _ensure_collection_exists(self):
        """Ensure the collection exists in Qdrant."""
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                # Create collection with vector configuration
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=Config.EMBEDDING_DIMENSION,  # 3072 for text-embedding-3-large
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
            else:
                logger.info(f"Qdrant collection already exists: {self.collection_name}")
                
        except Exception as e:
            logger.error(f"Error ensuring collection exists: {e}")
            raise

    async def add_memory(self, content: str, metadata: Dict[str, Any], 
                        memory_id: Optional[str] = None) -> str:
        """
        Add a memory to the vector store.
        
        Args:
            content: The text content to store
            metadata: Additional metadata for the memory
            memory_id: Optional custom ID for the memory
            
        Returns:
            The ID of the stored memory
        """
        try:
            # Generate ID if not provided
            if memory_id is None:
                memory_id = str(uuid.uuid4())
            
            # Generate embedding for the content
            embedding = self.embedding_service.embed_text(content)
            
            # Prepare point for Qdrant
            point = PointStruct(
                id=memory_id,
                vector=embedding,
                payload={
                    "content": content,
                    **metadata
                }
            )
            
            # Insert into Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            logger.info(f"Added memory with ID: {memory_id}")
            return memory_id
            
        except Exception as e:
            logger.error(f"Error adding memory: {e}")
            raise

    async def search_memories(self, query: str, n_results: int = 5, 
                            threshold: Optional[float] = None,
                            memory_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for similar memories.
        
        Args:
            query: The search query
            n_results: Number of results to return
            threshold: Minimum similarity threshold
            memory_type: Filter by memory type
            
        Returns:
            List of similar memories with metadata
        """
        try:
            # Generate embedding for the query
            query_embedding = self.embedding_service.embed_text(query)
            
            # Prepare filter if memory_type is specified
            query_filter = None
            if memory_type:
                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="memory_type",
                            match=MatchValue(value=memory_type)
                        )
                    ]
                )
            
            # Search in Qdrant
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=query_filter,
                limit=n_results,
                score_threshold=threshold
            )
            
            # Convert results to our format
            memories = []
            for result in search_results:
                memory = {
                    'id': result.id,
                    'content': result.payload.get('content', ''),
                    'similarity': result.score,
                    'metadata': {k: v for k, v in result.payload.items() if k != 'content'}
                }
                memories.append(memory)
            
            logger.debug(f"Found {len(memories)} memories for query: {query[:50]}...")
            return memories
            
        except Exception as e:
            logger.error(f"Error searching memories: {e}")
            return []

    async def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific memory by ID.
        
        Args:
            memory_id: The ID of the memory to retrieve
            
        Returns:
            The memory data or None if not found
        """
        try:
            # Retrieve from Qdrant
            result = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[memory_id]
            )
            
            if result:
                point = result[0]
                return {
                    'id': point.id,
                    'content': point.payload.get('content', ''),
                    'metadata': {k: v for k, v in point.payload.items() if k != 'content'}
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving memory {memory_id}: {e}")
            return None

    async def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a memory from the vector store.
        
        Args:
            memory_id: The ID of the memory to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Delete from Qdrant
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=[memory_id]
            )
            
            logger.info(f"Deleted memory with ID: {memory_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting memory {memory_id}: {e}")
            return False

    async def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the collection.
        
        Returns:
            Dictionary containing collection statistics
        """
        try:
            # Get collection info from Qdrant
            collection_info = self.client.get_collection(self.collection_name)
            
            return {
                'total_memories': collection_info.points_count,
                'collection_name': self.collection_name,
                'vector_size': collection_info.config.params.vectors.size,
                'distance_metric': collection_info.config.params.vectors.distance.name
            }
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {
                'total_memories': 0,
                'collection_name': self.collection_name,
                'error': str(e)
            }

    async def clear_collection(self) -> bool:
        """
        Clear all memories from the collection.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Delete the collection and recreate it
            self.client.delete_collection(self.collection_name)
            self._ensure_collection_exists()
            
            logger.info(f"Cleared collection: {self.collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing collection: {e}")
            return False

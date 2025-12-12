"""
Long-term memory implementation for persistent knowledge storage using vector search.
"""

import time
import json
import sys
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict

# Add the parent directory to the path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from Memory.qdrant_store import QdrantVectorStore


@dataclass
class LongTermMemory:
    """Represents a long-term memory entry."""
    content: str
    memory_type: str  # 'fact', 'preference', 'experience', 'knowledge', 'goal', 'skill', 'relationship'
    importance: float  # 0.0 to 1.0
    created_at: float
    last_accessed: float
    access_count: int
    tags: List[str]
    context: Optional[str] = None
    source: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert memory to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LongTermMemory':
        """Create memory from dictionary."""
        return cls(**data)


class LongTermMemoryManager:
    """
    Manages long-term memory for persistent knowledge storage.
    
    This class uses vector search to store and retrieve memories based on
    semantic similarity, allowing the agent to remember and recall relevant
    information from past conversations.
    """
    
    def __init__(self, vector_store: Optional[QdrantVectorStore] = None,
                 user_id: Optional[str] = None, session_id: Optional[str] = None):
        """
        Initialize the long-term memory manager.
        
        Args:
            vector_store: Optional custom vector store
            user_id: User ID for personalized memories
            session_id: Session ID for session-specific memories
        """
        self.vector_store = vector_store or QdrantVectorStore(
            user_id=user_id, session_id=session_id
        )
        self.similarity_threshold = getattr(Config, 'SIMILARITY_THRESHOLD', 0.7)
        self.max_memories = getattr(Config, 'MAX_SEARCH_RESULTS', 10)
        
        print("Initialized LongTermMemoryManager")
    
    async def store_memory(self, content: str, memory_type: str = "knowledge",
                    importance: float = 0.5, tags: Optional[List[str]] = None,
                    context: Optional[str] = None, source: Optional[str] = None) -> str:
        """
        Store a new long-term memory.
        
        Args:
            content: The memory content
            memory_type: Type of memory (fact, preference, experience, etc.)
            importance: Importance score (0.0 to 1.0)
            tags: Optional tags for categorization
            context: Optional context information
            source: Optional source information
            
        Returns:
            The ID of the stored memory
        """
        try:
            current_time = time.time()
            tags = tags or []
            
            # Create memory object
            memory = LongTermMemory(
                content=content,
                memory_type=memory_type,
                importance=importance,
                created_at=current_time,
                last_accessed=current_time,
                access_count=0,
                tags=tags,
                context=context,
                source=source
            )
            
            # Prepare metadata for vector store
            metadata = {
                'memory_type': memory_type,
                'importance': importance,
                'created_at': current_time,
                'last_accessed': current_time,
                'access_count': 0,
                'tags': json.dumps(tags),
                'context': context or '',
                'source': source or ''
            }
            
            # Clean metadata (ensure all values are JSON serializable)
            cleaned_metadata = {}
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool, type(None))):
                    cleaned_metadata[key] = value
                else:
                    cleaned_metadata[key] = str(value)

            metadata = cleaned_metadata
            
            # Store in vector store
            memory_id = self.vector_store.add_memory(
                content=content,
                metadata=metadata
            )
            
            print(f"Stored long-term memory: {memory_type} - {content[:50]}...")
            return memory_id
            
        except Exception as e:
            print(f"Error storing long-term memory: {e}")
            raise
    
    async def retrieve_memories(self, query: str, memory_type: Optional[str] = None,
                         max_results: Optional[int] = None,
                         min_importance: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Retrieve relevant memories based on a query.
        
        Args:
            query: Search query
            memory_type: Optional filter by memory type
            max_results: Maximum number of results to return
            min_importance: Minimum importance threshold
            
        Returns:
            List of relevant memories with scores
        """
        try:
            # Search for similar memories
            search_results = await self.vector_store.search_memories(
                query=query,
                n_results=max_results or self.max_memories,
                threshold=self.similarity_threshold
            )
            
            # Filter results based on criteria
            filtered_memories = []
            for result in search_results:
                metadata = result.get('metadata', {})
                
                # Filter by memory type if specified
                if memory_type and metadata.get('memory_type') != memory_type:
                    continue
                
                # Filter by importance if specified
                if min_importance and metadata.get('importance', 0) < min_importance:
                    continue
                
                # Update access count and timestamp
                metadata['last_accessed'] = time.time()
                metadata['access_count'] = metadata.get('access_count', 0) + 1
                
                # Create memory result
                memory_result = {
                    'id': result.get('id'),
                    'content': result.get('content', ''),
                    'memory_type': metadata.get('memory_type', 'unknown'),
                    'importance': metadata.get('importance', 0.0),
                    'created_at': metadata.get('created_at', 0),
                    'last_accessed': metadata.get('last_accessed', 0),
                    'access_count': metadata.get('access_count', 0),
                    'tags': metadata.get('tags', []),
                    'context': metadata.get('context', ''),
                    'source': metadata.get('source', ''),
                    'similarity_score': result.get('similarity', 0.0)
                }
                
                filtered_memories.append(memory_result)
                
                if max_results and len(filtered_memories) >= max_results:
                    break
            
            print(f"Retrieved {len(filtered_memories)} memories for query: {query[:50]}...")
            return filtered_memories
            
        except Exception as e:
            print(f"Error retrieving memories: {e}")
            return []
    
    def store_conversation_summary(self, summary: str, conversation_context: str,
                                 importance: float = 0.7) -> str:
        """
        Store a summary of a conversation.
        
        Args:
            summary: The conversation summary
            conversation_context: Context about the conversation
            importance: Importance score for the summary
            
        Returns:
            The ID of the stored memory
        """
        return self.store_memory(
            content=summary,
            memory_type="conversation",
            importance=importance,
            tags=["conversation", "summary"],
            context=conversation_context,
            source="conversation_summary"
        )
    
    async def store_math_solution(self, problem: str, solution: str, method: str = "",
                           importance: float = 0.8) -> str:
        """
        Store a mathematical solution.
        
        Args:
            problem: The math problem
            solution: The solution steps
            method: The method used to solve
            importance: Importance score
            
        Returns:
            The ID of the stored memory
        """
        content = f"Problem: {problem}\nSolution: {solution}"
        if method:
            content += f"\nMethod: {method}"
        
        return await self.store_memory(
            content=content,
            memory_type="math_solution",
            importance=importance,
            tags=["math", "solution", "problem"],
            context=f"Math problem solved using {method}" if method else "Math problem solved",
            source="math_agent"
        )
    
    def store_research_finding(self, topic: str, findings: str, sources: List[str],
                              importance: float = 0.7) -> str:
        """
        Store research findings.
        
        Args:
            topic: Research topic
            findings: Key findings
            sources: List of sources
            importance: Importance score
            
        Returns:
            The ID of the stored memory
        """
        content = f"Topic: {topic}\nFindings: {findings}\nSources: {', '.join(sources)}"
        
        return self.store_memory(
            content=content,
            memory_type="research",
            importance=importance,
            tags=["research", "findings", topic.lower().replace(" ", "_")],
            context=f"Research on {topic}",
            source="research_agent"
        )
    
    def get_memory_by_id(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific memory by ID.
        
        Args:
            memory_id: The ID of the memory
            
        Returns:
            The memory data or None if not found
        """
        try:
            memory_data = self.vector_store.get_memory(memory_id)
            if memory_data:
                payload = memory_data.get('payload', {})
                return {
                    'id': memory_id,
                    'content': payload.get('content', ''),
                    'memory_type': payload.get('memory_type', 'unknown'),
                    'importance': payload.get('importance', 0.0),
                    'created_at': payload.get('created_at', 0),
                    'last_accessed': payload.get('last_accessed', 0),
                    'access_count': payload.get('access_count', 0),
                    'tags': json.loads(payload.get('tags', '[]')),
                    'context': payload.get('context', ''),
                    'source': payload.get('source', '')
                }
            return None
        except Exception as e:
            print(f"Error getting memory {memory_id}: {e}")
            return None
    
    def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a memory by ID.
        
        Args:
            memory_id: The ID of the memory to delete
            
        Returns:
            True if deleted successfully
        """
        try:
            return self.vector_store.delete_memory(memory_id)
        except Exception as e:
            print(f"Error deleting memory {memory_id}: {e}")
            return False
    
    def list_all_memories(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        List all memories in the store.
        
        Args:
            limit: Maximum number of memories to return
            
        Returns:
            List of all memories
        """
        try:
            memories_data = self.vector_store.list_memories(limit=limit)
            memories = []
            
            for memory_data in memories_data:
                payload = memory_data.get('payload', {})
                memory = {
                    'id': memory_data.get('id'),
                    'content': payload.get('content', ''),
                    'memory_type': payload.get('memory_type', 'unknown'),
                    'importance': payload.get('importance', 0.0),
                    'created_at': payload.get('created_at', 0),
                    'last_accessed': payload.get('last_accessed', 0),
                    'access_count': payload.get('access_count', 0),
                    'tags': json.loads(payload.get('tags', '[]')),
                    'context': payload.get('context', ''),
                    'source': payload.get('source', '')
                }
                memories.append(memory)
            
            print(f"Listed {len(memories)} memories")
            return memories
        except Exception as e:
            print(f"Error listing memories: {e}")
            return []
    
    def clear_all_memories(self) -> bool:
        """
        Clear all memories from the store.
        
        Returns:
            True if cleared successfully
        """
        try:
            return self.vector_store.clear_all_memories()
        except Exception as e:
            print(f"Error clearing memories: {e}")
            return False
"""
Short-term memory implementation for conversation context management.
"""

import time
import sys
import os
from typing import List, Dict, Any, Optional
from collections import deque
from dataclasses import dataclass, asdict
# Remove loguru dependency

# Add the parent directory to the path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config


@dataclass
class Message:
    """Represents a single message in the conversation."""
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: float
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary."""
        return cls(**data)


class ShortTermMemory:
    """
    Manages short-term memory for conversation context.
    
    This class maintains a sliding window of recent messages and provides
    methods to add, retrieve, and manage conversation context.
    """
    
    def __init__(self, max_size: Optional[int] = None):
        """
        Initialize short-term memory.
        
        Args:
            max_size: Maximum number of messages to keep in memory
        """
        self.max_size = max_size or getattr(Config, 'SHORT_TERM_MAX_SIZE', 50)
        self.messages: deque = deque(maxlen=self.max_size)
        self.conversation_id: Optional[str] = None
        self.created_at = time.time()
        
        print(f"Initialized ShortTermMemory with max_size: {self.max_size}")
    
    def add_message(self, role: str, content: str, 
                   metadata: Optional[Dict[str, Any]] = None) -> Message:
        """
        Add a new message to short-term memory.
        
        Args:
            role: The role of the message sender ('user', 'assistant', 'system')
            content: The message content
            metadata: Optional metadata for the message
            
        Returns:
            The created Message object
        """
        message = Message(
            role=role,
            content=content,
            timestamp=time.time(),
            metadata=metadata or {}
        )
        
        self.messages.append(message)
        print(f"Added {role} message to short-term memory")
        
        return message
    
    def add_user_message(self, content: str, 
                        metadata: Optional[Dict[str, Any]] = None) -> Message:
        """Add a user message to memory."""
        return self.add_message("user", content, metadata)
    
    def add_assistant_message(self, content: str, 
                             metadata: Optional[Dict[str, Any]] = None) -> Message:
        """Add an assistant message to memory."""
        return self.add_message("assistant", content, metadata)
    
    def add_system_message(self, content: str, 
                          metadata: Optional[Dict[str, Any]] = None) -> Message:
        """Add a system message to memory."""
        return self.add_message("system", content, metadata)
    
    def get_messages(self, limit: Optional[int] = None, 
                    role_filter: Optional[str] = None) -> List[Message]:
        """
        Get messages from short-term memory.
        
        Args:
            limit: Maximum number of messages to return
            role_filter: Filter messages by role
            
        Returns:
            List of Message objects
        """
        messages = list(self.messages)
        
        # Apply role filter
        if role_filter:
            messages = [msg for msg in messages if msg.role == role_filter]
        
        # Apply limit
        if limit:
            messages = messages[-limit:]
        
        return messages
    
    def get_conversation_context(self, include_system: bool = True) -> List[Dict[str, str]]:
        """
        Get conversation context in a format suitable for LLM APIs.
        
        Args:
            include_system: Whether to include system messages
            
        Returns:
            List of message dictionaries with 'role' and 'content' keys
        """
        context = []
        
        for message in self.messages:
            if not include_system and message.role == "system":
                continue
            
            context.append({
                "role": message.role,
                "content": message.content
            })
        
        return context
    
    def get_recent_context(self, max_tokens: Optional[int] = None) -> str:
        """
        Get recent conversation context as a formatted string.
        
        Args:
            max_tokens: Approximate maximum tokens to include (rough estimate)
            
        Returns:
            Formatted conversation context
        """
        context_parts = []
        total_chars = 0
        max_chars = (max_tokens * 4) if max_tokens else None  # Rough token-to-char ratio
        
        # Iterate through messages in reverse order (most recent first)
        for message in reversed(self.messages):
            message_text = f"{message.role.upper()}: {message.content}"
            
            if max_chars and (total_chars + len(message_text)) > max_chars:
                break
            
            context_parts.insert(0, message_text)
            total_chars += len(message_text)
        
        return "\n\n".join(context_parts)
    
    def clear(self) -> None:
        """Clear all messages from short-term memory."""
        self.messages.clear()
        print("Cleared short-term memory")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about short-term memory.
        
        Returns:
            Dictionary with memory statistics
        """
        message_counts = {}
        for message in self.messages:
            role = message.role
            message_counts[role] = message_counts.get(role, 0) + 1
        
        return {
            "total_messages": len(self.messages),
            "max_size": self.max_size,
            "message_counts": message_counts,
            "oldest_message_time": self.messages[0].timestamp if self.messages else None,
            "newest_message_time": self.messages[-1].timestamp if self.messages else None,
            "created_at": self.created_at
        }
    
    def export_messages(self) -> List[Dict[str, Any]]:
        """
        Export all messages as a list of dictionaries.
        
        Returns:
            List of message dictionaries
        """
        return [message.to_dict() for message in self.messages]
    
    def import_messages(self, messages_data: List[Dict[str, Any]]) -> None:
        """
        Import messages from a list of dictionaries.
        
        Args:
            messages_data: List of message dictionaries
        """
        self.clear()
        for msg_data in messages_data:
            message = Message.from_dict(msg_data)
            self.messages.append(message)
        
        print(f"📥 Imported {len(messages_data)} messages to short-term memory")
    
    def get_last_user_message(self) -> Optional[Message]:
        """Get the most recent user message."""
        for message in reversed(self.messages):
            if message.role == "user":
                return message
        return None
    
    def get_last_assistant_message(self) -> Optional[Message]:
        """Get the most recent assistant message."""
        for message in reversed(self.messages):
            if message.role == "assistant":
                return message
        return None

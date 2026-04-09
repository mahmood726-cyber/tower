#!/usr/bin/env python3
"""
Session Manager for Conversation Context

Provides conversation/session management with:
- Message history with role tracking
- Context window calculation and automatic truncation
- Conversation summarization triggers
- Session persistence and recovery
- Multi-turn interaction support
"""

from __future__ import annotations

import hashlib
import json
import sys
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
TOWER_ROOT = SCRIPT_DIR.parent.parent
LEDGER_DIR = TOWER_ROOT / "addons" / "ledger"

# Import event logger
sys.path.insert(0, str(LEDGER_DIR))
try:
    from event_logger import EventLogger
    LEDGER_AVAILABLE = True
except ImportError:
    LEDGER_AVAILABLE = False


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class MessageRole(Enum):
    """Role of a message in the conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    FUNCTION = "function"  # Legacy OpenAI format


@dataclass
class Message:
    """A single message in the conversation."""

    role: MessageRole
    content: str
    name: Optional[str] = None           # For tool/function messages
    tool_call_id: Optional[str] = None   # For tool responses
    timestamp: str = field(default_factory=lambda: _now_utc().isoformat())
    token_count: Optional[int] = None    # Cached token count
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API-compatible format."""
        d = {"role": self.role.value, "content": self.content}
        if self.name:
            d["name"] = self.name
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d

    def to_full_dict(self) -> Dict[str, Any]:
        """Convert to full format with metadata."""
        d = asdict(self)
        d["role"] = self.role.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Message":
        """Create from dictionary."""
        role = MessageRole(d["role"]) if isinstance(d["role"], str) else d["role"]
        return cls(
            role=role,
            content=d["content"],
            name=d.get("name"),
            tool_call_id=d.get("tool_call_id"),
            timestamp=d.get("timestamp", _now_utc().isoformat()),
            token_count=d.get("token_count"),
            metadata=d.get("metadata", {}),
        )


class TruncationStrategy(Enum):
    """Strategy for truncating conversation history."""
    FIFO = "fifo"                      # Remove oldest messages first
    KEEP_SYSTEM = "keep_system"        # Keep system, remove oldest user/assistant
    SUMMARIZE = "summarize"            # Summarize old messages
    SLIDING_WINDOW = "sliding_window"  # Keep last N messages


@dataclass
class SessionConfig:
    """Configuration for a session."""

    max_tokens: int = 128000           # Max context window
    reserve_tokens: int = 4096         # Reserve for response
    truncation_strategy: TruncationStrategy = TruncationStrategy.KEEP_SYSTEM
    sliding_window_size: int = 20      # For SLIDING_WINDOW strategy
    auto_persist: bool = True          # Auto-save on changes
    summarize_threshold: float = 0.8   # Trigger summarization at 80% capacity
    tokens_per_char: float = 0.25      # Rough estimate (4 chars per token)


@dataclass
class Session:
    """A conversation session."""

    session_id: str
    card_id: Optional[str] = None
    messages: List[Message] = field(default_factory=list)
    config: SessionConfig = field(default_factory=SessionConfig)
    created_at: str = field(default_factory=lambda: _now_utc().isoformat())
    updated_at: str = field(default_factory=lambda: _now_utc().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    total_tokens_used: int = 0
    turn_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for persistence."""
        return {
            "session_id": self.session_id,
            "card_id": self.card_id,
            "messages": [m.to_full_dict() for m in self.messages],
            "config": {
                "max_tokens": self.config.max_tokens,
                "reserve_tokens": self.config.reserve_tokens,
                "truncation_strategy": self.config.truncation_strategy.value,
                "sliding_window_size": self.config.sliding_window_size,
                "auto_persist": self.config.auto_persist,
                "summarize_threshold": self.config.summarize_threshold,
                "tokens_per_char": self.config.tokens_per_char,
            },
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
            "total_tokens_used": self.total_tokens_used,
            "turn_count": self.turn_count,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Session":
        """Create from dictionary."""
        config_d = d.get("config", {})
        config = SessionConfig(
            max_tokens=config_d.get("max_tokens", 128000),
            reserve_tokens=config_d.get("reserve_tokens", 4096),
            truncation_strategy=TruncationStrategy(config_d.get("truncation_strategy", "keep_system")),
            sliding_window_size=config_d.get("sliding_window_size", 20),
            auto_persist=config_d.get("auto_persist", True),
            summarize_threshold=config_d.get("summarize_threshold", 0.8),
            tokens_per_char=config_d.get("tokens_per_char", 0.25),
        )

        messages = [Message.from_dict(m) for m in d.get("messages", [])]

        return cls(
            session_id=d["session_id"],
            card_id=d.get("card_id"),
            messages=messages,
            config=config,
            created_at=d.get("created_at", _now_utc().isoformat()),
            updated_at=d.get("updated_at", _now_utc().isoformat()),
            metadata=d.get("metadata", {}),
            total_tokens_used=d.get("total_tokens_used", 0),
            turn_count=d.get("turn_count", 0),
        )


class ContextOverflowError(Exception):
    """Raised when context cannot be reduced enough."""

    def __init__(self, required: int, available: int):
        self.required = required
        self.available = available
        super().__init__(
            f"Context overflow: required {required} tokens, "
            f"only {available} available after truncation"
        )


class SessionManager:
    """
    Manages conversation sessions with context window handling.

    Features:
    - Message history with role tracking
    - Automatic context window management
    - Multiple truncation strategies
    - Session persistence and recovery
    - Token counting (estimated or via callback)
    """

    # Default token limits for common models
    MODEL_LIMITS = {
        "claude-3-opus": 200000,
        "claude-3-sonnet": 200000,
        "claude-3-haiku": 200000,
        "claude-3-5-sonnet": 200000,
        "gpt-4": 8192,
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
        "gpt-3.5-turbo": 16385,
    }

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        token_counter: Optional[Callable[[str], int]] = None,
        summarizer: Optional[Callable[[List[Message]], str]] = None,
        ledger: Optional[EventLogger] = None,
        default_config: Optional[SessionConfig] = None,
    ):
        """
        Initialize session manager.

        Args:
            storage_path: Directory for session persistence
            token_counter: Function to count tokens (default: estimate)
            summarizer: Function to summarize messages for truncation
            ledger: Optional EventLogger for tracking
            default_config: Default configuration for new sessions
        """
        self.storage_path = storage_path or (TOWER_ROOT / "control" / "sessions")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.token_counter = token_counter or self._estimate_tokens
        self.summarizer = summarizer
        self.ledger = ledger
        self.default_config = default_config or SessionConfig()

        self._sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count from text length."""
        # Rough estimate: ~4 characters per token for English
        return int(len(text) * 0.25)

    def _count_message_tokens(self, message: Message) -> int:
        """Count tokens in a message."""
        if message.token_count is not None:
            return message.token_count

        # Count content tokens
        tokens = self.token_counter(message.content)

        # Add overhead for message structure (~4 tokens)
        tokens += 4

        if message.name:
            tokens += self.token_counter(message.name)

        message.token_count = tokens
        return tokens

    def _count_session_tokens(self, session: Session) -> int:
        """Count total tokens in session."""
        return sum(self._count_message_tokens(m) for m in session.messages)

    def _generate_session_id(self, card_id: Optional[str] = None) -> str:
        """Generate unique session ID."""
        timestamp = _now_utc().isoformat()
        seed = f"{card_id or 'global'}:{timestamp}"
        hash_suffix = hashlib.sha256(seed.encode()).hexdigest()[:8]
        return f"session_{hash_suffix}"

    def _log_event(
        self,
        event_type: str,
        session: Session,
        data: Dict[str, Any],
    ) -> None:
        """Log session event."""
        if self.ledger:
            self.ledger.log(
                event_type=f"session.{event_type}",
                card_id=session.card_id,
                actor="session_manager",
                data={"session_id": session.session_id, **data},
            )

    def _persist_session(self, session: Session) -> None:
        """Persist session to storage."""
        if not session.config.auto_persist:
            return

        session.updated_at = _now_utc().isoformat()
        file_path = self.storage_path / f"{session.session_id}.json"

        # Atomic write
        temp_path = file_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(session.to_dict(), f, indent=2)
            f.flush()
        temp_path.replace(file_path)

    def create_session(
        self,
        card_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        config: Optional[SessionConfig] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Session:
        """
        Create a new session.

        Args:
            card_id: Optional card ID to associate
            system_prompt: Optional system message
            config: Session configuration
            metadata: Additional metadata

        Returns:
            New Session instance
        """
        session_id = self._generate_session_id(card_id)
        session = Session(
            session_id=session_id,
            card_id=card_id,
            config=config or self.default_config,
            metadata=metadata or {},
        )

        if system_prompt:
            session.messages.append(Message(
                role=MessageRole.SYSTEM,
                content=system_prompt,
            ))

        with self._lock:
            self._sessions[session_id] = session

        self._persist_session(session)
        self._log_event("created", session, {"has_system_prompt": bool(system_prompt)})

        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        with self._lock:
            if session_id in self._sessions:
                return self._sessions[session_id]

        # Try loading from storage
        return self.load_session(session_id)

    def load_session(self, session_id: str) -> Optional[Session]:
        """Load session from storage."""
        file_path = self.storage_path / f"{session_id}.json"

        if not file_path.exists():
            return None

        try:
            with open(file_path) as f:
                data = json.load(f)

            session = Session.from_dict(data)

            with self._lock:
                self._sessions[session_id] = session

            return session

        except (json.JSONDecodeError, KeyError):
            return None

    def add_message(
        self,
        session: Session,
        role: MessageRole,
        content: str,
        name: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """
        Add a message to the session.

        Automatically handles context window overflow.

        Args:
            session: Target session
            role: Message role
            content: Message content
            name: Optional name for tool messages
            tool_call_id: Optional tool call ID
            metadata: Additional metadata

        Returns:
            The added message
        """
        message = Message(
            role=role,
            content=content,
            name=name,
            tool_call_id=tool_call_id,
            metadata=metadata or {},
        )

        # Count tokens
        self._count_message_tokens(message)

        # Check if we need to truncate
        current_tokens = self._count_session_tokens(session)
        new_tokens = message.token_count or 0
        available = session.config.max_tokens - session.config.reserve_tokens

        if current_tokens + new_tokens > available:
            self._truncate_session(session, new_tokens)

        # Add message
        session.messages.append(message)
        session.total_tokens_used += new_tokens

        # Track turns (user message = new turn)
        if role == MessageRole.USER:
            session.turn_count += 1

        self._persist_session(session)

        return message

    def add_user_message(self, session: Session, content: str) -> Message:
        """Convenience method to add user message."""
        return self.add_message(session, MessageRole.USER, content)

    def add_assistant_message(self, session: Session, content: str) -> Message:
        """Convenience method to add assistant message."""
        return self.add_message(session, MessageRole.ASSISTANT, content)

    def add_system_message(self, session: Session, content: str) -> Message:
        """Convenience method to add system message."""
        return self.add_message(session, MessageRole.SYSTEM, content)

    def _truncate_session(self, session: Session, required_tokens: int) -> None:
        """
        Truncate session to make room for new tokens.

        Args:
            session: Session to truncate
            required_tokens: Tokens needed for new message
        """
        strategy = session.config.truncation_strategy
        available = session.config.max_tokens - session.config.reserve_tokens
        target = available - required_tokens

        if strategy == TruncationStrategy.FIFO:
            self._truncate_fifo(session, target)
        elif strategy == TruncationStrategy.KEEP_SYSTEM:
            self._truncate_keep_system(session, target)
        elif strategy == TruncationStrategy.SLIDING_WINDOW:
            self._truncate_sliding_window(session)
        elif strategy == TruncationStrategy.SUMMARIZE:
            self._truncate_summarize(session, target)

        # Verify we have enough room
        current = self._count_session_tokens(session)
        if current + required_tokens > available:
            raise ContextOverflowError(current + required_tokens, available)

        self._log_event("truncated", session, {
            "strategy": strategy.value,
            "messages_remaining": len(session.messages),
            "tokens_after": current,
        })

    def _truncate_fifo(self, session: Session, target_tokens: int) -> None:
        """Remove oldest messages first."""
        while self._count_session_tokens(session) > target_tokens and len(session.messages) > 1:
            session.messages.pop(0)

    def _truncate_keep_system(self, session: Session, target_tokens: int) -> None:
        """Keep system messages, remove oldest user/assistant."""
        # Separate system and other messages
        system_msgs = [m for m in session.messages if m.role == MessageRole.SYSTEM]
        other_msgs = [m for m in session.messages if m.role != MessageRole.SYSTEM]

        # Calculate system tokens
        system_tokens = sum(self._count_message_tokens(m) for m in system_msgs)

        # Remove oldest non-system messages
        while other_msgs and system_tokens + sum(
            self._count_message_tokens(m) for m in other_msgs
        ) > target_tokens:
            other_msgs.pop(0)

        # Rebuild message list
        session.messages = system_msgs + other_msgs

    def _truncate_sliding_window(self, session: Session) -> None:
        """Keep only last N messages plus system."""
        window_size = session.config.sliding_window_size

        system_msgs = [m for m in session.messages if m.role == MessageRole.SYSTEM]
        other_msgs = [m for m in session.messages if m.role != MessageRole.SYSTEM]

        # Keep last window_size messages
        if len(other_msgs) > window_size:
            other_msgs = other_msgs[-window_size:]

        session.messages = system_msgs + other_msgs

    def _truncate_summarize(self, session: Session, target_tokens: int) -> None:
        """Summarize old messages."""
        if not self.summarizer:
            # Fall back to keep_system if no summarizer
            self._truncate_keep_system(session, target_tokens)
            return

        # Find messages to summarize (keep recent ones)
        keep_recent = 4  # Keep last 4 messages

        system_msgs = [m for m in session.messages if m.role == MessageRole.SYSTEM]
        other_msgs = [m for m in session.messages if m.role != MessageRole.SYSTEM]

        if len(other_msgs) <= keep_recent:
            return

        to_summarize = other_msgs[:-keep_recent]
        to_keep = other_msgs[-keep_recent:]

        # Generate summary
        summary_text = self.summarizer(to_summarize)
        summary_msg = Message(
            role=MessageRole.SYSTEM,
            content=f"[Summary of previous conversation]\n{summary_text}",
            metadata={"is_summary": True, "summarized_count": len(to_summarize)},
        )

        # Rebuild messages
        session.messages = system_msgs + [summary_msg] + to_keep

    def get_messages_for_api(
        self,
        session: Session,
        include_metadata: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get messages in API-compatible format.

        Args:
            session: Session to get messages from
            include_metadata: Include full metadata

        Returns:
            List of message dictionaries
        """
        if include_metadata:
            return [m.to_full_dict() for m in session.messages]
        return [m.to_dict() for m in session.messages]

    def get_context_usage(self, session: Session) -> Dict[str, Any]:
        """Get context window usage statistics."""
        current = self._count_session_tokens(session)
        max_tokens = session.config.max_tokens
        reserve = session.config.reserve_tokens
        available = max_tokens - reserve

        return {
            "current_tokens": current,
            "max_tokens": max_tokens,
            "reserve_tokens": reserve,
            "available_tokens": available,
            "used_percentage": (current / available) * 100 if available > 0 else 100,
            "message_count": len(session.messages),
            "turn_count": session.turn_count,
        }

    def clear_session(self, session: Session, keep_system: bool = True) -> None:
        """
        Clear session messages.

        Args:
            session: Session to clear
            keep_system: Keep system messages
        """
        if keep_system:
            session.messages = [m for m in session.messages if m.role == MessageRole.SYSTEM]
        else:
            session.messages = []

        session.turn_count = 0
        self._persist_session(session)
        self._log_event("cleared", session, {"kept_system": keep_system})

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]

        file_path = self.storage_path / f"{session_id}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def list_sessions(
        self,
        card_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all sessions, optionally filtered by card."""
        sessions = []

        for file_path in self.storage_path.glob("session_*.json"):
            try:
                with open(file_path) as f:
                    data = json.load(f)

                if card_id is None or data.get("card_id") == card_id:
                    sessions.append({
                        "session_id": data["session_id"],
                        "card_id": data.get("card_id"),
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                        "message_count": len(data.get("messages", [])),
                        "turn_count": data.get("turn_count", 0),
                    })
            except (json.JSONDecodeError, KeyError):
                continue

        return sorted(sessions, key=lambda s: s.get("updated_at", ""), reverse=True)


# Convenience functions
def create_session_manager(
    ledger: Optional[EventLogger] = None,
    max_tokens: int = 128000,
) -> SessionManager:
    """Create a session manager with default configuration."""
    config = SessionConfig(max_tokens=max_tokens)
    return SessionManager(ledger=ledger, default_config=config)


def create_session_for_model(
    model: str,
    ledger: Optional[EventLogger] = None,
) -> SessionManager:
    """Create a session manager configured for a specific model."""
    max_tokens = SessionManager.MODEL_LIMITS.get(model, 128000)
    config = SessionConfig(max_tokens=max_tokens)
    return SessionManager(ledger=ledger, default_config=config)

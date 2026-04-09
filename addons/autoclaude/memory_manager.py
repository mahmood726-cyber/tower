#!/usr/bin/env python3
"""
Memory Manager - Long-term Memory & Context Compaction

Inspired by:
- Anthropic Claude Code: "Context compaction and saving to external files"
- Quranic Amanah (Trust): Keep promises, maintain data integrity

Features:
- Working memory (current session)
- Long-term memory (persistent storage)
- Semantic retrieval (find relevant memories)
- Context compaction strategies
- Memory consolidation
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from enum import Enum
from datetime import datetime, timezone
from pathlib import Path
import json
import hashlib
import threading
import re

# Optional: integrate with ledger if available
try:
    import sys
    sys.path.insert(0, str(__file__).replace("autoclaude/memory_manager.py", ""))
    from ledger.event_logger import EventLogger
    HAS_LEDGER = True
except ImportError:
    HAS_LEDGER = False


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class MemoryType(Enum):
    """Types of memories."""
    FACT = "fact"              # Learned facts
    PROCEDURE = "procedure"    # How to do something
    EPISODE = "episode"        # What happened
    CONTEXT = "context"        # Session context
    PREFERENCE = "preference"  # User preferences
    ERROR = "error"            # Learned from mistakes
    INSIGHT = "insight"        # Derived understanding


class MemoryPriority(Enum):
    """Priority levels for memory retention."""
    CRITICAL = 5    # Never forget
    HIGH = 4        # Important
    MEDIUM = 3      # Standard
    LOW = 2         # Can forget if needed
    EPHEMERAL = 1   # Temporary only


class CompactionStrategy(Enum):
    """Strategies for context compaction."""
    SUMMARIZE = "summarize"      # Create summary
    EXTRACT_FACTS = "extract"    # Extract key facts
    HIERARCHICAL = "hierarchical"  # Multi-level summary
    SELECTIVE = "selective"      # Keep important, drop rest


@dataclass
class Memory:
    """A single memory unit."""
    id: str
    content: str
    memory_type: MemoryType
    priority: MemoryPriority
    keywords: List[str]
    source: str  # Where this memory came from
    created_at: datetime = field(default_factory=_now_utc)
    accessed_at: datetime = field(default_factory=_now_utc)
    access_count: int = 0
    ttl_hours: Optional[int] = None  # Time to live
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None  # For semantic search

    def is_expired(self) -> bool:
        """Check if memory has expired."""
        if self.ttl_hours is None:
            return False
        age_hours = (_now_utc() - self.created_at).total_seconds() / 3600
        return age_hours > self.ttl_hours

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "priority": self.priority.value,
            "keywords": self.keywords,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "access_count": self.access_count,
            "ttl_hours": self.ttl_hours,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Memory":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            content=data["content"],
            memory_type=MemoryType(data["memory_type"]),
            priority=MemoryPriority(data["priority"]),
            keywords=data["keywords"],
            source=data["source"],
            created_at=datetime.fromisoformat(data["created_at"]),
            accessed_at=datetime.fromisoformat(data["accessed_at"]),
            access_count=data["access_count"],
            ttl_hours=data.get("ttl_hours"),
            metadata=data.get("metadata", {})
        )


@dataclass
class RetrievalResult:
    """Result of memory retrieval."""
    memory: Memory
    relevance_score: float
    match_type: str  # "keyword", "semantic", "recent"


@dataclass
class CompactionResult:
    """Result of context compaction."""
    original_tokens: int
    compacted_tokens: int
    compression_ratio: float
    summary: str
    extracted_facts: List[str]
    discarded_count: int


@dataclass
class MemoryConfig:
    """Configuration for memory manager."""
    storage_path: Optional[Path] = None
    max_working_memory: int = 100
    max_long_term_memory: int = 10000
    auto_consolidate: bool = True
    consolidation_threshold: int = 50
    default_ttl_hours: Optional[int] = None
    enable_semantic_search: bool = False


class MemoryManager:
    """
    Manages working and long-term memory with retrieval and compaction.

    Amanah (Trust) Principle: "The faith of a believer is as good as his word"
    - Data integrity guaranteed
    - Promises (saved memories) are kept
    - Reliable retrieval
    """

    def __init__(self, config: Optional[MemoryConfig] = None, ledger_path: Optional[str] = None):
        self._config = config or MemoryConfig()
        self._working_memory: Dict[str, Memory] = {}
        self._long_term: Dict[str, Memory] = {}
        self._keyword_index: Dict[str, Set[str]] = {}  # keyword -> memory IDs
        self._type_index: Dict[MemoryType, Set[str]] = {}
        self._lock = threading.Lock()

        # Load from storage if configured
        if self._config.storage_path:
            self._load_from_storage()

        # Ledger integration
        self._logger: Optional[EventLogger] = None
        if HAS_LEDGER and ledger_path:
            self._logger = EventLogger(ledger_path)

    def _generate_id(self, content: str) -> str:
        """Generate unique memory ID."""
        timestamp = _now_utc().isoformat()
        return hashlib.sha256(f"{content}:{timestamp}".encode()).hexdigest()[:16]

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        # Simple keyword extraction
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        # Remove common stop words
        stop_words = {
            'the', 'and', 'for', 'that', 'this', 'with', 'are', 'from',
            'have', 'has', 'been', 'will', 'would', 'could', 'should',
            'was', 'were', 'being', 'their', 'there', 'then', 'than'
        }
        keywords = [w for w in words if w not in stop_words]
        # Return unique keywords, max 10
        seen = set()
        unique = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)
                if len(unique) >= 10:
                    break
        return unique

    def store(
        self,
        content: str,
        memory_type: MemoryType,
        source: str,
        priority: MemoryPriority = MemoryPriority.MEDIUM,
        keywords: Optional[List[str]] = None,
        ttl_hours: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        to_long_term: bool = False
    ) -> Memory:
        """Store a new memory."""
        memory_id = self._generate_id(content)
        extracted_keywords = keywords or self._extract_keywords(content)

        memory = Memory(
            id=memory_id,
            content=content,
            memory_type=memory_type,
            priority=priority,
            keywords=extracted_keywords,
            source=source,
            ttl_hours=ttl_hours or self._config.default_ttl_hours,
            metadata=metadata or {}
        )

        with self._lock:
            if to_long_term:
                self._long_term[memory_id] = memory
                self._check_long_term_limit()
            else:
                self._working_memory[memory_id] = memory
                self._check_working_limit()

            self._index_memory(memory)

        # Auto-consolidate if threshold reached
        if (self._config.auto_consolidate and
            len(self._working_memory) >= self._config.consolidation_threshold):
            self.consolidate_to_long_term()

        if self._logger:
            self._logger.log_event(
                event_type="MEMORY_STORED",
                card_id="autoclaude",
                details={
                    "memory_id": memory_id,
                    "type": memory_type.value,
                    "priority": priority.value,
                    "long_term": to_long_term,
                    "keyword_count": len(extracted_keywords)
                }
            )

        return memory

    def _index_memory(self, memory: Memory) -> None:
        """Add memory to search indices."""
        for keyword in memory.keywords:
            if keyword not in self._keyword_index:
                self._keyword_index[keyword] = set()
            self._keyword_index[keyword].add(memory.id)

        if memory.memory_type not in self._type_index:
            self._type_index[memory.memory_type] = set()
        self._type_index[memory.memory_type].add(memory.id)

    def _remove_from_index(self, memory: Memory) -> None:
        """Remove memory from search indices."""
        for keyword in memory.keywords:
            if keyword in self._keyword_index:
                self._keyword_index[keyword].discard(memory.id)
                if not self._keyword_index[keyword]:
                    del self._keyword_index[keyword]

        if memory.memory_type in self._type_index:
            self._type_index[memory.memory_type].discard(memory.id)

    def _check_working_limit(self) -> None:
        """Evict oldest low-priority memories if over limit."""
        while len(self._working_memory) > self._config.max_working_memory:
            # Find lowest priority, oldest memory
            to_evict = min(
                self._working_memory.values(),
                key=lambda m: (m.priority.value, -m.created_at.timestamp())
            )
            self._remove_from_index(to_evict)
            del self._working_memory[to_evict.id]

    def _check_long_term_limit(self) -> None:
        """Evict if over long-term limit."""
        while len(self._long_term) > self._config.max_long_term_memory:
            # Find lowest priority, least accessed memory
            to_evict = min(
                self._long_term.values(),
                key=lambda m: (m.priority.value, m.access_count)
            )
            self._remove_from_index(to_evict)
            del self._long_term[to_evict.id]

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        memory_types: Optional[List[MemoryType]] = None,
        min_priority: MemoryPriority = MemoryPriority.LOW,
        include_working: bool = True,
        include_long_term: bool = True
    ) -> List[RetrievalResult]:
        """
        Retrieve relevant memories using keyword matching.

        Returns memories sorted by relevance score.
        """
        query_keywords = set(self._extract_keywords(query))
        results: List[RetrievalResult] = []

        with self._lock:
            # Collect candidate memories
            candidates: Dict[str, Memory] = {}
            if include_working:
                candidates.update(self._working_memory)
            if include_long_term:
                candidates.update(self._long_term)

            for memory in candidates.values():
                # Skip expired memories
                if memory.is_expired():
                    continue

                # Skip low priority
                if memory.priority.value < min_priority.value:
                    continue

                # Filter by type
                if memory_types and memory.memory_type not in memory_types:
                    continue

                # Calculate relevance
                memory_keywords = set(memory.keywords)
                overlap = query_keywords & memory_keywords
                if overlap:
                    relevance = len(overlap) / max(len(query_keywords), 1)

                    # Boost by priority
                    relevance *= (memory.priority.value / 5.0)

                    # Boost by recency (within last hour)
                    age_hours = (_now_utc() - memory.accessed_at).total_seconds() / 3600
                    if age_hours < 1:
                        relevance *= 1.2
                    elif age_hours < 24:
                        relevance *= 1.1

                    # Update access
                    memory.accessed_at = _now_utc()
                    memory.access_count += 1

                    results.append(RetrievalResult(
                        memory=memory,
                        relevance_score=min(relevance, 1.0),
                        match_type="keyword"
                    ))

        # Sort by relevance
        results.sort(key=lambda r: r.relevance_score, reverse=True)

        if self._logger and results:
            self._logger.log_event(
                event_type="MEMORY_RETRIEVED",
                card_id="autoclaude",
                details={
                    "query_keywords": list(query_keywords)[:5],
                    "results_count": len(results[:top_k]),
                    "top_score": results[0].relevance_score if results else 0
                }
            )

        return results[:top_k]

    def get_memory(self, memory_id: str) -> Optional[Memory]:
        """Get a specific memory by ID."""
        with self._lock:
            if memory_id in self._working_memory:
                memory = self._working_memory[memory_id]
                memory.accessed_at = _now_utc()
                memory.access_count += 1
                return memory
            if memory_id in self._long_term:
                memory = self._long_term[memory_id]
                memory.accessed_at = _now_utc()
                memory.access_count += 1
                return memory
        return None

    def forget(self, memory_id: str) -> bool:
        """Delete a memory."""
        with self._lock:
            if memory_id in self._working_memory:
                memory = self._working_memory[memory_id]
                self._remove_from_index(memory)
                del self._working_memory[memory_id]
                return True
            if memory_id in self._long_term:
                memory = self._long_term[memory_id]
                self._remove_from_index(memory)
                del self._long_term[memory_id]
                return True
        return False

    def consolidate_to_long_term(
        self,
        min_access_count: int = 2,
        min_priority: MemoryPriority = MemoryPriority.MEDIUM
    ) -> int:
        """Move frequently accessed working memories to long-term storage."""
        moved = 0
        with self._lock:
            to_move = []
            for memory_id, memory in self._working_memory.items():
                if (memory.access_count >= min_access_count and
                    memory.priority.value >= min_priority.value and
                    not memory.is_expired()):
                    to_move.append(memory_id)

            for memory_id in to_move:
                memory = self._working_memory.pop(memory_id)
                self._long_term[memory_id] = memory
                moved += 1

            self._check_long_term_limit()

        if self._logger and moved > 0:
            self._logger.log_event(
                event_type="MEMORY_CONSOLIDATED",
                card_id="autoclaude",
                details={"moved_count": moved}
            )

        return moved

    def get_working_memory(self) -> List[Memory]:
        """Get all working memories sorted by recency."""
        with self._lock:
            memories = list(self._working_memory.values())
        return sorted(memories, key=lambda m: m.accessed_at, reverse=True)

    def get_context_for_prompt(
        self,
        query: str,
        max_tokens: int = 2000,
        include_types: Optional[List[MemoryType]] = None
    ) -> str:
        """Get relevant context formatted for inclusion in a prompt."""
        # Retrieve relevant memories
        results = self.retrieve(
            query=query,
            top_k=20,
            memory_types=include_types
        )

        if not results:
            return ""

        # Build context string within token limit (rough estimate: 4 chars = 1 token)
        max_chars = max_tokens * 4
        context_parts = []
        current_chars = 0

        for result in results:
            memory = result.memory
            entry = f"[{memory.memory_type.value.upper()}] {memory.content}"
            entry_chars = len(entry)

            if current_chars + entry_chars > max_chars:
                break

            context_parts.append(entry)
            current_chars += entry_chars

        if not context_parts:
            return ""

        return "Relevant context:\n" + "\n".join(context_parts)

    def compact_context(
        self,
        messages: List[Dict[str, str]],
        strategy: CompactionStrategy = CompactionStrategy.EXTRACT_FACTS,
        target_reduction: float = 0.5
    ) -> CompactionResult:
        """
        Compact conversation context using specified strategy.

        Note: Full summarization requires LLM call - this does rule-based extraction.
        """
        # Calculate original size
        original_text = "\n".join(m.get("content", "") for m in messages)
        original_tokens = len(original_text) // 4  # Rough estimate

        extracted_facts: List[str] = []
        discarded = 0

        if strategy == CompactionStrategy.EXTRACT_FACTS:
            # Extract key facts from messages
            for msg in messages:
                content = msg.get("content", "")
                # Look for fact-like patterns
                facts = self._extract_facts_from_text(content)
                extracted_facts.extend(facts)

            # Create compacted version
            summary = "Key facts:\n" + "\n".join(f"- {f}" for f in extracted_facts[:20])
            discarded = len(messages) - len(extracted_facts)

        elif strategy == CompactionStrategy.SELECTIVE:
            # Keep messages with high information density
            for msg in messages:
                content = msg.get("content", "")
                # Keep if it contains code, numbers, or key terms
                if self._is_high_value_content(content):
                    extracted_facts.append(content[:200])  # Truncate long messages
                else:
                    discarded += 1

            summary = "\n---\n".join(extracted_facts)

        else:
            # Default: simple truncation
            target_chars = int(len(original_text) * (1 - target_reduction))
            summary = original_text[:target_chars]
            if len(original_text) > target_chars:
                summary += "\n[... truncated ...]"

        compacted_tokens = len(summary) // 4

        return CompactionResult(
            original_tokens=original_tokens,
            compacted_tokens=compacted_tokens,
            compression_ratio=compacted_tokens / max(original_tokens, 1),
            summary=summary,
            extracted_facts=extracted_facts,
            discarded_count=discarded
        )

    def _extract_facts_from_text(self, text: str) -> List[str]:
        """Extract fact-like statements from text."""
        facts = []
        sentences = re.split(r'[.!?]\s+', text)

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or len(sentence) < 10:
                continue

            # Look for fact patterns
            fact_patterns = [
                r'^The\s+\w+\s+(is|are|was|were)\s+',  # "The X is Y"
                r'^\d+',  # Starts with number
                r'(must|should|always|never)\s+',  # Instructions
                r'(error|bug|issue|problem|fix)',  # Error info
                r'(function|class|method|variable)\s+\w+',  # Code entities
            ]

            for pattern in fact_patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    facts.append(sentence[:150])  # Limit length
                    break

        return facts[:10]  # Max 10 facts per text

    def _is_high_value_content(self, text: str) -> bool:
        """Check if content has high information density."""
        if not text:
            return False

        # Code blocks
        if '```' in text or 'def ' in text or 'function ' in text:
            return True

        # Numbers and data
        if re.search(r'\d+\.\d+|\d{3,}', text):
            return True

        # Error messages
        if re.search(r'error|exception|failed|traceback', text, re.IGNORECASE):
            return True

        # URLs and paths
        if 'http' in text or '/' in text and '.' in text:
            return True

        return False

    def cleanup_expired(self) -> int:
        """Remove all expired memories."""
        removed = 0
        with self._lock:
            # Working memory
            expired_working = [
                mid for mid, m in self._working_memory.items()
                if m.is_expired()
            ]
            for mid in expired_working:
                memory = self._working_memory.pop(mid)
                self._remove_from_index(memory)
                removed += 1

            # Long-term memory
            expired_long = [
                mid for mid, m in self._long_term.items()
                if m.is_expired()
            ]
            for mid in expired_long:
                memory = self._long_term.pop(mid)
                self._remove_from_index(memory)
                removed += 1

        return removed

    def save_to_storage(self) -> bool:
        """Persist memories to storage."""
        if not self._config.storage_path:
            return False

        path = Path(self._config.storage_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            data = {
                "saved_at": _now_utc().isoformat(),
                "working_memory": [m.to_dict() for m in self._working_memory.values()],
                "long_term": [m.to_dict() for m in self._long_term.values()]
            }

        path.write_text(json.dumps(data, indent=2))
        return True

    def _load_from_storage(self) -> bool:
        """Load memories from storage."""
        if not self._config.storage_path:
            return False

        path = Path(self._config.storage_path)
        if not path.exists():
            return False

        try:
            data = json.loads(path.read_text())

            for m_data in data.get("working_memory", []):
                memory = Memory.from_dict(m_data)
                self._working_memory[memory.id] = memory
                self._index_memory(memory)

            for m_data in data.get("long_term", []):
                memory = Memory.from_dict(m_data)
                self._long_term[memory.id] = memory
                self._index_memory(memory)

            return True
        except (json.JSONDecodeError, KeyError):
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        with self._lock:
            working_by_type = {}
            for m in self._working_memory.values():
                t = m.memory_type.value
                working_by_type[t] = working_by_type.get(t, 0) + 1

            long_term_by_type = {}
            for m in self._long_term.values():
                t = m.memory_type.value
                long_term_by_type[t] = long_term_by_type.get(t, 0) + 1

            return {
                "working_memory_count": len(self._working_memory),
                "long_term_count": len(self._long_term),
                "total_keywords": len(self._keyword_index),
                "working_by_type": working_by_type,
                "long_term_by_type": long_term_by_type
            }


# Convenience exports
__all__ = [
    "MemoryManager",
    "Memory",
    "MemoryType",
    "MemoryPriority",
    "MemoryConfig",
    "RetrievalResult",
    "CompactionResult",
    "CompactionStrategy"
]

#!/usr/bin/env python3
"""
Tool Registry - Semantic Tool Discovery & Validation

Inspired by:
- Anthropic Advanced Tool Use: "Tool Search Tool discovers tools on-demand"
- Quranic Hikmah (Wisdom): Choose the right tool wisely

Features:
- Semantic tool search (find tools by description)
- Usage examples for each tool
- Parameter validation with helpful errors
- Tool capability matching
- When-to-use guidance
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from enum import Enum
from datetime import datetime, timezone
import json
import re
import hashlib

# Optional: integrate with ledger if available
try:
    import sys
    sys.path.insert(0, str(__file__).replace("autoclaude/tool_registry.py", ""))
    from ledger.event_logger import EventLogger
    HAS_LEDGER = True
except ImportError:
    HAS_LEDGER = False


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ToolCategory(Enum):
    """Categories for tool organization."""
    DATA_RETRIEVAL = "data_retrieval"
    DATA_MODIFICATION = "data_modification"
    ANALYSIS = "analysis"
    COMMUNICATION = "communication"
    FILE_SYSTEM = "file_system"
    CODE_EXECUTION = "code_execution"
    EXTERNAL_API = "external_api"
    INTERNAL = "internal"


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""
    name: str
    param_type: str  # "string", "integer", "number", "boolean", "array", "object"
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    pattern: Optional[str] = None  # Regex pattern for strings
    examples: List[Any] = field(default_factory=list)


@dataclass
class ToolExample:
    """Example usage of a tool."""
    description: str
    parameters: Dict[str, Any]
    expected_outcome: str
    tags: List[str] = field(default_factory=list)


@dataclass
class Tool:
    """Complete tool definition with metadata."""
    name: str
    description: str
    when_to_use: str
    when_not_to_use: str
    parameters: List[ToolParameter]
    category: ToolCategory
    examples: List[ToolExample] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    requires_confirmation: bool = False
    is_destructive: bool = False
    rate_limit: Optional[int] = None  # Max calls per minute
    timeout_seconds: Optional[int] = None
    version: str = "1.0.0"
    deprecated: bool = False
    deprecation_message: Optional[str] = None
    created_at: datetime = field(default_factory=_now_utc)

    def to_schema(self) -> Dict[str, Any]:
        """Convert to JSON schema format for LLM consumption."""
        properties = {}
        required = []

        for param in self.parameters:
            prop = {
                "type": param.param_type,
                "description": param.description
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default
            if param.examples:
                prop["examples"] = param.examples
            if param.min_value is not None:
                prop["minimum"] = param.min_value
            if param.max_value is not None:
                prop["maximum"] = param.max_value
            if param.pattern:
                prop["pattern"] = param.pattern

            properties[param.name] = prop
            if param.required:
                required.append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }

    def get_tool_id(self) -> str:
        """Generate unique tool ID."""
        content = f"{self.name}:{self.version}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]


@dataclass
class ToolMatch:
    """Result of a tool search."""
    tool: Tool
    relevance_score: float  # 0.0 to 1.0
    match_reasons: List[str]
    example_match: Optional[ToolExample] = None


@dataclass
class ValidationError:
    """Parameter validation error."""
    parameter: str
    message: str
    value: Any
    expected: str


@dataclass
class ToolCallValidation:
    """Result of tool call validation."""
    valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    normalized_params: Dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    """
    Semantic tool discovery and validation registry.

    Hikmah (Wisdom) Principle: "Invite with wisdom" (16:125)
    - Choose the right tool for the right task
    - Validate before acting
    - Learn from examples
    """

    def __init__(
        self,
        ledger_path: Optional[str] = None,
        enable_semantic_search: bool = True
    ):
        self._tools: Dict[str, Tool] = {}
        self._tags_index: Dict[str, Set[str]] = {}  # tag -> tool names
        self._category_index: Dict[ToolCategory, Set[str]] = {}
        self._keyword_index: Dict[str, Set[str]] = {}  # keyword -> tool names
        self._enable_semantic = enable_semantic_search

        # Ledger integration
        self._logger: Optional[EventLogger] = None
        if HAS_LEDGER and ledger_path:
            self._logger = EventLogger(ledger_path)

    def register_tool(
        self,
        name: str,
        description: str,
        when_to_use: str,
        when_not_to_use: str,
        parameters: List[ToolParameter],
        category: ToolCategory,
        examples: Optional[List[ToolExample]] = None,
        tags: Optional[List[str]] = None,
        requires_confirmation: bool = False,
        is_destructive: bool = False,
        rate_limit: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
        version: str = "1.0.0"
    ) -> Tool:
        """Register a new tool with the registry."""
        tool = Tool(
            name=name,
            description=description,
            when_to_use=when_to_use,
            when_not_to_use=when_not_to_use,
            parameters=parameters,
            category=category,
            examples=examples or [],
            tags=tags or [],
            requires_confirmation=requires_confirmation,
            is_destructive=is_destructive,
            rate_limit=rate_limit,
            timeout_seconds=timeout_seconds,
            version=version
        )

        self._tools[name] = tool
        self._index_tool(tool)

        if self._logger:
            self._logger.log_event(
                event_type="TOOL_REGISTERED",
                card_id="autoclaude",
                details={
                    "tool_name": name,
                    "tool_id": tool.get_tool_id(),
                    "category": category.value,
                    "param_count": len(parameters),
                    "example_count": len(tool.examples)
                }
            )

        return tool

    def _index_tool(self, tool: Tool) -> None:
        """Build search indices for a tool."""
        # Tag index
        for tag in tool.tags:
            tag_lower = tag.lower()
            if tag_lower not in self._tags_index:
                self._tags_index[tag_lower] = set()
            self._tags_index[tag_lower].add(tool.name)

        # Category index
        if tool.category not in self._category_index:
            self._category_index[tool.category] = set()
        self._category_index[tool.category].add(tool.name)

        # Keyword index (from name, description, when_to_use)
        text = f"{tool.name} {tool.description} {tool.when_to_use}"
        keywords = self._extract_keywords(text)
        for kw in keywords:
            if kw not in self._keyword_index:
                self._keyword_index[kw] = set()
            self._keyword_index[kw].add(tool.name)

    def _extract_keywords(self, text: str) -> Set[str]:
        """Extract searchable keywords from text."""
        # Remove punctuation and split
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        # Filter common stop words
        stop_words = {
            'the', 'and', 'for', 'that', 'this', 'with', 'are', 'from',
            'have', 'has', 'been', 'will', 'would', 'could', 'should',
            'use', 'used', 'using', 'when', 'where', 'which', 'what'
        }
        return {w for w in words if w not in stop_words}

    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by exact name."""
        return self._tools.get(name)

    def search_tools(
        self,
        query: str,
        category: Optional[ToolCategory] = None,
        tags: Optional[List[str]] = None,
        max_results: int = 5,
        include_deprecated: bool = False
    ) -> List[ToolMatch]:
        """
        Search for tools using natural language query.

        Implements semantic matching against:
        - Tool name and description
        - When-to-use guidance
        - Tags and categories
        - Example descriptions
        """
        matches: List[ToolMatch] = []
        query_keywords = self._extract_keywords(query)
        query_lower = query.lower()

        # Get candidate tools
        candidates = set(self._tools.keys())

        # Filter by category if specified
        if category and category in self._category_index:
            candidates &= self._category_index[category]

        # Filter by tags if specified
        if tags:
            for tag in tags:
                tag_lower = tag.lower()
                if tag_lower in self._tags_index:
                    candidates &= self._tags_index[tag_lower]

        for tool_name in candidates:
            tool = self._tools[tool_name]

            # Skip deprecated unless requested
            if tool.deprecated and not include_deprecated:
                continue

            score, reasons = self._calculate_relevance(tool, query_lower, query_keywords)

            if score > 0.1:  # Minimum threshold
                # Find best matching example
                best_example = None
                best_example_score = 0.0
                for example in tool.examples:
                    ex_score = self._text_similarity(query_lower, example.description.lower())
                    if ex_score > best_example_score:
                        best_example_score = ex_score
                        best_example = example

                matches.append(ToolMatch(
                    tool=tool,
                    relevance_score=score,
                    match_reasons=reasons,
                    example_match=best_example
                ))

        # Sort by relevance
        matches.sort(key=lambda m: m.relevance_score, reverse=True)

        if self._logger:
            self._logger.log_event(
                event_type="TOOL_SEARCH",
                card_id="autoclaude",
                details={
                    "query": query[:100],
                    "category": category.value if category else None,
                    "tags": tags,
                    "results_count": len(matches[:max_results]),
                    "top_match": matches[0].tool.name if matches else None
                }
            )

        return matches[:max_results]

    def _calculate_relevance(
        self,
        tool: Tool,
        query_lower: str,
        query_keywords: Set[str]
    ) -> Tuple[float, List[str]]:
        """Calculate relevance score and reasons for a tool."""
        score = 0.0
        reasons = []

        # Exact name match
        if tool.name.lower() in query_lower:
            score += 0.4
            reasons.append(f"Name match: {tool.name}")

        # Keyword overlap with description
        tool_keywords = self._extract_keywords(tool.description)
        overlap = query_keywords & tool_keywords
        if overlap:
            keyword_score = len(overlap) / max(len(query_keywords), 1) * 0.3
            score += keyword_score
            reasons.append(f"Keywords: {', '.join(list(overlap)[:3])}")

        # When-to-use match
        when_keywords = self._extract_keywords(tool.when_to_use)
        when_overlap = query_keywords & when_keywords
        if when_overlap:
            score += len(when_overlap) / max(len(query_keywords), 1) * 0.2
            reasons.append(f"Use case match: {', '.join(list(when_overlap)[:2])}")

        # Tag match
        for tag in tool.tags:
            if tag.lower() in query_lower:
                score += 0.1
                reasons.append(f"Tag: {tag}")
                break

        # Category name in query
        if tool.category.value.replace("_", " ") in query_lower:
            score += 0.1
            reasons.append(f"Category: {tool.category.value}")

        # Text similarity as fallback
        if score < 0.2:
            sim = self._text_similarity(query_lower, tool.description.lower())
            if sim > 0.3:
                score += sim * 0.2
                reasons.append("Description similarity")

        return min(score, 1.0), reasons

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Simple word overlap similarity."""
        words1 = set(text1.split())
        words2 = set(text2.split())
        if not words1 or not words2:
            return 0.0
        overlap = len(words1 & words2)
        return overlap / max(len(words1), len(words2))

    def validate_tool_call(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> ToolCallValidation:
        """
        Validate a tool call before execution.

        Checks:
        - Required parameters present
        - Types match specification
        - Values within constraints
        - Enum values valid
        """
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolCallValidation(
                valid=False,
                errors=[ValidationError(
                    parameter="__tool__",
                    message=f"Tool '{tool_name}' not found",
                    value=tool_name,
                    expected="registered tool name"
                )]
            )

        errors: List[ValidationError] = []
        warnings: List[str] = []
        normalized: Dict[str, Any] = {}

        # Check each parameter definition
        param_defs = {p.name: p for p in tool.parameters}

        # Check required parameters
        for param in tool.parameters:
            if param.required and param.name not in parameters:
                if param.default is not None:
                    normalized[param.name] = param.default
                else:
                    errors.append(ValidationError(
                        parameter=param.name,
                        message=f"Required parameter '{param.name}' is missing",
                        value=None,
                        expected=param.param_type
                    ))

        # Validate provided parameters
        for param_name, value in parameters.items():
            if param_name not in param_defs:
                warnings.append(f"Unknown parameter '{param_name}' will be ignored")
                continue

            param = param_defs[param_name]

            # Type validation
            type_valid, normalized_value = self._validate_type(value, param.param_type)
            if not type_valid:
                errors.append(ValidationError(
                    parameter=param_name,
                    message=f"Invalid type for '{param_name}'",
                    value=value,
                    expected=param.param_type
                ))
                continue

            # Enum validation
            if param.enum and normalized_value not in param.enum:
                errors.append(ValidationError(
                    parameter=param_name,
                    message=f"Value must be one of {param.enum}",
                    value=normalized_value,
                    expected=f"one of {param.enum}"
                ))
                continue

            # Range validation
            if param.min_value is not None and normalized_value < param.min_value:
                errors.append(ValidationError(
                    parameter=param_name,
                    message=f"Value below minimum ({param.min_value})",
                    value=normalized_value,
                    expected=f">= {param.min_value}"
                ))
                continue

            if param.max_value is not None and normalized_value > param.max_value:
                errors.append(ValidationError(
                    parameter=param_name,
                    message=f"Value above maximum ({param.max_value})",
                    value=normalized_value,
                    expected=f"<= {param.max_value}"
                ))
                continue

            # Pattern validation
            if param.pattern and isinstance(normalized_value, str):
                if not re.match(param.pattern, normalized_value):
                    errors.append(ValidationError(
                        parameter=param_name,
                        message=f"Value does not match pattern",
                        value=normalized_value,
                        expected=f"pattern: {param.pattern}"
                    ))
                    continue

            normalized[param_name] = normalized_value

        # Deprecation warning
        if tool.deprecated:
            warnings.append(
                f"Tool '{tool_name}' is deprecated. "
                f"{tool.deprecation_message or 'Consider using an alternative.'}"
            )

        if self._logger and errors:
            self._logger.log_event(
                event_type="TOOL_VALIDATION_FAILED",
                card_id="autoclaude",
                details={
                    "tool_name": tool_name,
                    "error_count": len(errors),
                    "errors": [e.message for e in errors[:3]]
                }
            )

        return ToolCallValidation(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            normalized_params=normalized
        )

    def _validate_type(self, value: Any, expected_type: str) -> Tuple[bool, Any]:
        """Validate and normalize a value to the expected type."""
        try:
            if expected_type == "string":
                return True, str(value)
            elif expected_type == "integer":
                return True, int(value)
            elif expected_type == "number":
                return True, float(value)
            elif expected_type == "boolean":
                if isinstance(value, bool):
                    return True, value
                if isinstance(value, str):
                    return True, value.lower() in ('true', '1', 'yes')
                return True, bool(value)
            elif expected_type == "array":
                if isinstance(value, list):
                    return True, value
                return False, value
            elif expected_type == "object":
                if isinstance(value, dict):
                    return True, value
                return False, value
            else:
                return True, value
        except (ValueError, TypeError):
            return False, value

    def get_tool_examples(
        self,
        tool_name: str,
        tags: Optional[List[str]] = None
    ) -> List[ToolExample]:
        """Get usage examples for a tool, optionally filtered by tags."""
        tool = self._tools.get(tool_name)
        if not tool:
            return []

        if not tags:
            return tool.examples

        tag_set = {t.lower() for t in tags}
        return [
            ex for ex in tool.examples
            if any(t.lower() in tag_set for t in ex.tags)
        ]

    def get_tools_by_category(
        self,
        category: ToolCategory,
        include_deprecated: bool = False
    ) -> List[Tool]:
        """Get all tools in a category."""
        if category not in self._category_index:
            return []

        tools = [
            self._tools[name]
            for name in self._category_index[category]
            if include_deprecated or not self._tools[name].deprecated
        ]
        return sorted(tools, key=lambda t: t.name)

    def get_all_schemas(
        self,
        include_deprecated: bool = False
    ) -> List[Dict[str, Any]]:
        """Get JSON schemas for all tools (for LLM context)."""
        return [
            tool.to_schema()
            for tool in self._tools.values()
            if include_deprecated or not tool.deprecated
        ]

    def suggest_similar_tools(
        self,
        tool_name: str,
        max_results: int = 3
    ) -> List[Tool]:
        """Suggest similar tools based on category and tags."""
        tool = self._tools.get(tool_name)
        if not tool:
            return []

        similar: List[Tuple[Tool, int]] = []

        for other_name, other in self._tools.items():
            if other_name == tool_name or other.deprecated:
                continue

            score = 0

            # Same category
            if other.category == tool.category:
                score += 2

            # Overlapping tags
            overlap = set(tool.tags) & set(other.tags)
            score += len(overlap)

            if score > 0:
                similar.append((other, score))

        similar.sort(key=lambda x: x[1], reverse=True)
        return [t for t, _ in similar[:max_results]]

    def deprecate_tool(
        self,
        tool_name: str,
        message: str,
        replacement: Optional[str] = None
    ) -> bool:
        """Mark a tool as deprecated."""
        tool = self._tools.get(tool_name)
        if not tool:
            return False

        tool.deprecated = True
        if replacement:
            tool.deprecation_message = f"{message} Use '{replacement}' instead."
        else:
            tool.deprecation_message = message

        if self._logger:
            self._logger.log_event(
                event_type="TOOL_DEPRECATED",
                card_id="autoclaude",
                details={
                    "tool_name": tool_name,
                    "message": message,
                    "replacement": replacement
                }
            )

        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        active_tools = [t for t in self._tools.values() if not t.deprecated]
        deprecated_tools = [t for t in self._tools.values() if t.deprecated]

        category_counts = {}
        for cat in ToolCategory:
            count = len(self._category_index.get(cat, set()))
            if count > 0:
                category_counts[cat.value] = count

        return {
            "total_tools": len(self._tools),
            "active_tools": len(active_tools),
            "deprecated_tools": len(deprecated_tools),
            "total_examples": sum(len(t.examples) for t in self._tools.values()),
            "categories": category_counts,
            "unique_tags": len(self._tags_index),
            "indexed_keywords": len(self._keyword_index)
        }

    def export_catalog(self) -> Dict[str, Any]:
        """Export full tool catalog for documentation."""
        return {
            "generated_at": _now_utc().isoformat(),
            "stats": self.get_stats(),
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "when_to_use": tool.when_to_use,
                    "when_not_to_use": tool.when_not_to_use,
                    "category": tool.category.value,
                    "tags": tool.tags,
                    "parameters": [
                        {
                            "name": p.name,
                            "type": p.param_type,
                            "description": p.description,
                            "required": p.required
                        }
                        for p in tool.parameters
                    ],
                    "examples": [
                        {
                            "description": ex.description,
                            "parameters": ex.parameters
                        }
                        for ex in tool.examples
                    ],
                    "requires_confirmation": tool.requires_confirmation,
                    "is_destructive": tool.is_destructive,
                    "deprecated": tool.deprecated,
                    "version": tool.version
                }
                for tool in sorted(self._tools.values(), key=lambda t: t.name)
            ]
        }


# Convenience exports
__all__ = [
    "ToolRegistry",
    "Tool",
    "ToolParameter",
    "ToolExample",
    "ToolMatch",
    "ToolCategory",
    "ToolCallValidation",
    "ValidationError"
]

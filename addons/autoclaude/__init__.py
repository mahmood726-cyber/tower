#!/usr/bin/env python3
"""
Tower Autoclaude Addon - Production LLM Agent Patterns (v2.0)

Provides:
- LLMTracker: Token/cost tracking for LLM API calls
- CircuitBreaker: Prevents runaway correction loops
- RetryPolicy: Exponential backoff with jitter
- PromptRegistry: Version-controlled prompt management
- HumanCheckpoint: Human-in-the-loop review gates
- ConfidenceScorer: Output confidence assessment
- ErrorTaxonomy: Structured error classification
- FallbackChain: Model degradation fallback
- RateLimiter: Token bucket rate limiting
- SessionManager: Conversation context management
- OutputValidator: Structured output validation
- StateManager: Crash recovery and state persistence
- Guardrails: Safety filtering and PII detection
- MetricsExporter: Prometheus/StatsD observability
- ToolRegistry: Semantic tool discovery and validation
- MemoryManager: Long-term memory and context compaction
- AgentOrchestrator: Multi-agent coordination patterns
- AgentEvaluator: Offline/online evaluation and LLM-as-judge
- OTelExporter: OpenTelemetry GenAI semantic conventions
- DecisionExplainer: Transparent decision audit trail
"""

from .agent_evaluator import (
    AgentEvaluator,
    EvalCriteria,
    EvalReport,
    EvalResult,
    EvalScore,
    EvalType,
    QualityMetrics,
    ReviewItem,
    ReviewStatus,
    ScoreType,
    TestCase,
)
from .agent_orchestrator import (
    Agent,
    AgentCapability,
    AgentOrchestrator,
    AgentStatus,
    OrchestrationPattern,
    OrchestrationResult,
    Task,
    TaskStatus,
)
from .circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState
from .confidence_scorer import ConfidenceResult, ConfidenceScorer
from .decision_explainer import (
    Alternative,
    ConfidenceLevel,
    CounterfactualExplanation,
    DecisionExplainer,
    DecisionNode,
    DecisionType,
    ExplanationChain,
    Factor,
)
from .error_taxonomy import ClassifiedError, ErrorCategory, ErrorSeverity, ErrorTaxonomy
from .fallback_chain import (
    AllModelsFailedError,
    FallbackChain,
    FallbackReason,
    FallbackResult,
    ModelConfig,
)
from .guardrails import (
    GuardrailConfig,
    GuardrailResult,
    Guardrails,
    Violation,
    ViolationAction,
    ViolationType,
)
from .human_checkpoint import CheckpointDecision, CheckpointStatus, HumanCheckpoint
from .llm_tracker import CostReport, LLMCall, LLMTracker
from .memory_manager import (
    CompactionResult,
    CompactionStrategy,
    Memory,
    MemoryConfig,
    MemoryManager,
    MemoryPriority,
    MemoryType,
    RetrievalResult,
)
from .metrics_exporter import Metric, MetricsExporter, MetricsRegistry, MetricType
from .otel_exporter import (
    GenAIAttributes,
    GenAIOperationType,
    OTelConfig,
    OTelExporter,
    Span,
    SpanContext,
    SpanKind,
    SpanStatus,
)
from .output_validator import (
    OutputValidator,
    ToolCall,
    ToolCallSchema,
    ValidationError,
    ValidationResult,
)
from .prompt_registry import PromptRegistry, PromptVersion
from .rate_limiter import (
    LimitScope,
    RateLimitConfig,
    RateLimiter,
    RateLimitExceededError,
    TokenBucket,
)
from .retry_policy import RetryConfig, RetryExhaustedError, RetryPolicy
from .session_manager import (
    ContextOverflowError,
    Message,
    MessageRole,
    Session,
    SessionConfig,
    SessionManager,
    TruncationStrategy,
)
from .state_manager import (
    Snapshot,
    StateConfig,
    StateCorruptionError,
    StateManager,
    WALEntry,
)
from .tool_registry import (
    Tool,
    ToolCallValidation,
    ToolCategory,
    ToolExample,
    ToolMatch,
    ToolParameter,
    ToolRegistry,
)

__all__ = [
    # LLM Tracking
    "LLMTracker",
    "LLMCall",
    "CostReport",
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitState",
    "CircuitOpenError",
    # Retry
    "RetryPolicy",
    "RetryConfig",
    "RetryExhaustedError",
    # Prompts
    "PromptRegistry",
    "PromptVersion",
    # Human-in-the-loop
    "HumanCheckpoint",
    "CheckpointStatus",
    "CheckpointDecision",
    # Confidence
    "ConfidenceScorer",
    "ConfidenceResult",
    # Error Taxonomy
    "ErrorTaxonomy",
    "ClassifiedError",
    "ErrorCategory",
    "ErrorSeverity",
    # Fallback Chain
    "FallbackChain",
    "FallbackResult",
    "ModelConfig",
    "FallbackReason",
    "AllModelsFailedError",
    # Rate Limiter
    "RateLimiter",
    "RateLimitConfig",
    "TokenBucket",
    "RateLimitExceededError",
    "LimitScope",
    # Session Manager
    "SessionManager",
    "Session",
    "Message",
    "MessageRole",
    "SessionConfig",
    "TruncationStrategy",
    "ContextOverflowError",
    # Output Validator
    "OutputValidator",
    "ValidationResult",
    "ValidationError",
    "ToolCall",
    "ToolCallSchema",
    # State Manager
    "StateManager",
    "StateConfig",
    "Snapshot",
    "WALEntry",
    "StateCorruptionError",
    # Guardrails
    "Guardrails",
    "GuardrailConfig",
    "GuardrailResult",
    "Violation",
    "ViolationType",
    "ViolationAction",
    # Metrics Exporter
    "MetricsExporter",
    "MetricsRegistry",
    "Metric",
    "MetricType",
    # Tool Registry
    "ToolRegistry",
    "Tool",
    "ToolParameter",
    "ToolExample",
    "ToolMatch",
    "ToolCategory",
    "ToolCallValidation",
    # Memory Manager
    "MemoryManager",
    "Memory",
    "MemoryType",
    "MemoryPriority",
    "MemoryConfig",
    "RetrievalResult",
    "CompactionResult",
    "CompactionStrategy",
    # Agent Orchestrator
    "AgentOrchestrator",
    "Agent",
    "AgentCapability",
    "AgentStatus",
    "Task",
    "TaskStatus",
    "OrchestrationPattern",
    "OrchestrationResult",
    # Agent Evaluator
    "AgentEvaluator",
    "EvalCriteria",
    "TestCase",
    "EvalScore",
    "EvalResult",
    "EvalReport",
    "QualityMetrics",
    "ReviewItem",
    "EvalType",
    "ScoreType",
    "ReviewStatus",
    # OpenTelemetry Exporter
    "OTelExporter",
    "OTelConfig",
    "Span",
    "SpanContext",
    "SpanKind",
    "SpanStatus",
    "GenAIOperationType",
    "GenAIAttributes",
    # Decision Explainer
    "DecisionExplainer",
    "DecisionNode",
    "ExplanationChain",
    "Factor",
    "Alternative",
    "CounterfactualExplanation",
    "DecisionType",
    "ConfidenceLevel",
]

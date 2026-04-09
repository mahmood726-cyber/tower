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

from .llm_tracker import LLMTracker, LLMCall, CostReport
from .circuit_breaker import CircuitBreaker, CircuitState, CircuitOpenError
from .retry_policy import RetryPolicy, RetryConfig, RetryExhaustedError
from .prompt_registry import PromptRegistry, PromptVersion
from .human_checkpoint import HumanCheckpoint, CheckpointStatus, CheckpointDecision
from .confidence_scorer import ConfidenceScorer, ConfidenceResult
from .error_taxonomy import ErrorTaxonomy, ClassifiedError, ErrorCategory, ErrorSeverity
from .fallback_chain import FallbackChain, FallbackResult, ModelConfig, FallbackReason, AllModelsFailedError
from .rate_limiter import RateLimiter, RateLimitConfig, TokenBucket, RateLimitExceededError, LimitScope
from .session_manager import SessionManager, Session, Message, MessageRole, SessionConfig, TruncationStrategy, ContextOverflowError
from .output_validator import OutputValidator, ValidationResult, ValidationError, ToolCall, ToolCallSchema
from .state_manager import StateManager, StateConfig, Snapshot, WALEntry, StateCorruptionError
from .guardrails import Guardrails, GuardrailConfig, GuardrailResult, Violation, ViolationType, ViolationAction
from .metrics_exporter import MetricsExporter, MetricsRegistry, Metric, MetricType
from .tool_registry import ToolRegistry, Tool, ToolParameter, ToolExample, ToolMatch, ToolCategory, ToolCallValidation
from .memory_manager import MemoryManager, Memory, MemoryType, MemoryPriority, MemoryConfig, RetrievalResult, CompactionResult, CompactionStrategy
from .agent_orchestrator import AgentOrchestrator, Agent, AgentCapability, AgentStatus, Task, TaskStatus, OrchestrationPattern, OrchestrationResult
from .agent_evaluator import AgentEvaluator, EvalCriteria, TestCase, EvalScore, EvalResult, EvalReport, QualityMetrics, ReviewItem, EvalType, ScoreType, ReviewStatus
from .otel_exporter import OTelExporter, OTelConfig, Span, SpanContext, SpanKind, SpanStatus, GenAIOperationType, GenAIAttributes
from .decision_explainer import DecisionExplainer, DecisionNode, ExplanationChain, Factor, Alternative, CounterfactualExplanation, DecisionType, ConfidenceLevel

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

#!/usr/bin/env python3
"""
Structured Error Taxonomy for LLM Agent Analysis

Provides classification and categorization of errors with:
- Hierarchical error categories
- Root cause analysis hints
- Suggested remediation actions
- Severity levels
- Pattern matching for auto-classification
"""

from __future__ import annotations

import re
import sys
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


class ErrorCategory(Enum):
    """Primary error categories."""
    SYNTAX = "syntax"
    TYPE = "type"
    LOGIC = "logic"
    RUNTIME = "runtime"
    DEPENDENCY = "dependency"
    CONFIGURATION = "configuration"
    PERMISSION = "permission"
    NETWORK = "network"
    TIMEOUT = "timeout"
    RESOURCE = "resource"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """Error severity levels."""
    CRITICAL = "critical"     # System down, data loss risk
    HIGH = "high"             # Major feature broken
    MEDIUM = "medium"         # Feature degraded
    LOW = "low"               # Minor issue
    INFO = "info"             # Informational


class RemediationType(Enum):
    """Types of remediation actions."""
    AUTO_FIX = "auto_fix"           # Can be fixed automatically
    MANUAL_FIX = "manual_fix"       # Requires manual intervention
    RETRY = "retry"                 # Retry may resolve
    ESCALATE = "escalate"           # Needs human review
    IGNORE = "ignore"               # Can be safely ignored
    INVESTIGATE = "investigate"     # Needs investigation


@dataclass
class ErrorPattern:
    """Pattern for matching and classifying errors."""

    name: str
    category: ErrorCategory
    severity: ErrorSeverity
    pattern: str                    # Regex pattern
    subcategory: Optional[str] = None
    root_cause_hints: List[str] = field(default_factory=list)
    remediation_type: RemediationType = RemediationType.INVESTIGATE
    remediation_hints: List[str] = field(default_factory=list)
    auto_fixable: bool = False

    def __post_init__(self):
        self._compiled = re.compile(self.pattern, re.IGNORECASE | re.MULTILINE)

    def matches(self, error_text: str) -> Optional[re.Match]:
        """Check if pattern matches error text."""
        return self._compiled.search(error_text)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        d["severity"] = self.severity.value
        d["remediation_type"] = self.remediation_type.value
        del d["_compiled"]
        return d


@dataclass
class ClassifiedError:
    """A classified error with full context."""

    error_id: str
    original_text: str
    category: ErrorCategory
    subcategory: Optional[str]
    severity: ErrorSeverity
    pattern_name: Optional[str]
    root_cause_hints: List[str]
    remediation_type: RemediationType
    remediation_hints: List[str]
    auto_fixable: bool
    confidence: float               # Classification confidence 0-1
    timestamp: str
    card_id: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        d["severity"] = self.severity.value
        d["remediation_type"] = self.remediation_type.value
        return d


# Default error patterns
DEFAULT_PATTERNS: List[ErrorPattern] = [
    # Syntax errors
    ErrorPattern(
        name="python_syntax_error",
        category=ErrorCategory.SYNTAX,
        severity=ErrorSeverity.HIGH,
        pattern=r"SyntaxError:\s*(.+)",
        subcategory="python",
        root_cause_hints=["Check for missing colons, brackets, or quotes", "Verify indentation"],
        remediation_type=RemediationType.AUTO_FIX,
        remediation_hints=["Fix syntax at indicated line", "Check surrounding context"],
        auto_fixable=True,
    ),
    ErrorPattern(
        name="indentation_error",
        category=ErrorCategory.SYNTAX,
        severity=ErrorSeverity.HIGH,
        pattern=r"IndentationError:\s*(.+)",
        subcategory="python",
        root_cause_hints=["Mixed tabs and spaces", "Incorrect indentation level"],
        remediation_type=RemediationType.AUTO_FIX,
        remediation_hints=["Use consistent indentation (4 spaces)", "Check block alignment"],
        auto_fixable=True,
    ),
    ErrorPattern(
        name="json_parse_error",
        category=ErrorCategory.SYNTAX,
        severity=ErrorSeverity.MEDIUM,
        pattern=r"JSON(Decode)?Error|json\.decoder\.JSONDecodeError",
        subcategory="json",
        root_cause_hints=["Malformed JSON", "Trailing commas", "Unquoted keys"],
        remediation_type=RemediationType.AUTO_FIX,
        remediation_hints=["Validate JSON structure", "Remove trailing commas"],
        auto_fixable=True,
    ),

    # Type errors
    ErrorPattern(
        name="type_error",
        category=ErrorCategory.TYPE,
        severity=ErrorSeverity.HIGH,
        pattern=r"TypeError:\s*(.+)",
        subcategory="python",
        root_cause_hints=["Wrong argument type", "Missing method", "None value access"],
        remediation_type=RemediationType.MANUAL_FIX,
        remediation_hints=["Check variable types", "Add type guards", "Handle None cases"],
        auto_fixable=False,
    ),
    ErrorPattern(
        name="attribute_error",
        category=ErrorCategory.TYPE,
        severity=ErrorSeverity.HIGH,
        pattern=r"AttributeError:\s*(.+)",
        subcategory="python",
        root_cause_hints=["Object doesn't have attribute", "Typo in attribute name", "None object access"],
        remediation_type=RemediationType.MANUAL_FIX,
        remediation_hints=["Check object type", "Use hasattr() guard", "Handle None"],
        auto_fixable=False,
    ),

    # Runtime errors
    ErrorPattern(
        name="key_error",
        category=ErrorCategory.RUNTIME,
        severity=ErrorSeverity.MEDIUM,
        pattern=r"KeyError:\s*(.+)",
        subcategory="python",
        root_cause_hints=["Missing dictionary key", "Typo in key name"],
        remediation_type=RemediationType.MANUAL_FIX,
        remediation_hints=["Use .get() with default", "Check key exists first"],
        auto_fixable=False,
    ),
    ErrorPattern(
        name="index_error",
        category=ErrorCategory.RUNTIME,
        severity=ErrorSeverity.MEDIUM,
        pattern=r"IndexError:\s*(.+)",
        subcategory="python",
        root_cause_hints=["List index out of range", "Empty list access"],
        remediation_type=RemediationType.MANUAL_FIX,
        remediation_hints=["Check list length first", "Handle empty lists"],
        auto_fixable=False,
    ),
    ErrorPattern(
        name="value_error",
        category=ErrorCategory.RUNTIME,
        severity=ErrorSeverity.MEDIUM,
        pattern=r"ValueError:\s*(.+)",
        subcategory="python",
        root_cause_hints=["Invalid value for operation", "Conversion failure"],
        remediation_type=RemediationType.MANUAL_FIX,
        remediation_hints=["Validate input before operation", "Add try/except"],
        auto_fixable=False,
    ),
    ErrorPattern(
        name="zero_division",
        category=ErrorCategory.RUNTIME,
        severity=ErrorSeverity.MEDIUM,
        pattern=r"ZeroDivisionError",
        subcategory="python",
        root_cause_hints=["Division by zero", "Modulo by zero"],
        remediation_type=RemediationType.AUTO_FIX,
        remediation_hints=["Add zero check before division"],
        auto_fixable=True,
    ),

    # Dependency errors
    ErrorPattern(
        name="import_error",
        category=ErrorCategory.DEPENDENCY,
        severity=ErrorSeverity.HIGH,
        pattern=r"(Import|Module)Error:\s*(.+)",
        subcategory="python",
        root_cause_hints=["Package not installed", "Wrong package name", "Circular import"],
        remediation_type=RemediationType.MANUAL_FIX,
        remediation_hints=["Install missing package", "Check package name", "Fix import order"],
        auto_fixable=False,
    ),
    ErrorPattern(
        name="npm_not_found",
        category=ErrorCategory.DEPENDENCY,
        severity=ErrorSeverity.HIGH,
        pattern=r"Cannot find module '([^']+)'|Module not found",
        subcategory="npm",
        root_cause_hints=["Package not installed", "Wrong import path"],
        remediation_type=RemediationType.MANUAL_FIX,
        remediation_hints=["Run npm install", "Check import path"],
        auto_fixable=False,
    ),

    # Permission errors
    ErrorPattern(
        name="permission_denied",
        category=ErrorCategory.PERMISSION,
        severity=ErrorSeverity.HIGH,
        pattern=r"Permission(Error| denied)|EACCES|Access is denied",
        subcategory="filesystem",
        root_cause_hints=["Insufficient file permissions", "File in use", "Admin required"],
        remediation_type=RemediationType.ESCALATE,
        remediation_hints=["Check file permissions", "Run with elevated privileges"],
        auto_fixable=False,
    ),

    # Network errors
    ErrorPattern(
        name="connection_error",
        category=ErrorCategory.NETWORK,
        severity=ErrorSeverity.MEDIUM,
        pattern=r"Connection(Error|Refused|Reset)|ECONNREFUSED|ECONNRESET",
        subcategory="connection",
        root_cause_hints=["Service unavailable", "Network issue", "Firewall blocking"],
        remediation_type=RemediationType.RETRY,
        remediation_hints=["Check service status", "Retry with backoff"],
        auto_fixable=False,
    ),
    ErrorPattern(
        name="dns_error",
        category=ErrorCategory.NETWORK,
        severity=ErrorSeverity.MEDIUM,
        pattern=r"getaddrinfo|Name or service not known|ENOTFOUND",
        subcategory="dns",
        root_cause_hints=["DNS resolution failed", "Invalid hostname"],
        remediation_type=RemediationType.INVESTIGATE,
        remediation_hints=["Check hostname", "Verify DNS settings"],
        auto_fixable=False,
    ),

    # Timeout errors
    ErrorPattern(
        name="timeout",
        category=ErrorCategory.TIMEOUT,
        severity=ErrorSeverity.MEDIUM,
        pattern=r"Timeout|timed? ?out|ETIMEDOUT",
        subcategory="general",
        root_cause_hints=["Operation took too long", "Resource unavailable"],
        remediation_type=RemediationType.RETRY,
        remediation_hints=["Increase timeout", "Retry with backoff", "Check resource health"],
        auto_fixable=False,
    ),

    # Resource errors
    ErrorPattern(
        name="out_of_memory",
        category=ErrorCategory.RESOURCE,
        severity=ErrorSeverity.CRITICAL,
        pattern=r"Out of memory|MemoryError|ENOMEM|heap out of memory",
        subcategory="memory",
        root_cause_hints=["Insufficient memory", "Memory leak", "Large data structure"],
        remediation_type=RemediationType.ESCALATE,
        remediation_hints=["Reduce memory usage", "Process data in chunks", "Add more memory"],
        auto_fixable=False,
    ),
    ErrorPattern(
        name="disk_full",
        category=ErrorCategory.RESOURCE,
        severity=ErrorSeverity.CRITICAL,
        pattern=r"No space left|ENOSPC|disk full",
        subcategory="disk",
        root_cause_hints=["Disk is full", "Quota exceeded"],
        remediation_type=RemediationType.ESCALATE,
        remediation_hints=["Free disk space", "Increase quota"],
        auto_fixable=False,
    ),

    # Validation errors
    ErrorPattern(
        name="assertion_error",
        category=ErrorCategory.VALIDATION,
        severity=ErrorSeverity.HIGH,
        pattern=r"AssertionError:\s*(.+)?",
        subcategory="assertion",
        root_cause_hints=["Assertion condition failed", "Invariant violated"],
        remediation_type=RemediationType.INVESTIGATE,
        remediation_hints=["Check assertion condition", "Review input values"],
        auto_fixable=False,
    ),
    ErrorPattern(
        name="schema_validation",
        category=ErrorCategory.VALIDATION,
        severity=ErrorSeverity.MEDIUM,
        pattern=r"ValidationError|Schema.*(error|invalid)|Invalid.*schema",
        subcategory="schema",
        root_cause_hints=["Data doesn't match schema", "Missing required field"],
        remediation_type=RemediationType.AUTO_FIX,
        remediation_hints=["Check schema requirements", "Add missing fields"],
        auto_fixable=True,
    ),
]


class ErrorTaxonomy:
    """
    Structured error classification system.

    Features:
    - Pattern-based error classification
    - Hierarchical categories and subcategories
    - Root cause hints and remediation suggestions
    - Severity assessment
    - Auto-fix detection
    - Custom pattern support
    """

    def __init__(
        self,
        patterns: Optional[List[ErrorPattern]] = None,
        ledger: Optional[EventLogger] = None,
    ):
        """
        Initialize error taxonomy.

        Args:
            patterns: Custom patterns (default patterns added automatically)
            ledger: Optional EventLogger for tracking
        """
        self.patterns = list(DEFAULT_PATTERNS)
        if patterns:
            self.patterns.extend(patterns)

        self.ledger = ledger
        self._error_counter = 0

    def _generate_error_id(self) -> str:
        """Generate unique error ID."""
        ts = _now_utc().strftime("%Y%m%d%H%M%S")
        self._error_counter += 1
        return f"err_{ts}_{self._error_counter:04d}"

    def add_pattern(self, pattern: ErrorPattern) -> None:
        """Add a custom error pattern."""
        self.patterns.append(pattern)

    def classify(
        self,
        error_text: str,
        card_id: Optional[str] = None,
        file_path: Optional[str] = None,
        line_number: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ClassifiedError:
        """
        Classify an error based on its text.

        Args:
            error_text: The error message/traceback
            card_id: Optional card ID
            file_path: Optional source file path
            line_number: Optional line number
            metadata: Optional additional metadata

        Returns:
            ClassifiedError with full classification
        """
        best_match: Optional[Tuple[ErrorPattern, re.Match]] = None
        best_confidence = 0.0

        # Try all patterns
        for pattern in self.patterns:
            match = pattern.matches(error_text)
            if match:
                # Calculate confidence based on match specificity
                confidence = len(match.group(0)) / len(error_text) if error_text else 0
                confidence = min(confidence * 2, 1.0)  # Scale up

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = (pattern, match)

        # Build classified error
        if best_match:
            pattern, match = best_match
            classified = ClassifiedError(
                error_id=self._generate_error_id(),
                original_text=error_text,
                category=pattern.category,
                subcategory=pattern.subcategory,
                severity=pattern.severity,
                pattern_name=pattern.name,
                root_cause_hints=list(pattern.root_cause_hints),
                remediation_type=pattern.remediation_type,
                remediation_hints=list(pattern.remediation_hints),
                auto_fixable=pattern.auto_fixable,
                confidence=best_confidence,
                timestamp=_now_utc().isoformat(),
                card_id=card_id,
                file_path=file_path,
                line_number=line_number,
                metadata=metadata or {},
            )
        else:
            # Unknown error
            classified = ClassifiedError(
                error_id=self._generate_error_id(),
                original_text=error_text,
                category=ErrorCategory.UNKNOWN,
                subcategory=None,
                severity=ErrorSeverity.MEDIUM,
                pattern_name=None,
                root_cause_hints=["Error pattern not recognized"],
                remediation_type=RemediationType.INVESTIGATE,
                remediation_hints=["Review error message manually", "Add pattern if recurring"],
                auto_fixable=False,
                confidence=0.0,
                timestamp=_now_utc().isoformat(),
                card_id=card_id,
                file_path=file_path,
                line_number=line_number,
                metadata=metadata or {},
            )

        # Log if ledger available
        if self.ledger:
            self.ledger.log(
                event_type="error.classified",
                card_id=card_id,
                actor="error_taxonomy",
                data={
                    "error_id": classified.error_id,
                    "category": classified.category.value,
                    "severity": classified.severity.value,
                    "pattern_name": classified.pattern_name,
                    "auto_fixable": classified.auto_fixable,
                    "confidence": classified.confidence,
                },
            )

        return classified

    def classify_batch(
        self,
        errors: List[str],
        card_id: Optional[str] = None,
    ) -> List[ClassifiedError]:
        """Classify multiple errors."""
        return [self.classify(e, card_id=card_id) for e in errors]

    def get_auto_fixable(
        self,
        classified_errors: List[ClassifiedError],
    ) -> List[ClassifiedError]:
        """Filter to only auto-fixable errors."""
        return [e for e in classified_errors if e.auto_fixable]

    def get_by_severity(
        self,
        classified_errors: List[ClassifiedError],
        min_severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    ) -> List[ClassifiedError]:
        """Filter errors by minimum severity."""
        severity_order = {
            ErrorSeverity.INFO: 0,
            ErrorSeverity.LOW: 1,
            ErrorSeverity.MEDIUM: 2,
            ErrorSeverity.HIGH: 3,
            ErrorSeverity.CRITICAL: 4,
        }

        min_level = severity_order[min_severity]
        return [
            e for e in classified_errors
            if severity_order[e.severity] >= min_level
        ]

    def get_summary(
        self,
        classified_errors: List[ClassifiedError],
    ) -> Dict[str, Any]:
        """Get summary statistics for classified errors."""
        by_category: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        auto_fixable_count = 0

        for error in classified_errors:
            cat = error.category.value
            sev = error.severity.value

            by_category[cat] = by_category.get(cat, 0) + 1
            by_severity[sev] = by_severity.get(sev, 0) + 1

            if error.auto_fixable:
                auto_fixable_count += 1

        return {
            "total_errors": len(classified_errors),
            "by_category": by_category,
            "by_severity": by_severity,
            "auto_fixable_count": auto_fixable_count,
            "auto_fixable_pct": (
                auto_fixable_count / len(classified_errors) * 100
                if classified_errors else 0
            ),
        }

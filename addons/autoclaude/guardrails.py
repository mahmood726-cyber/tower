#!/usr/bin/env python3
"""
Guardrails for Safety Filtering

Provides input/output safety filtering with:
- PII detection and redaction
- Injection attack detection
- Harmful content filtering
- Tool call safety validation
- Configurable allow/deny lists
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Pattern, Set, Tuple

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


class ViolationType(Enum):
    """Types of guardrail violations."""
    PII_DETECTED = "pii_detected"
    INJECTION_DETECTED = "injection_detected"
    HARMFUL_CONTENT = "harmful_content"
    BLOCKED_TOOL = "blocked_tool"
    BLOCKED_PATH = "blocked_path"
    BLOCKED_DOMAIN = "blocked_domain"
    SENSITIVE_DATA = "sensitive_data"
    RATE_VIOLATION = "rate_violation"
    CUSTOM_RULE = "custom_rule"


class ViolationAction(Enum):
    """Action to take on violation."""
    BLOCK = "block"       # Block the request entirely
    REDACT = "redact"     # Redact sensitive content
    WARN = "warn"         # Log warning but allow
    AUDIT = "audit"       # Log for audit only


class Severity(Enum):
    """Severity of violation."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def ordinal(self) -> int:
        """Numeric severity for comparison (higher = more severe)."""
        return _SEVERITY_ORDER[self]


_SEVERITY_ORDER = {
    Severity.LOW: 0,
    Severity.MEDIUM: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}


@dataclass
class Violation:
    """A detected guardrail violation."""

    violation_type: ViolationType
    severity: Severity
    message: str
    action: ViolationAction
    matched_content: Optional[str] = None
    redacted_content: Optional[str] = None
    rule_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["violation_type"] = self.violation_type.value
        d["severity"] = self.severity.value
        d["action"] = self.action.value
        return d


@dataclass
class GuardrailResult:
    """Result of guardrail check."""

    passed: bool
    violations: List[Violation] = field(default_factory=list)
    original_content: str = ""
    filtered_content: str = ""
    blocked: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "violations": [v.to_dict() for v in self.violations],
            "blocked": self.blocked,
            "violation_count": len(self.violations),
        }


@dataclass
class PIIPattern:
    """Pattern for detecting PII."""

    name: str
    pattern: Pattern
    severity: Severity = Severity.HIGH
    action: ViolationAction = ViolationAction.REDACT
    replacement: str = "[REDACTED]"


@dataclass
class GuardrailConfig:
    """Configuration for guardrails."""

    # PII detection
    detect_pii: bool = True
    pii_action: ViolationAction = ViolationAction.REDACT

    # Injection detection
    detect_injection: bool = True
    injection_action: ViolationAction = ViolationAction.BLOCK

    # Tool safety
    blocked_tools: Set[str] = field(default_factory=set)
    allowed_tools: Optional[Set[str]] = None  # If set, only these allowed

    # Path safety
    blocked_paths: List[str] = field(default_factory=list)
    allowed_paths: Optional[List[str]] = None

    # Domain safety
    blocked_domains: Set[str] = field(default_factory=set)
    allowed_domains: Optional[Set[str]] = None

    # Content filtering
    blocked_phrases: Set[str] = field(default_factory=set)
    blocked_patterns: List[Pattern] = field(default_factory=list)

    # Severity threshold
    min_severity_to_block: Severity = Severity.HIGH


class Guardrails:
    """
    Safety filtering for LLM inputs and outputs.

    Features:
    - PII detection and redaction
    - Injection attack detection
    - Tool call validation
    - Path and domain restrictions
    - Custom rule support
    """

    # Default PII patterns
    DEFAULT_PII_PATTERNS = [
        PIIPattern(
            name="email",
            pattern=re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
            severity=Severity.MEDIUM,
            replacement="[EMAIL]",
        ),
        PIIPattern(
            name="phone_us",
            pattern=re.compile(r"\b(?:\+1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b"),
            severity=Severity.MEDIUM,
            replacement="[PHONE]",
        ),
        PIIPattern(
            name="ssn",
            pattern=re.compile(
                r"\b(?!000|666|9\d\d)"       # area: not 000, 666, 900-999
                r"\d{3}"                       # area: 3 digits
                r"[-.\s]?"                     # optional separator
                r"(?!00)\d{2}"                 # group: 2 digits, not 00
                r"[-.\s]?"                     # optional separator
                r"(?!0000)\d{4}\b"             # serial: 4 digits, not 0000
            ),
            severity=Severity.CRITICAL,
            replacement="[SSN]",
        ),
        PIIPattern(
            name="credit_card",
            pattern=re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b"),
            severity=Severity.CRITICAL,
            replacement="[CREDIT_CARD]",
        ),
        PIIPattern(
            name="ip_address",
            pattern=re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
            severity=Severity.LOW,
            replacement="[IP]",
        ),
        PIIPattern(
            name="api_key",
            pattern=re.compile(r"\b(?:sk-|pk_|api[_-]?key[=:]\s*)[a-zA-Z0-9_-]{20,}\b", re.IGNORECASE),
            severity=Severity.CRITICAL,
            replacement="[API_KEY]",
        ),
        PIIPattern(
            name="password",
            pattern=re.compile(r"(?:password|passwd|pwd)[=:\s]+['\"]?[^\s'\"]{8,}['\"]?", re.IGNORECASE),
            severity=Severity.CRITICAL,
            replacement="[PASSWORD]",
        ),
        PIIPattern(
            name="aws_key",
            pattern=re.compile(r"\b(?:AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}\b"),
            severity=Severity.CRITICAL,
            replacement="[AWS_KEY]",
        ),
    ]

    # Injection patterns
    INJECTION_PATTERNS = [
        (re.compile(r"ignore\s+(?:all\s+)?(?:previous|above|prior)\s+instructions?", re.IGNORECASE), "instruction_override"),
        (re.compile(r"you\s+are\s+now\s+(?:a|an|the)\s+", re.IGNORECASE), "role_hijack"),
        (re.compile(r"system\s*:\s*", re.IGNORECASE), "fake_system_prompt"),
        (re.compile(r"<\s*(?:system|admin|root)\s*>", re.IGNORECASE), "fake_xml_role"),
        (re.compile(r"pretend\s+(?:you\s+are|to\s+be|that)", re.IGNORECASE), "role_pretend"),
        (re.compile(r"forget\s+(?:all|everything|your)", re.IGNORECASE), "memory_wipe"),
        (re.compile(r"jailbreak|DAN\s+mode|developer\s+mode", re.IGNORECASE), "jailbreak_attempt"),
        (re.compile(r"(?:do\s+not|don't)\s+(?:follow|obey)\s+(?:your|the)\s+(?:rules|guidelines)", re.IGNORECASE), "rule_override"),
    ]

    # Dangerous file operations
    DANGEROUS_PATHS = [
        "/etc/passwd",
        "/etc/shadow",
        "~/.ssh/",
        "~/.aws/",
        ".env",
        ".git/config",
        "id_rsa",
        "id_ed25519",
    ]

    # Dangerous tools
    DANGEROUS_TOOLS = {
        "rm", "rmdir", "del", "format",
        "dd", "mkfs", "fdisk",
        "shutdown", "reboot", "halt",
        "chmod 777", "chmod -R",
    }

    def __init__(
        self,
        config: Optional[GuardrailConfig] = None,
        custom_pii_patterns: Optional[List[PIIPattern]] = None,
        custom_rules: Optional[List[Callable[[str], Optional[Violation]]]] = None,
        ledger: Optional[EventLogger] = None,
    ):
        """
        Initialize guardrails.

        Args:
            config: Guardrail configuration
            custom_pii_patterns: Additional PII patterns
            custom_rules: Custom validation functions
            ledger: Optional EventLogger
        """
        self.config = config or GuardrailConfig()
        self.ledger = ledger
        self.custom_rules = custom_rules or []

        # Build PII patterns
        self.pii_patterns = list(self.DEFAULT_PII_PATTERNS)
        if custom_pii_patterns:
            self.pii_patterns.extend(custom_pii_patterns)

        # Add default dangerous paths if not overridden
        if not self.config.blocked_paths:
            self.config.blocked_paths = list(self.DANGEROUS_PATHS)

    def _log_event(
        self,
        event_type: str,
        card_id: Optional[str],
        data: Dict[str, Any],
    ) -> None:
        """Log guardrail event."""
        if self.ledger:
            self.ledger.log(
                event_type=f"guardrail.{event_type}",
                card_id=card_id,
                actor="guardrails",
                data=data,
            )

    def _detect_pii(self, content: str) -> Tuple[List[Violation], str]:
        """Detect and optionally redact PII."""
        violations = []
        filtered = content

        for pattern in self.pii_patterns:
            matches = pattern.pattern.findall(content)

            for match in matches:
                violations.append(Violation(
                    violation_type=ViolationType.PII_DETECTED,
                    severity=pattern.severity,
                    message=f"Detected {pattern.name}",
                    action=pattern.action,
                    matched_content=match[:20] + "..." if len(match) > 20 else match,
                    rule_name=pattern.name,
                ))

                if pattern.action == ViolationAction.REDACT:
                    filtered = pattern.pattern.sub(pattern.replacement, filtered)

        return violations, filtered

    def _detect_injection(self, content: str) -> List[Violation]:
        """Detect injection attacks."""
        violations = []

        for pattern, name in self.INJECTION_PATTERNS:
            if pattern.search(content):
                violations.append(Violation(
                    violation_type=ViolationType.INJECTION_DETECTED,
                    severity=Severity.HIGH,
                    message=f"Detected injection attempt: {name}",
                    action=self.config.injection_action,
                    rule_name=name,
                ))

        return violations

    def _check_blocked_content(self, content: str) -> List[Violation]:
        """Check for blocked phrases and patterns."""
        violations = []
        lower_content = content.lower()

        # Check blocked phrases
        for phrase in self.config.blocked_phrases:
            if phrase.lower() in lower_content:
                violations.append(Violation(
                    violation_type=ViolationType.HARMFUL_CONTENT,
                    severity=Severity.MEDIUM,
                    message=f"Blocked phrase detected",
                    action=ViolationAction.BLOCK,
                    matched_content=phrase,
                ))

        # Check blocked patterns
        for pattern in self.config.blocked_patterns:
            if pattern.search(content):
                violations.append(Violation(
                    violation_type=ViolationType.HARMFUL_CONTENT,
                    severity=Severity.MEDIUM,
                    message=f"Blocked pattern matched",
                    action=ViolationAction.BLOCK,
                    rule_name=pattern.pattern,
                ))

        return violations

    def check_input(
        self,
        content: str,
        card_id: Optional[str] = None,
    ) -> GuardrailResult:
        """
        Check input content for violations.

        Args:
            content: Input to check
            card_id: Optional card ID for logging

        Returns:
            GuardrailResult with violations and filtered content
        """
        result = GuardrailResult(
            passed=True,
            original_content=content,
            filtered_content=content,
        )

        # PII detection
        if self.config.detect_pii:
            pii_violations, filtered = self._detect_pii(content)
            result.violations.extend(pii_violations)
            result.filtered_content = filtered

        # Injection detection
        if self.config.detect_injection:
            injection_violations = self._detect_injection(content)
            result.violations.extend(injection_violations)

        # Blocked content
        blocked_violations = self._check_blocked_content(content)
        result.violations.extend(blocked_violations)

        # Custom rules
        for rule in self.custom_rules:
            violation = rule(content)
            if violation:
                result.violations.append(violation)

        # Determine if blocked
        for v in result.violations:
            if v.action == ViolationAction.BLOCK:
                if v.severity.ordinal >= self.config.min_severity_to_block.ordinal:
                    result.blocked = True
                    result.passed = False
                    break

        if result.violations:
            self._log_event("input_checked", card_id, {
                "violation_count": len(result.violations),
                "blocked": result.blocked,
                "types": list(set(v.violation_type.value for v in result.violations)),
            })

        return result

    def check_output(
        self,
        content: str,
        card_id: Optional[str] = None,
    ) -> GuardrailResult:
        """
        Check output content for violations.

        Similar to check_input but focused on output-specific issues.
        """
        result = GuardrailResult(
            passed=True,
            original_content=content,
            filtered_content=content,
        )

        # PII detection (especially important in outputs)
        if self.config.detect_pii:
            pii_violations, filtered = self._detect_pii(content)
            result.violations.extend(pii_violations)
            result.filtered_content = filtered

        # Blocked content
        blocked_violations = self._check_blocked_content(content)
        result.violations.extend(blocked_violations)

        # Custom rules
        for rule in self.custom_rules:
            violation = rule(content)
            if violation:
                result.violations.append(violation)

        # Determine if blocked
        for v in result.violations:
            if v.action == ViolationAction.BLOCK:
                if v.severity.ordinal >= self.config.min_severity_to_block.ordinal:
                    result.blocked = True
                    result.passed = False
                    break

        if result.violations:
            self._log_event("output_checked", card_id, {
                "violation_count": len(result.violations),
                "blocked": result.blocked,
            })

        return result

    def check_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        card_id: Optional[str] = None,
    ) -> GuardrailResult:
        """
        Check if a tool call is safe.

        Args:
            tool_name: Name of tool being called
            arguments: Tool arguments
            card_id: Optional card ID

        Returns:
            GuardrailResult
        """
        result = GuardrailResult(passed=True)

        # Check blocked tools
        if tool_name in self.config.blocked_tools:
            result.violations.append(Violation(
                violation_type=ViolationType.BLOCKED_TOOL,
                severity=Severity.HIGH,
                message=f"Tool '{tool_name}' is blocked",
                action=ViolationAction.BLOCK,
                matched_content=tool_name,
            ))
            result.blocked = True
            result.passed = False

        # Check allowed tools
        if self.config.allowed_tools is not None:
            if tool_name not in self.config.allowed_tools:
                result.violations.append(Violation(
                    violation_type=ViolationType.BLOCKED_TOOL,
                    severity=Severity.HIGH,
                    message=f"Tool '{tool_name}' is not in allowed list",
                    action=ViolationAction.BLOCK,
                    matched_content=tool_name,
                ))
                result.blocked = True
                result.passed = False

        # Check dangerous tool patterns
        for dangerous in self.DANGEROUS_TOOLS:
            if dangerous in tool_name.lower():
                result.violations.append(Violation(
                    violation_type=ViolationType.BLOCKED_TOOL,
                    severity=Severity.CRITICAL,
                    message=f"Dangerous tool pattern detected: {dangerous}",
                    action=ViolationAction.BLOCK,
                    matched_content=tool_name,
                ))
                result.blocked = True
                result.passed = False

        # Check path arguments
        for key, value in arguments.items():
            if isinstance(value, str):
                path_result = self._check_path_safety(value)
                result.violations.extend(path_result.violations)
                if path_result.blocked:
                    result.blocked = True
                    result.passed = False

        if result.violations:
            self._log_event("tool_checked", card_id, {
                "tool": tool_name,
                "blocked": result.blocked,
                "violation_count": len(result.violations),
            })

        return result

    def _check_path_safety(self, path: str) -> GuardrailResult:
        """Check if a path is safe to access."""
        result = GuardrailResult(passed=True)

        # Normalize path
        path_lower = path.lower().replace("\\", "/")

        # Check blocked paths
        for blocked in self.config.blocked_paths:
            if blocked.lower() in path_lower:
                result.violations.append(Violation(
                    violation_type=ViolationType.BLOCKED_PATH,
                    severity=Severity.HIGH,
                    message=f"Blocked path pattern: {blocked}",
                    action=ViolationAction.BLOCK,
                    matched_content=path,
                ))
                result.blocked = True
                result.passed = False

        # Check allowed paths
        if self.config.allowed_paths is not None:
            allowed = False
            for allowed_path in self.config.allowed_paths:
                if path_lower.startswith(allowed_path.lower()):
                    allowed = True
                    break

            if not allowed:
                result.violations.append(Violation(
                    violation_type=ViolationType.BLOCKED_PATH,
                    severity=Severity.HIGH,
                    message="Path not in allowed list",
                    action=ViolationAction.BLOCK,
                    matched_content=path,
                ))
                result.blocked = True
                result.passed = False

        # Check path traversal
        if ".." in path:
            result.violations.append(Violation(
                violation_type=ViolationType.BLOCKED_PATH,
                severity=Severity.HIGH,
                message="Path traversal detected",
                action=ViolationAction.BLOCK,
                matched_content=path,
            ))
            result.blocked = True
            result.passed = False

        return result

    def check_url(
        self,
        url: str,
        card_id: Optional[str] = None,
    ) -> GuardrailResult:
        """Check if a URL is safe to access."""
        result = GuardrailResult(passed=True)

        # Extract domain
        domain_match = re.search(r"(?:https?://)?([^/]+)", url)
        if not domain_match:
            return result

        domain = domain_match.group(1).lower()

        # Check blocked domains
        for blocked in self.config.blocked_domains:
            if blocked.lower() in domain:
                result.violations.append(Violation(
                    violation_type=ViolationType.BLOCKED_DOMAIN,
                    severity=Severity.MEDIUM,
                    message=f"Blocked domain: {blocked}",
                    action=ViolationAction.BLOCK,
                    matched_content=domain,
                ))
                result.blocked = True
                result.passed = False

        # Check allowed domains
        if self.config.allowed_domains is not None:
            if domain not in self.config.allowed_domains:
                result.violations.append(Violation(
                    violation_type=ViolationType.BLOCKED_DOMAIN,
                    severity=Severity.MEDIUM,
                    message="Domain not in allowed list",
                    action=ViolationAction.BLOCK,
                    matched_content=domain,
                ))
                result.blocked = True
                result.passed = False

        if result.violations:
            self._log_event("url_checked", card_id, {
                "domain": domain,
                "blocked": result.blocked,
            })

        return result

    def redact_pii(self, content: str) -> str:
        """Redact PII from content without full check."""
        _, filtered = self._detect_pii(content)
        return filtered

    def add_blocked_phrase(self, phrase: str) -> None:
        """Add a phrase to the block list."""
        self.config.blocked_phrases.add(phrase)

    def add_blocked_tool(self, tool: str) -> None:
        """Add a tool to the block list."""
        self.config.blocked_tools.add(tool)

    def add_blocked_domain(self, domain: str) -> None:
        """Add a domain to the block list."""
        self.config.blocked_domains.add(domain)


# Convenience functions
def create_guardrails(
    ledger: Optional[EventLogger] = None,
    strict: bool = False,
) -> Guardrails:
    """Create guardrails with default or strict configuration."""
    if strict:
        config = GuardrailConfig(
            detect_pii=True,
            pii_action=ViolationAction.BLOCK,
            detect_injection=True,
            injection_action=ViolationAction.BLOCK,
            min_severity_to_block=Severity.MEDIUM,
        )
    else:
        config = GuardrailConfig()

    return Guardrails(config=config, ledger=ledger)


def redact_pii(content: str) -> str:
    """Quick PII redaction."""
    guardrails = Guardrails()
    return guardrails.redact_pii(content)


def check_safe(content: str) -> bool:
    """Quick safety check."""
    guardrails = Guardrails()
    result = guardrails.check_input(content)
    return result.passed

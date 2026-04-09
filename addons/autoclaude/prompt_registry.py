#!/usr/bin/env python3
"""
Prompt Registry for Version Control

Provides version-controlled prompt management with:
- Content-addressable storage (hash-based IDs)
- Version history tracking
- A/B testing support
- Template variable validation
- Audit trail for prompt changes
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Paths
SCRIPT_DIR = Path(__file__).parent.resolve()
TOWER_ROOT = SCRIPT_DIR.parent.parent
CONTROL_DIR = TOWER_ROOT / "control"
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


@dataclass
class PromptVersion:
    """A versioned prompt template."""

    prompt_id: str                      # Content hash (first 12 chars of SHA-256)
    name: str                           # Human-readable name
    version: int                        # Sequential version number
    template: str                       # Prompt template with {variables}
    variables: List[str]                # Required template variables
    created_at: str                     # ISO timestamp
    created_by: str                     # Author/system identifier
    description: Optional[str] = None   # Description of changes
    tags: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None     # Previous version's prompt_id
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def render(self, **kwargs: Any) -> str:
        """
        Render the prompt with provided variables.

        Args:
            **kwargs: Variable values to substitute

        Returns:
            Rendered prompt string

        Raises:
            ValueError: If required variables are missing
        """
        missing = set(self.variables) - set(kwargs.keys())
        if missing:
            raise ValueError(f"Missing required variables: {missing}")

        result = self.template
        for var, value in kwargs.items():
            result = result.replace(f"{{{var}}}", str(value))

        return result


@dataclass
class PromptUsage:
    """Record of prompt usage."""

    prompt_id: str
    timestamp: str
    card_id: Optional[str]
    session_id: Optional[str]
    variables: Dict[str, Any]
    outcome: Optional[str] = None  # success, failure, etc.

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PromptRegistry:
    """
    Version-controlled prompt registry.

    Features:
    - Content-addressable storage using SHA-256 hashes
    - Full version history with parent tracking
    - Template variable extraction and validation
    - Usage tracking for A/B testing
    - Audit trail for all changes
    """

    # Pattern to extract template variables like {variable_name}
    _VAR_PATTERN = re.compile(r'\{(\w+)\}')

    def __init__(
        self,
        registry_path: Optional[str] = None,
        ledger: Optional[EventLogger] = None,
    ):
        """
        Initialize prompt registry.

        Args:
            registry_path: Path to registry JSON file
            ledger: Optional EventLogger for audit trail
        """
        if registry_path:
            self.registry_path = Path(registry_path)
        else:
            self.registry_path = CONTROL_DIR / "prompt_registry.json"

        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        self.ledger = ledger
        self._prompts: Dict[str, PromptVersion] = {}  # prompt_id -> PromptVersion
        self._by_name: Dict[str, List[str]] = {}      # name -> [prompt_ids by version]
        self._usage: List[PromptUsage] = []

        self._load()

    def _compute_hash(self, template: str) -> str:
        """Compute content hash for a template."""
        normalized = template.strip()
        full_hash = hashlib.sha256(normalized.encode()).hexdigest()
        return full_hash[:12]  # First 12 chars for readability

    def _extract_variables(self, template: str) -> List[str]:
        """Extract variable names from template."""
        return sorted(set(self._VAR_PATTERN.findall(template)))

    def _load(self) -> None:
        """Load registry from file."""
        if not self.registry_path.exists():
            return

        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for prompt_data in data.get("prompts", []):
                prompt = PromptVersion(**prompt_data)
                self._prompts[prompt.prompt_id] = prompt

                if prompt.name not in self._by_name:
                    self._by_name[prompt.name] = []
                self._by_name[prompt.name].append(prompt.prompt_id)

            # Sort by version
            for name in self._by_name:
                self._by_name[name].sort(
                    key=lambda pid: self._prompts[pid].version
                )

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            # Start fresh on corrupt file
            self._prompts = {}
            self._by_name = {}

    def _save(self) -> None:
        """Save registry to file."""
        data = {
            "last_updated": _now_utc().isoformat(),
            "prompt_count": len(self._prompts),
            "prompts": [p.to_dict() for p in self._prompts.values()],
        }

        tmp_path = self.registry_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self.registry_path)

    def _log_event(
        self,
        event_type: str,
        prompt_id: str,
        data: Dict[str, Any],
    ) -> None:
        """Log prompt event to ledger."""
        if self.ledger:
            self.ledger.log(
                event_type=f"prompt.{event_type}",
                actor="prompt_registry",
                data={"prompt_id": prompt_id, **data},
            )

    def register(
        self,
        name: str,
        template: str,
        created_by: str = "system",
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PromptVersion:
        """
        Register a new prompt or new version of existing prompt.

        If the exact template already exists (same hash), returns existing version.
        If template is different, creates a new version.

        Args:
            name: Human-readable prompt name
            template: Prompt template with {variables}
            created_by: Author/system identifier
            description: Description of this version
            tags: Optional tags for categorization
            metadata: Optional additional metadata

        Returns:
            PromptVersion (new or existing)
        """
        prompt_id = self._compute_hash(template)
        variables = self._extract_variables(template)

        # Check if exact template already exists
        if prompt_id in self._prompts:
            return self._prompts[prompt_id]

        # Determine version number
        if name in self._by_name:
            # Get last version's ID
            last_id = self._by_name[name][-1]
            last_version = self._prompts[last_id]
            version = last_version.version + 1
            parent_id = last_id
        else:
            version = 1
            parent_id = None
            self._by_name[name] = []

        prompt = PromptVersion(
            prompt_id=prompt_id,
            name=name,
            version=version,
            template=template,
            variables=variables,
            created_at=_now_utc().isoformat(),
            created_by=created_by,
            description=description,
            tags=tags or [],
            parent_id=parent_id,
            metadata=metadata or {},
        )

        self._prompts[prompt_id] = prompt
        self._by_name[name].append(prompt_id)
        self._save()

        self._log_event("registered", prompt_id, {
            "name": name,
            "version": version,
            "variables": variables,
            "parent_id": parent_id,
        })

        return prompt

    def get(self, prompt_id: str) -> Optional[PromptVersion]:
        """
        Get prompt by ID.

        Args:
            prompt_id: Prompt hash ID

        Returns:
            PromptVersion or None if not found
        """
        return self._prompts.get(prompt_id)

    def get_by_name(
        self,
        name: str,
        version: Optional[int] = None,
    ) -> Optional[PromptVersion]:
        """
        Get prompt by name and optional version.

        Args:
            name: Prompt name
            version: Specific version (default: latest)

        Returns:
            PromptVersion or None if not found
        """
        if name not in self._by_name:
            return None

        prompt_ids = self._by_name[name]
        if not prompt_ids:
            return None

        if version is None:
            # Return latest
            return self._prompts[prompt_ids[-1]]

        # Find specific version
        for pid in prompt_ids:
            prompt = self._prompts[pid]
            if prompt.version == version:
                return prompt

        return None

    def get_latest(self, name: str) -> Optional[PromptVersion]:
        """Get latest version of a prompt by name."""
        return self.get_by_name(name, version=None)

    def get_versions(self, name: str) -> List[PromptVersion]:
        """
        Get all versions of a prompt.

        Args:
            name: Prompt name

        Returns:
            List of all versions, oldest first
        """
        if name not in self._by_name:
            return []

        return [
            self._prompts[pid]
            for pid in self._by_name[name]
        ]

    def render(
        self,
        prompt_id: str,
        card_id: Optional[str] = None,
        session_id: Optional[str] = None,
        track_usage: bool = True,
        **variables: Any,
    ) -> str:
        """
        Render a prompt with variables.

        Args:
            prompt_id: Prompt hash ID
            card_id: Optional card ID for usage tracking
            session_id: Optional session ID for usage tracking
            track_usage: Whether to record usage
            **variables: Variable values to substitute

        Returns:
            Rendered prompt string

        Raises:
            KeyError: If prompt not found
            ValueError: If required variables missing
        """
        prompt = self._prompts.get(prompt_id)
        if not prompt:
            raise KeyError(f"Prompt not found: {prompt_id}")

        result = prompt.render(**variables)

        if track_usage:
            usage = PromptUsage(
                prompt_id=prompt_id,
                timestamp=_now_utc().isoformat(),
                card_id=card_id,
                session_id=session_id,
                variables=variables,
            )
            self._usage.append(usage)

            self._log_event("used", prompt_id, {
                "card_id": card_id,
                "session_id": session_id,
                "name": prompt.name,
                "version": prompt.version,
            })

        return result

    def render_by_name(
        self,
        name: str,
        version: Optional[int] = None,
        card_id: Optional[str] = None,
        session_id: Optional[str] = None,
        **variables: Any,
    ) -> str:
        """
        Render a prompt by name with variables.

        Args:
            name: Prompt name
            version: Specific version (default: latest)
            card_id: Optional card ID for usage tracking
            session_id: Optional session ID for usage tracking
            **variables: Variable values to substitute

        Returns:
            Rendered prompt string

        Raises:
            KeyError: If prompt not found
            ValueError: If required variables missing
        """
        prompt = self.get_by_name(name, version)
        if not prompt:
            raise KeyError(f"Prompt not found: {name} (version={version})")

        return self.render(
            prompt.prompt_id,
            card_id=card_id,
            session_id=session_id,
            **variables,
        )

    def record_outcome(
        self,
        prompt_id: str,
        outcome: str,
        card_id: Optional[str] = None,
    ) -> None:
        """
        Record outcome for a prompt usage (for A/B testing).

        Args:
            prompt_id: Prompt hash ID
            outcome: Outcome string (e.g., "success", "failure")
            card_id: Optional card ID to match usage
        """
        self._log_event("outcome", prompt_id, {
            "outcome": outcome,
            "card_id": card_id,
        })

    def list_prompts(
        self,
        tag: Optional[str] = None,
    ) -> List[PromptVersion]:
        """
        List all prompts (latest versions only).

        Args:
            tag: Optional tag filter

        Returns:
            List of latest prompt versions
        """
        result = []
        for name in self._by_name:
            prompt = self.get_latest(name)
            if prompt:
                if tag is None or tag in prompt.tags:
                    result.append(prompt)
        return result

    def get_history(self, prompt_id: str) -> List[PromptVersion]:
        """
        Get version history for a prompt.

        Args:
            prompt_id: Any version's prompt ID

        Returns:
            Full version history, oldest first
        """
        prompt = self._prompts.get(prompt_id)
        if not prompt:
            return []

        return self.get_versions(prompt.name)

    def diff(
        self,
        prompt_id_a: str,
        prompt_id_b: str,
    ) -> Dict[str, Any]:
        """
        Compare two prompt versions.

        Args:
            prompt_id_a: First prompt ID
            prompt_id_b: Second prompt ID

        Returns:
            Dict with comparison details
        """
        a = self._prompts.get(prompt_id_a)
        b = self._prompts.get(prompt_id_b)

        if not a or not b:
            return {"error": "One or both prompts not found"}

        # Simple line-based diff
        lines_a = a.template.splitlines()
        lines_b = b.template.splitlines()

        return {
            "prompt_a": {"id": prompt_id_a, "name": a.name, "version": a.version},
            "prompt_b": {"id": prompt_id_b, "name": b.name, "version": b.version},
            "template_changed": a.template != b.template,
            "variables_added": list(set(b.variables) - set(a.variables)),
            "variables_removed": list(set(a.variables) - set(b.variables)),
            "lines_a": len(lines_a),
            "lines_b": len(lines_b),
        }

    def get_usage_stats(
        self,
        prompt_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get usage statistics for prompts.

        Args:
            prompt_id: Filter by specific prompt ID
            name: Filter by prompt name (all versions)

        Returns:
            Usage statistics
        """
        filtered = self._usage

        if prompt_id:
            filtered = [u for u in filtered if u.prompt_id == prompt_id]

        if name:
            name_ids = set(self._by_name.get(name, []))
            filtered = [u for u in filtered if u.prompt_id in name_ids]

        by_prompt: Dict[str, int] = {}
        by_card: Dict[str, int] = {}

        for usage in filtered:
            by_prompt[usage.prompt_id] = by_prompt.get(usage.prompt_id, 0) + 1
            if usage.card_id:
                by_card[usage.card_id] = by_card.get(usage.card_id, 0) + 1

        return {
            "total_usages": len(filtered),
            "by_prompt": by_prompt,
            "by_card": by_card,
        }

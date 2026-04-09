#!/usr/bin/env python3
"""
Output Validator for Structured LLM Output

Provides output validation with:
- JSON schema validation for structured outputs
- Tool call signature validation
- Retry-on-parse-failure logic
- Fallback to raw text handling
- Type coercion and normalization
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

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


T = TypeVar("T")


class ValidationErrorType(Enum):
    """Types of validation errors."""
    PARSE_ERROR = "parse_error"           # Failed to parse as JSON
    SCHEMA_ERROR = "schema_error"         # Failed schema validation
    TYPE_ERROR = "type_error"             # Wrong type
    MISSING_FIELD = "missing_field"       # Required field missing
    INVALID_VALUE = "invalid_value"       # Value out of range/invalid
    TOOL_ERROR = "tool_error"             # Invalid tool call
    EXTRACTION_ERROR = "extraction_error" # Failed to extract from text


@dataclass
class ValidationError:
    """A single validation error."""

    error_type: ValidationErrorType
    message: str
    path: Optional[str] = None    # JSON path to error
    value: Optional[Any] = None   # The invalid value
    expected: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["error_type"] = self.error_type.value
        return d


@dataclass
class ValidationResult:
    """Result of validation attempt."""

    success: bool
    data: Optional[Any] = None           # Parsed/validated data
    raw_output: str = ""                  # Original output
    errors: List[ValidationError] = field(default_factory=list)
    extraction_method: Optional[str] = None  # How data was extracted
    coercions_applied: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "raw_output": self.raw_output[:500] if self.raw_output else None,
            "errors": [e.to_dict() for e in self.errors],
            "extraction_method": self.extraction_method,
            "coercions_applied": self.coercions_applied,
        }


@dataclass
class ToolCallSchema:
    """Schema for validating tool calls."""

    name: str
    description: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    required: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ToolCall:
    """A parsed tool call."""

    name: str
    arguments: Dict[str, Any]
    id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OutputValidator:
    """
    Validates and parses LLM output.

    Features:
    - JSON extraction from mixed text
    - Schema validation
    - Tool call parsing
    - Type coercion
    - Retry suggestions
    """

    # Regex patterns for JSON extraction
    JSON_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", re.IGNORECASE)
    JSON_OBJECT_PATTERN = re.compile(r"\{[\s\S]*\}")
    JSON_ARRAY_PATTERN = re.compile(r"\[[\s\S]*\]")

    def __init__(
        self,
        schemas: Optional[Dict[str, Dict[str, Any]]] = None,
        tool_schemas: Optional[Dict[str, ToolCallSchema]] = None,
        strict_mode: bool = False,
        coerce_types: bool = True,
        ledger: Optional[EventLogger] = None,
    ):
        """
        Initialize validator.

        Args:
            schemas: Named JSON schemas for validation
            tool_schemas: Tool call schemas
            strict_mode: Fail on any validation error
            coerce_types: Attempt type coercion
            ledger: Optional EventLogger
        """
        self.schemas = schemas or {}
        self.tool_schemas = tool_schemas or {}
        self.strict_mode = strict_mode
        self.coerce_types = coerce_types
        self.ledger = ledger

    def _log_event(
        self,
        event_type: str,
        card_id: Optional[str],
        data: Dict[str, Any],
    ) -> None:
        """Log validation event."""
        if self.ledger:
            self.ledger.log(
                event_type=f"validator.{event_type}",
                card_id=card_id,
                actor="output_validator",
                data=data,
            )

    def extract_json(self, text: str) -> Optional[Any]:
        """
        Extract JSON from text.

        Tries multiple strategies:
        1. Code block extraction
        2. Direct JSON object/array
        3. Nested search
        """
        # Strategy 1: Look for code blocks
        matches = self.JSON_BLOCK_PATTERN.findall(text)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

        # Strategy 2: Try parsing entire text
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Strategy 3: Find JSON object
        obj_match = self.JSON_OBJECT_PATTERN.search(text)
        if obj_match:
            try:
                return json.loads(obj_match.group())
            except json.JSONDecodeError:
                pass

        # Strategy 4: Find JSON array
        arr_match = self.JSON_ARRAY_PATTERN.search(text)
        if arr_match:
            try:
                return json.loads(arr_match.group())
            except json.JSONDecodeError:
                pass

        return None

    def _coerce_value(
        self,
        value: Any,
        expected_type: str,
        coercions: List[str],
    ) -> Any:
        """Attempt to coerce value to expected type."""
        if not self.coerce_types:
            return value

        if expected_type == "string":
            if not isinstance(value, str):
                coercions.append(f"Coerced {type(value).__name__} to string")
                return str(value)

        elif expected_type == "number" or expected_type == "integer":
            if isinstance(value, str):
                try:
                    if expected_type == "integer":
                        result = int(float(value))
                    else:
                        result = float(value)
                    coercions.append(f"Coerced string '{value}' to {expected_type}")
                    return result
                except ValueError:
                    pass

        elif expected_type == "boolean":
            if isinstance(value, str):
                lower = value.lower()
                if lower in ("true", "yes", "1"):
                    coercions.append(f"Coerced string '{value}' to boolean true")
                    return True
                elif lower in ("false", "no", "0"):
                    coercions.append(f"Coerced string '{value}' to boolean false")
                    return False

        elif expected_type == "array":
            if isinstance(value, str):
                try:
                    result = json.loads(value)
                    if isinstance(result, list):
                        coercions.append("Coerced string to array")
                        return result
                except json.JSONDecodeError:
                    pass

        return value

    def _validate_schema(
        self,
        data: Any,
        schema: Dict[str, Any],
        path: str = "",
        coercions: List[str] = None,
    ) -> List[ValidationError]:
        """Validate data against a schema."""
        if coercions is None:
            coercions = []

        errors = []
        schema_type = schema.get("type")

        # Type validation
        if schema_type:
            expected_types = [schema_type] if isinstance(schema_type, str) else schema_type

            type_valid = False
            for expected in expected_types:
                if expected == "string" and isinstance(data, str):
                    type_valid = True
                elif expected == "number" and isinstance(data, (int, float)):
                    type_valid = True
                elif expected == "integer" and isinstance(data, int):
                    type_valid = True
                elif expected == "boolean" and isinstance(data, bool):
                    type_valid = True
                elif expected == "array" and isinstance(data, list):
                    type_valid = True
                elif expected == "object" and isinstance(data, dict):
                    type_valid = True
                elif expected == "null" and data is None:
                    type_valid = True

            if not type_valid and self.coerce_types:
                # Try coercion
                for expected in expected_types:
                    coerced = self._coerce_value(data, expected, coercions)
                    if coerced != data:
                        data = coerced
                        type_valid = True
                        break

            if not type_valid:
                errors.append(ValidationError(
                    error_type=ValidationErrorType.TYPE_ERROR,
                    message=f"Expected {expected_types}, got {type(data).__name__}",
                    path=path,
                    value=data,
                    expected=str(expected_types),
                ))
                return errors

        # Object validation
        if isinstance(data, dict) and schema_type == "object":
            properties = schema.get("properties", {})
            required = schema.get("required", [])

            # Check required fields
            for field_name in required:
                if field_name not in data:
                    errors.append(ValidationError(
                        error_type=ValidationErrorType.MISSING_FIELD,
                        message=f"Missing required field: {field_name}",
                        path=f"{path}.{field_name}" if path else field_name,
                    ))

            # Validate each property
            for prop_name, prop_schema in properties.items():
                if prop_name in data:
                    prop_path = f"{path}.{prop_name}" if path else prop_name
                    prop_errors = self._validate_schema(
                        data[prop_name],
                        prop_schema,
                        prop_path,
                        coercions,
                    )
                    errors.extend(prop_errors)

        # Array validation
        elif isinstance(data, list) and schema_type == "array":
            items_schema = schema.get("items", {})

            for i, item in enumerate(data):
                item_path = f"{path}[{i}]"
                item_errors = self._validate_schema(item, items_schema, item_path, coercions)
                errors.extend(item_errors)

            # Length validation
            min_items = schema.get("minItems")
            max_items = schema.get("maxItems")

            if min_items is not None and len(data) < min_items:
                errors.append(ValidationError(
                    error_type=ValidationErrorType.INVALID_VALUE,
                    message=f"Array has {len(data)} items, minimum is {min_items}",
                    path=path,
                ))

            if max_items is not None and len(data) > max_items:
                errors.append(ValidationError(
                    error_type=ValidationErrorType.INVALID_VALUE,
                    message=f"Array has {len(data)} items, maximum is {max_items}",
                    path=path,
                ))

        # String validation
        elif isinstance(data, str):
            min_length = schema.get("minLength")
            max_length = schema.get("maxLength")
            pattern = schema.get("pattern")
            enum_values = schema.get("enum")

            if min_length is not None and len(data) < min_length:
                errors.append(ValidationError(
                    error_type=ValidationErrorType.INVALID_VALUE,
                    message=f"String length {len(data)} is less than minimum {min_length}",
                    path=path,
                    value=data,
                ))

            if max_length is not None and len(data) > max_length:
                errors.append(ValidationError(
                    error_type=ValidationErrorType.INVALID_VALUE,
                    message=f"String length {len(data)} exceeds maximum {max_length}",
                    path=path,
                    value=data[:50] + "..." if len(data) > 50 else data,
                ))

            if pattern and not re.match(pattern, data):
                errors.append(ValidationError(
                    error_type=ValidationErrorType.INVALID_VALUE,
                    message=f"String does not match pattern: {pattern}",
                    path=path,
                    value=data,
                ))

            if enum_values and data not in enum_values:
                errors.append(ValidationError(
                    error_type=ValidationErrorType.INVALID_VALUE,
                    message=f"Value must be one of: {enum_values}",
                    path=path,
                    value=data,
                ))

        # Number validation
        elif isinstance(data, (int, float)):
            minimum = schema.get("minimum")
            maximum = schema.get("maximum")

            if minimum is not None and data < minimum:
                errors.append(ValidationError(
                    error_type=ValidationErrorType.INVALID_VALUE,
                    message=f"Value {data} is less than minimum {minimum}",
                    path=path,
                    value=data,
                ))

            if maximum is not None and data > maximum:
                errors.append(ValidationError(
                    error_type=ValidationErrorType.INVALID_VALUE,
                    message=f"Value {data} exceeds maximum {maximum}",
                    path=path,
                    value=data,
                ))

        return errors

    def validate(
        self,
        output: str,
        schema_name: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        card_id: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validate LLM output against a schema.

        Args:
            output: Raw LLM output
            schema_name: Name of registered schema to use
            schema: Inline schema (overrides schema_name)
            card_id: Optional card ID for logging

        Returns:
            ValidationResult with parsed data or errors
        """
        result = ValidationResult(success=False, raw_output=output)

        # Get schema
        if schema is None and schema_name:
            schema = self.schemas.get(schema_name)

        # Extract JSON
        data = self.extract_json(output)

        if data is None:
            result.errors.append(ValidationError(
                error_type=ValidationErrorType.PARSE_ERROR,
                message="Failed to extract JSON from output",
            ))
            self._log_event("parse_failed", card_id, {"output_length": len(output)})
            return result

        result.extraction_method = "json_extracted"

        # Validate against schema if provided
        if schema:
            errors = self._validate_schema(data, schema, "", result.coercions_applied)
            result.errors.extend(errors)

            if errors and self.strict_mode:
                self._log_event("validation_failed", card_id, {
                    "error_count": len(errors),
                    "first_error": errors[0].to_dict(),
                })
                return result

        result.success = len(result.errors) == 0 or not self.strict_mode
        result.data = data

        self._log_event("validated", card_id, {
            "success": result.success,
            "error_count": len(result.errors),
            "coercions": len(result.coercions_applied),
        })

        return result

    def validate_tool_call(
        self,
        output: str,
        card_id: Optional[str] = None,
    ) -> ValidationResult:
        """
        Parse and validate a tool call from output.

        Handles multiple formats:
        - OpenAI function calling format
        - Claude tool use format
        - Plain JSON with name/arguments
        """
        result = ValidationResult(success=False, raw_output=output)

        # Extract JSON
        data = self.extract_json(output)

        if data is None:
            result.errors.append(ValidationError(
                error_type=ValidationErrorType.PARSE_ERROR,
                message="Failed to extract tool call JSON",
            ))
            return result

        # Normalize to list of tool calls
        tool_calls = []

        if isinstance(data, dict):
            # Single tool call
            if "name" in data or "function" in data:
                tool_calls.append(data)
            elif "tool_calls" in data:
                tool_calls = data["tool_calls"]
            elif "tool_use" in data:
                tool_calls = data["tool_use"] if isinstance(data["tool_use"], list) else [data["tool_use"]]
        elif isinstance(data, list):
            tool_calls = data

        parsed_calls = []

        for call_data in tool_calls:
            # Handle different formats
            if "function" in call_data:
                # OpenAI format
                func = call_data["function"]
                name = func.get("name")
                args = func.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        result.errors.append(ValidationError(
                            error_type=ValidationErrorType.PARSE_ERROR,
                            message=f"Failed to parse function arguments for {name}",
                        ))
                        continue
            else:
                # Direct format
                name = call_data.get("name") or call_data.get("tool_name")
                args = call_data.get("arguments") or call_data.get("input") or call_data.get("parameters", {})

            if not name:
                result.errors.append(ValidationError(
                    error_type=ValidationErrorType.TOOL_ERROR,
                    message="Tool call missing name",
                ))
                continue

            # Validate against schema if available
            if name in self.tool_schemas:
                schema = self.tool_schemas[name]

                # Check required parameters
                for req in schema.required:
                    if req not in args:
                        result.errors.append(ValidationError(
                            error_type=ValidationErrorType.MISSING_FIELD,
                            message=f"Tool '{name}' missing required parameter: {req}",
                            path=f"{name}.{req}",
                        ))

                # Validate parameter types
                for param_name, param_schema in schema.parameters.items():
                    if param_name in args:
                        param_errors = self._validate_schema(
                            args[param_name],
                            param_schema,
                            f"{name}.{param_name}",
                            result.coercions_applied,
                        )
                        result.errors.extend(param_errors)

            parsed_calls.append(ToolCall(
                name=name,
                arguments=args,
                id=call_data.get("id"),
            ))

        if not result.errors or not self.strict_mode:
            result.success = True
            result.data = [c.to_dict() for c in parsed_calls]
            result.extraction_method = "tool_call_parsed"

        return result

    def validate_with_retry(
        self,
        generate_fn: Callable[[], str],
        schema_name: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        card_id: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validate output with retry on failure.

        Args:
            generate_fn: Function that generates LLM output
            schema_name: Schema name to validate against
            schema: Inline schema
            max_retries: Maximum retry attempts
            card_id: Optional card ID

        Returns:
            ValidationResult from successful attempt or last failure
        """
        last_result = None

        for attempt in range(max_retries):
            output = generate_fn()
            result = self.validate(output, schema_name, schema, card_id)

            if result.success:
                return result

            last_result = result

            self._log_event("retry", card_id, {
                "attempt": attempt + 1,
                "max_retries": max_retries,
                "error_count": len(result.errors),
            })

        return last_result or ValidationResult(success=False)

    def register_schema(self, name: str, schema: Dict[str, Any]) -> None:
        """Register a named schema."""
        self.schemas[name] = schema

    def register_tool(self, tool: ToolCallSchema) -> None:
        """Register a tool schema."""
        self.tool_schemas[tool.name] = tool

    def get_retry_prompt(self, result: ValidationResult) -> str:
        """Generate a prompt to help LLM fix validation errors."""
        if result.success:
            return ""

        lines = ["Your previous response had the following issues:"]

        for error in result.errors[:5]:  # Limit to 5 errors
            lines.append(f"- {error.message}")
            if error.path:
                lines.append(f"  (at path: {error.path})")

        lines.append("")
        lines.append("Please provide a corrected response in valid JSON format.")

        return "\n".join(lines)


# Convenience functions
def create_validator(
    strict: bool = False,
    ledger: Optional[EventLogger] = None,
) -> OutputValidator:
    """Create a validator with default settings."""
    return OutputValidator(strict_mode=strict, ledger=ledger)


def validate_json(output: str, schema: Dict[str, Any]) -> ValidationResult:
    """Quick validation of JSON output."""
    validator = OutputValidator()
    return validator.validate(output, schema=schema)


def extract_json_safe(text: str) -> Optional[Any]:
    """Safely extract JSON from text."""
    validator = OutputValidator()
    return validator.extract_json(text)

"""Validation of generated values against configured subtasks."""
from __future__ import annotations

from typing import Any

from app.core.constraints import ConstraintError, evaluate


def validate_subtasks(
    test_index: int,
    context: dict[str, Any],
    subtasks: list[dict[str, Any]],
) -> tuple[bool, str]:
    """Validate all subtasks whose inclusive test range contains the test."""

    for subtask in subtasks:
        name = str(subtask.get("name", "Subtask"))
        try:
            start = int(subtask.get("start", 1))
            end = int(subtask.get("end", start))
        except (TypeError, ValueError):
            return False, f"{name}: test range must contain integers"
        if start < 1 or end < start:
            return False, f"{name}: invalid test range {start}-{end}"
        if not start <= test_index <= end:
            continue
        for variable, rule in subtask.get("constraints", {}).items():
            if variable not in context:
                return False, f"{name}: variable {variable!r} is not available"
            valid, reason = _validate_value(variable, context[variable], rule, context)
            if not valid:
                return False, f"{name}: {reason}"
    return True, ""


def _validate_value(
    name: str, value: Any, rule: dict[str, Any], context: dict[str, Any],
) -> tuple[bool, str]:
    if "length" in rule or "count" in rule:
        expected_expression = rule.get("length", rule.get("count"))
        if not hasattr(value, "__len__"):
            return False, f"{name} has no length/count"
        expected = int(evaluate(expected_expression, context))
        if len(value) != expected:
            return False, f"len({name})={len(value)}, expected {expected}"

    comparable: list[int | float]
    if isinstance(value, (int, float)):
        comparable = [value]
    elif isinstance(value, list) and all(isinstance(item, (int, float)) for item in value):
        comparable = value
    elif isinstance(value, list) and all(isinstance(item, tuple) for item in value):
        comparable = [number for row in value for number in row
                      if isinstance(number, (int, float))]
    else:
        comparable = []
    try:
        if "min" in rule:
            minimum = evaluate(rule["min"], context)
            if comparable and any(item < minimum for item in comparable):
                return False, f"{name} contains value below {minimum}"
        if "max" in rule:
            maximum = evaluate(rule["max"], context)
            if comparable and any(item > maximum for item in comparable):
                return False, f"{name} contains value above {maximum}"
    except ConstraintError as exc:
        return False, f"constraint for {name} is invalid: {exc}"
    return True, ""

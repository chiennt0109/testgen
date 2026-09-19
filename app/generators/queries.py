"""Schema-driven query and operation-list generation."""
from __future__ import annotations

import random
from typing import Any

from app.core.constraints import ConstraintError, bounds, evaluate


def generate_queries(
    spec: dict[str, Any], context: dict[str, Any], rng: random.Random,
) -> list[tuple[Any, ...]]:
    """Generate query rows from weighted types and per-field constraints.

    Every field is evaluated against the project context plus fields generated
    earlier in the same row. Consequently ``r.min = l`` and similar
    dependencies do not require special parser rules.
    """

    count = int(evaluate(spec.get("count", 1), context))
    if count < 0:
        raise ConstraintError("Query count cannot be negative")
    query_types = _normalized_types(spec)
    if not query_types:
        raise ConstraintError("Query List requires at least one query type")
    weights = [float(item.get("weight", 1)) for item in query_types]
    if any(weight < 0 for weight in weights) or sum(weights) <= 0:
        raise ConstraintError("Query type weights must be non-negative with a positive sum")

    pattern = _slug(spec.get("pattern", "random"))
    duplicate_policy = _slug(spec.get("duplicate_policy", "allow"))
    rows: list[tuple[Any, ...]] = []
    seen: set[tuple[Any, ...]] = set()
    repeated_source: tuple[Any, ...] | None = None

    for index in range(count):
        for attempt in range(101):
            query_type = rng.choices(query_types, weights=weights, k=1)[0]
            row = _generate_row(query_type, pattern, index, count, context, rng,
                                repeated_source)
            if pattern == "repeated" and repeated_source is None:
                repeated_source = row
            if duplicate_policy != "avoid" or row not in seen:
                break
        else:
            raise ConstraintError(
                f"Could not avoid duplicate query at position {index + 1}; "
                "increase field ranges or allow duplicates")
        rows.append(row)
        seen.add(row)

    order = _slug(spec.get("query_order", "random"))
    if order == "sorted":
        rows.sort(key=lambda row: tuple(str(value) for value in row))
    elif order == "custom":
        order_codes = spec.get("custom_order", [])
        if order_codes:
            rank = {str(code): position for position, code in enumerate(order_codes)}
            rows.sort(key=lambda row: rank.get(str(row[0]), len(rank)))
    return rows


def _generate_row(
    query_type: dict[str, Any], pattern: str, index: int, total: int,
    context: dict[str, Any], rng: random.Random,
    repeated_source: tuple[Any, ...] | None,
) -> tuple[Any, ...]:
    if pattern == "repeated" and repeated_source is not None and rng.random() < .7:
        return repeated_source

    row_context = dict(context)
    fields = query_type.get("fields", [])
    values: list[Any] = []
    prefix = query_type.get("prefix")
    if prefix not in (None, ""):
        values.append(_literal(prefix))

    range_pair = _range_field_indices(fields)
    range_values: tuple[int, int] | None = None
    if range_pair:
        range_values = _pattern_range(fields, range_pair, pattern, index, total,
                                      row_context, rng)

    for field_index, field in enumerate(fields):
        name = str(field.get("name", f"field{field_index + 1}"))
        if field.get("fixed") not in (None, ""):
            value = _literal(field["fixed"])
        elif range_pair and field_index in range_pair and range_values is not None:
            value = range_values[range_pair.index(field_index)]
        else:
            value = _generate_field(field, row_context, rng)
        row_context[name] = value
        values.append(value)
    return tuple(values)


def _generate_field(
    field: dict[str, Any], context: dict[str, Any], rng: random.Random,
) -> Any:
    kind = _slug(field.get("type", "integer"))
    if kind in {"integer", "long_long"}:
        low, high = bounds(field, context, (0, 100))
        return rng.randint(low, high)
    if kind == "real":
        low = float(evaluate(field.get("min", 0), context))
        high = float(evaluate(field.get("max", 1), context))
        if low > high:
            raise ConstraintError(f"Empty real range [{low}, {high}]")
        return rng.uniform(low, high)
    if kind == "choice":
        choices = field.get("values", [])
        if not choices:
            raise ConstraintError(f"Field {field.get('name')} has no choices")
        return rng.choice(choices)
    if kind == "string":
        alphabet = str(field.get("alphabet", "abcdefghijklmnopqrstuvwxyz"))
        length = int(evaluate(field.get("length", 1), context))
        if not alphabet:
            raise ConstraintError("String query field alphabet cannot be empty")
        return "".join(rng.choice(alphabet) for _ in range(length))
    raise ConstraintError(f"Unsupported query field type: {kind}")


def _pattern_range(
    fields: list[dict[str, Any]], pair: tuple[int, int], pattern: str,
    index: int, total: int, context: dict[str, Any], rng: random.Random,
) -> tuple[int, int]:
    left_field, right_field = fields[pair[0]], fields[pair[1]]
    left_low, left_high = bounds(left_field, context, (1, 100))
    local = dict(context)
    left_name = str(left_field.get("name", "l"))

    if pattern == "whole_range":
        left = left_low
    elif pattern == "prefix":
        left = left_low
    elif pattern == "suffix":
        left = rng.randint(left_low, left_high)
    elif pattern == "single_point" or pattern == "point":
        left = rng.randint(left_low, left_high)
    elif pattern == "nested":
        span = max(1, left_high - left_low + 1)
        left = min(left_high, left_low + index % max(1, span // 2))
    else:
        left = rng.randint(left_low, left_high)

    local[left_name] = left
    right_low, right_high = bounds(right_field, local, (left, left_high))
    right_low = max(right_low, left) if pattern in _RANGE_PATTERNS else right_low
    if right_low > right_high:
        raise ConstraintError(
            f"Range fields are impossible after {left_name}={left}: "
            f"[{right_low}, {right_high}]")

    if pattern in {"single_point", "point"}:
        if right_low <= left <= right_high:
            right = left
        else:
            raise ConstraintError("Point pattern requires the right field to allow left")
    elif pattern in {"whole_range", "suffix"}:
        right = right_high
    elif pattern == "prefix":
        right = rng.randint(right_low, right_high)
    elif pattern == "short_range":
        right = rng.randint(right_low, min(right_high, max(right_low, left + 3)))
    elif pattern == "long_range":
        threshold = max(right_low, left + (right_high - left) // 2)
        right = rng.randint(threshold, right_high)
    elif pattern == "nested":
        shrink = index % max(1, (right_high - right_low + 1) // 2)
        right = max(right_low, right_high - shrink)
    elif pattern == "overlapping" and index:
        midpoint = (left_low + right_high) // 2
        left = min(left, midpoint)
        local[left_name] = left
        right_low, right_high = bounds(right_field, local, (left, right_high))
        right = rng.randint(max(right_low, midpoint), right_high)
    else:
        right = rng.randint(right_low, right_high)
    return left, right


def _range_field_indices(fields: list[dict[str, Any]]) -> tuple[int, int] | None:
    names = [str(field.get("name", "")).lower() for field in fields]
    if "l" in names and "r" in names:
        return names.index("l"), names.index("r")
    if "left" in names and "right" in names:
        return names.index("left"), names.index("right")
    return None


def _normalized_types(spec: dict[str, Any]) -> list[dict[str, Any]]:
    configured = spec.get("query_types")
    if isinstance(configured, list) and configured:
        return configured
    # Backward compatibility for projects created by the first UI version.
    maximum = spec.get("n", spec.get("max", 100))
    fields = [
        {"name": "l", "type": "integer", "min": 1, "max": maximum},
        {"name": "r", "type": "integer", "min": "l", "max": maximum},
    ]
    if spec.get("format") == "l r x":
        fields.append({"name": "x", "type": "integer",
                       "min": spec.get("min", 0), "max": spec.get("max", 100)})
    return [{"name": "Range Query", "weight": 100, "fields": fields}]


def _literal(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return text


def _slug(value: Any) -> str:
    return str(value).strip().lower().replace(" ", "_")


_RANGE_PATTERNS = {
    "random_range", "single_point", "point", "whole_range", "prefix",
    "suffix", "short_range", "long_range", "nested", "overlapping",
}

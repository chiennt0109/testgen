"""Generic adversarial profiles selected by block type and subtask strategy."""
from __future__ import annotations

import copy
from typing import Any


PROFILE_CATALOG: dict[str, tuple[str, ...]] = {
    "array": (
        "all_equal", "all_distinct", "many_duplicates", "strict_increasing",
        "strict_decreasing", "alternating", "extreme_values",
        "one_dominant_value", "sparse_domain", "dense_domain",
    ),
    "query_list": (
        "hit", "miss", "single_point", "whole_range", "prefix", "suffix",
        "repeated", "boundary", "worst_case_query",
    ),
    "graph": (
        "path", "star", "disconnected", "random_dense", "random_sparse",
        "extreme_weights",
    ),
    "tree": (
        "path", "star", "balanced_binary_tree", "broom", "caterpillar",
        "extreme_weights",
    ),
}


def choose_subtask_profile(
    strategy: dict[str, Any], position: int,
) -> tuple[str, str] | None:
    """Choose a targeted profile deterministically for a test within a subtask."""

    pools: list[tuple[str, str]] = []
    for category, key in (
        ("edge", "edge_profiles"),
        ("correctness", "correctness_profiles"),
        ("performance", "performance_profiles"),
    ):
        pools.extend((category, str(profile)) for profile in strategy.get(key, []))
    if not pools:
        return None
    return pools[position % len(pools)]


def profile_overrides(
    schema: list[dict[str, Any]], profile: str, category: str,
) -> dict[str, dict[str, Any]]:
    """Translate a generic profile into overrides for compatible schema blocks."""

    explicit_type, separator, profile_name = profile.partition(":")
    if not separator:
        explicit_type, profile_name = "", explicit_type
    normalized = profile_name.strip().lower().replace(" ", "_")
    result: dict[str, dict[str, Any]] = {}
    for block in schema:
        name = str(block.get("name", ""))
        kind = str(block.get("type", "")).lower()
        family = _family(kind)
        if not name:
            continue
        override: dict[str, Any] = {}
        if category == "performance":
            if "max" in block and family == "scalar":
                # Select the maximum of the *effective* range. Do not copy the
                # schema maximum into min/max because a Subtask may tighten it.
                override["mode"] = "maximum"
        if explicit_type and explicit_type != family:
            if override:
                result[name] = override
            continue
        if family == "array" and normalized in PROFILE_CATALOG["array"]:
            override["pattern"] = normalized
        elif family == "query_list":
            query_pattern = {
                "point": "single_point", "boundary": "whole_range",
                "worst_case_query": "whole_range", "repeated": "repeated",
            }.get(normalized, normalized)
            if normalized in PROFILE_CATALOG["query_list"]:
                if normalized in {"hit", "miss"}:
                    override["relation_profile"] = normalized
                else:
                    override["pattern"] = query_pattern
        elif family == "graph" and normalized in PROFILE_CATALOG["graph"]:
            override["pattern"] = "random_dense" if normalized == "extreme_weights" else normalized
            if normalized == "extreme_weights":
                override["weight_mode"] = "extreme"
        elif family == "tree" and normalized in PROFILE_CATALOG["tree"]:
            override["pattern"] = "path" if normalized == "extreme_weights" else normalized
            if normalized == "extreme_weights":
                override["weight_mode"] = "extreme"
        if override:
            result[name] = override
    return result


def merge_overrides(
    base: dict[str, Any], extra: dict[str, Any],
) -> dict[str, Any]:
    """Merge profile overrides without mutating project configuration."""

    result = copy.deepcopy(base)
    for variable, values in extra.items():
        result.setdefault(variable, {}).update(copy.deepcopy(values))
    return result


def _family(kind: str) -> str:
    if kind in {"integer", "long_long", "real"}:
        return "scalar"
    if kind in {"array", "permutation"}:
        return "array"
    if kind in {"query_list", "operation_list", "interval_list"}:
        return "query_list"
    if "tree" in kind:
        return "tree"
    if "graph" in kind:
        return "graph"
    return kind

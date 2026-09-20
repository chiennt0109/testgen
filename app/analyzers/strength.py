"""Test strength, output diversity, relation, and mutation coverage analysis."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any


def analyze_strength(folder: Path, required_coverage: list[str] | None = None) -> dict[str, Any]:
    """Build a generic strength report from manifest, inputs, outputs and mutations."""

    required = required_coverage or []
    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"tests": []}
    tests = manifest.get("tests", [])
    profiles = [entry for test in tests for entry in test.get("adversarial_profiles", [])]
    profile_names = {str(entry.get("profile")) for entry in profiles}
    categories = Counter(str(entry.get("category")) for entry in profiles)

    outputs = [path.read_text(encoding="utf-8").strip()
               for path in folder.glob("test*/*.out")]
    output_counts = Counter(outputs)
    zeros = sum(output in {"0", "0.0"} for output in outputs)
    numeric_answers: list[float] = []
    for output in outputs:
        try:
            numeric_answers.extend(float(token) for token in output.split())
        except ValueError:
            continue

    mutation_path = folder / "mutation_report.json"
    mutation = json.loads(mutation_path.read_text(encoding="utf-8")) if mutation_path.exists() else {}
    missing = sorted(set(required) - profile_names)
    warnings: list[str] = []
    if outputs and zeros / len(outputs) > .5:
        warnings.append("Quá nhiều output bằng 0")
    if outputs and max(output_counts.values()) / len(outputs) > .6:
        warnings.append("Quá nhiều output giống nhau")
    if numeric_answers and not any(value > 1 for value in numeric_answers):
        warnings.append("Thiếu trường hợp answer > 1")
    if "hit" not in profile_names or "miss" not in profile_names:
        warnings.append("Thiếu coverage hit/miss")
    if not ({"minimum", "maximum", "extreme_values"} & profile_names):
        warnings.append("Thiếu min/max hoặc extreme values")
    if categories.get("performance", 0) == 0:
        warnings.append("Thiếu max-size/performance killer")
    if missing:
        warnings.append("Thiếu required coverage: " + ", ".join(missing))
    if mutation.get("weak_suite"):
        warnings.append("Còn candidate/mutant sống; test suite còn yếu")

    dimensions = {
        "boundary_coverage": bool({"boundary", "minimum", "maximum", "extreme_values"} & profile_names),
        "relation_coverage": "hit" in profile_names and "miss" in profile_names,
        "output_diversity": len(output_counts) / len(outputs) if outputs else 0.0,
        "mutation_coverage": float(mutation.get("coverage", 0.0)),
        "performance_coverage": categories.get("performance", 0) > 0,
    }
    score_parts = [
        float(dimensions["boundary_coverage"]), float(dimensions["relation_coverage"]),
        min(1.0, float(dimensions["output_diversity"]) * 2),
        float(dimensions["mutation_coverage"]), float(dimensions["performance_coverage"]),
    ]
    return {
        "test_count": len(tests), "profiles": sorted(profile_names),
        "profile_categories": dict(categories), "outputs": {
            "count": len(outputs), "distinct": len(output_counts), "zero_ratio": zeros / len(outputs) if outputs else 0.0,
        },
        "mutation": mutation, "dimensions": dimensions,
        "strength_score": sum(score_parts) / len(score_parts), "warnings": warnings,
    }

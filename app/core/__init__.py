"""Core services exposed lazily to keep generator imports acyclic."""
from __future__ import annotations

from typing import Any

__all__ = ["GenerationEngine", "GenerationPipeline", "PlanAudit", "StressResult", "StressTester", "audit_plan"]


def __getattr__(name: str) -> Any:
    """Load public services on demand without importing the engine from constraints."""

    if name == "GenerationEngine":
        from .engine import GenerationEngine
        return GenerationEngine
    if name == "GenerationPipeline":
        from .pipeline import GenerationPipeline
        return GenerationPipeline
    if name in {"PlanAudit", "audit_plan"}:
        from .planning import PlanAudit, audit_plan
        return {"PlanAudit": PlanAudit, "audit_plan": audit_plan}[name]
    if name in {"StressResult", "StressTester"}:
        from .stress import StressResult, StressTester
        return {"StressResult": StressResult, "StressTester": StressTester}[name]
    raise AttributeError(name)

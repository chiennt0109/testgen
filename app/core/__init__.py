"""Core services exposed lazily to keep generator imports acyclic."""
from __future__ import annotations

from typing import Any

__all__ = ["Candidate", "GenerationEngine", "GenerationPipeline", "MutationReport", "MutationTester", "PlanAudit", "StressResult", "StressTester", "TargetedCase", "audit_plan", "generation_group"]


def __getattr__(name: str) -> Any:
    """Load public services on demand without importing the engine from constraints."""

    if name == "GenerationEngine":
        from .engine import GenerationEngine
        return GenerationEngine
    if name == "GenerationPipeline":
        from .pipeline import GenerationPipeline
        return GenerationPipeline
    if name in {"PlanAudit", "audit_plan", "generation_group"}:
        from .planning import PlanAudit, audit_plan, generation_group
        return {"PlanAudit": PlanAudit, "audit_plan": audit_plan,
                "generation_group": generation_group}[name]
    if name in {"StressResult", "StressTester"}:
        from .stress import StressResult, StressTester
        return {"StressResult": StressResult, "StressTester": StressTester}[name]
    if name in {"Candidate", "MutationReport", "MutationTester", "TargetedCase"}:
        from .mutation import Candidate, MutationReport, MutationTester, TargetedCase
        return {"Candidate": Candidate, "MutationReport": MutationReport,
                "MutationTester": MutationTester, "TargetedCase": TargetedCase}[name]
    raise AttributeError(name)

"""Serializable project models."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class TestGroup:
    """A deterministic group in a test plan."""
    name: str = "Random"
    count: int = 1
    profile: str = "random"
    seed_mode: str = "increment"
    overrides: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Project:
    """Complete, JSON-backed problem configuration."""
    problem_name: str = "PROBLEM"
    input_filename: str = "PROBLEM.inp"
    output_filename: str = "PROBLEM.out"
    test_folder_pattern: str = "test{index:02d}"
    test_count: int = 20
    language: str = "cpp"
    solution_path: str = "solution.cpp"
    brute_path: str = "brute.cpp"
    validator_path: str = "validator.py"
    generator_path: str = ""
    seed: int = 123456
    time_limit: float = 2.0
    memory_limit_mb: int = 256
    output_layout: str = "folders"
    io_mode: str = "stdio"
    cpp_standard: str = "c++17"
    compiler_path: str = ""
    duplicate_policy: str = "warn"
    schema: list[dict[str, Any]] = field(default_factory=list)
    test_plan: list[TestGroup] = field(default_factory=list)
    subtasks: list[dict[str, Any]] = field(default_factory=list)
    multiple_testcases: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        values = dict(data)
        values["test_plan"] = [g if isinstance(g, TestGroup) else TestGroup(**g) for g in values.get("test_plan", [])]
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in values.items() if k in allowed})

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Project":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

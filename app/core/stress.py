"""Brute-force cross-check service."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Callable

from app.models import Project
from app.runners import SolutionRunner

from .engine import GenerationEngine


@dataclass(slots=True)
class StressResult:
    """Summary of a completed or failed cross-check."""

    passed: int
    failed: int
    elapsed: float
    current_seed: int
    counterexample: Path | None = None


def normalize_output(text: str) -> str:
    """Normalize judge-style whitespace before comparison."""

    return " ".join(text.split())


class StressTester:
    """Compile solution and brute once, then compare deterministic small tests."""

    def __init__(self, engine: GenerationEngine | None = None) -> None:
        self.engine = engine or GenerationEngine()

    def run(
        self,
        project: Project,
        project_dir: Path,
        iterations: int,
        timeout: float,
        progress: Callable[[int, int, int, float], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> StressResult:
        runner = SolutionRunner()
        solution = project_dir / project.solution_path
        brute = project_dir / project.brute_path
        if not solution.exists() or not brute.exists():
            raise RuntimeError("Stress Test requires both solution and brute files")

        build_dir = project_dir / ".tgs-build"
        build_dir.mkdir(exist_ok=True)
        solution_program = self._prepare(runner, solution, build_dir / "solution.exe")
        brute_program = self._prepare(runner, brute, build_dir / "brute.exe")
        started = time.monotonic()
        last_seed = project.seed

        for iteration in range(1, iterations + 1):
            if cancelled and cancelled():
                return StressResult(iteration - 1, 0, time.monotonic() - started, last_seed)
            last_seed = project.seed + iteration
            group = {
                "name": "Stress small",
                "profile": "small",
                "overrides": {},
            }
            input_text, _ = self.engine.generate(
                project,
                last_seed,
                index=iteration,
                group=group,
                base=project_dir,
            )
            expected = runner.run(brute_program, input_text, timeout, project.io_mode,
                                  project.input_filename, project.output_filename)
            actual = runner.run(solution_program, input_text, timeout, project.io_mode,
                                project.input_filename, project.output_filename)
            if expected.status != "OK" or actual.status != "OK" or normalize_output(expected.stdout) != normalize_output(actual.stdout):
                counterexample = self._save_counterexample(
                    project_dir, last_seed, input_text, expected.stdout, actual.stdout,
                    expected.status, actual.status,
                )
                return StressResult(iteration - 1, 1, time.monotonic() - started,
                                    last_seed, counterexample)
            elapsed = time.monotonic() - started
            if progress:
                progress(iteration, iterations, last_seed, elapsed)
        return StressResult(iterations, 0, time.monotonic() - started, last_seed)

    @staticmethod
    def _prepare(runner: SolutionRunner, source: Path, executable: Path) -> Path:
        if source.suffix.lower() == ".cpp":
            return runner.compile(source, executable)
        return source

    @staticmethod
    def _save_counterexample(
        project_dir: Path, seed: int, input_text: str, brute_output: str,
        solution_output: str, brute_status: str, solution_status: str,
    ) -> Path:
        target = project_dir / "counterexamples" / f"seed_{seed}"
        target.mkdir(parents=True, exist_ok=True)
        (target / "input.txt").write_text(input_text, encoding="utf-8")
        (target / "brute.out").write_text(
            f"status: {brute_status}\n{brute_output}", encoding="utf-8")
        (target / "solution.out").write_text(
            f"status: {solution_status}\n{solution_output}", encoding="utf-8")
        return target

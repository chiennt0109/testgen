"""Brute-force cross-check service."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
import time
from typing import Callable

from app.models import Project
from app.runners import RunResult, SolutionRunner

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
        profile: str = "small",
        progress: Callable[[int, int, int, float], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> StressResult:
        runner = SolutionRunner(project.compiler_path or None)
        solution = project_dir / project.solution_path
        brute = project_dir / project.brute_path
        if not solution.exists() or not brute.exists():
            raise RuntimeError("Stress Test requires both solution and brute files")

        with tempfile.TemporaryDirectory(prefix="tgs-stress-") as raw_build_dir:
            build_dir = Path(raw_build_dir)
            solution_program = self._prepare(
                runner, solution, build_dir / "solution.exe", project.cpp_standard)
            brute_program = self._prepare(
                runner, brute, build_dir / "brute.exe", project.cpp_standard)
            started = time.monotonic()
            last_seed = project.seed
            group = self._select_group(project, profile)

            for iteration in range(1, iterations + 1):
                if cancelled and cancelled():
                    return StressResult(
                        iteration - 1, 0, time.monotonic() - started, last_seed)
                last_seed = project.seed + iteration
                input_text, _ = self.engine.generate(
                    project,
                    last_seed,
                    index=iteration,
                    group=group,
                    base=project_dir,
                )
                expected = runner.run(
                    brute_program, input_text, timeout, project.io_mode,
                    project.input_filename, project.output_filename)
                actual = runner.run(
                    solution_program, input_text, timeout, project.io_mode,
                    project.input_filename, project.output_filename)
                if (expected.status != "OK" or actual.status != "OK" or
                        normalize_output(expected.stdout) != normalize_output(actual.stdout)):
                    counterexample = self._save_counterexample(
                        project_dir, last_seed, input_text, expected, actual,
                    )
                    return StressResult(
                        iteration - 1, 1, time.monotonic() - started,
                        last_seed, counterexample)
                elapsed = time.monotonic() - started
                if progress:
                    progress(iteration, iterations, last_seed, elapsed)
            return StressResult(iterations, 0, time.monotonic() - started, last_seed)

    @staticmethod
    def _prepare(
        runner: SolutionRunner, source: Path, executable: Path, standard: str,
    ) -> Path:
        if source.suffix.lower() == ".cpp":
            return runner.compile(source, executable, standard)
        return source

    @staticmethod
    def _select_group(project: Project, requested_profile: str) -> dict[str, object]:
        normalized = requested_profile.strip().lower().replace(" ", "_")
        aliases = {
            "small_random": {"small", "random_small", "small_random"},
            "edge_cases": {"edge", "edge_cases", "adversarial"},
            "custom_generator": {"custom", "custom_generator"},
        }
        accepted = aliases.get(normalized, {normalized})
        for configured in project.test_plan:
            profile = configured.profile.strip().lower().replace(" ", "_")
            if profile in accepted:
                return {
                    "name": configured.name,
                    "profile": configured.profile,
                    "overrides": configured.overrides,
                }
        return {
            "name": f"Stress {requested_profile}",
            "profile": normalized,
            "overrides": {},
        }

    @staticmethod
    def _save_counterexample(
        project_dir: Path, seed: int, input_text: str,
        brute_result: RunResult, solution_result: RunResult,
    ) -> Path:
        target = project_dir / "counterexamples" / f"seed_{seed}"
        target.mkdir(parents=True, exist_ok=True)
        (target / "input.txt").write_text(input_text, encoding="utf-8")
        (target / "brute.out").write_text(
            f"status: {brute_result.status}\n{brute_result.stdout}", encoding="utf-8")
        (target / "solution.out").write_text(
            f"status: {solution_result.status}\n{solution_result.stdout}", encoding="utf-8")
        (target / "brute.stderr.txt").write_text(
            brute_result.stderr, encoding="utf-8")
        (target / "solution.stderr.txt").write_text(
            solution_result.stderr, encoding="utf-8")
        return target

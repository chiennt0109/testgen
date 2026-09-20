"""Generic candidate/mutation testing and counterexample retention."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import tempfile
import time
from typing import Iterable

from app.runners import SolutionRunner
from .stress import normalize_output


@dataclass(slots=True)
class Candidate:
    """A wrong, candidate, or complexity-sensitive solution."""

    name: str
    path: Path
    timeout: float = 1.0


@dataclass(slots=True)
class TargetedCase:
    """Input retained for a stated adversarial reason."""

    input_text: str
    seed: int
    reason: str
    profile: str = "correctness"


@dataclass(slots=True)
class MutationResult:
    """Per-candidate kill status."""

    name: str
    status: str = "survived"
    killed_by_seed: int | None = None
    reason: str = ""
    elapsed: float = 0.0
    counterexample: str = ""


@dataclass(slots=True)
class MutationReport:
    """Mutation coverage report for a candidate set."""

    results: list[MutationResult] = field(default_factory=list)

    @property
    def killed(self) -> int:
        return sum(result.status != "survived" for result in self.results)

    @property
    def coverage(self) -> float:
        return self.killed / len(self.results) if self.results else 1.0

    def to_dict(self) -> dict[str, object]:
        return {
            "killed": self.killed,
            "total": len(self.results),
            "coverage": self.coverage,
            "weak_suite": any(item.status == "survived" for item in self.results),
            "candidates": [asdict(item) for item in self.results],
        }


class MutationTester:
    """Compare many candidates against one reference and retain useful tests."""

    def __init__(self, runner: SolutionRunner | None = None) -> None:
        self.runner = runner or SolutionRunner()

    def run(
        self,
        reference: Path,
        candidates: list[Candidate],
        cases: Iterable[TargetedCase],
        output_dir: Path,
        *,
        reference_timeout: float = 3.0,
        cpp_standard: str = "c++17",
    ) -> MutationReport:
        case_list = list(cases)
        output_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="tgs-mutation-") as raw:
            build = Path(raw)
            reference_program = self._prepare(reference, build / "reference.exe", cpp_standard)
            programs = {
                candidate.name: self._prepare(
                    candidate.path, build / f"candidate_{index}.exe", cpp_standard)
                for index, candidate in enumerate(candidates, 1)
            }
            results = {candidate.name: MutationResult(candidate.name)
                       for candidate in candidates}
            for case in case_list:
                expected = self.runner.run(reference_program, case.input_text, reference_timeout)
                if expected.status != "OK":
                    raise RuntimeError(
                        f"Reference solution failed at seed {case.seed}: {expected.status}")
                for candidate in candidates:
                    result = results[candidate.name]
                    if result.status != "survived":
                        continue
                    started = time.monotonic()
                    actual = self.runner.run(
                        programs[candidate.name], case.input_text, candidate.timeout)
                    result.elapsed += time.monotonic() - started
                    if actual.status == "TIMEOUT":
                        self._kill(result, "timeout", case, expected.stdout,
                                   actual.stdout, actual.stderr, output_dir)
                    elif actual.status != "OK":
                        self._kill(result, "runtime_error", case, expected.stdout,
                                   actual.stdout, actual.stderr, output_dir)
                    elif normalize_output(actual.stdout) != normalize_output(expected.stdout):
                        self._kill(result, "killed", case, expected.stdout,
                                   actual.stdout, actual.stderr, output_dir)
            report = MutationReport(list(results.values()))
            (output_dir / "mutation_report.json").write_text(
                json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
            return report

    def _prepare(self, source: Path, output: Path, standard: str) -> Path:
        if source.suffix.lower() == ".cpp":
            return self.runner.compile(source, output, standard)
        return source

    @staticmethod
    def _kill(
        result: MutationResult, status: str, case: TargetedCase,
        expected: str, actual: str, stderr: str, output_dir: Path,
    ) -> None:
        result.status = status
        result.killed_by_seed = case.seed
        result.reason = case.reason
        target = output_dir / result.name
        target.mkdir(parents=True, exist_ok=True)
        (target / "input.txt").write_text(case.input_text, encoding="utf-8")
        (target / "reference.out").write_text(expected, encoding="utf-8")
        (target / "candidate.out").write_text(actual, encoding="utf-8")
        (target / "candidate.stderr.txt").write_text(stderr, encoding="utf-8")
        (target / "reason.txt").write_text(
            f"profile: {case.profile}\nreason: {case.reason}\nseed: {case.seed}\n",
            encoding="utf-8")
        result.counterexample = str(target)

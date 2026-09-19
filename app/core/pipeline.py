"""Transactional batch generation pipeline."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from typing import Callable

from app.models import Project
from app.runners import RunResult, SolutionRunner
from app.validators import validate_input, validate_subtasks

from .engine import GenerationEngine
from .planning import audit_plan, generation_group


class GenerationPipeline:
    """Generate and validate every input before building any expected output."""

    def __init__(self, engine: GenerationEngine | None = None) -> None:
        self.engine = engine or GenerationEngine()

    def generate(
        self,
        project: Project,
        project_dir: Path,
        destination: Path,
        *,
        progress: Callable[[int, int], None] | None = None,
        cancel: Callable[[], bool] | None = None,
    ) -> Path:
        audit = audit_plan(project)
        if audit.errors:
            raise RuntimeError("Test Plan / Subtask Error:\n- " + "\n- ".join(audit.errors))
        groups = [generation_group(project, index)
                  for index in range(1, project.test_count + 1)]
        runner = SolutionRunner(project.compiler_path or None)

        with tempfile.TemporaryDirectory(prefix="tgs-batch-") as raw:
            stage = Path(raw) / destination.name
            stage.mkdir()
            seen: dict[str, int] = {}
            manifest: list[dict[str, object]] = []
            inputs: list[tuple[int, Path, str]] = []
            total_steps = project.test_count * (2 if self._should_build_outputs(project, project_dir) else 1)

            # Phase A: complete all input generation and constraint validation.
            for index, group in enumerate(groups, 1):
                if cancel and cancel():
                    raise RuntimeError("Generation cancelled")
                seed = project.seed + index
                custom_validator = (
                    project_dir / project.validator_path if project.validator_path else None)
                for retry in range(101):
                    text, context = self.engine.generate(
                        project, seed, index=index, group=group, base=project_dir)
                    valid, message = validate_input(
                        text, project.to_dict(), custom_validator)
                    if not valid:
                        raise RuntimeError(
                            f"Validator Error at test{index:02d}: {message}")
                    valid, message = validate_subtasks(index, context, project.subtasks)
                    if not valid:
                        raise RuntimeError(
                            f"Subtask Constraint Error at test{index:02d}: {message}")
                    digest = hashlib.sha256(text.encode()).hexdigest()
                    duplicate = seen.get(digest)
                    if not duplicate or project.duplicate_policy != "regenerate":
                        break
                    seed = project.seed + index + (retry + 1) * project.test_count
                else:
                    raise RuntimeError(
                        f"Duplicate Input: could not regenerate test{index:02d} uniquely")
                if duplicate and project.duplicate_policy == "fail":
                    raise RuntimeError(
                        f"Duplicate Input: test{index:02d} duplicates test{duplicate:02d}")
                seen.setdefault(digest, index)
                folder = project.test_folder_pattern.format(index=index)
                test_dir = stage / folder
                test_dir.mkdir()
                input_path = test_dir / project.input_filename
                input_path.write_text(text, encoding="utf-8")
                inputs.append((index, input_path, text))
                manifest.append({
                    "id": f"{index:02d}", "folder": folder, "seed": seed,
                    "group": group["name"], "input_sha256": digest,
                    "subtasks": group.get("subtasks", []),
                    "duplicate_of": duplicate,
                })
                if progress:
                    progress(index, total_steps)

            # Phase B: only run the solution after the whole input batch is valid.
            solution = project_dir / project.solution_path
            if self._should_build_outputs(project, project_dir):
                executable = Path(raw) / (
                    "solution.exe" if solution.suffix.lower() == ".cpp" else solution.name)
                if solution.suffix.lower() == ".cpp":
                    runner.compile(solution, executable, project.cpp_standard)
                else:
                    executable = solution
                for completed, (index, input_path, text) in enumerate(inputs, 1):
                    if cancel and cancel():
                        raise RuntimeError("Build Output cancelled")
                    result = runner.run(
                        executable, text, project.time_limit, project.io_mode,
                        project.input_filename, project.output_filename)
                    if result.status != "OK":
                        failure = self.save_run_failure(
                            project_dir, index, text, result, project)
                        hint = self.run_hint(project, result)
                        raise RuntimeError(
                            f"test{index:02d}: {result.status} (exit code: {result.returncode})\n"
                            f"{hint}\nChi tiết đã lưu tại: {failure}\n"
                            f"stderr:\n{result.stderr or '(trống)' }")
                    (input_path.parent / project.output_filename).write_text(
                        result.stdout, encoding="utf-8")
                    if progress:
                        progress(project.test_count + completed, total_steps)

            data = {
                "problem": project.problem_name,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "master_seed": project.seed,
                "tests": manifest,
            }
            (stage / "manifest.json").write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            target = destination
            version = 2
            while target.exists():
                target = destination.with_name(f"{destination.name}_V{version:02d}")
                version += 1
            shutil.copytree(stage, target)
            return target

    @staticmethod
    def _should_build_outputs(project: Project, project_dir: Path) -> bool:
        return bool(
            project.generate_outputs and project.solution_path and
            (project_dir / project.solution_path).is_file())

    @staticmethod
    def save_run_failure(
        project_dir: Path, index: int, input_text: str,
        result: RunResult, project: Project,
    ) -> Path:
        root = project_dir / "generation_failures"
        root.mkdir(exist_ok=True)
        target = root / f"test{index:02d}"
        version = 2
        while target.exists():
            target = root / f"test{index:02d}_V{version:02d}"
            version += 1
        target.mkdir()
        (target / project.input_filename).write_text(input_text, encoding="utf-8")
        (target / "stderr.txt").write_text(result.stderr, encoding="utf-8")
        (target / "stdout.txt").write_text(result.stdout, encoding="utf-8")
        (target / "run.json").write_text(json.dumps({
            "status": result.status,
            "returncode": result.returncode,
            "io_mode": project.io_mode,
            "solution": project.solution_path,
            "input_filename": project.input_filename,
            "output_filename": project.output_filename,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        return target

    @staticmethod
    def run_hint(project: Project, result: RunResult) -> str:
        if result.status == "TIMEOUT":
            return "Gợi ý: kiểm tra vòng lặp vô hạn hoặc tăng Time limit trong General."
        if result.returncode in {3221225781, -1073741515}:
            return (
                "Windows báo thiếu DLL (0xC0000135). Hãy compile lại bằng phiên bản app "
                "mới để liên kết tĩnh MinGW runtime, hoặc thêm thư mục bin của MinGW vào PATH.")
        if project.io_mode == "stdio":
            return (
                "Gợi ý: nếu solution dùng freopen, chọn File I/O tại trang Solution; "
                "nếu không, chạy input đã lưu trực tiếp để kiểm tra lỗi truy cập bộ nhớ.")
        return (
            "Gợi ý: kiểm tra tên file trong freopen khớp chính xác Input/Output filename "
            "ở General và solution có tạo file output.")

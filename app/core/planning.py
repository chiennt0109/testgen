"""Preflight checks for Test Plan and Subtask compatibility."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models import Project


@dataclass(slots=True)
class PlanAudit:
    """Errors and non-fatal warnings found before batch generation."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def audit_plan(project: Project) -> PlanAudit:
    """Check counts, subtask ranges, overlaps, and obvious bound conflicts."""

    audit = PlanAudit()
    planned = sum(group.count for group in project.test_plan)
    if project.test_plan and planned != project.test_count:
        action = "bổ sung nhóm Random" if planned < project.test_count else "bỏ các test dư"
        audit.warnings.append(
            f"Test Plan có {planned} test nhưng General đặt {project.test_count}; app sẽ {action}.")

    owners: list[str | None] = [None] * (project.test_count + 1)
    for subtask in project.subtasks:
        name = str(subtask.get("name", "Subtask"))
        try:
            start, end = int(subtask.get("start", 1)), int(subtask.get("end", 1))
        except (TypeError, ValueError):
            audit.errors.append(f"{name}: khoảng test phải là số nguyên.")
            continue
        if start < 1 or end < start or end > project.test_count:
            audit.errors.append(
                f"{name}: khoảng {start}-{end} nằm ngoài 1-{project.test_count}.")
            continue
        for index in range(start, end + 1):
            if owners[index] is not None:
                audit.warnings.append(
                    f"test{index:02d} thuộc cả {owners[index]} và {name}; cả hai constraint sẽ áp dụng.")
            else:
                owners[index] = name

    expanded_groups: list[tuple[str, dict[str, Any]]] = []
    for group in project.test_plan:
        expanded_groups.extend([(group.name, group.overrides)] * max(0, group.count))
    expanded_groups = expanded_groups[:project.test_count]
    expanded_groups.extend(
        [("Random", {})] * (project.test_count - len(expanded_groups)))

    for index, (group_name, overrides) in enumerate(expanded_groups, 1):
        for subtask in project.subtasks:
            try:
                applies = int(subtask.get("start", 1)) <= index <= int(subtask.get("end", 1))
            except (TypeError, ValueError):
                continue
            if not applies:
                continue
            for variable, group_rule in overrides.items():
                subtask_rule = subtask.get("constraints", {}).get(variable)
                if not isinstance(group_rule, dict) or not isinstance(subtask_rule, dict):
                    continue
                conflict = _literal_bound_conflict(group_rule, subtask_rule)
                if conflict:
                    audit.errors.append(
                        f"test{index:02d}: group {group_name!r} và "
                        f"{subtask.get('name', 'Subtask')!r} xung đột tại {variable}: {conflict}.")
    return audit


def _literal_bound_conflict(first: dict[str, Any], second: dict[str, Any]) -> str:
    values = (first.get("min"), first.get("max"), second.get("min"), second.get("max"))
    if not all(value is None or isinstance(value, (int, float)) for value in values):
        return ""
    first_min = float("-inf") if values[0] is None else float(values[0])
    first_max = float("inf") if values[1] is None else float(values[1])
    second_min = float("-inf") if values[2] is None else float(values[2])
    second_max = float("inf") if values[3] is None else float(values[3])
    low, high = max(first_min, second_min), min(first_max, second_max)
    if low > high:
        return f"[{first_min:g}, {first_max:g}] không giao [{second_min:g}, {second_max:g}]"
    return ""

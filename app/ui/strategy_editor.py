"""Visual subtask adversarial strategy editor."""
from __future__ import annotations

import copy
from typing import Any

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout, QWidget,
)


class StrategyEditorDialog(QDialog):
    """Edit targeted profiles and required coverage without JSON."""

    def __init__(self, strategy: dict[str, Any] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Adversarial strategy")
        self.resize(760, 360)
        current = copy.deepcopy(strategy or {})
        layout = QVBoxLayout(self)
        help_text = QLabel(
            "Nhập profile cách nhau bằng dấu phẩy. Có thể chỉ rõ block type, ví dụ "
            "array:all_equal, query_list:hit, graph:path. Các profile được luân phiên "
            "giữa các test của subtask; performance profile ưu tiên max constraints."
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        form = QFormLayout()
        self.edge = QLineEdit(", ".join(current.get("edge_profiles", [])))
        self.correctness = QLineEdit(", ".join(current.get("correctness_profiles", [])))
        self.performance = QLineEdit(", ".join(current.get("performance_profiles", [])))
        self.required = QLineEdit(", ".join(current.get("required_coverage", [])))
        form.addRow("Edge-case profiles", self.edge)
        form.addRow("Correctness profiles", self.correctness)
        form.addRow("Performance/stress profiles", self.performance)
        form.addRow("Required coverage", self.required)
        layout.addLayout(form)
        examples = QLabel(
            "Array: all_equal, all_distinct, many_duplicates, one_dominant_value, "
            "extreme_values · Query: hit, miss, point, whole_range, repeated, boundary, "
            "worst_case_query · Graph/Tree: path, star, disconnected, dense, deep, balanced"
        )
        examples.setWordWrap(True)
        layout.addWidget(examples)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def strategy(self) -> dict[str, list[str]]:
        """Return normalized profile lists."""

        return {
            "edge_profiles": self._list(self.edge.text()),
            "correctness_profiles": self._list(self.correctness.text()),
            "performance_profiles": self._list(self.performance.text()),
            "required_coverage": self._list(self.required.text()),
        }

    @staticmethod
    def _list(text: str) -> list[str]:
        return [value.strip().lower().replace(" ", "_")
                for value in text.split(",") if value.strip()]


def summarize_strategy(strategy: dict[str, Any]) -> str:
    """Summarize configured categories for the Subtasks table."""

    parts = []
    for label, key in (("edge", "edge_profiles"), ("correct", "correctness_profiles"),
                       ("perf", "performance_profiles"), ("required", "required_coverage")):
        values = strategy.get(key, [])
        if values:
            parts.append(f"{label}: {', '.join(values)}")
    return "; ".join(parts) if parts else "Chưa có strategy"

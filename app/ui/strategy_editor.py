"""Visual subtask adversarial strategy editor without encoded text fields."""
from __future__ import annotations

import copy
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QGroupBox, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from app.core.adversarial import PROFILE_CATALOG


REQUIRED_COVERAGE = (
    "minimum", "maximum", "boundary", "extreme_values", "all_equal",
    "all_distinct", "many_duplicates", "hit", "miss", "point",
    "whole_range", "prefix", "suffix", "repeated", "path", "star",
    "disconnected", "dense", "max_size", "overflow", "negative_values",
    "output_diversity", "answer_greater_than_one",
)


class ProfilePicker(QGroupBox):
    """Pick typed profiles into an ordered category list."""

    def __init__(self, title: str, values: list[str], parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.family = QComboBox()
        self.family.addItems(["array", "query_list", "graph", "tree"])
        self.profile = QComboBox()
        self.family.currentTextChanged.connect(self._reload_profiles)
        self._reload_profiles(self.family.currentText())
        add = QPushButton("＋ Thêm profile")
        add.clicked.connect(self._add)
        remove = QPushButton("－ Xóa")
        remove.clicked.connect(self._remove)
        up = QPushButton("↑")
        up.clicked.connect(lambda: self._move(-1))
        down = QPushButton("↓")
        down.clicked.connect(lambda: self._move(1))
        for widget in (self.family, self.profile, add, remove, up, down):
            controls.addWidget(widget)
        controls.addStretch()
        layout.addLayout(controls)
        self.items = QListWidget()
        self.items.setAlternatingRowColors(True)
        layout.addWidget(self.items)
        for value in values:
            self.items.addItem(value)

    def values(self) -> list[str]:
        """Return ordered typed profile identifiers."""

        return [self.items.item(row).text() for row in range(self.items.count())]

    def _reload_profiles(self, family: str) -> None:
        self.profile.clear()
        self.profile.addItems(
            [value.replace("_", " ").title() for value in PROFILE_CATALOG.get(family, ())])

    def _add(self) -> None:
        if not self.profile.currentText():
            return
        value = f"{self.family.currentText()}:{self.profile.currentText().lower().replace(' ', '_')}"
        if not self.items.findItems(value, Qt.MatchFlag.MatchExactly):
            self.items.addItem(value)
            self.items.setCurrentRow(self.items.count() - 1)

    def _remove(self) -> None:
        row = self.items.currentRow()
        if row >= 0:
            self.items.takeItem(row)

    def _move(self, offset: int) -> None:
        row = self.items.currentRow()
        target = row + offset
        if row < 0 or target < 0 or target >= self.items.count():
            return
        item = self.items.takeItem(row)
        self.items.insertItem(target, item)
        self.items.setCurrentRow(target)


class StrategyEditorDialog(QDialog):
    """Edit targeted profiles and required coverage using pickers and checkboxes."""

    def __init__(self, strategy: dict[str, Any] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Adversarial strategy")
        self.resize(900, 760)
        current = copy.deepcopy(strategy or {})
        outer = QVBoxLayout(self)
        help_text = QLabel(
            "Chọn block family và profile, sau đó bấm Thêm. Thứ tự trong danh sách "
            "là thứ tự luân phiên giữa các test của subtask. Không cần nhập mã profile."
        )
        help_text.setWordWrap(True)
        outer.addWidget(help_text)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        self.edge = ProfilePicker("Edge-case profiles", current.get("edge_profiles", []))
        self.correctness = ProfilePicker(
            "Correctness profiles", current.get("correctness_profiles", []))
        self.performance = ProfilePicker(
            "Performance / stress profiles", current.get("performance_profiles", []))
        layout.addWidget(self.edge)
        layout.addWidget(self.correctness)
        layout.addWidget(self.performance)

        coverage_group = QGroupBox("Required coverage")
        coverage_layout = QVBoxLayout(coverage_group)
        coverage_layout.addWidget(QLabel(
            "Tick các coverage bắt buộc. Analyze sẽ cảnh báo nếu bộ test chưa đạt."))
        self.required = QListWidget()
        selected = set(current.get("required_coverage", []))
        known = list(REQUIRED_COVERAGE)
        known.extend(value for value in selected if value not in known)
        for coverage in known:
            item = QListWidgetItem(coverage.replace("_", " ").title())
            item.setData(Qt.ItemDataRole.UserRole, coverage)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if coverage in selected else Qt.CheckState.Unchecked)
            self.required.addItem(item)
        coverage_layout.addWidget(self.required)
        layout.addWidget(coverage_group)
        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def strategy(self) -> dict[str, list[str]]:
        """Return normalized profile lists."""

        required = [
            str(self.required.item(row).data(Qt.ItemDataRole.UserRole))
            for row in range(self.required.count())
            if self.required.item(row).checkState() == Qt.CheckState.Checked
        ]
        return {
            "edge_profiles": self.edge.values(),
            "correctness_profiles": self.correctness.values(),
            "performance_profiles": self.performance.values(),
            "required_coverage": required,
        }


def summarize_strategy(strategy: dict[str, Any]) -> str:
    """Summarize configured categories for the Subtasks table."""

    parts = []
    for label, key in (("edge", "edge_profiles"), ("correct", "correctness_profiles"),
                       ("perf", "performance_profiles"), ("required", "required_coverage")):
        values = strategy.get(key, [])
        if values:
            parts.append(f"{label}: {', '.join(values)}")
    return "; ".join(parts) if parts else "Chưa có strategy"

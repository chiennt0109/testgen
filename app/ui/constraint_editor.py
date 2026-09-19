"""Visual editors for Test Plan overrides and Subtask constraints."""
from __future__ import annotations

import copy
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

class ConstraintEditorDialog(QDialog):
    """Edit per-block constraints without exposing serialized JSON."""

    def __init__(
        self,
        schema: list[dict[str, Any]],
        constraints: dict[str, Any] | None = None,
        *,
        title: str = "Constraints",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(900, 520)
        self._schema = schema
        self._constraints = copy.deepcopy(constraints or {})
        layout = QVBoxLayout(self)
        help_text = QLabel(
            "Chọn biến cần override. Exact đặt đồng thời Min và Max; các ô có thể "
            "dùng số hoặc biểu thức như n, n-1. Pattern chỉ áp dụng cho block hỗ trợ pattern."
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Dùng", "Biến / block", "Loại", "Exact", "Min", "Max",
             "Length / Count", "Pattern"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)
        self._populate()

        clear = QPushButton("Bỏ toàn bộ override")
        clear.clicked.connect(self._clear)
        layout.addWidget(clear)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def constraints(self) -> dict[str, dict[str, Any]]:
        """Return constraints represented by checked rows."""

        result: dict[str, dict[str, Any]] = {}
        for row in range(self.table.rowCount()):
            use = self.table.item(row, 0)
            if not use or use.checkState() != Qt.CheckState.Checked:
                continue
            name = self._text(row, 1)
            exact = self._value(self._text(row, 3))
            override: dict[str, Any] = {}
            if exact != "":
                override["min"] = exact
                override["max"] = exact
            else:
                minimum = self._value(self._text(row, 4))
                maximum = self._value(self._text(row, 5))
                if minimum != "":
                    override["min"] = minimum
                if maximum != "":
                    override["max"] = maximum
            size = self._value(self._text(row, 6))
            kind = str(self.table.item(row, 2).data(Qt.ItemDataRole.UserRole) or "")
            if size != "":
                override["count" if kind in {"query_list", "operation_list", "interval_list"}
                         else "length"] = size
            pattern = self._text(row, 7)
            if pattern:
                override["pattern"] = pattern.strip().lower().replace(" ", "_")
            if override:
                result[name] = override
        return result

    def _populate(self) -> None:
        configured = set(self._constraints)
        for block in self._schema:
            name = str(block.get("name", "")).strip()
            if not name:
                continue
            kind = str(block.get("type", "block"))
            values = self._constraints.get(name, {})
            row = self.table.rowCount()
            self.table.insertRow(row)
            use = QTableWidgetItem()
            use.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            use.setCheckState(Qt.CheckState.Checked if name in configured else Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, use)
            name_item = QTableWidgetItem(name)
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 1, name_item)
            type_item = QTableWidgetItem(kind.replace("_", " ").title())
            type_item.setData(Qt.ItemDataRole.UserRole, kind)
            type_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 2, type_item)
            exact = ""
            if values.get("min") == values.get("max") and "min" in values:
                exact = values["min"]
            size = values.get("count", values.get("length", ""))
            row_values = (
                exact,
                "" if exact != "" else values.get("min", ""),
                "" if exact != "" else values.get("max", ""),
                size,
                str(values.get("pattern", "")).replace("_", " ").title(),
            )
            for column, value in enumerate(row_values, 3):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))

    def _clear(self) -> None:
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(Qt.CheckState.Unchecked)
            for column in range(3, 8):
                self.table.item(row, column).setText("")

    def _text(self, row: int, column: int) -> str:
        item = self.table.item(row, column)
        return item.text().strip() if item else ""

    @staticmethod
    def _value(text: str) -> Any:
        if not text:
            return ""
        try:
            return int(text)
        except ValueError:
            try:
                return float(text)
            except ValueError:
                return text


def summarize_constraints(constraints: dict[str, Any]) -> str:
    """Create a compact, human-readable summary for plan tables."""

    if not constraints:
        return "Không override"
    parts: list[str] = []
    for name, values in constraints.items():
        details: list[str] = []
        if values.get("min") == values.get("max") and "min" in values:
            details.append(f"={values['min']}")
        else:
            if "min" in values:
                details.append(f"min {values['min']}")
            if "max" in values:
                details.append(f"max {values['max']}")
        for key in ("length", "count", "pattern"):
            if key in values:
                details.append(f"{key} {values[key]}")
        parts.append(f"{name}: {', '.join(details)}")
    return "; ".join(parts)

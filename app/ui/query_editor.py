"""Dialog for editing schema-driven query and operation types."""
from __future__ import annotations

import copy
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)


class QuerySchemaDialog(QDialog):
    """Edit weighted query types and fields in a master/detail interface."""

    def __init__(self, block: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cấu trúc Query List")
        self.resize(900, 600)
        self._block = copy.deepcopy(block)
        self._types: list[dict[str, Any]] = copy.deepcopy(block.get("query_types") or [])
        if not self._types:
            maximum = block.get("n", "n")
            self._types = [{
                "name": "Range Query", "weight": 100, "prefix": "",
                "fields": [
                    {"name": "l", "type": "integer", "min": 1, "max": maximum},
                    {"name": "r", "type": "integer", "min": "l", "max": maximum},
                ],
            }]
        self._loading = False
        self._build_ui()
        self._refresh_types(0)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        help_text = QLabel(
            "Mỗi query type có trọng số, prefix/type code tùy chọn và schema field riêng. "
            "Min/max có thể tham chiếu project hoặc field đứng trước, ví dụ r.min = l."
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        splitter = QSplitter()

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("<b>Loại truy vấn</b>"))
        self.type_list = QListWidget()
        self.type_list.currentRowChanged.connect(self._select_type)
        left_layout.addWidget(self.type_list)
        type_buttons = QHBoxLayout()
        add_type = QPushButton("＋ Thêm loại")
        add_type.clicked.connect(self._add_type)
        remove_type = QPushButton("－ Xóa loại")
        remove_type.clicked.connect(self._remove_type)
        type_buttons.addWidget(add_type)
        type_buttons.addWidget(remove_type)
        left_layout.addLayout(type_buttons)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        type_form = QFormLayout()
        self.type_name = QLineEdit()
        self.weight = QSpinBox()
        self.weight.setRange(0, 1000000)
        self.weight.setSuffix(" %")
        self.prefix = QLineEdit()
        self.prefix.setPlaceholderText("Để trống, hoặc 1 / 2 / ADD / QUERY")
        type_form.addRow("Tên loại", self.type_name)
        type_form.addRow("Weight", self.weight)
        type_form.addRow("Fixed prefix/type code", self.prefix)
        right_layout.addLayout(type_form)
        right_layout.addWidget(QLabel("<b>Cấu trúc mỗi truy vấn</b>"))
        self.fields = QTableWidget(0, 6)
        self.fields.setHorizontalHeaderLabels(
            ["Field", "Type", "Min", "Max", "Fixed value", "Options"])
        self.fields.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.fields.setToolTip(
            "Field được sinh từ trái sang phải; Min/Max được phép dùng field trước đó.")
        right_layout.addWidget(self.fields)
        field_buttons = QHBoxLayout()
        add_field = QPushButton("＋ Thêm field")
        add_field.clicked.connect(self._add_field)
        remove_field = QPushButton("－ Xóa field")
        remove_field.clicked.connect(self._remove_field)
        move_up = QPushButton("↑")
        move_up.clicked.connect(lambda: self._move_field(-1))
        move_down = QPushButton("↓")
        move_down.clicked.connect(lambda: self._move_field(1))
        for button in (add_field, remove_field, move_up, move_down):
            field_buttons.addWidget(button)
        field_buttons.addStretch()
        right_layout.addLayout(field_buttons)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        options = QFormLayout()
        self.duplicate_policy = QComboBox()
        self.duplicate_policy.addItem("Allow", "allow")
        self.duplicate_policy.addItem("Warn", "warn")
        self.duplicate_policy.addItem("Avoid", "avoid")
        self.query_order = QComboBox()
        self.query_order.addItem("Random", "random")
        self.query_order.addItem("Sorted", "sorted")
        self.query_order.addItem("Custom", "custom")
        self.output = QComboBox()
        self.output.addItem("Mỗi query một dòng", True)
        self.output.addItem("Ghép tất cả query cùng dòng", False)
        options.addRow("Duplicate policy", self.duplicate_policy)
        options.addRow("Thứ tự query", self.query_order)
        options.addRow("Output", self.output)
        layout.addLayout(options)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.type_name.editingFinished.connect(self._store_type)
        self.weight.valueChanged.connect(self._store_type)
        self.prefix.editingFinished.connect(self._store_type)
        self.fields.itemChanged.connect(lambda _item: self._store_type())

        self._set_combo(self.duplicate_policy, block_value=self._block.get("duplicate_policy", "allow"))
        self._set_combo(self.query_order, block_value=self._block.get("query_order", "random"))
        self._set_combo(self.output, block_value=bool(self._block.get("one_query_per_line", True)))

    def result_block(self) -> dict[str, Any]:
        """Return the block updated with query-schema settings."""

        result = copy.deepcopy(self._block)
        result["query_types"] = copy.deepcopy(self._types)
        result["duplicate_policy"] = self.duplicate_policy.currentData()
        result["query_order"] = self.query_order.currentData()
        result["one_query_per_line"] = bool(self.output.currentData())
        result["layout"] = "line" if result["one_query_per_line"] else "same_line"
        result.pop("n", None)  # Query fields own their variable dependencies.
        result.pop("m", None)
        return result

    def _refresh_types(self, selected: int) -> None:
        self._loading = True
        self.type_list.clear()
        for index, query_type in enumerate(self._types, 1):
            prefix = query_type.get("prefix")
            prefix_text = f" [{prefix}]" if prefix not in (None, "") else ""
            self.type_list.addItem(
                f"{index:02d}. {query_type.get('name', 'Query')}{prefix_text}  "
                f"{query_type.get('weight', 0)}%")
        self._loading = False
        if self._types:
            self.type_list.setCurrentRow(max(0, min(selected, len(self._types) - 1)))
        else:
            self.fields.setRowCount(0)

    def _select_type(self, row: int) -> None:
        if self._loading or row < 0 or row >= len(self._types):
            return
        query_type = self._types[row]
        self._loading = True
        self.type_name.setText(str(query_type.get("name", "Query")))
        self.weight.setValue(int(query_type.get("weight", 1)))
        self.prefix.setText(str(query_type.get("prefix", "")))
        self.fields.setRowCount(0)
        for field in query_type.get("fields", []):
            self._append_field_row(field)
        self._loading = False

    def _store_type(self) -> None:
        row = self.type_list.currentRow()
        if self._loading or row < 0 or row >= len(self._types):
            return
        fields: list[dict[str, Any]] = []
        for field_row in range(self.fields.rowCount()):
            field: dict[str, Any] = {
                "name": self._cell(field_row, 0) or f"field{field_row + 1}",
                "type": (self._cell(field_row, 1) or "integer").lower().replace(" ", "_"),
            }
            for key, column in (("min", 2), ("max", 3), ("fixed", 4)):
                value = self._value(self._cell(field_row, column))
                if value != "":
                    field[key] = value
            options = self._cell(field_row, 5)
            if options:
                field["values"] = [self._value(value.strip()) for value in options.split(",")]
            fields.append(field)
        self._types[row] = {
            "name": self.type_name.text().strip() or f"Query {row + 1}",
            "weight": self.weight.value(),
            "prefix": self._value(self.prefix.text()),
            "fields": fields,
        }
        item = self.type_list.item(row)
        prefix = self._types[row]["prefix"]
        prefix_text = f" [{prefix}]" if prefix not in (None, "") else ""
        item.setText(f"{row + 1:02d}. {self._types[row]['name']}{prefix_text}  {self.weight.value()}%")

    def _add_type(self) -> None:
        self._store_type()
        self._types.append({
            "name": f"Query Type {len(self._types) + 1}", "weight": 50,
            "prefix": len(self._types) + 1,
            "fields": [{"name": "x", "type": "integer", "min": 1, "max": 100}],
        })
        self._refresh_types(len(self._types) - 1)

    def _remove_type(self) -> None:
        row = self.type_list.currentRow()
        if row < 0:
            return
        if len(self._types) == 1:
            QMessageBox.warning(self, "Query Types", "Query List cần ít nhất một loại.")
            return
        del self._types[row]
        self._refresh_types(min(row, len(self._types) - 1))

    def _add_field(self) -> None:
        self._append_field_row({
            "name": f"field{self.fields.rowCount() + 1}", "type": "integer",
            "min": 1, "max": 100,
        })
        self.fields.setCurrentCell(self.fields.rowCount() - 1, 0)

    def _remove_field(self) -> None:
        if self.fields.currentRow() >= 0:
            self.fields.removeRow(self.fields.currentRow())
            self._store_type()

    def _move_field(self, offset: int) -> None:
        row = self.fields.currentRow()
        target = row + offset
        if row < 0 or target < 0 or target >= self.fields.rowCount():
            return
        values = [[self._cell(item_row, column) for column in range(6)]
                  for item_row in range(self.fields.rowCount())]
        values[row], values[target] = values[target], values[row]
        self._loading = True
        for item_row, row_values in enumerate(values):
            for column, value in enumerate(row_values):
                self.fields.setItem(item_row, column, QTableWidgetItem(value))
        self._loading = False
        self.fields.setCurrentCell(target, 0)
        self._store_type()

    def _append_field_row(self, field: dict[str, Any]) -> None:
        row = self.fields.rowCount()
        self.fields.insertRow(row)
        options = field.get("values", [])
        values = (
            field.get("name", "field"), field.get("type", "integer"),
            field.get("min", ""), field.get("max", ""), field.get("fixed", ""),
            ", ".join(map(str, options)) if options else "",
        )
        for column, value in enumerate(values):
            self.fields.setItem(row, column, QTableWidgetItem(str(value)))

    def _accept(self) -> None:
        self._store_type()
        if not self._types or any(not item.get("fields") and item.get("prefix") in (None, "")
                                  for item in self._types):
            QMessageBox.warning(self, "Query Schema", "Mỗi loại phải có prefix hoặc ít nhất một field.")
            return
        if sum(float(item.get("weight", 0)) for item in self._types) <= 0:
            QMessageBox.warning(self, "Query Schema", "Tổng weight phải lớn hơn 0.")
            return
        self.accept()

    def _cell(self, row: int, column: int) -> str:
        item = self.fields.item(row, column)
        return item.text().strip() if item else ""

    @staticmethod
    def _value(value: str) -> Any:
        text = value.strip()
        if not text:
            return ""
        try:
            return int(text)
        except ValueError:
            try:
                return float(text)
            except ValueError:
                return text

    @staticmethod
    def _set_combo(combo: QComboBox, block_value: Any) -> None:
        index = combo.findData(block_value)
        combo.setCurrentIndex(max(0, index))

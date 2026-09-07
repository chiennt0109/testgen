"""Visual input-schema editor widgets."""
from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .query_editor import QuerySchemaDialog


BLOCK_TYPES = [
    "Integer", "Long Long", "Real", "String", "Array", "Permutation",
    "Matrix", "Grid", "Pair", "Triple", "Record/List", "Query List",
    "Interval List", "Graph", "Tree", "Weighted Graph", "Weighted Tree",
    "Operation List", "Raw Custom Block",
]

ARRAY_PATTERNS = [
    "Random", "All Equal", "Increasing", "Strict Increasing", "Decreasing",
    "Strict Decreasing", "Nondecreasing", "Nonincreasing", "Alternating",
    "Zigzag", "Many Duplicates", "Few Distinct", "Permutation", "Binary",
    "Mostly Zero", "Mostly One", "Arithmetic Progression", "Periodic",
    "Mountain", "Valley", "Random Blocks", "Extreme Values", "Custom Pattern",
]


class SchemaBuilder(QWidget):
    """Edit schema blocks through forms instead of requiring JSON knowledge."""

    schema_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._schema: list[dict[str, Any]] = []
        self._loading = False
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        intro = QLabel(
            "Tạo các block theo đúng thứ tự xuất hiện trong input. "
            "Giá trị min/max/length có thể là số hoặc biểu thức như n, n-1."
        )
        intro.setWordWrap(True)
        outer.addWidget(intro)

        controls = QHBoxLayout()
        self.add_type = QComboBox()
        self.add_type.addItems(BLOCK_TYPES)
        add_button = QPushButton("＋ Thêm block")
        add_button.clicked.connect(self._add)
        duplicate = QPushButton("Nhân bản")
        duplicate.clicked.connect(self._duplicate)
        remove = QPushButton("Xóa")
        remove.clicked.connect(self._remove)
        up = QPushButton("↑")
        up.setToolTip("Di chuyển lên")
        up.clicked.connect(lambda: self._move(-1))
        down = QPushButton("↓")
        down.setToolTip("Di chuyển xuống")
        down.clicked.connect(lambda: self._move(1))
        for widget in (self.add_type, add_button, duplicate, remove, up, down):
            controls.addWidget(widget)
        controls.addStretch()
        outer.addLayout(controls)

        splitter = QSplitter()
        self.blocks = QListWidget()
        self.blocks.setMinimumWidth(250)
        self.blocks.currentRowChanged.connect(self._select)
        splitter.addWidget(self.blocks)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        editor = QWidget()
        form = QFormLayout(editor)
        self.type_label = QLabel("—")
        self.name = QLineEdit()
        self.name.setPlaceholderText("Ví dụ: n, k, a, edges")
        self.minimum = QLineEdit()
        self.minimum.setPlaceholderText("Ví dụ: 1 hoặc -n")
        self.maximum = QLineEdit()
        self.maximum.setPlaceholderText("Ví dụ: 100000 hoặc n*(n-1)/2")
        self.length = QLineEdit()
        self.length.setPlaceholderText("Ví dụ: n")
        self.count = QLineEdit()
        self.count.setPlaceholderText("Ví dụ: q")
        self.n_ref = QLineEdit()
        self.n_ref.setPlaceholderText("Biến số đỉnh, thường là n")
        self.m_ref = QLineEdit()
        self.m_ref.setPlaceholderText("Biến số cạnh, thường là m")
        self.pattern = QComboBox()
        self.pattern.setEditable(True)
        self.layout = QComboBox()
        self.layout.addItem("Ghép cùng dòng", "same_line")
        self.layout.addItem("Kết thúc dòng", "line")
        self.newline = QCheckBox("Xuống dòng sau block này")
        self.distinct = QCheckBox("Các giá trị khác nhau")
        self.shuffle = QCheckBox("Trộn kết quả")
        self.connected = QCheckBox("Liên thông")
        self.simple = QCheckBox("Đơn đồ thị (không cạnh trùng)")
        self.simple.setChecked(True)
        self.directed = QCheckBox("Có hướng")
        self.weighted = QCheckBox("Có trọng số")
        self.weight_min = QLineEdit("1")
        self.weight_max = QLineEdit("100")
        self.extra = QLineEdit()
        self.extra.setPlaceholderText('Tùy chọn nâng cao dạng JSON, ví dụ {"alphabet":"binary"}')
        self.query_summary = QLabel()
        self.query_summary.setWordWrap(True)
        self.edit_queries = QPushButton("Chỉnh cấu trúc query…")
        self.edit_queries.clicked.connect(self._edit_query_schema)
        form.addRow("Loại block", self.type_label)
        form.addRow("Tên biến", self.name)
        form.addRow("Giá trị nhỏ nhất", self.minimum)
        form.addRow("Giá trị lớn nhất", self.maximum)
        form.addRow("Độ dài", self.length)
        form.addRow("Số dòng/phần tử", self.count)
        form.addRow("Tham chiếu n", self.n_ref)
        form.addRow("Tham chiếu m", self.m_ref)
        form.addRow("Pattern", self.pattern)
        form.addRow("Cách xuất", self.layout)
        form.addRow("", self.newline)
        form.addRow("", self.distinct)
        form.addRow("", self.shuffle)
        form.addRow("", self.connected)
        form.addRow("", self.simple)
        form.addRow("", self.directed)
        form.addRow("", self.weighted)
        form.addRow("Trọng số min", self.weight_min)
        form.addRow("Trọng số max", self.weight_max)
        form.addRow("Query Types", self.query_summary)
        form.addRow("", self.edit_queries)
        form.addRow("Tùy chọn khác", self.extra)
        self.form = form
        scroll.setWidget(editor)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(1, 1)
        outer.addWidget(splitter, 1)

        for widget in (self.name, self.minimum, self.maximum, self.length,
                       self.count, self.n_ref, self.m_ref, self.weight_min,
                       self.weight_max, self.extra):
            widget.editingFinished.connect(self._store)
        self.pattern.currentTextChanged.connect(self._store)
        self.layout.currentIndexChanged.connect(self._store)
        for widget in (self.newline, self.distinct, self.shuffle, self.connected,
                       self.simple, self.directed, self.weighted):
            widget.toggled.connect(self._store)

    def schema(self) -> list[dict[str, Any]]:
        """Return a detached serializable schema."""

        self._store()
        return json.loads(json.dumps(self._schema, ensure_ascii=False))

    def set_schema(self, schema: list[dict[str, Any]]) -> None:
        """Replace all blocks and refresh the editor."""

        self._schema = json.loads(json.dumps(schema, ensure_ascii=False))
        self._refresh()

    def _add(self) -> None:
        type_names = {
            "Record/List": "record_list",
            "Query List": "query_list",
            "Interval List": "interval_list",
            "Weighted Graph": "weighted_graph",
            "Weighted Tree": "weighted_tree",
            "Operation List": "operation_list",
            "Raw Custom Block": "raw_custom_block",
            "Long Long": "long_long",
        }
        kind = type_names.get(
            self.add_type.currentText(), self.add_type.currentText().lower().replace(" ", "_"))
        block: dict[str, Any] = {"type": kind, "name": f"var{len(self._schema) + 1}"}
        if kind in {"integer", "long_long", "real"}:
            block.update({"min": 1, "max": 100})
        elif kind in {"array", "permutation", "string"}:
            block.update({"length": "n", "min": 0, "max": 100, "pattern": "random"})
        elif "graph" in kind:
            block.update({"n": "n", "m": "m", "simple": True, "pattern": "random_sparse"})
        elif "tree" in kind:
            block.update({"n": "n", "pattern": "random_tree"})
        elif kind in {"query_list", "interval_list", "operation_list"}:
            block.update({"count": "q", "pattern": "random_range"})
            if kind in {"query_list", "operation_list"}:
                block.update({
                    "duplicate_policy": "allow", "query_order": "random",
                    "one_query_per_line": True,
                    "query_types": [{
                        "name": "Range Query", "weight": 100, "prefix": "",
                        "fields": [
                            {"name": "l", "type": "integer", "min": 1, "max": "n"},
                            {"name": "r", "type": "integer", "min": "l", "max": "n"},
                        ],
                    }],
                })
        self._schema.append(block)
        self._refresh(len(self._schema) - 1)
        self.schema_changed.emit()

    def _duplicate(self) -> None:
        row = self.blocks.currentRow()
        if row < 0:
            return
        self._store()
        duplicate = json.loads(json.dumps(self._schema[row]))
        duplicate["name"] = f"{duplicate.get('name', 'var')}_copy"
        self._schema.insert(row + 1, duplicate)
        self._refresh(row + 1)
        self.schema_changed.emit()

    def _remove(self) -> None:
        row = self.blocks.currentRow()
        if row < 0:
            return
        del self._schema[row]
        self._refresh(min(row, len(self._schema) - 1))
        self.schema_changed.emit()

    def _move(self, offset: int) -> None:
        row = self.blocks.currentRow()
        target = row + offset
        if row < 0 or target < 0 or target >= len(self._schema):
            return
        self._store()
        self._schema[row], self._schema[target] = self._schema[target], self._schema[row]
        self._refresh(target)
        self.schema_changed.emit()

    def _refresh(self, selected: int = 0) -> None:
        self._loading = True
        self.blocks.clear()
        for index, block in enumerate(self._schema, 1):
            kind = str(block.get("type", "block")).replace("_", " ").title()
            self.blocks.addItem(f"{index:02d}. {block.get('name', '—')}  ·  {kind}")
        self._loading = False
        if self._schema:
            self.blocks.setCurrentRow(max(0, min(selected, len(self._schema) - 1)))
        else:
            self._clear_editor()

    def _select(self, row: int) -> None:
        if self._loading or row < 0 or row >= len(self._schema):
            return
        block = self._schema[row]
        self._loading = True
        kind = str(block.get("type", ""))
        self.type_label.setText(kind.replace("_", " ").title())
        self.name.setText(str(block.get("name", "")))
        self.minimum.setText(self._text(block.get("min")))
        self.maximum.setText(self._text(block.get("max")))
        self.length.setText(self._text(block.get("length")))
        self.count.setText(self._text(block.get("count")))
        self.n_ref.setText(self._text(block.get("n")))
        self.m_ref.setText(self._text(block.get("m")))
        patterns = ARRAY_PATTERNS if kind in {"array", "permutation"} else self._patterns_for(kind)
        self.pattern.clear()
        self.pattern.addItems(patterns)
        self.pattern.setCurrentText(str(block.get("pattern", "random")).replace("_", " ").title())
        self.layout.setCurrentIndex(0 if block.get("layout") == "same_line" else 1)
        self.newline.setChecked(bool(block.get("newline")))
        self.distinct.setChecked(bool(block.get("distinct")))
        self.shuffle.setChecked(bool(block.get("shuffle")))
        self.connected.setChecked(bool(block.get("connected")))
        self.simple.setChecked(bool(block.get("simple", True)))
        self.directed.setChecked(bool(block.get("directed")))
        self.weighted.setChecked(bool(block.get("weighted")) or kind.startswith("weighted_"))
        self.weight_min.setText(self._text(block.get("weight_min", 1)))
        self.weight_max.setText(self._text(block.get("weight_max", 100)))
        known = {"type", "name", "min", "max", "length", "count", "n", "m",
                 "pattern", "layout", "newline", "distinct", "shuffle", "connected",
                 "simple", "directed", "weighted", "weight_min", "weight_max",
                 "query_types", "duplicate_policy", "query_order",
                 "one_query_per_line", "custom_order"}
        extra = {key: value for key, value in block.items() if key not in known}
        self.extra.setText(json.dumps(extra, ensure_ascii=False) if extra else "")
        is_query = kind in {"query_list", "operation_list"}
        is_graph = "graph" in kind
        self.form.setRowVisible(self.n_ref, is_graph or "tree" in kind)
        self.form.setRowVisible(self.m_ref, is_graph)
        self.form.setRowVisible(self.query_summary, is_query)
        self.form.setRowVisible(self.edit_queries, is_query)
        query_types = block.get("query_types", [])
        self.query_summary.setText(
            f"{len(query_types)} loại · " + ", ".join(
                f"{item.get('name', 'Query')} ({item.get('weight', 0)}%)"
                for item in query_types))
        self._loading = False

    def _store(self) -> None:
        row = self.blocks.currentRow()
        if self._loading or row < 0 or row >= len(self._schema):
            return
        old_block = self._schema[row]
        block = {"type": old_block.get("type", "integer")}
        for key in ("query_types", "duplicate_policy", "query_order",
                    "one_query_per_line", "custom_order"):
            if key in old_block:
                block[key] = old_block[key]
        for key, widget in (("name", self.name), ("min", self.minimum),
                            ("max", self.maximum), ("length", self.length),
                            ("count", self.count), ("n", self.n_ref),
                            ("m", self.m_ref), ("weight_min", self.weight_min),
                            ("weight_max", self.weight_max)):
            value = self._value(widget.text())
            if value != "":
                block[key] = value
        pattern = self.pattern.currentText().strip().lower().replace(" ", "_")
        if pattern:
            block["pattern"] = pattern
        if self.layout.currentData() == "same_line":
            block["layout"] = "same_line"
        for key, widget in (("newline", self.newline), ("distinct", self.distinct),
                            ("shuffle", self.shuffle), ("connected", self.connected),
                            ("simple", self.simple), ("directed", self.directed),
                            ("weighted", self.weighted)):
            if widget.isChecked() or key == "simple":
                block[key] = widget.isChecked()
        try:
            if self.extra.text().strip():
                extra = json.loads(self.extra.text())
                if not isinstance(extra, dict):
                    raise ValueError("Tùy chọn khác phải là một JSON object")
                block.update(extra)
        except (json.JSONDecodeError, ValueError) as exc:
            QMessageBox.warning(self, "Tùy chọn không hợp lệ", str(exc))
            return
        self._schema[row] = block
        item = self.blocks.item(row)
        item.setText(f"{row + 1:02d}. {block.get('name', '—')}  ·  "
                     f"{str(block['type']).replace('_', ' ').title()}")
        self.schema_changed.emit()

    def _edit_query_schema(self) -> None:
        row = self.blocks.currentRow()
        if row < 0:
            return
        self._store()
        dialog = QuerySchemaDialog(self._schema[row], self)
        if dialog.exec() == QuerySchemaDialog.DialogCode.Accepted:
            self._schema[row] = dialog.result_block()
            self._select(row)
            self.schema_changed.emit()

    def _clear_editor(self) -> None:
        self._loading = True
        self.type_label.setText("Chưa có block")
        for widget in (self.name, self.minimum, self.maximum, self.length,
                       self.count, self.n_ref, self.m_ref, self.extra):
            widget.clear()
        self._loading = False

    @staticmethod
    def _text(value: Any) -> str:
        return "" if value is None else str(value)

    @staticmethod
    def _value(value: str) -> str | int | float:
        value = value.strip()
        if not value:
            return ""
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return value

    @staticmethod
    def _patterns_for(kind: str) -> list[str]:
        if kind == "string":
            return ["Random", "All Same", "Alternating", "Periodic", "Palindrome",
                    "Almost Palindrome", "Unique Characters", "Many Repetitions",
                    "Long Runs", "Repeated Prefix", "Repeated Suffix", "Injected Pattern"]
        if "graph" in kind:
            return ["Random Sparse", "Random Dense", "Path", "Star", "Cycle",
                    "Complete", "Almost Complete", "Disconnected", "Two Components",
                    "Many Components"]
        if "tree" in kind:
            return ["Random Tree", "Path", "Star", "Balanced Binary Tree",
                    "Random Parent", "Broom", "Caterpillar"]
        if kind in {"query_list", "operation_list", "interval_list"}:
            return ["Random Range", "Single Point", "Whole Range", "Prefix", "Suffix",
                    "Short Range", "Long Range", "Nested", "Overlapping", "Repeated",
                    "Custom"]
        return ["Random"]

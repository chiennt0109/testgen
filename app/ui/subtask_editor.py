"""Basic visual editor for Subtask identity and test range."""
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QMessageBox, QSpinBox,
    QVBoxLayout, QWidget,
)


class SubtaskEditorDialog(QDialog):
    """Edit a subtask name and inclusive test range with validated controls."""

    def __init__(self, name: str, start: int, end: int, test_count: int,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Thông tin Subtask")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(name)
        self.start = QSpinBox(); self.start.setRange(1, test_count); self.start.setValue(start)
        self.end = QSpinBox(); self.end.setRange(1, test_count); self.end.setValue(end)
        form.addRow("Tên subtask", self.name)
        form.addRow("Test bắt đầu", self.start)
        form.addRow("Test kết thúc", self.end)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Subtask", "Tên subtask không được để trống.")
            return
        if self.start.value() > self.end.value():
            QMessageBox.warning(self, "Subtask", "Test bắt đầu phải nhỏ hơn hoặc bằng test kết thúc.")
            return
        self.accept()

    def values(self) -> tuple[str, int, int]:
        """Return validated dialog values."""

        return self.name.text().strip(), self.start.value(), self.end.value()

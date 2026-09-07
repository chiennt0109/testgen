"""Main PySide6 window and task-oriented pages."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.analyzers import analyze
from app.core import GenerationEngine, GenerationPipeline, StressTester
from app.exporters import export_zip
from app.models import Project, TestGroup
from app.runners import SolutionRunner
from app.validators import validate_input

from .schema_builder import SchemaBuilder


class Worker(QObject):
    """Execute a callable away from the GUI thread."""

    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)

    def __init__(self, function: Callable[[Callable[[int, int], None]], Any]) -> None:
        super().__init__()
        self.function = function

    @Slot()
    def run(self) -> None:
        try:
            self.finished.emit(self.function(self.progress.emit))
        except Exception as exc:  # UI boundary: errors are logged and shown.
            logging.exception("Background task failed")
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    """Project editor coordinating UI pages with independent core services."""

    PAGE_NAMES = [
        "General", "Input Schema", "Test Plan", "Subtasks", "Solution",
        "Validator", "Stress Test", "Analyze", "Export",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.project = Project()
        self.path: Path | None = None
        self.generated_path: Path | None = None
        self.preview_text = ""
        self._cancel_requested = False
        self._thread: QThread | None = None
        self._worker: Worker | None = None
        self.setWindowTitle("Test Generator Studio")
        self.resize(1280, 800)
        self._build_shell()
        self._build_toolbar()
        self._apply_project()
        self._change_mode(0)
        self.statusBar().showMessage("Sẵn sàng")

    def _build_shell(self) -> None:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        self.nav = QListWidget()
        self.nav.addItems(self.PAGE_NAMES)
        self.nav.setMaximumWidth(190)
        self.nav.setMinimumWidth(155)
        self.pages = QStackedWidget()
        layout.addWidget(self.nav)
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(root)

        self.pages.addWidget(self._general_page())
        self.pages.addWidget(self._schema_page())
        self.pages.addWidget(self._test_plan_page())
        self.pages.addWidget(self._subtasks_page())
        self.pages.addWidget(self._solution_page())
        self.pages.addWidget(self._validator_page())
        self.pages.addWidget(self._stress_page())
        self.pages.addWidget(self._analyze_page())
        self.pages.addWidget(self._export_page())
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(0)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Chức năng chính")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        actions = [
            ("New Project", self.new_project),
            ("Open Project", self.open_project),
            ("Save", self.save_project),
            ("Save As", self.save_project_as),
            ("Generate Preview", self.generate_preview),
            ("Generate All", self.generate_all),
            ("Validate", self.validate_current),
            ("Build Output", self.build_output),
            ("Stress Test", self.start_stress),
            ("Analyze", self.run_analyze),
            ("Export ZIP", self.export_current),
            ("Open Output Folder", self.open_output_folder),
        ]
        for label, callback in actions:
            action = QAction(label, self)
            action.triggered.connect(callback)
            toolbar.addAction(action)
        toolbar.addSeparator()
        self.mode = QComboBox()
        self.mode.addItems(["Basic Mode", "Advanced Mode"])
        self.mode.currentIndexChanged.connect(self._change_mode)
        toolbar.addWidget(self.mode)

        bottom = QWidget()
        status_layout = QHBoxLayout(bottom)
        status_layout.setContentsMargins(8, 2, 8, 2)
        self.task_status = QLabel("Sẵn sàng")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setMaximumWidth(260)
        self.cancel_button = QPushButton("Hủy")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel)
        status_layout.addWidget(self.task_status, 1)
        status_layout.addWidget(self.progress)
        status_layout.addWidget(self.cancel_button)
        self.statusBar().addPermanentWidget(bottom, 1)

    def _general_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        title = QLabel("<h2>Cấu hình chung</h2>")
        outer.addWidget(title)
        group = QGroupBox("Bài toán và cấu trúc đầu ra")
        form = QFormLayout(group)
        self.name = QLineEdit()
        self.input_filename = QLineEdit()
        self.output_filename = QLineEdit()
        self.test_count = QSpinBox()
        self.test_count.setRange(1, 100000)
        self.folder_prefix = QLineEdit("test")
        self.folder_digits = QSpinBox()
        self.folder_digits.setRange(1, 8)
        self.output_layout = QComboBox()
        self.output_layout.addItems(["Mỗi test trong một thư mục"])
        self.duplicate_policy = QComboBox()
        self.duplicate_policy.addItem("Warn", "warn")
        self.duplicate_policy.addItem("Allow", "allow")
        self.duplicate_policy.addItem("Regenerate", "regenerate")
        self.duplicate_policy.addItem("Fail", "fail")
        self.seed = QLineEdit()
        self.time_limit = QDoubleSpinBox()
        self.time_limit.setRange(0.05, 3600)
        self.time_limit.setDecimals(2)
        self.time_limit.setSuffix(" s")
        self.memory_limit = QSpinBox()
        self.memory_limit.setRange(16, 1048576)
        self.memory_limit.setSuffix(" MB")
        form.addRow("Problem name", self.name)
        form.addRow("Input filename", self.input_filename)
        form.addRow("Output filename", self.output_filename)
        form.addRow("Test count", self.test_count)
        form.addRow("Test folder prefix", self.folder_prefix)
        form.addRow("Number of digits", self.folder_digits)
        form.addRow("Output layout", self.output_layout)
        form.addRow("Duplicate inputs", self.duplicate_policy)
        form.addRow("Random seed", self.seed)
        form.addRow("Time limit", self.time_limit)
        form.addRow("Memory limit", self.memory_limit)
        outer.addWidget(group)
        note = QLabel("Tên file tự đổi theo tên bài cho đến khi bạn sửa tên file riêng.")
        note.setWordWrap(True)
        outer.addWidget(note)
        outer.addStretch()
        self.name.textEdited.connect(self._problem_renamed)
        return page

    def _schema_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>Input Schema Builder</h2>"))
        self.schema_builder = SchemaBuilder()
        layout.addWidget(self.schema_builder, 3)
        preview_group = QGroupBox("Generate Preview")
        preview_layout = QVBoxLayout(preview_group)
        preview_buttons = QHBoxLayout()
        for label, callback in (("Sinh thử", self.generate_preview),
                                ("Regenerate", self.regenerate_preview),
                                ("Copy", self.copy_preview),
                                ("Save This Test", self.save_preview)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            preview_buttons.addWidget(button)
        preview_buttons.addStretch()
        self.preview_meta = QLabel("Chưa có preview")
        preview_buttons.addWidget(self.preview_meta)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        preview_layout.addLayout(preview_buttons)
        preview_layout.addWidget(self.preview)
        layout.addWidget(preview_group, 2)
        return page

    def _test_plan_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>Test Plan</h2>"))
        layout.addWidget(QLabel("Chia bộ test thành các nhóm; overrides là JSON theo tên biến."))
        self.plan_table = QTableWidget(0, 5)
        self.plan_table.setHorizontalHeaderLabels(
            ["Group name", "Number of tests", "Size profile", "Seed mode", "Overrides"])
        self.plan_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.plan_table)
        buttons = QHBoxLayout()
        add = QPushButton("Thêm nhóm")
        add.clicked.connect(self._add_plan_row)
        edge = QPushButton("Add Edge Cases")
        edge.clicked.connect(self._add_edge_groups)
        remove = QPushButton("Xóa nhóm")
        remove.clicked.connect(lambda: self._remove_table_row(self.plan_table))
        buttons.addWidget(add)
        buttons.addWidget(edge)
        buttons.addWidget(remove)
        buttons.addStretch()
        layout.addLayout(buttons)
        return page

    def _subtasks_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>Subtasks</h2>"))
        self.subtask_table = QTableWidget(0, 4)
        self.subtask_table.setHorizontalHeaderLabels(
            ["Subtask", "Test bắt đầu", "Test kết thúc", "Constraints (JSON)"])
        self.subtask_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.subtask_table)
        buttons = QHBoxLayout()
        add = QPushButton("Thêm subtask")
        add.clicked.connect(self._add_subtask_row)
        remove = QPushButton("Xóa")
        remove.clicked.connect(lambda: self._remove_table_row(self.subtask_table))
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch()
        layout.addLayout(buttons)
        return page

    def _solution_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>Solution Runner</h2>"))
        form = QFormLayout()
        self.solution_path = QLineEdit()
        self.brute_path = QLineEdit()
        self.language = QComboBox()
        self.language.addItems(["cpp", "python", "exe"])
        self.cpp_standard = QComboBox()
        self.cpp_standard.addItems(["c++17", "c++20"])
        self.io_mode = QComboBox()
        self.io_mode.addItem("STDIN / STDOUT", "stdio")
        self.io_mode.addItem("File I/O (freopen)", "file")
        self.compiler_path = QLineEdit()
        self.compiler_status = QLabel("Chưa kiểm tra")
        form.addRow("Solution", self._path_picker(self.solution_path, "Chọn solution"))
        form.addRow("Brute", self._path_picker(self.brute_path, "Chọn brute"))
        form.addRow("Language", self.language)
        form.addRow("C++ standard", self.cpp_standard)
        form.addRow("I/O mode", self.io_mode)
        form.addRow("g++ path", self._path_picker(self.compiler_path, "Chọn g++"))
        form.addRow("Compiler status", self.compiler_status)
        layout.addLayout(form)
        test = QPushButton("Test Compiler")
        test.clicked.connect(self.test_compiler)
        layout.addWidget(test)
        layout.addStretch()
        return page

    def _validator_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>Validator</h2>"))
        self.builtin_validator = QCheckBox("Bật built-in validator")
        self.builtin_validator.setChecked(True)
        self.custom_validator = QLineEdit()
        layout.addWidget(self.builtin_validator)
        form = QFormLayout()
        form.addRow("Custom validator.py", self._path_picker(self.custom_validator, "Chọn validator.py"))
        layout.addLayout(form)
        validate = QPushButton("Validate preview / generated tests")
        validate.clicked.connect(self.validate_current)
        layout.addWidget(validate)
        self.validation_result = QPlainTextEdit()
        self.validation_result.setReadOnly(True)
        layout.addWidget(self.validation_result)
        return page

    def _stress_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>Stress Test & Brute Cross-check</h2>"))
        form = QFormLayout()
        self.stress_iterations = QSpinBox()
        self.stress_iterations.setRange(1, 1000000)
        self.stress_iterations.setValue(100)
        self.stress_profile = QComboBox()
        self.stress_profile.addItems(["Small random", "Edge cases", "Custom generator"])
        self.stress_timeout = QDoubleSpinBox()
        self.stress_timeout.setRange(.05, 60)
        self.stress_timeout.setValue(2)
        self.stress_timeout.setSuffix(" s")
        form.addRow("Iterations", self.stress_iterations)
        form.addRow("Generator profile", self.stress_profile)
        form.addRow("Timeout", self.stress_timeout)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        start = QPushButton("Start Cross Check")
        start.clicked.connect(self.start_stress)
        stop = QPushButton("Stop")
        stop.clicked.connect(self._cancel)
        buttons.addWidget(start)
        buttons.addWidget(stop)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.stress_status = QPlainTextEdit()
        self.stress_status.setReadOnly(True)
        layout.addWidget(self.stress_status)
        return page

    def _analyze_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>Test Quality Analyzer</h2>"))
        button = QPushButton("Analyze generated tests")
        button.clicked.connect(self.run_analyze)
        layout.addWidget(button)
        self.analysis_result = QPlainTextEdit()
        self.analysis_result.setReadOnly(True)
        layout.addWidget(self.analysis_result)
        return page

    def _export_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("<h2>Export</h2>"))
        self.export_source = QLineEdit()
        self.export_destination = QLineEdit()
        form = QFormLayout()
        form.addRow("Generated folder", self._path_picker(self.export_source, "Chọn thư mục", directory=True))
        form.addRow("ZIP destination", self._path_picker(self.export_destination, "Chọn ZIP", save=True))
        layout.addLayout(form)
        export = QPushButton("Export ZIP")
        export.clicked.connect(self.export_current)
        open_folder = QPushButton("Open Output Folder")
        open_folder.clicked.connect(self.open_output_folder)
        layout.addWidget(export)
        layout.addWidget(open_folder)
        self.manifest_details = QPlainTextEdit()
        self.manifest_details.setReadOnly(True)
        layout.addWidget(QLabel("Manifest details"))
        layout.addWidget(self.manifest_details)
        return page

    def _path_picker(self, edit: QLineEdit, title: str, *, directory: bool = False,
                     save: bool = False) -> QWidget:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton("Browse…")

        def choose() -> None:
            if directory:
                value = QFileDialog.getExistingDirectory(self, title)
            elif save:
                value, _ = QFileDialog.getSaveFileName(self, title, "", "ZIP (*.zip)")
            else:
                value, _ = QFileDialog.getOpenFileName(self, title)
            if value:
                edit.setText(value)

        button.clicked.connect(choose)
        layout.addWidget(edit, 1)
        layout.addWidget(button)
        return wrapper

    def _problem_renamed(self, text: str) -> None:
        old = self.project.problem_name
        if self.input_filename.text() == f"{old}.inp":
            self.input_filename.setText(f"{text}.inp")
        if self.output_filename.text() == f"{old}.out":
            self.output_filename.setText(f"{text}.out")
        self.project.problem_name = text

    def _sync_project(self) -> None:
        self.project.problem_name = self.name.text().strip() or "PROBLEM"
        self.project.input_filename = self.input_filename.text().strip() or f"{self.project.problem_name}.inp"
        self.project.output_filename = self.output_filename.text().strip() or f"{self.project.problem_name}.out"
        self.project.test_count = self.test_count.value()
        prefix = self.folder_prefix.text().strip() or "test"
        self.project.test_folder_pattern = prefix + "{index:0" + str(self.folder_digits.value()) + "d}"
        try:
            self.project.seed = int(self.seed.text())
        except ValueError as exc:
            raise ValueError("Random seed phải là số nguyên") from exc
        self.project.time_limit = self.time_limit.value()
        self.project.memory_limit_mb = self.memory_limit.value()
        self.project.output_layout = "folders" if self.output_layout.currentIndex() == 0 else "flat"
        self.project.duplicate_policy = str(self.duplicate_policy.currentData())
        self.project.schema = self.schema_builder.schema()
        self.project.test_plan = self._read_test_plan()
        self.project.subtasks = self._read_subtasks()
        self.project.solution_path = self._relative_path(self.solution_path.text())
        self.project.brute_path = self._relative_path(self.brute_path.text())
        self.project.validator_path = self._relative_path(self.custom_validator.text())
        self.project.language = self.language.currentText()
        self.project.io_mode = str(self.io_mode.currentData())
        self.project.cpp_standard = self.cpp_standard.currentText()
        self.project.compiler_path = self.compiler_path.text().strip()

    def _apply_project(self) -> None:
        self.name.setText(self.project.problem_name)
        self.input_filename.setText(self.project.input_filename)
        self.output_filename.setText(self.project.output_filename)
        self.test_count.setValue(self.project.test_count)
        pattern = self.project.test_folder_pattern
        self.folder_prefix.setText(pattern.split("{")[0] or "test")
        digits = 2
        if ":0" in pattern:
            try:
                digits = int(pattern.split(":0", 1)[1].split("d", 1)[0])
            except ValueError:
                digits = 2
        self.folder_digits.setValue(digits)
        self.seed.setText(str(self.project.seed))
        self.time_limit.setValue(self.project.time_limit)
        self.memory_limit.setValue(self.project.memory_limit_mb)
        self.output_layout.setCurrentIndex(0 if self.project.output_layout == "folders" else 1)
        duplicate_index = self.duplicate_policy.findData(self.project.duplicate_policy)
        self.duplicate_policy.setCurrentIndex(max(0, duplicate_index))
        self.schema_builder.set_schema(self.project.schema)
        self.solution_path.setText(self.project.solution_path)
        self.brute_path.setText(self.project.brute_path)
        self.custom_validator.setText(self.project.validator_path)
        self.language.setCurrentText(self.project.language)
        self.cpp_standard.setCurrentText(self.project.cpp_standard)
        self.compiler_path.setText(self.project.compiler_path)
        io_index = self.io_mode.findData(self.project.io_mode)
        self.io_mode.setCurrentIndex(max(0, io_index))
        self._fill_test_plan()
        self._fill_subtasks()

    def new_project(self) -> None:
        if not self._confirm_discard():
            return
        self.project = Project()
        self.path = None
        self.generated_path = None
        self.preview.clear()
        self._apply_project()
        self.statusBar().showMessage("Đã tạo project mới")

    def open_project(self) -> None:
        raw, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "Project JSON (*.json)")
        if not raw:
            return
        try:
            self.path = Path(raw)
            self.project = Project.load(self.path)
            self._apply_project()
            self.statusBar().showMessage(f"Đã mở {self.path}")
        except Exception as exc:
            QMessageBox.critical(self, "Open Project Error", str(exc))

    def save_project(self) -> None:
        if self.path is None:
            self.save_project_as()
            return
        try:
            self._sync_project()
            self.project.save(self.path)
            self.statusBar().showMessage(f"Đã lưu {self.path}")
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))

    def save_project_as(self) -> None:
        raw, _ = QFileDialog.getSaveFileName(self, "Save Project", "project.json", "JSON (*.json)")
        if raw:
            self.path = Path(raw)
            self.save_project()

    def generate_preview(self) -> None:
        self._generate_preview_with_seed_offset(1)

    def regenerate_preview(self) -> None:
        offset = int(self.preview_meta.property("offset") or 1) + 1
        self._generate_preview_with_seed_offset(offset)

    def _generate_preview_with_seed_offset(self, offset: int) -> None:
        try:
            self._sync_project()
            seed = self.project.seed + offset
            text, _ = GenerationEngine().generate(
                self.project, seed, index=offset, base=self._project_dir())
            valid, reason = validate_input(text, self.project.to_dict(), self._validator_file())
            self.preview_text = text
            self.preview.setPlainText(text)
            self.preview_meta.setProperty("offset", offset)
            self.preview_meta.setText(
                f"Seed: {seed}  ·  Group: Preview  ·  "
                f"Validation: {'OK' if valid else reason}")
            self.nav.setCurrentRow(1)
        except Exception as exc:
            QMessageBox.critical(self, "Generator Error", str(exc))

    def copy_preview(self) -> None:
        QApplication.clipboard().setText(self.preview.toPlainText())
        self.statusBar().showMessage("Đã copy preview")

    def save_preview(self) -> None:
        if not self.preview.toPlainText():
            QMessageBox.information(self, "Save This Test", "Hãy sinh preview trước.")
            return
        raw, _ = QFileDialog.getSaveFileName(self, "Save This Test", self.project.input_filename)
        if raw:
            Path(raw).write_text(self.preview.toPlainText(), encoding="utf-8")

    def generate_all(self) -> None:
        try:
            self._sync_project()
        except Exception as exc:
            QMessageBox.critical(self, "Configuration Error", str(exc))
            return
        destination = self._project_dir() / "generated" / self.project.problem_name

        def task(progress: Callable[[int, int], None]) -> Path:
            return GenerationPipeline().generate(
                self.project, self._project_dir(), destination,
                progress=progress, cancel=lambda: self._cancel_requested)

        self._start_task("Đang sinh toàn bộ test…", task, self._generation_finished)

    def validate_current(self) -> None:
        try:
            self._sync_project()
            results: list[str] = []
            if self.preview.toPlainText():
                valid, reason = validate_input(self.preview.toPlainText(), self.project.to_dict(), self._validator_file())
                results.append(f"Preview: {'OK' if valid else 'FAILED — ' + reason}")
            folder = self._resolved_generated_path()
            if folder and folder.exists():
                files = list(folder.glob("test*/*.inp"))
                for path in files:
                    valid, reason = validate_input(path.read_text(encoding="utf-8"), self.project.to_dict(), self._validator_file())
                    results.append(f"{path.parent.name}: {'OK' if valid else 'FAILED — ' + reason}")
            if not results:
                results.append("Chưa có preview hoặc generated test để validate.")
            self.validation_result.setPlainText("\n".join(results))
            self.nav.setCurrentRow(5)
        except Exception as exc:
            QMessageBox.critical(self, "Validator Error", str(exc))

    def build_output(self) -> None:
        folder = self._resolved_generated_path()
        if not folder or not folder.exists():
            QMessageBox.warning(self, "Build Output", "Chưa có thư mục generated.")
            return
        try:
            self._sync_project()
            runner = SolutionRunner(self.compiler_path.text().strip() or None)
            solution = self._project_dir() / self.project.solution_path
            executable = solution
            if solution.suffix.lower() == ".cpp":
                build_dir = self._project_dir() / ".tgs-build"
                build_dir.mkdir(exist_ok=True)
                executable = runner.compile(solution, build_dir / "solution.exe",
                                            self.cpp_standard.currentText())
            inputs = list(folder.glob("test*/*.inp"))

            def task(progress: Callable[[int, int], None]) -> Path:
                for index, input_path in enumerate(inputs, 1):
                    if self._cancel_requested:
                        raise RuntimeError("Build Output đã bị hủy")
                    result = runner.run(executable, input_path.read_text(encoding="utf-8"),
                                        self.project.time_limit, self.project.io_mode,
                                        self.project.input_filename, self.project.output_filename)
                    if result.status != "OK":
                        raise RuntimeError(f"{input_path.parent.name}: {result.status}\n{result.stderr}")
                    (input_path.parent / self.project.output_filename).write_text(result.stdout, encoding="utf-8")
                    progress(index, len(inputs))
                return folder

            self._start_task("Đang build output…", task,
                             lambda result: self.statusBar().showMessage(f"Đã build output tại {result}"))
        except Exception as exc:
            QMessageBox.critical(self, "Build Output Error", str(exc))

    def start_stress(self) -> None:
        try:
            self._sync_project()
            iterations = self.stress_iterations.value()
            timeout = self.stress_timeout.value()

            def task(progress: Callable[[int, int], None]) -> Any:
                return StressTester().run(
                    self.project, self._project_dir(), iterations, timeout,
                    progress=lambda current, total, seed, elapsed: progress(current, total),
                    cancelled=lambda: self._cancel_requested)

            self.nav.setCurrentRow(6)
            self.stress_status.setPlainText("Đang compile solution và brute…")
            self._start_task("Stress testing…", task, self._stress_finished)
        except Exception as exc:
            QMessageBox.critical(self, "Stress Test Error", str(exc))

    def run_analyze(self) -> None:
        folder = self._resolved_generated_path()
        if not folder or not folder.exists():
            QMessageBox.warning(self, "Analyze", "Chưa có generated tests.")
            return

        def task(progress: Callable[[int, int], None]) -> dict[str, Any]:
            result = analyze(folder)
            progress(1, 1)
            return result

        self.nav.setCurrentRow(7)
        self._start_task("Đang phân tích coverage…", task, self._analysis_finished)

    def export_current(self) -> None:
        source_text = self.export_source.text().strip()
        source = Path(source_text) if source_text else self._resolved_generated_path()
        if not source or not source.exists():
            QMessageBox.warning(self, "Export ZIP", "Chưa chọn thư mục generated hợp lệ.")
            return
        destination_text = self.export_destination.text().strip()
        destination = Path(destination_text) if destination_text else source.parent / f"{self.project.problem_name}_tests.zip"
        if destination.exists():
            answer = QMessageBox.question(
                self, "ZIP đã tồn tại", f"Ghi đè {destination.name}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            export_zip(source, destination)
            self.export_source.setText(str(source))
            self.export_destination.setText(str(destination))
            self.nav.setCurrentRow(8)
            self.statusBar().showMessage(f"Đã export {destination}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    def open_output_folder(self) -> None:
        folder = self._resolved_generated_path()
        if not folder or not folder.exists():
            QMessageBox.warning(self, "Open Output Folder", "Thư mục output chưa tồn tại.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve())))

    def test_compiler(self) -> None:
        runner = SolutionRunner(self.compiler_path.text().strip() or None)
        ok, message = runner.compiler_status()
        if ok and not self.compiler_path.text():
            self.compiler_path.setText(runner.gpp)
        self.compiler_status.setText(("✓ " if ok else "✗ ") + message)

    def _start_task(self, status: str, task: Callable[[Callable[[int, int], None]], Any],
                    completed: Callable[[Any], None]) -> None:
        if self._thread and self._thread.isRunning():
            QMessageBox.information(self, "Đang bận", "Một tác vụ nền đang chạy.")
            return
        self._cancel_requested = False
        self.cancel_button.setEnabled(True)
        self.progress.setValue(0)
        self.task_status.setText(status)
        thread = QThread(self)
        worker = Worker(task)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._update_progress)
        worker.finished.connect(completed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(self._task_failed)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._task_stopped)
        self._thread = thread
        self._worker = worker
        thread.start()

    def _update_progress(self, current: int, total: int) -> None:
        self.progress.setValue(round(current * 100 / max(1, total)))
        self.task_status.setText(f"Đang xử lý {current}/{total}")

    def _task_failed(self, message: str) -> None:
        QMessageBox.critical(self, "Task Error", message)
        self.task_status.setText("Tác vụ thất bại")

    def _task_stopped(self) -> None:
        self.cancel_button.setEnabled(False)
        if self.task_status.text().startswith("Đang"):
            self.task_status.setText("Hoàn tất")

    def _generation_finished(self, path: Any) -> None:
        self.generated_path = Path(path)
        self.export_source.setText(str(path))
        manifest = self.generated_path / "manifest.json"
        if manifest.exists():
            self.manifest_details.setPlainText(manifest.read_text(encoding="utf-8"))
        self.task_status.setText("Sinh test hoàn tất")
        self.statusBar().showMessage(f"Generated: {path}")

    def _stress_finished(self, result: Any) -> None:
        rate = result.passed / result.elapsed if result.elapsed else 0
        lines = [
            f"Passed: {result.passed}", f"Failed: {result.failed}",
            f"Elapsed: {result.elapsed:.3f}s", f"Tests/sec: {rate:.2f}",
            f"Current seed: {result.current_seed}",
        ]
        if result.counterexample:
            lines.append(f"Counterexample: {result.counterexample}")
        self.stress_status.setPlainText("\n".join(lines))
        self.task_status.setText("Stress test hoàn tất")

    def _analysis_finished(self, result: Any) -> None:
        self.analysis_result.setPlainText(json.dumps(result, indent=2, ensure_ascii=False))
        self.task_status.setText("Analyze hoàn tất")

    def _cancel(self) -> None:
        self._cancel_requested = True
        self.task_status.setText("Đang yêu cầu hủy…")

    def _change_mode(self, index: int) -> None:
        advanced = index == 1
        for page_index in (3, 5, 6, 7, 8):
            self.nav.item(page_index).setHidden(not advanced)
        self.manifest_details.setVisible(advanced)

    def _add_plan_row(self, values: tuple[str, int, str, str, str] | None = None) -> None:
        values = values or ("Random", 1, "small", "increment", "{}")
        row = self.plan_table.rowCount()
        self.plan_table.insertRow(row)
        for column, value in enumerate(values):
            self.plan_table.setItem(row, column, QTableWidgetItem(str(value)))

    def _add_edge_groups(self) -> None:
        for values in (("n=1", 1, "edge", "increment", '{"n":{"min":1,"max":1}}'),
                       ("Minimum values", 1, "edge", "increment", "{}"),
                       ("Maximum values", 1, "max", "increment", "{}"),
                       ("Adversarial", 1, "adversarial", "increment", "{}")):
            self._add_plan_row(values)

    def _read_test_plan(self) -> list[TestGroup]:
        groups: list[TestGroup] = []
        for row in range(self.plan_table.rowCount()):
            values = [self._cell(self.plan_table, row, column) for column in range(5)]
            try:
                overrides = json.loads(values[4] or "{}")
                groups.append(TestGroup(values[0] or "Random", int(values[1] or 1),
                                        values[2] or "random", values[3] or "increment", overrides))
            except (ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"Test Plan dòng {row + 1} không hợp lệ: {exc}") from exc
        return groups

    def _fill_test_plan(self) -> None:
        self.plan_table.setRowCount(0)
        for group in self.project.test_plan:
            self._add_plan_row((group.name, group.count, group.profile, group.seed_mode,
                                json.dumps(group.overrides, ensure_ascii=False)))

    def _add_subtask_row(self) -> None:
        row = self.subtask_table.rowCount()
        self.subtask_table.insertRow(row)
        for column, value in enumerate((f"Subtask {row + 1}", 1, self.project.test_count, "{}")):
            self.subtask_table.setItem(row, column, QTableWidgetItem(str(value)))

    def _read_subtasks(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for row in range(self.subtask_table.rowCount()):
            try:
                result.append({
                    "name": self._cell(self.subtask_table, row, 0),
                    "start": int(self._cell(self.subtask_table, row, 1)),
                    "end": int(self._cell(self.subtask_table, row, 2)),
                    "constraints": json.loads(self._cell(self.subtask_table, row, 3) or "{}"),
                })
            except (ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"Subtask dòng {row + 1} không hợp lệ: {exc}") from exc
        return result

    def _fill_subtasks(self) -> None:
        self.subtask_table.setRowCount(0)
        for item in self.project.subtasks:
            row = self.subtask_table.rowCount()
            self.subtask_table.insertRow(row)
            values = (item.get("name", "Subtask"), item.get("start", 1),
                      item.get("end", 1), json.dumps(item.get("constraints", {}), ensure_ascii=False))
            for column, value in enumerate(values):
                self.subtask_table.setItem(row, column, QTableWidgetItem(str(value)))

    @staticmethod
    def _remove_table_row(table: QTableWidget) -> None:
        if table.currentRow() >= 0:
            table.removeRow(table.currentRow())

    @staticmethod
    def _cell(table: QTableWidget, row: int, column: int) -> str:
        item = table.item(row, column)
        return item.text().strip() if item else ""

    def _project_dir(self) -> Path:
        return self.path.parent if self.path else Path.cwd()

    def _relative_path(self, value: str) -> str:
        value = value.strip()
        if not value:
            return ""
        path = Path(value)
        try:
            return str(path.resolve().relative_to(self._project_dir().resolve()))
        except ValueError:
            return str(path)

    def _validator_file(self) -> Path | None:
        if not self.custom_validator.text().strip():
            return None
        path = Path(self.custom_validator.text())
        return path if path.is_absolute() else self._project_dir() / path

    def _resolved_generated_path(self) -> Path | None:
        if self.generated_path:
            return self.generated_path
        if self.export_source.text().strip():
            return Path(self.export_source.text())
        candidate = self._project_dir() / "generated" / self.project.problem_name
        return candidate if candidate.exists() else None

    def _confirm_discard(self) -> bool:
        answer = QMessageBox.question(
            self, "New Project", "Tạo project mới? Hãy lưu thay đổi hiện tại trước khi tiếp tục.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes

    def closeEvent(self, event: Any) -> None:
        """Ask a running cooperative worker to stop before closing."""

        if self._thread and self._thread.isRunning():
            answer = QMessageBox.question(
                self, "Tác vụ đang chạy", "Hủy tác vụ và đóng ứng dụng?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._cancel_requested = True
            self._thread.quit()
            if not self._thread.wait(3000):
                QMessageBox.warning(self, "Đang dừng", "Tác vụ chưa dừng an toàn. Hãy chờ thêm rồi đóng lại.")
                event.ignore()
                return
        event.accept()

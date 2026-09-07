"""PySide6 GUI shell; domain work is delegated to core services."""
from __future__ import annotations
import json,logging
from pathlib import Path
from PySide6.QtCore import QObject,QThread,Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QApplication,QFileDialog,QFormLayout,QHBoxLayout,QLabel,QLineEdit,QListWidget,QMainWindow,QMessageBox,QPlainTextEdit,QProgressBar,QPushButton,QSpinBox,QStackedWidget,QToolBar,QVBoxLayout,QWidget)
from app.core import GenerationEngine,GenerationPipeline
from app.models import Project

class Worker(QObject):
    finished=Signal(object);failed=Signal(str);progress=Signal(int,int)
    def __init__(self,fn):super().__init__();self.fn=fn
    def run(self):
        try:self.finished.emit(self.fn(self.progress.emit))
        except Exception as exc:logging.exception("Background task failed");self.failed.emit(str(exc))

class MainWindow(QMainWindow):
    """Main navigation, editing, preview, and background batch controls."""
    def __init__(self):
        super().__init__();self.project=Project();self.path:Path|None=None;self.setWindowTitle("Test Generator Studio");self.resize(1100,700)
        root=QWidget();layout=QHBoxLayout(root);self.nav=QListWidget();self.nav.addItems(["General","Input Schema","Test Plan","Subtasks","Solution","Validator","Stress Test","Analyze","Export"]);self.nav.setMaximumWidth(180);self.pages=QStackedWidget();layout.addWidget(self.nav);layout.addWidget(self.pages,1);self.setCentralWidget(root);self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self._general();self._schema();[self._info_page(x) for x in ["Test Plan (edit in project JSON)","Subtasks","Solution / compiler","Validator","Stress Test / cross-check","Analyze","Export"]];self.nav.setCurrentRow(0);self._toolbar();self.statusBar().showMessage("Ready")
    def _general(self):
        page=QWidget();form=QFormLayout(page);self.name=QLineEdit(self.project.problem_name);self.inp=QLineEdit(self.project.input_filename);self.out=QLineEdit(self.project.output_filename);self.count=QSpinBox();self.count.setRange(1,100000);self.count.setValue(20);self.seed=QLineEdit(str(self.project.seed));form.addRow("Problem name",self.name);form.addRow("Input filename",self.inp);form.addRow("Output filename",self.out);form.addRow("Test count",self.count);form.addRow("Random seed",self.seed);self.name.textEdited.connect(self._rename);self.pages.addWidget(page)
    def _schema(self):
        page=QWidget();layout=QVBoxLayout(page);layout.addWidget(QLabel("Schema blocks (JSON array; Integer, Array, String, Graph, Tree, Query List…):"));self.schema=QPlainTextEdit("[]");layout.addWidget(self.schema);self.preview=QPlainTextEdit();self.preview.setReadOnly(True);layout.addWidget(QLabel("Preview"));layout.addWidget(self.preview);self.pages.addWidget(page)
    def _info_page(self,text):page=QWidget();layout=QVBoxLayout(page);layout.addWidget(QLabel(text));layout.addStretch();self.pages.addWidget(page)
    def _toolbar(self):
        bar=QToolBar();self.addToolBar(bar)
        for label,slot in [("New Project",self.new),("Open Project",self.open),("Save",self.save),("Save As",self.save_as),("Generate Preview",self.generate_preview),("Generate All",self.generate_all)]:action=QAction(label,self);action.triggered.connect(slot);bar.addAction(action)
        self.progress=QProgressBar();self.progress.setMaximumWidth(180);bar.addWidget(self.progress)
    def _rename(self,text):
        old=self.project.problem_name
        if self.inp.text()==f"{old}.inp":self.inp.setText(f"{text}.inp")
        if self.out.text()==f"{old}.out":self.out.setText(f"{text}.out")
        self.project.problem_name=text
    def _sync(self):self.project.problem_name=self.name.text();self.project.input_filename=self.inp.text();self.project.output_filename=self.out.text();self.project.test_count=self.count.value();self.project.seed=int(self.seed.text());self.project.schema=json.loads(self.schema.toPlainText())
    def _load(self):self.name.setText(self.project.problem_name);self.inp.setText(self.project.input_filename);self.out.setText(self.project.output_filename);self.count.setValue(self.project.test_count);self.seed.setText(str(self.project.seed));self.schema.setPlainText(json.dumps(self.project.schema,indent=2,ensure_ascii=False))
    def new(self):self.project=Project();self.path=None;self._load()
    def open(self):
        raw,_=QFileDialog.getOpenFileName(self,"Open Project","","Project (project.json *.json)")
        if raw:self.path=Path(raw);self.project=Project.load(self.path);self._load()
    def save(self):
        if not self.path:return self.save_as()
        try:self._sync();self.project.save(self.path);self.statusBar().showMessage(f"Saved {self.path}")
        except Exception as exc:QMessageBox.critical(self,"Save Error",str(exc))
    def save_as(self):
        raw,_=QFileDialog.getSaveFileName(self,"Save Project","project.json","JSON (*.json)")
        if raw:self.path=Path(raw);self.save()
    def generate_preview(self):
        try:self._sync();text,_=GenerationEngine().generate(self.project,self.project.seed+1,base=self.path.parent if self.path else Path.cwd());self.preview.setPlainText(text);self.statusBar().showMessage(f"Preview seed: {self.project.seed+1}")
        except Exception as exc:QMessageBox.critical(self,"Generator Error",str(exc))
    def generate_all(self):
        try:self._sync()
        except Exception as exc:QMessageBox.critical(self,"Configuration Error",str(exc));return
        base=self.path.parent if self.path else Path.cwd();destination=base/"generated"/self.project.problem_name
        thread=QThread(self);worker=Worker(lambda progress:GenerationPipeline().generate(self.project,base,destination,progress=progress));worker.moveToThread(thread);thread.started.connect(worker.run);worker.progress.connect(lambda a,b:self.progress.setValue(int(a*100/b)));worker.failed.connect(lambda message:QMessageBox.critical(self,"Generation Error",message));worker.finished.connect(lambda path:self.statusBar().showMessage(f"Generated: {path}"));worker.finished.connect(thread.quit);worker.failed.connect(thread.quit);thread.finished.connect(worker.deleteLater);thread.finished.connect(thread.deleteLater);self._thread=thread;self._worker=worker;thread.start()

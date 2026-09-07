"""Application entry point."""
import logging
from pathlib import Path
import sys
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow

def main()->int:
    Path("logs").mkdir(exist_ok=True);logging.basicConfig(filename="logs/app.log",level=logging.INFO,encoding="utf-8",format="%(asctime)s %(levelname)s %(message)s")
    app=QApplication(sys.argv);window=MainWindow();window.show();return app.exec()

if __name__=="__main__":raise SystemExit(main())

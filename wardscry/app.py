from __future__ import annotations
import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from .db import init_db
from .ui.main_window import MainWindow

def run() -> None:
    init_db()
    app = QApplication(sys.argv)
    app.setApplicationName("WardScry")

    # Clean defaults: no heavy theming. Just make scaling sane.
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    win = MainWindow()
    win.resize(1100, 720)
    win.show()

    raise SystemExit(app.exec())

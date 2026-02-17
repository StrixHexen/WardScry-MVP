from __future__ import annotations
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout

def section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    f = lbl.font()
    f.setPointSize(f.pointSize() + 3)
    f.setBold(True)
    lbl.setFont(f)
    return lbl

def hint(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color: #666;")
    return lbl

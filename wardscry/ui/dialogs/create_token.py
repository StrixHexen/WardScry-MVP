from __future__ import annotations
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QPushButton, QHBoxLayout, QFileDialog, QMessageBox
)

from ...templates import TEMPLATES
from ...core import add_token

class CreateTokenDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create Honeytoken")
        self.setModal(True)

        lay = QVBoxLayout(self)
        form = QFormLayout()

        self.ed_name = QLineEdit()
        self.ed_name.setPlaceholderText("e.g., Finance Firewall Backup")

        self.cmb_template = QComboBox()
        for t in TEMPLATES:
            self.cmb_template.addItem(t.display, t.key)

        self.cmb_sens = QComboBox()
        self.cmb_sens.addItems(["low", "medium", "high"])
        self.cmb_sens.setCurrentText("medium")

        self.ed_dir = QLineEdit()
        self.ed_dir.setPlaceholderText("Choose a directory to plant the token…")
        self.btn_browse = QPushButton("Browse…")

        dir_row = QHBoxLayout()
        dir_row.addWidget(self.ed_dir, 1)
        dir_row.addWidget(self.btn_browse)

        form.addRow("Name:", self.ed_name)
        form.addRow("Template:", self.cmb_template)
        form.addRow("Sensitivity:", self.cmb_sens)
        form.addRow("Directory:", dir_row)

        lay.addLayout(form)

        btns = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_create = QPushButton("Create")
        btns.addStretch(1)
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_create)
        lay.addLayout(btns)

        self.btn_browse.clicked.connect(self.on_browse)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_create.clicked.connect(self.on_create)

    def on_browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select directory")
        if d:
            self.ed_dir.setText(d)

    def on_create(self) -> None:
        name = self.ed_name.text().strip()
        directory = self.ed_dir.text().strip()

        if not name:
            QMessageBox.warning(self, "Missing", "Please enter a token name.")
            return
        if not directory:
            QMessageBox.warning(self, "Missing", "Please choose a directory.")
            return

        template_key = self.cmb_template.currentData()
        sensitivity = self.cmb_sens.currentText()

        try:
            add_token(name, Path(directory), template_key, sensitivity)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create token:\n\n{e}")
            return

        self.accept()

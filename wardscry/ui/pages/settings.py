from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QSpinBox, QCheckBox, QComboBox, QPushButton, QHBoxLayout, QMessageBox
from ..widgets import section_title, hint
from ...config import load_config, save_config

class SettingsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.cfg = load_config()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(12)

        lay.addWidget(section_title("Settings"))
        lay.addWidget(hint("These settings are written to config.yaml. The daemon will read them later."))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)

        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 3600)
        self.spin_interval.setValue(int(self.cfg.get("check_interval_seconds", 10)))

        self.chk_hash = QCheckBox("Count content hash changes as a touch")
        self.chk_hash.setChecked(bool(self.cfg.get("touch_rules", {}).get("content_hash", True)))

        self.chk_meta = QCheckBox("Count metadata changes as a touch")
        self.chk_meta.setChecked(bool(self.cfg.get("touch_rules", {}).get("metadata", True)))

        self.chk_exist = QCheckBox("Count missing/deleted as a touch")
        self.chk_exist.setChecked(bool(self.cfg.get("touch_rules", {}).get("existence", True)))

        self.chk_notify = QCheckBox("Enable notifications")
        self.chk_notify.setChecked(bool(self.cfg.get("notifications", {}).get("enabled", True)))

        self.cmb_sev = QComboBox()
        self.cmb_sev.addItems(["low", "medium", "high"])
        self.cmb_sev.setCurrentText(self.cfg.get("notifications", {}).get("min_severity", "medium"))

        form.addRow("Check interval (seconds):", self.spin_interval)
        form.addRow("", self.chk_hash)
        form.addRow("", self.chk_meta)
        form.addRow("", self.chk_exist)
        form.addRow("", self.chk_notify)
        form.addRow("Notify on severity ≥", self.cmb_sev)

        lay.addLayout(form)

        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("Save")
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_save)
        lay.addLayout(btn_row)

        lay.addStretch(1)

        self.btn_save.clicked.connect(self.on_save)

    def refresh(self) -> None:
        # Reload if external edits happen
        self.cfg = load_config()

    def on_save(self) -> None:
        cfg = load_config()
        cfg["check_interval_seconds"] = int(self.spin_interval.value())
        cfg["touch_rules"]["content_hash"] = bool(self.chk_hash.isChecked())
        cfg["touch_rules"]["metadata"] = bool(self.chk_meta.isChecked())
        cfg["touch_rules"]["existence"] = bool(self.chk_exist.isChecked())
        cfg["notifications"]["enabled"] = bool(self.chk_notify.isChecked())
        cfg["notifications"]["min_severity"] = str(self.cmb_sev.currentText())
        save_config(cfg)
        QMessageBox.information(self, "Saved", "Settings saved.")

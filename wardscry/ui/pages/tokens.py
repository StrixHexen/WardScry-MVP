from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QItemSelectionModel
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableView,
    QMessageBox,
    QAbstractItemView,
)

from ...db import q_all
from ...core import delete_token, reset_token_status
from ..widgets import section_title, hint
from ..dialogs.create_token import CreateTokenDialog
from .tokens_model import TokensModel


class TokensPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(12)

        lay.addWidget(section_title("Tokens"))
        lay.addWidget(
            hint("Plant, list, and manage honeytokens. (Files are never deleted automatically.)")
        )

        # Buttons
        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Create Honeytoken")
        self.btn_remove = QPushButton("Remove")
        self.btn_reset = QPushButton("Reset status")
        self.btn_refresh = QPushButton("Refresh")

        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_remove)
        btn_row.addWidget(self.btn_reset)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_refresh)
        lay.addLayout(btn_row)

        # Table
        self.table = QTableView()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.table, 1)

        # Model
        self.model = TokensModel([])
        self.table.setModel(self.model)
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        # Signals
        self.btn_add.clicked.connect(self.on_add)
        self.btn_remove.clicked.connect(self.on_remove)
        self.btn_reset.clicked.connect(self.on_reset)
        self.btn_refresh.clicked.connect(self.refresh)

        self.refresh()

    def refresh(self) -> None:
        """
        Auto-called by MainWindow's QTimer.
        Model resets clear selection, so we capture selected token id
        and restore it after updating rows (next event loop tick).
        """
        keep_id = self.selected_token_id()

        rows = q_all(
            """
            SELECT id, name, path, template, sensitivity, status, created_at, last_event_at
            FROM tokens
            ORDER BY created_at DESC
            """
        )
        self.model.set_rows(rows)

        if keep_id is not None:
            # Let Qt finish any pending sort/layout work, then restore selection
            QTimer.singleShot(0, lambda: self._restore_selection(keep_id))

    def _restore_selection(self, token_id: int) -> None:
        sm = self.table.selectionModel()
        if sm is None:
            return

        for r, rec in enumerate(getattr(self.model, "rows", [])):
            try:
                if int(rec["id"]) != token_id:
                    continue
            except Exception:
                continue

            idx = self.model.index(r, 0)
            flags = (
                QItemSelectionModel.SelectionFlag.ClearAndSelect
                | QItemSelectionModel.SelectionFlag.Rows
            )
            sm.select(idx, flags)
            self.table.setCurrentIndex(idx)
            self.table.scrollTo(idx)
            return

    def selected_token_id(self) -> int | None:
        sm = self.table.selectionModel()
        if sm is None:
            return None

        idxs = sm.selectedRows()
        if not idxs:
            return None

        row = idxs[0].row()
        try:
            return int(self.model.rows[row]["id"])
        except Exception:
            return None

    def on_add(self) -> None:
        dlg = CreateTokenDialog(self)
        if dlg.exec():
            self.refresh()

    def on_remove(self) -> None:
        token_id = self.selected_token_id()
        if token_id is None:
            QMessageBox.information(self, "Remove", "Select a token first.")
            return

        resp = QMessageBox.question(
            self,
            "Remove token",
            "Remove this honeytoken?\n\nThis removes the WardScry record. "
            "The file is not deleted automatically.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        delete_token(token_id)
        self.refresh()

    def on_reset(self) -> None:
        token_id = self.selected_token_id()
        if token_id is None:
            QMessageBox.information(self, "Reset status", "Select a token first.")
            return

        reset_token_status(token_id)
        self.refresh()


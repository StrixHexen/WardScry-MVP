from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableView, QAbstractItemView
from PySide6.QtCore import Qt

from ...db import q_all
from ..widgets import section_title, hint
from .events_model import EventsModel

class AlertsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(12)

        lay.addWidget(section_title("Alerts & Events"))
        lay.addWidget(hint("This shows events recorded in the database. When the daemon lands, this becomes your tripwire feed."))

        btn_row = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh")
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_refresh)
        lay.addLayout(btn_row)

        self.table = QTableView()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.table, 1)

        self.model = EventsModel([])
        self.table.setModel(self.model)
        self.table.sortByColumn(0, Qt.DescendingOrder)

        self.btn_refresh.clicked.connect(self.refresh)

        self.refresh()

    def refresh(self) -> None:
        rows = q_all("""
            SELECT e.ts, t.name AS token, e.event_type, e.severity, e.details
            FROM events e
            JOIN tokens t ON t.id = e.token_id
            ORDER BY e.ts DESC
            LIMIT 500
        """)
        self.model.set_rows(rows)

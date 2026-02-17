from __future__ import annotations
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PySide6.QtCore import Qt

from ...db import q_one
from ..widgets import section_title, hint

class StatCard(QFrame):
    def __init__(self, title: str, value: str) -> None:
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumWidth(220)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(4)

        t = QLabel(title)
        t.setStyleSheet("color: #666;")
        v = QLabel(value)
        f = v.font()
        f.setPointSize(f.pointSize() + 10)
        f.setBold(True)
        v.setFont(f)

        lay.addWidget(t)
        lay.addWidget(v)
        lay.addStretch(1)

    def set_value(self, value: str) -> None:
        # second widget is value label
        self.findChildren(QLabel)[1].setText(value)

class DashboardPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(12)

        self.layout.addWidget(section_title("Dashboard"))
        self.layout.addWidget(hint("A quick pulse-check: tokens planted, alerts seen, and last activity."))

        row = QHBoxLayout()
        row.setSpacing(12)

        self.card_tokens = StatCard("Tokens monitored", "0")
        self.card_alerts = StatCard("Alerts (24h)", "0")
        self.card_events = StatCard("Events (24h)", "0")

        row.addWidget(self.card_tokens)
        row.addWidget(self.card_alerts)
        row.addWidget(self.card_events)
        row.addStretch(1)

        self.layout.addLayout(row)

        self.status = QLabel("Daemon: not connected (MVP)")
        self.status.setStyleSheet("color: #666;")
        self.layout.addWidget(self.status)

        self.layout.addStretch(1)

        self.refresh()

    def refresh(self) -> None:
        tokens = q_one("SELECT COUNT(*) AS c FROM tokens")
        events_24 = q_one("SELECT COUNT(*) AS c FROM events WHERE ts >= datetime('now', '-1 day')")
        alerts_24 = q_one("""
            SELECT COUNT(*) AS c FROM events
            WHERE ts >= datetime('now', '-1 day')
              AND severity IN ('high','medium')
        """)

        self.card_tokens.set_value(str(tokens["c"] if tokens else 0))
        self.card_events.set_value(str(events_24["c"] if events_24 else 0))
        self.card_alerts.set_value(str(alerts_24["c"] if alerts_24 else 0))

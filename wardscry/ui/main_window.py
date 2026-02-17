from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QStackedWidget, QLabel
)
from PySide6.QtCore import Qt, QTimer

from .pages.dashboard import DashboardPage
from .pages.tokens import TokensPage
from .pages.alerts import AlertsPage
from .pages.settings import SettingsPage

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("WardScry")

        root = QWidget()
        self.setCentralWidget(root)

        outer = QHBoxLayout(root)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        # Sidebar
        self.nav = QListWidget()
        self.nav.setFixedWidth(220)
        self.nav.setSpacing(2)
        self.nav.setAlternatingRowColors(False)

        for text in ("Dashboard", "Tokens", "Alerts", "Settings"):
            item = QListWidgetItem(text)
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.nav.addItem(item)

        # Pages
        self.stack = QStackedWidget()
        self.pages = {
            0: DashboardPage(),
            1: TokensPage(),
            2: AlertsPage(),
            3: SettingsPage(),
        }
        for i in range(4):
            self.stack.addWidget(self.pages[i])

        outer.addWidget(self.nav)
        outer.addWidget(self.stack, 1)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        # Light auto-refresh so GUI updates if a daemon starts writing events later.
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(2000)
        self.refresh_timer.timeout.connect(self.refresh_visible_page)
        self.refresh_timer.start()

    def refresh_visible_page(self) -> None:
        w = self.stack.currentWidget()
        if hasattr(w, "refresh"):
            try:
                w.refresh()
            except Exception:
                # Keep GUI resilient even if DB/config has oddities.
                pass

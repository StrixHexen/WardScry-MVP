from __future__ import annotations
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex
import sqlite3

COLUMNS = [
    ("name", "Name"),
    ("path", "Path"),
    ("template", "Template"),
    ("sensitivity", "Sensitivity"),
    ("status", "Status"),
    ("created_at", "Created"),
    ("last_event_at", "Last event"),
]

class TokensModel(QAbstractTableModel):
    def __init__(self, rows: list[sqlite3.Row]) -> None:
        super().__init__()
        self.rows: list[sqlite3.Row] = rows

    def set_rows(self, rows: list[sqlite3.Row]) -> None:
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        key, _ = COLUMNS[index.column()]
        if role == Qt.DisplayRole:
            v = row[key]
            return "" if v is None else str(v)
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return COLUMNS[section][1]
        return str(section + 1)

    def sort(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder) -> None:
        key, _ = COLUMNS[column]
        self.layoutAboutToBeChanged.emit()
        self.rows.sort(key=lambda r: (r[key] is None, r[key]))
        if order == Qt.DescendingOrder:
            self.rows.reverse()
        self.layoutChanged.emit()

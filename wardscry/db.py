from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Optional
from .paths import db_path, user_data_dir

SCHEMA = '''
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    token_type TEXT NOT NULL,         -- file | dir
    template TEXT NOT NULL,
    sensitivity TEXT NOT NULL,        -- low | medium | high
    status TEXT NOT NULL DEFAULT 'ok',-- ok | missing | triggered
    created_at TEXT NOT NULL,
    last_checked_at TEXT,
    last_event_at TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_id INTEGER NOT NULL,
    ts TEXT NOT NULL,
    event_type TEXT NOT NULL,         -- created | modified | deleted | opened | renamed | note
    severity TEXT NOT NULL,           -- low | medium | high
    details TEXT,
    FOREIGN KEY(token_id) REFERENCES tokens(id)
);

CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts DESC);
CREATE INDEX IF NOT EXISTS idx_events_token ON events(token_id, ts DESC);
'''

def connect() -> sqlite3.Connection:
    user_data_dir().mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path())
    con.row_factory = sqlite3.Row
    return con

def init_db() -> None:
    con = connect()
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()

def q_all(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    con = connect()
    try:
        cur = con.execute(sql, params)
        rows = cur.fetchall()
        return rows
    finally:
        con.close()

def q_one(sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
    con = connect()
    try:
        cur = con.execute(sql, params)
        row = cur.fetchone()
        return row
    finally:
        con.close()

def exec_sql(sql: str, params: tuple = ()) -> int:
    con = connect()
    try:
        cur = con.execute(sql, params)
        con.commit()
        return cur.lastrowid
    finally:
        con.close()

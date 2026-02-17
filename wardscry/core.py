from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import os

from . import db
from .templates import template_by_key

def now_iso() -> str:
    # UTC is nice for logs; display layer can localize later.
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def safe_plant_file(directory: Path, filename: str, content: bytes) -> Path:
    directory = directory.expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)

    base = directory / filename
    if not base.exists():
        base.write_bytes(content)
        return base

    # never overwrite: add suffix
    stem = base.stem
    suffix = base.suffix
    for i in range(1, 1000):
        candidate = directory / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            candidate.write_bytes(content)
            return candidate

    raise RuntimeError("Could not find a free filename after many attempts.")

def add_token(
    name: str,
    directory: Path,
    template_key: str,
    sensitivity: str,
) -> int:
    t = template_by_key(template_key)
    planted = safe_plant_file(directory, t.default_filename, t.make_bytes())

    token_id = db.exec_sql(
        """
        INSERT INTO tokens (name, path, token_type, template, sensitivity, status, created_at)
        VALUES (?, ?, 'file', ?, ?, 'ok', ?)
        """,
        (name, str(planted), template_key, sensitivity, now_iso()),
    )

    db.exec_sql(
        """
        INSERT INTO events (token_id, ts, event_type, severity, details)
        VALUES (?, ?, 'created', ?, ?)
        """,
        (token_id, now_iso(), "low", f"Planted decoy file at {planted}"),
    )
    return token_id

def delete_token(token_id: int) -> None:
    # Note: we do NOT delete the file automatically (safer). We can add a checkbox later.
    db.exec_sql("DELETE FROM events WHERE token_id = ?", (token_id,))
    db.exec_sql("DELETE FROM tokens WHERE id = ?", (token_id,))

def reset_token_status(token_id: int) -> None:
    # Don't delete history; just mark token as OK again.
    db.exec_sql("UPDATE tokens SET status='ok' WHERE id = ?", (token_id,))
    db.exec_sql(
        "INSERT INTO events (token_id, ts, event_type, severity, details) VALUES (?, ?, 'note', 'low', ?)",
        (token_id, now_iso(), "Status reset to ok"),
    )

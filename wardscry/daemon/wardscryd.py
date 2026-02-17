from __future__ import annotations

import json
import os
import socket
import time
import threading
import uuid
from pathlib import Path
from typing import Dict, Tuple, Set, Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from wardscry.db import q_all, exec_sql

# --- Optional dependency for read/open detection (Linux) ---
try:
    from inotify_simple import INotify, flags as IFlags
    HAVE_INOTIFY = True
except Exception:
    HAVE_INOTIFY = False


# Sensitivity -> severity label (simple MVP)
SEV = {"low": "low", "medium": "medium", "high": "high"}

# Severity label -> numeric (handy for SIEM rules)
SEV_NUM = {"low": 3, "medium": 7, "high": 12}

# Noise control knobs
MOD_QUIET_SECONDS = 1.25     # flush a burst if no new mods for this long
MOD_MAX_WINDOW_SECONDS = 3.0 # cap burst window so it flushes even if constant edits

# Hot-reload: how often the daemon re-reads tokens from the DB
TOKEN_REFRESH_SECONDS = 2.0

# --- SIEM emission (JSON Lines / NDJSON) ---
# Override with env var WARDSCRY_SIEM_JSONL, e.g.:
#   export WARDSCRY_SIEM_JSONL=/var/log/wardscry/wardscry.jsonl
DEFAULT_SIEM_JSONL = "~/.local/share/wardscry/wardscry.jsonl"


def now_iso_utc() -> str:
    import datetime
    from datetime import timezone
    return datetime.datetime.now(timezone.utc).isoformat(timespec="seconds")


def _siem_path() -> Path:
    raw = os.environ.get("WARDSCRY_SIEM_JSONL", DEFAULT_SIEM_JSONL)
    return Path(raw).expanduser()


def emit_jsonl(event: dict) -> None:
    """
    Append a single-line JSON event for SIEM ingestion.
    - One JSON object per line (JSONL/NDJSON).
    - Never crashes the daemon if logging fails.
    """
    try:
        path = _siem_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        line = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
        new_file = not path.exists()

        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

        # Try to make it readable for collectors (Wazuh agent often runs as root anyway).
        if new_file:
            try:
                path.chmod(0o644)
            except Exception:
                pass
    except Exception as e:
        print(f"[WardScry] SIEM emit failed: {e}")


def load_tokens() -> Dict[str, Tuple[int, str]]:
    """
    Returns: { resolved_token_path_str: (token_id, sensitivity) }
    """
    rows = q_all("SELECT id, path, sensitivity FROM tokens")
    out: Dict[str, Tuple[int, str]] = {}
    for r in rows:
        out[str(Path(r["path"]).expanduser().resolve())] = (int(r["id"]), str(r["sensitivity"]))
    return out


def write_event(
    token_id: int,
    event_type: str,
    severity: str,
    details: str,
    *,
    token_path: Optional[str] = None,
    sensitivity: Optional[str] = None,
) -> None:
    ts = now_iso_utc()
    exec_sql(
        "INSERT INTO events (token_id, ts, event_type, severity, details) VALUES (?, ?, ?, ?, ?)",
        (token_id, ts, event_type, severity, details),
    )

    # Status transitions (defender logic)
    if event_type == "deleted":
        exec_sql("UPDATE tokens SET status='missing', last_event_at=? WHERE id=?", (ts, token_id))
    elif event_type in ("modified", "renamed", "opened"):
        exec_sql("UPDATE tokens SET status='triggered', last_event_at=? WHERE id=?", (ts, token_id))
    else:
        exec_sql("UPDATE tokens SET last_event_at=? WHERE id=?", (ts, token_id))

    # --- SIEM-friendly JSONL event ---
    sev_label = str(severity)
    sev_num = SEV_NUM.get(sev_label, 3)

    event = {
        "@timestamp": ts,
        "observer": {"product": "WardScry", "type": "honeypot"},
        "host": {"hostname": socket.gethostname()},
        "event": {
            "kind": "alert",
            "action": event_type,
            "severity": sev_num,
        },
        "log": {"level": sev_label},
        "file": {"path": token_path} if token_path else {},
        "wardscry": {
            "event_id": str(uuid.uuid4()),
            "token_id": token_id,
            "sensitivity": sensitivity,
            "details": details,
        },
        "message": f"WardScry token {event_type}: {details}",
    }

    # Strip empty dict keys to keep events tidy
    if not event.get("file"):
        event.pop("file", None)

    emit_jsonl(event)


class OpenAccessWatcher(threading.Thread):
    """
    Watches token directories for OPEN/CLOSE_NOWRITE using inotify.
    We log "opened" on CLOSE_NOWRITE (opened + closed without writing),
    which is a good proxy for "read attempt".

    Notes:
    - Linux-only.
    - Does not identify WHO opened the file (that requires auditd/fanotify/etc.).
    """
    def __init__(self, handler: "TokenEventHandler", watched_dirs: Set[str]) -> None:
        super().__init__(daemon=True)
        self.handler = handler
        self._stop = threading.Event()
        self._lock = threading.Lock()

        self.inotify = INotify()
        self.wd_to_dir: Dict[int, str] = {}
        self.dir_to_wd: Dict[str, int] = {}

        for d in sorted(watched_dirs):
            self.add_dir(d)

    def add_dir(self, d: str) -> None:
        d = str(Path(d).expanduser().resolve())
        with self._lock:
            if d in self.dir_to_wd:
                return
            try:
                wd = self.inotify.add_watch(
                    d,
                    # OPEN can be noisy; CLOSE_NOWRITE is the "read attempt" signal.
                    IFlags.CLOSE_NOWRITE | IFlags.OPEN,
                )
            except FileNotFoundError:
                return
            except PermissionError:
                print(f"[WardScry] OpenWatcher: no permission to watch {d}")
                return

            self.dir_to_wd[d] = wd
            self.wd_to_dir[wd] = d
            print(f"[WardScry] OpenWatcher now watching: {d}")

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                events = self.inotify.read(timeout=1000)  # ms
            except TypeError:
                # Older versions may not support timeout; fall back to short sleep loop
                time.sleep(0.5)
                continue
            except Exception:
                time.sleep(0.5)
                continue

            for ev in events:
                d = self.wd_to_dir.get(ev.wd)
                if not d or not ev.name:
                    continue

                full_path = str(Path(d) / ev.name)

                hit = self.handler._lookup_token(full_path)
                if not hit:
                    continue

                token_id, sens, resolved = hit

                ev_flags = IFlags.from_mask(ev.mask)

                # "Opened(read)" = close without write
                if IFlags.CLOSE_NOWRITE in ev_flags:
                    # Debounce to avoid spam if apps open repeatedly
                    if self.handler._debounced(token_id, "opened", window=1.0):
                        continue
                    self.handler._log_immediate(
                        token_id,
                        sens,
                        "opened",
                        f"opened(read) -> {resolved}",
                        resolved_path=resolved,
                    )
                    print(f"[WardScry] opened(read): {resolved}")


class TokenEventHandler(FileSystemEventHandler):
    def __init__(
        self,
        token_map: Dict[str, Tuple[int, str]],
        observer: Observer,
        watched_dirs: Set[str],
        open_watcher: Optional[OpenAccessWatcher] = None,
    ) -> None:
        super().__init__()
        self.token_map = token_map
        self.observer = observer
        self.watched_dirs = watched_dirs
        self.open_watcher = open_watcher

        # Lock for modified-burst buffering
        self._lock = threading.Lock()

        # Lock for token_map reads/writes
        self._map_lock = threading.Lock()

        # Lock for watched_dirs (schedule changes can happen from observer thread + main thread)
        self._watch_lock = threading.Lock()

        # Debounce for non-burst events (rename/delete/open)
        self._last_seen: Dict[Tuple[int, str], float] = {}  # (token_id, event_type) -> time

        # Burst buffer for modified events:
        # token_id -> dict with keys: path, sens, first, last, count
        self._mod_bursts: Dict[int, Dict[str, object]] = {}

    def _debounced(self, token_id: int, event_type: str, window: float = 0.75) -> bool:
        now = time.time()
        key = (token_id, event_type)
        last = self._last_seen.get(key, 0.0)
        if now - last < window:
            return True
        self._last_seen[key] = now
        return False

    def _ensure_watch_dir_for(self, path: str) -> None:
        d = str(Path(path).expanduser().resolve().parent)
        with self._watch_lock:
            if d in self.watched_dirs:
                return
            self.observer.schedule(self, d, recursive=False)
            self.watched_dirs.add(d)

        # Also add to open watcher (read/open detection)
        if self.open_watcher is not None:
            self.open_watcher.add_dir(d)

        print(f"[WardScry] Now watching: {d}")

    def refresh_tokens_from_db(self) -> None:
        """
        Reload token definitions from the DB and hot-apply changes.

        - Updates self.token_map atomically
        - Adds new directory watches for any newly-added token paths
        - Does NOT unschedule watches (fine for MVP)
        """
        new_map = load_tokens()

        with self._map_lock:
            old_map = self.token_map
            if new_map == old_map:
                return

            added = [p for p in new_map.keys() if p not in old_map]
            removed = [p for p in old_map.keys() if p not in new_map]
            changed = [p for p in new_map.keys() if p in old_map and old_map[p] != new_map[p]]

            self.token_map = new_map

        # Ensure watches exist for any newly-added token paths
        for p in added:
            self._ensure_watch_dir_for(p)

        print(f"[WardScry] Token refresh: +{len(added)} ~{len(changed)} -{len(removed)}")

    def _lookup_token(self, path: str) -> Optional[Tuple[int, str, str]]:
        """
        Returns (token_id, sens, resolved_path) if path is a tracked token.
        """
        p = str(Path(path).expanduser().resolve())
        with self._map_lock:
            hit = self.token_map.get(p)
        if not hit:
            return None
        token_id, sens = hit
        return token_id, sens, p

    def _log_immediate(
        self,
        token_id: int,
        sens: str,
        event_type: str,
        details: str,
        *,
        resolved_path: Optional[str] = None,
    ) -> None:
        sev = SEV.get(sens, "low")
        write_event(
            token_id,
            event_type,
            sev,
            details,
            token_path=resolved_path,
            sensitivity=sens,
        )

    def _buffer_modified(self, token_id: int, sens: str, resolved_path: str) -> None:
        now = time.time()
        with self._lock:
            b = self._mod_bursts.get(token_id)
            if b is None:
                self._mod_bursts[token_id] = {
                    "path": resolved_path,
                    "sens": sens,
                    "first": now,
                    "last": now,
                    "count": 1,
                }
            else:
                b["path"] = resolved_path
                b["sens"] = sens
                b["last"] = now
                b["count"] = int(b["count"]) + 1

    def flush_modified_bursts(self) -> None:
        """
        Flush buffered modified events into a single summarized DB event.
        Called from the main loop periodically.
        """
        now = time.time()
        to_flush: list[tuple[int, Dict[str, object]]] = []

        with self._lock:
            for token_id, b in list(self._mod_bursts.items()):
                first = float(b["first"])
                last = float(b["last"])
                count = int(b["count"])

                quiet = (now - last) >= MOD_QUIET_SECONDS
                too_long = (now - first) >= MOD_MAX_WINDOW_SECONDS

                if quiet or too_long:
                    to_flush.append((token_id, b))
                    del self._mod_bursts[token_id]

        for token_id, b in to_flush:
            path = str(b["path"])
            sens = str(b["sens"])
            count = int(b["count"])
            dur = max(0.0, float(b["last"]) - float(b["first"]))

            if count <= 1:
                details = f"modified -> {path}"
            else:
                details = f"modified -> {path} (burst x{count} over {dur:.3f}s)"

            self._log_immediate(token_id, sens, "modified", details, resolved_path=path)
            print(f"[WardScry] modified: {path}" + (f" (burst x{count})" if count > 1 else ""))

    # ---- Watchdog callbacks ----

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        hit = self._lookup_token(event.src_path)
        if not hit:
            return
        token_id, sens, resolved = hit
        # Re-creation is interesting; treat as a modified burst.
        self._buffer_modified(token_id, sens, resolved)

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        hit = self._lookup_token(event.src_path)
        if not hit:
            return
        token_id, sens, resolved = hit
        self._buffer_modified(token_id, sens, resolved)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        hit = self._lookup_token(event.src_path)
        if not hit:
            return
        token_id, sens, resolved = hit
        if self._debounced(token_id, "deleted"):
            return
        self._log_immediate(token_id, sens, "deleted", f"deleted -> {resolved}", resolved_path=resolved)
        print(f"[WardScry] deleted: {resolved}")

    def on_moved(self, event) -> None:
        if event.is_directory:
            return

        src = str(Path(event.src_path).expanduser().resolve())
        dest = str(Path(event.dest_path).expanduser().resolve())

        # Token itself renamed/moved
        with self._map_lock:
            src_hit = self.token_map.get(src)

        if src_hit:
            token_id, sens = src_hit
            if self._debounced(token_id, "renamed"):
                return

            # Emit rename event (use dest as the primary file.path)
            self._log_immediate(
                token_id,
                sens,
                "renamed",
                f"renamed -> {src} (to {dest})",
                resolved_path=dest,
            )

            exec_sql("UPDATE tokens SET path=? WHERE id=?", (dest, token_id))

            with self._map_lock:
                # Re-check in case a refresh swapped maps mid-flight
                if src in self.token_map:
                    del self.token_map[src]
                self.token_map[dest] = (token_id, sens)

            self._ensure_watch_dir_for(dest)

            print(f"[WardScry] renamed: {src} -> {dest}")
            return

        # Atomic-save style replace: dest becomes the token path
        with self._map_lock:
            dest_hit = self.token_map.get(dest)

        if dest_hit:
            token_id, sens = dest_hit
            self._buffer_modified(token_id, sens, dest)
            return


def main() -> None:
    token_map = load_tokens()
    watched_dirs: Set[str] = {str(Path(p).parent) for p in token_map.keys()}

    if watched_dirs:
        print("[WardScry] Watching directories:")
        for d in sorted(watched_dirs):
            print("  -", d)
    else:
        print("[WardScry] No tokens found in DB yet. Will auto-refresh and start watching when tokens appear.")

    print(f"[WardScry] SIEM JSONL output: {_siem_path()}")

    observer = Observer()

    open_watcher: Optional[OpenAccessWatcher] = None
    if HAVE_INOTIFY:
        # Create handler first with open_watcher placeholder; we’ll attach after.
        handler = TokenEventHandler(token_map, observer, watched_dirs, open_watcher=None)
        open_watcher = OpenAccessWatcher(handler, watched_dirs)
        handler.open_watcher = open_watcher
        open_watcher.start()
        print("[WardScry] Open/read detection enabled (inotify).")
    else:
        handler = TokenEventHandler(token_map, observer, watched_dirs, open_watcher=None)
        print("[WardScry] Open/read detection NOT enabled (missing inotify-simple).")

    for d in sorted(watched_dirs):
        observer.schedule(handler, d, recursive=False)

    observer.start()
    print("[WardScry] Daemon running. Ctrl+C to stop.")

    last_refresh = 0.0
    try:
        while True:
            time.sleep(1.0)
            handler.flush_modified_bursts()

            now = time.time()
            if (now - last_refresh) >= TOKEN_REFRESH_SECONDS:
                handler.refresh_tokens_from_db()
                last_refresh = now

    except KeyboardInterrupt:
        print("\n[WardScry] Stopping…")
    finally:
        if open_watcher is not None:
            open_watcher.stop()
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()


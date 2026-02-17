# WardScry (GUI MVP)

A clean, Linux-friendly desktop GUI for creating and managing WardScry honeytokens.

## What this MVP includes
- Sidebar navigation: Dashboard, Tokens, Alerts, Settings
- SQLite storage (tokens + events)
- YAML config (settings)
- "Create Honeytoken" dialog:
  - choose directory
  - choose template + sensitivity
  - plants a decoy file (non-destructive: never overwrites; adds suffix if needed)
  - records token in SQLite

## Not included (yet)
- The daemon watcher (inotify/audit) that detects touches and writes events.
  - The GUI is already structured to read events from SQLite when the daemon exists.

## Quick start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Data locations
- DB: `~/.local/share/wardscry/wardscry.db`
- Config: `~/.config/wardscry/config.yaml`

## Notes
- This is intentionally minimal and clean. Polish comes after we can *play with it*.

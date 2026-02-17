# WardScry (MVP)

WardScry is a Linux-first honeytoken system: a desktop GUI to plant decoy files and a daemon that watches for suspicious interaction, records events to SQLite, and emits SIEM-friendly JSONL.

## What it does
- GUI: create/plant/manage honeytokens (decoy files) and view status/events
- Daemon: watches token paths for filesystem activity
- Stores tokens + events in SQLite
- Emits JSON Lines (NDJSON) events for SIEM ingestion (ECS-ish fields)
- Hot-reloads token definitions from the DB (no daemon restart needed)
- Basic noise control for “modified” bursts

## How it works (high-level)
1. GUI writes token definitions into SQLite (name, path, sensitivity, template, status)
2. Daemon reads tokens from SQLite and watches their directories
3. On activity, daemon:
   - writes an event to SQLite
   - updates token status (ok/triggered/missing)
   - appends a JSONL event for SIEM ingestion

## Install
```bash
sudo apt update
sudo apt install -y python3 python3-venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt


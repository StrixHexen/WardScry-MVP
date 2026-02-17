from __future__ import annotations
from pathlib import Path

APP_NAME = "WardScry"

def user_data_dir() -> Path:
    return Path.home() / ".local" / "share" / APP_NAME

def user_config_dir() -> Path:
    return Path.home() / ".config" / APP_NAME

def db_path() -> Path:
    return user_data_dir() / "wardscry.db"

def config_path() -> Path:
    return user_config_dir() / "config.yaml"

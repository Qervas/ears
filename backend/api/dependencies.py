"""Shared dependencies for API endpoints."""

import json
from pathlib import Path

from core import Database
from core.config import (
    BASE_DIR,
    RECORDINGS_DIR,
    TTS_CACHE_DIR,
    BACKUPS_DIR,
    SETTINGS_PATH,
)

# Re-export paths for backward compatibility
BACKUP_DIR = BACKUPS_DIR
TTS_CACHE = TTS_CACHE_DIR
SETTINGS_FILE = Path(SETTINGS_PATH)

# Shared database instance
db = Database()


def load_settings() -> dict:
    """Load settings from JSON file."""
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return {
        "ai_provider": "lm-studio",
        "lm_studio_url": "http://localhost:1234/v1",
        "copilot_api_url": "http://localhost:4141",
        "copilot_model": "gpt-4o-mini",
        "openai_api_key": ""
    }


def save_settings(settings: dict):
    """Save settings to JSON file."""
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

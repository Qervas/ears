"""Shared dependencies for API endpoints."""

import json
from pathlib import Path

from database import Database

# Base directory (backend folder)
BASE_DIR = Path(__file__).parent.parent.resolve()
RECORDINGS_DIR = BASE_DIR / "recordings"
SETTINGS_FILE = BASE_DIR / "settings.json"
BACKUP_DIR = BASE_DIR / "backups"
TTS_CACHE = BASE_DIR / "tts_cache"

# Ensure directories exist
RECORDINGS_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)
TTS_CACHE.mkdir(exist_ok=True)

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

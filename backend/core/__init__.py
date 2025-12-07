"""
Core module - shared code used across the application.

This module contains:
- config: Application configuration
- database: Database operations
- languages: Language definitions and utilities

Usage:
    from core import Database
    from core import LANGUAGES, get_tts_voice
    from core.config import DATABASE_PATH
"""

# Import languages (loaded from config/languages.yaml)
from .languages import (
    LANGUAGES,
    DEFAULT_LANGUAGE,
    get_language,
    get_tts_voice,
    get_whisper_code,
    is_valid_language,
    reload_languages,
)

# Import database (has aiosqlite dependency but needed by most code)
from .database import Database

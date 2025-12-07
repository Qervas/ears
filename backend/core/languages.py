"""
Language registry for multi-language support.

Languages are loaded from config/languages.yaml.
To add a new language, edit that file - no code changes needed.
"""

import yaml
from pathlib import Path

# Path to config file
CONFIG_DIR = Path(__file__).parent.parent / "config"
LANGUAGES_FILE = CONFIG_DIR / "languages.yaml"


def _load_languages() -> tuple[dict, str]:
    """Load languages from YAML config file."""
    if not LANGUAGES_FILE.exists():
        # Fallback defaults if config file missing
        return {
            "de": {
                "name": "German",
                "native_name": "Deutsch",
                "flag": "🇩🇪",
                "tts_voice": "de-DE-KatjaNeural",
                "whisper_code": "de",
            }
        }, "de"

    with open(LANGUAGES_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config.get("languages", {}), config.get("default_language", "de")


# Load on module import
LANGUAGES, DEFAULT_LANGUAGE = _load_languages()


def reload_languages():
    """Reload languages from config file (useful after editing)."""
    global LANGUAGES, DEFAULT_LANGUAGE
    LANGUAGES, DEFAULT_LANGUAGE = _load_languages()


def get_language(code: str) -> dict | None:
    """Get language config by code."""
    return LANGUAGES.get(code)


def get_tts_voice(code: str) -> str:
    """Get TTS voice for a language."""
    lang = LANGUAGES.get(code)
    return lang["tts_voice"] if lang else LANGUAGES[DEFAULT_LANGUAGE]["tts_voice"]


def get_whisper_code(code: str) -> str:
    """Get Whisper language code."""
    lang = LANGUAGES.get(code)
    return lang["whisper_code"] if lang else DEFAULT_LANGUAGE


def is_valid_language(code: str) -> bool:
    """Check if language code is valid."""
    return code in LANGUAGES

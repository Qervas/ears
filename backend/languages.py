"""
Backward-compatible shim for languages module.

New code should import from core.languages instead.
"""

from core.languages import (
    LANGUAGES,
    DEFAULT_LANGUAGE,
    get_language,
    get_tts_voice,
    get_whisper_code,
    is_valid_language,
)

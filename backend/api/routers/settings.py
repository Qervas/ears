"""Settings endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..dependencies import load_settings, save_settings, db
from ..models.settings import SettingsUpdate
from ..services.ai_service import AIService
from core import LANGUAGES, is_valid_language, reload_languages
from core.languages import LANGUAGES_FILE
import yaml

router = APIRouter(tags=["Settings"])


@router.get("/settings")
async def get_settings():
    """Get current application settings."""
    settings = load_settings()
    # Mask API key for security
    if settings.get("openai_api_key"):
        settings["openai_api_key"] = "***" if settings["openai_api_key"] else ""
    return settings


@router.post("/settings")
async def update_settings(settings: SettingsUpdate):
    """Update application settings."""
    current = load_settings()

    current["ai_provider"] = settings.ai_provider

    if settings.lm_studio_url:
        current["lm_studio_url"] = settings.lm_studio_url

    if settings.copilot_api_url:
        current["copilot_api_url"] = settings.copilot_api_url

    if settings.copilot_model:
        current["copilot_model"] = settings.copilot_model

    # Only update API key if a real value is provided (not masked)
    if settings.openai_api_key and settings.openai_api_key != "***":
        current["openai_api_key"] = settings.openai_api_key

    save_settings(current)
    return {"status": "settings_saved"}


@router.get("/test-ai-connection")
async def test_ai_connection():
    """Test connection to the configured AI provider."""
    try:
        client = AIService.get_client()
        settings = load_settings()
        provider = settings.get("ai_provider", "lm-studio")
        model = AIService.get_model()

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say 'OK' if you can read this."}],
            max_tokens=10,
            temperature=0.1
        )

        return {
            "success": True,
            "provider": provider,
            "model": response.model if hasattr(response, 'model') else model,
            "response": response.choices[0].message.content
        }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# ============== Language Settings ==============

@router.get("/languages")
async def get_languages():
    """Get all available languages."""
    active = await db.get_active_language()
    return {
        "languages": LANGUAGES,
        "active": active
    }


@router.get("/languages/active")
async def get_active_language():
    """Get the currently active language."""
    active = await db.get_active_language()
    lang_info = LANGUAGES.get(active, {})
    return {
        "code": active,
        "name": lang_info.get("name", active),
        "native_name": lang_info.get("native_name", active),
        "flag": lang_info.get("flag", ""),
        "tts_voice": lang_info.get("tts_voice", "")
    }


@router.put("/languages/active/{language_code}")
async def set_active_language(language_code: str):
    """Set the active language."""
    if not is_valid_language(language_code):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid language code: {language_code}. Valid codes: {list(LANGUAGES.keys())}"
        )

    await db.set_active_language(language_code)
    lang_info = LANGUAGES[language_code]

    return {
        "status": "language_changed",
        "code": language_code,
        "name": lang_info["name"],
        "flag": lang_info["flag"]
    }


# ============== Language Management ==============

class LanguageCreate(BaseModel):
    """Model for creating/updating a language."""
    code: str
    name: str
    native_name: str
    flag: str
    tts_voice: str
    whisper_code: Optional[str] = None


def _save_languages_config(languages: dict, default_language: str):
    """Save languages to YAML config file."""
    config = {
        "default_language": default_language,
        "languages": languages
    }
    with open(LANGUAGES_FILE, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    # Reload in memory
    reload_languages()


@router.post("/languages")
async def add_language(lang: LanguageCreate):
    """Add a new language."""
    if lang.code in LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Language '{lang.code}' already exists. Use PUT to update."
        )

    # Get current config
    with open(LANGUAGES_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Add new language
    config["languages"][lang.code] = {
        "name": lang.name,
        "native_name": lang.native_name,
        "flag": lang.flag,
        "tts_voice": lang.tts_voice,
        "whisper_code": lang.whisper_code or lang.code,
    }

    # Save
    _save_languages_config(config["languages"], config["default_language"])

    return {
        "status": "language_added",
        "code": lang.code,
        "name": lang.name
    }


@router.put("/languages/{language_code}")
async def update_language(language_code: str, lang: LanguageCreate):
    """Update an existing language."""
    if language_code not in LANGUAGES:
        raise HTTPException(
            status_code=404,
            detail=f"Language '{language_code}' not found."
        )

    # Get current config
    with open(LANGUAGES_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # If code is changing, we need to handle that
    if lang.code != language_code:
        # Remove old key, add new
        del config["languages"][language_code]
        # Update default if it was the old code
        if config["default_language"] == language_code:
            config["default_language"] = lang.code

    # Update language
    config["languages"][lang.code] = {
        "name": lang.name,
        "native_name": lang.native_name,
        "flag": lang.flag,
        "tts_voice": lang.tts_voice,
        "whisper_code": lang.whisper_code or lang.code,
    }

    # Save
    _save_languages_config(config["languages"], config["default_language"])

    return {
        "status": "language_updated",
        "code": lang.code,
        "name": lang.name
    }


@router.delete("/languages/{language_code}")
async def delete_language(language_code: str):
    """Delete a language."""
    if language_code not in LANGUAGES:
        raise HTTPException(
            status_code=404,
            detail=f"Language '{language_code}' not found."
        )

    # Get current config
    with open(LANGUAGES_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Don't allow deleting the default language
    if config["default_language"] == language_code:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the default language. Change default first."
        )

    # Don't allow deleting if it's the only language
    if len(config["languages"]) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the last language."
        )

    # Delete
    del config["languages"][language_code]

    # Save
    _save_languages_config(config["languages"], config["default_language"])

    return {
        "status": "language_deleted",
        "code": language_code
    }


@router.put("/languages/default/{language_code}")
async def set_default_language(language_code: str):
    """Set the default language (for new users)."""
    if language_code not in LANGUAGES:
        raise HTTPException(
            status_code=404,
            detail=f"Language '{language_code}' not found."
        )

    # Get current config
    with open(LANGUAGES_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    config["default_language"] = language_code

    # Save
    _save_languages_config(config["languages"], config["default_language"])

    return {
        "status": "default_language_changed",
        "code": language_code
    }

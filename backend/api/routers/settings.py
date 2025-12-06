"""Settings endpoints."""

from fastapi import APIRouter

from ..dependencies import load_settings, save_settings
from ..models.settings import SettingsUpdate
from ..services.ai_service import AIService

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

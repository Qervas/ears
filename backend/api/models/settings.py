"""Settings-related Pydantic models."""

from pydantic import BaseModel


class SettingsUpdate(BaseModel):
    """Update application settings."""
    ai_provider: str
    lm_studio_url: str = ""
    copilot_api_url: str = ""
    copilot_model: str = ""
    openai_api_key: str = ""

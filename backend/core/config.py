"""
Application configuration.

All configurable settings for the Ears application.
"""

from pathlib import Path

# Base directory (where the backend folder is located)
BASE_DIR = Path(__file__).parent.parent.resolve()

# Audio settings
SAMPLE_RATE = 16000  # Whisper expects 16kHz
CHANNELS = 1  # Mono
CHUNK_DURATION = 5  # Seconds per chunk for transcription

# Whisper settings
WHISPER_MODEL = "small"  # Options: tiny, base, small, medium, large-v3
WHISPER_DEVICE = "cpu"  # Use CPU (change to "cuda" if cuDNN is installed)

# LM Studio settings (OpenAI-compatible API)
LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
LM_STUDIO_API_KEY = "lm-studio"  # LM Studio doesn't need a real key

# Storage paths
DATABASE_PATH = str(BASE_DIR / "transcripts.db")
SETTINGS_PATH = str(BASE_DIR / "settings.json")
RECORDINGS_DIR = BASE_DIR / "recordings"
TTS_CACHE_DIR = BASE_DIR / "tts_cache"
BACKUPS_DIR = BASE_DIR / "backups"

# Ensure directories exist
RECORDINGS_DIR.mkdir(exist_ok=True)
TTS_CACHE_DIR.mkdir(exist_ok=True)
BACKUPS_DIR.mkdir(exist_ok=True)

"""Configuration for the Swedish audio transcription pipeline."""

# Audio settings
SAMPLE_RATE = 16000  # Whisper expects 16kHz
CHANNELS = 1  # Mono
CHUNK_DURATION = 5  # Seconds per chunk for transcription

# Whisper settings
WHISPER_MODEL = "small"  # Options: tiny, base, small, medium, large-v3
WHISPER_LANGUAGE = "sv"  # Swedish
WHISPER_DEVICE = "cpu"  # Use CPU (change to "cuda" if cuDNN is installed)

# LM Studio settings (OpenAI-compatible API)
LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
LM_STUDIO_API_KEY = "lm-studio"  # LM Studio doesn't need a real key

# Storage
DATABASE_PATH = "transcripts.db"

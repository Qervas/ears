"""API routers for Ears backend."""

from . import health
from . import vocabulary
from . import transcripts
from . import tts
from . import learning
from . import recordings
from . import settings
from . import backups

__all__ = [
    "health",
    "vocabulary",
    "transcripts",
    "tts",
    "learning",
    "recordings",
    "settings",
    "backups",
]

"""Text-to-Speech endpoints."""

import hashlib
from pathlib import Path

import edge_tts
from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..dependencies import TTS_CACHE, db
from core import get_tts_voice

router = APIRouter(prefix="/tts", tags=["TTS"])


@router.get("/voices")
async def list_voices():
    """List available TTS voices."""
    voices = await edge_tts.list_voices()
    return {"voices": voices}


@router.get("/{word}")
async def text_to_speech(word: str, voice: str = None):
    """Generate TTS audio for a word (with caching)."""
    # Get voice for active language if not specified
    if voice is None:
        active_lang = await db.get_active_language()
        voice = get_tts_voice(active_lang)

    # Create cache key from word + voice
    cache_key = hashlib.md5(f"{word}:{voice}".encode()).hexdigest()
    cache_file = TTS_CACHE / f"{cache_key}.mp3"

    # Return cached file if exists
    if cache_file.exists():
        return FileResponse(cache_file, media_type="audio/mpeg")

    # Generate new audio
    communicate = edge_tts.Communicate(word, voice)
    await communicate.save(str(cache_file))

    return FileResponse(cache_file, media_type="audio/mpeg")

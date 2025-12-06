"""Text-to-Speech endpoints."""

import hashlib
from pathlib import Path

import edge_tts
from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..dependencies import TTS_CACHE

router = APIRouter(prefix="/tts", tags=["TTS"])


@router.get("/voices")
async def list_voices():
    """List available TTS voices."""
    voices = await edge_tts.list_voices()
    swedish_voices = [v for v in voices if v["Locale"].startswith("sv")]
    return {"voices": swedish_voices}


@router.get("/{word}")
async def text_to_speech(word: str):
    """Generate TTS audio for a Swedish word (with caching)."""
    # Create cache key from word
    cache_key = hashlib.md5(word.encode()).hexdigest()
    cache_file = TTS_CACHE / f"{cache_key}.mp3"

    # Return cached file if exists
    if cache_file.exists():
        return FileResponse(cache_file, media_type="audio/mpeg")

    # Generate new audio
    communicate = edge_tts.Communicate(word, "sv-SE-SofieNeural")
    await communicate.save(str(cache_file))

    return FileResponse(cache_file, media_type="audio/mpeg")

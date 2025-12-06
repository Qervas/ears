"""Transcript endpoints."""

from fastapi import APIRouter

from ..dependencies import db

router = APIRouter(prefix="/transcripts", tags=["Transcripts"])


@router.get("/stats")
async def get_transcript_stats():
    """Get transcript statistics."""
    stats = await db.get_transcript_stats()
    return stats


@router.get("")
async def get_transcripts(limit: int = 50, offset: int = 0, language: str = None):
    """Get transcript segments."""
    transcripts = await db.get_transcripts(limit=limit, offset=offset, language=language)
    return {"transcripts": transcripts}



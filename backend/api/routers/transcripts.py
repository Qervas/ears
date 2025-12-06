"""Transcript endpoints."""

from fastapi import APIRouter, BackgroundTasks

from ..dependencies import db
from ..models.recordings import TranscribeRequest

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


async def run_transcription(filepath: str):
    """Background task to transcribe audio file."""
    from faster_whisper import WhisperModel

    model = WhisperModel("large-v3", device="cuda", compute_type="float16")
    segments, info = model.transcribe(filepath, language="sv")

    for segment in segments:
        await db.add_transcript(
            raw_text=segment.text,
            confidence=segment.avg_logprob,
            duration_seconds=segment.end - segment.start
        )


@router.post("/transcribe")
async def transcribe_audio(request: TranscribeRequest, background_tasks: BackgroundTasks):
    """Transcribe an audio file."""
    background_tasks.add_task(run_transcription, request.filepath)
    return {"status": "transcription_started", "filepath": request.filepath}

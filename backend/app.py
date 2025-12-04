"""FastAPI backend for Ears language learning app."""

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
import asyncio
import edge_tts
import tempfile
import os

from database import Database
from config import LM_STUDIO_BASE_URL, LM_STUDIO_API_KEY

app = FastAPI(title="Ears", description="Language learning from real content")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
db = Database()

# TTS cache directory
TTS_CACHE = Path("tts_cache")
TTS_CACHE.mkdir(exist_ok=True)


# ============== Models ==============

class WordStatus(BaseModel):
    word: str
    status: str  # new, learning, known, ignored


class TranscribeRequest(BaseModel):
    filepath: str


class ChatMessage(BaseModel):
    message: str
    context: str = ""  # optional vocabulary context


class ExplanationRequest(BaseModel):
    word: str
    context: str = ""


# ============== Health ==============

@app.get("/")
async def root():
    return {"status": "ok", "app": "Ears"}


@app.get("/api/health")
async def health():
    return {"status": "healthy"}


# ============== Vocabulary ==============

@app.get("/api/vocabulary")
async def get_vocabulary(
    limit: int = 100,
    offset: int = 0,
    status: str = None,
    sort: str = "frequency"
):
    """Get vocabulary list with filtering and pagination."""
    words = await db.get_vocabulary(limit=limit, offset=offset, status=status, sort=sort)
    total = await db.get_vocabulary_count(status=status)
    return {"words": words, "total": total}


@app.get("/api/vocabulary/{word}")
async def get_word(word: str):
    """Get word details with contexts."""
    word_data = await db.get_word(word)
    if not word_data:
        raise HTTPException(status_code=404, detail="Word not found")
    contexts = await db.get_word_contexts(word)
    return {**word_data, "contexts": contexts}


@app.put("/api/vocabulary/{word}/status")
async def update_word_status(word: str, data: WordStatus):
    """Update word learning status."""
    await db.set_word_status(word, data.status)
    return {"success": True}


@app.get("/api/vocabulary/stats")
async def get_vocabulary_stats():
    """Get vocabulary statistics."""
    return await db.get_stats()


# ============== Transcripts ==============

@app.get("/api/transcripts")
async def get_transcripts(limit: int = 50, offset: int = 0):
    """Get transcript segments."""
    transcripts = await db.get_transcripts(limit=limit, offset=offset)
    total = await db.get_transcript_count()
    return {"transcripts": transcripts, "total": total}


@app.post("/api/transcribe")
async def transcribe_file(data: TranscribeRequest, background_tasks: BackgroundTasks):
    """Transcribe an audio file (runs in background)."""
    filepath = Path(data.filepath)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Queue transcription in background
    background_tasks.add_task(run_transcription, str(filepath))
    return {"status": "transcription_started", "file": str(filepath)}


async def run_transcription(filepath: str):
    """Background transcription task."""
    from recorder import transcribe_file
    transcribe_file(filepath)
    # Rebuild vocabulary after transcription
    from vocabulary import build_from_transcripts
    build_from_transcripts()


# ============== TTS ==============

@app.get("/api/tts/{word}")
async def text_to_speech(word: str, voice: str = "sv-SE-SofieNeural"):
    """Generate TTS audio for a word or phrase."""
    # Check cache
    cache_file = TTS_CACHE / f"{word}_{voice}.mp3"

    if not cache_file.exists():
        # Generate TTS
        communicate = edge_tts.Communicate(word, voice)
        await communicate.save(str(cache_file))

    return FileResponse(cache_file, media_type="audio/mpeg")


@app.get("/api/tts/voices")
async def get_tts_voices():
    """Get available Swedish TTS voices."""
    return {
        "voices": [
            {"id": "sv-SE-SofieNeural", "name": "Sofie (Female)"},
            {"id": "sv-SE-MattiasNeural", "name": "Mattias (Male)"},
        ]
    }


# ============== AI / LLM ==============

@app.post("/api/explain")
async def explain_word(data: ExplanationRequest):
    """Get AI explanation for a word."""
    from openai import OpenAI

    client = OpenAI(base_url=LM_STUDIO_BASE_URL, api_key=LM_STUDIO_API_KEY)

    prompt = f"""Explain the Swedish word "{data.word}" to an English speaker learning Swedish.
Include:
1. English translation
2. Part of speech (noun, verb, etc.)
3. Common usage
4. Example sentence in Swedish with English translation

Keep it concise."""

    if data.context:
        prompt += f"\n\nContext where the word appeared: {data.context}"

    try:
        response = client.chat.completions.create(
            model="local-model",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
        return {"explanation": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"LLM unavailable: {str(e)}")


@app.post("/api/chat")
async def chat(data: ChatMessage):
    """Chat with AI tutor in Swedish."""
    from openai import OpenAI

    client = OpenAI(base_url=LM_STUDIO_BASE_URL, api_key=LM_STUDIO_API_KEY)

    system_prompt = """You are a friendly Swedish language tutor.
- Respond in Swedish with simple vocabulary
- After your Swedish response, add a brief English translation in parentheses
- Correct any mistakes gently
- Keep responses conversational and encouraging"""

    if data.context:
        system_prompt += f"\n\nThe student is currently learning these words: {data.context}"

    try:
        response = client.chat.completions.create(
            model="local-model",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": data.message}
            ],
            temperature=0.7,
            max_tokens=300,
        )
        return {"response": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"LLM unavailable: {str(e)}")


# ============== Learning ==============

@app.get("/api/learn/session")
async def get_learning_session(mode: str = "vocabulary", count: int = 10):
    """Get a learning session with words to practice."""
    if mode == "vocabulary":
        # Get words marked as 'learning' or high-frequency 'new' words
        words = await db.get_learning_words(count)
        return {"mode": mode, "words": words}
    elif mode == "sentences":
        # Get sentences containing learning words
        sentences = await db.get_learning_sentences(count)
        return {"mode": mode, "sentences": sentences}
    else:
        raise HTTPException(status_code=400, detail="Invalid mode")


@app.get("/api/learn/progress")
async def get_learning_progress():
    """Get overall learning progress."""
    stats = await db.get_stats()
    return {
        "total_words": stats["total_words"],
        "known": stats["known"],
        "learning": stats["learning"],
        "new": stats["new"],
        "progress_percent": round(stats["known"] / max(stats["total_words"], 1) * 100, 1)
    }


# ============== Recordings ==============

@app.get("/api/recordings")
async def list_recordings():
    """List available recordings."""
    recordings_dir = Path("recordings")
    if not recordings_dir.exists():
        return {"recordings": []}

    files = []
    for f in sorted(recordings_dir.glob("*.wav")):
        files.append({
            "name": f.name,
            "path": str(f),
            "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
            "has_transcript": (recordings_dir / f"{f.stem}.txt").exists()
        })

    return {"recordings": files}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

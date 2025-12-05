"""FastAPI backend for Ears language learning app."""

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
import asyncio
import edge_tts
import tempfile
import os
import sounddevice as sd
from datetime import datetime

from database import Database
from config import LM_STUDIO_BASE_URL, LM_STUDIO_API_KEY
from recorder import Recorder

# Base directory (where app.py is located)
BASE_DIR = Path(__file__).parent.resolve()
RECORDINGS_DIR = BASE_DIR / "recordings"

# Global recorder instance
recorder_instance: Recorder | None = None
recording_status = {"recording": False, "device_id": None, "start_time": None}

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
TTS_CACHE = BASE_DIR / "tts_cache"
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


@app.get("/api/vocabulary/stats")
async def get_vocabulary_stats():
    """Get vocabulary statistics."""
    return await db.get_stats()


@app.get("/api/vocabulary/words-without-explanations")
async def get_words_without_explanations():
    """Get list of words without explanation_json."""
    # Get total count first
    total = await db.get_vocabulary_count()
    # Fetch all words
    words = await db.get_vocabulary(limit=total, offset=0)
    words_without = [
        w['word'] for w in words
        if not w.get('explanation_json')
    ]
    return {"words": words_without}


@app.post("/api/vocabulary/generate-explanation/{word}")
async def generate_single_explanation(word: str):
    """Generate AI explanation for a single word."""
    from openai import OpenAI
    import json as json_module

    # Get context examples
    contexts = await db.get_word_contexts(word, limit=2)
    context = contexts[0] if contexts else ""

    prompt = f"""You are a Swedish language teacher helping English speakers learn Swedish.

Explain the Swedish word: "{word}"
{f'Context where learner saw it: "{context}"' if context else ''}

Provide a structured JSON explanation in this exact format:
{{
  "translation": "primary English translation",
  "type": "word type (noun/verb/adjective/preposition/etc.)",
  "usagePatterns": [
    {{"pattern": "swedish phrase", "meaning": "english meaning", "category": "type like 'accompaniment' or 'instrument'"}},
    {{"pattern": "another phrase", "meaning": "its meaning", "category": "category"}}
  ],
  "relatedWords": [
    {{"word": "swedish word", "relation": "opposite/similar/related", "translation": "english"}},
    {{"word": "another word", "relation": "type", "translation": "english"}}
  ],
  "tip": "One helpful sentence about usage or memory trick",
  "note": "Cultural note or important grammar point (or null if none)"
}}

Focus on practical, common usage. Include 2-3 usage patterns and 2-3 related words."""

    client = OpenAI(base_url=LM_STUDIO_BASE_URL, api_key=LM_STUDIO_API_KEY)

    try:
        response = client.chat.completions.create(
            model="local-model",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=800,
        )

        explanation_text = response.choices[0].message.content.strip()

        # Try to parse as JSON
        try:
            json_module.loads(explanation_text)  # Validate JSON
            await db.update_word_explanation(word, explanation_text)
            return {"success": True, "word": word}
        except json_module.JSONDecodeError:
            print(f"Failed to parse JSON for word: {word}")
            return {"success": False, "word": word, "error": "Invalid JSON response"}

    except Exception as e:
        print(f"Error generating explanation for {word}: {e}")
        return {"success": False, "word": word, "error": str(e)}


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


# ============== Transcripts ==============

@app.get("/api/transcripts/stats")
async def get_transcript_stats():
    """Get transcript statistics by language."""
    return await db.get_transcript_stats()


@app.get("/api/transcripts")
async def get_transcripts(limit: int = 50, offset: int = 0, language: str = None):
    """Get transcript segments."""
    transcripts = await db.get_transcripts(limit=limit, offset=offset, language=language)
    total = await db.get_transcript_count()
    stats = await db.get_transcript_stats()
    return {"transcripts": transcripts, "total": total, "stats": stats}


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

@app.get("/api/tts/voices")
async def get_tts_voices():
    """Get available Swedish TTS voices."""
    return {
        "voices": [
            {"id": "sv-SE-SofieNeural", "name": "Sofie (Female)"},
            {"id": "sv-SE-MattiasNeural", "name": "Mattias (Male)"},
        ]
    }


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


# ============== AI / LLM ==============

@app.post("/api/explain")
async def explain_word(data: ExplanationRequest):
    """Get AI explanation for a word with structured JSON output."""
    from openai import OpenAI
    import json as json_module

    client = OpenAI(base_url=LM_STUDIO_BASE_URL, api_key=LM_STUDIO_API_KEY)

    # Get word frequency for context
    db = Database()
    word_data = await db.get_word(data.word)
    frequency = word_data.get('frequency', 0) if word_data else 0

    prompt = f"""You are a Swedish language teacher. Explain the Swedish word "{data.word}" (seen {frequency} times by the learner) in a structured, engaging way.

Respond with ONLY a valid JSON object (no markdown, no code blocks) with this exact structure:
{{
  "translation": "primary English translation",
  "type": "word type (noun/verb/adjective/preposition/etc.)",
  "usagePatterns": [
    {{"pattern": "swedish phrase", "meaning": "english meaning", "category": "type like 'accompaniment' or 'instrument'"}},
    {{"pattern": "another phrase", "meaning": "its meaning", "category": "category"}}
  ],
  "relatedWords": [
    {{"word": "swedish word", "relation": "opposite/similar/related", "translation": "english"}},
    {{"word": "another word", "relation": "type", "translation": "english"}}
  ],
  "tip": "One helpful sentence about usage or memory trick",
  "note": "Cultural note or important grammar point (or null if none)"
}}

Focus on practical, common usage. Include 2-3 usage patterns and 2-3 related words."""

    if data.context:
        prompt += f"\n\nThe learner saw this word in context: \"{data.context}\""

    try:
        response = client.chat.completions.create(
            model="local-model",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=800,
        )

        explanation_text = response.choices[0].message.content.strip()

        # Try to parse as JSON
        try:
            explanation_json = json_module.loads(explanation_text)

            # Save to database
            await db.update_word_explanation(data.word, explanation_text)

            return {"explanation": explanation_json}
        except json_module.JSONDecodeError:
            # Fallback to plain text if JSON parsing fails
            return {"explanation": {"raw": explanation_text}}

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
        # Get words marked as 'learning'
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
        "progress_percent": round(stats["known"] / max(stats["total_words"], 1) * 100, 1)
    }


@app.get("/api/learn/listening-quiz")
async def get_listening_quiz(count: int = 10):
    """Get random Swedish segments from recordings for listening practice."""
    import json as json_module
    import random

    # Get all JSON transcript files
    json_files = list(RECORDINGS_DIR.glob("*.json"))

    if not json_files:
        return {"segments": []}

    # Collect all Swedish segments from all recordings
    all_segments = []

    for json_file in json_files:
        try:
            data = json_module.loads(json_file.read_text(encoding='utf-8'))
            recording_name = json_file.stem + ".wav"

            for seg in data.get("segments", []):
                # Only include Swedish segments with timestamps and reasonable length
                if (seg.get("language") == "sv" and
                    seg.get("start") is not None and
                    seg.get("end") is not None and
                    len(seg.get("text", "").strip()) > 10):  # At least 10 chars

                    all_segments.append({
                        "text": seg["text"].strip(),
                        "start": seg["start"],
                        "end": seg["end"],
                        "recording": recording_name,
                        "audio_url": f"http://localhost:8000/api/recordings/{recording_name}/audio"
                    })
        except Exception as e:
            print(f"Error reading {json_file}: {e}")
            continue

    # Randomly select segments
    if len(all_segments) == 0:
        return {"segments": []}

    selected = random.sample(all_segments, min(count, len(all_segments)))

    return {"segments": selected}


@app.get("/api/learn/grammar-patterns")
async def get_grammar_patterns():
    """Extract grammar patterns from recordings."""
    import json as json_module
    from collections import defaultdict

    # Common Swedish prepositions
    PREPOSITIONS = ['med', 'på', 'i', 'till', 'från', 'av', 'för', 'om', 'över', 'under', 'vid', 'hos', 'åt']

    # Common Swedish modal verbs
    MODALS = ['ska', 'vill', 'kan', 'måste', 'bör', 'får', 'skulle', 'kunde']

    json_files = list(RECORDINGS_DIR.glob("*.json"))

    if not json_files:
        return {"patterns": []}

    # Collect patterns
    prep_patterns = defaultdict(list)
    modal_patterns = defaultdict(list)

    for json_file in json_files:
        try:
            data = json_module.loads(json_file.read_text(encoding='utf-8'))
            recording_name = json_file.stem + ".wav"

            for seg in data.get("segments", []):
                if seg.get("language") != "sv":
                    continue

                text = seg.get("text", "").strip()
                words = text.lower().split()

                # Find preposition patterns
                for i, word in enumerate(words):
                    if word in PREPOSITIONS:
                        # Get context (1 word before, prep, 2 words after if available)
                        context_before = words[i-1] if i > 0 else ""
                        context_after = " ".join(words[i+1:i+3]) if i < len(words)-1 else ""

                        if context_before and context_after:
                            prep_patterns[word].append({
                                "text": text,
                                "context_before": context_before,
                                "preposition": word,
                                "context_after": context_after,
                                "recording": recording_name
                            })

                # Find modal verb patterns
                for i, word in enumerate(words):
                    if word in MODALS and i < len(words) - 1:
                        # Modal + verb pattern
                        modal_patterns[word].append({
                            "text": text,
                            "modal": word,
                            "following_word": words[i+1],
                            "recording": recording_name
                        })

        except Exception as e:
            print(f"Error processing {json_file}: {e}")
            continue

    # Format patterns for frontend
    patterns = []

    # Add preposition patterns
    for prep, examples in prep_patterns.items():
        if len(examples) >= 3:  # Only include if we have at least 3 examples
            patterns.append({
                "type": "preposition",
                "word": prep,
                "count": len(examples),
                "examples": examples[:10]  # Limit to 10 examples
            })

    # Add modal verb patterns
    for modal, examples in modal_patterns.items():
        if len(examples) >= 3:
            patterns.append({
                "type": "modal",
                "word": modal,
                "count": len(examples),
                "examples": examples[:10]
            })

    # Sort by count (most common first)
    patterns.sort(key=lambda x: x["count"], reverse=True)

    return {"patterns": patterns[:20]}  # Return top 20 patterns


@app.get("/api/learn/grammar-quiz")
async def get_grammar_quiz(count: int = 10):
    """Generate grammar fill-in-the-blank quiz using AI."""
    from openai import OpenAI
    import json as json_module
    import random

    # First, get patterns
    patterns_response = await get_grammar_patterns()
    patterns = patterns_response.get("patterns", [])

    if not patterns:
        return {"questions": []}

    # Select random patterns
    selected_patterns = random.sample(patterns, min(count, len(patterns)))

    questions = []

    # Use LLM to generate quiz questions
    client = OpenAI(base_url=LM_STUDIO_BASE_URL, api_key=LM_STUDIO_API_KEY)

    for pattern in selected_patterns:
        # Get 2-3 real examples from recordings
        examples = pattern.get("examples", [])[:3]
        word = pattern["word"]
        pattern_type = pattern["type"]

        # Create a base sentence from examples
        if not examples:
            continue

        base_example = examples[0]["text"]

        # Generate AI quiz question
        prompt = f"""You are a Swedish language teacher. Based on this Swedish word "{word}" ({pattern_type}), create a fill-in-the-blank quiz question.

Real example from student's recordings: "{base_example}"

Generate a JSON response with:
1. A new sentence with "{word}" replaced by "___"
2. Four options (one correct: "{word}", three plausible Swedish alternatives)
3. A brief explanation of when to use "{word}"

Respond with ONLY valid JSON (no markdown, no code blocks):
{{
  "sentence": "Swedish sentence with ___",
  "options": ["word1", "word2", "word3", "word4"],
  "correct_index": 0,
  "explanation": "Brief explanation"
}}"""

        try:
            response = client.chat.completions.create(
                model="local-model",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=300,
            )

            ai_response = response.choices[0].message.content.strip()

            # Parse JSON
            try:
                quiz_data = json_module.loads(ai_response)
                questions.append({
                    "word": word,
                    "type": pattern_type,
                    "sentence": quiz_data.get("sentence", ""),
                    "options": quiz_data.get("options", []),
                    "correct_index": quiz_data.get("correct_index", 0),
                    "explanation": quiz_data.get("explanation", ""),
                    "real_examples": [ex["text"] for ex in examples]
                })
            except json_module.JSONDecodeError:
                # Fallback: create simple question from real example
                # Blank out the target word
                sentence_with_blank = base_example.replace(word, "___", 1)
                questions.append({
                    "word": word,
                    "type": pattern_type,
                    "sentence": sentence_with_blank,
                    "options": [word, "på", "i", "till"],  # Simple fallback options
                    "correct_index": 0,
                    "explanation": f"Common usage of '{word}'",
                    "real_examples": [ex["text"] for ex in examples]
                })

        except Exception as e:
            print(f"Error generating quiz for {word}: {e}")
            continue

    return {"questions": questions[:count]}


# ============== Recordings ==============

@app.get("/api/recordings")
async def list_recordings():
    """List available recordings."""
    if not RECORDINGS_DIR.exists():
        return {"recordings": []}

    files = []
    for f in sorted(RECORDINGS_DIR.glob("*.wav"), reverse=True):  # Most recent first
        txt_file = RECORDINGS_DIR / f"{f.stem}.txt"
        files.append({
            "name": f.name,
            "path": str(f),
            "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
            "has_transcript": txt_file.exists()
        })

    return {"recordings": files}


@app.get("/api/recordings/{filename}/transcript")
async def get_recording_transcript(filename: str):
    """Get transcript content for a specific recording with timestamps."""
    import json as json_module
    from recorder import detect_segment_language

    wav_file = RECORDINGS_DIR / filename
    json_file = RECORDINGS_DIR / f"{wav_file.stem}.json"
    txt_file = RECORDINGS_DIR / f"{wav_file.stem}.txt"

    if not wav_file.exists():
        raise HTTPException(status_code=404, detail="Recording not found")

    # Prefer JSON file with timestamps if available
    if json_file.exists():
        data = json_module.loads(json_file.read_text(encoding='utf-8'))
        full_text = " ".join(s["text"] for s in data["segments"])
        return {
            "full_text": full_text,
            "duration": data.get("duration", 0),
            "segments": data["segments"],
            "stats": data["stats"]
        }

    # Fallback to txt file (no timestamps)
    if not txt_file.exists():
        raise HTTPException(status_code=404, detail="Transcript not found")

    full_text = txt_file.read_text(encoding='utf-8')

    # Split into sentences and detect language for each
    import re
    sentences = re.split(r'(?<=[.!?])\s+', full_text)
    segments = []

    for sentence in sentences:
        sentence = sentence.strip()
        if sentence:
            lang = detect_segment_language(sentence)
            segments.append({
                "text": sentence,
                "language": lang,
                "start": None,
                "end": None
            })

    sv_count = sum(1 for s in segments if s["language"] == "sv")
    en_count = len(segments) - sv_count

    return {
        "full_text": full_text,
        "duration": None,
        "segments": segments,
        "stats": {
            "total": len(segments),
            "swedish": sv_count,
            "english": en_count
        }
    }


@app.get("/api/recordings/{filename}/audio")
async def get_recording_audio(filename: str, request: Request):
    """Serve the audio file for playback with range support."""
    from fastapi.responses import StreamingResponse

    wav_file = RECORDINGS_DIR / filename
    if not wav_file.exists():
        raise HTTPException(status_code=404, detail="Recording not found")

    file_size = wav_file.stat().st_size

    # Handle range requests for proper streaming
    range_header = request.headers.get("range")

    if range_header:
        # Parse range header: "bytes=start-end"
        range_match = range_header.replace("bytes=", "").split("-")
        start = int(range_match[0]) if range_match[0] else 0
        end = int(range_match[1]) if range_match[1] else file_size - 1

        if start >= file_size:
            raise HTTPException(status_code=416, detail="Range not satisfiable")

        end = min(end, file_size - 1)
        content_length = end - start + 1

        def iter_file():
            with open(wav_file, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk_size = min(8192, remaining)
                    data = f.read(chunk_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            iter_file(),
            status_code=206,
            media_type="audio/wav",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
            }
        )

    # No range header - return full file
    return FileResponse(
        wav_file,
        media_type="audio/wav",
        headers={"Accept-Ranges": "bytes"}
    )


# ============== Recording Control ==============

@app.get("/api/audio-devices")
async def get_audio_devices():
    """List available audio input devices."""
    devices = sd.query_devices()
    input_devices = []
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            input_devices.append({
                "id": i,
                "name": dev['name'],
                "sample_rate": int(dev['default_samplerate']),
                "channels": dev['max_input_channels']
            })
    return {"devices": input_devices}


class RecordingStartRequest(BaseModel):
    device_id: int


@app.post("/api/recording/start")
async def start_recording(data: RecordingStartRequest):
    """Start recording from specified device."""
    global recorder_instance, recording_status

    if recording_status["recording"]:
        raise HTTPException(status_code=400, detail="Already recording")

    try:
        recorder_instance = Recorder()
        recorder_instance.start(data.device_id)
        recording_status = {
            "recording": True,
            "device_id": data.device_id,
            "start_time": datetime.now().isoformat()
        }
        return {"status": "recording_started", "device_id": data.device_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start recording: {str(e)}")


@app.post("/api/recording/stop")
async def stop_recording(background_tasks: BackgroundTasks):
    """Stop recording and optionally transcribe."""
    global recorder_instance, recording_status

    if not recording_status["recording"] or recorder_instance is None:
        raise HTTPException(status_code=400, detail="Not currently recording")

    try:
        filepath = recorder_instance.stop()
        recording_status = {"recording": False, "device_id": None, "start_time": None}
        recorder_instance = None

        if filepath:
            return {"status": "recording_stopped", "filepath": filepath}
        else:
            raise HTTPException(status_code=500, detail="No audio recorded")
    except Exception as e:
        recording_status = {"recording": False, "device_id": None, "start_time": None}
        recorder_instance = None
        raise HTTPException(status_code=500, detail=f"Failed to stop recording: {str(e)}")


@app.get("/api/recording/status")
async def get_recording_status():
    """Get current recording status."""
    return recording_status


@app.post("/api/vocabulary/rebuild")
async def rebuild_vocabulary():
    """Rebuild vocabulary from all transcripts."""
    from vocabulary import build_from_transcripts
    try:
        build_from_transcripts()
        return {"status": "vocabulary_rebuilt"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to rebuild vocabulary: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

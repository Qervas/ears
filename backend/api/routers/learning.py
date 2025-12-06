"""Learning mode endpoints."""

import random
import re
from collections import Counter

from fastapi import APIRouter

from ..dependencies import db
from ..models.vocabulary import ChatMessage
from ..services.ai_service import AIService

router = APIRouter(prefix="/learn", tags=["Learning"])


@router.get("/session")
async def get_learning_session(mode: str = "vocabulary", count: int = 10):
    """Get a learning session with words or sentences."""
    if mode == "vocabulary":
        words = await db.get_learning_words(count)
        return {"mode": mode, "words": words}
    elif mode == "sentences":
        sentences = await db.get_random_sentences(count)
        return {"mode": mode, "sentences": sentences}
    else:
        return {"mode": mode, "items": []}


@router.get("/progress")
async def get_learning_progress():
    """Get overall learning progress."""
    total = await db.get_vocabulary_count()
    known = await db.get_vocabulary_count(status="known")
    learning = await db.get_vocabulary_count(status="learning")

    return {
        "total_words": total,
        "known": known,
        "learning": learning,
        "progress_percent": round((known / total * 100) if total > 0 else 0, 1)
    }


@router.get("/listening-quiz")
async def get_listening_quiz(count: int = 10):
    """Get random Swedish audio segments for listening practice."""
    import json
    from ..dependencies import RECORDINGS_DIR

    all_segments = []

    # Read from JSON transcript files in recordings folder
    if RECORDINGS_DIR.exists():
        for json_file in RECORDINGS_DIR.glob("*.json"):
            try:
                data = json.loads(json_file.read_text(encoding='utf-8'))
                recording_name = json_file.stem + ".wav"

                # Get Swedish segments with timestamps
                for seg in data.get("segments", []):
                    if seg.get("language") == "sv" and seg.get("start") is not None:
                        all_segments.append({
                            "text": seg["text"],
                            "start": seg["start"],
                            "end": seg["end"],
                            "recording": recording_name,
                            "audio_url": f"/api/recordings/{recording_name}/audio"
                        })
            except Exception:
                continue

    # Sample random segments
    sample_size = min(count, len(all_segments))
    segments = random.sample(all_segments, sample_size) if all_segments else []

    return {"segments": segments}


@router.get("/grammar-patterns")
async def get_grammar_patterns():
    """Extract common grammar patterns from transcripts."""
    transcripts = await db.get_transcripts(limit=200)

    # Simple pattern extraction
    patterns = []
    pattern_counts = Counter()

    for t in transcripts:
        text = t.get("cleaned_text") or t.get("raw_text", "")

        # Find verb patterns (ending in -ar, -er, -r)
        verbs = re.findall(r'\b\w+(?:ar|er|ir|or)\b', text.lower())
        for v in verbs:
            pattern_counts[f"verb: {v}"] += 1

        # Find definite article patterns
        definite = re.findall(r'\b\w+(?:en|et|na|erna)\b', text.lower())
        for d in definite:
            pattern_counts[f"definite: {d}"] += 1

    # Get top patterns
    for pattern, count in pattern_counts.most_common(20):
        pattern_type, word = pattern.split(": ", 1)
        patterns.append({
            "pattern": pattern_type,
            "example": word,
            "frequency": count
        })

    return {"patterns": patterns}


@router.get("/grammar-quiz")
async def get_grammar_quiz():
    """Generate grammar quiz questions using AI."""
    # Get patterns to base questions on
    transcripts = await db.get_transcripts(limit=50)

    patterns = []
    for t in transcripts[:5]:
        text = t.get("cleaned_text") or t.get("raw_text", "")
        if text:
            patterns.append({"pattern": "sentence", "example": text[:100]})

    if not patterns:
        return {"questions": []}

    questions = await AIService.generate_grammar_quiz(patterns)
    return {"questions": questions}


@router.post("/chat")
async def chat_with_tutor(message: ChatMessage):
    """Chat with AI Swedish tutor."""
    try:
        response = await AIService.chat(message.message, message.context)
        return {"response": response}
    except Exception as e:
        return {"response": f"Sorry, I encountered an error: {str(e)}"}


@router.post("/explain")
async def explain_word(word: str, context: str = ""):
    """Get AI explanation for a word and save it."""
    result = await AIService.generate_explanation(word, context)

    if result["success"]:
        return {"explanation": result["explanation"]}
    else:
        return {"explanation": f"Could not generate explanation: {result['error']}"}

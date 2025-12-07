"""Vocabulary endpoints."""

from fastapi import APIRouter, HTTPException, BackgroundTasks

from ..dependencies import db
from ..models.vocabulary import WordStatus, ExplanationRequest, ChatMessage, ReviewRequest
from ..services.ai_service import AIService

router = APIRouter(prefix="/vocabulary", tags=["Vocabulary"])


@router.get("")
async def get_vocabulary(
    limit: int = 100,
    offset: int = 0,
    status: str = None,
    sort: str = "frequency",
    search: str = None
):
    """Get vocabulary list with optional filtering and search."""
    words = await db.get_vocabulary(limit=limit, offset=offset, status=status, sort=sort, search=search)
    total = await db.get_vocabulary_count(status=status)
    return {"words": words, "total": total}


@router.get("/stats")
async def get_vocabulary_stats():
    """Get vocabulary statistics."""
    total = await db.get_vocabulary_count()
    undiscovered = await db.get_vocabulary_count(status="undiscovered")
    learning = await db.get_vocabulary_count(status="learning")
    known = await db.get_vocabulary_count(status="known")
    return {
        "total": total,
        "undiscovered": undiscovered,
        "learning": learning,
        "known": known
    }


@router.get("/words-without-explanations")
async def get_words_without_explanations():
    """Get count of words without AI explanations."""
    total = await db.get_vocabulary_count()
    words = await db.get_vocabulary(limit=total, offset=0)
    without = [w for w in words if not w.get('explanation_json')]
    return {"count": len(without), "total": total}


@router.get("/bulk-generation-status")
async def get_bulk_generation_status():
    """Get current status of bulk explanation generation."""
    return AIService.bulk_status


@router.post("/generate-all-explanations")
async def start_bulk_generation(background_tasks: BackgroundTasks):
    """Start background task to generate explanations for all words without them."""
    if AIService.bulk_status["running"]:
        raise HTTPException(status_code=409, detail="Bulk generation already running")

    # Get words without explanations
    total = await db.get_vocabulary_count()
    words = await db.get_vocabulary(limit=total, offset=0)

    words_with_explanations = [w for w in words if w.get('explanation_json')]
    words_without = [w['word'] for w in words if not w.get('explanation_json')]

    print(f"\n📊 GENERATE MISSING - Database stats:")
    print(f"   Total words: {total}")
    print(f"   With explanations: {len(words_with_explanations)}")
    print(f"   Without explanations: {len(words_without)}")
    print(f"   Will process: {len(words_without)} words\n")

    if not words_without:
        return {"message": "No words need explanations", "count": 0}

    background_tasks.add_task(AIService.generate_explanations_batch, words_without)

    return {"message": "Bulk generation started", "count": len(words_without)}


@router.post("/regenerate-all-explanations")
async def start_regenerate_all(background_tasks: BackgroundTasks):
    """Start background task to regenerate explanations for ALL words."""
    if AIService.bulk_status["running"]:
        raise HTTPException(status_code=409, detail="Bulk generation already running")

    total = await db.get_vocabulary_count()
    words = await db.get_vocabulary(limit=total, offset=0)
    all_words = [w['word'] for w in words]

    words_with_explanations = [w for w in words if w.get('explanation_json')]

    print(f"\n⚠️ REGENERATE ALL - Database stats:")
    print(f"   Total words: {total}")
    print(f"   Existing explanations: {len(words_with_explanations)} (will be overwritten!)")
    print(f"   Will process: {len(all_words)} words\n")

    if not all_words:
        return {"message": "No words in vocabulary", "count": 0}

    background_tasks.add_task(AIService.generate_explanations_batch, all_words)

    return {"message": "Regeneration started", "count": len(all_words)}


@router.post("/generate-explanation/{word}")
async def generate_single_explanation(word: str, request: ExplanationRequest = None):
    """Generate AI explanation for a single word."""
    context = request.context if request else ""
    result = await AIService.generate_explanation(word, context)

    if result["success"]:
        return result
    else:
        raise HTTPException(status_code=500, detail=result["error"])


@router.get("/{word}")
async def get_word(word: str):
    """Get details for a specific word."""
    word_data = await db.get_word(word)
    if not word_data:
        raise HTTPException(status_code=404, detail="Word not found")

    # Add contexts and example
    contexts = await db.get_word_contexts(word, limit=10)
    word_data["contexts"] = contexts
    word_data["example"] = contexts[0] if contexts else None

    return word_data


@router.put("/{word}/status")
async def update_word_status(word: str, status_update: WordStatus):
    """Update the learning status of a word."""
    await db.set_word_status(word, status_update.status)
    return {"status": "updated", "word": word, "new_status": status_update.status}


# ============== Spaced Repetition ==============

@router.get("/srs/due")
async def get_due_words(count: int = 20):
    """Get words due for spaced repetition review."""
    words = await db.get_due_words(count)
    return {"words": words, "count": len(words)}


@router.get("/srs/stats")
async def get_srs_stats():
    """Get spaced repetition statistics."""
    return await db.get_srs_stats()


@router.post("/srs/review/{word}")
async def record_review(word: str, review: ReviewRequest):
    """Record a spaced repetition review for a word."""
    if not 0 <= review.quality <= 5:
        raise HTTPException(status_code=400, detail="Quality must be between 0 and 5")
    result = await db.record_review(word, review.quality)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/rebuild")
async def rebuild_vocabulary():
    """Rebuild vocabulary from all transcripts."""
    from vocabulary import extract_and_store_vocabulary
    await extract_and_store_vocabulary()
    return {"status": "vocabulary_rebuilt"}

"""Vocabulary-related Pydantic models."""

from pydantic import BaseModel


class WordStatus(BaseModel):
    """Update word learning status."""
    word: str
    status: str  # new, learning, known, ignored


class ExplanationRequest(BaseModel):
    """Request AI explanation for a word."""
    word: str
    context: str = ""


class ChatMessage(BaseModel):
    """Chat message for AI tutor."""
    message: str
    context: str = ""  # optional vocabulary context

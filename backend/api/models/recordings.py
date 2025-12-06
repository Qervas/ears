"""Recording-related Pydantic models."""

from pydantic import BaseModel


class TranscribeRequest(BaseModel):
    """Request to transcribe an audio file."""
    filepath: str


class RecordingStartRequest(BaseModel):
    """Request to start recording."""
    device_id: int

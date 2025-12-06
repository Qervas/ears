"""Recording endpoints."""

import os
from pathlib import Path

import sounddevice as sd
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..dependencies import db, RECORDINGS_DIR
from ..services.recording_service import RecordingService

router = APIRouter(tags=["Recordings"])


@router.get("/recordings")
async def list_recordings():
    """List all recordings with metadata."""
    recordings = []
    if RECORDINGS_DIR.exists():
        for f in sorted(RECORDINGS_DIR.glob("*.wav"), reverse=True):
            stat = f.stat()
            recordings.append({
                "filename": f.name,
                "size_bytes": stat.st_size,
                "created": stat.st_mtime
            })
    return {"recordings": recordings}


@router.get("/recordings/{filename}/transcript")
async def get_recording_transcript(filename: str):
    """Get transcript segments for a specific recording."""
    # Get segments that reference this recording
    segments = await db.get_recording_segments(filename)
    return {"filename": filename, "segments": segments}


@router.get("/recordings/{filename}/audio")
async def stream_audio(filename: str, request: Request):
    """Stream audio file with range request support."""
    # Security: prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    filepath = RECORDINGS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Recording not found")

    file_size = filepath.stat().st_size
    range_header = request.headers.get("range")

    if range_header:
        # Parse range header
        range_match = range_header.replace("bytes=", "").split("-")
        start = int(range_match[0])
        end = int(range_match[1]) if range_match[1] else file_size - 1

        def iterfile():
            with open(filepath, "rb") as f:
                f.seek(start)
                remaining = end - start + 1
                chunk_size = 8192
                while remaining > 0:
                    chunk = f.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            iterfile(),
            status_code=206,
            media_type="audio/wav",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(end - start + 1)
            }
        )
    else:
        def iterfile():
            with open(filepath, "rb") as f:
                yield from f

        return StreamingResponse(
            iterfile(),
            media_type="audio/wav",
            headers={
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes"
            }
        )


@router.get("/audio-devices")
async def list_audio_devices():
    """List available audio input devices."""
    devices = sd.query_devices()
    input_devices = [
        {"id": i, "name": d["name"], "channels": d["max_input_channels"]}
        for i, d in enumerate(devices)
        if d["max_input_channels"] > 0
    ]
    return {"devices": input_devices}


@router.post("/recording/start")
async def start_recording(device_id: int = 0):
    """Start recording audio."""
    result = RecordingService.start_recording(device_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/recording/stop")
async def stop_recording():
    """Stop recording and save the audio file."""
    result = RecordingService.stop_recording()

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/recording/status")
async def get_recording_status():
    """Get current recording status."""
    return RecordingService.get_status()

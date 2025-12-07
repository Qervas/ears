"""Recording endpoints."""

import os
from pathlib import Path

import sounddevice as sd
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse

from ..dependencies import RECORDINGS_DIR
from ..models.recordings import RecordingStartRequest, TranscribeRequest
from ..services.recording_service import RecordingService

router = APIRouter(tags=["Recordings"])


@router.get("/recordings")
async def list_recordings():
    """List all recordings with metadata."""
    recordings = []
    if RECORDINGS_DIR.exists():
        for f in sorted(RECORDINGS_DIR.glob("*.wav"), reverse=True):
            txt_file = RECORDINGS_DIR / f"{f.stem}.txt"
            recordings.append({
                "name": f.name,
                "path": str(f),
                "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                "has_transcript": txt_file.exists()
            })
    return {"recordings": recordings}


@router.post("/recordings/open-folder")
async def open_recordings_folder():
    """Open the recordings folder in file explorer."""
    import subprocess
    import sys

    try:
        if sys.platform == 'win32':
            subprocess.Popen(['explorer', str(RECORDINGS_DIR)])
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', str(RECORDINGS_DIR)])
        else:
            subprocess.Popen(['xdg-open', str(RECORDINGS_DIR)])

        return {"status": "opened", "path": str(RECORDINGS_DIR)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open folder: {str(e)}")


@router.get("/recordings/{filename}/transcript")
async def get_recording_transcript(filename: str):
    """Get transcript content for a specific recording with timestamps."""
    import json as json_module
    import re
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
        # Parse range header: "bytes=start-end"
        range_match = range_header.replace("bytes=", "").split("-")
        start = int(range_match[0]) if range_match[0] else 0
        end = int(range_match[1]) if range_match[1] else file_size - 1

        if start >= file_size:
            raise HTTPException(status_code=416, detail="Range not satisfiable")

        end = min(end, file_size - 1)
        content_length = end - start + 1

        def iterfile():
            with open(filepath, "rb") as f:
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
            iterfile(),
            status_code=206,
            media_type="audio/wav",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length)
            }
        )

    # No range header - return full file
    return FileResponse(
        filepath,
        media_type="audio/wav",
        headers={"Accept-Ranges": "bytes"}
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
async def start_recording(data: RecordingStartRequest):
    """Start recording audio."""
    result = RecordingService.start_recording(data.device_id)

    if "error" in result:
        raise HTTPException(status_code=500, detail=f"Failed to start recording: {result['error']}")

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


def run_transcription(filepath: str):
    """Background task to transcribe audio file."""
    from recorder import transcribe_file
    transcribe_file(filepath)
    # Rebuild vocabulary after transcription
    from vocabulary import build_from_transcripts
    build_from_transcripts()


@router.post("/transcribe")
async def transcribe_audio(request: TranscribeRequest, background_tasks: BackgroundTasks):
    """Transcribe an audio file."""
    background_tasks.add_task(run_transcription, request.filepath)
    return {"status": "transcription_started", "filepath": request.filepath}

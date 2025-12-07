"""Recording service for managing audio recording state."""

from datetime import datetime
from typing import Optional

from recorder import Recorder


class RecordingService:
    """Service for managing recording state and operations."""

    # Shared recording state
    _instance: Optional[Recorder] = None
    _status = {
        "recording": False,
        "device_id": None,
        "start_time": None
    }

    @classmethod
    def get_instance(cls) -> Optional[Recorder]:
        """Get the current recorder instance."""
        return cls._instance

    @classmethod
    def set_instance(cls, recorder: Optional[Recorder]):
        """Set the recorder instance."""
        cls._instance = recorder

    @classmethod
    def get_status(cls) -> dict:
        """Get current recording status."""
        return cls._status.copy()

    @classmethod
    def is_recording(cls) -> bool:
        """Check if currently recording."""
        return cls._status["recording"]

    @classmethod
    def start_recording(cls, device_id: int) -> dict:
        """Start a new recording session."""
        if cls._status["recording"]:
            return {"error": "Already recording"}

        try:
            cls._instance = Recorder()
            cls._instance.start(device_id)

            cls._status["recording"] = True
            cls._status["device_id"] = device_id
            cls._status["start_time"] = datetime.now().isoformat()

            return {
                "status": "recording_started",
                "device_id": device_id,
                "start_time": cls._status["start_time"]
            }
        except Exception as e:
            return {"error": str(e)}

    @classmethod
    def stop_recording(cls) -> dict:
        """Stop the current recording session."""
        if not cls._status["recording"] or cls._instance is None:
            return {"error": "Not currently recording"}

        try:
            filepath = cls._instance.stop()

            cls._status["recording"] = False
            cls._status["device_id"] = None
            cls._status["start_time"] = None
            cls._instance = None

            return {
                "status": "recording_stopped",
                "filepath": filepath
            }
        except Exception as e:
            cls._status["recording"] = False
            cls._instance = None
            return {"error": str(e)}

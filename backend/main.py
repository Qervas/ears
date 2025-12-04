"""Main application - Real-time Swedish audio transcription."""

import time
import signal
import sys
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from audio_capture import AudioCapture
from transcriber import Transcriber
from storage import save_transcript
from config import CHUNK_DURATION

console = Console()


class Ears:
    """Main application for real-time Swedish transcription."""

    def __init__(self):
        self.running = False
        self.capture = None
        self.transcriber = None
        self.transcript_count = 0

    def setup(self, device_id: int = None):
        """Initialize components."""
        console.print("[bold blue]EARS - Swedish Audio Transcription[/bold blue]")
        console.print()

        # Initialize transcriber (loads model)
        self.transcriber = Transcriber()
        console.print()

        # Initialize audio capture
        self.capture = AudioCapture(chunk_seconds=CHUNK_DURATION)

        if device_id is None:
            self.capture.list_devices()
            console.print("\nEnter device ID for system audio (or press Enter to auto-detect):")
            device_input = input("> ").strip()
            device_id = int(device_input) if device_input else None

        if not self.capture.start(device_id):
            return False

        return True

    def run(self):
        """Main transcription loop."""
        self.running = True
        console.print("\n[green]✓ Listening... Press Ctrl+C to stop[/green]\n")

        while self.running:
            try:
                # Wait for enough audio
                if not self.capture.has_audio():
                    time.sleep(0.1)
                    continue

                # Get audio chunk
                audio = self.capture.get_chunk()
                if audio is None:
                    continue

                # Transcribe
                text, confidence = self.transcriber.transcribe(audio)

                # Skip empty results
                if not text or not text.strip():
                    continue

                # Save to database
                transcript_id = save_transcript(
                    raw_text=text,
                    confidence=confidence,
                    duration=CHUNK_DURATION
                )
                self.transcript_count += 1

                # Display
                conf_color = "green" if confidence > -0.5 else "yellow" if confidence > -1.0 else "red"
                console.print(f"[dim]#{transcript_id}[/dim] [{conf_color}]●[/{conf_color}] {text}")

            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

        self.stop()

    def stop(self):
        """Stop the application."""
        self.running = False
        if self.capture:
            self.capture.stop()
        console.print(f"\n[blue]Session ended. Captured {self.transcript_count} segments.[/blue]")
        console.print("Run [bold]python cleaner.py[/bold] to clean transcripts with LLM.")
        console.print("Run [bold]python review.py[/bold] to browse your corpus.")


def main():
    app = Ears()

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        app.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Setup and run
    if app.setup():
        app.run()


if __name__ == "__main__":
    main()

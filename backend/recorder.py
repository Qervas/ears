"""Record system audio to file, then transcribe."""

import sounddevice as sd
import numpy as np
import wave
import time
import threading
from datetime import datetime
from pathlib import Path


class Recorder:
    """Records system audio to WAV files."""

    def __init__(self, output_dir: str = "recordings"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.recording = False
        self.frames = []
        self.sample_rate = None
        self.stream = None

    def _callback(self, indata, frames, time_info, status):
        if status:
            print(f"Status: {status}")
        if self.recording:
            self.frames.append(indata.copy())

    def start(self, device_id: int):
        """Start recording."""
        device_info = sd.query_devices(device_id)
        self.sample_rate = int(device_info['default_samplerate'])

        self.frames = []
        self.recording = True

        self.stream = sd.InputStream(
            device=device_id,
            samplerate=self.sample_rate,
            channels=2,
            dtype=np.float32,
            callback=self._callback
        )
        self.stream.start()
        print(f"Recording started (device {device_id}, {self.sample_rate}Hz)")

    def stop(self) -> str:
        """Stop recording and save to file. Returns filename."""
        self.recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        if not self.frames:
            print("No audio recorded!")
            return None

        # Combine all frames
        audio = np.concatenate(self.frames, axis=0)

        # Convert to mono
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.output_dir / f"recording_{timestamp}.wav"

        # Save as WAV
        audio_int16 = (audio * 32767).astype(np.int16)
        with wave.open(str(filename), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_int16.tobytes())

        duration = len(audio) / self.sample_rate
        print(f"Saved: {filename} ({duration:.1f} seconds)")
        return str(filename)


def transcribe_file(filepath: str):
    """Transcribe a WAV file."""
    from faster_whisper import WhisperModel
    from storage import save_transcript
    from config import WHISPER_MODEL, WHISPER_LANGUAGE, WHISPER_DEVICE
    import wave

    print(f"\nTranscribing: {filepath}")
    print("Loading model...")

    # Load model directly for full-file transcription
    model = WhisperModel(
        WHISPER_MODEL,
        device=WHISPER_DEVICE,
        compute_type="int8" if WHISPER_DEVICE == "cpu" else "float16"
    )

    # Load audio
    with wave.open(filepath, 'rb') as wf:
        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        audio_bytes = wf.readframes(n_frames)
        audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32767.0

    # Resample to 16kHz if needed
    if sample_rate != 16000:
        print(f"Resampling from {sample_rate}Hz to 16000Hz...")
        duration = len(audio) / sample_rate
        target_length = int(duration * 16000)
        indices = np.linspace(0, len(audio) - 1, target_length)
        audio = np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

    total_duration = len(audio) / 16000
    print(f"Audio length: {total_duration:.1f} seconds ({total_duration/60:.1f} minutes)")
    print("Transcribing entire file (this may take a while)...\n")

    # Transcribe the ENTIRE audio at once - faster-whisper handles chunking internally
    segments, info = model.transcribe(
        audio,
        language=WHISPER_LANGUAGE,
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=500,
            speech_pad_ms=200,
        ),
    )

    all_text = []
    segment_count = 0

    print("Time        | Text")
    print("-" * 70)

    for segment in segments:
        start_time = segment.start
        end_time = segment.end
        text = segment.text.strip()

        if text:
            segment_count += 1
            all_text.append(text)

            # Save each segment to database
            save_transcript(
                raw_text=text,
                confidence=segment.avg_logprob,
                duration=end_time - start_time
            )

            # Format timestamp
            start_str = f"{int(start_time//60):02d}:{start_time%60:05.2f}"
            end_str = f"{int(end_time//60):02d}:{end_time%60:05.2f}"
            print(f"[{start_str}-{end_str}] {text}")

    print("\n" + "=" * 70)
    print(f"TRANSCRIPTION COMPLETE: {segment_count} segments from {total_duration:.1f}s audio")
    print("=" * 70)
    print("\nFULL TEXT:")
    print("-" * 70)
    full_text = " ".join(all_text)
    print(full_text)
    print("-" * 70)
    print(f"\nWord count: {len(full_text.split())}")
    print(f"Saved to database: {segment_count} segments")

    # Also save full transcript to text file
    txt_path = filepath.replace('.wav', '.txt')
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(full_text)
    print(f"Saved transcript to: {txt_path}")

    return full_text


def list_recordings():
    """List all recordings."""
    recordings_dir = Path("recordings")
    if not recordings_dir.exists():
        print("No recordings directory found.")
        return []

    files = sorted(recordings_dir.glob("*.wav"))
    if not files:
        print("No recordings found.")
        return []

    print("\nRecordings:")
    for i, f in enumerate(files):
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  [{i}] {f.name} ({size_mb:.1f} MB)")

    return files


def main():
    import sys

    print("=" * 60)
    print("EARS - Record & Transcribe")
    print("=" * 60)

    if len(sys.argv) > 1:
        # Transcribe existing file
        filepath = sys.argv[1]
        if filepath == "--list":
            files = list_recordings()
            if files:
                print("\nTo transcribe: python recorder.py <filename>")
        else:
            transcribe_file(filepath)
        return

    # Record new audio
    print("\nAvailable input devices:")
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            print(f"  [{i}] {dev['name']}")

    print("\nEnter device ID (14=Stereo Mix, 17=PC Speaker):")
    device_id = int(input("> ").strip() or "17")

    recorder = Recorder()

    print("\nPress ENTER to start recording...")
    input()

    recorder.start(device_id)

    print("Recording... Press ENTER to stop.")
    input()

    filepath = recorder.stop()

    if filepath:
        print("\nTranscribe now? (y/n)")
        if input("> ").strip().lower() == 'y':
            transcribe_file(filepath)
        else:
            print(f"\nTo transcribe later: python recorder.py {filepath}")


if __name__ == "__main__":
    main()

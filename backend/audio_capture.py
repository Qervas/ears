"""Audio capture using WASAPI loopback (Windows system audio)."""

import sounddevice as sd
import numpy as np
from collections import deque
import threading
from config import SAMPLE_RATE


class AudioCapture:
    """Captures system audio using WASAPI loopback."""

    def __init__(self, chunk_seconds: float = 5.0):
        self.target_sample_rate = SAMPLE_RATE  # What Whisper needs (16kHz)
        self.device_sample_rate = None  # Will be set from device
        self.chunk_seconds = chunk_seconds
        self.chunk_samples = int(self.target_sample_rate * chunk_seconds)

        self._buffer = deque(maxlen=self.chunk_samples * 2)
        self._lock = threading.Lock()
        self._stream = None
        self._running = False
        self._resample_ratio = 1.0

    def _find_loopback_device(self) -> int:
        """Find the WASAPI loopback device for system audio."""
        devices = sd.query_devices()

        for i, dev in enumerate(devices):
            name = dev["name"].lower()
            if dev["max_input_channels"] > 0:
                if any(kw in name for kw in ["loopback", "stereo mix", "stereomix", "what u hear", "wave out"]):
                    print(f"Found loopback device: [{i}] {dev['name']}")
                    return i

        return None

    def list_devices(self):
        """Print available audio devices."""
        print("\nAvailable audio devices:")
        print("-" * 50)
        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            channels = f"in:{dev['max_input_channels']} out:{dev['max_output_channels']}"
            rate = dev.get('default_samplerate', 'N/A')
            print(f"  [{i}] {dev['name']} ({channels}, {rate}Hz)")
        print("-" * 50)

    def _resample(self, audio: np.ndarray, orig_rate: float, target_rate: float) -> np.ndarray:
        """Simple linear interpolation resampling."""
        if orig_rate == target_rate:
            return audio

        duration = len(audio) / orig_rate
        target_length = int(duration * target_rate)
        indices = np.linspace(0, len(audio) - 1, target_length)
        return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

    def _audio_callback(self, indata, frames, time, status):
        """Called for each audio block."""
        if status:
            print(f"Audio status: {status}")

        # Convert to mono if stereo
        if indata.shape[1] > 1:
            mono = np.mean(indata, axis=1)
        else:
            mono = indata[:, 0]

        # Resample to target rate if needed
        if self._resample_ratio != 1.0:
            mono = self._resample(mono, self.device_sample_rate, self.target_sample_rate)

        with self._lock:
            self._buffer.extend(mono)

    def start(self, device_id: int = None):
        """Start capturing audio."""
        if device_id is None:
            device_id = self._find_loopback_device()

        if device_id is None:
            print("\n⚠ No loopback device found automatically.")
            print("Please enable 'Stereo Mix' in Windows Sound settings, or")
            print("install VB-Cable (free virtual audio cable).")
            self.list_devices()
            return False

        try:
            # Get device's default sample rate
            device_info = sd.query_devices(device_id)
            self.device_sample_rate = int(device_info['default_samplerate'])
            self._resample_ratio = self.target_sample_rate / self.device_sample_rate

            print(f"Device sample rate: {self.device_sample_rate}Hz, resampling to {self.target_sample_rate}Hz")

            self._stream = sd.InputStream(
                device=device_id,
                samplerate=self.device_sample_rate,  # Use device's native rate
                channels=2,  # Capture stereo, convert to mono
                dtype=np.float32,
                callback=self._audio_callback,
                blocksize=int(self.device_sample_rate * 0.1),  # 100ms blocks
            )
            self._stream.start()
            self._running = True
            print(f"✓ Audio capture started (device: {device_id})")
            return True
        except Exception as e:
            print(f"✗ Failed to start audio capture: {e}")
            self.list_devices()
            return False

    def stop(self):
        """Stop capturing audio."""
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        print("✓ Audio capture stopped")

    def get_chunk(self) -> np.ndarray:
        """Get a chunk of audio for transcription. Returns None if not enough data."""
        with self._lock:
            if len(self._buffer) < self.chunk_samples:
                return None

            # Get chunk and clear buffer
            chunk = np.array(list(self._buffer)[:self.chunk_samples])
            # Keep some overlap for continuity
            overlap = self.chunk_samples // 4
            for _ in range(self.chunk_samples - overlap):
                if self._buffer:
                    self._buffer.popleft()

            return chunk.astype(np.float32)

    def has_audio(self) -> bool:
        """Check if there's enough audio for a chunk."""
        with self._lock:
            return len(self._buffer) >= self.chunk_samples


if __name__ == "__main__":
    # Test audio capture
    capture = AudioCapture(chunk_seconds=3)
    capture.list_devices()

    print("\nTo test, enter device ID (or press Enter to auto-detect):")
    device_input = input("> ").strip()
    device_id = int(device_input) if device_input else None

    if capture.start(device_id):
        print("Recording for 10 seconds... Play some audio!")
        import time
        time.sleep(10)

        chunk = capture.get_chunk()
        if chunk is not None:
            print(f"Got audio chunk: {len(chunk)} samples, max amplitude: {np.max(np.abs(chunk)):.4f}")
        else:
            print("No audio captured (was audio playing?)")

        capture.stop()

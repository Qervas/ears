"""Real-time transcription using faster-whisper."""

from faster_whisper import WhisperModel
import numpy as np
from config import WHISPER_MODEL, WHISPER_LANGUAGE, WHISPER_DEVICE, SAMPLE_RATE


class Transcriber:
    """Transcribes audio chunks using faster-whisper."""

    def __init__(self):
        print(f"Loading Whisper model '{WHISPER_MODEL}' on {WHISPER_DEVICE}...")
        self.model = WhisperModel(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type="float16" if WHISPER_DEVICE == "cuda" else "int8"
        )
        print("✓ Whisper model loaded")

    def transcribe(self, audio: np.ndarray) -> tuple[str, float]:
        """
        Transcribe an audio chunk.
        Returns (text, avg_confidence)
        """
        # faster-whisper expects float32 audio normalized to [-1, 1]
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Ensure proper range
        if np.max(np.abs(audio)) > 1.0:
            audio = audio / np.max(np.abs(audio))

        segments, info = self.model.transcribe(
            audio,
            language=WHISPER_LANGUAGE,
            beam_size=5,
            vad_filter=True,  # Filter out non-speech
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=200,
            ),
        )

        # Collect all segments
        texts = []
        confidences = []

        for segment in segments:
            texts.append(segment.text.strip())
            confidences.append(segment.avg_logprob)

        full_text = " ".join(texts)
        avg_confidence = np.mean(confidences) if confidences else 0.0

        return full_text, avg_confidence


if __name__ == "__main__":
    # Test with a simple audio array (silence)
    print("Testing transcriber initialization...")
    transcriber = Transcriber()

    # Create a short test audio (just silence)
    test_audio = np.zeros(SAMPLE_RATE * 2, dtype=np.float32)
    text, conf = transcriber.transcribe(test_audio)
    print(f"Test transcription (silence): '{text}' (confidence: {conf:.2f})")
    print("✓ Transcriber working")

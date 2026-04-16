"""
Speech-to-text using faster-whisper.

Model options (set in config.yaml):
  ivrit-ai/whisper-large-v2-tuned-ct2  — best Hebrew accuracy, downloads directly
  openai/whisper-large-v3              — excellent Hebrew, good fallback
  openai/whisper-medium                — faster, lower memory, decent Hebrew
"""

import numpy as np
from faster_whisper import WhisperModel


class Transcriber:
    def __init__(self, model_name: str = "openai/whisper-large-v3", language: str = "he"):
        print(f"Loading Whisper model '{model_name}'...")
        self._model = WhisperModel(model_name, device="cpu", compute_type="int8")
        self._language = language
        print("Model ready.")

    def transcribe(self, audio: np.ndarray) -> str:
        """
        Transcribe a float32 audio array sampled at 16kHz.
        Returns the transcribed text, or empty string if nothing detected.
        """
        segments, _ = self._model.transcribe(
            audio,
            language=self._language,
            beam_size=1,       # fastest
            vad_filter=True,   # built-in VAD filters out silence segments
            vad_parameters={"min_silence_duration_ms": 500},
        )
        return " ".join(s.text for s in segments).strip()

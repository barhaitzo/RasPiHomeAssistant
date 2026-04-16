"""
Voice pipeline: mic → VAD → Whisper → wake word check → parser → dispatch → TTS.
"""

import asyncio
import re
from difflib import SequenceMatcher
from typing import Callable, Awaitable

from .vad import record_command
from .transcriber import Transcriber
from .speaker import speak


def _fuzzy_find(text: str, wake_word: str, threshold: float = 0.75) -> int | None:
    """
    Find wake_word (or a close phonetic match) in text.
    Slides a word-level window and returns the end character position of the
    best match, or None if nothing exceeds the threshold.
    """
    # Exact match first
    m = re.search(re.escape(wake_word), text, re.IGNORECASE)
    if m:
        return m.end()

    # Fuzzy: slide a window of the same word count over the transcription
    ww_words = wake_word.split()
    text_words = text.split()
    n = len(ww_words)

    best_ratio, best_end = 0.0, None
    for i in range(max(1, len(text_words) - n + 1)):
        window = " ".join(text_words[i : i + n])
        ratio = SequenceMatcher(None, wake_word.lower(), window.lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            # find end position of the last matched word in original text
            last_word = text_words[i + n - 1]
            pos = text.lower().rfind(last_word.lower(), 0, len(text))
            best_end = pos + len(last_word) if pos != -1 else None

    return best_end if best_ratio >= threshold else None


def _strip_wake_word(text: str, wake_words: list[str]) -> str | None:
    """
    Check all wake word variants (with fuzzy matching).
    Returns the command text after the best match, or None if no variant matched.
    """
    best: tuple[int, str] | None = None  # (match_end, remainder)
    for word in wake_words:
        end = _fuzzy_find(text, word)
        if end is not None and (best is None or end > best[0]):
            best = (end, text[end:].strip(" ,،.!"))
    return best[1] if best is not None else None


class VoicePipeline:
    def __init__(
        self,
        transcriber: Transcriber,
        dispatch: Callable[[str], Awaitable[str]],
        energy_threshold: float = 0.02,
        wake_words: list[str] | None = None,
    ):
        self._transcriber = transcriber
        self._dispatch = dispatch          # async fn: text → Hebrew confirmation
        self._energy_threshold = energy_threshold
        self._wake_words = wake_words or []

    async def run(self) -> None:
        """
        Loop forever:
          listen → transcribe → (wake word check) → dispatch → speak confirmation
        """
        if self._wake_words:
            print(f'מאזין למילות הפעלה {self._wake_words}... (Ctrl+C לעצירה)')
        else:
            print("מאזין... (Ctrl+C לעצירה)")

        while True:
            try:
                audio = await record_command(energy_threshold=self._energy_threshold)
                if audio is None:
                    continue

                text = self._transcriber.transcribe(audio)
                if not text:
                    continue

                print(f"  שמעתי: {text}")

                if self._wake_words:
                    command_text = _strip_wake_word(text, self._wake_words)
                    if command_text is None:
                        print("  (ללא מילת הפעלה — מתעלם)")
                        continue
                    if not command_text:
                        await speak("כן?")
                        continue
                else:
                    command_text = text

                # Fire acknowledgment and dispatch in parallel:
                # "רגע" plays immediately while the AC call + TTS run behind it.
                ack_task = asyncio.create_task(speak("רגע"))
                dispatch_task = asyncio.create_task(self._dispatch(command_text))
                await ack_task
                response = await dispatch_task
                print(f"  → {response}")
                await speak(response)

            except KeyboardInterrupt:
                print("\nיוצא")
                break
            except Exception as e:
                print(f"  שגיאה: {e}")
                continue

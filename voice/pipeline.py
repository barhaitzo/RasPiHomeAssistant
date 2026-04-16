"""
Voice pipeline: mic → VAD → Whisper → wake word check → parser → dispatch → TTS.
"""

import asyncio
import re
from typing import Callable, Awaitable

from .vad import record_command
from .transcriber import Transcriber
from .speaker import speak


def _strip_wake_word(text: str, wake_words: list[str]) -> str | None:
    """
    Check all wake word variants. Return the command text after the first match,
    or None if none of the wake words are present.
    """
    best: tuple[int, str] | None = None  # (match_end, remainder)
    for word in wake_words:
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        match = pattern.search(text)
        if match and (best is None or match.end() > best[0]):
            best = (match.end(), text[match.end():].strip(" ,،.!"))
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

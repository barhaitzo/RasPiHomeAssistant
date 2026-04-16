"""
Voice pipeline: mic → VAD → Whisper → wake word check → parser → dispatch → TTS.
"""

import asyncio
import re
from typing import Callable, Awaitable

from .vad import record_command
from .transcriber import Transcriber
from .speaker import speak


def _strip_wake_word(text: str, wake_word: str) -> str | None:
    """
    Return the command text after the wake word, or None if the wake word
    isn't present. Matching is case-insensitive and ignores leading punctuation.
    """
    pattern = re.compile(re.escape(wake_word), re.IGNORECASE)
    match = pattern.search(text)
    if match is None:
        return None
    return text[match.end():].strip(" ,،.!")


class VoicePipeline:
    def __init__(
        self,
        transcriber: Transcriber,
        dispatch: Callable[[str], Awaitable[str]],
        energy_threshold: float = 0.02,
        wake_word: str | None = None,
    ):
        self._transcriber = transcriber
        self._dispatch = dispatch          # async fn: text → Hebrew confirmation
        self._energy_threshold = energy_threshold
        self._wake_word = wake_word

    async def run(self) -> None:
        """
        Loop forever:
          listen → transcribe → (wake word check) → dispatch → speak confirmation
        """
        if self._wake_word:
            print(f'מאזין למילת ההפעלה "{self._wake_word}"... (Ctrl+C לעצירה)')
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

                if self._wake_word:
                    command_text = _strip_wake_word(text, self._wake_word)
                    if command_text is None:
                        print("  (ללא מילת הפעלה — מתעלם)")
                        continue
                    if not command_text:
                        # wake word said alone — acknowledge and wait for next utterance
                        await speak("כן?")
                        continue
                else:
                    command_text = text

                response = await self._dispatch(command_text)
                print(f"  → {response}")
                await speak(response)

            except KeyboardInterrupt:
                print("\nיוצא")
                break
            except Exception as e:
                print(f"  שגיאה: {e}")
                continue

"""
Hebrew text-to-speech using edge-tts (Microsoft Neural TTS, free).

Voice: he-IL-AvriNeural (male) — swap to he-IL-HilaNeural for female.
Requires internet access.
"""

import asyncio
import os
import tempfile

import edge_tts
import pygame

VOICE = "he-IL-AvriNeural"

_mixer_initialized = False


def _ensure_mixer():
    global _mixer_initialized
    if not _mixer_initialized:
        pygame.mixer.init()
        _mixer_initialized = True


async def speak(text: str) -> None:
    """Generate Hebrew speech for `text` and play it through the speakers."""
    if not text:
        return

    # generate to a temp mp3 file
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tmp_path = f.name

    try:
        communicate = edge_tts.Communicate(text, voice=VOICE)
        await communicate.save(tmp_path)
        _ensure_mixer()
        pygame.mixer.music.load(tmp_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.05)
    finally:
        os.unlink(tmp_path)

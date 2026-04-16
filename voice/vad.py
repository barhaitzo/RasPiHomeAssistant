"""
Energy-based Voice Activity Detection.

Listens on the microphone, buffers audio once energy crosses the threshold,
and returns the recorded chunk when silence follows the speech.
"""

import asyncio
from collections import deque

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHUNK_DURATION = 0.03          # 30ms per chunk
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)
PRE_ROLL_CHUNKS = 10           # ~300ms buffered before trigger (captures word onset)
SILENCE_CHUNKS = 20            # ~600ms of silence ends recording
MAX_DURATION_S = 10            # hard cap to avoid runaway recording


async def record_command(
    energy_threshold: float = 0.02,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray | None:
    """
    Block until a voice command is captured.

    Returns a float32 numpy array at `sample_rate` Hz, or None if nothing
    was recorded before the max duration was hit.

    Tune `energy_threshold` if it triggers on background noise (raise it)
    or misses quiet speech (lower it). Typical range: 0.01 – 0.05.
    """
    loop = asyncio.get_running_loop()
    audio_buffer: list[np.ndarray] = []
    pre_roll: deque[np.ndarray] = deque(maxlen=PRE_ROLL_CHUNKS)
    recording = False
    silence_count = 0
    max_chunks = int(MAX_DURATION_S / CHUNK_DURATION)
    done = asyncio.Event()

    def _callback(indata, frames, time_info, status):
        nonlocal recording, silence_count
        chunk = indata[:, 0].copy()
        rms = float(np.sqrt(np.mean(chunk ** 2)))

        if not recording:
            pre_roll.append(chunk)
            if rms > energy_threshold:
                recording = True
                silence_count = 0
                audio_buffer.extend(list(pre_roll))
                audio_buffer.append(chunk)
        else:
            audio_buffer.append(chunk)
            if rms < energy_threshold:
                silence_count += 1
                if silence_count >= SILENCE_CHUNKS:
                    loop.call_soon_threadsafe(done.set)
            else:
                silence_count = 0

            if len(audio_buffer) >= max_chunks:
                loop.call_soon_threadsafe(done.set)

    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        blocksize=CHUNK_SIZE,
        callback=_callback,
    ):
        await done.wait()

    return np.concatenate(audio_buffer) if audio_buffer else None

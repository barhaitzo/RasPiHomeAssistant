"""
Hebrew text-to-speech using edge-tts (Microsoft Neural TTS, free).

Voice: he-IL-AvriNeural (male) — swap to he-IL-HilaNeural for female.
Requires internet access.

Playback uses av (already a faster-whisper dependency) to decode the MP3,
then sounddevice to play it — no pygame needed.
"""

import asyncio
import os
import tempfile

import av
import numpy as np
import sounddevice as sd
import edge_tts

VOICE = "he-IL-HilaNeural"  # female; swap to he-IL-AvriNeural for male


def _decode_mp3(path: str) -> tuple[np.ndarray, int]:
    """Decode an mp3 file to a float32 numpy array and its sample rate."""
    container = av.open(path)
    stream = container.streams.audio[0]
    sample_rate = stream.rate

    resampler = av.AudioResampler(format="fltp")
    frames = []
    for packet in container.demux(stream):
        for frame in packet.decode():
            for rf in resampler.resample(frame):
                frames.append(rf.to_ndarray())       # (channels, samples)
    for rf in resampler.resample(None):              # flush
        frames.append(rf.to_ndarray())

    container.close()

    if not frames:
        return np.zeros((1, 1), dtype=np.float32), sample_rate

    audio = np.concatenate(frames, axis=1).T         # (total_samples, channels)
    return audio.astype(np.float32), sample_rate


async def speak(text: str) -> None:
    """Generate Hebrew speech for `text` and play it through the speakers."""
    if not text:
        return

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tmp_path = f.name

    try:
        communicate = edge_tts.Communicate(text, voice=VOICE)
        await communicate.save(tmp_path)

        audio, sample_rate = await asyncio.get_running_loop().run_in_executor(
            None, _decode_mp3, tmp_path
        )

        await asyncio.get_running_loop().run_in_executor(
            None, lambda: (sd.play(audio, samplerate=sample_rate), sd.wait())
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass  # Windows may hold the handle briefly; OS cleans temp files

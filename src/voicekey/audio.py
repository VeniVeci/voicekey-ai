from __future__ import annotations

import tempfile
import threading
import time
import wave
from pathlib import Path


def cleanup_stale_recordings(max_age_seconds: int = 24 * 60 * 60) -> int:
    """Remove only VoiceKey-owned temporary WAV files older than the threshold."""
    removed = 0
    cutoff = time.time() - max_age_seconds
    for path in Path(tempfile.gettempdir()).glob("voicekey-*.wav"):
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


class AudioRecorder:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self._frames: list[bytes] = []
        self._stream = None
        self._lock = threading.Lock()
        self.started_at = 0.0

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    @property
    def duration(self) -> float:
        return max(0.0, time.monotonic() - self.started_at) if self.is_recording else 0.0

    def start(self) -> None:
        import sounddevice as sd

        if self.is_recording:
            return
        with self._lock:
            self._frames.clear()

        def callback(indata, frames, time_info, status):
            del frames, time_info
            if status:
                # PortAudio status is diagnostic only; retaining the usable frames is preferable.
                pass
            with self._lock:
                self._frames.append(bytes(indata))

        self._stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=1024,
            callback=callback,
        )
        self._stream.start()
        self.started_at = time.monotonic()

    def stop(self) -> tuple[Path, float]:
        if not self.is_recording:
            raise RuntimeError("Recorder is not running")
        duration = self.duration
        stream = self._stream
        self._stream = None
        stream.stop()
        stream.close()
        with self._lock:
            payload = b"".join(self._frames)
            self._frames.clear()
        handle = tempfile.NamedTemporaryFile(prefix="voicekey-", suffix=".wav", delete=False)
        path = Path(handle.name)
        handle.close()
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(payload)
        return path, duration

    def cancel(self) -> None:
        if self._stream is not None:
            stream = self._stream
            self._stream = None
            stream.abort()
            stream.close()
        with self._lock:
            self._frames.clear()

"""
microphone_input.py
===================
Live microphone capture with configurable backends.

WHY:
The voice gateway needs audio to transcribe. This module abstracts capture
cross-platform: ALSA (Linux/Jetson), PyAudio, and WAV file fallback.

FEATURES:
- Continuous streaming or one-shot recording
- Automatic silence detection and chunk splitting
- Configurable sample rate, bit depth, channels
- WAV file fallback for mock/demonstration
- Non-blocking queue for async STT pipeline

USAGE:
    from wrench_voice.microphone_input import MicrophoneInput

    mic = MicrophoneInput(backend="alsa", sample_rate=16000, channels=1)
    mic.calibrate(duration_sec=2.0)  # Set silence threshold

    # Streaming mode: voice gateway pulls from queue
    mic.start_streaming()
    chunk = mic.audio_queue.get(timeout=5.0)  # bytes of audio

    # One-shot mode
    wav_path = mic.record_to_file(duration_sec=5.0, out_path="/tmp/recording.wav")

BACKENDS:
- "alsa":  best on Linux/Jetson, direct hw interface, lowest latency
- "pyaudio": cross-platform via PyAudio library
- "wav":     reads a WAV file repeatedly (mock / test / benchmark)
- "none":    yields silence, for stress-testing STT without capture

DEPENDENCIES (optional, loaded lazily):
    sudo apt install python3-alsaaudio   # for alsaaudio
    pip install pyaudio                   # for pyaudio cross-platform

AUDIO FORMAT:
- PCM WAV, 16-bit signed integer
- Default 16 kHz mono (best for Whisper)
- Chunked at ~250ms intervals (4000 samples @ 16kHz)

SILENCE DETECTION:
- RMS energy computed per chunk
- Threshold calibrated to ambient noise floor + 6dB
- If chunk is below threshold for 1.5s, auto-stop one-shot recording
- VAD-like behavior without requiring heavy ML

WALKTHROUGH:
1. Instantiate with backend and format
2. (Optional) Calibrate silence threshold
3a. Stream: start_streaming(), pull from audio_queue
3b. Record: record_to_file() with silence auto-stop
4. Stop cleanly: stop_streaming() or close()
5. Release hardware resources

EXAMPLE — Minimal one-shot:
    mic = MicrophoneInput()
    filepath = mic.record_to_file(duration_sec=5.0)
    result = stt.transcribe(filepath)
    print(result.text)
    mic.close()

EXAMPLE — Streaming daemon:
    mic = MicrophoneInput()
    mic.calibrate()
    mic.start_streaming()

    while True:
        chunk = mic.audio_queue.get(timeout=2.0)
        if chunk is None:
            break
        voice_buffer.extend(chunk)
        if mic.is_speaking():
            continue
        # silence detected, process buffer
        text = stt.transcribe_bytes(voice_buffer)
        voice_buffer.clear()
        print(text)

EXAMPLE — Mock benchmark (no hardware):
    mic = MicrophoneInput(backend="wav", wav_source="sample.wav")
    for chunk in mic.stream_chunks():
        process(chunk)
"""

from __future__ import annotations

import os
import wave
import struct
import threading
import time
from pathlib import Path
from typing import Iterator, Optional

from pydantic import BaseModel


class MicConfig(BaseModel):
    """Immutable microphone configuration."""
    sample_rate: int = 16000      # Hz; Whisper prefers 16kHz
    channels: int = 1              # Mono
    bit_depth: int = 16            # 16-bit signed PCM
    chunk_ms: int = 250            # ms per chunk (16kHz → 4000 samples)
    device_index: int | None = None  # ALSA card index or None for default
    silence_threshold: float = 500.0  # RMS threshold after calibration
    silence_stop_sec: float = 1.5   # Auto-stop after this many sec of silence


class RecordingResult(BaseModel):
    """Output of a one-shot recording."""
    file_path: str
    duration_sec: float
    peak_rms: float
    silence_limited: bool   # True if stopped early by silence detection


class MicrophoneInput:
    """
    Live microphone capture with silence detection and queue-based streaming.
    """
    def __init__(
        self,
        backend: str = "alsa",          # "alsa" | "pyaudio" | "wav" | "none"
        wav_source: str | None = None,   # Required when backend="wav"
        config: MicConfig | None = None,
        mock_mode: bool = False,        # Alias for backend="none"
    ):
        if mock_mode:
            backend = "none"
        self.backend = backend
        self.config = config or MicConfig()
        self.wav_source = wav_source
        self._running = False
        self._stream_thread: threading.Thread | None = None
        self._silence_start: float | None = None
        self._latest_rms: float = 0.0
        self._is_speaking: bool = False

        # Thread-safe queue for streaming audio chunks
        self.audio_queue: "queue.Queue[bytes]" = queue.Queue(maxsize=100)

        # ALSA / PyAudio handles (lazy init)
        self._alsa_pcm: object | None = None
        self._pyaudio_instance: object | None = None
        self._pyaudio_stream: object | None = None
        self._wav_reader: wave.Wave_read | None = None

        if backend == "alsa":
            self._init_alsa()
        elif backend == "pyaudio":
            self._init_pyaudio()
        elif backend == "wav":
            self._init_wav()
        elif backend == "none":
            pass
        else:
            raise ValueError(f"Unknown microphone backend: {backend}")

    # ── Backend initializers ────────────────────────────────────────────

    def _init_alsa(self) -> None:
        """Load alsaaudio module and open default PCM capture."""
        try:
            import alsaaudio  # type: ignore
        except ImportError:
            raise RuntimeError(
                "alsaaudio not installed. Run: sudo apt install python3-alsaaudio"
            )
        card = self.config.device_index if self.config.device_index is not None else "default"
        fmt_map = {8: alsaaudio.PCM_FORMAT_S8, 16: alsaaudio.PCM_FORMAT_S16_LE}
        fmt = fmt_map.get(self.config.bit_depth, alsaaudio.PCM_FORMAT_S16_LE)
        self._alsa_pcm = alsaaudio.PCM(
            alsaaudio.PCM_CAPTURE,
            alsaaudio.PCM_NORMAL,
            device=f"hw:{card}" if isinstance(card, int) else card,
            channels=self.config.channels,
            rate=self.config.sample_rate,
            format=fmt,
            periodsize=self._chunk_samples(),
        )

    def _init_pyaudio(self) -> None:
        """Load PyAudio and open stream."""
        try:
            import pyaudio  # type: ignore
        except ImportError:
            raise RuntimeError(
                "pyaudio not installed. Run: pip install pyaudio"
            )
        self._pyaudio_instance = pyaudio.PyAudio()
        fmt = {8: pyaudio.paInt8, 16: pyaudio.paInt16}.get(
            self.config.bit_depth, pyaudio.paInt16
        )
        self._pyaudio_stream = self._pyaudio_instance.open(
            format=fmt,
            channels=self.config.channels,
            rate=self.config.sample_rate,
            input=True,
            frames_per_buffer=self._chunk_samples(),
            input_device_index=self.config.device_index,
        )

    def _init_wav(self) -> None:
        if not self.wav_source:
            raise ValueError("backend='wav' requires wav_source=path")
        p = Path(self.wav_source)
        if not p.exists():
            raise FileNotFoundError(f"WAV source not found: {p}")
        self._wav_reader = wave.open(str(p), "rb")

    # ── Helpers ─────────────────────────────────────────────────────────

    def _chunk_samples(self) -> int:
        return int(self.config.sample_rate * self.config.chunk_ms / 1000)

    def _rms(self, chunk: bytes) -> float:
        """Root-mean-square energy of 16-bit PCM chunk."""
        if self.config.bit_depth != 16:
            return 0.0
        n = len(chunk) // 2
        if n == 0:
            return 0.0
        # Unpack shorts efficiently
        shorts = struct.unpack(f"<{n}h", chunk[: n * 2])
        squares = sum(s * s for s in shorts)
        return (squares / n) ** 0.5

    def _read_chunk(self) -> bytes:
        """Read one chunk from active backend."""
        if self.backend == "alsa" and self._alsa_pcm:
            _, data = self._alsa_pcm.read()
            if not data:
                data = b"\x00" * (self._chunk_samples() * self.config.channels * self.config.bit_depth // 8)
            return data
        if self.backend == "pyaudio" and self._pyaudio_stream:
            return self._pyaudio_stream.read(self._chunk_samples(), exception_on_overflow=False)
        if self.backend == "wav" and self._wav_reader:
            frames = self._wav_reader.readframes(self._chunk_samples())
            if not frames:
                self._wav_reader.rewind()
                frames = self._wav_reader.readframes(self._chunk_samples())
            return frames
        if self.backend == "none":
            time.sleep(self.config.chunk_ms / 1000.0)
            return b"\x00" * (self._chunk_samples() * self.config.channels * self.config.bit_depth // 8)
        return b""

    # ── Calibration ───────────────────────────────────────────────────────

    def calibrate(self, duration_sec: float = 2.0) -> float:
        """
        Measure ambient RMS and set silence threshold.
        Call before streaming for accurate VAD.
        Returns the calibrated threshold.
        """
        if self.backend in ("none", "wav"):
            return self.config.silence_threshold

        samples = int(duration_sec * 1000 / self.config.chunk_ms)
        readings: list[float] = []
        for _ in range(samples):
            chunk = self._read_chunk()
            readings.append(self._rms(chunk))
            time.sleep(self.config.chunk_ms / 1000.0)
        avg = sum(readings) / len(readings)
        # Threshold = ambient floor + 6 dB (≈ ×2 RMS)
        self.config.silence_threshold = avg * 2.0 + 1.0
        return self.config.silence_threshold

    # ── Streaming API ─────────────────────────────────────────────────────

    def start_streaming(self) -> None:
        """Begin background thread feeding audio_queue."""
        self._running = True
        self._stream_thread = threading.Thread(target=self._stream_worker, daemon=True)
        self._stream_thread.start()

    def stop_streaming(self) -> None:
        """Stop background thread."""
        self._running = False
        if self._stream_thread:
            self._stream_thread.join(timeout=2.0)

    def _stream_worker(self) -> None:
        while self._running:
            chunk = self._read_chunk()
            self._latest_rms = self._rms(chunk)
            self._is_speaking = self._latest_rms > self.config.silence_threshold
            if self._is_speaking:
                self._silence_start = None
            else:
                if self._silence_start is None:
                    self._silence_start = time.time()
            # Non-blocking put; drop oldest if queue full
            try:
                self.audio_queue.put_nowait(chunk)
            except queue.Full:
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    pass
                self.audio_queue.put_nowait(chunk)

    def is_speaking(self) -> bool:
        """True if current chunk is above silence threshold."""
        return self._is_speaking

    def silence_duration(self) -> float:
        """Seconds since last speech ended."""
        if self._silence_start is None:
            return 0.0
        return time.time() - self._silence_start

    # ── One-shot recording ──────────────────────────────────────────────

    def record_to_file(
        self,
        duration_sec: float | None = None,
        out_path: str | None = None,
        silence_limited: bool = True,
    ) -> RecordingResult:
        """
        Record to WAV file.
        If silence_limited=True and silence_stop_sec exceeded, stop early.
        """
        if out_path is None:
            out_path = f"/tmp/wrench_rec_{int(time.time())}.wav"
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)

        peak = 0.0
        chunks: list[bytes] = []
        start = time.time()
        silence_accum = 0.0

        while True:
            chunk = self._read_chunk()
            r = self._rms(chunk)
            peak = max(peak, r)
            chunks.append(chunk)

            elapsed = time.time() - start
            if r <= self.config.silence_threshold:
                silence_accum += self.config.chunk_ms / 1000.0
            else:
                silence_accum = 0.0

            # Stop conditions
            if duration_sec and elapsed >= duration_sec:
                break
            if silence_limited and silence_accum >= self.config.silence_stop_sec:
                break
            if duration_sec is None and silence_limited and silence_accum >= self.config.silence_stop_sec:
                break

        # Write WAV
        total_frames = sum(len(c) for c in chunks) // (self.config.bit_depth // 8) // self.config.channels
        with wave.open(str(p), "wb") as wf:
            wf.setnchannels(self.config.channels)
            wf.setsampwidth(self.config.bit_depth // 8)
            wf.setframerate(self.config.sample_rate)
            wf.writeframes(b"".join(chunks))

        return RecordingResult(
            file_path=str(p),
            duration_sec=time.time() - start,
            peak_rms=peak,
            silence_limited=silence_limited and silence_accum >= self.config.silence_stop_sec,
        )

    # ── Iterator (for simple loops) ───────────────────────────────────────

    def stream_chunks(self) -> Iterator[bytes]:
        """Yield audio chunks until stopped."""
        while self._running or self.backend == "wav":
            yield self._read_chunk()

    # ── Cleanup ───────────────────────────────────────────────────────────

    def close(self) -> None:
        """Release all hardware and file handles."""
        self.stop_streaming()
        if self._alsa_pcm:
            self._alsa_pcm.close()
            self._alsa_pcm = None
        if self._pyaudio_stream:
            self._pyaudio_stream.stop_stream()
            self._pyaudio_stream.close()
            self._pyaudio_stream = None
        if self._pyaudio_instance:
            self._pyaudio_instance.terminate()
            self._pyaudio_instance = None
        if self._wav_reader:
            self._wav_reader.close()
            self._wav_reader = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Lazy import for queue (avoid at module level on non-threaded envs)
import queue  # noqa: E402


if __name__ == "__main__":
    # Demo: one-shot recording with ALSA
    mic = MicrophoneInput(backend="none", mock_mode=True)
    result = mic.record_to_file(duration_sec=3.0, silence_limited=False)
    print(f"Saved to {result.file_path}: {result.duration_sec:.2f}s, peak RMS={result.peak_rms:.1f}")
    mic.close()

"""
voice_gateway.py
================
Always-hot voice processing gateway: STT + TTS kept in RAM for instant response.

WHY:
A mechanic can't wait 3 seconds for a model to load while holding a greasy wrench.
This module loads the STT model ONCE at startup and keeps it resident.
Incoming audio goes straight to transcription without cold-start delay.

ARCHITECTURE:
- Loads faster-whisper model at startup (once, stays in RAM)
- Queues audio chunks from mic or file
- Returns transcription in ~200–500ms after audio ends
- TTS backend pre-loaded (coqui/piper/os-native)
- Simple queue-based interface: other modules push audio, pop text
- Can run as background thread or standalone process

BACKENDS:
- STT: faster-whisper (default), openai-whisper (fallback), mock
- TTS: piper-tts (local, fast), coqui-tts (quality), pyttsx3 (cross-platform mock)

CONFIG:
    ~/.config/wrench-voice/voice.yml or env vars:
    WRENCH_STT_BACKEND=whisper  # faster-whisper|openai-whisper|mock
    WRENCH_TTS_BACKEND=piper  # piper|coqui|pyttsx3|mock
    WRENCH_VOICE_DEVICE=hw:1,0  # ALSA device for mic
"""

from __future__ import annotations

import io
import json
import os
import queue
import threading
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class TranscriptionResult:
    text: str
    confidence: float
    language: str = "en"
    segments: list[dict[str, Any]] = field(default_factory=list)
    processing_time_ms: float = 0.0


@dataclass
class TTSResult:
    audio_bytes: bytes | None
    duration_sec: float
    sample_rate: int = 22050


class VoiceGateway:
    """
    Hot-resident voice gateway for wrench-voice.

    Usage:
        gateway = VoiceGateway(stt_backend="faster-whisper", tts_backend="piper")
        gateway.warmup()  # Load models NOW (at startup)

        # In the main loop:
        result = gateway.transcribe_audio("/tmp/recording.wav")
        print(result.text)

        # TTS:
        tts = gateway.synthesize("Thermostat replacement. Two hundred forty dollars.")
        # Play tts.audio_bytes via speaker

        # Daemon mode:
        gateway.start_daemon()
        # Other threads call gateway.push_audio_chunk(data)
        text = gateway.pop_transcription()
    """

    SUPPORTED_STT = {"faster-whisper", "openai-whisper", "mock"}
    SUPPORTED_TTS = {"piper", "coqui", "pyttsx3", "mock"}

    def __init__(
        self,
        stt_backend: str = "faster-whisper",
        tts_backend: str = "piper",
        model_size: str = "base.en",
        device: str = "cpu",
        cache_dir: str | None = None,
        mock_mode: bool = False,
    ) -> None:
        self.stt_backend = stt_backend if not mock_mode else "mock"
        self.tts_backend = tts_backend if not mock_mode else "mock"
        self.model_size = model_size
        self.device = device
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "wrench-voice" / "voice_models"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Model handles — populated by warmup()
        self._stt_model: Any = None
        self._tts_model: Any = None
        self._warm: bool = False

        # Thread-safe queues for daemon mode
        self._audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=32)
        self._text_queue: queue.Queue[TranscriptionResult] = queue.Queue(maxsize=32)
        self._daemon_running = False
        self._daemon_thread: threading.Thread | None = None

    # ─── Warmup / Model Loading ────────────────────────────────────────────────────

    def warmup(self) -> dict[str, Any]:
        """Preload STT and TTS models. Call once at startup. Takes 5–20s."""
        results: dict[str, Any] = {}
        # STT warmup
        if self.stt_backend == "faster-whisper":
            results["stt"] = self._warmup_faster_whisper()
        elif self.stt_backend == "openai-whisper":
            results["stt"] = self._warmup_openai_whisper()
        else:
            results["stt"] = {"status": "mock", "loaded": True}
            self._stt_model = "mock"

        # TTS warmup
        if self.tts_backend == "piper":
            results["tts"] = self._warmup_piper()
        elif self.tts_backend == "coqui":
            results["tts"] = self._warmup_coqui()
        elif self.tts_backend == "pyttsx3":
            results["tts"] = self._warmup_pyttsx3()
        else:
            results["tts"] = {"status": "mock", "loaded": True}
            self._tts_model = "mock"

        self._warm = True
        return results

    def is_warm(self) -> bool:
        return self._warm

    # ─── STT: Faster-Whisper ───────────────────────────────────────────────────────

    def _warmup_faster_whisper(self) -> dict[str, Any]:
        try:
            # Lazy import — heavy dependency
            from faster_whisper import WhisperModel  # type: ignore[import-not-found]

            model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type="int8" if self.device == "cpu" else "float16",
                download_root=str(self.cache_dir / "faster-whisper"),
            )
            self._stt_model = model
            return {"status": "loaded", "backend": "faster-whisper", "model": self.model_size, "device": self.device}
        except ImportError:
            return {"status": "error", "reason": "faster-whisper not installed. pip install faster-whisper"}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def _warmup_openai_whisper(self) -> dict[str, Any]:
        try:
            import whisper  # type: ignore[import-not-found]

            model = whisper.load_model(self.model_size, download_root=str(self.cache_dir / "whisper"))
            self._stt_model = model
            return {"status": "loaded", "backend": "openai-whisper", "model": self.model_size}
        except ImportError:
            return {"status": "error", "reason": "openai-whisper not installed. pip install openai-whisper"}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def transcribe_audio(self, wav_path: str | bytes) -> TranscriptionResult:
        """Transcribe audio file or raw WAV bytes. Fast when warm."""
        import time
        t0 = time.perf_counter()

        if self._stt_model == "mock":
            import random
            mocks = [
                "overheating at idle",
                "knocking sound under acceleration",
                "rough idle when cold",
                "won't start, cranks but no fire",
                "oil leak from the front of the engine",
                "check engine light came on yesterday",
            ]
            text = random.choice(mocks)
            return TranscriptionResult(text=text, confidence=0.92, processing_time_ms=50.0)

        if isinstance(wav_path, str):
            audio_input = wav_path
        else:
            # Write bytes to temp file for faster-whisper
            tmp = self.cache_dir / "temp_recording.wav"
            tmp.write_bytes(wav_path)
            audio_input = str(tmp)

        if self.stt_backend == "faster-whisper":
            return self._transcribe_faster(audio_input, t0)
        elif self.stt_backend == "openai-whisper":
            return self._transcribe_openai(audio_input, t0)

        return TranscriptionResult(text="", confidence=0.0, processing_time_ms=0.0)

    def _transcribe_faster(self, wav_path: str, t0: float) -> TranscriptionResult:
        import time
        model = self._stt_model
        segments, info = model.transcribe(wav_path, beam_size=5, language="en", condition_on_previous_text=False)
        text = " ".join(seg.text.strip() for seg in segments)
        elapsed = (time.perf_counter() - t0) * 1000
        return TranscriptionResult(
            text=text,
            confidence=info.language_probability if hasattr(info, "language_probability") else 0.85,
            language=info.language if hasattr(info, "language") else "en",
            segments=[{"start": seg.start, "end": seg.end, "text": seg.text} for seg in segments],
            processing_time_ms=elapsed,
        )

    def _transcribe_openai(self, wav_path: str, t0: float) -> TranscriptionResult:
        import time
        import numpy as np
        model = self._stt_model
        result = model.transcribe(wav_path, fp16=(self.device != "cpu"))
        elapsed = (time.perf_counter() - t0) * 1000
        return TranscriptionResult(
            text=result["text"],
            confidence=0.85,
            language=result.get("language", "en"),
            segments=result.get("segments", []),
            processing_time_ms=elapsed,
        )

    # ─── TTS: Piper ─────────────────────────────────────────────────────────────────

    def _warmup_piper(self) -> dict[str, Any]:
        try:
            from piper.voice import PiperVoice  # type: ignore[import-not-found]
            # Piper loads model on first synthesis — no explicit warmup needed
            self._tts_model = "piper_ready"
            return {"status": "ready", "backend": "piper", "note": "Model loads on first synth call"}
        except ImportError:
            return {"status": "error", "reason": "piper-tts not installed"}

    def _warmup_coqui(self) -> dict[str, Any]:
        try:
            from TTS.api import TTS  # type: ignore[import-not-found]
            tts = TTS("tts_models/en/ljspeech/tacotron2-DDC")
            self._tts_model = tts
            return {"status": "loaded", "backend": "coqui"}
        except ImportError:
            return {"status": "error", "reason": "coqui-tts not installed"}

    def _warmup_pyttsx3(self) -> dict[str, Any]:
        try:
            import pyttsx3  # type: ignore[import-not-found]
            engine = pyttsx3.init()
            self._tts_model = engine
            return {"status": "loaded", "backend": "pyttsx3"}
        except ImportError:
            return {"status": "error", "reason": "pyttsx3 not installed"}

    def synthesize(self, text: str) -> TTSResult:
        """Convert text to speech audio. Fast when warm."""
        if self._tts_model == "mock":
            return TTSResult(audio_bytes=None, duration_sec=len(text.split()) * 0.4, sample_rate=22050)

        if self.tts_backend == "piper":
            return self._synth_piper(text)
        elif self.tts_backend == "coqui":
            return self._synth_coqui(text)
        elif self.tts_backend == "pyttsx3":
            return self._synth_pyttsx3(text)

        return TTSResult(audio_bytes=None, duration_sec=0.0)

    def _synth_piper(self, text: str) -> TTSResult:
        import subprocess
        import tempfile
        # Piper CLI: echo text | piper --model en_US-lessac-medium.onnx --output_file out.wav
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            out_path = f.name
        try:
            proc = subprocess.run(
                ["piper", "--model", "en_US-lessac-medium.onnx", "--output_file", out_path],
                input=text.encode(),
                capture_output=True,
                timeout=10,
            )
            if proc.returncode == 0:
                audio = Path(out_path).read_bytes()
                # Rough duration estimate from file size (mono 16-bit 22050Hz ~ 44100 bytes/sec)
                duration = len(audio) / 44100.0
                return TTSResult(audio_bytes=audio, duration_sec=duration, sample_rate=22050)
            else:
                return TTSResult(audio_bytes=None, duration_sec=0.0)
        finally:
            Path(out_path).unlink(missing_ok=True)

    def _synth_coqui(self, text: str) -> TTSResult:
        import tempfile
        tts = self._tts_model
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            out_path = f.name
        tts.tts_to_file(text=text, file_path=out_path)
        audio = Path(out_path).read_bytes()
        duration = len(audio) / 44100.0
        Path(out_path).unlink(missing_ok=True)
        return TTSResult(audio_bytes=audio, duration_sec=duration, sample_rate=22050)

    def _synth_pyttsx3(self, text: str) -> TTSResult:
        import tempfile
        engine = self._tts_model
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            out_path = f.name
        engine.save_to_file(text, out_path)
        engine.runAndWait()
        audio = Path(out_path).read_bytes()
        duration = len(audio) / 44100.0
        Path(out_path).unlink(missing_ok=True)
        return TTSResult(audio_bytes=audio, duration_sec=duration, sample_rate=22050)

    # ─── Daemon Mode ───────────────────────────────────────────────────────────────

    def start_daemon(self, audio_source: Callable[[], bytes] | None = None) -> None:
        """
        Start background thread that continuously pulls audio and pushes transcriptions.
        audio_source: callable that returns raw PCM/WAV bytes (e.g. from microphone)
        """
        self._daemon_running = True
        self._daemon_thread = threading.Thread(target=self._daemon_loop, args=(audio_source,), daemon=True)
        self._daemon_thread.start()

    def stop_daemon(self) -> None:
        self._daemon_running = False
        if self._daemon_thread:
            self._daemon_thread.join(timeout=2.0)

    def _daemon_loop(self, audio_source: Callable[[], bytes] | None) -> None:
        import time
        while self._daemon_running:
            # Priority: explicit queue items first
            try:
                chunk = self._audio_queue.get(timeout=0.05)
            except queue.Empty:
                if audio_source:
                    chunk = audio_source()
                else:
                    time.sleep(0.05)
                    continue
            if chunk:
                result = self.transcribe_audio(chunk)
                self._text_queue.put(result, block=False)

    def push_audio(self, wav_bytes: bytes) -> None:
        """Push raw audio for transcription (used by external threads)."""
        self._audio_queue.put(wav_bytes, block=False)

    def pop_transcription(self, timeout: float = 1.0) -> TranscriptionResult | None:
        try:
            return self._text_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    # ─── Status ──────────────────────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        return {
            "stt_backend": self.stt_backend,
            "tts_backend": self.tts_backend,
            "warm": self._warm,
            "stt_loaded": self._stt_model is not None,
            "tts_loaded": self._tts_model is not None,
            "daemon_running": self._daemon_running,
            "cache_dir": str(self.cache_dir),
        }

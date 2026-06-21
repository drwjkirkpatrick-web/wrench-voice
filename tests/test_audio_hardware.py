"""
Tests for audio and hardware modules: microphone_input, barcode_scanner, audio_effects.

All tests are hermetic — no real audio hardware or barcode scanner needed.
"""

import pytest


class TestMicrophoneInput:
    def test_mock_record(self):
        from wrench_voice.microphone_input import MicrophoneInput
        mic = MicrophoneInput(backend="none", mock_mode=True)
        result = mic.record_to_file(duration_sec=1.0, silence_limited=False)
        assert result.duration_sec >= 0.9
        assert result.file_path.endswith(".wav")
        mic.close()

    def test_mock_stream(self):
        from wrench_voice.microphone_input import MicrophoneInput
        mic = MicrophoneInput(backend="none")
        mic.start_streaming()
        import time
        time.sleep(0.3)
        assert not mic.audio_queue.empty()
        mic.stop_streaming()
        mic.close()

    def test_wav_backend(self):
        import tempfile, wave, struct, io
        sr = 16000
        data = b"".join(struct.pack("<h", int(5000 * (1 if i % 50 < 25 else -1))) for i in range(sr))
        bio = io.BytesIO()
        with wave.open(bio, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(data)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(bio.getvalue())
        tmp.close()
        from wrench_voice.microphone_input import MicrophoneInput
        mic = MicrophoneInput(backend="wav", wav_source=tmp.name)
        result = mic.record_to_file(duration_sec=0.5, silence_limited=False)
        assert result.duration_sec >= 0.4
        import os
        os.unlink(tmp.name)
        mic.close()


class TestBarcodeScanner:
    def test_mock_scan(self):
        from wrench_voice.barcode_scanner import BarcodeScanner
        scanner = BarcodeScanner(backend="mock", mock_barcodes=["012345678901", "QR-TEST"])
        scans = list(scanner.listen())
        assert len(scans) == 2
        assert scans[0][0] == "012345678901"

    def test_manual_mode(self):
        from wrench_voice.barcode_scanner import BarcodeScanner
        scanner = BarcodeScanner(backend="manual")
        assert scanner.backend == "manual"

    def test_inventory_lookup_placeholder(self):
        from wrench_voice.barcode_scanner import BarcodeScanner
        scanner = BarcodeScanner(backend="mock")
        result = scanner.lookup_inventory("unknown-barcode")
        assert result.found is False
        assert result.barcode == "unknown-barcode"


class TestAudioEffects:
    def test_process_synthetic(self):
        import numpy as np, wave, io
        sr = 22050
        t = np.linspace(0, 0.5, int(sr * 0.5))
        sig = np.sin(2 * np.pi * 440 * t) * 0.3
        bio = io.BytesIO()
        with wave.open(bio, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes((sig * 32767).astype(np.int16).tobytes())
        raw = bio.getvalue()
        from wrench_voice.audio_effects import AudioEffects, AudioEffectsConfig
        fx = AudioEffects(AudioEffectsConfig(profile="garage", target_lufs=-16.0))
        processed = fx.process(raw)
        assert len(processed) > 0
        before = fx.measure_loudness(raw)
        after = fx.measure_loudness(processed)
        assert after != before

    def test_measure_loudness(self):
        import numpy as np, wave, io
        sr = 22050
        t = np.linspace(0, 0.3, int(sr * 0.3))
        sig = np.sin(2 * np.pi * 440 * t) * 0.5
        bio = io.BytesIO()
        with wave.open(bio, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes((sig * 32767).astype(np.int16).tobytes())
        from wrench_voice.audio_effects import AudioEffects
        fx = AudioEffects()
        lufs = fx.measure_loudness(bio.getvalue())
        assert lufs < 0

    def test_room_profiles(self):
        import numpy as np, wave, io
        sr = 22050
        t = np.linspace(0, 0.2, int(sr * 0.2))
        sig = np.sin(2 * np.pi * 440 * t) * 0.3
        bio = io.BytesIO()
        with wave.open(bio, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes((sig * 32767).astype(np.int16).tobytes())
        raw = bio.getvalue()
        from wrench_voice.audio_effects import AudioEffects, AudioEffectsConfig
        for profile in ["garage", "office", "outdoor", "headphones", "flat"]:
            fx = AudioEffects(AudioEffectsConfig(profile=profile))
            out = fx.process(raw)
            assert len(out) > 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])

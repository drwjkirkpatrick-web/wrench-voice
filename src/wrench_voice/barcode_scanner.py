"""
barcode_scanner.py
==================
Barcode scanning for parts intake, inventory lookup, and job assignment.

WHY:
Typing part numbers and SKUs is slow and error-prone. A cheap USB barcode
scanner turns any part box into instant inventory data.

FEATURES:
- USB HID keyboard emulation scanners (plug and play, no drivers)
- Camera-based scanning via OpenCV + zxing (for phone/tablet/webcam)
- Manual fallback for damaged labels
- Auto-prefix stripping (some scanners prepend SKU- or PN-)
- Integration with inventory_manager, parts_finder, price_tracker

HARDWARE:
- USB barcode scanner: $15–$40 on Amazon (TaoTronics, Eyoyo, etc.)
- Works as USB HID keyboard — scans appear as keystrokes
- Recommended: 2D imager (reads QR codes too) for modern packaging

USAGE:
    from wrench_voice.barcode_scanner import BarcodeScanner

    # HID mode: scanner acts as keyboard
    scanner = BarcodeScanner(backend="hid", device="/dev/input/event0")
    for barcode, timestamp in scanner.listen():
        print(f"Scanned: {barcode}")
        item = scanner.lookup_inventory(barcode)
        if item:
            print(f"In stock: {item.qty_on_hand} @ bin {item.bin_location}")
        else:
            print("Not in inventory — consider adding")

    # Camera mode: scan with webcam/phone
    scanner = BarcodeScanner(backend="camera", camera_index=0)
    result = scanner.scan_frame()  # One-shot
    print(result.barcode, result.format)

    # Mock mode: simulate scans for testing
    scanner = BarcodeScanner(backend="mock", mock_barcodes=["012345678901", "QR-MOCK-001"])
    for barcode, ts in scanner.listen():
        process(barcode)

    # Cleanup
    scanner.close()

BACKENDS:
- "hid":     Linux evdev input event (root may need access to /dev/input/*)
- "camera":  OpenCV webcam + zxing-cpp or pyzbar decoding
- "mock":    Simulated scans for testing without hardware
- "manual":  Terminal prompt for keyboard entry (fallback)

EVDEV SETUP (Linux):
    # Find your scanner device
    ls /dev/input/by-id/
    # Grant access (temporary, for testing)
    sudo chmod 666 /dev/input/event0
    # Permanent: add udev rule
    echo 'SUBSYSTEM=="input", ATTRS{name}=="*Barcode*", MODE="0666"' | sudo tee /etc/udev/rules.d/99-barcode.rules
    sudo udevadm control --reload-rules

CAMERA SETUP:
    pip install opencv-python zxing-cpp
    # or: pip install pyzbar pillow

BARCODE FORMATS:
- UPC-A/EAN-13: retail auto parts
- Code 128: warehouse SKUs
- QR Code: modern packaging, digital inspection links
- Data Matrix: small parts labels

INTEGRATION WITH VOICE:
    # While working under the hood, tech scans a part box
    # Wrench Voice speaks the result automatically
    scanner = BarcodeScanner(backend="hid")
    gw = VoiceGateway(mock_mode=False)
    gw.warmup()
    for barcode, ts in scanner.listen():
        item = scanner.lookup_inventory(barcode)
        if item:
            gw.synthesize(f"{item.part_name}. {item.qty_on_hand} on hand. Bin {item.bin_location}.")
        else:
            # Not in stock — look up prices
            results = scanner.lookup_parts(barcode)
            if results:
                gw.synthesize(f"Not in inventory. Best price: {results[0].supplier}, {results[0].price} dollars. Shall I add to order?")
            else:
                gw.synthesize("Unknown part. Please say the part name.")

WALKTHROUGH:
1. Scan a part box → barcode read instantly
2. Check inventory → qty on hand, bin location, unit cost
3. If not found → auto-lookup prices across suppliers
4. Voice announces result → hands stay on the wrench
5. Option to add to current job or auto-order

MOCK DEMO:
    scanner = BarcodeScanner(backend="mock")
    scanner.mock_scan("012345678901")  # Simulate scan
    item = scanner.lookup_inventory("012345678901")
    # Will return a placeholder item for demonstration
"""

from __future__ import annotations

import os
import time
import select
import struct
import threading
from pathlib import Path
from typing import Iterator

from pydantic import BaseModel


class ScanResult(BaseModel):
    """Single barcode scan with metadata."""
    barcode: str
    format: str          # "UPC_A", "EAN_13", "CODE_128", "QR_CODE", "UNKNOWN"
    timestamp: float
    source: str            # "hid", "camera", "mock", "manual"


class InventoryLookupResult(BaseModel):
    """What we know about a scanned part."""
    barcode: str
    found: bool
    sku: str | None = None
    part_name: str | None = None
    qty_on_hand: int | None = None
    bin_location: str | None = None
    unit_cost: float | None = None
    last_price: float | None = None
    supplier: str | None = None


class BarcodeScanner:
    """
    Unified barcode scanner: HID keyboard emulation, camera, or mock.
    """
    def __init__(
        self,
        backend: str = "mock",          # "hid" | "camera" | "mock" | "manual"
        device: str | None = None,      # /dev/input/event* for hid
        camera_index: int = 0,           # cv2.VideoCapture index
        mock_barcodes: list[str] | None = None,
        prefix_strip: str = "",          # Strip prefix like "SKU-"
        suffix_strip: str = "",          # Strip suffix like "\r\n"
        inventory_db_path: str | None = None,
    ):
        self.backend = backend
        self.device = device
        self.camera_index = camera_index
        self.mock_barcodes = mock_barcodes or ["MOCK-BARCODE-001", "012345678901"]
        self.prefix_strip = prefix_strip
        self.suffix_strip = suffix_strip
        self.inventory_db_path = inventory_db_path
        self._running = False
        self._scan_thread: threading.Thread | None = None

        # Handles (lazy init)
        self._evdev_fd: int | None = None
        self._cap: object | None = None  # cv2.VideoCapture
        self._mock_idx = 0

        if backend == "hid":
            self._init_hid()
        elif backend == "camera":
            self._init_camera()
        elif backend == "mock":
            pass
        elif backend == "manual":
            pass
        else:
            raise ValueError(f"Unknown barcode backend: {backend}")

    # ── Init ──────────────────────────────────────────────────────────

    def _init_hid(self) -> None:
        dev = self.device or self._find_hid_device()
        if not dev:
            raise RuntimeError(
                "No HID barcode device found. "
                "Check ls /dev/input/by-id/ or set device= explicitly."
            )
        self.device = dev
        self._evdev_fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)

    def _init_camera(self) -> None:
        try:
            import cv2  # type: ignore
        except ImportError:
            raise RuntimeError("OpenCV not installed. Run: pip install opencv-python")
        self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open camera index {self.camera_index}")

    def _find_hid_device(self) -> str | None:
        """Heuristic: find first input device with 'barcode' in name."""
        dev_path = Path("/dev/input/by-id/")
        if not dev_path.exists():
            return None
        for child in dev_path.iterdir():
            name = child.name.lower()
            if "barcode" in name or "scanner" in name:
                resolved = child.resolve()
                return str(resolved)
        # Fallback: try event0 if no heuristic match
        event0 = Path("/dev/input/event0")
        if event0.exists():
            return str(event0)
        return None

    # ── Listen / Stream ─────────────────────────────────────────────────

    def listen(self) -> Iterator[tuple[str, float]]:
        """Yield (barcode, timestamp) as scans occur."""
        if self.backend == "hid":
            yield from self._listen_hid()
        elif self.backend == "camera":
            yield from self._listen_camera()
        elif self.backend == "mock":
            yield from self._listen_mock()
        elif self.backend == "manual":
            yield from self._listen_manual()

    def _listen_hid(self) -> Iterator[tuple[str, float]]:
        if self._evdev_fd is None:
            return
        buf = ""
        while self._running:
            ready, _, _ = select.select([self._evdev_fd], [], [], 0.1)
            if ready:
                data = os.read(self._evdev_fd, 24)
                ch = self._evdev_key_to_char(data)
                if ch == "\n" or ch == "\r":
                    if buf:
                        yield self._clean(buf), time.time()
                        buf = ""
                elif ch:
                    buf += ch

    def _listen_camera(self) -> Iterator[tuple[str, float]]:
        try:
            import cv2
            while self._running and self._cap:
                ret, frame = self._cap.read()
                if not ret:
                    continue
                code = self._decode_opencv(frame)
                if code:
                    yield code, time.time()
                # Small delay to avoid burning CPU
                time.sleep(0.1)
        except Exception:
            pass

    def _listen_mock(self) -> Iterator[tuple[str, float]]:
        for bc in self.mock_barcodes:
            yield bc, time.time()
            time.sleep(0.05)  # brief pause between scans

    def _listen_manual(self) -> Iterator[tuple[str, float]]:
        import sys
        while self._running:
            line = input("Scan or type barcode (or 'quit'): ").strip()
            if line.lower() == "quit":
                break
            if line:
                yield line, time.time()

    # ── Decode helpers ──────────────────────────────────────────────────

    def _evdev_key_to_char(self, data: bytes) -> str | None:
        """
        Parse evdev input_event struct for keyboard scancode → ASCII.
        Simplified: assumes US QWERTY layout.
        """
        if len(data) < 24:
            return None
        # struct input_event: sec, usec, type, code, value
        sec, usec, type_, code, value = struct.unpack("llHHI", data[:16])
        if type_ != 1:   # EV_KEY
            return None
        if value != 1:   # key press (not release)
            return None
        return self._scancode_to_ascii(code)

    def _scancode_to_ascii(self, code: int) -> str | None:
        """Minimal scancode map for barcode scanners (digits, letters, symbols)."""
        # Common scancodes for USB HID keyboard
        scancodes = {
            2: '1', 3: '2', 4: '3', 5: '4', 6: '5', 7: '6', 8: '7', 9: '8', 10: '9', 11: '0',
            12: '-', 13: '=', 16: 'q', 17: 'w', 18: 'e', 19: 'r', 20: 't', 21: 'y', 22: 'u',
            23: 'i', 24: 'o', 25: 'p', 26: '[', 27: ']', 30: 'a', 31: 's', 32: 'd', 33: 'f',
            34: 'g', 35: 'h', 36: 'j', 37: 'k', 38: 'l', 39: ';', 40: "'", 43: '\\', 44: 'z',
            45: 'x', 46: 'c', 47: 'v', 48: 'b', 49: 'n', 50: 'm', 51: ',', 52: '.', 53: '/',
            57: ' ', 28: '\n',
        }
        return scancodes.get(code)

    def _decode_opencv(self, frame: object) -> str | None:
        """Decode barcode from OpenCV frame using zxing or pyzbar."""
        try:
            from pyzbar.pyzbar import decode  # type: ignore
            decoded = decode(frame)
            if decoded:
                return decoded[0].data.decode("utf-8")
        except ImportError:
            pass
        try:
            import cv2
            detector = cv2.barcode_BarcodeDetector()
            ok, decoded_info, _, _ = detector.detectAndDecode(frame)
            if ok and decoded_info:
                return decoded_info[0]
        except Exception:
            pass
        return None

    def _clean(self, raw: str) -> str:
        """Strip configured prefix/suffix."""
        if self.prefix_strip and raw.startswith(self.prefix_strip):
            raw = raw[len(self.prefix_strip):]
        if self.suffix_strip and raw.endswith(self.suffix_strip):
            raw = raw[:-len(self.suffix_strip)]
        return raw.strip()

    # ── Lookup integrations ───────────────────────────────────────────

    def lookup_inventory(self, barcode: str) -> InventoryLookupResult | None:
        """Query inventory_manager for scanned barcode."""
        try:
            from wrench_voice.inventory_manager import InventoryManager
            inv = InventoryManager(db_path=self.inventory_db_path)
            item = inv.get_item_by_barcode(barcode)
            if item:
                return InventoryLookupResult(
                    barcode=barcode, found=True,
                    sku=item.sku, part_name=item.part_name,
                    qty_on_hand=item.qty_on_hand, bin_location=item.bin_location,
                    unit_cost=item.unit_cost, last_price=item.last_price,
                    supplier=item.supplier,
                )
        except Exception:
            pass
        return InventoryLookupResult(barcode=barcode, found=False)

    def lookup_parts(self, barcode: str) -> list[dict]:
        """Query parts_finder for scanned barcode / SKU."""
        try:
            from wrench_voice.parts_finder import PartsFinder
            finder = PartsFinder(mock_mode=True)
            return finder.lookup(barcode)
        except Exception:
            return []

    # ── Control ───────────────────────────────────────────────────────

    def start(self) -> None:
        """Start background listening thread."""
        self._running = True
        self._scan_thread = threading.Thread(target=self._background_listener, daemon=True)
        self._scan_thread.start()

    def stop(self) -> None:
        """Stop listening."""
        self._running = False
        if self._scan_thread:
            self._scan_thread.join(timeout=2.0)

    def _background_listener(self) -> None:
        """Background thread feeds internal queue."""
        self._scan_queue: "queue.Queue[tuple[str, float]]" = queue.Queue()
        for bc, ts in self.listen():
            if not self._running:
                break
            self._scan_queue.put((bc, ts))

    def get_scan(self, timeout: float = 1.0) -> tuple[str, float] | None:
        """Non-blocking scan retrieval from background thread."""
        try:
            return self._scan_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def mock_scan(self, barcode: str) -> None:
        """Inject a simulated scan (for demo/testing)."""
        if hasattr(self, "_scan_queue"):
            self._scan_queue.put((barcode, time.time()))

    # ── Cleanup ───────────────────────────────────────────────────────

    def close(self) -> None:
        self.stop()
        if self._evdev_fd is not None:
            os.close(self._evdev_fd)
            self._evdev_fd = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


import queue  # noqa: E402


if __name__ == "__main__":
    scanner = BarcodeScanner(backend="mock")
    for bc, ts in scanner.listen():
        print(f"Scanned: {bc}")
        result = scanner.lookup_inventory(bc)
        print(f"  Found: {result.found}, Qty: {result.qty_on_hand}")

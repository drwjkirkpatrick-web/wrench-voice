"""tests/test_photo_hint_manager.py"""

import pytest
from wrench_voice.photo_hint_manager import PhotoHintManager, PhotoHint


class TestPhotoHintManager:
    @pytest.fixture
    def mgr(self, tmp_path):
        return PhotoHintManager(db_path=str(tmp_path / "test_hints.db"))

    def test_schema_created(self, mgr):
        hints = mgr.get_hints("test_wf")
        assert hints == []

    def test_register_and_retrieve(self, mgr):
        hint = PhotoHint(
            step_number=3,
            hint_type="photo",
            url_or_path="/tmp/test.jpg",
            description="Test photo",
            tags=["test"],
        )
        row_id = mgr.register_hint("test_wf", hint)
        assert isinstance(row_id, int)

        hints = mgr.get_hints("test_wf", step_number=3)
        assert len(hints) == 1
        assert hints[0].url_or_path == "/tmp/test.jpg"

    def test_filter_by_type(self, mgr):
        mgr.register_hint("wf", PhotoHint(1, "photo", "a.jpg", "", ["a"]))
        mgr.register_hint("wf", PhotoHint(1, "diagram", "b.png", "", ["b"]))
        photos = mgr.get_hints("wf", step_number=1, hint_type="photo")
        assert len(photos) == 1
        assert photos[0].hint_type == "photo"

    def test_search_by_tag(self, mgr):
        mgr.register_hint("wf", PhotoHint(2, "photo", "c.jpg", "Crank bolt", ["crank", "22mm"]))
        results = mgr.search_by_tag("crank")
        assert len(results) == 1
        assert results[0][1].tags == ["crank", "22mm"]

    def test_populate_defaults(self, mgr):
        mgr.populate_defaults()
        hints = mgr.get_hints("toyota_5sfe__water_pump_timing_belt")
        assert len(hints) >= 5
        types = {h.hint_type for h in hints}
        assert "photo" in types
        assert "diagram" in types
        assert "video" in types

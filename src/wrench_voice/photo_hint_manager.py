"""
photo_hint_manager.py
=====================
Manage visual hints, diagrams, and photo references for each repair workflow step.

WHY:
A photo is worth 1,000 words when a mechanic is upside down under a dash trying
to find a bolt. This module maps each workflow step to photos, diagrams, and
video clips that show the exact view, angle, and context.

USAGE:
    from wrench_voice.photo_hint_manager import PhotoHintManager
    mgr = PhotoHintManager()
    mgr.register_hints("toyota_5sfe__water_pump_timing_belt", [
        PhotoHint(step=6, photo_id="5sfe_tdc_marks", ...),
    ])

    hint = mgr.get_hint("toyota_5sfe__water_pump_timing_belt", step=6, hint_type="photo")
    # Returns URL or local path + description + bounding boxes for key areas

STRUCTURE:
- photo_hints.db (SQLite) stores metadata
- Assets can be local files, URLs, or base64 thumbnails
- Supports overlays (arrows, circles, labels) via JSON bounding boxes
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class PhotoHint:
    """A single visual hint for one step of a workflow."""
    step_number: int           # Which step this hint belongs to
    hint_type: str             # photo | diagram | video | arrow_overlay | thermal
    url_or_path: str           # Local path or remote URL
    description: str           # What the image shows
    tags: list[str]            # Searchable tags: "tdc_marks", "tensioner_bolt", etc.
    bounding_boxes: list[dict[str, Any]] | None = None
    captured_by: str = ""      # Mechanic name or source
    captured_at: str = ""      # ISO timestamp
    vehicle_info: str = ""     # e.g. "1998 Camry 5S-FE"


class PhotoHintManager:
    """SQLite-backed manager for repair workflow photo hints."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            self.db_path = Path(__file__).resolve().parents[2] / "data" / "photo_hints.db"
        else:
            self.db_path = Path(db_path)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS photo_hints (
                id INTEGER PRIMARY KEY,
                workflow_slug TEXT NOT NULL,
                step_number INTEGER NOT NULL,
                hint_type TEXT NOT NULL,
                url_or_path TEXT NOT NULL,
                description TEXT,
                tags TEXT,
                bounding_boxes TEXT,
                captured_by TEXT,
                captured_at TEXT,
                vehicle_info TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hints_slug_step ON photo_hints(workflow_slug, step_number)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hints_type ON photo_hints(hint_type)")
        conn.commit()
        conn.close()

    def register_hint(self, workflow_slug: str, hint: PhotoHint) -> int:
        """Store a single hint. Returns row id."""
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.execute(
            """INSERT INTO photo_hints
               (workflow_slug, step_number, hint_type, url_or_path, description, tags, bounding_boxes, captured_by, captured_at, vehicle_info)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                workflow_slug,
                hint.step_number,
                hint.hint_type,
                hint.url_or_path,
                hint.description,
                json.dumps(hint.tags) if hint.tags else "[]",
                json.dumps(hint.bounding_boxes) if hint.bounding_boxes else "[]",
                hint.captured_by,
                hint.captured_at,
                hint.vehicle_info,
            ),
        )
        conn.commit()
        row_id = cur.lastrowid
        conn.close()
        return row_id

    def register_hints(self, workflow_slug: str, hints: list[PhotoHint]) -> list[int]:
        """Bulk register hints for a workflow."""
        return [self.register_hint(workflow_slug, h) for h in hints]

    def get_hints(self, workflow_slug: str, step_number: Optional[int] = None, hint_type: Optional[str] = None) -> list[PhotoHint]:
        """Retrieve hints for a workflow, optionally filtered by step and type."""
        conn = sqlite3.connect(str(self.db_path))
        query = "SELECT * FROM photo_hints WHERE workflow_slug = ?"
        params = [workflow_slug]
        if step_number is not None:
            query += " AND step_number = ?"
            params.append(step_number)
        if hint_type is not None:
            query += " AND hint_type = ?"
            params.append(hint_type)
        query += " ORDER BY step_number, id"

        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [self._row_to_hint(r) for r in rows]

    def search_by_tag(self, tag: str) -> list[tuple[str, PhotoHint]]:
        """Find hints across all workflows by tag."""
        conn = sqlite3.connect(str(self.db_path))
        rows = conn.execute(
            "SELECT * FROM photo_hints WHERE tags LIKE ? ORDER BY workflow_slug, step_number",
            (f'%"{tag}"%',),
        ).fetchall()
        conn.close()
        return [(r[1], self._row_to_hint(r)) for r in rows]

    def _row_to_hint(self, row: tuple) -> PhotoHint:
        """Convert DB row to PhotoHint dataclass."""
        return PhotoHint(
            step_number=row[2],
            hint_type=row[3],
            url_or_path=row[4],
            description=row[5] or "",
            tags=json.loads(row[6]) if row[6] else [],
            bounding_boxes=json.loads(row[7]) if row[7] else [],
            captured_by=row[8] or "",
            captured_at=row[9] or "",
            vehicle_info=row[10] or "",
        )

    def populate_defaults(self) -> None:
        """Seed with example hints for the Camry water pump workflow."""
        hints = [
            PhotoHint(
                step_number=4,
                hint_type="diagram",
                url_or_path="assets/diagrams/5sfe_crank_pulley_holder.png",
                description="Crank pulley holder tool positioned on flywheel teeth through inspection port",
                tags=["crank_pulley", "holder_tool", "22mm_bolt"],
                bounding_boxes=[
                    {"label": "Holder teeth", "x": 180, "y": 120, "w": 60, "h": 40},
                    {"label": "22mm bolt head", "x": 220, "y": 200, "w": 35, "h": 35},
                ],
                vehicle_info="Toyota 5S-FE 1990-2001",
            ),
            PhotoHint(
                step_number=6,
                hint_type="photo",
                url_or_path="assets/photos/5sfe_tdc_marks_aligned.jpg",
                description="Cam sprocket punch marks aligned with backing plate notches at 12 o'clock. Crank mark aligned with pointer.",
                tags=["tdc", "timing_marks", "cam_sprocket", "crank_sprocket"],
                bounding_boxes=[
                    {"label": "Cam punch mark", "x": 145, "y": 85, "w": 20, "h": 20},
                    {"label": "Backing plate notch", "x": 145, "y": 105, "w": 20, "h": 20},
                    {"label": "Crank mark", "x": 200, "y": 250, "w": 25, "h": 25},
                ],
                vehicle_info="Toyota 5S-FE 1990-2001",
            ),
            PhotoHint(
                step_number=7,
                hint_type="video",
                url_or_path="assets/videos/5sfe_tensioner_removal.mp4",
                description="Video: loosening tensioner bolt with 14mm socket while holding spring pressure",
                tags=["tensioner", "14mm_socket", "belt_removal"],
                vehicle_info="Toyota 5S-FE 1990-2001",
            ),
            PhotoHint(
                step_number=11,
                hint_type="diagram",
                url_or_path="assets/diagrams/5sfe_belt_routing.png",
                description="Timing belt routing diagram: crank to tensioner to water pump to cam. Arrows show direction.",
                tags=["belt_routing", "diagram", "crank", "cam", "tensioner"],
                bounding_boxes=[
                    {"label": "Crank sprocket", "x": 100, "y": 300, "w": 80, "h": 80},
                    {"label": "Cam sprocket", "x": 300, "y": 80, "w": 80, "h": 80},
                    {"label": "Tensioner", "x": 200, "y": 200, "w": 60, "h": 60},
                ],
                vehicle_info="Toyota 5S-FE 1990-2001",
            ),
            PhotoHint(
                step_number=12,
                hint_type="photo",
                url_or_path="assets/photos/5sfe_belt_tensioned.jpg",
                description="Properly tensioned belt: deflection 5mm at longest span between cam and water pump",
                tags=["belt_tension", "deflection_test", "final_check"],
                bounding_boxes=[
                    {"label": "Belt span (test here)", "x": 150, "y": 180, "w": 100, "h": 20},
                ],
                vehicle_info="Toyota 5S-FE 1990-2001",
            ),
        ]
        self.register_hints("toyota_5sfe__water_pump_timing_belt", hints)


# Convenience
DEFAULT_MANAGER: PhotoHintManager | None = None


def get_manager() -> PhotoHintManager:
    global DEFAULT_MANAGER
    if DEFAULT_MANAGER is None:
        DEFAULT_MANAGER = PhotoHintManager()
        DEFAULT_MANAGER.populate_defaults()
    return DEFAULT_MANAGER

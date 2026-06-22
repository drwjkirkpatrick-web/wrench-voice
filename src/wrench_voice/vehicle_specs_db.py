"""
vehicle_specs_db.py
===================
SQLite-backed vehicle specs, torque, fluids, maintenance, and known issues.

WHY:
The old system kept everything in Python dicts (ENGINE_FAMILY_ALIASES) and
markdown files (kb/). That works for 23 families but doesn't scale to 100+.
This module provides a clean query interface over vehicle_specs.db so the
diagnostic engine, parts planner, and CLI can ask structured questions.

HOW:
1. Open the SQLite DB (lazy: opens on first query)
2. Search by alias, make/model/year, or engine slug
3. Return typed dataclasses for downstream consumption

WHAT mechanics ask:
- "What's the torque spec for head bolts on an EJ25?"
- "How much coolant does a 7.3 Power Stroke hold?"
- "What goes wrong with a 6.0 Power Stroke?"
- "Show me all Subarus with the EJ25 SOHC"
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class EngineFamily:
    slug: str
    code: str
    manufacturer: str
    displacement: str
    configuration: str
    cylinders: int
    valvetrain: str
    fuel_system: str
    timing: str
    interference: str
    years: str
    notes: str


@dataclass
class VehicleModel:
    id: int
    make: str
    model: str
    year_start: int
    year_end: int
    engine_slug: str
    body_style: str | None
    drivetrain: str | None
    transmission: str | None


@dataclass
class TorqueSpec:
    component: str
    ft_lbs: float | None
    nm: float | None
    angle_degrees: float | None
    torque_type: str
    sequence: str | None
    notes: str | None


@dataclass
class FluidCapacity:
    fluid_type: str
    capacity: str
    specification: str | None
    notes: str | None


@dataclass
class MaintenanceInterval:
    interval_miles: int | None
    interval_months: int | None
    service: str
    severity: str


@dataclass
class KnownIssue:
    issue_name: str
    description: str
    prevalence: float
    severity: str
    affected_years: str | None
    symptoms: str | None
    parts_needed: str | None


@dataclass
class EngineSpec:
    spec_name: str
    value: str
    unit: str | None
    notes: str | None


# ─── Database Interface ─────────────────────────────────────────────────────

class VehicleSpecsDB:
    """
    Query interface for vehicle_specs.db.

    Thread-safe for reads (each method opens its own connection).
    No write methods — data is populated by a migration script.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            # Relative to this file: ../../data/vehicle_specs.db
            # __file__ = .../src/wrench_voice/vehicle_specs_db.py
            self._db_path = Path(__file__).parent.parent.parent / "data" / "vehicle_specs.db"
        else:
            self._db_path = Path(db_path)

    # ─── Internal ───────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ─── Engine Family Lookups ───────────────────────────────────────────────

    def resolve_alias(self, text: str) -> str | None:
        """
        Fuzzy-resolve a user query like 'ej25' or 'wrx 2.5' to a slug.
        Tries aliases first, then falls back to family code.
        """
        conn = self._connect()
        cur = conn.execute(
            "SELECT engine_slug FROM engine_aliases WHERE alias LIKE ? LIMIT 1",
            (f"%{text.lower().strip()}%",),
        )
        row = cur.fetchone()
        if row:
            return row["engine_slug"]
        # Fallback: direct slug match
        cur = conn.execute(
            "SELECT slug FROM engine_families WHERE slug LIKE ? LIMIT 1",
            (f"%{text.lower().strip()}%",),
        )
        row = cur.fetchone()
        return row["slug"] if row else None

    def get_family(self, slug: str) -> EngineFamily | None:
        conn = self._connect()
        cur = conn.execute("SELECT * FROM engine_families WHERE slug = ?", (slug,))
        row = cur.fetchone()
        if not row:
            return None
        return EngineFamily(**dict(row))

    def list_families(self, manufacturer: str | None = None) -> list[EngineFamily]:
        conn = self._connect()
        if manufacturer:
            cur = conn.execute(
                "SELECT * FROM engine_families WHERE manufacturer = ? ORDER BY code",
                (manufacturer,),
            )
        else:
            cur = conn.execute("SELECT * FROM engine_families ORDER BY manufacturer, code")
        return [EngineFamily(**dict(r)) for r in cur.fetchall()]

    # ─── Vehicle Model Lookups ───────────────────────────────────────────────

    def find_models(self, make: str | None = None, model: str | None = None,
                    year: int | None = None, engine_slug: str | None = None) -> list[VehicleModel]:
        conn = self._connect()
        query = "SELECT * FROM vehicle_models WHERE 1=1"
        params: list[Any] = []
        if make:
            query += " AND make LIKE ?"
            params.append(f"%{make}%")
        if model:
            query += " AND model LIKE ?"
            params.append(f"%{model}%")
        if year:
            query += " AND year_start <= ? AND year_end >= ?"
            params.extend([year, year])
        if engine_slug:
            query += " AND engine_slug = ?"
            params.append(engine_slug)
        query += " ORDER BY make, model, year_start"
        cur = conn.execute(query, params)
        return [VehicleModel(**dict(r)) for r in cur.fetchall()]

    # ─── Specs Lookups ────────────────────────────────────────────────────────

    def get_torque_specs(self, slug: str) -> list[TorqueSpec]:
        conn = self._connect()
        cur = conn.execute(
            "SELECT * FROM torque_specs WHERE engine_slug = ? ORDER BY component",
            (slug,),
        )
        return [TorqueSpec(**{k: r[k] for k in r.keys() if k != "id" and k != "engine_slug"}) for r in cur.fetchall()]

    def get_fluids(self, slug: str) -> list[FluidCapacity]:
        conn = self._connect()
        cur = conn.execute(
            "SELECT * FROM fluid_capacities WHERE engine_slug = ? ORDER BY fluid_type",
            (slug,),
        )
        return [FluidCapacity(**{k: r[k] for k in r.keys() if k != "id" and k != "engine_slug"}) for r in cur.fetchall()]

    def get_maintenance(self, slug: str) -> list[MaintenanceInterval]:
        conn = self._connect()
        cur = conn.execute(
            "SELECT * FROM maintenance_intervals WHERE engine_slug = ? ORDER BY interval_miles",
            (slug,),
        )
        return [MaintenanceInterval(**{k: r[k] for k in r.keys() if k != "id" and k != "engine_slug"}) for r in cur.fetchall()]

    def get_issues(self, slug: str) -> list[KnownIssue]:
        conn = self._connect()
        cur = conn.execute(
            "SELECT * FROM known_issues WHERE engine_slug = ? ORDER BY prevalence DESC",
            (slug,),
        )
        return [KnownIssue(**{k: r[k] for k in r.keys() if k != "id" and k != "engine_slug"}) for r in cur.fetchall()]

    def get_specs(self, slug: str) -> list[EngineSpec]:
        conn = self._connect()
        cur = conn.execute(
            "SELECT * FROM engine_specs WHERE engine_slug = ? ORDER BY spec_name",
            (slug,),
        )
        return [EngineSpec(**{k: r[k] for k in r.keys() if k != "id" and k != "engine_slug"}) for r in cur.fetchall()]

    # ─── Convenience: Full Engine Report ──────────────────────────────────────

    def engine_report(self, slug: str) -> dict[str, Any]:
        """Return a complete dict of everything we know about an engine family."""
        family = self.get_family(slug)
        if not family:
            return {"error": f"Unknown engine family: {slug}"}
        return {
            "family": family,
            "models": self.find_models(engine_slug=slug),
            "torque_specs": self.get_torque_specs(slug),
            "fluids": self.get_fluids(slug),
            "maintenance": self.get_maintenance(slug),
            "issues": self.get_issues(slug),
            "specs": self.get_specs(slug),
        }

    # ─── Search ───────────────────────────────────────────────────────────────

    def search(self, query: str) -> dict[str, Any]:
        """
        Broad search: try alias resolution on full query first, then individual
        words (preferring words with digits — engine codes like '22re', 'ej25'),
        then make/model split.
        Returns the best engine_report() match or an empty dict.
        """
        # Try full query as alias first
        slug = self.resolve_alias(query)
        if slug:
            return self.engine_report(slug)
        # Try each word individually as alias, preferring engine-code-looking words
        words = query.split()
        # Prefer words with digits (likely engine codes: 22re, ej25, b16, etc.)
        engine_code_words = [w for w in words if any(ch.isdigit() for ch in w)]
        other_words = [w for w in words if w not in engine_code_words]
        for word in engine_code_words + other_words:
            slug = self.resolve_alias(word)
            if slug:
                return self.engine_report(slug)
        # Try make/model
        if len(words) >= 2:
            models = self.find_models(make=words[0], model=words[1])
            if models:
                return self.engine_report(models[0].engine_slug)
        return {}

    # ─── Stats ──────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, int]:
        conn = self._connect()
        return {
            "families": conn.execute("SELECT COUNT(*) FROM engine_families").fetchone()[0],
            "models": conn.execute("SELECT COUNT(*) FROM vehicle_models").fetchone()[0],
            "torque_specs": conn.execute("SELECT COUNT(*) FROM torque_specs").fetchone()[0],
            "fluids": conn.execute("SELECT COUNT(*) FROM fluid_capacities").fetchone()[0],
            "issues": conn.execute("SELECT COUNT(*) FROM known_issues").fetchone()[0],
            "specs": conn.execute("SELECT COUNT(*) FROM engine_specs").fetchone()[0],
            "aliases": conn.execute("SELECT COUNT(*) FROM engine_aliases").fetchone()[0],
        }

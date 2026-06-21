"""
parts_planner.py
================
Plan parts + timeline for a diagnosed repair.

WHY:
After diagnosis, the mechanic needs to know:
1. What parts to buy (including gaskets, seals, fluids — the stuff you always forget)
2. How much it costs
3. How long until everything arrives
4. What's already in the shop

HOW:
1. Take a DiagnosisResult
2. Expand the diagnosis's parts_needed into a full bill of materials
3. Look up each part with PartsFinder
4. Cross-check against local inventory
5. Build a JobPlan with timeline and sourcing breakdown

WHAT'S A BILL OF MATERIALS EXPANSION:
A simple head gasket job becomes:
- Head gasket set
- Head bolts (T-T-Y, must replace)
- Coolant (drain + refill)
- Oil (drain + refill, coolant contamination)
- Oil filter
- RTV sealant
- Throttle body gasket
- Intake manifold gasket
- Exhaust manifold gasket (if disturbed)
- Valve cover gasket (might as well while it's apart)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Lazy imports — PartsFinder is heavy (httpx, beautifulsoup)
# We only import it when needed.


@dataclass
class PlannedPart:
    """One line item in the job plan."""
    name: str
    quantity: int
    unit_price: float
    total_price: float
    supplier: str
    availability: str
    shipping_days: int
    on_hand: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "total_price": self.total_price,
            "supplier": self.supplier,
            "availability": self.availability,
            "shipping_days": self.shipping_days,
            "on_hand": self.on_hand,
        }


@dataclass
class JobPlan:
    """Complete repair plan ready for the mechanic or shop foreman."""
    job_id: str
    vehicle_info: dict[str, Any]
    diagnosis: dict[str, Any]
    parts_needed: list[PlannedPart]
    consumables: list[str]       # Fluids, sealants, cleaners — always needed
    estimated_cost: float
    sourcing_plan: str           # Text summary of what's in stock vs ordered
    timeline: str
    warnings: list[str]
    notes: str = ""

    def to_markdown(self) -> str:
        lines = [
            f"# Job Plan: {self.job_id}",
            "",
            f"**Vehicle:** {self.vehicle_info}",
            f"**Diagnosis:** {self.diagnosis.get('symptom', 'N/A')}",
            f"**Total Cost:** ${self.estimated_cost:.2f}",
            f"**Timeline:** {self.timeline}",
            "",
        ]
        if self.warnings:
            lines.append("⚠️ **Warnings:**")
            for w in self.warnings:
                lines.append(f"  - {w}")
            lines.append("")

        lines.append("## Parts Needed")
        lines.append("| Part | Qty | Unit | Total | Supplier | Avail | Ship | On Hand |")
        lines.append("|------|-----|------|-------|----------|-------|------|---------|")
        for p in self.parts_needed:
            lines.append(
                f"| {p.name} | {p.quantity} | ${p.unit_price:.2f} | ${p.total_price:.2f} "
                f"| {p.supplier} | {p.availability} | {p.shipping_days}d | {'✓' if p.on_hand else ''} |"
            )
        lines.append("")

        lines.append("## Consumables")
        for c in self.consumables:
            lines.append(f"- {c}")
        lines.append("")

        lines.append("## Sourcing Plan")
        lines.append(self.sourcing_plan)
        lines.append("")

        if self.notes:
            lines.append("## Notes")
            lines.append(self.notes)

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "vehicle_info": self.vehicle_info,
            "diagnosis": self.diagnosis,
            "parts_needed": [p.to_dict() for p in self.parts_needed],
            "consumables": self.consumables,
            "estimated_cost": self.estimated_cost,
            "sourcing_plan": self.sourcing_plan,
            "timeline": self.timeline,
            "warnings": self.warnings,
            "notes": self.notes,
        }

    def export_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    def export_yaml(self, path: str | Path) -> None:
        try:
            import yaml
            Path(path).write_text(yaml.dump(self.to_dict()), encoding="utf-8")
        except ImportError:
            # Fallback if PyYAML not installed
            self.export_json(str(path).replace(".yaml", ".json"))


class PartsPlanner:
    """
    Convert a diagnosis into a full job plan with parts and timeline.

    Usage:
        planner = PartsPlanner()
        plan = planner.plan(diagnosis_result)
        plan.export_json("~/jobs/job-001.json")
    """

    def __init__(self, mock_mode: bool = False) -> None:
        self.mock_mode = mock_mode
        # Lazy init — only create finder when needed
        self._finder: Any | None = None

    @property
    def finder(self) -> Any:
        """Lazy getter for PartsFinder — avoids heavy imports at init."""
        if self._finder is None:
            from .parts_finder import PartsFinder
            self._finder = PartsFinder(mock_mode=self.mock_mode)
        return self._finder

    def plan(self, diagnosis: Any) -> JobPlan:
        """
        Build a JobPlan from a DiagnosisResult.

        Automatically expands the diagnosis's parts_needed into a full BOM,
        looks up pricing, and estimates timeline.
        """
        # Unique job ID
        import uuid
        job_id = f"job-{uuid.uuid4().hex[:8]}"

        vehicle_info = getattr(diagnosis, "vehicle_info", {})
        make = vehicle_info.get("make")
        year = vehicle_info.get("year")
        engine = vehicle_info.get("engine")

        # Get base parts from diagnosis
        base_parts: list[str] = []
        if hasattr(diagnosis, "ranked_causes") and diagnosis.ranked_causes:
            top_cause = diagnosis.ranked_causes[0]
            base_parts = top_cause.get("parts_needed", [])

        # Expand to full BOM (the mechanic always forgets something)
        expanded = self._expand_bom(base_parts)

        # Look up each part
        planned: list[PlannedPart] = []
        total = 0.0
        for part_name in expanded:
            results = self.finder.lookup(part_name, make=make, year=year, engine=engine)
            if results:
                best = results[0]  # Cheapest in-stock or shipping
                qty = self._default_qty(part_name)
                line_total = best.price * qty
                planned.append(
                    PlannedPart(
                        name=best.part_name,
                        quantity=qty,
                        unit_price=best.price,
                        total_price=round(line_total, 2),
                        supplier=best.supplier,
                        availability=best.availability,
                        shipping_days=best.shipping_days,
                        on_hand="Local Inventory" in best.supplier or "In stock" in best.availability,
                    )
                )
                total += line_total
            else:
                # Couldn't find — add as placeholder
                planned.append(
                    PlannedPart(
                        name=part_name,
                        quantity=1,
                        unit_price=0.0,
                        total_price=0.0,
                        supplier="Unknown",
                        availability="Manual lookup required",
                        shipping_days=0,
                        on_hand=False,
                    )
                )

        # Determine timeline from longest shipping time
        ship_times = [p.shipping_days for p in planned if not p.on_hand]
        max_ship = max(ship_times) if ship_times else 0

        labor_estimate = self._labor_time(diagnosis)
        if max_ship > 0:
            timeline = f"Parts arrive in {max_ship} days. Estimated labor: {labor_estimate}. Total turnaround: {max_ship + 1}–{max_ship + 2} days."
        else:
            timeline = f"All parts in stock. Estimated labor: {labor_estimate}. Same-day completion possible."

        # Sourcing summary
        in_stock = [p for p in planned if p.on_hand]
        ordered = [p for p in planned if not p.on_hand]

        sourcing_lines: list[str] = []
        if in_stock:
            sourcing_lines.append(f"On shelf ({len(in_stock)} items): " + ", ".join(p.name for p in in_stock[:3]))
        if ordered:
            sourcing_lines.append(f"Order ({len(ordered)} items): " + ", ".join(p.name for p in ordered[:3]))
        sourcing = "\n".join(sourcing_lines) or "Manual sourcing required."

        # Warnings from diagnosis
        warnings = list(getattr(diagnosis, "warnings", []))
        if not any(p.on_hand for p in planned):
            warnings.append("No parts currently in stock — delay job start until parts arrive.")

        # Consumables always needed
        consumables = self._default_consumables(base_parts)

        return JobPlan(
            job_id=job_id,
            vehicle_info=vehicle_info,
            diagnosis=getattr(diagnosis, "to_dict", lambda: {})(),
            parts_needed=planned,
            consumables=consumables,
            estimated_cost=round(total, 2),
            sourcing_plan=sourcing,
            timeline=timeline,
            warnings=warnings,
            notes="Prices from online sources — verify before ordering.",
        )

    def plan_from_file(self, job_file: str | Path) -> JobPlan:
        """
        Load a diagnosis from a JSON file and plan parts for it.
        Used by the CLI `plan` command.
        """
        from .diagnostic_engine import DiagnosisResult

        raw = Path(job_file).read_text(encoding="utf-8")
        data = json.loads(raw)
        diagnosis = DiagnosisResult(**data)
        return self.plan(diagnosis)

    # ─── Helpers ───────────────────────────────────────────────────────────────

    def _expand_bom(self, base_parts: list[str]) -> list[str]:
        """
        Expand a minimal parts list into a realistic bill of materials.

        The mechanic ALWAYS forgets gaskets, sealant, and fluids.
        This catches the obvious ones.
        """
        # Deduplicate while preserving order
        seen = set()
        expanded: list[str] = []
        for p in base_parts:
            key = p.lower()
            if key not in seen:
                seen.add(key)
                expanded.append(p)

        # Auto-add ancillaries based on what's in the list
        text = " ".join(expanded).lower()

        if "head gasket" in text:
            for extra in ["head bolts", "coolant", "motor oil", "oil filter", "RTV sealant", "valve cover gasket", "intake manifold gasket"]:
                if extra not in seen:
                    seen.add(extra)
                    expanded.append(extra)

        if "water pump" in text or "thermostat" in text:
            for extra in ["coolant", "hose", "clamp", "RTV sealant"]:
                if extra not in seen:
                    seen.add(extra)
                    expanded.append(extra)

        if "timing belt" in text:
            for extra in ["timing belt tensioner", "idler pulley", "coolant", "serpentine belt", "crankshaft seal"]:
                if extra not in seen:
                    seen.add(extra)
                    expanded.append(extra)

        if "spark" in text or "ignition" in text:
            for extra in ["spark plug", "dielectric grease", "coil boot"]:
                if extra not in seen:
                    seen.add(extra)
                    expanded.append(extra)

        if "piston" in text or "ring" in text:
            for extra in ["cylinder hone", "connecting rod bearings", "main bearings", "assembly lube"]:
                if extra not in seen:
                    seen.add(extra)
                    expanded.append(extra)

        return expanded

    def _default_qty(self, part_name: str) -> int:
        """Common quantities so we don't order 1 spark plug for a 4-cylinder."""
        low = part_name.lower()
        if "plug" in low:
            return 4
        if "bolt" in low or "nut" in low:
            return 10  # Set
        if "clamp" in low:
            return 4
        if "hose" in low:
            return 2
        if "gasket" in low:
            return 1  # Set usually
        return 1

    def _default_consumables(self, base_parts: list[str]) -> list[str]:
        """Fluids and supplies every job consumes."""
        text = " ".join(base_parts).lower()
        result: list[str] = []
        if "coolant" not in text:
            result.append("Coolant (verify type: green / orange / pink)")
        if "oil" not in text and "filter" not in text:
            result.append("Motor oil (match spec on oil cap / manual)")
            result.append("Oil filter")
        result.append("Shop towels")
        result.append("Brake cleaner")
        return result

    def _labor_time(self, diagnosis: Any) -> str:
        """Rough labor estimate based on diagnosis severity."""
        est = getattr(diagnosis, "estimated_time", "1–3 hours")
        return est

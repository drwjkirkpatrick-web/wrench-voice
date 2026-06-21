"""
auto_order.py
=============
Generate purchase orders based on scheduled jobs, inventory levels, and
learned delivery times.

WHY:
A mechanic shop wastes money on:
1. Rush shipping (emergency part orders)
2. Holding excess inventory (capital tied up)
3. Delayed jobs (parts didn't arrive in time)

This module looks at the next N days of scheduled jobs, checks what's in stock,
consolidates orders by supplier to hit free-shipping thresholds, and orders with
buffer calculated from actual delivery history.

FEATURES:
- Daily auto-scan: upcoming jobs -> parts needed -> shortages -> PO generation
- Consolidation: group parts by supplier for free shipping
- Buffer calculation: learned delivery time + 1-2 day safety margin
- Priority flags: critical jobs get expedited shipping
- Manual override: exclude items, change quantities, split suppliers
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from wrench_voice.delivery_predictor import DeliveryPredictor
from wrench_voice.inventory_manager import InventoryManager


class AutoOrder:
    """
    Automated parts ordering system.

    Usage:
        ao = AutoOrder()
        # Generate POs for jobs next 7 days
        pos = ao.generate_pos(look_ahead_days=7, dest_zip="97201")
        for po in pos:
            print(po['supplier'], po['total'], po['shipping_estimate'])
            # Optionally: ao.export_po(po, format="csv")
    """

    FREE_SHIP_THRESHOLDS = {
        "RockAuto": 49.0,
        "Advance": 35.0,
        "O'Reilly": 35.0,
        "AutoZone": 35.0,
        "FCPEuro": 49.0,
        "Pelican": 49.0,
    }

    def __init__(self, db_path: str | None = None) -> None:
        self.inv = InventoryManager(db_path)
        self.pred = DeliveryPredictor(db_path)

    def generate_pos(
        self,
        upcoming_parts: list[dict[str, Any]],
        dest_zip: str,
        look_ahead_days: int = 7,
        min_buffer_days: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Generate purchase orders from a list of needed parts.

        upcoming_parts: [{sku, part_number, part_name, supplier, qty_needed, unit_price, part_category}]
        Returns: list of PO dicts per supplier
        """
        # Group by supplier
        by_supplier: dict[str, list[dict[str, Any]]] = {}
        for p in upcoming_parts:
            supplier = p.get("supplier", "RockAuto")
            by_supplier.setdefault(supplier, []).append(p)

        pos: list[dict[str, Any]] = []
        for supplier, items in by_supplier.items():
            total = sum(i.get("unit_price", 0) * i.get("qty_needed", 1) for i in items)
            est = self.pred.predict(supplier, dest_zip, items[0].get("part_category", "general"), promised=3)
            buffer = max(est["buffer_days"], min_buffer_days)
            ship_method = "standard"
            if any(i.get("priority") == "critical" for i in items):
                ship_method = "expedited"
                buffer = 1  # Rush it

            free_ship = self.FREE_SHIP_THRESHOLDS.get(supplier, 49.0)
            shipping_cost = 0.0 if total >= free_ship else 9.99

            pos.append({
                "supplier": supplier,
                "order_date": datetime.now().isoformat(),
                "need_by": (datetime.now() + timedelta(days=buffer)).isoformat(),
                "items": items,
                "subtotal": round(total, 2),
                "shipping_estimate": shipping_cost,
                "shipping_method": ship_method,
                "free_ship_threshold": free_ship,
                "free_ship_achieved": total >= free_ship,
                "delivery_estimate_days": est["estimate_days"],
                "confidence": est["confidence"],
                "recommendation": est["recommendation"],
            })

        return pos

    def suggest_additions(self, current_pos: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        For POs close to free-shipping threshold, suggest fast-moving consumables
        to push the order over the line.
        """
        suggestions = []
        for po in current_pos:
            gap = po["free_ship_threshold"] - po["subtotal"]
            if 0 < gap <= 15:
                suggestions.append({
                    "for_po": po["supplier"],
                    "gap": round(gap, 2),
                    "suggested_extras": ["brake cleaner", "RTV sealant", "zip ties", "shop towels"],
                    "why": f"Add ~${gap:.2f} to reach free shipping",
                })
        return suggestions

    def export_po(self, po: dict[str, Any], fmt: str = "json", out_path: str | None = None) -> str:
        """Export a PO to JSON, CSV, or text for email."""
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path(out_path or f"/tmp/po_{po['supplier']}_{stamp}.{fmt}")
        if fmt == "json":
            path.write_text(json.dumps(po, indent=2))
        elif fmt == "csv":
            lines = ["sku,part_number,part_name,qty,unit_price,line_total"]
            for it in po["items"]:
                qty = it.get("qty_needed", 1)
                price = it.get("unit_price", 0)
                lines.append(f"{it['sku']},{it['part_number']},{it['part_name']},{qty},{price},{qty*price}")
            lines.append(f",,,,Subtotal,{po['subtotal']}")
            lines.append(f",,,,Shipping,{po['shipping_estimate']}")
            lines.append(f",,,,Total,{po['subtotal'] + po['shipping_estimate']}")
            path.write_text("\n".join(lines))
        else:
            lines = [
                f"PURCHASE ORDER — {po['supplier']}",
                f"Date: {po['order_date']}",
                f"Need by: {po['need_by']}",
                f"Shipping: {po['shipping_method']} (est. {po['delivery_estimate_days']} days)",
                "",
            ]
            for it in po["items"]:
                lines.append(f"  {it['part_number']} x{it.get('qty_needed',1)} @ ${it.get('unit_price',0):.2f} — {it['part_name']}")
            lines.extend(["", f"Subtotal: ${po['subtotal']:.2f}", f"Shipping: ${po['shipping_estimate']:.2f}"])
            path.write_text("\n".join(lines))
        return str(path)

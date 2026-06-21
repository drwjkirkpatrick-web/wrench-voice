"""
quickbooks_sync.py
==================
QuickBooks Desktop / Online invoice sync stub.

WHY:
Manual double-entry of invoices into QuickBooks is error-prone and slow.
This module provides a bridge to push job data from wrench-voice
into QuickBooks automatically.

CURRENT STATUS: STUB — waits for QuickBooks API credentials.
Future: QBO OAuth2 or QBD QBXML integration.

FEATURES:
- Push completed jobs as invoices
- Sync customers (vehicle owner -> QuickBooks customer)
- Track accounts receivable
- Reconcile payments
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class QBInvoice:
    ticket_id: str
    customer: str
    line_items: list[dict[str, Any]]
    total: float
    tax: float
    created_at: str
    qb_invoice_id: str | None = None
    status: str = "draft"  # draft | sent | paid | void


class QuickBooksSync:
    """
    QuickBooks sync stub.

    Usage:
        qb = QuickBooksSync(mock_mode=True)
        invoice = qb.create_invoice(ticket_id="JOB-001", customer="Jane Doe",
                                     line_items=[{"desc": "Water pump", "amount": 89.99},
                                                 {"desc": "Labor 2.5 hrs", "amount": 237.50}])
        # In production: qb.push_to_qbo(invoice)
    """

    def __init__(self, mock_mode: bool = True, credentials_path: str | None = None) -> None:
        self.mock_mode = mock_mode
        self.credentials_path = Path(credentials_path) if credentials_path else None
        self.invoices: list[QBInvoice] = []

    def create_invoice(
        self,
        ticket_id: str,
        customer: str,
        line_items: list[dict[str, Any]],
        tax_rate: float = 0.0,
    ) -> QBInvoice:
        subtotal = sum(i["amount"] for i in line_items)
        tax = subtotal * tax_rate
        total = subtotal + tax
        from datetime import datetime
        inv = QBInvoice(
            ticket_id=ticket_id,
            customer=customer,
            line_items=line_items,
            total=round(total, 2),
            tax=round(tax, 2),
            created_at=datetime.now().isoformat(),
            qb_invoice_id=f"QB-MOCK-{datetime.now().strftime('%Y%m%d%H%M%S')}" if self.mock_mode else None,
        )
        self.invoices.append(inv)
        return inv

    def push_to_qbo(self, invoice: QBInvoice) -> dict[str, Any]:
        """Real QBO push. Requires OAuth2 tokens."""
        if self.mock_mode:
            return {"status": "mock_sent", "qb_id": invoice.qb_invoice_id}
        # Future: implement QBO API call
        return {"status": "not_implemented", "message": "Configure QBO OAuth2 in quickbooks_sync.py"}

    def list_invoices(self, status: str | None = None) -> list[QBInvoice]:
        if status:
            return [i for i in self.invoices if i.status == status]
        return list(self.invoices)

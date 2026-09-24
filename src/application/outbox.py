"""The repair job is saved once.

The same event is not saved again. A missing fault is not a row. The row is not deleted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["work_order"]


class OutboxError(Exception):
    code = "outbox_error"


class DuplicateOutboxEvent(OutboxError):
    code = "duplicate_outbox_event"


class MissingReceipt(OutboxError):
    code = "missing_receipt"


@dataclass(frozen=True)
class OutboxRow:
    tenant_id: str
    event_id: str
    work_order_id: str
    station_id: str
    evse_id: int | None
    correlation_id: str
    kind: Kind = "work_order"


@dataclass
class Outbox:
    rows: list[OutboxRow] = field(default_factory=list)
    seen: set[tuple[str, str]] = field(default_factory=set)

    def append(self, row: OutboxRow) -> OutboxRow:
        key = (row.tenant_id, row.event_id)
        if key in self.seen:
            raise DuplicateOutboxEvent(row.event_id)
        self.seen.add(key)
        self.rows.append(row)
        return row

    def by_event(self, tenant_id: str, event_id: str) -> OutboxRow | None:
        for row in self.rows:
            if row.tenant_id == tenant_id and row.event_id == event_id:
                return row
        return None

    def for_tenant(self, tenant_id: str) -> tuple[OutboxRow, ...]:
        return tuple(r for r in self.rows if r.tenant_id == tenant_id)


def enqueue_work_order(outbox: Outbox, receipt, event_id: str) -> OutboxRow:
    if receipt is None or not getattr(receipt, "work_order_id", None):
        raise MissingReceipt("outbox will not enqueue a receipt without a work_order_id")
    row = OutboxRow(
        tenant_id=receipt.tenant_id,
        event_id=event_id,
        work_order_id=receipt.work_order_id,
        station_id=receipt.station_id,
        evse_id=receipt.evse_id,
        correlation_id=receipt.correlation_id,
    )
    return outbox.append(row)

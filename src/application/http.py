"""Was this a real charger fault?

One posted fault becomes a repair job. There is no charger socket in this file.
The charger-management system posts the fault. This file locks the charger, then opens the job.
"""
from __future__ import annotations

from dataclasses import dataclass

from platforms.bayline.src.application.outbox import Outbox, OutboxRow, enqueue_work_order
from platforms.bayline.src.application.receipt import (
    Component,
    IncomingMessage,
    NotADiagnosis,
    NotifyEventRow,
    Receipt,
    ReceiptError,
    ReceiptStore,
    Variable,
    ingest,
    open_work_order,
    set_lockout,
)


class BadEnvelope(ReceiptError):
    code = "bad_envelope"


@dataclass(frozen=True)
class IngestResult:
    receipt: Receipt
    diagnosed: int
    outbox_row: OutboxRow | None


def _require(envelope: dict, key: str) -> str:
    value = envelope.get(key)
    if not value:
        raise BadEnvelope(f"CSMS envelope missing {key}")
    return str(value)


def _row_from_event_data(item: dict) -> NotifyEventRow:
    component = item.get("component") or {}
    evse = component.get("evse") or {}
    variable = item.get("variable") or {}
    return NotifyEventRow(
        event_id=int(item.get("eventId") or item.get("event_id") or 0),
        timestamp=str(item.get("timestamp") or ""),
        trigger=item.get("trigger") or "Alerting",
        actual_value=str(item.get("actualValue") or item.get("actual_value") or ""),
        component=Component(
            name=str(component.get("name") or "EVSE"),
            evse_id=evse.get("id"),
            connector_id=component.get("connectorId"),
        ),
        variable=Variable(name=str(variable.get("name") or "AvailabilityState")),
        tech_code=item.get("techCode"),
        tech_info=item.get("techInfo"),
        cleared=bool(item.get("cleared", False)),
    )


def message_from_envelope(envelope: dict) -> IncomingMessage:
    payload = envelope.get("payload") or {}
    raw_rows = payload.get("eventData") or payload.get("event_data") or envelope.get("eventData") or ()
    rows = tuple(_row_from_event_data(item) for item in raw_rows)
    return IncomingMessage(
        tenant_id=_require(envelope, "tenant_id"),
        station_id=_require(envelope, "station_id"),
        correlation_id=_require(envelope, "correlation_id"),
        protocol=envelope.get("protocol") or "ocpp2.1",
        action=envelope.get("action") or "NotifyEvent",
        rows=rows,
        stream_id=payload.get("streamId") or envelope.get("stream_id"),
    )


def handle_notify_event(
    store: ReceiptStore,
    envelope: dict,
    *,
    outbox: Outbox | None = None,
) -> IngestResult:
    """POST NotifyEvent → diagnosed rows → LOTO → work order → optional outbox."""
    message = message_from_envelope(envelope)
    diagnosed = ingest(store, message)
    if not diagnosed:
        raise NotADiagnosis("NotifyEvent carried no diagnosis row")
    set_lockout(store, message.tenant_id, message.correlation_id)
    work_order_id = _require(envelope, "work_order_id")
    receipt = open_work_order(store, message, diagnosed[0], work_order_id)
    row = None
    if outbox is not None:
        event_id = str(envelope.get("event_id") or message.correlation_id)
        row = enqueue_work_order(outbox, receipt, event_id)
    return IngestResult(receipt=receipt, diagnosed=len(diagnosed), outbox_row=row)

"""Was this a real charger fault?

An alert is kept. A change to faulted that is still open is kept.
A cleared fault, a status update, the old protocol, and an update stream are refused.
The repair job cannot be opened before the lock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Protocol = Literal["ocpp2.1", "ocpp2.0.1", "ocpp1.6"]
Trigger = Literal["Alerting", "Delta", "Periodic"]
Action = Literal["NotifyEvent", "NotifyPeriodicEventStream", "StatusNotification"]

RECEIPT_TRIGGERS = frozenset({"Alerting"})
FAULTED_STATES = frozenset({"Faulted"})


class ReceiptError(Exception):
    code: str = "receipt_error"

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


class ProtocolRejected(ReceiptError):
    code = "protocol_rejected"


class StreamIsNotAReceipt(ReceiptError):
    code = "stream_is_not_a_receipt"


class DuplicateEvent(ReceiptError):
    code = "duplicate"


class LockoutRequired(ReceiptError):
    code = "lockout_required"


class NotADiagnosis(ReceiptError):
    code = "not_a_diagnosis"


@dataclass(frozen=True)
class Component:
    name: str
    evse_id: int | None = None
    connector_id: int | None = None
    instance: str | None = None


@dataclass(frozen=True)
class Variable:
    name: str


@dataclass(frozen=True)
class NotifyEventRow:
    event_id: int
    timestamp: str
    trigger: Trigger
    actual_value: str
    component: Component
    variable: Variable
    tech_code: str | None = None
    tech_info: str | None = None
    cleared: bool = False
    severity: int | None = None
    variable_monitoring_id: int | None = None
    event_notification_type: str | None = None


@dataclass(frozen=True)
class IncomingMessage:
    tenant_id: str
    station_id: str
    correlation_id: str
    protocol: Protocol
    action: Action
    rows: tuple[NotifyEventRow, ...] = ()
    stream_id: int | None = None


@dataclass(frozen=True)
class Receipt:
    tenant_id: str
    station_id: str
    correlation_id: str
    source_event_id: int
    trigger: Trigger
    actual_value: str
    component: str
    variable: str
    evse_id: int | None
    lockout: bool
    work_order_id: str | None
    status: Literal["diagnosed", "isolated", "open"]


@dataclass
class ReceiptStore:
    seen: set[tuple[str, str]] = field(default_factory=set)
    lockouts: set[tuple[str, str]] = field(default_factory=set)
    receipts: dict[tuple[str, str], Receipt] = field(default_factory=dict)


def is_diagnosis(row: NotifyEventRow) -> bool:
    if row.cleared:
        return False
    if row.trigger == "Alerting":
        return True
    if row.trigger == "Delta" and row.variable.name == "AvailabilityState" and row.actual_value in FAULTED_STATES:
        return True
    return False


def ingest(store: ReceiptStore, message: IncomingMessage) -> list[NotifyEventRow]:
    if message.protocol == "ocpp1.6" or message.action == "StatusNotification":
        raise ProtocolRejected("OCPP 1.6 StatusNotification is telemetry, not a Bayline receipt")
    if message.protocol not in {"ocpp2.1", "ocpp2.0.1"}:
        raise ProtocolRejected(f"unsupported protocol {message.protocol}")
    if message.action == "NotifyPeriodicEventStream":
        raise StreamIsNotAReceipt("NotifyPeriodicEventStream is Loadclear telemetry, not a work order")
    if message.action != "NotifyEvent":
        raise ProtocolRejected(f"action {message.action} is not a receipt source")
    key = (message.tenant_id, message.correlation_id)
    if key in store.seen:
        raise DuplicateEvent(message.correlation_id)
    store.seen.add(key)
    return [row for row in message.rows if is_diagnosis(row)]


def set_lockout(store: ReceiptStore, tenant_id: str, correlation_id: str) -> None:
    key = (tenant_id, correlation_id)
    if key not in store.seen:
        raise ReceiptError("no ingested event to isolate", code="missing_event")
    store.lockouts.add(key)


def open_work_order(
    store: ReceiptStore,
    message: IncomingMessage,
    row: NotifyEventRow,
    work_order_id: str,
) -> Receipt:
    key = (message.tenant_id, message.correlation_id)
    if key not in store.lockouts:
        raise LockoutRequired("torque/swap overlay and work order stay blocked until LOTO")
    receipt = Receipt(
        tenant_id=message.tenant_id,
        station_id=message.station_id,
        correlation_id=message.correlation_id,
        source_event_id=row.event_id,
        trigger=row.trigger,
        actual_value=row.actual_value,
        component=row.component.name,
        variable=row.variable.name,
        evse_id=row.component.evse_id,
        lockout=True,
        work_order_id=work_order_id,
        status="open",
    )
    store.receipts[key] = receipt
    return receipt

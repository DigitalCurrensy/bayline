"""The repair job is saved once."""
from platforms.bayline.src.application.outbox import (
    DuplicateOutboxEvent,
    MissingReceipt,
    Outbox,
    enqueue_work_order,
)
from platforms.bayline.src.application.receipt import (
    Component,
    IncomingMessage,
    NotifyEventRow,
    ReceiptStore,
    Variable,
    ingest,
    open_work_order,
    set_lockout,
)


def _open_receipt():
    store = ReceiptStore()
    row = NotifyEventRow(
        event_id=7,
        timestamp="2026-09-13T23:00:00Z",
        trigger="Alerting",
        actual_value="Faulted",
        component=Component("Connector", evse_id=1),
        variable=Variable("AvailabilityState"),
    )
    msg = IncomingMessage(
        tenant_id="t1",
        station_id="s1",
        correlation_id="corr-1",
        protocol="ocpp2.1",
        action="NotifyEvent",
        rows=(row,),
    )
    ingest(store, msg)
    set_lockout(store, "t1", "corr-1")
    return open_work_order(store, msg, row, "wo-1")


def test_enqueue_requires_work_order():
    try:
        enqueue_work_order(Outbox(), None, "evt-1")
        assert False
    except MissingReceipt:
        pass


def test_enqueue_idempotent_on_event_id():
    receipt = _open_receipt()
    box = Outbox()
    row = enqueue_work_order(box, receipt, "evt-1")
    assert row.work_order_id == "wo-1"
    assert box.by_event("t1", "evt-1") is row
    assert len(box.for_tenant("t1")) == 1
    try:
        enqueue_work_order(box, receipt, "evt-1")
        assert False
    except DuplicateOutboxEvent:
        pass

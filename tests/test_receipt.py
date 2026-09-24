"""A real fault is kept. An old message, a cleared fault, and a repeat are refused."""
try:
    from src.application.receipt import (
        Component,
        DuplicateEvent,
        IncomingMessage,
        LockoutRequired,
        NotifyEventRow,
        ProtocolRejected,
        ReceiptError,
        ReceiptStore,
        StreamIsNotAReceipt,
        Variable,
        ingest,
        open_work_order,
        set_lockout,
    )
except ImportError:
    from platforms.bayline.src.application.receipt import (
        Component,
        DuplicateEvent,
        IncomingMessage,
        LockoutRequired,
        NotifyEventRow,
        ProtocolRejected,
        ReceiptError,
        ReceiptStore,
        StreamIsNotAReceipt,
        Variable,
        ingest,
        open_work_order,
        set_lockout,
    )


def _row(trigger="Alerting", variable="Temperature", value="92", evse=1, cleared=False):
    return NotifyEventRow(
        event_id=1,
        timestamp="2026-09-13T01:00:00Z",
        trigger=trigger,
        actual_value=value,
        component=Component(name="EVSE", evse_id=evse),
        variable=Variable(name=variable),
        tech_code="ConnectorOverheat",
        cleared=cleared,
    )


def _msg(action="NotifyEvent", protocol="ocpp2.1", rows=(), correlation="c1"):
    return IncomingMessage(
        tenant_id="t1",
        station_id="s1",
        correlation_id=correlation,
        protocol=protocol,
        action=action,
        rows=rows,
    )


def test_alerting_is_diagnosis():
    store = ReceiptStore()
    rows = ingest(store, _msg(rows=(_row(),)))
    assert len(rows) == 1


def test_status_notification_rejected():
    store = ReceiptStore()
    try:
        ingest(store, _msg(action="StatusNotification", protocol="ocpp1.6"))
        assert False
    except ProtocolRejected:
        pass


def test_stream_is_not_a_receipt():
    store = ReceiptStore()
    try:
        ingest(store, _msg(action="NotifyPeriodicEventStream"))
        assert False
    except StreamIsNotAReceipt:
        pass


def test_work_order_requires_lockout():
    store = ReceiptStore()
    row = _row()
    msg = _msg(rows=(row,))
    ingest(store, msg)
    try:
        open_work_order(store, msg, row, "wo-1")
        assert False
    except LockoutRequired:
        pass
    set_lockout(store, "t1", "c1")
    receipt = open_work_order(store, msg, row, "wo-1")
    assert receipt.lockout is True
    assert receipt.work_order_id == "wo-1"


def test_faulted_state_change_is_kept():
    row = _row(trigger="Delta", variable="AvailabilityState", value="Faulted")
    rows = ingest(ReceiptStore(), _msg(rows=(row,), correlation="c2"))
    assert len(rows) == 1


def test_cleared_fault_is_not_kept():
    assert ingest(ReceiptStore(), _msg(rows=(_row(cleared=True),))) == []


def test_status_update_is_not_a_fault():
    assert ingest(ReceiptStore(), _msg(rows=(_row(trigger="Periodic"),))) == []


def test_same_fault_twice_is_one_record():
    store = ReceiptStore()
    ingest(store, _msg(rows=(_row(),)))
    try:
        ingest(store, _msg(rows=(_row(),)))
        assert False
    except DuplicateEvent:
        pass


def test_lock_without_a_fault_is_refused():
    try:
        set_lockout(ReceiptStore(), "t1", "missing")
        assert False
    except ReceiptError as error:
        assert error.code == "missing_event"


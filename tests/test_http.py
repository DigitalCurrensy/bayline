"""A posted fault becomes a repair job. A bad message is refused."""
from platforms.bayline.src.application.http import BadEnvelope, handle_notify_event
from platforms.bayline.src.application.outbox import Outbox
from platforms.bayline.src.application.receipt import (
    NotADiagnosis,
    ProtocolRejected,
    ReceiptStore,
    StreamIsNotAReceipt,
)


def _envelope(**overrides):
    body = {
        "tenant_id": "t1",
        "station_id": "s1",
        "correlation_id": "corr-1",
        "protocol": "ocpp2.1",
        "action": "NotifyEvent",
        "work_order_id": "wo-1",
        "event_id": "evt-wo",
        "payload": {
            "eventData": [
                {
                    "eventId": 7,
                    "timestamp": "2026-09-13T23:00:00Z",
                    "trigger": "Alerting",
                    "actualValue": "Faulted",
                    "component": {"name": "Connector", "evse": {"id": 1}},
                    "variable": {"name": "AvailabilityState"},
                }
            ]
        },
    }
    body.update(overrides)
    return body


def test_notify_event_opens_work_order_and_enqueues():
    store = ReceiptStore()
    box = Outbox()
    result = handle_notify_event(store, _envelope(), outbox=box)
    assert result.receipt.work_order_id == "wo-1"
    assert result.receipt.lockout is True
    assert result.diagnosed == 1
    assert result.outbox_row.work_order_id == "wo-1"
    assert box.by_event("t1", "evt-wo") is result.outbox_row


def test_missing_work_order_id_is_bad_envelope():
    store = ReceiptStore()
    body = _envelope()
    body.pop("work_order_id")
    try:
        handle_notify_event(store, body)
        assert False
    except BadEnvelope:
        pass


def test_stream_still_refused():
    store = ReceiptStore()
    try:
        handle_notify_event(store, _envelope(action="NotifyPeriodicEventStream"))
        assert False
    except StreamIsNotAReceipt:
        pass


def test_status_notification_still_refused():
    store = ReceiptStore()
    try:
        handle_notify_event(
            store, _envelope(action="StatusNotification", protocol="ocpp1.6")
        )
        assert False
    except ProtocolRejected:
        pass


def test_periodic_row_is_not_a_diagnosis():
    store = ReceiptStore()
    body = _envelope()
    body["payload"]["eventData"][0]["trigger"] = "Periodic"
    body["payload"]["eventData"][0]["actualValue"] = "Available"
    try:
        handle_notify_event(store, body)
        assert False
    except NotADiagnosis:
        pass

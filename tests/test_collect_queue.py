"""Tests for the Service Bus collection queue."""

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _reset_settings():
    from shared.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ── _post_to_service_bus ──────────────────────────────────────────


def test_post_to_service_bus_skipped_when_namespace_unset(monkeypatch):
    monkeypatch.setenv("SERVICE_BUS_NAMESPACE", "")
    from shared.config import get_settings

    get_settings.cache_clear()

    from routes import collect

    assert collect._post_to_service_bus("t1", "T", "D", 1) is False


def test_post_to_service_bus_sends_message(monkeypatch):
    monkeypatch.setenv("SERVICE_BUS_NAMESPACE", "fake.servicebus.windows.net")
    monkeypatch.setenv("SERVICE_BUS_QUEUE_NAME", "tenant-collect")
    from shared.config import get_settings

    get_settings.cache_clear()

    fake_sender = MagicMock()
    fake_client_inner = MagicMock()
    fake_client_inner.get_queue_sender.return_value.__enter__.return_value = fake_sender
    fake_client = MagicMock()
    fake_client.__enter__.return_value = fake_client_inner

    from routes import collect

    with (
        patch("azure.servicebus.ServiceBusClient", return_value=fake_client),
        patch("azure.identity.DefaultAzureCredential"),
    ):
        ok = collect._post_to_service_bus("11111111-1111-1111-1111-111111111111", "Test", "DOJ", 7)

    assert ok is True
    fake_sender.send_messages.assert_called_once()
    msg = fake_sender.send_messages.call_args.args[0]
    # Dedup contract: message_id is the tenant_id so duplicate-detection
    # within the configured window swallows accidental double-fires.
    assert msg.message_id == "11111111-1111-1111-1111-111111111111"


def test_post_to_service_bus_returns_false_on_failure(monkeypatch):
    monkeypatch.setenv("SERVICE_BUS_NAMESPACE", "fake.servicebus.windows.net")
    from shared.config import get_settings

    get_settings.cache_clear()

    from routes import collect

    with patch("azure.servicebus.ServiceBusClient", side_effect=RuntimeError("network down")):
        assert collect._post_to_service_bus("t1", "T", "D", 1) is False


# ── _trigger_collection_async fallback path ───────────────────────


def test_trigger_uses_service_bus_when_post_succeeds(monkeypatch):
    monkeypatch.setenv("SERVICE_BUS_NAMESPACE", "fake.servicebus.windows.net")
    from shared.config import get_settings

    get_settings.cache_clear()

    from routes import collect

    with (
        patch.object(collect, "_post_to_service_bus", return_value=True) as post,
        patch.object(collect._COLLECTION_EXECUTOR, "submit") as submit,
        patch.object(collect, "get_settings_or_settings", create=True),
    ):
        # Stub the inner settings access
        with patch("shared.config.get_settings") as gs:
            gs.return_value = MagicMock(
                COLLECTOR_CLIENT_ID="cid",
                COLLECTOR_CLIENT_SECRET="sec",
                COLLECTOR_AUDIT_LOG_DAYS=1,
            )
            collect._trigger_collection_async("t1", "T", "D")

    post.assert_called_once_with("t1", "T", "D", 1)
    submit.assert_not_called()


def test_trigger_falls_back_to_thread_when_post_fails(monkeypatch):
    from shared.config import get_settings

    get_settings.cache_clear()

    from routes import collect

    with (
        patch.object(collect, "_post_to_service_bus", return_value=False),
        patch.object(collect._COLLECTION_EXECUTOR, "submit") as submit,
        patch("shared.config.get_settings") as gs,
    ):
        gs.return_value = MagicMock(
            COLLECTOR_CLIENT_ID="cid",
            COLLECTOR_CLIENT_SECRET="sec",
            COLLECTOR_AUDIT_LOG_DAYS=1,
        )
        collect._trigger_collection_async("t1", "T", "D")

    submit.assert_called_once()


# ── process_collect_message handler ───────────────────────────────


def _fake_msg(body: dict, delivery_count: int = 1, message_id: str = "msg-1"):
    msg = MagicMock()
    msg.get_body.return_value = json.dumps(body).encode("utf-8")
    msg.delivery_count = delivery_count
    msg.message_id = message_id
    return msg


def test_queue_handler_calls_collect_single_tenant(monkeypatch):
    from routes import collect_queue
    from shared.config import get_settings

    monkeypatch.setenv("COLLECTOR_CLIENT_ID", "cid")
    monkeypatch.setenv("COLLECTOR_CLIENT_SECRET", "sec")
    get_settings.cache_clear()

    fn = collect_queue.bp._function_builders[0]._function._func
    msg = _fake_msg({"tenant_id": "t1", "display_name": "T", "department": "D", "audit_days": 7})

    with patch.object(collect_queue, "_collect_single_tenant", return_value={"status": "ok"}) as collect_call:
        fn(msg)

    collect_call.assert_called_once_with(
        tid="t1",
        display_name="T",
        department="D",
        client_id="cid",
        client_secret="sec",
        audit_days=7,
    )


def test_queue_handler_raises_on_collection_failure_for_redelivery(monkeypatch):
    from routes import collect_queue
    from shared.config import get_settings

    monkeypatch.setenv("COLLECTOR_CLIENT_ID", "cid")
    monkeypatch.setenv("COLLECTOR_CLIENT_SECRET", "sec")
    get_settings.cache_clear()

    fn = collect_queue.bp._function_builders[0]._function._func
    msg = _fake_msg({"tenant_id": "t1", "display_name": "T", "department": "D"})

    with patch.object(collect_queue, "_collect_single_tenant", return_value={"status": "error", "error": "boom"}):
        with pytest.raises(RuntimeError, match="Collection failed"):
            fn(msg)


def test_queue_handler_raises_when_credentials_missing(monkeypatch):
    monkeypatch.delenv("COLLECTOR_CLIENT_ID", raising=False)
    monkeypatch.delenv("COLLECTOR_CLIENT_SECRET", raising=False)
    from shared.config import get_settings

    get_settings.cache_clear()

    from routes import collect_queue

    fn = collect_queue.bp._function_builders[0]._function._func
    msg = _fake_msg({"tenant_id": "t1"})
    with pytest.raises(RuntimeError, match="credentials"):
        fn(msg)

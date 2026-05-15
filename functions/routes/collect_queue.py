"""Service Bus queue trigger for durable tenant-collection hand-off.

Replaces the in-process ``ThreadPoolExecutor`` that silently dropped work
on Function App instance recycle / scale-in.

Flow:

1. ``/api/tenants`` or ``/api/tenants/callback`` calls
   :func:`routes.collect.enqueue_collection` (refactored from
   ``_trigger_collection_async``).
2. ``enqueue_collection`` posts a JSON message to the
   ``tenant-collect`` queue: ``{"tenant_id", "display_name", "department"}``.
3. The Functions runtime invokes :func:`process_collect_message` for each
   message with at-least-once delivery. Service Bus retries up to
   ``maxDeliveryCount=5`` (configured in Bicep); after that the message
   moves to the dead-letter queue for operator review.
4. ``process_collect_message`` calls ``_collect_single_tenant``. On
   success the message is auto-completed; on exception Service Bus
   redelivers (with exponential backoff) until the limit.

Connection: identity-based via ``ServiceBus__fullyQualifiedNamespace``
app setting (set in Bicep). Function App MI has Data Sender + Receiver
roles at the namespace scope.

Local dev: when ``SERVICE_BUS_NAMESPACE`` is unset, the post step
no-ops and we fall back to the legacy ThreadPoolExecutor in
``routes.collect`` so ``func start`` continues to work.
"""

from __future__ import annotations

import json
import logging

import azure.functions as func

from routes.collect import _collect_single_tenant

log = logging.getLogger(__name__)

bp = func.Blueprint()


@bp.function_name("process_collect_message")
@bp.service_bus_queue_trigger(
    arg_name="msg",
    queue_name="%SERVICE_BUS_QUEUE_NAME%",
    connection="ServiceBus",
)
def process_collect_message(msg: func.ServiceBusMessage) -> None:
    """Pull one tenant-collection message and run the collector.

    Raises on failure so Service Bus delivers it again (up to
    maxDeliveryCount); after that the message is dead-lettered.
    """
    body = json.loads(msg.get_body().decode("utf-8"))
    tenant_id = body.get("tenant_id", "")
    display_name = body.get("display_name", "")
    department = body.get("department", "")
    audit_days = int(body.get("audit_days", 1))

    log.info(
        "process_collect_message: starting tenant=%s delivery_count=%s message_id=%s",
        tenant_id,
        msg.delivery_count,
        msg.message_id,
    )

    from shared.config import get_settings

    settings = get_settings()
    client_id = settings.COLLECTOR_CLIENT_ID
    client_secret = settings.COLLECTOR_CLIENT_SECRET

    if not client_id or not client_secret:
        # No credentials → permanent failure, send to DLQ via abandon.
        log.error("process_collect_message: COLLECTOR_CLIENT_ID/SECRET unset; tenant=%s", tenant_id)
        raise RuntimeError("Collector credentials not configured")

    result = _collect_single_tenant(
        tid=tenant_id,
        display_name=display_name,
        department=department,
        client_id=client_id,
        client_secret=client_secret,
        audit_days=audit_days,
    )

    if result.get("status") != "ok":
        # Raise so Service Bus retries; after maxDeliveryCount it
        # moves to the dead-letter queue.
        raise RuntimeError(f"Collection failed: {result.get('error', 'unknown')}")

    log.info("process_collect_message: completed tenant=%s", tenant_id)

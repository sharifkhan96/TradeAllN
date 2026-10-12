"""Fire-and-forget pushes to WebSocket groups from sync code."""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

log = logging.getLogger(__name__)


def _send(group: str, payload: dict):
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(group, {"type": "push", "payload": payload})
    except Exception:  # realtime is best-effort; never break a trade over it
        log.warning("push to %s failed", group, exc_info=True)


def notify_user(user_id: int, kind: str, data: dict):
    _send(f"user.{user_id}", {"type": kind, **data})


def broadcast_symbol(symbol: str, kind: str, data: dict):
    _send(f"ticker.{symbol}", {"type": kind, **data})


def broadcast_all(kind: str, data: dict):
    _send("market", {"type": kind, **data})

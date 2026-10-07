"""In-memory approval event manager for blocking wait/signal.

SQLite stores approval records; this module handles the async
blocking: request_approval creates an asyncio.Event and awaits it,
resolve_approval sets the event to unblock.
"""

import asyncio
import logging

from admiral_mcp.models import ApprovalDecision

logger = logging.getLogger(__name__)


class ApprovalEvents:
    def __init__(self) -> None:
        self._events: dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    async def create(self, approval_id: str) -> asyncio.Event:
        event = asyncio.Event()
        async with self._lock:
            self._events[approval_id] = event
        return event

    async def signal(self, approval_id: str, decision: ApprovalDecision) -> bool:
        async with self._lock:
            event = self._events.pop(approval_id, None)
        if event is None:
            return False
        event.set()
        return True

    async def wait(self, approval_id: str, timeout: int) -> ApprovalDecision:
        async with self._lock:
            event = self._events.get(approval_id)
        if event is None:
            return ApprovalDecision.TIMEOUT
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except TimeoutError:
            return ApprovalDecision.TIMEOUT
        return ApprovalDecision.TIMEOUT


_events: ApprovalEvents | None = None


def get_approval_events() -> ApprovalEvents:
    global _events
    if _events is None:
        _events = ApprovalEvents()
    return _events

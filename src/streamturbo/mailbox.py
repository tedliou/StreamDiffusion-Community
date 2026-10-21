"""Single-slot latest-frame mailbox (ADR-0003): a new item replaces any unread one."""

import threading


class Mailbox[T]:
    def __init__(self) -> None:
        self._item: T | None = None
        self._ready = threading.Condition()

    def put(self, item: T) -> bool:
        """Leave `item` for the reader. Returns True when it replaced an unread item."""
        with self._ready:
            replaced = self._item is not None
            self._item = item
            self._ready.notify()
            return replaced

    def take(self, timeout: float) -> T | None:
        """The newest item, or None when nothing arrived within `timeout` seconds."""
        with self._ready:
            self._ready.wait_for(lambda: self._item is not None, timeout)
            item, self._item = self._item, None
            return item

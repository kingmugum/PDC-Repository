from __future__ import annotations

import threading


class OperationLock:
    """Process-local lock shared by Git Manager and BoardRepo tabs."""

    def __init__(self):
        self._lock = threading.Lock()
        self._owner = None

    @property
    def owner(self):
        return self._owner

    def acquire(self, owner: str) -> bool:
        ok = self._lock.acquire(blocking=False)
        if ok:
            self._owner = owner
        return ok

    def release(self, owner: str) -> None:
        if self._owner != owner:
            return
        self._owner = None
        try:
            self._lock.release()
        except RuntimeError:
            pass

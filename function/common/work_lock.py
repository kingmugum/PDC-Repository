from __future__ import annotations

import threading


class OperationLock:
    """Process-local lock shared by Git Manager and BoardRepo tabs."""

    def __init__(self):
        self._lock = threading.Lock()
        self._owner = None
        self._listeners = []

    @property
    def owner(self):
        return self._owner

    def subscribe(self, listener) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)
        try:
            listener(self._owner)
        except Exception:
            pass

    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            try:
                listener(self._owner)
            except Exception:
                pass

    def acquire(self, owner: str) -> bool:
        ok = self._lock.acquire(blocking=False)
        if ok:
            self._owner = owner
            self._notify()
        return ok

    def release(self, owner: str) -> None:
        if self._owner != owner:
            return
        self._owner = None
        try:
            self._lock.release()
        except RuntimeError:
            pass
        self._notify()

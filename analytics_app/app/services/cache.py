from dataclasses import dataclass
from time import monotonic
from typing import Any


@dataclass
class CacheItem:
    value: Any
    expires_at: float


class TTLCache:
    def __init__(self, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds
        self._storage: dict[str, CacheItem] = {}

    def get(self, key: str) -> Any | None:
        item = self._storage.get(key)
        if item is None:
            return None

        if item.expires_at <= monotonic():
            self._storage.pop(key, None)
            return None

        return item.value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl_seconds
        self._storage[key] = CacheItem(
            value=value,
            expires_at=monotonic() + ttl,
        )

    def clear(self) -> None:
        self._storage.clear()

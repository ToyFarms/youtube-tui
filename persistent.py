from threading import Lock
from typing import Hashable, Self

import shelve
import atexit


class PersistentStorage:
    _instance: Self | None = None
    _lock: Lock = Lock()
    _db: shelve.Shelf[object] | None = None

    def __new__(cls, db_path: str = "appstate.db") -> Self:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._db = shelve.open(db_path)
                _ = atexit.register(cls._instance.close)
        return cls._instance

    def set(self, key: Hashable, value: object) -> None:
        if self._db is None:
            return

        print(key, value)
        self._db[str(key)] = value
        self._db.sync()

    def get[T](self, key: Hashable, default: T = None) -> object | T:
        if self._db is None:
            return default

        return self._db.get(str(key), default)

    def delete(self, key: Hashable) -> None:
        if self._db is None:
            return

        k = str(key)
        if k in self._db:
            del self._db[k]
            self._db.sync()

    def all_keys(self) -> list[Hashable]:
        if self._db is None:
            return []

        return list(self._db.keys())

    def all_values(self) -> list[object]:
        if self._db is None:
            return []

        return list(self._db.values())

    def items(self) -> dict[str, object]:
        if self._db is None:
            return {}

        return dict(self._db)

    def clear(self) -> None:
        if self._db is None:
            return

        self._db.clear()
        self._db.sync()

    def close(self) -> None:
        if self._db is None:
            return

        if hasattr(self, "_db") and self._db is not None:
            self._db.close()
            self._db = None


shared_db = PersistentStorage()

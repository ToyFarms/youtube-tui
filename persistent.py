from threading import Lock
from typing import Hashable, Self
from collections.abc import ItemsView

import shelve
import atexit

from utils import expect


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

        self._db[str(key)] = value
        self._db.sync()

    def get[T](self, key: Hashable, default: T) -> T:
        if self._db is None:
            return default

        v = expect(self._db.get(str(key), default), type(default))
        return v

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

    def items(self) -> ItemsView[str, object]:
        if self._db is None:
            return expect({}.items(), ItemsView[str, object])

        return dict(self._db).items()

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

    def __contains__(self, key: Hashable) -> bool:
        if not self._db:
            return False

        return str(key) in self._db


shared_db = PersistentStorage()

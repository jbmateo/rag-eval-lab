"""Content-addressed JSON cache on disk: one file per sha256 of the request payload."""
import hashlib
import json
from pathlib import Path


class DiskCache:
    def __init__(self, dir: Path):
        self.dir = Path(dir)

    @staticmethod
    def key(payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def _path(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def has(self, key: str) -> bool:
        return self.get(key) is not None

    def get(self, key: str) -> dict | None:
        try:
            return json.loads(self._path(key).read_text())
        except (OSError, ValueError):
            return None

    def put(self, key: str, value: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self._path(key).write_text(json.dumps(value, sort_keys=True, ensure_ascii=False))

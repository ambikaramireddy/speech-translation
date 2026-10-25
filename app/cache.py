import hashlib, sqlite3
from pathlib import Path

class Cache:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    @staticmethod
    def key(*parts: str) -> str:
        return hashlib.sha256("\0".join(parts).encode()).hexdigest()
    def get(self, key: str) -> str | None:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT value FROM cache WHERE key=?", (key,)).fetchone()
        return row[0] if row else None
    def put(self, key: str, value: str) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR REPLACE INTO cache VALUES (?,?)", (key, value))

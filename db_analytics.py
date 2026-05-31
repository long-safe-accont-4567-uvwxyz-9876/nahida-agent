import os
import aiosqlite
from loguru import logger


class DBAnalytics:

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._db = None

    async def init(self):
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._init_tables()
        logger.info("db_analytics.ready")

    async def _init_tables(self):
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                tags TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_analytics_name ON analytics(metric_name);
            CREATE INDEX IF NOT EXISTS idx_analytics_time ON analytics(created_at);
        """)
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()

    async def record(self, name: str, value: float, tags: str = ""):
        await self._db.execute(
            "INSERT INTO analytics (metric_name, metric_value, tags) VALUES (?, ?, ?)",
            (name, value, tags)
        )
        await self._db.commit()

    async def query(self, name: str, limit: int = 100) -> list:
        cursor = await self._db.execute(
            "SELECT metric_value, tags, created_at FROM analytics WHERE metric_name = ? ORDER BY id DESC LIMIT ?",
            (name, limit)
        )
        rows = await cursor.fetchall()
        return [{"value": r[0], "tags": r[1], "created_at": r[2]} for r in rows]

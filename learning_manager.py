import os
import json
import aiosqlite
from loguru import logger


class LearningManager:

    def __init__(self, db_path: str = "data/learning.db"):
        self._db_path = db_path
        self._db = None

    async def init(self):
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._init_tables()
        logger.info("learning_manager.ready")

    async def _init_tables(self):
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS learning (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT DEFAULT '',
                mastered BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_learning_category ON learning(category);
        """)
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()

    async def add(self, category: str, content: str, source: str = "") -> int:
        cursor = await self._db.execute(
            "INSERT INTO learning (category, content, source) VALUES (?, ?, ?)",
            (category, content, source)
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_by_category(self, category: str, limit: int = 20) -> list:
        cursor = await self._db.execute(
            "SELECT id, content, source, mastered, created_at FROM learning WHERE category = ? ORDER BY id DESC LIMIT ?",
            (category, limit)
        )
        rows = await cursor.fetchall()
        return [{"id": r[0], "content": r[1], "source": r[2], "mastered": r[3], "created_at": r[4]} for r in rows]

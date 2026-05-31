import os
import aiosqlite
from loguru import logger


class NotebookManager:

    def __init__(self, db_path: str = "data/notebook.db"):
        self._db_path = db_path
        self._db = None

    async def init(self):
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._init_tables()
        logger.info("notebook_manager.ready")

    async def _init_tables(self):
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS notebook (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                tags TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_notebook_category ON notebook(category);
            CREATE INDEX IF NOT EXISTS idx_notebook_tags ON notebook(tags);
        """)
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()

    async def add(self, title: str, content: str, category: str = "general", tags: str = "") -> int:
        cursor = await self._db.execute(
            "INSERT INTO notebook (title, content, category, tags) VALUES (?, ?, ?, ?)",
            (title, content, category, tags)
        )
        await self._db.commit()
        return cursor.lastrowid

    async def search(self, query: str, limit: int = 10) -> list:
        cursor = await self._db.execute(
            "SELECT id, title, content, category, tags, created_at FROM notebook WHERE title LIKE ? OR content LIKE ? ORDER BY updated_at DESC LIMIT ?",
            (f"%{query}%", f"%{query}%", limit)
        )
        rows = await cursor.fetchall()
        return [{"id": r[0], "title": r[1], "content": r[2], "category": r[3], "tags": r[4], "created_at": r[5]} for r in rows]

    async def get_all(self, limit: int = 50) -> list:
        cursor = await self._db.execute(
            "SELECT id, title, category, tags, created_at FROM notebook ORDER BY updated_at DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [{"id": r[0], "title": r[1], "category": r[2], "tags": r[3], "created_at": r[4]} for r in rows]

import os
import aiosqlite
from loguru import logger


class DBKnowledge:

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._db = None

    async def init(self):
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._init_tables()
        logger.info("db_knowledge.ready")

    async def _init_tables(self):
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT DEFAULT '',
                confidence REAL DEFAULT 0.5,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_knowledge_topic ON knowledge(topic);
        """)
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()

    async def add(self, topic: str, content: str, source: str = "", confidence: float = 0.5) -> int:
        cursor = await self._db.execute(
            "INSERT INTO knowledge (topic, content, source, confidence) VALUES (?, ?, ?, ?)",
            (topic, content, source, confidence)
        )
        await self._db.commit()
        return cursor.lastrowid

    async def search(self, topic: str, limit: int = 10) -> list:
        cursor = await self._db.execute(
            "SELECT id, topic, content, source, confidence, created_at FROM knowledge WHERE topic LIKE ? ORDER BY confidence DESC LIMIT ?",
            (f"%{topic}%", limit)
        )
        rows = await cursor.fetchall()
        return [{"id": r[0], "topic": r[1], "content": r[2], "source": r[3], "confidence": r[4], "created_at": r[5]} for r in rows]

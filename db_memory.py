import os
import aiosqlite
from loguru import logger


class DBMemory:

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._db = None

    async def init(self):
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._init_tables()
        logger.info("db_memory.ready")

    async def _init_tables(self):
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                tags TEXT DEFAULT '',
                importance REAL DEFAULT 0.5,
                access_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_input TEXT NOT NULL,
                assistant_reply TEXT NOT NULL,
                user_id TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_memories_tags ON memories(tags);
            CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);
        """)
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()

    async def add_memory(self, content: str, tags: str = "", importance: float = 0.5) -> int:
        cursor = await self._db.execute(
            "INSERT INTO memories (content, tags, importance) VALUES (?, ?, ?)",
            (content, tags, importance)
        )
        await self._db.commit()
        return cursor.lastrowid

    async def search(self, query: str, limit: int = 10) -> list:
        cursor = await self._db.execute(
            "SELECT id, content, tags, importance, created_at FROM memories WHERE content LIKE ? ORDER BY importance DESC LIMIT ?",
            (f"%{query}%", limit)
        )
        rows = await cursor.fetchall()
        return [{"id": r[0], "content": r[1], "tags": r[2], "importance": r[3], "created_at": r[4]} for r in rows]

    async def get_recent(self, limit: int = 10) -> list:
        cursor = await self._db.execute(
            "SELECT id, content, tags, importance, created_at FROM memories ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [{"id": r[0], "content": r[1], "tags": r[2], "importance": r[3], "created_at": r[4]} for r in rows]

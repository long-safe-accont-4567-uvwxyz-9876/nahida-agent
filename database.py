import os
import aiosqlite
from loguru import logger


class Database:

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._db = None

    async def init(self):
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA synchronous=NORMAL")
        await self._init_tables()
        logger.info("database.ready", path=self._db_path)

    async def _init_tables(self):
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                user_id TEXT,
                detail TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_log(event_type);
        """)
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()

    async def insert_message(self, session_id: str, role: str, content: str):
        await self._db.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content)
        )
        await self._db.commit()

    async def insert_audit_log(self, event_type: str, user_id: str, detail: str):
        await self._db.execute(
            "INSERT INTO audit_log (event_type, user_id, detail) VALUES (?, ?, ?)",
            (event_type, user_id, detail)
        )
        await self._db.commit()

    async def get_messages(self, session_id: str, limit: int = 50) -> list:
        cursor = await self._db.execute(
            "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        )
        rows = await cursor.fetchall()
        return [{"role": r[0], "content": r[1], "created_at": r[2]} for r in reversed(rows)]

import os
import json
from pathlib import Path
from loguru import logger


class KnowledgeGraph:

    def __init__(self, config: dict):
        self._config = config
        self._db_path = config.get("knowledge_db_path", "data/knowledge.db")
        self._db = None

    async def init(self):
        import aiosqlite
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._init_tables()
        logger.info("knowledge_graph.ready")

    async def _init_tables(self):
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                entity_type TEXT DEFAULT 'concept',
                properties TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                relation_type TEXT NOT NULL,
                properties TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES entities(id),
                FOREIGN KEY (target_id) REFERENCES entities(id)
            );
            CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
            CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id);
            CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id);
        """)
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()

    async def add_entity(self, name: str, entity_type: str = "concept", properties: dict = None) -> int:
        import json
        props = json.dumps(properties or {}, ensure_ascii=False)
        try:
            cursor = await self._db.execute(
                "INSERT OR IGNORE INTO entities (name, entity_type, properties) VALUES (?, ?, ?)",
                (name, entity_type, props)
            )
            await self._db.commit()
            if cursor.lastrowid:
                return cursor.lastrowid
            cursor = await self._db.execute("SELECT id FROM entities WHERE name = ?", (name,))
            row = await cursor.fetchone()
            return row[0] if row else 0
        except Exception as e:
            logger.warning("knowledge_graph.add_entity_failed", error=str(e))
            return 0

    async def add_relation(self, source_name: str, target_name: str, relation_type: str, properties: dict = None) -> bool:
        source_id = await self.add_entity(source_name)
        target_id = await self.add_entity(target_name)
        if not source_id or not target_id:
            return False
        import json
        props = json.dumps(properties or {}, ensure_ascii=False)
        await self._db.execute(
            "INSERT INTO relations (source_id, target_id, relation_type, properties) VALUES (?, ?, ?, ?)",
            (source_id, target_id, relation_type, props)
        )
        await self._db.commit()
        return True

    async def query(self, entity_name: str, depth: int = 1) -> dict:
        cursor = await self._db.execute("SELECT id, name, entity_type, properties FROM entities WHERE name = ?", (entity_name,))
        entity = await cursor.fetchone()
        if not entity:
            return {"entity": entity_name, "relations": []}
        entity_id = entity[0]
        cursor = await self._db.execute("""
            SELECT r.relation_type, e.name, e.entity_type
            FROM relations r
            JOIN entities e ON r.target_id = e.id
            WHERE r.source_id = ?
        """, (entity_id,))
        relations = [{"type": r[0], "target": r[1], "target_type": r[2]} for r in await cursor.fetchall()]
        return {
            "entity": entity[1],
            "entity_type": entity[2],
            "relations": relations,
        }

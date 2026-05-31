import os
import sys
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

BASE_DIR = Path(__file__).parent

MEMORY_PERSONALITY = BASE_DIR / "config" / "workspace" / "IDENTITY.md"
MEMORY_SOUL = BASE_DIR / "config" / "workspace" / "SOUL.md"
AGENT_CONFIG = BASE_DIR / "config" / "agent.json5"

PERSONALITY_FILES = {
    "nahida": BASE_DIR / "nahida_personality.md",
    "klee": BASE_DIR / "klee_personality.md",
    "yinlang": BASE_DIR / "yinlang_personality.md",
    "xilian": BASE_DIR / "xilian_personality.md",
    "nico": BASE_DIR / "nike_personality.md",
}

type SafetyLevel = str


def load_config() -> dict:
    mimo_api_key = os.getenv("MIMO_API_KEY", "")
    mimo_base_url = os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
    mimo_model = os.getenv("MIMO_MODEL_NAME", "mimo-v2.5")
    mimo_pro_model = os.getenv("MIMO_PRO_MODEL_NAME", "mimo-v2.5-pro")

    owner_ids_raw = os.getenv("OWNER_IDS", "")
    owner_ids = [oid.strip() for oid in owner_ids_raw.split(",") if oid.strip()]

    agent_name = os.getenv("AGENT_NAME", "nahida").strip().lower()
    if agent_name not in PERSONALITY_FILES:
        agent_name = "nahida"

    data_dir = os.getenv("KIOXIA_DATA_DIR", "")
    if data_dir and Path(data_dir).is_dir():
        db_path = Path(data_dir) / "agent.db"
        file_dir = Path(data_dir) / "files"
    else:
        db_path = BASE_DIR / "data" / "agent.db"
        file_dir = BASE_DIR / "data" / "files"

    return {
        "mimo_api_key": mimo_api_key,
        "mimo_base_url": mimo_base_url,
        "mimo_model": mimo_model,
        "mimo_pro_model": mimo_pro_model,
        "owner_ids": owner_ids,
        "agent_name": agent_name,
        "personality_file": PERSONALITY_FILES.get(agent_name, PERSONALITY_FILES["nahida"]),
        "db_path": db_path,
        "file_dir": file_dir,
        "base_dir": BASE_DIR,
        "memory_personality": MEMORY_PERSONALITY,\n        "memory_soul": MEMORY_SOUL,
        "agent_config": AGENT_CONFIG,
        "embed_api_key": os.getenv("EMBED_API_KEY", ""),
        "embed_base_url": os.getenv("EMBED_BASE_URL", ""),
        "embed_model": os.getenv("EMBED_MODEL", ""),
        "imgbb_api_key": os.getenv("IMGBB_API_KEY", ""),
        "tavily_api_key": os.getenv("TAVILY_API_KEY", ""),
        "siliconflow_api_key": os.getenv("SILICONFLOW_API_KEY", ""),
        "openrouter_api_key": os.getenv("OPENROUTER_API_KEY", ""),
        "qqbot_app_id": os.getenv("QQBOT_APP_ID", ""),
        "qqbot_app_secret": os.getenv("QQBOT_APP_SECRET", ""),
        "nudge_enabled": os.getenv("NUDGE_ENABLED", "true").lower() == "true",
        "nudge_user_openid": os.getenv("NUDGE_USER_OPENID", ""),
        "nudge_greeting_threshold": int(os.getenv("NUDGE_GREETING_THRESHOLD", "3600")),
        "nudge_dnd_start": int(os.getenv("NUDGE_DND_START", "23")),
        "nudge_dnd_end": int(os.getenv("NUDGE_DND_END", "7")),
    }


def build_system_prompt(cfg: dict, personality_override: str | None = None) -> str:
    personality_file = personality_override or cfg.get("personality_file")
    if personality_file and Path(personality_file).is_file():
        return Path(personality_file).read_text(encoding="utf-8").strip()
    return "你是纳西妲，须弥的草神，智慧之神。温柔、善良、充满好奇心。"


def _load_json5(path: Path) -> dict:
    if not path.is_file():
        return {}
    raw = path.read_text(encoding="utf-8")
    import re
    raw = re.sub(r'//.*?\n', '\n', raw)
    raw = re.sub(r'/\*.*?\*/', '', raw, flags=re.DOTALL)
    raw = re.sub(r',\s*([}\]])', r'\1', raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("config.json5_parse_failed", path=str(path))
        return {}


def get_agent_config() -> dict:
    return _load_json5(AGENT_CONFIG)

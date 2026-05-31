import os
from dotenv import load_dotenv

load_dotenv()


def load_config() -> dict:
    config = {
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "base_url": os.getenv("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1"),
        "model_name": os.getenv("MODEL_NAME", "Qwen/Qwen3-8B"),
        "model_name_pro": os.getenv("MODEL_NAME_PRO", "MiMo/MiMo-V2.5-Pro"),
        "api_key_pro": os.getenv("OPENAI_API_KEY_PRO", ""),
        "base_url_pro": os.getenv("OPENAI_BASE_URL_PRO", ""),
        "owner_qq": os.getenv("OWNER_QQ", ""),
        "app_id": os.getenv("APP_ID", ""),
        "app_secret": os.getenv("APP_SECRET", ""),
        "embed_api_key": os.getenv("EMBED_API_KEY", ""),
        "embed_base_url": os.getenv("EMBED_BASE_URL", "https://api.siliconflow.cn/v1"),
        "embed_model": os.getenv("EMBED_MODEL", "BAAI/bge-m3"),
        "db_path": os.getenv("DB_PATH", "data/nahida.db"),
        "memory_db_path": os.getenv("MEMORY_DB_PATH", "data/memory.db"),
        "knowledge_db_path": os.getenv("KNOWLEDGE_DB_PATH", "data/knowledge.db"),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "owner_ids": [x.strip() for x in os.getenv("OWNER_IDS", "").split(",") if x.strip()],
        "max_context": int(os.getenv("MAX_CONTEXT", "50")),
        "max_tokens": int(os.getenv("MAX_TOKENS", "4096")),
        "temperature": float(os.getenv("TEMPERATURE", "0.7")),
        "web_port": int(os.getenv("WEB_PORT", "5000")),
        "web_host": os.getenv("WEB_HOST", "0.0.0.0"),
    }
    if not config["owner_ids"] and config["owner_qq"]:
        config["owner_ids"].append(config["owner_qq"])
    return config

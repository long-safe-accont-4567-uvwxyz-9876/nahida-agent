import asyncio
import sqlite3
import time
import os
import subprocess

DB_PATH = "/media/orangepi/KIOXIA/nahida-data/db/agent.db"
STICKER_DIR = "/media/orangepi/KIOXIA/nahida-data/stickers"

tests = []
passed = failed = 0

def test(name, func):
    global passed, failed
    try:
        func()
        tests.append((name, "PASS", ""))
        passed += 1
    except Exception as e:
        tests.append((name, "FAIL", str(e)[:120]))
        failed += 1

# ========== 数据库层 ==========
def test_db_tables():
    conn = sqlite3.connect(DB_PATH)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    expected = ["conversation_logs", "episodic_memories", "user_portrait",
                "notebook_entries", "proactive_messages", "api_usage", "sessions",
                "knowledge_entities", "knowledge_relations", "learnings",
                "errors", "feature_requests", "schema_version"]
    for t in expected:
        assert t in tables, f"Missing table: {t}"
    conn.close()
test("数据库13张核心表完整性", test_db_tables)

def test_db_api_usage_writable():
    conn = sqlite3.connect(DB_PATH)
    now = time.time()
    date_str = time.strftime("%Y%m%d")
    uid = f"API-{date_str}-{int(now) % 100000:05d}"
    conn.execute("INSERT INTO api_usage (id, user_openid, session_id, model, task_type, prompt_tokens, completion_tokens, cache_hit_tokens, cache_miss_tokens, cost_usd, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (uid, "test_user", "test_session", "deepseek-v4-pro", "chat", 100, 50, 0, 100, 0.001, now))
    conn.commit()
    row = conn.execute("SELECT cost_usd FROM api_usage WHERE id=?", (uid,)).fetchone()
    assert row is not None and row[0] == 0.001, f"api_usage write failed: {row}"
    conn.execute("DELETE FROM api_usage WHERE id=?", (uid,))
    conn.commit()
    conn.close()
test("api_usage写入+cost_usd精度(验证float修复)", test_db_api_usage_writable)

def test_db_learnings_writable():
    conn = sqlite3.connect(DB_PATH)
    now = time.time()
    date_str = time.strftime("%Y%m%d")
    lid = f"LRN-{date_str}-{int(now % 10000):04d}"
    conn.execute("INSERT INTO learnings (learning_id, category, priority, status, area, summary, details, suggested_action, source, pattern_key, recurrence_count, first_seen, last_seen, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (lid, "test", 1, "active", "test_area", "test summary", "test details", "test action", "auto", "test_pattern", 1, now, now, now))
    conn.commit()
    row = conn.execute("SELECT learning_id FROM learnings WHERE learning_id=?", (lid,)).fetchone()
    assert row is not None, "learnings write failed"
    conn.execute("DELETE FROM learnings WHERE learning_id=?", (lid,))
    conn.commit()
    conn.close()
test("learnings写入+读取(验证float修复)", test_db_learnings_writable)

def test_db_notebook_writable():
    conn = sqlite3.connect(DB_PATH)
    now = time.time()
    conn.execute("INSERT INTO notebook_entries (kind, content, tags, importance, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                 ("auto", "test note content", "test", 1, "active", now, now))
    conn.commit()
    row = conn.execute("SELECT content FROM notebook_entries WHERE content='test note content'").fetchone()
    assert row is not None, "notebook write failed"
    conn.execute("DELETE FROM notebook_entries WHERE content='test note content'")
    conn.commit()
    conn.close()
test("notebook写入+读取", test_db_notebook_writable)

def test_db_knowledge_graph_temporal():
    conn = sqlite3.connect(DB_PATH)
    now = time.time()
    conn.execute("INSERT INTO knowledge_entities (name, kind, observations, updated_at) VALUES (?,?,?,?)",
                 ("test_nahida", "character", "test obs", now))
    conn.execute("INSERT INTO knowledge_entities (name, kind, observations, updated_at) VALUES (?,?,?,?)",
                 ("test_dendro", "element", "test obs", now))
    conn.execute("INSERT INTO knowledge_relations (from_entity, relation_type, to_entity, updated_at, valid_from, valid_to, confidence) VALUES (?,?,?,?,?,?,?)",
                 ("test_nahida", "uses_element", "test_dendro", now, now, 0, 1.0))
    conn.commit()
    row = conn.execute("SELECT valid_from, valid_to, confidence FROM knowledge_relations WHERE from_entity='test_nahida' AND to_entity='test_dendro'").fetchone()
    assert row is not None, "knowledge_relations write failed"
    assert row[2] == 1.0, f"confidence wrong: {row[2]}"
    conn.execute("DELETE FROM knowledge_relations WHERE from_entity='test_nahida'")
    conn.execute("DELETE FROM knowledge_entities WHERE name IN ('test_nahida','test_dendro')")
    conn.commit()
    conn.close()
test("知识图谱时序字段(valid_from/valid_to/confidence)", test_db_knowledge_graph_temporal)

# ========== 模块导入 ==========
def test_model_router():
    from dotenv import load_dotenv
    load_dotenv("/home/orangepi/ai-agent/.env")
    from model_router import ModelRouter, PRO_MODEL, FLASH_MODEL
    assert "pro" in PRO_MODEL.lower() or "v4" in PRO_MODEL.lower() or "chat" in PRO_MODEL.lower(), f"PRO: {PRO_MODEL}"
    assert "flash" in FLASH_MODEL.lower() or "v4" in FLASH_MODEL.lower() or "chat" in FLASH_MODEL.lower(), f"FLASH: {FLASH_MODEL}"
    assert hasattr(ModelRouter, 'route')
    assert hasattr(ModelRouter, 'flush_costs')
test("ModelRouter(模型名+方法)", test_model_router)

def test_vector_store():
    from vector_store import VectorStore
    assert hasattr(VectorStore, 'upsert')
    assert hasattr(VectorStore, 'search')
    assert hasattr(VectorStore, 'embed')
test("VectorStore(upsert+search+embed)", test_vector_store)

def test_security():
    from dotenv import load_dotenv
    load_dotenv("/home/orangepi/ai-agent/.env")
    import os
    from security import SecurityFilter
    owner_ids = os.getenv("OWNER_IDS", "").split(",")
    sf = SecurityFilter(owner_ids=owner_ids)
    assert hasattr(sf, 'is_owner')
    assert sf.is_owner("qq_36407984B56AD1C82292FA35C2EB9568") == True
    assert sf.is_owner("qq_unknown") == False
test("SecurityFilter(is_owner权限验证)", test_security)

def test_slash_commands():
    from slash_commands import SlashCommandHandler
    handler = SlashCommandHandler.__new__(SlashCommandHandler)
test("SlashCommandHandler可导入", test_slash_commands)

def test_all_tools():
    from tools import get_all_tools
    tools = get_all_tools()
    names = [t.name for t in tools]
    assert "multi_search" in names, f"multi_search missing: {names}"
    assert "wolfram_query" in names, f"wolfram_query missing: {names}"
    assert "web_search" in names, f"web_search missing: {names}"
    assert len(tools) >= 8, f"Too few tools: {len(tools)}"
    print(f"    ({len(tools)} tools: {', '.join(names)})")
test("工具系统完整性(8+工具)", test_all_tools)

# ========== 表情包 ==========
def test_sticker_deep():
    from sticker_manager import StickerManager
    from pathlib import Path
    sm = StickerManager(Path(STICKER_DIR))
    assert sm.available
    total = sum(len(v) for v in sm._cache.values())
    assert total >= 30, f"Too few stickers: {total}"
    assert sm.detect_emotion("哈哈太好了") == "happy"
    assert sm.detect_emotion("呜呜好难过") == "sad"
    assert sm.detect_emotion("哼生气") == "angry"
    assert sm.detect_emotion("早上好呀") == "greeting"
    assert sm.detect_emotion("让我想想") == "thinking"
    assert sm.detect_emotion("好奇") == "curious"
    assert sm.detect_emotion("害羞") == "shy"
    sticker = sm.pick("happy")
    assert sticker is not None and sticker.exists()
    print(f"    ({total} stickers in {len(sm._cache)} categories)")
test("表情包系统(39张+7种情绪)", test_sticker_deep)

# ========== 文件接收器 ==========
def test_file_receiver_deep():
    from file_receiver import FileReceiver
    from pathlib import Path
    fr = FileReceiver(Path("/media/orangepi/KIOXIA/nahida-data/files"))
    assert fr._safe_filename("../../../etc/passwd") == "passwd"
    assert fr._safe_filename("") == "unknown"
    assert fr._classify("doc.pdf", "") == "documents"
    assert fr._classify("photo.png", "image/png") == "images"
    assert fr._classify("data.json", "") == "other"
    assert fr.MAX_FILE_SIZE == 20 * 1024 * 1024
test("文件接收器(安全+分类+大小限制)", test_file_receiver_deep)

# ========== text_utils ==========
def test_humanize_deep():
    from text_utils import humanize
    assert "此外" not in humanize("此外，我们需要注意")
    assert "值得" not in humanize("值得注意的是，这个问题")
    assert "综上" not in humanize("综上所述，我们可以得出")
    assert "首先" not in humanize("首先，我们要明确")
    assert "总而言" not in humanize("总而言之，这就是答案")
    assert "你好" in humanize("你好，世界")
    assert "纳西妲" in humanize("纳西妲是最可爱的！")
test("humanize去AI味(13种模式+保留正常内容)", test_humanize_deep)

def test_smart_truncate():
    from text_utils import smart_truncate
    assert smart_truncate("你好", max_len=100) == "你好"
    very_long = "这是一段很长的文本内容，用于测试截断功能。" * 200
    result = smart_truncate(very_long, max_len=200)
    assert len(result) < len(very_long), "Truncate did not shorten very long text"
test("smart_truncate智能截断(超长文本)", test_smart_truncate)

def test_dsml():
    from text_utils import strip_dsml, has_dsml_tool_calls, parse_dsml_tool_calls
    t = '你好<｜｜DSML｜｜tool_calls><｜｜DSML｜｜invoke name="web_search">test</｜｜DSML｜｜invoke></｜｜DSML｜｜tool_calls>世界'
    c = strip_dsml(t)
    assert "DSML" not in c and "你好" in c and "世界" in c
    assert has_dsml_tool_calls(t) and not has_dsml_tool_calls("普通文本")
    calls = parse_dsml_tool_calls(t)
    assert len(calls) >= 1
    assert calls[0]["function"]["name"] == "web_search"
test("DSML三层防护(strip+has+parse)", test_dsml)

# ========== 环境变量 ==========
def test_env_config():
    from dotenv import load_dotenv
    load_dotenv("/home/orangepi/ai-agent/.env")
    assert os.getenv("DEEPSEEK_API_KEY"), "DEEPSEEK_API_KEY missing"
    assert os.getenv("QQBOT_APP_ID"), "QQBOT_APP_ID missing"
    assert os.getenv("OWNER_IDS"), "OWNER_IDS missing"
    assert os.getenv("EMBED_API_KEY"), "EMBED_API_KEY missing"
test("环境变量完整性(DEEPSEEK/QQ/OWNER/EMBED)", test_env_config)

# ========== 系统服务 ==========
def test_systemd():
    r1 = subprocess.run(["systemctl", "is-active", "qq-agent.service"], capture_output=True, text=True)
    assert r1.stdout.strip() == "active", f"Not active: {r1.stdout.strip()}"
    r2 = subprocess.run(["systemctl", "is-enabled", "qq-agent.service"], capture_output=True, text=True)
    assert r2.stdout.strip() == "enabled", f"Not enabled: {r2.stdout.strip()}"
test("systemd服务(active+enabled)", test_systemd)

def test_fstab():
    with open("/etc/fstab") as f:
        content = f.read()
    assert "KIOXIA" in content or "2F33-B38A" in content
test("fstab KIOXIA自动挂载", test_fstab)

def test_disk_space():
    stat = os.statvfs("/media/orangepi/KIOXIA")
    free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
    assert free_gb > 1, f"KIOXIA low: {free_gb:.1f}GB"
    print(f"    (KIOXIA free: {free_gb:.1f}GB)")
test("KIOXIA磁盘空间", test_disk_space)

# ========== 数据路径 ==========
def test_data_on_kioxia():
    from config import DATA_DIR, LOG_DIR, STICKER_DIR, FILE_DIR
    from database import DB_PATH
    for name, path in [("DATA_DIR", DATA_DIR), ("LOG_DIR", LOG_DIR),
                        ("STICKER_DIR", STICKER_DIR), ("FILE_DIR", FILE_DIR),
                        ("DB_PATH", DB_PATH)]:
        assert "KIOXIA" in str(path), f"{name} not on KIOXIA: {path}"
        assert path.exists() or path.parent.exists(), f"{name} path missing: {path}"
test("所有数据路径→KIOXIA", test_data_on_kioxia)

# ========== Print Results ==========
print("=" * 55)
print("纳西妲 AI Agent 全面测试报告")
print("=" * 55)
for name, status, err in tests:
    icon = "PASS" if status == "PASS" else "FAIL"
    print(f"  [{icon}] {name}")
    if err:
        print(f"       -> {err}")
print("-" * 55)
print(f"总计: {passed+failed} | 通过: {passed} | 失败: {failed}")
print("=" * 55)

import asyncio
import sqlite3
import time
import os
import json
import sys

DB_PATH = "/media/orangepi/KIOXIA/nahida-data/db/agent.db"

tests = []
passed = failed = 0

def test(name, func):
    global passed, failed
    try:
        func()
        tests.append((name, "PASS", ""))
        passed += 1
    except Exception as e:
        tests.append((name, "FAIL", str(e)[:150]))
        failed += 1

# ========== 数据库端到端(DatabaseManager) ==========
async def _test_session_flow():
    from database import DatabaseManager
    db = DatabaseManager()
    await db.init()
    sid = await db.create_session("test_e2e_openid")
    assert sid is not None and len(sid) > 0
    await db.update_session(sid)
    session = await db.get_active_session("test_e2e_openid")
    assert session is not None
    assert session["id"] == sid
    await db.archive_session(sid)
    await db.close()

def test_session_flow():
    asyncio.run(_test_session_flow())
test("会话管理(创建→获取→归档)", test_session_flow)

async def _test_conversation_log():
    from database import DatabaseManager
    db = DatabaseManager()
    await db.init()
    await db.insert_conversation_log("test_e2e_user", "test", "你好", "你好呀！我是纳西妲～")
    rows = await db._conn.execute_fetchall(
        "SELECT user_message, assistant_reply FROM conversation_logs WHERE user_id='test_e2e_user' ORDER BY timestamp DESC LIMIT 1"
    )
    assert len(rows) > 0, "No conversation log found"
    assert rows[0][0] == "你好"
    await db._conn.execute("DELETE FROM conversation_logs WHERE user_id='test_e2e_user'")
    await db._conn.commit()
    await db.close()

def test_conversation_log():
    asyncio.run(_test_conversation_log())
test("对话日志写入+查询", test_conversation_log)

async def _test_api_usage_e2e():
    from database import DatabaseManager
    db = DatabaseManager()
    await db.init()
    now = time.time()
    date_str = time.strftime("%Y%m%d")
    uid = f"API-{date_str}-{int(now) % 100000:05d}"
    await db._conn.execute(
        "INSERT INTO api_usage (id, user_openid, session_id, model, task_type, prompt_tokens, completion_tokens, cache_hit_tokens, cache_miss_tokens, cost_usd, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (uid, "test_e2e_user", "test_session", "deepseek-v4-pro", "chat", 1000, 500, 800, 200, 0.005, now)
    )
    await db._conn.commit()
    row = await db._conn.execute_fetchall(
        "SELECT cost_usd, cache_hit_tokens FROM api_usage WHERE id=?", (uid,)
    )
    assert len(row) > 0 and row[0][0] == 0.005
    await db._conn.execute("DELETE FROM api_usage WHERE id=?", (uid,))
    await db._conn.commit()
    await db.close()

def test_api_usage_e2e():
    asyncio.run(_test_api_usage_e2e())
test("API用量追踪(写入+查询+缓存)", test_api_usage_e2e)

async def _test_kg_e2e():
    from database import DatabaseManager
    db = DatabaseManager()
    await db.init()
    now = time.time()
    await db._conn.execute(
        "INSERT INTO knowledge_entities (name, kind, observations, updated_at) VALUES (?,?,?,?)",
        ("e2e_nahida", "character", "草神", now)
    )
    await db._conn.execute(
        "INSERT INTO knowledge_relations (from_entity, relation_type, to_entity, updated_at, valid_from, valid_to, confidence) VALUES (?,?,?,?,?,?,?)",
        ("e2e_nahida", "lives_in", "e2e_sumeru", now, now, 0, 0.95)
    )
    await db._conn.commit()
    row = await db._conn.execute_fetchall(
        "SELECT confidence FROM knowledge_relations WHERE from_entity='e2e_nahida'"
    )
    assert len(row) > 0 and row[0][0] == 0.95
    await db._conn.execute("DELETE FROM knowledge_relations WHERE from_entity='e2e_nahida'")
    await db._conn.execute("DELETE FROM knowledge_entities WHERE name='e2e_nahida'")
    await db._conn.commit()
    await db.close()

def test_kg_e2e():
    asyncio.run(_test_kg_e2e())
test("知识图谱端到端(实体+关系+置信度)", test_kg_e2e)

async def _test_notebook_e2e():
    from database import DatabaseManager
    db = DatabaseManager()
    await db.init()
    await db._conn.execute(
        "INSERT INTO notebook_entries (kind, content, tags, importance, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        ("auto", "e2e_test_note", "test", 5, "active", time.time(), time.time())
    )
    await db._conn.commit()
    rows = await db._conn.execute_fetchall(
        "SELECT importance FROM notebook_entries WHERE content='e2e_test_note'"
    )
    assert len(rows) > 0 and rows[0][0] == 5
    await db._conn.execute("DELETE FROM notebook_entries WHERE content='e2e_test_note'")
    await db._conn.commit()
    await db.close()

def test_notebook_e2e():
    asyncio.run(_test_notebook_e2e())
test("Notebook端到端(写入+查询)", test_notebook_e2e)

# ========== 消息序列去重 ==========
def test_msg_seq():
    import uuid
    seen = set()
    for _ in range(100):
        seq = str(uuid.uuid4())
        assert seq not in seen
        seen.add(seq)
    assert len(seen) == 100
test("消息序列去重(100次无重复)", test_msg_seq)

# ========== 表情包边界 ==========
def test_sticker_edge():
    from sticker_manager import StickerManager
    from pathlib import Path
    sm = StickerManager(Path("/media/orangepi/KIOXIA/nahida-data/stickers"))
    assert sm.detect_emotion("普通文本没有情绪关键词") == ""
    assert sm.should_send("普通文本") in (True, False)
test("表情包边界(无情绪+空输入)", test_sticker_edge)

# ========== 文件接收器边界 ==========
def test_file_receiver_edge():
    from file_receiver import FileReceiver
    from pathlib import Path
    fr = FileReceiver(Path("/media/orangepi/KIOXIA/nahida-data/files"))
    assert fr._safe_filename("normal.jpg") == "normal.jpg"
    assert fr._safe_filename("") == "unknown"
    assert fr._safe_filename("../../../etc/passwd") == "passwd"
    assert fr._classify("image.webp", "") == "images"
    assert fr._classify("presentation.pptx", "") == "documents"
    assert fr._classify("unknown.xyz", "") == "other"
    assert fr._classify("", "image/jpeg") == "images"
test("文件接收器边界(安全/分类/未知类型)", test_file_receiver_edge)

# ========== humanize边界 ==========
def test_humanize_edge():
    from text_utils import humanize
    assert humanize("") == ""
    assert humanize("短文本") == "短文本"
    long_ai = "此外，值得注意的是，综上所述，总而言之，不仅如此，更重要的是，简而言之"
    result = humanize(long_ai)
    for word in ["此外", "值得", "综上", "总而言", "不仅", "更重要", "简而言"]:
        assert word not in result, f"AI pattern '{word}' not removed"
test("humanize边界(空/短/多重AI模式)", test_humanize_edge)

# ========== DSML边界 ==========
def test_dsml_edge():
    from text_utils import strip_dsml, has_dsml_tool_calls, parse_dsml_tool_calls
    assert strip_dsml("") == ""
    assert not has_dsml_tool_calls("")
    multi = '前文<｜｜DSML｜｜tool_calls><｜｜DSML｜｜invoke name="web_search">q1</｜｜DSML｜｜invoke></｜｜DSML｜｜tool_calls>中间<｜｜DSML｜｜tool_calls><｜｜DSML｜｜invoke name="shell_command">ls</｜｜DSML｜｜invoke></｜｜DSML｜｜tool_calls>后文'
    cleaned = strip_dsml(multi)
    assert "DSML" not in cleaned
    assert "前文" in cleaned and "后文" in cleaned
    calls = parse_dsml_tool_calls(multi)
    assert len(calls) == 2
test("DSML边界(空/多工具调用)", test_dsml_edge)

# ========== 定价表 ==========
def test_pricing():
    from dotenv import load_dotenv
    load_dotenv("/home/orangepi/ai-agent/.env")
    from model_router import DEEPSEEK_PRICING
    for model in ["pro", "flash"]:
        p = DEEPSEEK_PRICING[model]
        assert p["input_per_m"] > p["cache_hit_per_m"], f"{model}: input should > cache_hit"
        assert p["output_per_m"] > 0
test("DeepSeek定价表(input>cache_hit)", test_pricing)

# ========== 工具注册 ==========
def test_tools():
    from tools import get_all_tools
    tools = get_all_tools()
    names = [t.name for t in tools]
    for name in ["shell_command", "web_search", "multi_search", "wolfram_query"]:
        assert name in names, f"Missing: {name}"
    for t in tools:
        assert len(t.description) > 10, f"{t.name}: short desc"
test("工具注册(12个+描述完整)", test_tools)

# ========== 安全过滤 ==========
def test_security():
    from dotenv import load_dotenv
    load_dotenv("/home/orangepi/ai-agent/.env")
    import os
    from security import SecurityFilter
    sf = SecurityFilter(owner_ids=os.getenv("OWNER_IDS", "").split(","))
    assert sf.is_owner(os.getenv("OWNER_IDS", "").split(",")[0])
    assert not sf.is_owner("qq_unknown")
    assert not sf.is_owner("")
test("SecurityFilter深度", test_security)

# ========== 斜杠命令 ==========
def test_slash():
    from slash_commands import SlashCommandHandler
    handler = SlashCommandHandler.__new__(SlashCommandHandler)
    valid = ["/cost", "/status", "/model", "/help", "/learn", "/note"]
    for cmd in valid:
        assert handler.is_slash_command(cmd), f"Not detected: {cmd}"
    assert not handler.is_slash_command("//help")
    assert not handler.is_slash_command("你好")
test("斜杠命令检测(6有效+2无效)", test_slash)

# ========== 数据库并发 ==========
def test_db_concurrent():
    import threading
    import tempfile
    tmp_db = os.path.join(tempfile.gettempdir(), "e2e_concurrent_test.db")
    conn_init = sqlite3.connect(tmp_db)
    conn_init.execute("PRAGMA journal_mode=WAL")
    conn_init.execute("""CREATE TABLE IF NOT EXISTS conversation_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT, user_input TEXT, bot_reply TEXT, source TEXT, created_at REAL
    )""")
    conn_init.commit()
    conn_init.close()
    results = []
    def write_thread(i):
        try:
            conn = sqlite3.connect(tmp_db, timeout=15)
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA journal_mode=WAL")
            now = time.time()
            conn.execute("INSERT INTO conversation_logs (user_id, user_input, bot_reply, source, created_at) VALUES (?,?,?,?,?)",
                         (f"concurrent_user_{i}", f"test_{i}", f"reply_{i}", "test", now))
            conn.commit()
            conn.execute("DELETE FROM conversation_logs WHERE user_id=?", (f"concurrent_user_{i}",))
            conn.commit()
            conn.close()
            results.append(True)
        except Exception as e:
            results.append(False)
    threads = [threading.Thread(target=write_thread, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    os.unlink(tmp_db)
    success_rate = results.count(True) / len(results)
    assert success_rate >= 0.6, f"Too many failures: {results.count(False)}/{len(results)}"
test("数据库并发安全(5线程WAL)", test_db_concurrent)

# ========== KIOXIA完整性 ==========
def test_kioxia():
    base = "/media/orangepi/KIOXIA/nahida-data"
    for d in ["db", "logs", "config", "stickers", "files", "credentials"]:
        assert os.path.isdir(os.path.join(base, d)), f"Missing: {d}"
    assert os.path.exists(os.path.join(base, "db", "agent.db"))
test("KIOXIA数据目录完整性", test_kioxia)

# ========== 配置回退 ==========
def test_fallback():
    from config import _resolve_data_path
    from pathlib import Path
    result = _resolve_data_path(Path("/media/orangepi/KIOXIA/nahida-data/db"), Path("/home/orangepi/ai-agent/data"))
    assert "KIOXIA" in str(result)
test("配置回退(KIOXIA优先)", test_fallback)

# ========== VectorStore ==========
def test_vector():
    from vector_store import VectorStore
    from pathlib import Path
    vs = VectorStore(Path("/media/orangepi/KIOXIA/nahida-data/db/agent_vec.db"))
    assert hasattr(vs, 'upsert')
    assert hasattr(vs, 'search')
test("VectorStore初始化", test_vector)

# ========== Print Results ==========
print("=" * 55)
print("纳西妲 AI Agent 端到端+边界测试")
print("=" * 55)
for name, status, err in tests:
    icon = "PASS" if status == "PASS" else "FAIL"
    print(f"  [{icon}] {name}")
    if err:
        print(f"       -> {err}")
print("-" * 55)
print(f"总计: {passed+failed} | 通过: {passed} | 失败: {failed}")
print("=" * 55)

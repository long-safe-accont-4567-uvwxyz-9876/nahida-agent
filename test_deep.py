import asyncio
import sqlite3
import time
import os
import json

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

# ========== NudgeEngine ==========
def test_nudge_init():
    from nudge_engine import NudgeEngine
    ne = NudgeEngine(db=None, router=None, api=None, analytics=None, user_openid="test",
                     greeting_threshold=3600, dnd_start=23, dnd_end=8)
    assert ne.greeting_enabled == True
    assert ne.greeting_threshold == 3600
    assert ne.dnd_start == 23
    assert ne.dnd_end == 8
test("NudgeEngine初始化+配置", test_nudge_init)

def test_nudge_greeting():
    from nudge_engine import NudgeEngine
    ne = NudgeEngine(db=None, router=None, api=None, analytics=None, user_openid="test")
    greeting = ne.get_time_greeting()
    assert isinstance(greeting, str) and len(greeting) > 0
test("NudgeEngine时间问候生成", test_nudge_greeting)

def test_nudge_poke():
    from nudge_engine import NudgeEngine
    ne = NudgeEngine(db=None, router=None, api=None, analytics=None, user_openid="test")
    ne.poke()
    assert ne._last_user_message_time > 0
test("NudgeEngine.poke()重置计时", test_nudge_poke)

def test_nudge_portrait_manager():
    from nudge_engine import NudgeEngine
    ne = NudgeEngine(db=None, analytics=None, router=None, api=None, user_openid="test", portrait_manager="mock_pm")
    assert ne._portrait_manager == "mock_pm"
test("NudgeEngine portrait_manager依赖注入", test_nudge_portrait_manager)

# ========== PortraitManager ==========
def test_portrait():
    from portrait_manager import PortraitManager
    pm = PortraitManager(db=None, memory=None, router=None)
    assert hasattr(pm, 'mark_dirty')
    assert hasattr(pm, 'consolidate')
    assert hasattr(pm, 'ensure_exists')
    pm.mark_dirty()
    assert pm._dirty == True
test("PortraitManager初始化+mark_dirty", test_portrait)

# ========== NotebookManager ==========
def test_notebook():
    from notebook_manager import NotebookManager
    nm = NotebookManager(db=None, notebook=None, router=None)
    for m in ['add_note', 'add_focus', 'schedule_task', 'auto_note_after_message',
              'get_recent_notes', 'get_pending_tasks', 'complete_task']:
        assert hasattr(nm, m), f"Missing method: {m}"
test("NotebookManager方法完整性", test_notebook)

# ========== LearningManager ==========
def test_learning():
    from learning_manager import LearningManager, CORRECTION_SIGNALS, FEATURE_SIGNALS
    lm = LearningManager(db=None, learning=None, router=None)
    for m in ['log_error', 'log_correction', 'log_feature_request',
              'evaluate_after_conversation', 'auto_promote', 'get_system_prompt_additions']:
        assert hasattr(lm, m), f"Missing method: {m}"
    assert len(CORRECTION_SIGNALS) > 0
    assert len(FEATURE_SIGNALS) > 0
test("LearningManager方法+信号词", test_learning)

# ========== KnowledgeGraph ==========
def test_kg():
    from knowledge_graph import KnowledgeGraph
    kg = KnowledgeGraph(db=None, router=None)
    for m in ['extract_from_summary', 'merge_entities', 'merge_relations',
              'get_related_knowledge', 'auto_extract_and_merge', 'cleanup_stale']:
        assert hasattr(kg, m), f"Missing method: {m}"
    assert KnowledgeGraph.MAX_ENTITIES == 500
    assert KnowledgeGraph.CLEANUP_AGE_DAYS == 30
test("KnowledgeGraph方法+常量", test_kg)

# ========== ToolCallRepair ==========
def test_tool_repair():
    from tool_repair import ToolCallRepair
    tr = ToolCallRepair(allowed_tool_names={"web_search", "shell_command"})
    for m in ['scavenge', 'repair_truncation', 'detect_storm', 'clear_storm_window']:
        assert hasattr(tr, m), f"Missing method: {m}"
    same_args = '{"query":"test"}'
    r1 = tr.detect_storm("web_search", same_args)
    r2 = tr.detect_storm("web_search", same_args)
    r3 = tr.detect_storm("web_search", same_args)
    assert r3 == True, f"Storm not detected after 3 same calls"
    tr.clear_storm_window()
    r4 = tr.detect_storm("web_search", same_args)
    assert r4 == False, "Storm should be cleared"
test("ToolCallRepair风暴检测(相同参数3次触发)", test_tool_repair)

def test_tool_repair_truncation():
    from tool_repair import ToolCallRepair
    tr = ToolCallRepair()
    truncated = '{"query": "test", "limit"'
    result = tr.repair_truncation(truncated)
    if result:
        parsed = json.loads(result)
        assert "query" in parsed
test("ToolCallRepair截断修复", test_tool_repair_truncation)

# ========== ModelRouter ==========
def test_router_cost():
    from dotenv import load_dotenv
    load_dotenv("/home/orangepi/ai-agent/.env")
    from model_router import ModelRouter
    router = ModelRouter()
    cost_pro = router._calc_cost(1000, 500, cache_hit_tokens=0, cache_miss_tokens=1000, model="pro")
    cost_flash = router._calc_cost(1000, 500, cache_hit_tokens=0, cache_miss_tokens=1000, model="flash")
    assert cost_pro > 0 and cost_flash > 0
    assert cost_flash < cost_pro, f"Flash should be cheaper: flash={cost_flash}, pro={cost_pro}"
test("ModelRouter费用计算(Pro>Flash)", test_router_cost)

def test_router_cache():
    from dotenv import load_dotenv
    load_dotenv("/home/orangepi/ai-agent/.env")
    from model_router import ModelRouter
    router = ModelRouter()
    cost_no = router._calc_cost(1000, 500, cache_hit_tokens=0, cache_miss_tokens=1000, model="pro")
    cost_yes = router._calc_cost(1000, 500, cache_hit_tokens=800, cache_miss_tokens=200, model="pro")
    assert cost_yes < cost_no, f"Cache should be cheaper: no={cost_no}, yes={cost_yes}"
test("ModelRouter缓存命中更便宜", test_router_cache)

def test_router_preference():
    from dotenv import load_dotenv
    load_dotenv("/home/orangepi/ai-agent/.env")
    from model_router import ModelRouter
    router = ModelRouter()
    assert router.set_model_preference("pro") == True
    assert router.get_model_preference() == "pro"
    assert router.set_model_preference("flash") == True
    assert router.get_model_preference() == "flash"
    assert router.set_model_preference("auto") == True
    assert router.get_model_preference() == "auto"
    assert router.set_model_preference("invalid") == False
test("ModelRouter模型偏好(pro/flash/auto/invalid)", test_router_preference)

def test_router_resolve():
    from dotenv import load_dotenv
    load_dotenv("/home/orangepi/ai-agent/.env")
    from model_router import ModelRouter
    router = ModelRouter()
    router.set_model_preference("pro")
    assert "pro" in router.resolve_task_type("chat")
    router.set_model_preference("flash")
    assert "flash" in router.resolve_task_type("chat")
test("ModelRouter任务类型解析", test_router_resolve)

def test_router_label():
    from dotenv import load_dotenv
    load_dotenv("/home/orangepi/ai-agent/.env")
    from model_router import ModelRouter
    router = ModelRouter()
    for pref in ["auto", "pro", "flash"]:
        router.set_model_preference(pref)
        label = router.get_model_preference_label()
        assert isinstance(label, str) and len(label) > 0
test("ModelRouter偏好中文标签", test_router_label)

def test_router_cache_stats():
    from dotenv import load_dotenv
    load_dotenv("/home/orangepi/ai-agent/.env")
    from model_router import ModelRouter
    router = ModelRouter()
    stats = router.get_cache_stats()
    assert isinstance(stats, dict)
test("ModelRouter缓存统计", test_router_cache_stats)

# ========== ToolExecutor ==========
def test_tool_executor():
    from tool_executor import ToolExecutor
    te = ToolExecutor(db=None)
    assert hasattr(te, 'execute')
    assert te._global_timeout == 60.0
test("ToolExecutor初始化+超时", test_tool_executor)

# ========== 数据库深度测试(使用正确列名) ==========
def test_db_sessions():
    conn = sqlite3.connect(DB_PATH)
    now = time.time()
    conn.execute("INSERT INTO sessions (id, user_openid, turn_count, total_cost_usd, cache_hit_tokens, cache_miss_tokens, started_at, status) VALUES (?,?,?,?,?,?,?,?)",
                 ("test_s_001", "test_openid", 1, 0.001, 0, 100, now, "active"))
    conn.commit()
    row = conn.execute("SELECT user_openid FROM sessions WHERE id='test_s_001'").fetchone()
    assert row is not None and row[0] == "test_openid"
    conn.execute("DELETE FROM sessions WHERE id='test_s_001'")
    conn.commit()
    conn.close()
test("sessions会话写入+读取", test_db_sessions)

def test_db_episodic():
    conn = sqlite3.connect(DB_PATH)
    now = time.time()
    conn.execute("INSERT INTO episodic_memories (timestamp, summary, importance, emotion_label, session_id) VALUES (?,?,?,?,?)",
                 (now, "测试情景记忆", 3, "neutral", "test_session"))
    conn.commit()
    row = conn.execute("SELECT summary FROM episodic_memories WHERE summary='测试情景记忆'").fetchone()
    assert row is not None
    conn.execute("DELETE FROM episodic_memories WHERE summary='测试情景记忆'")
    conn.commit()
    conn.close()
test("episodic_memories情景记忆写入", test_db_episodic)

def test_db_portrait():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    now = time.time()
    conn.execute("DELETE FROM user_portrait WHERE id=999")
    conn.commit()
    conn.execute("INSERT INTO user_portrait (id, content, version, source_ids, change_log, created_at) VALUES (?,?,?,?,?,?)",
                 (999, "测试用户画像", 1, "[]", "init", now))
    conn.commit()
    row = conn.execute("SELECT content FROM user_portrait WHERE id=999").fetchone()
    assert row is not None and "画像" in row[0]
    conn.execute("DELETE FROM user_portrait WHERE id=999")
    conn.commit()
    conn.close()
test("user_portrait用户画像写入", test_db_portrait)

def test_db_proactive():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    now = time.time()
    conn.execute("INSERT INTO proactive_messages (user_id, message_type, content, sent_at) VALUES (?,?,?,?)",
                 ("test_user_999", "greeting", "测试主动消息_999", now))
    conn.commit()
    row = conn.execute("SELECT content FROM proactive_messages WHERE content='测试主动消息_999'").fetchone()
    assert row is not None
    conn.execute("DELETE FROM proactive_messages WHERE content='测试主动消息_999'")
    conn.commit()
    conn.close()
test("proactive_messages主动消息写入", test_db_proactive)

def test_db_errors_features():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    now = time.time()
    date_str = time.strftime("%Y%m%d")
    eid = f"ERR-{date_str}-{int(now % 10000):04d}"
    fid = f"FEAT-{date_str}-{int(now % 10000):04d}"
    conn.execute("INSERT INTO errors (error_id, priority, status, area, summary, error_text, context, suggested_fix, reproducible, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                 (eid, "high", "open", "test", "test summary", "test error", "test ctx", "test fix", 0, now))
    conn.execute("INSERT INTO feature_requests (request_id, priority, status, area, capability, user_context, created_at) VALUES (?,?,?,?,?,?,?)",
                 (fid, "medium", "open", "test", "test cap", "test ctx", now))
    conn.commit()
    assert conn.execute("SELECT error_id FROM errors WHERE error_id=?", (eid,)).fetchone() is not None
    assert conn.execute("SELECT request_id FROM feature_requests WHERE request_id=?", (fid,)).fetchone() is not None
    conn.execute("DELETE FROM errors WHERE error_id=?", (eid,))
    conn.execute("DELETE FROM feature_requests WHERE request_id=?", (fid,))
    conn.commit()
    conn.close()
test("errors+feature_requests写入(float修复验证)", test_db_errors_features)

# ========== 配置文件 ==========
def test_workspace_files():
    from config import WORKSPACE_DIR
    for f in ["AGENTS.md", "SOUL.md", "IDENTITY.md", "USER.md", "TOOLS.md", "MEMORY.md"]:
        assert (WORKSPACE_DIR / f).exists(), f"Missing: {f}"
test("workspace配置文件完整性", test_workspace_files)

def test_agent_config():
    from config import AGENT_CONFIG_PATH
    assert AGENT_CONFIG_PATH.exists()
    with open(AGENT_CONFIG_PATH) as f:
        content = f.read()
    assert len(content) > 10
test("agent.json5配置文件存在", test_agent_config)

# ========== SSL + systemd ==========
def test_ssl():
    cert = "/home/orangepi/miniconda3/lib/python3.13/site-packages/certifi/cacert.pem"
    assert os.path.exists(cert) and os.path.getsize(cert) > 100000
test("SSL证书完整性", test_ssl)

def test_systemd():
    with open("/etc/systemd/system/qq-agent.service") as f:
        c = f.read()
    assert "Restart=always" in c and "SSL_CERT_FILE" in c and "qq_bot_adapter.py" in c
test("systemd配置(Restart+SSL)", test_systemd)

# ========== Print Results ==========
print("=" * 55)
print("纳西妲 AI Agent 深度功能测试")
print("=" * 55)
for name, status, err in tests:
    icon = "PASS" if status == "PASS" else "FAIL"
    print(f"  [{icon}] {name}")
    if err:
        print(f"       -> {err}")
print("-" * 55)
print(f"总计: {passed+failed} | 通过: {passed} | 失败: {failed}")
print("=" * 55)

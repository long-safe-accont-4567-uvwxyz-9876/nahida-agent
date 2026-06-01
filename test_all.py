import sys, traceback

tests = []
passed = failed = 0

def test(name, func):
    global passed, failed
    try:
        func()
        tests.append((name, "PASS", ""))
        passed += 1
    except Exception as e:
        tests.append((name, "FAIL", str(e)))
        failed += 1

def t1():
    from config import DATA_DIR, LOG_DIR, STICKER_DIR, FILE_DIR
    assert "KIOXIA" in str(DATA_DIR) and DATA_DIR.exists()
    assert "KIOXIA" in str(LOG_DIR) and LOG_DIR.exists()
    assert "KIOXIA" in str(STICKER_DIR) and STICKER_DIR.exists()
test("config路径->KIOXIA", t1)

def t2():
    from database import DB_PATH
    assert "KIOXIA" in str(DB_PATH) and DB_PATH.exists()
test("数据库->KIOXIA", t2)

def t3():
    from sticker_manager import StickerManager
    from config import STICKER_DIR
    sm = StickerManager(STICKER_DIR)
    assert sm.available and sum(len(v) for v in sm._cache.values()) >= 30
    assert sm.detect_emotion("哈哈太好了") == "happy"
    assert sm.detect_emotion("呜呜好难过") == "sad"
    assert sm.pick("happy") is not None
test("表情包系统(39张+情绪检测)", t3)

def t4():
    from file_receiver import FileReceiver
    from config import FILE_DIR
    fr = FileReceiver(FILE_DIR)
    assert fr._safe_filename("../../../etc/passwd") == "passwd"
    assert fr._classify("doc.pdf", "") == "documents"
test("文件接收器(安全+分类)", t4)

def t5():
    from text_utils import humanize
    assert "此外" not in humanize("此外，值得注意的是，这很重要")
test("humanize去AI味", t5)

def t6():
    from text_utils import strip_dsml, has_dsml_tool_calls
    t = '你好<｜｜DSML｜｜tool_calls><｜｜DSML｜｜invoke name="web_search">test</｜｜DSML｜｜invoke></｜｜DSML｜｜tool_calls>世界'
    c = strip_dsml(t)
    assert "DSML" not in c and "你好" in c and "世界" in c
    assert has_dsml_tool_calls(t) and not has_dsml_tool_calls("普通文本")
test("DSML解析", t6)

def t7():
    import time
    now = time.time()
    f"API-{int(now)%100000:05d}"
    f"LRN-{int(now%10000):04d}"
test("float->int格式化", t7)

def t8():
    import tools.multi_search_tools
    from tool_registry import _tools
    assert "multi_search" in _tools and "wolfram_query" in _tools
test("多引擎搜索工具", t8)

def t9():
    import sqlite3
    conn = sqlite3.connect("/media/orangepi/KIOXIA/nahida-data/db/agent.db")
    assert conn.execute("SELECT version FROM schema_version").fetchone()[0] >= 1
    cols = [c[1] for c in conn.execute("PRAGMA table_info(knowledge_relations)").fetchall()]
    assert "valid_from" in cols and "valid_to" in cols
    conn.close()
test("时序知识图谱+版本控制", t9)

def t10():
    from config import LOG_DIR
    import glob
    assert len(glob.glob(str(LOG_DIR / "*.json"))) > 0
test("日志->KIOXIA", t10)

print("=" * 50)
print("纳西妲 AI Agent 测试报告")
print("=" * 50)
for name, status, err in tests:
    icon = "PASS" if status == "PASS" else "FAIL"
    print(f"  [{icon}] {name}")
    if err:
        print(f"       -> {err[:80]}")
print("-" * 50)
print(f"总计: {passed+failed} | 通过: {passed} | 失败: {failed}")
print("=" * 50)

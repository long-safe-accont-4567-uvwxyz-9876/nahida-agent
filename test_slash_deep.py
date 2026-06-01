import asyncio
import sys
import os
import traceback
import tempfile

PASS = 0
FAIL = 0
ERRORS = []

def section(name):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

def check(desc, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {desc}")
    else:
        FAIL += 1
        ERRORS.append(f"{desc}: {detail}")
        print(f"  ❌ {desc} - {detail}")

from dotenv import load_dotenv
load_dotenv()

section("web_browse 修复验证")

from tools.web_browse_tools import web_browse

r = web_browse(url="https://www.baidu.com")
check("web_browse (百度)", r.success, f"失败: {r.error[:150] if r.error else ''}")
if r.success:
    print(f"    📄 {str(r.data)[:200]}")

r = web_browse(url="https://example.com")
check("web_browse (example.com)", r.success, f"失败: {r.error[:150] if r.error else ''}")
if r.success:
    print(f"    📄 {str(r.data)[:200]}")

section("斜杠命令深度功能测试")

from slash_commands import SlashCommandHandler
from model_router import ModelRouter
from security import SecurityFilter
from agent_context import AgentContext
from database import DatabaseManager

async def test_slash_commands():
    router = ModelRouter()
    security = SecurityFilter(owner_ids=["test_owner", "cli_test"])
    context = AgentContext(system_prompt="测试系统提示")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_db_path = tmp.name

    try:
        db = DatabaseManager(tmp_db_path)
        await db.init()

        handler = SlashCommandHandler(
            db=db, router=router, context=context,
            security=security, agent=None,
        )

        # /help
        r = await handler.handle("/help", user_id="cli_test")
        check("/help 返回非空", r is not None and len(r) > 0)
        check("/help 包含命令列表", "命令列表" in r or "/cost" in r, f"内容: {r[:100]}")

        # /help 区分主人/非主人
        r_owner = await handler.handle("/help", user_id="test_owner")
        r_stranger = await handler.handle("/help", user_id="stranger")
        check("/help 主人看到专属命令", "主人专属" in r_owner, f"主人看到: {r_owner[:100]}")
        check("/help 非主人看不到专属命令", "主人专属" not in r_stranger, f"非主人看到: {r_stranger[:100]}")

        # /cost
        r = await handler.handle("/cost", user_id="cli_test")
        check("/cost 返回非空", r is not None and len(r) > 0)
        check("/cost 包含花费或无调用提示", "花费" in r or "API" in r or "调用" in r, f"内容: {r[:100]}")

        r = await handler.handle("/cost 7d", user_id="cli_test")
        check("/cost 7d 返回非空", r is not None and len(r) > 0)

        # /status
        r = await handler.handle("/status", user_id="cli_test")
        check("/status 返回非空", r is not None and len(r) > 0)
        check("/status 包含运行时间", "运行时间" in r, f"内容: {r[:100]}")

        # /model
        r = await handler.handle("/model", user_id="test_owner")
        check("/model (查看当前) 返回非空", r is not None and len(r) > 0)
        check("/model 包含当前模式或用法", "当前" in r or "用法" in r, f"内容: {r[:100]}")

        r = await handler.handle("/model mimo", user_id="test_owner")
        check("/model mimo 切换成功", "MiMo" in r or "mimo" in r.lower(), f"内容: {r[:100]}")

        r = await handler.handle("/model auto", user_id="test_owner")
        check("/model auto 切换成功", "自动" in r or "auto" in r.lower(), f"内容: {r[:100]}")

        # /model 非主人不能切换
        r = await handler.handle("/model pro", user_id="stranger")
        check("/model 非主人被拒绝", "主人" in r, f"内容: {r[:100]}")

        # /forget
        context.add_message("user", "测试消息1")
        context.add_message("assistant", "测试回复1")
        r = await handler.handle("/forget", user_id="cli_test")
        check("/forget 返回非空", r is not None and len(r) > 0)
        check("/forget 包含清除提示", "清除" in r or "记忆" in r, f"内容: {r[:100]}")
        check("/forget 实际清除了历史", len(context.history) == 0, f"剩余: {len(context.history)}")

        # /reset
        context.add_message("user", "测试消息2")
        r = await handler.handle("/reset", user_id="test_owner")
        check("/reset 返回非空", r is not None and len(r) > 0)
        check("/reset 包含重置提示", "重置" in r, f"内容: {r[:100]}")

        # /reset 非主人不能执行
        r = await handler.handle("/reset", user_id="stranger")
        check("/reset 非主人被拒绝", "主人" in r, f"内容: {r[:100]}")

        # /learn
        r = await handler.handle("/learn", user_id="cli_test")
        check("/learn 返回非空", r is not None and len(r) > 0)

        # /note
        r = await handler.handle("/note", user_id="cli_test")
        check("/note 返回非空", r is not None and len(r) > 0)

        # /hw
        r = await handler.handle("/hw", user_id="cli_test")
        check("/hw 返回非空", r is not None and len(r) > 0)
        check("/hw 包含硬件信息", "CPU" in r or "温度" in r or "内存" in r, f"内容: {r[:100]}")

        # /sys
        r = await handler.handle("/sys", user_id="cli_test")
        check("/sys 返回非空", r is not None and len(r) > 0)
        check("/sys 包含系统信息", "运行" in r or "模型" in r or "错误" in r, f"内容: {r[:100]}")

        # /voice (无agent时)
        r = await handler.handle("/voice", user_id="test_owner")
        check("/voice (无agent) 返回提示", r is not None and ("语音" in r or "Agent" in r or "还没" in r), f"内容: {r[:100]}")

        # /agent (无agent时)
        r = await handler.handle("/agent", user_id="test_owner")
        check("/agent (无agent) 返回提示", r is not None and ("Agent" in r or "还没" in r), f"内容: {r[:100]}")

        # /cam (可能无摄像头)
        r = await handler.handle("/cam", user_id="cli_test")
        check("/cam 返回非空", r is not None and len(r) > 0)

        # 未知命令
        r = await handler.handle("/unknown_cmd", user_id="cli_test")
        check("未知命令返回帮助", r is not None and len(r) > 0)

        # 非斜杠命令
        is_slash = handler.is_slash_command("你好")
        check("非斜杠命令不被识别", not is_slash)

        is_slash = handler.is_slash_command("/help")
        check("斜杠命令被识别", is_slash)

        is_slash = handler.is_slash_command("//注释")
        check("//注释不被识别为斜杠命令", not is_slash)

        # is_owner_command
        check("/model 是主人命令", handler.is_owner_command("/model"))
        check("/reset 是主人命令", handler.is_owner_command("/reset"))
        check("/agent 是主人命令", handler.is_owner_command("/agent"))
        check("/help 不是主人命令", not handler.is_owner_command("/help"))
        check("/hw 不是主人命令", not handler.is_owner_command("/hw"))
        check("/cost 不是主人命令", not handler.is_owner_command("/cost"))

    finally:
        os.unlink(tmp_db_path)

asyncio.run(test_slash_commands())


section("测试结果汇总")
print(f"\n  ✅ 通过: {PASS}")
print(f"  ❌ 失败: {FAIL}")
print(f"  📊 总计: {PASS + FAIL}")

if ERRORS:
    print(f"\n  失败详情:")
    for e in ERRORS:
        print(f"    ❌ {e}")

sys.exit(1 if FAIL > 0 else 0)

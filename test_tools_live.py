import asyncio
import sys
import os
import traceback
from pathlib import Path

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

def check_tool_result(name, result, expect_success=True):
    from tool_registry import ToolResult
    if isinstance(result, ToolResult):
        if expect_success:
            check(f"{name}", result.success, f"失败: {result.error[:150] if result.error else 'unknown'}")
            if result.success and result.data:
                data_str = str(result.data)[:200]
                print(f"    📄 {data_str}")
        else:
            check(f"{name} (预期失败)", not result.success, f"意外成功: {str(result.data)[:100]}")
    else:
        check(f"{name}", False, f"返回类型异常: {type(result)}")

section("工具实测")

# ---- code_tools_v2 ----
from tools.code_tools_v2 import get_current_time, python_executor, calculator

section("代码工具 (code_tools_v2)")

r = get_current_time()
check_tool_result("get_current_time", r)

r = python_executor(code="print(2+3)")
check_tool_result("python_executor", r)

r = python_executor(code="import os; os.system('rm -rf /tmp/noexist')")
check_tool_result("python_executor (os.system应可执行)", r)

r = calculator(expression="2**10 + sqrt(144)")
check_tool_result("calculator", r)

r = calculator(expression="sin(pi/2)")
check_tool_result("calculator (三角函数)", r)

# ---- file_tools_v2 ----
from tools.file_tools_v2 import shell_command, list_files, read_file, write_file, search_files

section("文件工具 (file_tools_v2)")

r = shell_command(command="echo hello_world_test")
check_tool_result("shell_command (echo)", r)

r = shell_command(command="rm -rf /")
check_tool_result("shell_command (危险命令应被拦截)", r, expect_success=False)

r = shell_command(command="ls /tmp")
check_tool_result("shell_command (ls)", r)

r = list_files(path="/tmp")
check_tool_result("list_files (/tmp)", r)

r = read_file(path="/etc/hostname", offset=1, limit=5)
check_tool_result("read_file (/etc/hostname)", r)

r = write_file(input_str="/tmp/test_ai_agent_write.txt|||hello test content")
check_tool_result("write_file", r)

r = read_file(path="/tmp/test_ai_agent_write.txt")
check_tool_result("read_file (刚写入的文件)", r)

r = search_files(pattern="/tmp/test_ai_agent*")
check_tool_result("search_files", r)

# cleanup
os.unlink("/tmp/test_ai_agent_write.txt")

# ---- hardware_tools ----
from tools.hardware_tools import gpio_control, i2c_comm, hardware_status

section("硬件工具 (hardware_tools)")

r = gpio_control(action="read", pin=7)
check_tool_result("gpio_control (read pin 7)", r)

r = gpio_control(action="read", pin=1)
check_tool_result("gpio_control (保护引脚1应被拦截)", r, expect_success=False)

r = i2c_comm(action="scan")
check_tool_result("i2c_comm (scan)", r)

r = hardware_status(target="all")
check_tool_result("hardware_status", r)

# ---- system_tools ----
from tools.system_tools import service_manage, network_diag, dev_assist

section("系统工具 (system_tools)")

r = service_manage(action="list")
check_tool_result("service_manage (list)", r)

r = service_manage(action="status", name="qq-agent")
check_tool_result("service_manage (status qq-agent)", r)

r = network_diag(action="interfaces")
check_tool_result("network_diag (interfaces)", r)

r = network_diag(action="ping", target="127.0.0.1")
check_tool_result("network_diag (ping localhost)", r)

r = dev_assist(action="git_status", path="/home/orangepi/ai-agent")
check_tool_result("dev_assist (git_status)", r)

# ---- web_tools_v2 ----
from tools.web_tools_v2 import web_search, get_weather

section("网络工具 (web_tools_v2)")

r = web_search(query="Python 3.12 新特性")
check_tool_result("web_search", r)

r = get_weather(city="北京")
check_tool_result("get_weather (北京)", r)

r = get_weather(city="武汉")
check_tool_result("get_weather (武汉)", r)

# ---- web_browse_tools ----
from tools.web_browse_tools import web_browse

section("网页浏览工具 (web_browse_tools)")

r = web_browse(url="https://httpbin.org/get")
check_tool_result("web_browse (httpbin)", r)

# ---- multi_search_tools ----
from tools.multi_search_tools import multi_search, wolfram_query

section("多引擎搜索工具 (multi_search_tools)")

r = multi_search(query="test")
check_tool_result("multi_search (已禁用应失败)", r, expect_success=False)

r = wolfram_query(query="2+2")
check_tool_result("wolfram_query", r)

# ---- document_tools ----
from tools.document_tools import document_reader

section("文档工具 (document_tools)")

r = document_reader(path="/nonexistent.pdf")
check_tool_result("document_reader (不存在文件应失败)", r, expect_success=False)

# ---- vision_tools ----
from tools.vision_tools import camera_capture, vision_analyze

section("视觉工具 (vision_tools)")

r = camera_capture(device=0)
check_tool_result("camera_capture", r)

r = vision_analyze(action="detect")
check_tool_result("vision_analyze (detect, 无摄像头应优雅降级)", r)

# ---- call_klee / call_nahida ----
from tools.code_tools_v2 import call_klee, call_nahida

section("委派工具")

r = call_klee(task="讲个笑话")
check_tool_result("call_klee", r)

r = call_nahida(question="测试问题")
check_tool_result("call_nahida", r)


# ---- 斜杠命令实测 ----
section("斜杠命令实测")

from dotenv import load_dotenv
load_dotenv()
from slash_commands import SlashCommandHandler
from model_router import ModelRouter

router = ModelRouter()
handler = SlashCommandHandler(router=router, agent=None)

async def test_slash_commands():
    # /help
    r = await handler.handle("/help", user_id="cli_test")
    check("/help", r is not None and len(r) > 0, f"返回: {str(r)[:100]}")

    # /status
    r = await handler.handle("/status", user_id="cli_test")
    check("/status", r is not None and len(r) > 0, f"返回: {str(r)[:100]}")

    # /cost
    r = await handler.handle("/cost", user_id="cli_test")
    check("/cost", r is not None and len(r) > 0, f"返回: {str(r)[:100]}")

    # /hw
    r = await handler.handle("/hw", user_id="cli_test")
    check("/hw", r is not None and len(r) > 0, f"返回: {str(r)[:100]}")

    # /sys
    r = await handler.handle("/sys", user_id="cli_test")
    check("/sys", r is not None and len(r) > 0, f"返回: {str(r)[:100]}")

    # /forget
    r = await handler.handle("/forget", user_id="cli_test")
    check("/forget", r is not None, f"返回: {str(r)[:100]}")

    # /learn
    r = await handler.handle("/learn", user_id="cli_test")
    check("/learn", r is not None, f"返回: {str(r)[:100]}")

    # /note
    r = await handler.handle("/note", user_id="cli_test")
    check("/note", r is not None, f"返回: {str(r)[:100]}")

    # /model
    r = await handler.handle("/model", user_id="cli_test")
    check("/model (查看当前)", r is not None, f"返回: {str(r)[:100]}")

    # /voice
    r = await handler.handle("/voice", user_id="cli_test")
    check("/voice (查看状态)", r is not None, f"返回: {str(r)[:100]}")

    # /agent
    r = await handler.handle("/agent", user_id="cli_test")
    check("/agent (查看当前)", r is not None, f"返回: {str(r)[:100]}")

    # /cam
    r = await handler.handle("/cam", user_id="cli_test")
    check("/cam", r is not None, f"返回: {str(r)[:100]}")

    # /reset
    r = await handler.handle("/reset", user_id="cli_test")
    check("/reset", r is not None, f"返回: {str(r)[:100]}")

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

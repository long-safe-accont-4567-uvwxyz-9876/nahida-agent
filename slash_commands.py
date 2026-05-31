import os
from loguru import logger


class SlashCommandHandler:

    def __init__(self, agent_core):
        self._agent = agent_core
        self._commands = {
            "/help": self._cmd_help,
            "/clear": self._cmd_clear,
            "/memory": self._cmd_memory,
            "/tools": self._cmd_tools,
            "/status": self._cmd_status,
            "/forget": self._cmd_forget,
        }

    async def handle(self, input_text: str) -> str:
        parts = input_text.strip().split(" ", 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        handler = self._commands.get(cmd)
        if handler:
            return await handler(args)
        return f"未知命令: {cmd}，输入 /help 查看帮助"

    async def _cmd_help(self, args: str) -> str:
        return """🌿 可用命令：
/help   - 显示帮助
/clear  - 清除对话历史
/memory - 查看记忆
/tools  - 查看可用工具
/status - 查看系统状态
/forget - 删除记忆"""

    async def _cmd_clear(self, args: str) -> str:
        self._agent.context.clear()
        return "对话历史已清除 ✨"

    async def _cmd_memory(self, args: str) -> str:
        memories = await self._agent._memory.get_recent(10)
        if not memories:
            return "暂无记忆"
        lines = [f"- {m['content'][:60]}" for m in memories]
        return "🌿 最近记忆：\n" + "\n".join(lines)

    async def _cmd_tools(self, args: str) -> str:
        from tool_registry import list_tools
        tools = list_tools()
        lines = [f"- {t['name']}: {t['description'][:40]}" for t in tools]
        return "🌿 可用工具：\n" + "\n".join(lines)

    async def _cmd_status(self, args: str) -> str:
        return f"🌿 系统状态：正常\n模型: {self._agent.config.get('model_name')}"

    async def _cmd_forget(self, args: str) -> str:
        if not args:
            return "请指定要忘记的内容，例如：/forget 关键词"
        result = await self._agent._memory.forget(args)
        if result:
            return "已忘记 ✨"
        return "没有找到相关记忆"

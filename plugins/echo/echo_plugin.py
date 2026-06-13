"""Echo 示例插件"""
from plugins.sdk import Plugin, register_tool


class EchoPlugin(Plugin):
    """最简示例插件"""

    @register_tool("echo", description="回显输入的文本")
    async def echo(self, text: str = "") -> str:
        return text or "echo!"

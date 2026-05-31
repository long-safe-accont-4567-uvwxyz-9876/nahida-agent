import os
import asyncio
from datetime import datetime
from typing import Optional

from loguru import logger


class SlashCommandHandler:

    def __init__(self, agent_core=None):
        self._agent = agent_core
        self._commands = {
            "/help": self._cmd_help,
            "/cost": self._cmd_cost,
            "/status": self._cmd_status,
            "/forget": self._cmd_forget,
            "/learn": self._cmd_learn,
            "/note": self._cmd_note,
            "/model": self._cmd_model,
            "/reset": self._cmd_reset,
            "/voice": self._cmd_voice,
            "/agent": self._cmd_agent,
            "/hw": self._cmd_hardware,
            "/sys": self._cmd_system,
            "/cam": self._cmd_camera,
        }

    async def handle(self, input_text: str) -> str:
        parts = input_text.strip().split(" ", 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        handler = self._commands.get(cmd)
        if handler:
            try:
                return await handler(args)
            except Exception as e:
                logger.error("slash_cmd.error", cmd=cmd, error=str(e))
                return f"命令执行出错: {e}"

        return f"未知命令: {cmd}，输入 /help 查看帮助"

    async def _cmd_help(self, args: str) -> str:
        return """🌿 可用命令：

📋 基础命令：
/help   - 显示帮助
/status - 查看系统状态
/cost   - 查看用量统计
/model  - 查看/切换模型
/reset  - 重置对话上下文

🧠 记忆管理：
/learn <内容> - 记忆新知识
/forget <关键词> - 删除记忆
/note <内容> - 添加笔记

🎙 语音相关：
/voice  - 查看语音设置

🤖 Agent 管理：
/agent  - 查看Agent列表

🔧 硬件/系统：
/hw     - 查看硬件信息
/sys    - 查看系统信息
/cam    - 摄像头相关"""

    async def _cmd_cost(self, args: str) -> str:
        if not self._agent:
            return "系统未初始化"

        try:
            memory = self._agent._memory
            if hasattr(memory, 'get_stats'):
                stats = await memory.get_stats()
                return f"""📊 用量统计：
今日对话: {stats.get('today_count', 0)} 次
总对话数: {stats.get('total_count', 0)} 次
记忆条数: {stats.get('memory_count', 0)} 条"""
            return "📊 用量统计暂不可用"
        except Exception as e:
            return f"获取统计失败: {e}"

    async def _cmd_status(self, args: str) -> str:
        if not self._agent:
            return "系统未初始化"

        try:
            model_name = "unknown"
            if hasattr(self._agent, '_model_router'):
                model_name = self._agent._model_router.model

            memory_count = 0
            if hasattr(self._agent, '_memory') and hasattr(self._agent._memory, 'count'):
                memory_count = await self._agent._memory.count()

            return f"""🌿 系统状态：
模型: {model_name}
记忆数: {memory_count}
运行状态: 正常"""
        except Exception as e:
            return f"获取状态失败: {e}"

    async def _cmd_forget(self, args: str) -> str:
        if not args:
            return "请指定要忘记的内容，例如：/forget 关键词"

        if not self._agent or not hasattr(self._agent, '_memory'):
            return "记忆系统未初始化"

        try:
            result = await self._agent._memory.forget(args)
            if result:
                return f"已忘记与「{args}」相关的记忆 ✨"
            return f"没有找到与「{args}」相关的记忆"
        except Exception as e:
            return f"操作失败: {e}"

    async def _cmd_learn(self, args: str) -> str:
        if not args:
            return "请提供要学习的内容，例如：/learn 我喜欢喝咖啡"

        if not self._agent or not hasattr(self._agent, '_memory'):
            return "记忆系统未初始化"

        try:
            await self._agent._memory.add(args, memory_type="learned", importance=0.9)
            return f"已学习: {args} ✨"
        except Exception as e:
            return f"学习失败: {e}"

    async def _cmd_note(self, args: str) -> str:
        if not args:
            return "请提供笔记内容，例如：/note 明天有会议"

        if not self._agent or not hasattr(self._agent, '_memory'):
            return "记忆系统未初始化"

        try:
            await self._agent._memory.add(args, memory_type="note", importance=0.7)
            return f"已添加笔记: {args} ✨"
        except Exception as e:
            return f"添加笔记失败: {e}"

    async def _cmd_model(self, args: str) -> str:
        if not self._agent or not hasattr(self._agent, '_model_router'):
            return "模型系统未初始化"

        router = self._agent._model_router
        if not args:
            return f"当前模型: {router.model}\n使用 /model <名称> 切换模型"

        try:
            router.set_model(args)
            return f"已切换到模型: {args} ✨"
        except Exception as e:
            return f"切换失败: {e}"

    async def _cmd_reset(self, args: str) -> str:
        if not self._agent:
            return "系统未初始化"

        try:
            if hasattr(self._agent, 'context'):
                self._agent.context.clear()
            return "对话上下文已重置 ✨"
        except Exception as e:
            return f"重置失败: {e}"

    async def _cmd_voice(self, args: str) -> str:
        if not self._agent:
            return "系统未初始化"

        try:
            tts = getattr(self._agent, '_tts', None)
            if tts:
                return f"""🎙 语音设置：
TTS引擎: {type(tts).__name__}
可用: {'是' if hasattr(tts, 'available') and tts.available else '否'}"""
            return "语音系统未启用"
        except Exception as e:
            return f"获取语音信息失败: {e}"

    async def _cmd_agent(self, args: str) -> str:
        if not self._agent or not hasattr(self._agent, '_dispatcher'):
            return "Agent系统未初始化"

        try:
            dispatcher = self._agent._dispatcher
            agents = []
            for name, agent in dispatcher._agents.items():
                status = "✅" if agent.available else "❌"
                agents.append(f"  {status} {agent.config.display_name} ({name})")

            if not agents:
                return "没有注册的Agent"

            return "🤖 Agent列表：\n" + "\n".join(agents)
        except Exception as e:
            return f"获取Agent列表失败: {e}"

    async def _cmd_hardware(self, args: str) -> str:
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            return f"""🔧 硬件信息：
CPU使用率: {cpu_percent}%
内存: {memory.used / 1024**3:.1f}GB / {memory.total / 1024**3:.1f}GB ({memory.percent}%)
磁盘: {disk.used / 1024**3:.1f}GB / {disk.total / 1024**3:.1f}GB ({disk.percent}%)"""
        except ImportError:
            return "psutil未安装，无法获取硬件信息"
        except Exception as e:
            return f"获取硬件信息失败: {e}"

    async def _cmd_system(self, args: str) -> str:
        try:
            import platform
            import psutil

            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time

            return f"""💻 系统信息：
系统: {platform.system()} {platform.release()}
架构: {platform.machine()}
Python: {platform.python_version()}
启动时间: {boot_time.strftime('%Y-%m-%d %H:%M:%S')}
运行时长: {str(uptime).split('.')[0]}"""
        except ImportError:
            return "psutil未安装"
        except Exception as e:
            return f"获取系统信息失败: {e}"

    async def _cmd_camera(self, args: str) -> str:
        if not self._agent:
            return "系统未初始化"

        try:
            if hasattr(self._agent, '_vision') and self._agent._vision:
                vision = self._agent._vision
                if hasattr(vision, 'capture'):
                    img_path = await vision.capture()
                    if img_path:
                        return f"已拍照: {img_path}"
                    return "拍照失败"
                return "摄像头不支持拍照"
            return "视觉服务未启用"
        except Exception as e:
            return f"摄像头操作失败: {e}"

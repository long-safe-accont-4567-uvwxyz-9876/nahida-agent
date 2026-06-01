"""
Agent 智能错误处理集成示例
展示如何将 smart_error_handler 集成到现有的 agent_core.py 中
"""

# ============================================
# 在 agent_core.py 的 __init__ 方法中添加：
# ============================================

# 在 import 部分添加：
from smart_error_handler import get_error_handler, SmartErrorHandler

# 在 __init__ 方法末尾添加：
self._error_handler = None  # 将在 _init_interaction 中初始化


# ============================================
# 在 _init_interaction 方法中初始化错误处理器：
# ============================================

async def _init_interaction(self) -> None:
    # ... 现有代码 ...
    
    # 初始化智能错误处理器
    self._error_handler = get_error_handler(
        db=self.db,
        dispatcher=self.dispatcher if hasattr(self, 'dispatcher') else None
    )
    
    # ... 现有代码 ...


# ============================================
# 修改 slash_commands.py 的错误处理逻辑：
# ============================================

# 原始代码（第61-65行）：
"""
if handler:
    try:
        return await handler(args, user_id)
    except Exception as e:
        logger.warning("slash.handle_error", command=command, error=str(e))
        return f"执行 /{command} 时出了点问题：{str(e)[:100]}"
"""

# 改进后的代码：
async def handle(self, text: str, user_id: str = "") -> str | None:
    parts = text.strip().split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""

    if self.is_owner_command(command):
        if not self._security or not self._security.is_owner(user_id):
            return "这个命令只有主人才能用哦～"

    handlers = {
        "/cost": self._cmd_cost,
        "/status": self._cmd_status,
        "/model": self._cmd_model,
        "/forget": self._cmd_forget,
        "/reset": self._cmd_reset,
        "/learn": self._cmd_learn,
        "/note": self._cmd_note,
        "/help": self._cmd_help,
        "/voice": self._cmd_voice,
        "/agent": self._cmd_agent,
    }

    handler = handlers.get(command)
    if handler:
        try:
            return await handler(args, user_id)
        except Exception as e:
            logger.warning("slash.handle_error", command=command, error=str(e))
            
            # 使用智能错误处理器（如果可用）
            if hasattr(self, '_agent') and self._agent and hasattr(self._agent, '_error_handler'):
                error_handler = self._agent._error_handler
                smart_reply = await error_handler.handle_error_with_intelligence(
                    error=e,
                    user_query=text,  # 传入原始用户输入用于意图理解
                    context=f"执行命令 /{command} 参数: {args}"
                )
                return smart_reply
            
            # 回退到简单错误消息
            return f"执行 /{command} 时出了点问题：{str(e)[:100]}"

    return await self._cmd_help("", user_id)


# ============================================
# 在 agent_core.py 的 process 方法中增强错误处理：
# ============================================

# 找到第475-487行的异常处理代码：

"""
except Exception as e:
    trace.error("agent.model_error", error=str(e))
    try:
        result = await self.router.route(
            "chat_flash",
            messages,
            temperature=0.7,
            user_openid=user_openid,
            session_id=session_id,
        )
        reply = self._clean_reply(result) if isinstance(result, str) else DEGRADED_REPLY
    except Exception:
        reply = DEGRADED_REPLY
"""

# 改进为：
except Exception as e:
    trace.error("agent.model_error", error=str(e))
    
    # 使用智能错误处理器
    if self._error_handler:
        error_reply = await self._error_handler.handle_error_with_intelligence(
            error=e,
            user_query=user_input,
            context="在主处理流程中调用模型时发生错误"
        )
        
        # 如果错误处理器返回了有用的信息，使用它
        if error_reply and len(error_reply) > 50:
            reply = error_reply
        else:
            # 否则尝试降级到 flash 模型
            try:
                result = await self.router.route(
                    "chat_flash",
                    messages,
                    temperature=0.7,
                    user_openid=user_openid,
                    session_id=session_id,
                )
                reply = self._clean_reply(result) if isinstance(result, str) else DEGRADED_REPLY
            except Exception:
                reply = DEGRADED_REPLY or error_reply
    else:
        # 回退到原有逻辑
        try:
            result = await self.router.route(
                "chat_flash",
                messages,
                temperature=0.7,
                user_openid=user_openid,
                session_id=session_id,
            )
            reply = self._clean_reply(result) if isinstance(result, str) else DEGRADED_REPLY
        except Exception:
            reply = DEGRADED_REPLY


# ============================================
# 增强上下文理解 - 在 process 方法开头添加：
# ============================================

async def process(self, user_input: str, user_id: str = "qq_user",
                  source: str = "qq",
                  user_openid: str = "",
                  session_id: str = "",
                  status_callback=None) -> ProcessResult:
    
    # 新增：检查是否在询问最近的错误解决方案
    if self._error_handler and self._error_handler._recent_errors:
        solution_keywords = ["怎么办", "怎么修", "如何解决", "修复", "fix", "help"]
        if any(kw in user_input.lower() for kw in solution_keywords):
            latest_error = self._error_handler._recent_errors[-1]
            
            # 构建带有错误上下文的增强提示
            error_context = self._error_handler.get_recent_error_summary()
            enhanced_input = f"{user_input}\n\n[系统提示：最近发生了以下错误]\n{error_context}"
            
            # 继续正常处理，但使用增强的输入
            user_input = enhanced_input
    
    # ... 继续原有的处理逻辑 ...


# ============================================
# 可选：创建专门的代码修复子代理配置
# ============================================

# 在 config.py 或 agent_dispatcher.py 中添加：

CODE_REPAIR_AGENT_CONFIG = {
    "name": "code_repair",
    "display_name": "代码修复专家 🔧",
    "provider": "deepseek",
    "model": "deepseek-reasoner",  # 使用推理模型以获得更好的分析能力
    "personality_file": "personalities/code_repair.txt",
    "capabilities": [
        "code_analysis",
        "bug_fixing",
        "refactoring",
        "performance_optimization"
    ],
    "route_description": (
        "专门处理代码错误、调试、重构、性能优化等编程任务。"
        "能够分析错误原因、提供修复方案、解释代码逻辑。"
    ),
    "excluded_tools": {
        "tts_speak",  # 不需要语音功能
        "send_image",  # 不需要发送图片
        # 可以根据需要排除其他工具
    }
}


# personalities/code_repair.txt 内容示例：
"""
你是一个专业的代码修复专家助手。

你的职责：
1. 分析代码错误的原因
2. 提供清晰、可执行的修复方案
3. 解释修复原理，帮助开发者理解
4. 提供预防类似错误的最佳实践

工作原则：
- 先理解问题再给出方案
- 提供完整的代码示例
- 解释每一步修改的原因
- 考虑边界情况和潜在副作用
- 推荐相关的学习资源

回复风格：
- 专业但不晦涩
- 结构化（使用列表、代码块）
- 提供多种解决方案（如果适用）
- 标注风险等级（安全/需测试/有风险）
"""


# ============================================
# 使用示例：在主 Agent 中委托任务给子代理
# ============================================

async def handle_complex_coding_task(self, task_description: str, 
                                    error_context: ErrorContext = None) -> str:
    """处理复杂的编程任务，委托给代码修复专家"""
    
    if not self.dispatcher:
        return "抱歉，现在没有可用的代码专家助手～"
    
    code_expert = self.dispatcher.get_agent("code_repair")
    if not code_expert or not code_expert.available:
        return "代码专家现在有点忙，稍后再试吧～"
    
    # 构建详细的任务描述
    prompt_parts = [
        "请帮我解决以下编程问题：\n",
        f"任务描述：{task_description}\n"
    ]
    
    if error_context:
        prompt_parts.extend([
            f"\n相关错误信息：",
            f"- 错误类型：{error_context.error_type}",
            f"- 错误详情：{error_context.error_message}",
            f"- 文件位置：{error_context.file_path}:{error_context.line_number}" if error_context.file_path else "",
            f"- 上下文代码：\n```python\n{error_context.context_code}\n```" if error_context.context_code else ""
        ])
    
    prompt_parts.append("\n请提供：\n1. 问题分析\n2. 解决方案代码\n3. 解释说明")
    
    try:
        result = await code_expert.chat("\n".join(prompt_parts))
        
        # 记录这次成功的协作
        if self._error_handler:
            logger.info("task.delegated_to_specialist", 
                       specialist="code_repair",
                       success=True)
        
        return f"🔧 **代码专家的建议**\n\n{result}"
        
    except Exception as e:
        logger.warning("task.specialist_failed", error=str(e))
        return f"代码专家处理失败：{str(e)}\n\n要不让人家先试试？"


# ============================================
# 测试用例
# ============================================

import asyncio

async def test_smart_error_handler():
    """测试智能错误处理器"""
    from smart_error_handler import SmartErrorHandler
    
    handler = SmartErrorHandler()
    
    # 测试1：AttributeError
    try:
        db = type('DatabaseManager', (), {})()
        db.get_promoted_learnings()
    except AttributeError as e:
        error_ctx = handler.record_error(e, "slash_commands.py line 188")
        print(f"✓ 错误解析成功:")
        print(f"  类型: {error_ctx.error_type}")
        print(f"  建议: {error_ctx.suggested_fix}")
        
        smart_reply = await handler.handle_error_with_intelligence(
            e, 
            user_query="怎么办？"
        )
        print(f"\n✓ 智能回复:\n{smart_reply}\n")
    
    # 测试2：判断是否需要委托
    should_delegate, agent_name = handler.should_delegate_to_specialist(error_ctx)
    print(f"✓ 是否需要委托: {should_delegate}, 目标代理: {agent_name}")
    
    # 测试3：模拟用户询问解决方案
    is_asking = handler._is_asking_for_solution("这个问题怎么办？")
    print(f"✓ 用户在询问解决方案: {is_asking}")


if __name__ == "__main__":
    asyncio.run(test_smart_error_handler())

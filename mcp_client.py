"""MCP (Model Context Protocol) Client framework.

Connects to MCP servers via stdio (subprocess), discovers their tools,
and registers them into the existing tool_registry.
"""

import asyncio
import json
import os
from typing import Any

from loguru import logger

import tool_registry
from tool_registry import ToolPermission, ToolResult


class MCPClient:
    """MCP Client that connects to an MCP server via stdio."""

    def __init__(self, server_name: str, command: str, args: list[str], env: dict | None = None):
        self.server_name = server_name
        self.command = command
        self.args = args
        self.env = env

        self._process: asyncio.subprocess.Process | None = None
        self._next_id: int = 1
        self._pending: dict[int, asyncio.Future] = {}
        self._read_task: asyncio.Task | None = None
        self._available: bool = False
        self._tool_names: set[str] = set()
        self._registered_names: set[str] = set()  # prefixed names in tool_registry

    # ── properties ──────────────────────────────────────────────

    @property
    def available(self) -> bool:
        return self._available

    @property
    def tool_names(self) -> set[str]:
        return set(self._tool_names)

    # ── lifecycle ───────────────────────────────────────────────

    async def start(self) -> None:
        """Start the MCP server subprocess and perform initialization handshake."""
        try:
            proc_env = dict(os.environ)
            if self.env:
                proc_env.update(self.env)

            self._process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=proc_env,
            )

            # Start reading loop
            self._read_task = asyncio.create_task(self._read_loop())

            # 1) initialize
            init_result = await self._request({
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "nahida-agent", "version": "1.0.0"},
                },
            })

            if not init_result:
                raise RuntimeError(f"MCP server '{self.server_name}' initialize failed: no response")

            logger.info("mcp_client.initialized", server=self.server_name,
                        server_info=init_result.get("serverInfo", {}))

            # 2) initialized notification
            await self._notify({
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            })

            # 3) tools/list
            tools_result = await self._request({
                "jsonrpc": "2.0",
                "method": "tools/list",
            })

            if not tools_result:
                raise RuntimeError(f"MCP server '{self.server_name}' tools/list failed: no response")

            tools = tools_result.get("tools", [])
            for tool_info in tools:
                self._register_mcp_tool(tool_info)

            self._available = True
            logger.info("mcp_client.started", server=self.server_name,
                        tools=list(self._tool_names))

        except Exception as e:
            logger.error("mcp_client.start_failed", server=self.server_name, error=str(e))
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop the MCP server subprocess gracefully."""
        self._available = False

        # Cancel pending futures
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()

        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            self._read_task = None

        if self._process and self._process.returncode is None:
            try:
                self._process.stdin.close()
                await self._process.stdin.wait_closed()
            except Exception:
                pass
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()

        self._process = None

        # Unregister tools from tool_registry (使用公共 API)
        for name in self._registered_names:
            tool_registry.unregister_tool(name)
        self._registered_names.clear()
        self._tool_names.clear()

        logger.info("mcp_client.stopped", server=self.server_name)

    # ── tool call ───────────────────────────────────────────────

    async def call_tool(self, tool_name: str, arguments: dict, timeout: float = 30.0) -> ToolResult:
        """Call a tool on the MCP server."""
        if not self._available:
            return ToolResult.fail(f"MCP server '{self.server_name}' is not available")

        try:
            result = await self._request(
                {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments,
                    },
                },
                timeout=timeout,
            )

            if result is None:
                return ToolResult.fail(f"MCP tool '{tool_name}' call timed out")

            # Check for error in response
            if "error" in result:
                error_msg = result["error"].get("message", str(result["error"]))
                return ToolResult.fail(f"MCP tool '{tool_name}' error: {error_msg}")

            # Extract content from result
            content = result.get("content", [])
            if not content:
                return ToolResult.ok("")

            # Concatenate text content items
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    text_parts.append(item)

            data = "\n".join(text_parts) if text_parts else str(content)
            is_error = result.get("isError", False)
            if is_error:
                return ToolResult.fail(data)

            return ToolResult.ok(data)

        except asyncio.TimeoutError:
            return ToolResult.fail(f"MCP tool '{tool_name}' call timed out")
        except Exception as e:
            logger.error("mcp_client.call_tool_error", server=self.server_name,
                         tool=tool_name, error=str(e))
            return ToolResult.fail(f"MCP tool '{tool_name}' error: {e}")

    # ── JSON-RPC helpers ────────────────────────────────────────

    async def _request(self, msg: dict, timeout: float = 30.0) -> dict | None:
        """Send a JSON-RPC request and wait for the response."""
        if not self._process or self._process.returncode is not None:
            return None

        msg_id = self._next_id
        self._next_id += 1
        msg["id"] = msg_id

        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = fut

        line = json.dumps(msg) + "\n"
        try:
            self._process.stdin.write(line.encode())
            await self._process.stdin.drain()
        except Exception as e:
            self._pending.pop(msg_id, None)
            fut.set_result(None)
            logger.error("mcp_client.write_error", server=self.server_name, error=str(e))
            return None

        try:
            result = await asyncio.wait_for(fut, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            return None

    async def _notify(self, msg: dict) -> None:
        """Send a JSON-RPC notification (no id, no response expected)."""
        if not self._process or self._process.returncode is not None:
            return

        line = json.dumps(msg) + "\n"
        try:
            self._process.stdin.write(line.encode())
            await self._process.stdin.drain()
        except Exception as e:
            logger.error("mcp_client.notify_error", server=self.server_name, error=str(e))

    async def _read_loop(self) -> None:
        """Continuously read lines from stdout and resolve pending futures."""
        try:
            while self._process and self._process.returncode is None:
                line_bytes = await self._process.stdout.readline()
                if not line_bytes:
                    # EOF — server closed stdout
                    break

                line = line_bytes.decode().strip()
                if not line:
                    continue

                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("mcp_client.invalid_json", server=self.server_name, line=line[:200])
                    continue

                msg_id = msg.get("id")
                if msg_id is not None and msg_id in self._pending:
                    fut = self._pending.pop(msg_id)
                    if not fut.done():
                        # Response contains "result" on success, or "error" on failure
                        if "result" in msg:
                            fut.set_result(msg["result"])
                        elif "error" in msg:
                            fut.set_result({"error": msg["error"]})
                        else:
                            fut.set_result(msg)
                # Notifications from server (no id) are logged but not handled
                elif "method" in msg and "id" not in msg:
                    logger.debug("mcp_client.server_notification",
                                 server=self.server_name, method=msg.get("method"))

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("mcp_client.read_loop_error", server=self.server_name, error=str(e))
        finally:
            self._available = False
            # Resolve any remaining pending futures with None
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_result(None)
            self._pending.clear()

    # ── tool registration ───────────────────────────────────────

    def _register_mcp_tool(self, tool_info: dict) -> None:
        """Register a discovered MCP tool into tool_registry."""
        original_name = tool_info.get("name", "")
        if not original_name:
            return

        prefixed_name = f"mcp_{self.server_name}_{original_name}"
        description = tool_info.get("description", f"MCP tool: {original_name}")
        input_schema = tool_info.get("inputSchema", {"type": "object", "properties": {}})

        self._tool_names.add(original_name)
        self._registered_names.add(prefixed_name)

        # Capture for closure
        server_name = self.server_name
        tool_name = original_name

        async def _mcp_tool_wrapper(**kwargs) -> ToolResult:
            # We need a reference to the client; use the captured variable
            # which refers to self at registration time
            client = _mcp_client_ref
            if client is None or not client.available:
                return ToolResult.fail(f"MCP server '{server_name}' is not available")
            return await client.call_tool(tool_name, kwargs)

        # Store self reference for the wrapper
        _mcp_client_ref = self

        # Register via the decorator pattern: register_tool returns a decorator
        tool_registry.register_tool(
            name=prefixed_name,
            description=description,
            schema=input_schema,
            permission=ToolPermission.EXECUTE,
            category="mcp",
            max_frequency=10,
            requires_confirmation=False,
        )(_mcp_tool_wrapper)

        logger.debug("mcp_client.tool_registered", server=self.server_name,
                     original=original_name, prefixed=prefixed_name)


class MCPManager:
    """Manages multiple MCP clients."""

    def __init__(self):
        self._clients: dict[str, MCPClient] = {}
        self._sdk_servers: dict[str, SdkMcpServer] = {}

    async def start_all(self, configs: dict[str, dict]) -> None:
        """Start all configured MCP servers.

        configs format:
        {
            "git": {
                "command": "/path/to/uvx",
                "args": ["mcp-server-git", "--repository", "/path"],
                "env": {"UV_INDEX_URL": "..."}
            },
            ...
        }
        """
        for server_name, cfg in configs.items():
            command = cfg.get("command", "")
            args = cfg.get("args", [])
            env = cfg.get("env")

            if not command:
                logger.warning("mcp_manager.skip_no_command", server=server_name)
                continue

            client = MCPClient(server_name, command, args, env)
            self._clients[server_name] = client

            try:
                await client.start()
                logger.info("mcp_manager.server_started", server=server_name)
            except Exception as e:
                logger.error("mcp_manager.server_start_failed",
                             server=server_name, error=str(e))

    async def stop_all(self) -> None:
        """Stop all MCP servers."""
        for server_name, client in self._clients.items():
            try:
                await client.stop()
            except Exception as e:
                logger.error("mcp_manager.server_stop_failed",
                             server=server_name, error=str(e))
        self._clients.clear()

        # 清理 SDK MCP 服务器
        for name in list(self._sdk_servers.keys()):
            # 注销工具
            server = self._sdk_servers.pop(name)
            for tool in server.tools.values():
                full_name = f"sdk_{name}_{tool.name}"
                from tool_registry import unregister_tool
                unregister_tool(full_name)

    def get_tools_for_agent(self, mcp_servers: list[str]) -> list[dict]:
        """Get OpenAI-format tool schemas for the specified MCP servers."""
        result = []
        for server_name in mcp_servers:
            client = self._clients.get(server_name)
            if not client or not client.available:
                continue
            for prefixed_name in client._registered_names:
                tool = tool_registry.get_tool(prefixed_name)
                if tool and tool.get("max_frequency", 0) > 0:
                    result.append({
                        "type": "function",
                        "function": {
                            "name": tool["name"],
                            "description": tool["description"],
                            "parameters": tool["schema"],
                        },
                    })

        # 添加 SDK MCP 工具
        for server_name, server in self._sdk_servers.items():
            if not mcp_servers or server_name in mcp_servers:
                sdk_tools = server.list_tools()
                result.extend(sdk_tools)

        return result

    def register_sdk_server(self, server: "SdkMcpServer") -> None:
        """注册进程内 SDK MCP 服务器"""
        self._sdk_servers[server.name] = server
        # 注册工具到 tool_registry
        from tool_registry import register_tool_direct
        for tool in server.tools.values():
            full_name = f"sdk_{server.name}_{tool.name}"
            register_tool_direct(
                name=full_name,
                description=tool.description,
                func=self._make_sdk_tool_wrapper(server.name, tool.name),
                parameters=tool.input_schema,
                permission="read_only",
                category="sdk_mcp",
            )
        logger.info(f"mcp_manager.sdk_server_registered", name=server.name,
                    tools=len(server.tools))

    def _make_sdk_tool_wrapper(self, server_name: str, tool_name: str):
        """创建 SDK MCP 工具的调用包装器"""
        async def wrapper(**kwargs):
            server = self._sdk_servers.get(server_name)
            if not server:
                from tool_registry import ToolResult
                return ToolResult.fail(f"SDK MCP 服务器 '{server_name}' 未注册")
            result = await server.call_tool(tool_name, kwargs)
            from tool_registry import ToolResult
            if "error" in result:
                return ToolResult.fail(result["error"])
            # 提取文本内容
            content = result.get("content", [])
            texts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    texts.append(item.get("text", ""))
            return ToolResult.ok("\n".join(texts) if texts else str(result))
        return wrapper

    def get_client(self, server_name: str) -> MCPClient | None:
        """Get a specific MCP client."""
        return self._clients.get(server_name)


# ── SDK MCP Server（进程内 MCP）──────────────────────────

from dataclasses import dataclass
from typing import Callable, Awaitable


@dataclass
class SdkMcpTool:
    """SDK MCP 工具定义 — 进程内工具，零 IPC 开销"""
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict], Awaitable[dict[str, Any]]]
    annotations: dict[str, Any] | None = None


def sdk_tool(
    name: str,
    description: str,
    input_schema: dict[str, Any] | None = None,
    annotations: dict[str, Any] | None = None,
) -> Callable:
    """装饰器：注册进程内 MCP 工具

    示例:
        @sdk_tool("memory_search", "搜索记忆", {"query": str, "top_k": int})
        async def memory_search(args):
            return {"content": [{"type": "text", "text": "搜索结果..."}]}
    """
    def decorator(handler: Callable[[dict], Awaitable[dict[str, Any]]]) -> SdkMcpTool:
        schema = input_schema or {}
        # 如果 schema 不是标准 JSON Schema，自动转换
        if not isinstance(schema, dict) or "type" not in schema:
            properties = {}
            for param_name, param_type in schema.items():
                if param_type is str:
                    properties[param_name] = {"type": "string"}
                elif param_type is int:
                    properties[param_name] = {"type": "integer"}
                elif param_type is float:
                    properties[param_name] = {"type": "number"}
                elif param_type is bool:
                    properties[param_name] = {"type": "boolean"}
                else:
                    properties[param_name] = {"type": "string"}
            schema = {
                "type": "object",
                "properties": properties,
                "required": list(properties.keys()),
            }
        return SdkMcpTool(
            name=name,
            description=description,
            input_schema=schema,
            handler=handler,
            annotations=annotations,
        )
    return decorator


class SdkMcpServer:
    """进程内 MCP 服务器 — 无需子进程，直接调用 Python 函数"""

    def __init__(self, name: str, version: str = "1.0.0",
                 tools: list[SdkMcpTool] | None = None):
        self.name = name
        self.version = version
        self.tools: dict[str, SdkMcpTool] = {}
        if tools:
            for tool in tools:
                self.tools[tool.name] = tool

    def list_tools(self) -> list[dict[str, Any]]:
        """列出所有工具（OpenAI function calling 格式）"""
        result = []
        for tool in self.tools.values():
            result.append({
                "type": "function",
                "function": {
                    "name": f"sdk_{self.name}_{tool.name}",
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            })
        return result

    async def call_tool(self, tool_name: str, arguments: dict) -> dict[str, Any]:
        """调用工具"""
        tool = self.tools.get(tool_name)
        if not tool:
            return {"error": f"Tool '{tool_name}' not found"}

        try:
            result = await tool.handler(arguments)
            return result
        except Exception as e:
            logger.error(f"sdk_mcp_server.call_tool.error", tool=tool_name, error=str(e))
            return {"error": str(e)}

    def register_tool(self, tool: SdkMcpTool) -> None:
        """注册工具"""
        self.tools[tool.name] = tool
        logger.debug(f"sdk_mcp_server.register_tool", name=tool.name, server=self.name)


def create_sdk_mcp_server(name: str, version: str = "1.0.0",
                           tools: list[SdkMcpTool] | None = None) -> SdkMcpServer:
    """创建进程内 MCP 服务器

    与外部 MCP 服务器（stdio 子进程）不同，SDK MCP 服务器
    在同一 Python 进程内运行，提供：
    - 更好的性能（无 IPC 开销）
    - 更简单的部署（单进程）
    - 更容易调试（同一进程）
    - 直接访问应用状态

    Args:
        name: 服务器唯一标识
        version: 版本号
        tools: SdkMcpTool 列表

    Returns:
        SdkMcpServer 实例
    """
    return SdkMcpServer(name=name, version=version, tools=tools)

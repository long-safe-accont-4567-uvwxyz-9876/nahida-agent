import os
import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable
from openai import AsyncOpenAI

from loguru import logger
from agent_dispatcher import AgentDispatcher
from emoji_config import get_status_msg


@dataclass
class TaskState:
    user_input: str
    user_id: str
    session_id: str = ""
    current_node: str = ""
    route_target: str = ""
    route_targets: list[str] = field(default_factory=list)
    route_plan: list[str] = field(default_factory=list)
    current_step_index: int = 0
    sub_agent_reply: str = ""
    intermediate_results: list[dict] = field(default_factory=list)
    final_output: str = ""
    progress_log: list[str] = field(default_factory=list)
    status_callback: Any = None
    _dispatcher: Any = None
    _agent_configs: dict = field(default_factory=dict)

    def update(self, updates: dict) -> "TaskState":
        for k, v in updates.items():
            if hasattr(self, k):
                setattr(self, k, v)
        return self

    async def push_progress(self, msg: str):
        self.progress_log.append(msg)
        if self.status_callback:
            try:
                await self.status_callback(msg)
            except Exception:
                pass


END = "__END__"
PARALLEL_EXECUTE = "__parallel_execute__"
SINGLE_EXECUTE = "__single_execute__"


class TaskGraph:
    def __init__(self):
        self._nodes: dict[str, Callable] = {}
        self._edges: dict[str, Callable] = {}
        self._entry_point: str = ""
        self._compiled = False

    def add_node(self, name: str, handler: Callable[[TaskState], Awaitable[dict]]):
        self._nodes[name] = handler

    def add_conditional_edge(self, source: str, condition_fn: Callable[[TaskState], Awaitable[str]]):
        self._edges[source] = condition_fn

    def set_entry_point(self, name: str):
        self._entry_point = name

    def compile(self) -> "TaskGraph":
        if not self._entry_point:
            raise ValueError("Entry point not set")
        if self._entry_point not in self._nodes:
            raise ValueError(f"Entry point node '{self._entry_point}' not found")
        self._compiled = True
        return self

    async def run(self, initial_state: TaskState) -> TaskState:
        if not self._compiled:
            raise RuntimeError("Graph not compiled. Call compile() first.")

        state = initial_state
        current = self._entry_point
        max_steps = 15

        for step in range(max_steps):
            if current == END:
                break

            handler = self._nodes.get(current)
            if not handler:
                logger.warning("task_graph.node_not_found", node=current)
                break

            state.current_node = current
            logger.info("task_graph.executing", node=current, step=step)

            try:
                updates = await handler(state)
                if updates:
                    state.update(updates)
            except Exception as e:
                logger.error("task_graph.node_error", node=current, error=str(e))
                state.final_output = f"\u4efb\u52a1\u6267\u884c\u51fa\u9519: {e}"
                break

            edge_fn = self._edges.get(current)
            if edge_fn:
                try:
                    result = edge_fn(state)
                    if asyncio.iscoroutine(result):
                        next_node = await result
                    else:
                        next_node = result
                    current = next_node
                except Exception as e:
                    logger.error("task_graph.edge_error", node=current, error=str(e))
                    break
            else:
                break

        return state


class RouterNode:
    @staticmethod
    def _rule_route(user_input: str) -> list[str]:
        q = user_input.lower()
        search_kw = ["\u641c\u7d22", "\u641c\u4e00\u4e0b", "\u67e5\u4e00\u4e0b", "\u627e\u4e00\u4e0b", "\u5e2e\u6211\u67e5", "\u5e2e\u6211\u641c", "\u641c\u7d22\u4e00\u4e0b",
                     "\u67e5\u8d44\u6599", "\u6700\u65b0", "\u65b0\u95fb", "\u8d44\u8baf", "\u83b7\u53d6\u7f51\u4e0a", "\u770b\u770b\u6709\u6ca1\u6709"]
        code_kw = ["\u4ee3\u7801", "\u7f16\u7a0b", "\u5199\u4ee3\u7801", "debug", "\u8c03\u8bd5", "\u7a0b\u5e8f", "\u5f00\u53d1", "\u90e8\u7f72",
                   "git", "api", "\u63a5\u53e3", "\u51fd\u6570", "\u811a\u672c", "\u8fd0\u884c", "\u6267\u884c\u547d\u4ee4",
                   "\u5de1\u68c0", "\u68c0\u67e5\u7cfb\u7edf", "\u78c1\u76d8", "\u5185\u5b58", "cpu", "\u8fdb\u7a0b", "\u670d\u52a1\u72b6\u6001",
                   "\u65e5\u5fd7", "\u76d1\u63a7", "\u7cfb\u7edf\u4fe1\u606f", "\u9999\u6a59\u6d3e", "orange pi", "\u670d\u52a1\u5668",
                   "docker", "\u5bb9\u5668", "\u7f51\u7edc", "\u7aef\u53e3", "\u9632\u706b\u5899", "\u914d\u7f6e\u6587\u4ef6",
                   "gpio", "i2c", "spi", "\u4f20\u611f\u5668", "led", "\u8235\u673a", "\u786c\u4ef6", "\u5f15\u811a",
                   "\u4e32\u53e3", "uart", "pwm", "adc", "dac",
                   "\u6444\u50cf\u5934", "\u62cd\u7167", "\u770b\u770b", "\u89c2\u5bdf", "\u8bc6\u522b", "\u68c0\u6d4b",
                   "\u91cd\u542f\u670d\u52a1", "\u90e8\u7f72", "\u670d\u52a1\u72b6\u6001", "\u7cfb\u7edf\u670d\u52a1",
                   "\u91cd\u542f", "\u670d\u52a1",
                   ]
        research_kw = ["\u7814\u7a76", "\u5206\u6790", "\u5b66\u672f", "\u8bba\u6587", "\u6df1\u5ea6", "\u8ba1\u7b97\u590d\u6742\u5ea6", "\u6570\u5b66\u8bc1\u660e",
                       "\u7269\u7406", "\u5316\u5b66", "\u751f\u7269", "\u7edf\u8ba1", "\u63a8\u5bfc", "\u516c\u5f0f"]
        parallel_trigger_kw = [
            "\u5168\u9762", "\u6574\u4f53", "\u7efc\u5408", "\u5404\u4e2a\u65b9\u9762", "\u591a\u65b9\u9762", "\u540c\u65f6",
            "\u5168\u90e8", "\u4e00\u8d77", "\u90fd\u68c0\u67e5", "\u90fd\u641c\u4e00\u4e0b", "\u5206\u522b",
            "\u5168\u65b9\u4f4d", "\u5f7b\u5e95", "\u5b8c\u6574", "\u6240\u6709", "\u5404\u4e2a\u677f\u5757",
            "\u5de1\u68c0", "\u4f53\u68c0", "\u8bca\u65ad", "\u5065\u5eb7\u68c0\u67e5", "\u72b6\u51b5\u62a5\u544a",
        ]

        matched = []
        if any(kw in q for kw in search_kw):
            matched.append("xilian")
        if any(kw in q for kw in code_kw):
            matched.append("yinlang")
        if any(kw in q for kw in research_kw):
            matched.append("nike")

        nahida_only_patterns = [
            "\u5929\u6c14", "\u6c14\u6e29", "\u6e29\u5ea6", "\u4e0b\u96e8", "\u6674\u5929", "\u9634\u5929",
            "\u65f6\u95f4", "\u51e0\u70b9", "\u73b0\u5728\u51e0\u70b9", "\u65e5\u671f", "\u4eca\u5929\u661f\u671f\u51e0",
            "\u7ffb\u8bd1", "\u610f\u601d\u662f\u4ec0\u4e48",
        ]
        if any(kw in q for kw in nahida_only_patterns):
            return ["nahida"]

        is_parallel = any(kw in q for kw in parallel_trigger_kw)

        if len(matched) > 1 and is_parallel:
            return matched
        if len(matched) == 1:
            return matched
        return ["nahida"]

    def __init__(self, client: AsyncOpenAI, model: str = "mimo-v2.5"):
        self._client = client
        self._model = model

    def _build_route_prompt(self, user_input: str, agent_configs: dict) -> str:
        agent_list = []
        for name, cfg in agent_configs.items():
            if name == "keli":
                continue
            caps = ", ".join(cfg.get("capabilities", []))
            desc = cfg.get("route_description", "")
            agent_list.append(f"- {name}\uff08{cfg.get('display_name', name)}\uff09: \u80fd\u529b[{caps}] {desc}")
        agent_list.append("- nahida\uff08\u7eb3\u897f\u59b2\uff09: \u80fd\u529b[chat, emotion, daily, general] \u65e5\u5e38\u5bf9\u8bdd\u3001\u60c5\u611f\u4ea4\u6d41\u3001\u7efc\u5408\u5206\u6790")

        return f"""\u4f60\u662f\u4e00\u4e2a\u4efb\u52a1\u8def\u7531\u5668\u3002\u6839\u636e\u7528\u6237\u8f93\u5165\uff0c\u51b3\u5b9a\u5e94\u8be5\u7531\u54ea\u4e9bAgent\u6765\u5904\u7406\u3002

\u53ef\u7528Agent\u5217\u8868:
{chr(10).join(agent_list)}

\u89c4\u5219:
1. \u8fd4\u56deAgent\u7684name\u5b57\u6bb5\u503c\uff0c\u591a\u4e2aAgent\u7528\u9017\u53f7\u5206\u9694\uff08\u5982\uff1ayinlang,xilian\uff09
2. \u7f16\u7a0b/\u4ee3\u7801/\u6280\u672f\u95ee\u9898 \u2192 yinlang
3. \u641c\u7d22/\u67e5\u8be2/\u63a2\u7d22/\u53d1\u73b0\u4fe1\u606f \u2192 xilian
4. \u7814\u7a76/\u5206\u6790/\u5b66\u672f/\u6df1\u5ea6\u601d\u8003 \u2192 nike
5. \u5982\u679c\u7528\u6237\u8981\u6c42\u5168\u9762/\u7efc\u5408/\u540c\u65f6\u5904\u7406\u591a\u4e2a\u65b9\u9762\uff0c\u53ef\u4ee5\u8fd4\u56de\u591a\u4e2aAgent\u540d\u79f0\uff0c\u7528\u9017\u53f7\u5206\u9694
6. \u65e5\u5e38\u95f2\u804a/\u60c5\u611f/\u7efc\u5408\u95ee\u9898 \u2192 nahida
7. \u5982\u679c\u4e0d\u786e\u5b9a\uff0c\u8fd4\u56de nahida
8. \u6700\u591a\u8fd4\u56de3\u4e2aAgent

\u7528\u6237\u8f93\u5165: {user_input}

\u8bf7\u53ea\u8fd4\u56deAgent\u540d\u79f0\uff08\u591a\u4e2a\u7528\u9017\u53f7\u5206\u9694\uff09:"""

    async def route(self, state: TaskState) -> dict:
        user_input = state.user_input
        agent_configs = state._agent_configs

        if not agent_configs:
            return {"route_targets": ["nahida"], "route_target": "nahida", "route_plan": ["nahida"]}

        rule_result = self._rule_route(user_input)
        if rule_result:
            targets = [t for t in rule_result if t in agent_configs or t == "nahida"]
            if not targets:
                targets = ["nahida"]
            display_names = []
            for t in targets:
                if t in agent_configs:
                    display_names.append(agent_configs[t].get("display_name", t))
                else:
                    display_names.append(t)
            if len(targets) == 1 and targets[0] == "nahida":
                pass
            else:
                await state.push_progress(f"\ud83d\udd00 \u8def\u7531\u5206\u6790\u5b8c\u6210 \u2192 \u4ea4\u7ed9{', '.join(display_names)}{'\u5e76\u884c\u5904\u7406' if len(targets) > 1 else ''}")
            return {
                "route_targets": targets,
                "route_target": targets[0] if len(targets) == 1 else "",
                "route_plan": targets,
            }

        prompt = self._build_route_prompt(user_input, agent_configs)
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=30,
            temperature=0.1,
        )
        msg = response.choices[0].message
        raw_result = msg.content.strip() if msg.content else ""

        if not raw_result:
            rc = getattr(msg, "reasoning_content", None) or ""
            raw_result = rc[:50] if rc else ""

        name_map = {}
        for n, cfg in agent_configs.items():
            name_map[n] = n
            name_map[cfg.get("display_name", "")] = n
        name_map["nahida"] = "nahida"
        name_map["\u7eb3\u897f\u59b2"] = "nahida"

        targets = []
        seen = set()
        for part in raw_result.replace("\uff0c", ",").split(","):
            part = part.strip()
            if not part:
                continue
            matched = name_map.get(part)
            if not matched:
                for key, val in name_map.items():
                    if key and key in part and val not in seen:
                        matched = val
                        break
            if matched and matched not in seen:
                targets.append(matched)
                seen.add(matched)

        if not targets:
            targets = ["nahida"]

        valid_targets = [t for t in targets if t in agent_configs or t == "nahida"]
        if not valid_targets:
            valid_targets = ["nahida"]

        display_names = []
        for t in valid_targets:
            if t in agent_configs:
                display_names.append(agent_configs[t].get("display_name", t))
            else:
                display_names.append(t)

        if not (len(valid_targets) == 1 and valid_targets[0] == "nahida"):
            await state.push_progress(f"\ud83d\udd00 LLM\u8def\u7531\u5206\u6790\u5b8c\u6210 \u2192 \u4ea4\u7ed9{', '.join(display_names)}{'\u5e76\u884c\u5904\u7406' if len(valid_targets) > 1 else ''}")

        return {
            "route_targets": valid_targets,
            "route_target": valid_targets[0] if len(valid_targets) == 1 else "",
            "route_plan": valid_targets,
        }


class ParallelAgentNode:
    def __init__(self, dispatcher: AgentDispatcher, route_client: AsyncOpenAI, route_model: str = "mimo-v2.5"):
        self._dispatcher = dispatcher
        self._route_client = route_client
        self._route_model = route_model

    def _build_decompose_prompt(self, user_input: str, targets: list[str], agent_configs: dict) -> str:
        target_descs = []
        for t in targets:
            if t in agent_configs:
                cfg = agent_configs[t]
                caps = ", ".join(cfg.get("capabilities", []))
                target_descs.append(f"- {t}\uff08{cfg.get('display_name', t)}\uff09\uff1a\u64c5\u957f [{caps}]")
            else:
                target_descs.append(f"- {t}")

        return f"""\u4f60\u9700\u8981\u5c06\u7528\u6237\u7684\u8bf7\u6c42\u62c6\u5206\u4e3a\u7ed9\u4e0d\u540cAgent\u7684\u5b50\u4efb\u52a1\u3002

\u7528\u6237\u539f\u59cb\u8bf7\u6c42: {user_input}

\u9700\u8981\u5206\u914d\u7ed9\u7684Agent:
{chr(10).join(target_descs)}

\u8bf7\u4e3a\u6bcf\u4e2aAgent\u751f\u6210\u4e00\u4e2a\u9488\u5bf9\u6027\u7684\u5b50\u4efb\u52a1\u63cf\u8ff0\u3002\u8981\u6c42\uff1a
1. \u6bcf\u4e2a\u5b50\u4efb\u52a1\u5e94\u8be5\u805a\u7126\u4e8e\u8be5Agent\u64c5\u957f\u7684\u9886\u57df
2. \u5b50\u4efb\u52a1\u4e4b\u95f4\u4e0d\u5e94\u8be5\u6709\u91cd\u590d\u7684\u5de5\u4f5c
3. \u6bcf\u4e2a\u5b50\u4efb\u52a1\u8981\u5177\u4f53\u3001\u53ef\u6267\u884c
4. \u4fdd\u6301\u539f\u95ee\u9898\u7684\u6838\u5fc3\u610f\u56fe

\u8bf7\u4e25\u683c\u6309\u4ee5\u4e0bJSON\u683c\u5f0f\u8f93\u51fa\uff0c\u4e0d\u8981\u8f93\u51fa\u5176\u4ed6\u5185\u5bb9\uff1a
{{\"\u5b50\u4efb\u52a1\": {{\"agent_name\": \"\u9488\u5bf9\u8be5Agent\u7684\u5177\u4f53\u5b50\u4efb\u52a1\u63cf\u8ff0\"}}}}"""
    async def _decompose_task(self, user_input: str, targets: list[str], agent_configs: dict) -> dict[str, str]:
        sub_tasks = {}
        capabilities_map = {}
        for t in targets:
            if t in agent_configs:
                cfg = agent_configs[t]
                capabilities_map[t] = cfg.get("capabilities", [])
                capabilities_map[t + "_desc"] = cfg.get("route_description", "")

        if len(targets) == 1:
            sub_tasks[targets[0]] = user_input
            return sub_tasks

        if len(targets) == 2:
            t0, t1 = targets[0], targets[1]
            cap0 = capabilities_map.get(t0, [])
            cap1 = capabilities_map.get(t1, [])
            desc0 = capabilities_map.get(t0 + "_desc", "")
            desc1 = capabilities_map.get(t1 + "_desc", "")

            sub_tasks[t0] = (
                f"\u7528\u6237\u8bf7\u6c42\uff1a{user_input}\n\n"
                f"\u4f60\u7684\u4e13\u957f\u9886\u57df\uff1a{desc0 or t0}\n"
                f"\u4f60\u7684\u80fd\u529b\uff1a{', '.join(cap0) if cap0 else '\u7efc\u5408\u5206\u6790'}\n\n"
                f"\u8bf7\u9488\u5bf9\u4e0a\u8ff0\u7528\u6237\u8bf7\u6c42\uff0c**\u4ec5\u4ece\u4f60\u64c5\u957f\u7684{desc0 or t0}\u89d2\u5ea6**\u7ed9\u51fa\u5177\u4f53\u7684\u5206\u6790\u3001\u7ed3\u8bba\u6216\u884c\u52a8\u65b9\u6848\u3002"
                f"\u805a\u7126\u6838\u5fc3\u95ee\u9898\uff0c\u8f93\u51fa\u5b9e\u8d28\u6027\u5185\u5bb9\uff0c\u4e0d\u8981\u6cdb\u6cdb\u800c\u8c08\u3002"
            )
            sub_tasks[t1] = (
                f"\u7528\u6237\u8bf7\u6c42\uff1a{user_input}\n\n"
                f"\u4f60\u7684\u4e13\u957f\u9886\u57df\uff1a{desc1 or t1}\n"
                f"\u4f60\u7684\u80fd\u529b\uff1a{', '.join(cap1) if cap1 else '\u7efc\u5408\u5206\u6790'}\n\n"
                f"\u8bf7\u9488\u5bf9\u4e0a\u8ff0\u7528\u6237\u8bf7\u6c42\uff0c**\u4ec5\u4ece\u4f60\u64c5\u957f\u7684{desc1 or t1}\u89d2\u5ea6**\u7ed9\u51fa\u5177\u4f53\u7684\u5206\u6790\u3001\u7ed3\u8bba\u6216\u884c\u52a8\u65b9\u6848\u3002"
                f"\u805a\u7126\u6838\u5fc3\u95ee\u9898\uff0c\u8f93\u51fa\u5b9e\u8d28\u6027\u5185\u5bb9\uff0c\u4e0d\u8981\u6cdb\u6cdb\u800c\u8c08\u3002"
            )
            return sub_tasks

        for i, t in enumerate(targets):
            desc = capabilities_map.get(t + "_desc", t)
            caps = capabilities_map.get(t, [])
            sub_tasks[t] = (
                f"\u3010\u4efb\u52a1{i+1}/{len(targets)}\u3011\u7528\u6237\u8bf7\u6c42\uff1a{user_input}\n\n"
                f"\u4f60\u7684\u4e13\u957f\u9886\u57df\uff1a{desc}\n"
                f"\u4f60\u7684\u80fd\u529b\uff1a{', '.join(caps) if caps else '\u7efc\u5408\u5206\u6790'}\n\n"
                f"\u8bf7**\u4e25\u683c\u9650\u5b9a\u5728\u4f60\u64c5\u957f\u7684{desc}\u9886\u57df\u5185**\uff0c\u9488\u5bf9\u8be5\u8bf7\u6c42\u7ed9\u51fa\u4e13\u4e1a\u3001\u5177\u4f53\u7684\u5206\u6790\u548c\u7ed3\u8bba\u3002"
                f"\u53ea\u8f93\u51fa\u4e0e\u4f60\u9886\u57df\u76f4\u63a5\u76f8\u5173\u7684\u5185\u5bb9\uff0c\u5ffd\u7565\u5176\u4ed6\u65b9\u9762\u3002"
            )

        return sub_tasks

    async def execute_single(self, target: str, task_prompt: str, state: TaskState) -> dict | None:
        agent = self._dispatcher.get_agent(target)
        if not agent or not agent.available:
            return {"agent": target, "display_name": target, "reply": f"{target}\u6682\u65f6\u4e0d\u53ef\u7528", "error": True}

        display_name = agent.config.display_name
        try:
            reply = await asyncio.wait_for(
                self._dispatcher.dispatch(target, task_prompt, status_callback=None),
                timeout=180,
            )
            if reply is None:
                reply = f"{display_name}\u73b0\u5728\u6709\u70b9\u7d2f\u4e86...\u7b49\u4f1a\u513f\u518d\u6765\u5427\uff01\ud83d\udca4"
            return {"agent": target, "display_name": display_name, "reply": reply}
        except asyncio.TimeoutError:
            return {"agent": target, "display_name": display_name, "reply": f"{display_name}\u5904\u7406\u8d85\u65f6", "error": True}
        except Exception as e:
            return {"agent": target, "display_name": display_name, "reply": f"{display_name}\u5904\u7406\u51fa\u9519: {e}", "error": True}

    async def execute(self, state: TaskState) -> dict:
        targets = state.route_targets
        if not targets:
            return {"sub_agent_reply": "", "final_output": ""}

        if len(targets) == 1:
            target = targets[0]
            if target == "nahida":
                return {"final_output": "", "sub_agent_reply": ""}
            single_result = await self.execute_single(target, state.user_input, state)
            if single_result:
                return {"sub_agent_reply": single_result.get("reply", ""), "intermediate_results": [single_result]}
            return {"sub_agent_reply": "", "intermediate_results": []}

        await state.push_progress(f"\u26a1 \u542f\u52a8\u5e76\u884c\u6a21\u5f0f\uff0c\u540c\u65f6\u8c03\u5ea6 {len(targets)} \u4e2aAgent...")

        sub_tasks = await self._decompose_task(state.user_input, targets, state._agent_configs)

        for t in targets:
            display_name = t
            if t in state._agent_configs:
                display_name = state._agent_configs[t].get("display_name", t)

        tasks = [
            self.execute_single(t, sub_tasks.get(t, state.user_input), state)
            for t in targets
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        intermediate = []
        for r in results:
            if isinstance(r, Exception):
                logger.error("parallel_agent.exception", error=str(r))
                intermediate.append({"agent": "unknown", "display_name": "\u672a\u77e5", "reply": f"\u6267\u884c\u5f02\u5e38: {r}", "error": True})
            elif isinstance(r, dict):
                display_name = r.get("display_name", r.get("agent", ""))
                status = "done" if not r.get("error") else "error"
                intermediate.append(r)

        all_replies = "\n\n".join([f"\u3010{r['display_name']}\u3011\n{r['reply']}" for r in intermediate])
        await state.push_progress(f"\ud83c\udfaf \u5168\u90e8{len(targets)}\u4e2aAgent\u5df2\u6267\u884c\u5b8c\u6bd5\uff0c\u8fdb\u5165\u7ed3\u679c\u7efc\u5408...")

        return {"sub_agent_reply": all_replies, "intermediate_results": intermediate}


class AgentNode:
    def __init__(self, dispatcher: AgentDispatcher):
        self._dispatcher = dispatcher

    async def execute(self, state: TaskState) -> dict:
        target = state.route_target
        if not target or target == "nahida":
            return {"final_output": "", "sub_agent_reply": ""}

        agent = self._dispatcher.get_agent(target)
        if not agent or not agent.available:
            await state.push_progress(f"\u26a0\ufe0f {target}\u6682\u65f6\u4e0d\u53ef\u7528")
            return {"sub_agent_reply": f"\u8be5Agent\u6682\u65f6\u4e0d\u53ef\u7528", "final_output": ""}

        display_name = agent.config.display_name
        await state.push_progress(get_status_msg(target, "using", f"{display_name}\u6b63\u5728\u5904\u7406...", agent.config.personality_file))

        try:
            reply = await asyncio.wait_for(
                self._dispatcher.dispatch(target, state.user_input, status_callback=None),
                timeout=180,
            )
            if reply is None:
                reply = f"{display_name}\u73b0\u5728\u6709\u70b9\u7d2f\u4e86...\u7b49\u4f1a\u513f\u518d\u6765\u5427\uff01\ud83d\udca4"

            await state.push_progress(get_status_msg(target, "done", f"{display_name}\u5df2\u5b8c\u6210\uff01", agent.config.personality_file))

            result_entry = {"agent": target, "display_name": display_name, "reply": reply}
            intermediate = list(state.intermediate_results)
            intermediate.append(result_entry)

            return {"sub_agent_reply": reply, "intermediate_results": intermediate}

        except asyncio.TimeoutError:
            logger.warning("agent_node.timeout", target=target)
            await state.push_progress(f"\u23f0 {display_name}\u5904\u7406\u8d85\u65f6")
            return {"sub_agent_reply": f"{display_name}\u5904\u7406\u8d85\u65f6\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5"}
        except Exception as e:
            logger.error("agent_node.execute_failed", target=target, error=str(e))
            await state.push_progress(f"\u274c {display_name}\u5904\u7406\u5931\u8d25")
            return {"sub_agent_reply": f"\u5904\u7406\u51fa\u9519: {e}"}


class SynthesisNode:
    def __init__(self, client: AsyncOpenAI, model: str = "mimo-v2.5", nahida_chat_callback=None):
        self._client = client
        self._model = model
        self._nahida_chat = nahida_chat_callback

    async def synthesize(self, state: TaskState) -> dict:
        results = state.intermediate_results
        if not results:
            return {"final_output": state.sub_agent_reply}

        await state.push_progress(get_status_msg("nahida", "done", "\u7eb3\u897f\u59b2\u6b63\u5728\u6574\u7406\u5168\u90e8\u7ed3\u679c...", None))

        parts = []
        for r in results:
            parts.append(f"\u3010{r['display_name']}\u7684\u56de\u590d\u3011\n{r['reply']}")
        combined = "\n\n".join(parts)

        if self._nahida_chat:
            try:
                agent_count = len(results)
                agent_names = "\u3001".join([r['display_name'] for r in results])
                prompt = f"""\u4ee5\u4e0b\u662f{agent_count}\u4f4d\u56e2\u961f\u6210\u5458\uff08{agent_names}\uff09\u7684\u5e76\u884c\u5de5\u4f5c\u7ed3\u679c\uff0c\u8bf7\u4f60\u6574\u7406\u540e\u5411\u7528\u6237\u505a\u4e00\u4efd\u5b8c\u6574\u7684\u6c47\u62a5\uff1a

{combined}

\u8981\u6c42\uff1a
- \u5148\u7ed9\u51fa\u4e00\u4e2a\u603b\u4f53\u6982\u8ff0\uff08\u4e00\u53e5\u8bdd\u603b\u7ed3\u5168\u5c40\u60c5\u51b5\uff09
- \u7136\u540e\u6309\u6bcf\u4e2a\u56e2\u961f\u6210\u5458\u5206\u677f\u5757\u6c47\u62a5\uff0c\u63d0\u53d6\u6240\u6709\u5177\u4f53\u7684\u4e8b\u5b9e\u3001\u6570\u636e\u3001\u6807\u9898\u548c\u5173\u952e\u4fe1\u606f
- \u6700\u540e\u7ed9\u51fa\u4e00\u4e2a\u7efc\u5408\u8bc4\u4f30\u6216\u5efa\u8bae
- \u7528\u6e05\u6670\u7684\u7ed3\u6784\u7ec4\u7ec7\uff0c\u5148\u603b\u8ff0\u518d\u5206\u70b9
- \u4e0d\u8981\u53ea\u8bf4\u7a7a\u6d1e\u7684\u611f\u60f3\u6216\u6bd4\u55bb\uff0c\u5fc5\u987b\u6709\u5b9e\u9645\u4fe1\u606f\u91cf
- \u8bed\u6c14\u6e29\u67d4\u4f46\u5185\u5bb9\u5fc5\u987b\u5145\u5b9e
- \u5982\u679c\u67d0\u4e2aAgent\u7684\u7ed3\u679c\u660e\u663e\u4e0d\u5b8c\u6574\u6216\u62a5\u9519\uff0c\u5b9e\u4e8b\u6c42\u662f\u8bf4\u660e"""
                final = await self._nahida_chat(prompt)
                return {"final_output": final}
            except Exception as e:
                logger.warning("synthesis.nahida_failed", error=str(e))

        if len(results) == 1:
            return {"final_output": results[0].get("reply", state.sub_agent_reply)}

        try:
            prompt = f"""\u8bf7\u5c06\u4ee5\u4e0b{len(results)}\u4e2aAgent\u7684\u5e76\u884c\u5de5\u4f5c\u7ed3\u679c\u6574\u7406\u6210\u6e05\u6670\u7684\u6c47\u62a5\uff0c\u63d0\u53d6\u6240\u6709\u5177\u4f53\u4fe1\u606f\uff1a

{combined}

\u8981\u6c42\uff1a
- \u5217\u51fa\u5177\u4f53\u7684\u4e8b\u5b9e\u3001\u6570\u636e\u3001\u6807\u9898
- \u5148\u4e00\u53e5\u8bdd\u603b\u8ff0\uff0c\u518d\u6309Agent\u5206\u70b9\u5217\u51fa\u5173\u952e\u4fe1\u606f
- \u4e0d\u8981\u7a7a\u6d1e\u7684\u6bd4\u55bb\uff0c\u5fc5\u987b\u6709\u5b9e\u9645\u5185\u5bb9"""
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                temperature=0.5,
            )
            final = response.choices[0].message.content.strip()
            return {"final_output": final}
        except Exception as e:
            logger.warning("synthesis.fallback_failed", error=str(e))
            return {"final_output": combined}


async def route_condition(state: TaskState) -> str:
    targets = state.route_targets
    if not targets or (len(targets) == 1 and targets[0] == "nahida"):
        return END
    if len(targets) > 1:
        return PARALLEL_EXECUTE
    return SINGLE_EXECUTE


def build_task_graph(dispatcher: AgentDispatcher, agent_configs: dict,
                     route_client: AsyncOpenAI, route_model: str = "mimo-v2.5",
                     nahida_chat_callback=None) -> TaskGraph:
    router = RouterNode(route_client, route_model)
    parallel_node = ParallelAgentNode(dispatcher, route_client, route_model)
    agent_node = AgentNode(dispatcher)
    synthesis = SynthesisNode(route_client, route_model, nahida_chat_callback=nahida_chat_callback)

    graph = TaskGraph()

    async def router_handler(state: TaskState) -> dict:
        return await router.route(state)

    async def parallel_handler(state: TaskState) -> dict:
        return await parallel_node.execute(state)

    async def agent_handler(state: TaskState) -> dict:
        return await agent_node.execute(state)

    async def synthesis_handler(state: TaskState) -> dict:
        return await synthesis.synthesize(state)

    graph.add_node("router", router_handler)
    graph.add_node(PARALLEL_EXECUTE, parallel_handler)
    graph.add_node(SINGLE_EXECUTE, agent_handler)
    graph.add_node("synthesis", synthesis_handler)

    graph.set_entry_point("router")

    graph.add_conditional_edge("router", route_condition)
    graph.add_conditional_edge(PARALLEL_EXECUTE, lambda s: "synthesis")
    graph.add_conditional_edge(SINGLE_EXECUTE, lambda s: "synthesis")
    graph.add_conditional_edge("synthesis", lambda s: END)

    graph.compile()

    graph._agent_configs = agent_configs
    graph._dispatcher = dispatcher
    graph._router = router
    graph._route_client = route_client
    graph._route_model = route_model

    return graph


async def run_task_graph(graph: TaskGraph, user_input: str, user_id: str,
                         session_id: str = "", status_callback=None,
                         agent_configs: dict = None,
                         dispatcher: AgentDispatcher = None) -> TaskState:
    state = TaskState(
        user_input=user_input,
        user_id=user_id,
        session_id=session_id,
        status_callback=status_callback,
        _dispatcher=dispatcher,
        _agent_configs=agent_configs or {},
    )
    result = await graph.run(state)
    return result

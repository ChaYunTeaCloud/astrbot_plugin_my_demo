from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.core.agent.tool import FunctionTool, ToolExecResult, ToolSet
from astrbot.core.agent.handoff import HandoffTool
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext
from astrbot.core.provider.register import llm_tools


def create_list_sub_agents_tool(orch):
    """工厂函数：接收 orchestrator，返回已注入数据的工具实例。"""
    info = _build_agents_info(orch)

    @dataclass
    class _Tool(FunctionTool[AstrAgentContext]):
        name: str = "list_sub_agents"
        description: str = (
            "列出当前可用的 SubAgent 及其描述和工具权限。"
            "当你需要把任务委派给其他 Agent 时，先调用此工具了解有哪些 Agent 可用。"
        )
        parameters: dict = Field(
            default_factory=lambda: {
                "type": "object",
                "properties": {},
                "required": [],
            }
        )

        async def call(
            self, context: ContextWrapper[AstrAgentContext], **kwargs
        ) -> ToolExecResult:
            return info

    return _Tool()


def _build_agents_info(orch) -> str:
    lines = ["当前可用的 SubAgent：\n"]
    if not orch or not orch.handoffs:
        lines.append("  (无已配置的 SubAgent)")
    else:
        for h in orch.handoffs:
            name = h.agent.name
            desc = h.description or "(无描述)"
            tools = h.agent.tools
            if tools is None:
                tools_str = "全部工具"
            elif not tools:
                tools_str = "无工具"
            else:
                tools_str = ", ".join(str(t) for t in tools)
            lines.append(f"  - {name}: {desc} [工具: {tools_str}]")
    return "\n".join(lines)

def create_delegate_tool(star_context):
    @dataclass
    class _Tool(FunctionTool[AstrAgentContext]):
        name: str = "delegate_to_sub_agent"
        description: str = (
            "将任务委派给指定的 SubAgent 并返回结果。"
            "先用 list_sub_agents 查看可用列表。"
        )
        parameters: dict = Field(
            default_factory=lambda: {
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string", "description": "目标 SubAgent 名称"},
                    "task": {"type": "string", "description": "完整的任务描述，需自包含所有上下文"},
                },
                "required": ["agent_name", "task"],
            }
        )

        async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
            agent_name = kwargs["agent_name"]
            task = kwargs["task"]
            event = context.context.event
            ctx = context.context.context

            orch = star_context.subagent_orchestrator
            for h in orch.handoffs:
                if h.agent.name == agent_name:
                    handoff = h
                    break
            else:
                return f"未找到 Agent: {agent_name}"

            toolset = _build_toolset(handoff.agent.tools)
            umo = event.unified_msg_origin
            prov_id = handoff.provider_id or await ctx.get_current_chat_provider_id(umo)

            resp = await ctx.tool_loop_agent(
                event=event, chat_provider_id=prov_id,
                prompt=task, system_prompt=handoff.agent.instructions,
                tools=toolset,
            )
            return resp.completion_text or "(空回复)"

    return _Tool()


def _build_toolset(agent_tools):
    if agent_tools == []:
        return None
    toolset = ToolSet()
    if agent_tools is None:
        for t in llm_tools.func_list:
            if isinstance(t, HandoffTool) or not t.active:
                continue
            toolset.add_tool(t)
    else:
        for name in agent_tools:
            t = llm_tools.get_func(name)
            if t and t.active:
                toolset.add_tool(t)
    return toolset
from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext


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

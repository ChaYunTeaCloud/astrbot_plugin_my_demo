from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.api import logger
from astrbot.core.agent.tool import FunctionTool, ToolExecResult, ToolSet
from astrbot.core.agent.handoff import HandoffTool
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext
from astrbot.core.provider.register import llm_tools


def create_list_sub_agents_tool(orch):
    """工厂函数：接收 orchestrator,返回已注入数据的 list_sub_agents 工具。 args: orch - orchestrator"""
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
    """ 构建 SubAgent 信息字符串。 args: orch - orchestrator"""
    lines = ["当前可用的 SubAgent:\n"]
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

def create_delegate_to_sub_agent(star_context):
    """工厂函数：接收 orchestrator,返回已注入数据的 delegate_to_sub_agent 工具。 args: star_context - 当前上下文"""
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
            """ 调用指定 SubAgent 并返回结果。 args: self - 工具实例,context - 当前上下文,kwargs - 工具参数"""
            agent_name = kwargs["agent_name"]   # 目标 SubAgent 名称
            task = kwargs["task"]    # 任务描述
            event = context.context.event    # 当前事件
            ctx = context.context.context    # 当前上下文

            orch = star_context.subagent_orchestrator    # 子 Agent 调度器
            for h in orch.handoffs:    # 遍历所有 Handoff
                if h.agent.name == agent_name:  # 如果找到目标 SubAgent
                    handoff = h    # 记录当前 Handoff 信息
                    break
            else:
                return f"未找到 Agent: {agent_name}"    # 如果未找到目标 SubAgent，返回错误信息

            toolset = _build_toolset(handoff.agent.tools)    # 构建工具集
            umo = event.unified_msg_origin    # 获取统一消息来源
            prov_id = handoff.provider_id or await ctx.get_current_chat_provider_id(umo)    # 获取当前聊天提供者 ID

            resp = await ctx.tool_loop_agent(    # 调用目标 SubAgent
                event=event, chat_provider_id=prov_id,    # 传递当前事件和当前聊天提供者 ID
                prompt=task, system_prompt=handoff.agent.instructions,    # 传递任务描述和系统提示
                tools=toolset,    # 传递工具集
            )
            return resp.completion_text or "(空回复)"    # 返回目标 SubAgent 的回复文本

    return _Tool()


def _build_toolset(agent_tools):
    """ 构建工具集。 args: agent_tools - 目标 SubAgent 工具列表"""
    if agent_tools == []:
        return None
    toolset = ToolSet() # 初始化工具集
    if agent_tools is None:    # 如果目标 SubAgent 工具列表为 None
        logger.info(f"llm_tools count: {len(llm_tools.func_list)}, names: {[t.name for t in llm_tools.func_list]}")
        for t in llm_tools.func_list:
            if isinstance(t, HandoffTool) or not t.active:  # 如果是 HandoffTool 或未激活，跳过
                continue
            toolset.add_tool(t)    # 添加工具到工具集
    else:
        for name in agent_tools:
            t = llm_tools.get_func(name)
            if t and t.active:
                toolset.add_tool(t)    # 添加工具到工具集
    return toolset
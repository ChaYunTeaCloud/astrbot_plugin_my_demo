from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.core.agent.tool import ToolSet
from astrbot.core.agent.handoff import HandoffTool
from astrbot.core.provider.register import llm_tools

from .tools import create_list_sub_agents_tool


@register("astrbot_plugin_my_demo", "ChaYunTeaCloud",
          "SubAgent 路由层插件", "0.1.0")
class SubAgentRouter(Star):
    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        cfg = config or {}
        self.nested_mode: bool = bool(cfg.get("nested_mode", False))
        self.router_agent: str = cfg.get("router_agent", "")

    async def initialize(self):
        pass

    async def terminate(self):
        pass

    @filter.on_llm_request()
    async def _on_llm_request(self, event: AstrMessageEvent, request) -> None:
        if not hasattr(request, "func_tool") or not request.func_tool:
            return

        tools = getattr(request.func_tool, "tools", None)
        if not isinstance(tools, list):
            return

        if not self.nested_mode:
            # 移除 delegate_to_sub_agent
            request.func_tool.tools = [
                t for t in tools
                if getattr(t, "name", None) != "delegate_to_sub_agent"
            ]
            return

        # 嵌套模式：注入 list_sub_agents
        if not any(getattr(t, "name", None) == "list_sub_agents" for t in tools):
            orch = self.context.subagent_orchestrator
            tools.append(create_list_sub_agents_tool(orch))
            logger.debug("astrbot_plugin_my_demo: 注入 list_sub_agents")

    @filter.llm_tool(name="delegate_to_sub_agent")
    async def delegate_to_sub_agent(
        self, event: AstrMessageEvent,
        agent_name: str,
        task: str,
    ) -> str:
        """将任务委派给指定的 SubAgent 并返回结果。

        Args:
            agent_name(string): 目标 SubAgent 名称。先用 list_sub_agents 查看可用列表
            task(string): 完整的任务描述
        """
        orch = self.context.subagent_orchestrator
        handoff = None
        for h in orch.handoffs:
            if h.agent.name == agent_name:
                handoff = h
                break
        if not handoff:
            return f"未找到 Agent: {agent_name}"

        # 根据 SubAgent 的 tools 配置构建 ToolSet
        agent_tools = handoff.agent.tools

        if agent_tools == []:
            toolset = None
        elif agent_tools is None:
            toolset = ToolSet()
            for t in llm_tools.func_list:
                if isinstance(t, HandoffTool):
                    continue
                if t.active:
                    toolset.add_tool(t)
        else:
            toolset = ToolSet()
            for name in agent_tools:
                t = llm_tools.get_func(name)
                if t and t.active:
                    toolset.add_tool(t)

        umo = event.unified_msg_origin
        prov_id = handoff.provider_id or await self.context.get_current_chat_provider_id(umo)

        llm_resp = await self.context.tool_loop_agent(
            event=event,
            chat_provider_id=prov_id,
            prompt=task,
            system_prompt=handoff.agent.instructions,
            tools=toolset,
        )
        return llm_resp.completion_text or "(空回复)"
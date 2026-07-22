import yaml, os

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig

from .tools import create_list_sub_agents_tool, create_delegate_tool

_META = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "metadata.yaml"), encoding="utf-8"))

@register(_META["name"], _META["author"], _META["desc"], _META["version"])
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
        """嵌套模式: 注入 list_sub_agents 和 delegate_to_sub_agent 到请求中"""
        if not hasattr(request, "func_tool") or not request.func_tool:
            logger.error("astrbot_plugin_my_demo: 请求中没有工具集")
            return
        tools = getattr(request.func_tool, "tools", None)   # 获取当前请求中的工具列表
        if not isinstance(tools, list):
            logger.error("astrbot_plugin_my_demo: 工具列表不是列表")
            return

        if not self.nested_mode:    # 如果不是嵌套模式，直接返回
            return

        # 注入 list_sub_agents 和 delegate_to_sub_agent 工具
        orch = self.context.subagent_orchestrator
        tools.append(create_list_sub_agents_tool(orch))
        tools.append(create_delegate_tool(self.context))

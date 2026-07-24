from astrbot.api import logger
from astrbot.api.star import Context, Star
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.provider import ProviderRequest

# 注册插件
class SubAgentRouter(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        logger.info("SubAgentRouter initialized")

        cfg = context.get_config()
        """插件配置"""

        self.nested_mode: bool = bool(cfg.get("nested_mode", False))
        """是否开启嵌套模式"""

        self.router_agent: str = cfg.get("router_agent", "")
        """路由智能体名称"""

    async def initialize(self):
        pass

    async def terminate(self):
        pass

    @filter.on_llm_request()
    async def _on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest) -> None:
        
        return None

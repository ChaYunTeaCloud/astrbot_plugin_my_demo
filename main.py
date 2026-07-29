from astrbot.api import logger
from astrbot.api.star import Context, Star
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.provider import ProviderRequest

from astrbot.core.agent.tool import FunctionTool, ToolExecResult


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

        async def _get_weather_handler(event: AstrMessageEvent, **kwargs) -> str:
            """实际的 handler，第一个参数是 event"""
            city = kwargs.get("city", "北京")
            date = kwargs.get("date", "")
            weather = "晴"
            return f"{city}{date}{weather}"

        weather_tool = FunctionTool(
            name="get_weather",
            description="获取指定城市的天气信息",
            parameters={
                        "type": "object",
                        "properties": {
                            "city": {"type": "string", "description": "城市名称"},
                            "date": {"type": "string", "description": "日期（可选）"}
                        },
                        "required": ["city"]
                    },
            handler=_get_weather_handler
        )
        
        # 注册到框架
        # self.context.add_llm_tools(weather_tool)
        # 注入到请求中
        req.func_tool.add_tool(weather_tool)

        return None

    # @filter.llm_tool(name="get_weather")
    # # async def get_weather(self, event: AstrMessageEvent, city: str):
    # async def get_weather(self, event: AstrMessageEvent, city: str, date: str = "今天") -> ToolExecResult:
    #     """获取指定城市的天气信息
        
    #     Args:
    #         city(str): 城市名称（必填）
    #         date(str): 日期（可选）
    #     """
    #     # city = kwargs.get("city", "北京")
    #     # date = kwargs.get("date", "今天")
    #     # 调用天气 API
    #     weather = "晴"
    #     return f"{city}{date}{weather}"

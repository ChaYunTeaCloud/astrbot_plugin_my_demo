from astrbot.api.star import Context, Star
from astrbot.api import logger

# 注册插件
class SubAgentRouter(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        logger.info("SubAgentRouter initialized")

    async def initialize(self):
        pass

    async def terminate(self):
        pass

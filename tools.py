from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext


@dataclass
class TestTool(FunctionTool[AstrAgentContext]):
    name: str = "test_tool"
    description: str = "这是一个测试工具"
    args: dict = Field(description="工具参数")

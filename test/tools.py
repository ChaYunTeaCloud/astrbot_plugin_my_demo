from pydantic import Field
from pydantic.dataclasses import dataclass

from astrbot.api import logger
from astrbot.core.agent.tool import FunctionTool, ToolExecResult, ToolSet
from astrbot.core.agent.handoff import HandoffTool
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext
from astrbot.core.provider.register import llm_tools
from astrbot.core.tools.computer_tools import (
    CuaKeyboardTypeTool,
    CuaMouseClickTool,
    CuaScreenshotTool,
    ExecuteShellTool,
    FileDownloadTool,
    FileEditTool,
    FileReadTool,
    FileUploadTool,
    FileWriteTool,
    GrepTool,
    LocalPythonTool,
    PythonTool,
)


def create_list_sub_agents_tool(orch):
    """工厂函数：接收 orchestrator,返回已注入数据的 list_sub_agents 工具。 args: orch - orchestrator"""

    # 构建 SubAgent 信息字符串
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

            toolset = _build_toolset(handoff.agent.tools, star_context.get_llm_tool_manager(), ctx, event)    # 构建工具集
            if toolset is None:    # SubAgent 无可用工具时，构建空工具集以承载路由工具
                toolset = ToolSet()
            umo = event.unified_msg_origin    # 获取统一消息来源
            prov_id = handoff.provider_id or await ctx.get_current_chat_provider_id(umo)    # 获取当前聊天提供者 ID

            # 注入路由工具
            toolset.add_tool(create_list_sub_agents_tool(orch))
            toolset.add_tool(create_delegate_to_sub_agent(star_context))

            resp = await ctx.tool_loop_agent(    # 调用目标 SubAgent
                event=event, chat_provider_id=prov_id,    # 传递当前事件和当前聊天提供者 ID
                prompt=task, system_prompt=handoff.agent.instructions,    # 传递任务描述和系统提示
                tools=toolset,    # 传递工具集
            )
            return resp.completion_text or "(空回复)"    # 返回目标 SubAgent 的回复文本

    return _Tool()


def _get_runtime_computer_tools(runtime, tool_mgr, booter=None):
    """根据 runtime 获取系统内置计算机工具（shell/python/文件/grep 等）。
    这些工具不在 get_full_tool_set() 中，需通过 get_builtin_tool(ToolClass) 单独获取。
    args: runtime - 运行时类型 (sandbox/local), tool_mgr - 工具管理器, booter - 沙箱启动器类型 (cua 等)
    """
    booter = "" if booter is None else str(booter).lower()
    if runtime == "sandbox":
        shell_tool = tool_mgr.get_builtin_tool(ExecuteShellTool)
        python_tool = tool_mgr.get_builtin_tool(PythonTool)
        upload_tool = tool_mgr.get_builtin_tool(FileUploadTool)
        download_tool = tool_mgr.get_builtin_tool(FileDownloadTool)
        read_tool = tool_mgr.get_builtin_tool(FileReadTool)
        write_tool = tool_mgr.get_builtin_tool(FileWriteTool)
        edit_tool = tool_mgr.get_builtin_tool(FileEditTool)
        grep_tool = tool_mgr.get_builtin_tool(GrepTool)
        tools = {
            shell_tool.name: shell_tool,
            python_tool.name: python_tool,
            upload_tool.name: upload_tool,
            download_tool.name: download_tool,
            read_tool.name: read_tool,
            write_tool.name: write_tool,
            edit_tool.name: edit_tool,
            grep_tool.name: grep_tool,
        }
        if booter == "cua":
            screenshot_tool = tool_mgr.get_builtin_tool(CuaScreenshotTool)
            mouse_click_tool = tool_mgr.get_builtin_tool(CuaMouseClickTool)
            keyboard_type_tool = tool_mgr.get_builtin_tool(CuaKeyboardTypeTool)
            tools.update(
                {
                    screenshot_tool.name: screenshot_tool,
                    mouse_click_tool.name: mouse_click_tool,
                    keyboard_type_tool.name: keyboard_type_tool,
                }
            )
        return tools
    if runtime == "local":
        shell_tool = tool_mgr.get_builtin_tool(ExecuteShellTool)
        python_tool = tool_mgr.get_builtin_tool(LocalPythonTool)
        read_tool = tool_mgr.get_builtin_tool(FileReadTool)
        write_tool = tool_mgr.get_builtin_tool(FileWriteTool)
        edit_tool = tool_mgr.get_builtin_tool(FileEditTool)
        grep_tool = tool_mgr.get_builtin_tool(GrepTool)
        return {
            shell_tool.name: shell_tool,
            python_tool.name: python_tool,
            read_tool.name: read_tool,
            write_tool.name: write_tool,
            edit_tool.name: edit_tool,
            grep_tool.name: grep_tool,
        }
    return {}


def _build_toolset(agent_tools, tool_mgr, ctx, event):
    """构建工具集（插件工具 + 系统内置计算机工具）。
    args: agent_tools - 目标 SubAgent 工具列表 (None=全部, []=无, [...] 白名单),
          tool_mgr - 工具管理器, ctx - AstrAgentContext, event - 当前事件
    """
    # 读取 provider_settings 以确定 computer_use_runtime
    umo = event.unified_msg_origin
    cfg = ctx.get_config(umo=umo)
    provider_settings = cfg.get("provider_settings", {})
    runtime = str(provider_settings.get("computer_use_runtime", "local"))
    booter = provider_settings.get("sandbox", {}).get("booter")

    # 系统内置计算机工具需单独获取，get_full_tool_set() 不包含它们
    runtime_computer_tools = _get_runtime_computer_tools(runtime, tool_mgr, booter)

    if agent_tools is None:    # None 表示"全部工具"
        toolset = ToolSet()
        # 排除 HandoffTool（transfer_to_*），避免 SubAgent 递归 handoff
        handoff_names = {
            t.name for t in tool_mgr.func_list if isinstance(t, HandoffTool)
        }
        for registered_tool in tool_mgr.get_full_tool_set():
            if registered_tool.name in handoff_names:
                continue
            if getattr(registered_tool, "active", True):
                toolset.add_tool(registered_tool)
        # 追加系统内置计算机工具
        for runtime_tool in runtime_computer_tools.values():
            toolset.add_tool(runtime_tool)
        return None if toolset.empty() else toolset

    if not agent_tools:    # 空列表表示"无工具"
        return None

    # 白名单模式：按名称解析，先查插件工具，再查系统内置计算机工具
    toolset = ToolSet()
    for name in agent_tools:
        registered_tool = tool_mgr.get_func(name)
        if registered_tool and getattr(registered_tool, "active", True):
            toolset.add_tool(registered_tool)
            continue
        runtime_tool = runtime_computer_tools.get(name)
        if runtime_tool:
            toolset.add_tool(runtime_tool)
    return None if toolset.empty() else toolset
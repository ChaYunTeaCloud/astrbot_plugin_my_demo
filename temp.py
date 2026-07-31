from astrbot.api import logger, FunctionTool, ToolSet
from astrbot.api.star import Context
from astrbot.api.event import AstrMessageEvent

from astrbot.core.skills.skill_manager import SkillManager, build_skills_prompt

class MyToolManager:
    def __init__(self, context: Context):
        self._tool_set = ToolSet()
        """用于缓存所有自定义工具"""
        self._context = context
        """上下文实例"""
        self._cfg = context.get_config()
        """配置实例"""
        self._BUILTIN_TOOL_GROUPS = {
            # ═══════════════════════════════════════════════════════════════
            # 说明：
            #   因 AstrBot 原生不支持配置系统内置工具故维护此映射表
            #   至少 2026-7-31 日前：
            #   AstrBot的实现中不会给SubAgent注入除沙箱能力外的其它系统内置工具
            #   以下分类中，runtime_common、sandbox_only、local_only 以及 cua
            #   这些是 `_get_runtime_computer_tools()` 可能会注入的工具
            #   sandbox 模式：除 execute_python 外的 8 个
            #   local 模式：不含 upload/download/ipython，用 execute_python 替代
            #   cua booter：sandbox 8 个 + cua 3 个
            # ═══════════════════════════════════════════════════════════════
            # ═══════════════════════════════════════════════════════════════
            # Runtime 共有基础（5 个）
            # sandbox & local 都会注入
            # ═══════════════════════════════════════════════════════════════
            "runtime_common": [
                # ▼ _get_runtime_computer_tools 注入（sandbox & local）
                "astrbot_execute_shell",      # 执行 Shell 命令
                "astrbot_file_read_tool",     # 读取文件（文本/图片/PDF/docx/epub）
                "astrbot_file_write_tool",    # 写入 UTF-8 文本文件
                "astrbot_file_edit_tool",     # 编辑文件（文本替换）
                "astrbot_grep_tool",          # ripgrep 搜索文件内容
            ],

            # ═══════════════════════════════════════════════════════════════
            # sandbox 专用（3 个）
            # _get_runtime_computer_tools 在 runtime=="sandbox" 时注入
            # ═══════════════════════════════════════════════════════════════
            "sandbox_only": [
                # ▼ _get_runtime_computer_tools 注入（sandbox 专用）
                "astrbot_execute_ipython",    # IPython 交互执行（沙箱内）
                "astrbot_upload_file",        # 宿主机 → 沙箱 上传文件
                "astrbot_download_file",      # 沙箱 → 宿主机 下载文件
            ],

            # ═══════════════════════════════════════════════════════════════
            # local 专用（1 个）
            # _get_runtime_computer_tools 在 runtime=="local" 时注入
            # ═══════════════════════════════════════════════════════════════
            "local_only": [
                # ▼ _get_runtime_computer_tools 注入（local 专用）
                "astrbot_execute_python",     # 本地 Python 执行（非沙箱）
            ],

            # ═══════════════════════════════════════════════════════════════
            # CUA 图形界面工具（3 个）,cua 即 Computer Use Agent，支持 GUI 操作
            # 说明：_get_runtime_computer_tools 在 sandbox + booter=="cua" 时注入
            # ═══════════════════════════════════════════════════════════════
            "cua": [
                # ▼ _get_runtime_computer_tools 注入（sandbox + cua booter）
                "astrbot_cua_screenshot",     # CUA 桌面截图
                "astrbot_cua_mouse_click",    # CUA 鼠标点击坐标
                "astrbot_cua_keyboard_type",  # CUA 键盘输入文本
            ],

            # ═══════════════════════════════════════════════════════════════
            # Neo Skill 管理工具（12 个）
            # 说明：不由 _get_runtime_computer_tools 注入，需手动加入 toolset
            # ═══════════════════════════════════════════════════════════════
            "neo_skill": [
                # 执行历史
                "astrbot_get_execution_history",    # 获取沙箱执行历史记录
                "astrbot_annotate_execution",       # 标注一条执行历史

                # Skill Payload 管理（Step 1/3）
                "astrbot_create_skill_payload",     # 创建不可变的 Skill Payload
                "astrbot_get_skill_payload",        # 按 payload_ref 获取 Payload

                # Skill Candidate 管理（Step 2/3）
                "astrbot_create_skill_candidate",   # 创建 Skill 候选（绑定证据+标识）
                "astrbot_list_skill_candidates",    # 列出 Skill 候选
                "astrbot_evaluate_skill_candidate", # 评估 Skill 候选

                # Skill Release 管理（Step 3/3）
                "astrbot_promote_skill_candidate",  # 候选 → canary/stable 发布
                "astrbot_list_skill_releases",      # 列出已发布 Skill
                "astrbot_rollback_skill_release",   # 回滚一次 Skill 发布
                "astrbot_sync_skill_release",       # 同步 stable 发布到本地 SKILL.md

                # Skill 运行
                "astrbot_run_browser_skill",        # 按 skill_key 运行已发布的浏览器 Skill
            ],

            # ═══════════════════════════════════════════════════════════════
            # 浏览器工具（2 个）
            # 说明：不由 _get_runtime_computer_tools 注入，需手动加入 toolset
            # ═══════════════════════════════════════════════════════════════
            "browser": [
                "astrbot_execute_browser",        # 在沙箱执行单条浏览器自动化命令
                "astrbot_execute_browser_batch",  # 在沙箱批量执行浏览器命令
            ],

            # ═══════════════════════════════════════════════════════════════
            # 网页搜索及提取工具（9 个）
            # 说明：不由 _get_runtime_computer_tools 注入，需手动加入 toolset
            # ═══════════════════════════════════════════════════════════════
            "web_search": [
                "web_search_tavily",           # Tavily 联网搜索
                "tavily_extract_web_page",     # Tavily 提取网页正文
                "web_search_bocha",            # Bocha 联网搜索
                "web_search_brave",            # Brave 联网搜索
                "web_search_firecrawl",        # Firecrawl 联网搜索
                "firecrawl_extract_web_page",  # Firecrawl 提取网页正文
                "web_search_baidu",            # 百度 AI 联网搜索
                "web_search_exa",              # Exa AI 语义搜索
                "exa_get_contents",            # Exa 提取网页正文
            ],

            # ═══════════════════════════════════════════════════════════════
            # 系统功能工具（3 个）
            # 说明：不由 _get_runtime_computer_tools 注入，需手动加入 toolset
            # ═══════════════════════════════════════════════════════════════
            "system": [
                "send_message_to_user",        # 主动发送消息/媒体给用户
                "future_task",                 # 管理定时/一次性任务（cron/run_at）
                "astr_kb_search",              # 知识库查询
            ],
        }
        """系统内置工具集"""

    def get_list_subagent_tool(self) -> FunctionTool:
        """获取 list_subagent 工具"""
        tool = self._tool_set.get_tool("list_subagent")
        if tool:
            return tool
        async def _handler(event: AstrMessageEvent) -> str:
            """获取现有的 SubAgent 列表"""
            logger.debug("list_subagent: 获取现有的 SubAgent 列表")

            handoffs = self._context.subagent_orchestrator.handoffs
            result = []
            for h in handoffs:
                agent = h.agent  # Agent 实例
                result.append({
                    # "handoff_name": h.name,           # 工具名称 transfer_to_{agent_name}
                    "agent_name": agent.name,         # Agent 名称
                    # "instructions": agent.instructions,  # 系统提示词(人格设定)
                    "tool_description": h.description,  # 工具描述
                    "tools": agent.tools,             # 可用工具列表
                    "has_begin_dialogs": bool(agent.begin_dialogs),  # 是否有预设对话
                    # "provider_id": h.provider_id,    # 专用 Provider ID
                })
            # yield event.plain_result(f"已注册的 SubAgent: {result}")
            return f"已有的 SubAgent 列表: {result}"

        tool = FunctionTool(
            name="list_subagent",
            description="获取现有的 SubAgent 列表",
            parameters={},
            handler=_handler,
        )
        self._tool_set.add_tool(tool)
        return tool

    def get_call_subagent_tool(self) -> FunctionTool:
        """获取 call_subagent 工具"""
        tool = self._tool_set.get_tool("call_subagent")
        if tool:
            return tool
        
        async def _handler(event: AstrMessageEvent, agent_name: str) -> str:
            """调用指定 SubAgent"""
            logger.debug(f"call_subagent: 委派给 Agent {agent_name}")

            # 获取指定 SubAgent 的 handoff 工具和 Agent 实例
            handoff_tool = next(
                (h for h in self._context.subagent_orchestrator.handoffs if h.agent.name == agent_name),
                None
            )
            if handoff_tool is None:
                logger.warning(f"call_subagent: Agent {agent_name} 不存在")
                return f"Agent {agent_name} 不存在"
            agent = handoff_tool.agent  # Agent 实例
            if agent is None:
                logger.warning(f"call_subagent: Agent {agent_name} 不存在")
                return f"Agent {agent_name} 不存在"
            

            # 获取Agent能力需使用系统内置工具的集合
            computer_use_tool_set = self._get_computer_use_toolset()

            # 获取 neo Skill 能力所需系统工具集合
            neo_skill_tool_set = self._get_builtin_toolset_by_group_key("neo_skill")

            # # 获取人格设定管理器
            # persona_mgr = self._context.persona_manager
            # persona = persona_mgr.get_persona(agent_name)

            # 调用 SubAgent
            result = ""
            result += f"Agent {agent_name} 的能力需使用工具:\n"
            for tool in computer_use_tool_set.tools:
                result += f"{tool.name}: {tool.description}\n"
            result += f"Agent {agent_name} 的 neo Skill 能力所需系统工具:\n"
            for tool in neo_skill_tool_set.tools:
                result += f"{tool.name}: {tool.description}\n"

            # 先不实现真正的调用逻辑，先测试获取handoff以及agent是否正常，都拿到了什么内容
            # result += f"handoff 的内容:\n"
            # result += f"description: {handoff_tool.description}\n"
            # result += f"provider_id: {handoff_tool.provider_id}\n"
            # result += "agent 的内容:\n"
            # result += f"name: {agent.name}\n"
            # result += f"instructions: {agent.instructions}\n"
            # result += f"tools: {agent.tools}\n"
            # result += f"run_hooks: {agent.run_hooks}\n"
            # result += f"has_begin_dialogs: {bool(agent.begin_dialogs)}\n"
            # result += f"other_tools: {other_tools}\n"
            # result += f"system_tools: {system_tools}\n"
            # result += f"other_tool_set 的内容:\n"
            # for tool in other_tool_set.tools:
            #     result += f"{tool.name}: {tool.description}\n"
            # result += f"system_tool_set 的内容:\n"
            # for tool in system_tool_set.tools:
            #     result += f"{tool.name}: {tool.description}\n"
            # result += f"通过 iter_builtin_tool_classes 尝试获取所有系统内置工具的内容:\n"
            # for tool_cls in iter_builtin_tool_classes():
            #     tool_instance  = tool_mgr.get_builtin_tool(tool_cls)
            #     result += f"className:{tool_cls.__name__},{tool_instance.name}: {tool_instance.description}\n"
            return result

        tool = FunctionTool(
            name="call_subagent",
            description="调用指定 SubAgent",
            parameters={
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": "要调用的 SubAgent 名称",
                    },
                },
                "required": ["agent_name"],
            },
            handler=_handler,
        )
        self._tool_set.add_tool(tool)
        return tool

    def _get_computer_use_toolset(self) -> ToolSet:
        """根据当前配置获取Agent能力需使用工具的集合"""
        runtime = self._cfg["provider_settings"]["computer_use_runtime"]
        booter  = self._cfg["provider_settings"]["sandbox"]["booter"]

        names = list(self._BUILTIN_TOOL_GROUPS["runtime_common"])

        if runtime == "local":
            names += self._BUILTIN_TOOL_GROUPS["local_only"]
        else:  # sandbox
            names += self._BUILTIN_TOOL_GROUPS["sandbox_only"]
            if booter == "cua":
                names += self._BUILTIN_TOOL_GROUPS["cua"]

        return self._get_builtin_toolset_by_names(names)

    def _get_builtin_toolset_by_names(self, names: list[str]) -> ToolSet:
        """根据系统内置工具名称列表获取系统内置工具实例集合"""
        tool_set = ToolSet()
        tool_mgr = self._context.get_llm_tool_manager()
        for name in names:
            tool_set.add_tool(tool_mgr.get_builtin_tool(name))
        return tool_set

    def _get_builtin_toolset_by_group_key(self, key: str) -> ToolSet:
        """根据系统内置工具名称键获取系统内置工具实例集合"""
        names = self._BUILTIN_TOOL_GROUPS[key]
        return self._get_builtin_toolset_by_names(names)

    async def _get_skills_prompt(self, agent_name: str) -> str:
        """根据 Persona 的 skills 配置获取应注入的 Skill prompt"""
        # 1. 找到此 agent 的 persona_id
        persona_id = None
        for item in self._cfg["subagent_orchestrator"]["agents"]:
            if item.get("name") == agent_name:
                persona_id = item.get("persona_id")
                break
        if not persona_id:
            return ""

        # 2. 拿到 persona 数据
        persona = await self._context.persona_manager.get_persona(persona_id)
        if not persona:
            return ""

        # 3. 拿 skills 白名单
        allowed_skills = persona.skills
        if allowed_skills is None:
            return ""  # None = 不限制，但 SubAgent 默认也不注入，保持原行为
        if not allowed_skills:
            return ""  # [] = 禁用全部

        # 4. 获取全部可用 skill，按白名单过滤
        skill_mgr = SkillManager()
        runtime = self._cfg["provider_settings"]["computer_use_runtime"]
        skills = skill_mgr.list_skills(active_only=True, runtime=runtime)
        skills = [s for s in skills if s.name in allowed_skills]

        if not skills:
            return ""

        return build_skills_prompt(skills)

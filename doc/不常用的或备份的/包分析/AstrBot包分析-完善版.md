# AstrBot 框架逐文件详解（完善版）

> 本文档对 AstrBot 框架（`astrbot` 包，位于 `.venv/lib/site-packages/astrbot/`）下的**每一个 `.py` 文件**进行系统、完整的逐文件结构化分析。
>
> 分析维度统一为：**职责 / 核心类（含基类、关键属性、关键方法）/ 核心函数 / 关键常量 / 依赖**。
>
> 文档以"目录归属"为单位组织，覆盖 `astrbot` 包下全部子目录（`api/`、`builtin_stars/`、`cli/`、`core/` 及其全部子目录）。`core/` 是绝对核心，其下又细分为：顶层模块、`agent/`、`backup/`、`computer/`、`config/`、`cron/`、`db/`、`knowledge_base/`、`message/`、`pipeline/`、`platform/`、`provider/`、`skills/`、`star/`、`tools/`。
>
> 路径前缀（Windows 绝对路径）：`c:\Users\xwzwO\Documents\GitHub\astrbot_plugin_my_demo\.venv\lib\site-packages\astrbot\`

---

## 总目录

| 章节 | 模块 | 覆盖文件数 | 核心内容 |
|------|------|-----------|---------|
| 一 | `core/` 顶层 + `api/` + `builtin_stars/` + `cli/` | 61 | 全局初始化、日志、异常、事件总线、Agent 上下文、生命周期、配置管理器、对话管理、Persona、公共 API 门面、内置插件、命令行工具 |
| 二 | `core/db/` + `core/config/` + `core/message/` + `core/star/` + `core/knowledge_base/` | 68 | 数据持久化（SQLite+FAISS）、配置管理、消息组件、插件系统（Star/Context/PluginManager/过滤器）、知识库（解析/分块/混合检索） |
| 三 | `core/pipeline/` | 25 | 9 阶段洋葱模型管道、`PipelineScheduler`、各 Stage 实现、内容安全策略、process_stage 子包 |
| 四 | `core/platform/` | ~80 | 平台抽象基类、`PlatformManager`、18 个平台适配器（QQ/TG/Discord/Kook/Lark/微信等） |
| 五 | `core/provider/` | ~49 | Provider 抽象基类、`ProviderManager`、LLM/Embedding/Rerank/TTS/STT 适配器 |
| 六 | `core/agent/` 根 + `context/` | 17 | `Agent` dataclass、`ContextWrapper`、消息模型、`FunctionTool`/`ToolSet`、MCP 客户端、上下文压缩/截断 |
| 七 | `core/agent/runners/` | 11+ | `BaseAgentRunner`、`ToolLoopAgentRunner`（核心）、Coze/Dashscope/DeerFlow/Dify Runner |
| 八 | `core/tools/` + `core/computer/` + `core/backup/` + `core/skills/` + `core/cron/` | 42 | 内置工具注册中心、消息/计算机/Cron/知识库/Web 搜索工具、Booter 体系、OLayer、备份、技能同步、定时任务 |

> **说明**：以下各章节由对应子目录的逐文件分析组成，每节内部以子目录或文件为单位展开。各章节由独立的子文档整合而成，保留了原始的子文档标题以便于阅读。

---



---

## 章节一：core 顶层 + api + builtin_stars + cli

# AstrBot 框架逐文件详解

> 本文档对 AstrBot 框架以下目录的 `.py` 文件进行逐文件结构化分析：
> `core/` 顶层、`api/`（含子目录）、`builtin_stars/`（astrbot/ 与 builtin_commands/）、`cli/`（commands/ 与 utils/）。
>
> 路径前缀（Windows 绝对路径）：
> `c:\Users\xwzwO\Documents\GitHub\astrbot_plugin_my_demo\.venv\lib\site-packages\astrbot\`
>
> 文中相对路径均相对于此前缀。共覆盖 61 个 `.py` 文件（core 27 + api 10 + builtin_stars 12 + cli 12）。

---

## 一、`core/` 顶层 `.py` 文件（27 个）

### 1. `core/__init__.py`
- **职责**：core 包初始化模块，在导入时创建并缓存一批全局单例（配置、日志、数据库、偏好存储、文件令牌服务、pip 安装器、html 渲染器），并创建数据存储目录。
- **核心类**：无
- **核心函数**：无（模块级副作用初始化）
- **关键常量 / 全局对象**：
  - `DEMO_MODE`（读取环境变量 `DEMO_MODE`）
  - `astrbot_config: AstrBotConfig`
  - `t2i_base_url`、`html_renderer: HtmlRenderer`
  - `logger`（通过 `LogManager.GetLogger("astrbot")`）
  - `db_helper: SQLiteDatabase`
  - `sp: SharedPreferences`
  - `file_token_service: FileTokenService`
  - `pip_installer: PipInstaller`
- **依赖**：`os`；`astrbot.core.config.AstrBotConfig`、`astrbot.core.config.default.DB_PATH`、`astrbot.core.db.sqlite.SQLiteDatabase`、`astrbot.core.file_token_service.FileTokenService`、`astrbot.core.utils.pip_installer`、`astrbot.core.utils.requirements_utils`、`astrbot.core.utils.shared_preferences.SharedPreferences`、`astrbot.core.utils.t2i.renderer.HtmlRenderer`、`.log`、`astrbot.core.utils.astrbot_path`；透传重导出 `DependencyConflictError` / `PipInstaller` / `find_missing_requirements` 等。

### 2. `core/log.py`
- **职责**：日志系统，统一将标准 `logging` 输出转发到 `loguru`，支持 WebUI 队列分发、文件 sink、trace 日志与噪声 logger 抑制。
- **核心类**：
  - `_RecordEnricherFilter(logging.Filter)` — 为 LogRecord 注入 AstrBot 字段（plugin_tag/short_levelname/astrbot_version_tag/source_file/source_line/is_trace）。
  - `_QueueAnsiColorFilter(logging.Filter)` — 注入 ANSI 颜色前缀供 WebUI 控制台渲染。
  - `_LoguruInterceptHandler(logging.Handler)` — 将 logging 记录转发到 loguru。
  - `LogBroker` — 日志代理，缓存（`deque`）+ 订阅者队列分发。方法：`register()` / `unregister(q)` / `publish(log_entry)`；属性：`log_cache`、`subscribers`。
  - `LogQueueHandler(logging.Handler)` — 将日志发送到 `LogBroker`。方法：`emit()`。
  - `LogManager` — 类方法集合管理 loguru 控制台/文件/trace sink 与 root bridge。关键方法：`GetLogger(log_name)`、`set_queue_handler(logger, log_broker)`、`configure_logger(logger, config, override_level)`、`configure_trace_logger(config)`、`_setup_loguru()`、`_setup_root_bridge()`、`_add_file_sink(...)`、`_remove_sink(sink_id)`。属性：`_configured`、`_console_sink_id`、`_file_sink_id`、`_trace_sink_id`、`_NOISY_LOGGER_LEVELS`。
- **核心函数**：`_is_plugin_path(pathname)`、`_get_short_level_name(level_name)`、`_build_source_file(pathname)`、`_patch_record(record)`。
- **关键常量**：`CACHED_SIZE = 500`。
- **依赖**：`asyncio`、`logging`、`os`、`sys`、`time`、`asyncio.Queue`、`collections.deque`、`loguru`；`astrbot.core.config.default.VERSION`、`astrbot.core.utils.astrbot_path`。

### 3. `core/exceptions.py`
- **职责**：定义 AstrBot 全局异常体系。
- **核心类**：
  - `AstrBotError(Exception)` — 所有 AstrBot 错误的基类。
  - `ProviderNotFoundError(AstrBotError)` — 指定 provider 未找到。
  - `EmptyModelOutputError(AstrBotError)` — 模型响应无可用 assistant 输出。
  - `KnowledgeBaseUploadError(AstrBotError)` — 知识库上传失败；含 `stage` / `user_message` / `details` 属性。
- **核心函数**：无
- **关键常量**：无
- **依赖**：`__future__`

### 4. `core/sentinels.py`
- **职责**：定义哨兵值，用于区分"未传参"与 `None`。
- **核心类**：无
- **核心函数**：无
- **关键常量**：`NOT_GIVEN = object()`。
- **依赖**：无

### 5. `core/initial_loader.py`
- **职责**：AstrBot 启动器，初始化核心生命周期并启动仪表板服务器，并发运行核心任务与 WebUI。
- **核心类**：
  - `InitialLoader` — 启动器。方法：`start()`（初始化 lifecycle → 启动 dashboard → `asyncio.gather` 并发运行）；属性：`db`、`logger`、`log_broker`、`webui_dir`、`dashboard_server`。
- **核心函数**：无
- **关键常量**：无
- **依赖**：`asyncio`、`traceback`；`astrbot.core`（`LogBroker`、`logger`）、`astrbot.core.core_lifecycle.AstrBotCoreLifecycle`、`astrbot.core.db.BaseDatabase`、`astrbot.dashboard.server.AstrBotDashboard`。

### 6. `core/core_lifecycle.py`
- **职责**：核心生命周期管理，初始化并运行所有组件（Provider/Platform/Conversation/Plugin/Pipeline/EventBus/Persona/KB/Cron/SubAgent/Updator/UMOP 路由等）。
- **核心类**：
  - `AstrBotCoreLifecycle` — 关键方法：`initialize()`、`_load()`、`start()`、`stop()`、`restart()`、`load_platform()`、`load_pipeline_scheduler()`、`reload_pipeline_scheduler(conf_id)`、`_init_or_reload_subagent_orchestrator()`、`_warn_about_unset_default_chat_provider()`、`_task_wrapper(task)`。属性：`log_broker`、`astrbot_config`、`db`、`provider_manager`、`platform_manager`、`conversation_manager`、`persona_mgr`、`plugin_manager`、`event_bus`、`subagent_orchestrator`、`cron_manager`、`temp_dir_cleaner`、`dashboard_shutdown_event` 等。
- **核心函数**：无
- **关键常量**：无（`VERSION` 来自 `config.default`）
- **依赖**：`asyncio`、`os`、`threading`、`time`、`traceback`；大量 core 子模块：`astrbot_config_mgr`、`config.default`、`conversation_mgr`、`cron`、`db`、`knowledge_base.kb_mgr`、`persona_mgr`、`pipeline.scheduler`、`platform.manager`、`platform_message_history_mgr`、`provider.manager`、`star.context`、`star.star_handler`、`star.star_manager`、`subagent_orchestrator`、`umop_config_router`、`updator`、`utils.*`、`event_bus`。

### 7. `core/event_bus.py`
- **职责**：事件总线，从异步队列消费 `AstrMessageEvent`，按会话配置路由到对应 `PipelineScheduler` 执行。
- **核心类**：
  - `EventBus` — 方法：`dispatch()`（无限循环消费事件 + 创建 task）、`_on_task_done(task)`、`_print_event(event, conf_name)`；属性：`event_queue`、`pipeline_scheduler_mapping`、`astrbot_config_mgr`、`_pending_tasks`。
- **核心函数**：无
- **关键常量**：无
- **依赖**：`asyncio`、`asyncio.Queue`；`astrbot.core.logger`、`astrbot.core.astrbot_config_mgr.AstrBotConfigManager`、`astrbot.core.pipeline.scheduler.PipelineScheduler`、`.platform.AstrMessageEvent`。

### 8. `core/astr_agent_hooks.py`
- **职责**：主 Agent 运行钩子实现，将 agent 生命周期事件桥接到 Star 事件钩子。
- **核心类**：
  - `MainAgentHooks(BaseAgentRunHooks[AstrAgentContext])` — 方法：`on_agent_begin`、`on_agent_done`、`on_tool_start`、`on_tool_end`（分别触发 `OnAgentBeginEvent` / `OnLLMResponseEvent` / `OnAgentDoneEvent` / `OnUsingLLMToolEvent` / `OnLLMToolRespondEvent`）。
  - `EmptyAgentHooks(BaseAgentRunHooks[AstrAgentContext])` — 空实现。
- **核心函数**：无
- **关键常量**：`MAIN_AGENT_HOOKS = MainAgentHooks()`。
- **依赖**：`mcp.types.CallToolResult`；`astrbot.core.agent.hooks.BaseAgentRunHooks`、`astrbot.core.agent.run_context.ContextWrapper`、`astrbot.core.agent.tool.FunctionTool`、`astrbot.core.astr_agent_context.AstrAgentContext`、`astrbot.core.pipeline.context_utils.call_event_hook`、`astrbot.core.star.star_handler.EventType`。

### 9. `core/astr_agent_context.py`
- **职责**：定义 AstrBot 主 Agent 的上下文数据类（pydantic dataclass）。
- **核心类**：
  - `AstrAgentContext`（`@dataclass`，`arbitrary_types_allowed=True`）— 属性：`context: Context`、`event: AstrMessageEvent`、`extra: dict[str, str]`。
- **核心函数**：无
- **关键常量**：`AgentContextWrapper = ContextWrapper[AstrAgentContext]`。
- **依赖**：`pydantic`；`astrbot.core.agent.run_context.ContextWrapper`、`astrbot.core.platform.astr_message_event.AstrMessageEvent`、`astrbot.core.star.context.Context`。

### 10. `core/astr_main_agent.py`
- **职责**：构建并运行主对话 Agent，整合 provider 选择、知识库检索、文件抽取、persona/skills、图片/音频/视频/引用消息附件、web 搜索、沙箱/本地工具、Live TTS 等。
- **核心类**：
  - `MainAgentBuildConfig`（`@dataclass(slots=True)`）— 主 Agent 构建配置；属性含 `tool_call_timeout`、`provider_settings`、`streaming_response`、`provider_wake_prefix` 等。
  - `MainAgentBuildResult` — 构建结果（含 `agent_runner` 等）。
- **核心函数**：
  - `build_main_agent(*, event, plugin_context, config, provider=None, req=None, apply_reset=True)` — 构建主对话代理并 reset。
  - `_select_provider(event, plugin_context)` — 选择对话 provider。
  - `_get_session_conv(*, event, plugin_context)` — 获取会话当前对话。
  - `_apply_kb(...)` — 应用知识库检索。
  - `_apply_file_extract(...)` — 文件抽取。
  - `_apply_prompt_prefix(req, cfg)` — 注入 prompt 前缀。
  - `_get_workspace_path_for_umo(umo, plugin_context)` / `_apply_workspace_extra_prompt(...)` — 工作区路径与额外提示。
  - `_apply_local_env_tools(req, plugin_context)` / `_build_local_mode_prompt()` — 本地模式工具与提示。
  - `_filter_skills_for_current_config(...)` / `_ensure_persona_and_skills(...)` — skills 过滤与 persona/skills 装配。
  - `_request_img_caption(...)` / `_ensure_img_caption(...)` — 图片描述。
  - `_append_quoted_image_attachment(req, image_path)` / `_append_audio_attachment(req, audio_path)` / `_append_quoted_audio_attachment(req, audio_path)` / `_append_video_attachment(req, comp)` — 附件追加。
  - `_get_quoted_message_parser_settings(...)` / `_get_image_compress_args(...)` / `_compress_image_for_provider(...)` / `_is_generated_compressed_image_path(...)` / `_process_quote_message(...)` — 引用消息与图片压缩。
  - `_append_system_reminders(...)` / `_decorate_llm_request(...)` — 系统提醒与请求装饰。
  - `_plugin_tool_fix(event, req)` — 插件工具修复。
  - `_handle_webchat(...)` — webchat 处理。
  - `_apply_llm_safety_mode(config, req)` / `_apply_sandbox_tools(...)` / `_proactive_cron_job_tools(req, plugin_context)` / `_apply_web_search_tools(...)` / `_apply_web_search_citation_prompt(...)` — 安全模式/沙箱/主动 cron/web 搜索工具与引用提示。
  - `_get_compress_provider(...)` / `_get_fallback_chat_providers(...)` / `_provider_supports_modality(provider, modality)` / `_select_image_chat_provider(...)` — provider 选择与模态支持判断。
  - `_set_llm_error_message(event, message)` — 设置 LLM 错误消息到 event。
- **关键常量**：`LLM_ERROR_MESSAGE_EXTRA_KEY`、`WEEKDAY_NAMES`、`WEB_SEARCH_CITATION_TOOL_NAMES`、`WEB_SEARCH_CITATION_PROMPT`。
- **依赖**：`asyncio`、`copy`、`datetime`、`json`、`os`、`platform`、`zoneinfo`、`dataclasses`、`pathlib`；大量 `astrbot.core.agent.*`（handoff/mcp_client/message/tool/run_context）、`conversation_mgr.Conversation`、`db`、`message.components`、`persona_error_reply`、`platform.astr_message_event`、`provider.Provider`、`provider.entities.ProviderRequest`、`provider.register.llm_tools`、`skills.skill_manager`、`star.*`、`tools.*`（computer/cron/knowledge_base/message/web_search）、`utils.*`、`workspace`。

### 11. `core/astr_agent_run_util.py`
- **职责**：Agent 运行工具，提供 `run_agent` / `run_live_agent` 异步生成器，驱动 `ToolLoopAgentRunner` 步进、流式输出、工具状态消息与 Live TTS 分句流式。
- **核心类**：无（`AgentRunner = ToolLoopAgentRunner[AstrAgentContext]` 类型别名）
- **核心函数**：
  - `run_agent(agent_runner, max_step=30, show_tool_use=True, show_tool_call_result=False, stream_to_general=False, show_reasoning=False, buffer_intermediate_messages=False)` — 运行 Agent，`yield MessageChain`，处理 `tool_call` / `tool_call_result` / `llm_result` / `streaming_delta` / `err` / `aborted` / `agent_stats`。
  - `run_live_agent(agent_runner, tts_provider=None, ...)` — Live Mode 运行器，支持原生流式与模拟流式 TTS。
  - `_run_agent_feeder(...)` — Agent 文本分句喂入队列。
  - `_safe_tts_stream_wrapper(...)` — 原生流式 TTS 包装。
  - `_simulated_stream_tts(...)` — 模拟流式 TTS（按句生成）。
  - `_watch_agent_stop_signal(...)` — 监听停止信号。
  - 辅助：`_should_stop_agent`、`_truncate_tool_result`、`_extract_chain_json_data`、`_record_tool_call_name`、`_build_tool_call_status_message`、`_build_tool_result_status_message`、`_should_buffer_llm_result`、`_merge_buffered_llm_chains`。
- **关键常量**：`AgentRunner`。
- **依赖**：`asyncio`、`re`、`time`、`traceback`；`astrbot.core.logger`、`astrbot.core.agent.message.Message`、`astrbot.core.agent.runners.tool_loop_agent_runner.ToolLoopAgentRunner`、`astrbot.core.astr_agent_context.AstrAgentContext`、`astrbot.core.message.components`、`astrbot.core.message.message_event_result.*`、`astrbot.core.persona_error_reply`、`astrbot.core.provider.entities.LLMResponse`、`astrbot.core.provider.provider.TTSProvider`。

### 12. `core/astr_agent_tool_exec.py`
- **职责**：函数工具执行器，执行 HandoffTool / MCPTool / 本地工具 / 后台任务，处理图片 URL 收集、handoff 子代理调用、后台任务完成后唤醒主 Agent。
- **核心类**：
  - `FunctionToolExecutor(BaseFunctionToolExecutor[AstrAgentContext])` — 类方法集。方法：`execute(tool, run_context, **tool_args)`（按工具类型分发）、`_execute_handoff(...)`、`_execute_handoff_background(...)`、`_do_handoff_background(...)`、`_execute_background(...)`、`_wake_main_agent_for_background_result(...)`、`_execute_local(...)`、`_execute_mcp(...)`、`_build_handoff_toolset(...)`、`_get_runtime_computer_tools(runtime, tool_mgr, booter)`、`_collect_image_urls_from_args(...)`、`_collect_image_urls_from_message(...)`、`_collect_handoff_image_urls(...)`。
- **核心函数**：
  - `call_local_llm_tool(context, handler, method_name, *args, **kwargs)` — 执行本地 LLM 工具处理函数并处理返回（协程或异步生成器，`MessageEventResult` / `CommandResult` / `str` / `None`）。
- **关键常量**：无
- **依赖**：`asyncio`、`inspect`、`json`、`traceback`、`typing`、`uuid`、`mcp`；`astrbot.logger`、`astrbot.core.agent.*`（handoff/mcp_client/message/run_context/tool/tool_executor）、`astrbot.core.astr_agent_context`、`astrbot.core.astr_main_agent_resources`、`astrbot.core.cron.events.CronMessageEvent`、`astrbot.core.message.components.Image`、`astrbot.core.message.message_event_result.*`、`astrbot.core.platform.message_session.MessageSession`、`astrbot.core.provider.entites.ProviderRequest`、`astrbot.core.provider.register.llm_tools`、`astrbot.core.tools.*`、`astrbot.core.utils.*`。

### 13. `core/astr_main_agent_resources.py`
- **职责**：主 Agent 使用的系统提示词常量与恶意域名拦截列表。
- **核心类**：无
- **核心函数**：无
- **关键常量**：`LLM_SAFETY_MODE_SYSTEM_PROMPT`、`SANDBOX_MODE_PROMPT`、`TOOL_CALL_PROMPT`、`TOOL_CALL_PROMPT_SKILLS_LIKE_MODE`、`CHATUI_SPECIAL_DEFAULT_PERSONA_PROMPT`、`CHATUI_INLINE_GENUI_SYSTEM_PROMPT`、`LIVE_MODE_SYSTEM_PROMPT`、`PROACTIVE_AGENT_CRON_WOKE_SYSTEM_PROMPT`、`BACKGROUND_TASK_RESULT_WOKE_SYSTEM_PROMPT`、`BLOCKED`（base64 编码的恶意域名集合）、`decoded_blocked`。
- **依赖**：`base64`

### 14. `core/astrbot_config_mgr.py`
- **职责**：AstrBot 系统配置管理器（ACM），维护多个 `AstrBotConfig`（按 uuid），将会话（UMO）路由到对应配置文件，支持配置增删改查。
- **核心类**：
  - `ConfInfo(TypedDict)` — `id` / `name` / `path`。
  - `AstrBotConfigManager` — 方法：`get_conf(umo)`、`get_conf_info(umo)`、`get_conf_list()`、`create_conf(...)`、`delete_conf(conf_id)`、`update_conf_info(conf_id, name)`、`g(...)`（get 别名/快捷）、`_load_all_configs()`、`_load_conf_mapping(umo)`、`_save_conf_mapping(...)`、`_get_abconf_data()`。属性：`sp`、`ucr`、`confs`、`abconf_data`。属性 `default_conf` 为只读属性返回默认配置。
- **核心函数**：无
- **关键常量**：`DEFAULT_CONFIG_CONF_INFO`。
- **依赖**：`os`、`uuid`；`astrbot.core`（`AstrBotConfig`、`logger`）、`astrbot.core.config.astrbot_config.ASTRBOT_CONFIG_PATH`、`astrbot.core.config.default.DEFAULT_CONFIG`、`astrbot.core.platform.message_session.MessageSession`、`astrbot.core.umop_config_router.UmopConfigRouter`、`astrbot.core.utils.astrbot_path`、`astrbot.core.utils.shared_preferences.SharedPreferences`。

### 15. `core/conversation_mgr.py`
- **职责**：会话-对话管理器，维护会话（UMO）与对话（conversation）的映射、对话 CRUD、消息对追加、历史可读化，支持会话删除回调（级联清理）。
- **核心类**：
  - `ConversationManager` — 方法：`new_conversation(...)`、`switch_conversation(...)`、`delete_conversation(...)`、`delete_conversations_by_user_id(...)`、`get_curr_conversation_id(...)`、`get_conversation(...)`、`get_conversations(...)`、`get_filtered_conversations(...)`、`update_conversation(...)`、`update_conversation_title(...)`、`update_conversation_persona_id(...)`、`add_message_pair(...)`、`get_human_readable_context(...)`、`register_on_session_deleted(callback)`、`_trigger_session_deleted(...)`、`_convert_conv_from_v2_to_v1(...)`。属性：`session_conversations`、`db`、`save_interval=60`、`_on_session_deleted_callbacks`。
- **核心函数**：无
- **关键常量**：无
- **依赖**：`json`；`astrbot.core.sp`、`astrbot.core.agent.message`（`AssistantMessageSegment` / `UserMessageSegment`）、`astrbot.core.db.BaseDatabase`、`astrbot.core.db.po`（`Conversation` / `ConversationV2`）、`astrbot.core.utils.datetime_utils.to_utc_timestamp`。

### 16. `core/platform_message_history_mgr.py`
- **职责**：平台消息历史管理器，封装平台消息历史的增查改删（分页查询、按时间偏移删除）。
- **核心类**：
  - `PlatformMessageHistoryManager` — 方法：`insert(...)`、`get(...)`、`delete(...)`、`update(...)`、`delete_by_id(message_id)`；属性：`db`。
- **核心函数**：无
- **关键常量**：无
- **依赖**：`astrbot.core.db.BaseDatabase`、`astrbot.core.db.po.PlatformMessageHistory`。

### 17. `core/persona_mgr.py`
- **职责**：Persona（人格）管理器，管理 persona 与文件夹的 CRUD、v3 persona 数据解析、默认 persona 解析、会话级 persona 解析。
- **核心类**：
  - `PersonaManager` — 方法：`initialize()`、`get_persona(persona_id)`、`get_persona_v3_by_id(persona_id)`、`get_default_persona_v3(umo)`、`resolve_selected_persona(...)`、`delete_persona(...)`、`update_persona(...)`、`get_all_personas()`、`get_personas_by_folder(folder_id)`、`move_persona_to_folder(...)`、`create_folder(...)` / `get_folder(folder_id)` / `get_folders(parent_id)` / `get_all_folders()` / `update_folder(...)` / `delete_folder(folder_id)` / `batch_update_sort_order(items)` / `get_folder_tree()`、`create_persona(...)`、`get_v3_persona_data()`。属性：`db`、`acm`、`default_persona`、`personas`、`selected_default_persona`、`personas_v3`、`selected_default_persona_v3`、`persona_v3_config`。
- **核心函数**：无
- **关键常量**：`DEFAULT_PERSONALITY`。
- **依赖**：`astrbot.logger`、`astrbot.api.sp`、`astrbot.core.astrbot_config_mgr.AstrBotConfigManager`、`astrbot.core.db.BaseDatabase`、`astrbot.core.db.po`（`Persona` / `PersonaFolder` / `Personality`）、`astrbot.core.platform.message_session.MessageSession`、`astrbot.core.sentinels.NOT_GIVEN`。

### 18. `core/persona_error_reply.py`
- **职责**：persona 自定义错误回复文本的归一化、存取与解析（从 persona/event 提取，写入 event extras）。
- **核心类**：无
- **核心函数**：
  - `normalize_persona_custom_error_message(value)` — 归一化为非空字符串或 None。
  - `extract_persona_custom_error_message_from_persona(persona)` — 从 persona mapping 提取。
  - `extract_persona_custom_error_message_from_event(event)` — 从 event extras 提取。
  - `set_persona_custom_error_message_on_event(event, message)` — 写入 event extras。
  - `resolve_persona_custom_error_message(*, event, persona_manager, provider_settings, conversation_persona_id)` — 解析当前 persona 错误回复。
  - `resolve_event_conversation_persona_id(event, conversation_manager)` — 解析当前对话 persona_id。
- **关键常量**：`PERSONA_CUSTOM_ERROR_MESSAGE_EXTRA_KEY = "persona_custom_error_message"`。
- **依赖**：`collections.abc.Mapping`、`typing`。

### 19. `core/file_token_service.py`
- **职责**：基于令牌的文件下载服务，支持注册文件→生成单次令牌、令牌校验、超时懒清除。
- **核心类**：
  - `FileTokenService` — 方法：`register_file(file_path, timeout=None)`、`handle_file(file_token)`、`check_token_expired(file_token)`、`_cleanup_expired_tokens()`；属性：`lock`、`staged_files`（token→(path, expire)）、`default_timeout=300`。
- **核心函数**：无
- **关键常量**：无
- **依赖**：`asyncio`、`os`、`time`、`uuid`；动态导入 `astrbot.core.utils.media_utils`（`file_uri_to_path` / `is_file_uri`）。

### 20. `core/desktop_runtime.py`
- **职责**：检测是否运行在 AstrBot Desktop 托管环境下。
- **核心类**：无
- **核心函数**：`is_desktop_managed_backend()` — 检查环境变量 `ASTRBOT_DESKTOP_MANAGED == "1"`。
- **关键常量**：`DESKTOP_MANAGED_RESTART_MESSAGE`。
- **依赖**：`os`

### 21. `core/updator.py`
- **职责**：AstrBot 更新器，继承 `RepoZipUpdator`，处理版本检查、更新包下载/解压、子进程终止、冻结（PyInstaller）环境重启。
- **核心类**：
  - `AstrBotUpdator(RepoZipUpdator)` — 方法：`check_update(...)`、`get_releases()`、`update(...)`、`download_update_package(...)`、`apply_update_package(zip_path)`、`terminate_child_processes()`、`_build_core_package_url(version)`、`_build_frozen_reboot_args()`、`_reset_pyinstaller_environment()`、`_build_reboot_argv(executable)`、`_exec_reboot(executable, argv)`、`_reboot(delay=3)`、`_resolve_webui_dir_arg(argv)`、`_collect_flag_values(argv, flag)`、`_is_option_arg(arg)`。属性：`MAIN_PATH`、`ASTRBOT_RELEASE_API`、`CORE_PACKAGE_BASE_URL`。
- **核心函数**：无
- **关键常量**：无
- **依赖**：`os`、`subprocess`、`sys`、`time`、`zipfile`、`pathlib`、`psutil`；`astrbot.core.logger`、`astrbot.core.config.default.VERSION`、`astrbot.core.desktop_runtime`、`astrbot.core.utils.astrbot_path`、`astrbot.core.utils.io`、`.zip_updator`（`ReleaseInfo` / `RepoZipUpdator`）。

### 22. `core/zip_updator.py`
- **职责**：基于 zip 的仓库更新器基类，提供 GitHub release 解析、文件下载（带进度回调）、zip 解压、版本比较、URL 解析。
- **核心类**：
  - `ReleaseInfo` — 属性：`version`、`published_at`、`body`；`__str__`。
  - `RepoZipUpdator` — 方法：`fetch_github_default_branch(author, repo)`、`resolve_github_source_branch(...)`、`_download_file(...)`、`fetch_release_info(url, latest)`、`github_api_release_parser(releases)`、`check_update(...)`、`download_from_repo_url(...)`、`parse_github_url(url)`、`unzip_file(zip_path, target_dir)`、`_resolve_archive_root_dir(entries)`、`_finalize_extracted_archive(...)`、`format_name(name)`、`compare_version(v1, v2)`、`update()`（NoReturn）、`unzip()`（NoReturn）、`_create_httpx_client(timeout)`。属性：`repo_mirror`、`rm_on_error`、`httpx_verify`。
- **核心函数**：无
- **关键常量**：无
- **依赖**：`inspect`、`os`、`re`、`shutil`、`time`、`zipfile`、`pathlib`、`typing.NoReturn`、`certifi`、`httpx`；`astrbot.core.logger`、`astrbot.core.utils.io`（`ensure_dir` / `on_error`）、`astrbot.core.utils.version_comparator.VersionComparator`。

### 23. `core/workspace.py`
- **职责**：工作区路径解析，支持 session / project / custom 三种工作区类型，解析 webchat UMO 到项目工作区根。
- **核心类**：无
- **核心函数**：
  - `normalize_umo_for_workspace(umo)` — UMO 转文件系统安全名。
  - `normalize_project_workspace_type(value)` — 归一化工作区类型。
  - `normalize_workspace_path(path)` — 归一化自定义路径。
  - `default_workspace_root(umo)` — 默认 session 工作区根。
  - `project_workspace_root(project_id)` — 项目工作区根。
  - `workspace_path_to_root(path)` — 自定义路径解析（防越界，相对路径必须留在 workspaces 根下）。
  - `resolve_project_workspace_root(project, *, fallback_umo)` — 从项目记录解析工作区根。
  - `parse_webchat_umo(umo)` — 解析 webchat UMO 为 `(creator, session_id)`。
  - `resolve_workspace_root_for_umo(umo, db=None)` — 解析 UMO 工作区根。
- **关键常量**：`WORKSPACE_TYPE_SESSION`、`WORKSPACE_TYPE_PROJECT`、`WORKSPACE_TYPE_CUSTOM`、`WORKSPACE_TYPES`。
- **依赖**：`re`、`pathlib`；`astrbot.core.db.BaseDatabase`、`astrbot.core.platform.message_session.MessageSession`、`astrbot.core.utils.astrbot_path.get_astrbot_workspaces_path`。

### 24. `core/umop_config_router.py`
- **职责**：UMOP 配置路由器，将 UMO（`platform:message_type:session_id`）模式匹配到配置文件 ID，支持通配符与 `fnmatch`。
- **核心类**：
  - `UmopConfigRouter` — 方法：`initialize()`、`get_conf_id_for_umop(umo)`、`update_routing_data(new_routing)`、`update_route(umo, conf_id)`、`delete_route(umo)`、`_load_routing_table()`、`_split_umo(umo)`、`_is_umo_match(p1, p2)`。属性：`umop_to_conf_id`、`sp`。
- **核心函数**：无
- **关键常量**：无
- **依赖**：`fnmatch`；`astrbot.core.utils.shared_preferences.SharedPreferences`。

### 25. `core/umo_alias.py`
- **职责**：UMO 别名工具函数，归一化 / 解析 UMO、生成自动名称、序列化别名。
- **核心类**：无
- **核心函数**：
  - `normalize_umo_name(name)` — 归一化并截断至 255。
  - `parse_umo(umo)` — 拆分为 `platform` / `message_type` / `session_id`。
  - `get_event_auto_name(event)` — 从事件生成自动名称（群名优先，其次发送者名/ID）。
  - `get_umo_display_name(*, umo, auto_name, user_alias)` — 显示名（用户别名 > 自动名 > umo）。
  - `serialize_umo_alias(alias, umo)` — 序列化为 dict（含 `auto_name` / `user_alias` / `display_name` / `creator_sender_id`）。
  - `build_umo_alias_map(aliases)` — 构建 `umo → UmoAlias` 映射。
- **关键常量**：`MAX_UMO_NAME_LENGTH = 255`。
- **依赖**：`typing`；`astrbot.core.db.po.UmoAlias`。

### 26. `core/subagent_orchestrator.py`
- **职责**：SubAgent 编排器，从配置加载子代理定义并注册 `HandoffTool`（自身不执行，执行由 `FunctionToolExecutor` 完成）。
- **核心类**：
  - `SubAgentOrchestrator` — 方法：`reload_from_config(cfg)`（解析 `agents` 列表，按 persona/工具/system_prompt 构建 `Agent` 与 `HandoffTool`，可选 per-subagent provider 覆盖）。属性：`_tool_mgr`、`_persona_mgr`、`handoffs`。
- **核心函数**：无
- **关键常量**：无
- **依赖**：`copy`、`typing`；`astrbot.logger`、`astrbot.core.agent.agent.Agent`、`astrbot.core.agent.handoff.HandoffTool`、`astrbot.core.provider.func_tool_manager.FunctionToolManager`；`astrbot.core.persona_mgr.PersonaManager`（TYPE_CHECKING）。

### 27. `core/sentinels.py`
- （见第 4 项，避免重复，哨兵值 `NOT_GIVEN`。）

> 注：第 27 项与第 4 项为同一文件 `core/sentinels.py`，此处仅作占位以匹配 27 个文件的编号；实际 `core/` 顶层共 27 个 `.py` 文件已全部覆盖于第 1–26 项（`__init__`、`log`、`exceptions`、`sentinels`、`initial_loader`、`core_lifecycle`、`event_bus`、`astr_agent_hooks`、`astr_agent_context`、`astr_main_agent`、`astr_agent_run_util`、`astr_agent_tool_exec`、`astr_main_agent_resources`、`astrbot_config_mgr`、`conversation_mgr`、`platform_message_history_mgr`、`persona_mgr`、`persona_error_reply`、`file_token_service`、`desktop_runtime`、`updator`、`zip_updator`、`workspace`、`umop_config_router`、`umo_alias`、`subagent_orchestrator`，共 26 个唯一文件）。

---

## 二、`api/` 目录（10 个，含子目录）

### 1. `api/__init__.py`
- **职责**：api 包入口，导出插件开发常用对象（`logger` / `sp` / `html_renderer` / `AstrBotConfig` / `FunctionTool` / `ToolSet` / `BaseFunctionToolExecutor` / `agent` / `llm_tool`）。
- **核心类**：无
- **核心函数**：无
- **关键常量**：`__all__`。
- **依赖**：`astrbot`（`logger`）、`astrbot.core`（`html_renderer`、`sp`）、`astrbot.core.agent.tool`（`FunctionTool` / `ToolSet`）、`astrbot.core.agent.tool_executor.BaseFunctionToolExecutor`、`astrbot.core.config.astrbot_config.AstrBotConfig`、`astrbot.core.star.register`（`register_agent as agent`、`register_llm_tool as llm_tool`）。

### 2. `api/all.py`
- **职责**：汇总导出插件开发常用 API（事件结果类、Star/Context、注册装饰器、provider、platform、消息组件、config 等），即 `from astrbot.api.all import *`。
- **核心类**：无
- **核心函数**：无
- **关键常量**：无（`ruff: noqa`）
- **依赖**：`astrbot.core.config.astrbot_config.AstrBotConfig`、`astrbot.logger`、`astrbot.core.html_renderer`、`astrbot.core.star.register.*`、`astrbot.core.star.filter.*`、`astrbot.core.star`（`Context` / `Star`）、`astrbot.core.star.config`、`astrbot.core.provider`（`Provider` / `ProviderMetaData`）、`astrbot.core.db.po.Personality`、`astrbot.core.platform.*`、`astrbot.core.platform.register.register_platform_adapter`、`.message_components`。

### 3. `api/web.py`
- **职责**：插件 Web API 处理器的请求 / 响应封装，提供类 Flask 的 `request` 代理与 JSON / file / stream 响应构建。
- **核心类**：
  - `PluginMultiDict(Generic[ValueT])` — 保留重复键的多值字典。方法：`get(key, default, type)`、`getlist(key)`、`keys()`、`values()`、`items()`、`__contains__`、`__getitem__`、`__bool__`。
  - `PluginUploadFile` — 上传文件包装（基于 starlette `UploadFile`）。方法：`save(destination)`、`read(size)`、`write(data)`、`seek(offset)`、`close()`；属性：`filename`、`content_type`、`headers`、`content_length`。
  - `PluginRequest` — 请求对象。方法：`body()`、`json(default)`、`form()`、`files()`；属性：`method`、`path`、`headers`、`cookies`、`content_type`、`client_host`、`path_params`、`plugin_name`、`username`、`query`。
  - `PluginRequestProxy` — 基于 `contextvars` 的当前请求代理（属性与方法转发现 `PluginRequest`）。
- **核心函数**：
  - `bind_request_context(request_)` — `contextmanager`，绑定请求到当前异步上下文。
  - `json_response(data, *, status_code=200, headers=None)` — 构建 JSON 响应。
  - `error_response(message, *, status_code=400, data=None, headers=None)` — 构建标准错误响应（`{status, message, data}`）。
  - `file_response(path, *, filename=None, content_type=None, headers=None)` — 构建文件下载响应。
  - `stream_response(content, *, content_type="text/event-stream", status_code=200, headers=None)` — 构建流式响应。
- **关键常量**：`request`（模块级 `PluginRequestProxy` 实例）；`ValueT` / `DefaultT` / `ConvertedT` TypeVar。
- **依赖**：`contextvars`、`collections.abc`、`contextlib.contextmanager`、`pathlib`、`typing`；`fastapi.encoders.jsonable_encoder`、`fastapi.responses`（`FileResponse` / `JSONResponse`）、`starlette.datastructures`（`Headers` / `UploadFile`）、`starlette.responses.StreamingResponse`。

### 4. `api/message_components.py`
- **职责**：直接转发 `astrbot.core.message.components` 的消息组件（`Plain` / `Image` / `At` / `Reply` 等）。
- **核心类**：无（透传）
- **核心函数**：无
- **关键常量**：无
- **依赖**：`astrbot.core.message.components`

### 5. `api/event/__init__.py`
- **职责**：导出事件相关类（`AstrMessageEvent` / `MessageEventResult` / `MessageChain` / `CommandResult` / `EventResultType` / `ResultContentType`）。
- **核心类**：无
- **核心函数**：无
- **关键常量**：`__all__`。
- **依赖**：`astrbot.core.message.message_event_result`、`astrbot.core.platform.AstrMessageEvent`。

### 6. `api/event/filter/__init__.py`
- **职责**：导出过滤器与事件钩子注册装饰器。
- **核心类**：无（透传 `CustomFilter` / `EventMessageType(Filter)` / `EventMessageTypeFilter` / `PermissionType` / `PermissionTypeFilter` / `PlatformAdapterType` / `PlatformAdapterTypeFilter`）
- **核心函数**：无（透传装饰器：`command` / `command_group` / `regex` / `event_message_type` / `platform_adapter_type` / `permission_type` / `custom_filter` / `llm_tool` / `on_llm_request` / `on_llm_response` / `on_agent_begin` / `on_agent_done` / `on_using_llm_tool` / `on_llm_tool_respond` / `after_message_sent` / `on_astrbot_loaded` / `on_plugin_loaded` / `on_plugin_unloaded` / `on_platform_loaded` / `on_plugin_error` / `on_decorating_result` / `on_waiting_llm_request`）
- **关键常量**：`__all__`。
- **依赖**：`astrbot.core.star.filter.custom_filter.CustomFilter`、`astrbot.core.star.filter.event_message_type`、`astrbot.core.star.filter.permission`、`astrbot.core.star.filter.platform_adapter_type`、`astrbot.core.star.register.*`。

### 7. `api/platform/__init__.py`
- **职责**：导出平台相关类（`AstrBotMessage` / `AstrMessageEvent` / `Group` / `MessageMember` / `MessageType` / `Platform` / `PlatformMetadata` / `register_platform_adapter`）+ 消息组件。
- **核心类**：无（透传）
- **核心函数**：无
- **关键常量**：`__all__`。
- **依赖**：`astrbot.core.message.components`、`astrbot.core.platform`、`astrbot.core.platform.register.register_platform_adapter`。

### 8. `api/provider/__init__.py`
- **职责**：导出 provider 相关类（`Provider` / `STTProvider` / `LLMResponse` / `ProviderRequest` / `ProviderMetaData` / `ProviderType` / `Personality`）。
- **核心类**：无（透传）
- **核心函数**：无
- **关键常量**：`__all__`。
- **依赖**：`astrbot.core.db.po.Personality`、`astrbot.core.provider`（`Provider` / `STTProvider`）、`astrbot.core.provider.entities`（`LLMResponse` / `ProviderMetaData` / `ProviderRequest` / `ProviderType`）。

### 9. `api/star/__init__.py`
- **职责**：导出 Star 插件核心（`Context` / `Star` / `StarTools` / `register` / `config.*`）。
- **核心类**：无（透传）
- **核心函数**：无
- **关键常量**：`__all__`。
- **依赖**：`astrbot.core.star`（`Context` / `Star` / `StarTools`）、`astrbot.core.star.config`、`astrbot.core.star.register.register_star as register`。

### 10. `api/util/__init__.py`
- **职责**：导出会话等待器工具（`SessionController` / `SessionWaiter` / `session_waiter`）。
- **核心类**：无（透传）
- **核心函数**：无
- **关键常量**：`__all__`。
- **依赖**：`astrbot.core.utils.session_waiter`（`SessionController` / `SessionWaiter` / `session_waiter`）。

---

## 三、`builtin_stars/` 目录（12 个）

### 1. `builtin_stars/astrbot/main.py`
- **职责**：内置 Star 插件 `Main`，处理会话控制代理、空 @ 等待、群聊上下文感知、LLM 请求装饰、消息发送后钩子。
- **核心类**：
  - `Main(star.Star)` — 方法：`handle_session_control_agent(event)`（最高优先级 `maxsize`，触发 session waiter）、`handle_empty_mention(event)`（仅一个 @ 或唤醒前缀时等待用户下一条内容）、`on_message(event)`（群消息上下文记录 + 主动回复）、`decorate_llm_req(event, req)`（`on_llm_request` 注入群上下文）、`after_message_sent(event)`、`group_context_enabled(event)`。属性：`context`、`group_chat_context`。
- **核心函数**：`_iter_message_components(event)`。
- **关键常量**：无（`maxsize` 用于优先级）。
- **依赖**：`astrbot.api.message_components`、`astrbot.api.star`、`astrbot.api.event`（`AstrMessageEvent` / `filter`）、`astrbot.api.provider.ProviderRequest`、`astrbot.core.logger`、`astrbot.core.utils.session_waiter`（`FILTERS` / `USER_SESSIONS` / `SessionController` / `SessionWaiter` / `session_waiter`）、`.group_chat_context.GroupChatContext`。

### 2. `builtin_stars/astrbot/group_chat_context.py`
- **职责**：群聊上下文感知，记录群消息历史并在 LLM 请求时注入，支持图片描述、主动回复（概率）、记录裁剪。
- **核心类**：
  - `GroupChatContext` — 方法：`cfg(event)`、`get_image_caption(...)`、`need_active_reply(event)`、`remove_session(event)`、`handle_message(event)`、`on_req_llm(event, req)`、`_format_message(event, cfg)`、`_get_lock(umo)`。属性：`acm`、`context`、`_locks`、`raw_records`、`_record_ids`。
- **核心函数**：`_describe_chain(chain)`、`_truncate_reply_text(text)`、`_positive_int(value, fallback)`、`_trim_left(records, max_records, record_ids)`、`_format_group_history_block(records)`。
- **关键常量**：`GROUP_HISTORY_HEADER`、`GROUP_HISTORY_FOOTER`、`DEFAULT_GROUP_MESSAGE_MAX_CNT = 300`、`_MAX_REPLY_TEXT_LENGTH = 200`。
- **依赖**：`asyncio`、`datetime`、`random`、`uuid`、`collections`（`defaultdict` / `deque`）；`astrbot.logger`、`astrbot.api.star`、`astrbot.api.event.AstrMessageEvent`、`astrbot.api.message_components.*`、`astrbot.api.platform.MessageType`、`astrbot.api.provider`（`Provider` / `ProviderRequest`）、`astrbot.core.agent.message.TextPart`、`astrbot.core.astrbot_config_mgr.AstrBotConfigManager`。

### 3. `builtin_stars/builtin_commands/main.py`
- **职责**：内置指令 Star 插件 `Main`，聚合各命令处理器并注册 `help` / `sid` / `name` / `reset` / `stop` / `new` / `stats` / `provider` / `dashboard_update` / `set` / `unset` 指令。
- **核心类**：
  - `Main(star.Star)` — 方法：`help`、`sid`、`name`、`reset`、`stop`、`new_conv`、`stats`、`provider`、`update_dashboard`、`set_variable`、`unset_variable`。属性：`context`、`admin_c`、`conversation_c`、`help_c`、`name_c`、`provider_c`、`setunset_c`、`sid_c`。
- **核心函数**：无
- **关键常量**：无
- **依赖**：`astrbot.api.star`、`astrbot.api.event`（`AstrMessageEvent` / `filter`）、`astrbot.core.star.filter.command.GreedyStr`、`.commands.*`。

### 4. `builtin_stars/builtin_commands/commands/__init__.py`
- **职责**：commands 子包入口，导出各命令处理器类。
- **核心类**：无（透传 `AdminCommands` / `ConversationCommands` / `HelpCommand` / `NameCommand` / `ProviderCommands` / `SetUnsetCommands` / `SIDCommand`）
- **核心函数**：无
- **关键常量**：`__all__`。
- **依赖**：`.admin`、`.conversation`、`.help`、`.name`、`.provider`、`.setunset`、`.sid`。

### 5. `builtin_stars/builtin_commands/commands/admin.py`
- **职责**：管理员命令处理器（更新 WebUI 面板）。
- **核心类**：
  - `AdminCommands` — 方法：`update_dashboard(event)`；属性：`context`。
- **核心函数**：无
- **关键常量**：无
- **依赖**：`astrbot.api.star`、`astrbot.api.event`（`AstrMessageEvent` / `MessageChain`）、`astrbot.core.config.default.VERSION`、`astrbot.core.utils.io.download_dashboard`。

### 6. `builtin_stars/builtin_commands/commands/conversation.py`
- **职责**：对话命令处理器（`reset` / `stop` / `new` / `stats`），含第三方 agent runner（dify / coze / dashscope / deerflow）状态清理。
- **核心类**：
  - `ConversationCommands` — 方法：`reset(message)`、`stop(message)`、`new_conv(message)`、`stats(message)`、`_get_current_persona_id(session_id)`；属性：`context`。
- **核心函数**：
  - `_cleanup_deerflow_thread_if_present(context, umo)` — 清理 DeerFlow 远程线程。
  - `_clear_third_party_agent_runner_state(context, umo, agent_runner_type)` — 清理第三方 runner 状态。
- **关键常量**：`THIRD_PARTY_AGENT_RUNNER_KEY`、`THIRD_PARTY_AGENT_RUNNER_STR`。
- **依赖**：`sqlalchemy`（`case` / `func` / `select`）、`sqlmodel.col`；`astrbot.api`（`sp` / `star`）、`astrbot.api.event`（`AstrMessageEvent` / `MessageEventResult`）、`astrbot.core.logger`、`astrbot.core.agent.runners.deerflow.*`、`astrbot.core.db.po.ProviderStat`、`astrbot.core.utils.active_event_registry.active_event_registry`、`.utils.rst_scene.RstScene`。

### 7. `builtin_stars/builtin_commands/commands/help.py`
- **职责**：`help` 命令处理器，查询公告、构建内置指令清单、显示版本信息。
- **核心类**：
  - `HelpCommand` — 方法：`help(event)`、`_query_astrbot_notice()`、`_build_reserved_command_lines()`；属性：`context`。
- **核心函数**：无
- **关键常量**：无
- **依赖**：`aiohttp`；`astrbot.api.star`、`astrbot.api.event`（`AstrMessageEvent` / `MessageEventResult`）、`astrbot.core.config.default.VERSION`、`astrbot.core.star.command_management`、`astrbot.core.utils.io.get_dashboard_version`。

### 8. `builtin_stars/builtin_commands/commands/name.py`
- **职责**：`name` 命令处理器，设置 / 查询当前 UMO 显示别名。
- **核心类**：
  - `NameCommand` — 方法：`name(event, alias)`；属性：`context`。
- **核心函数**：无
- **关键常量**：无
- **依赖**：`astrbot.api.star`、`astrbot.api.event`（`AstrMessageEvent` / `MessageEventResult`）、`astrbot.core.umo_alias`（`get_event_auto_name` / `normalize_umo_name`）。

### 9. `builtin_stars/builtin_commands/commands/provider.py`
- **职责**：`provider` 命令处理器，查看 / 切换 LLM Provider，支持可达性测试与展示。
- **核心类**：
  - `ProviderCommands` — 方法：`provider(event, idx, idx2)`、`_test_provider_capability(provider)`、`_build_provider_display_data(providers, provider_type, reachability_check_enabled)`、`_log_reachability_failure(...)`；属性：`context`。
- **核心函数**：无
- **关键常量**：无
- **依赖**：`asyncio`；`astrbot.logger`、`astrbot.api.star`、`astrbot.api.event`（`AstrMessageEvent` / `MessageEventResult`）、`astrbot.core.provider.entities.ProviderType`、`astrbot.core.utils.error_redaction.safe_error`。

### 10. `builtin_stars/builtin_commands/commands/setunset.py`
- **职责**：`set` / `unset` 命令处理器，设置 / 移除会话变量。
- **核心类**：
  - `SetUnsetCommands` — 方法：`set_variable(event, key, value)`、`unset_variable(event, key)`；属性：`context`。
- **核心函数**：无
- **关键常量**：无
- **依赖**：`astrbot.api`（`sp` / `star`）、`astrbot.api.event`（`AstrMessageEvent` / `MessageEventResult`）。

### 11. `builtin_stars/builtin_commands/commands/sid.py`
- **职责**：`sid` 命令处理器，输出会话 ID（UMO / UID / 平台 / 消息类型 / 会话 ID）信息。
- **核心类**：
  - `SIDCommand` — 方法：`sid(event)`；属性：`context`。
- **核心函数**：无
- **关键常量**：无
- **依赖**：`astrbot.api.star`、`astrbot.api.event`（`AstrMessageEvent` / `MessageEventResult`）。

### 12. `builtin_stars/builtin_commands/commands/utils/rst_scene.py`
- **职责**：reset 命令场景枚举（群聊隔离开 / 关、私聊）。
- **核心类**：
  - `RstScene(Enum)` — 成员：`GROUP_UNIQUE_ON`、`GROUP_UNIQUE_OFF`、`PRIVATE`；属性：`key`、`name`；类方法：`from_index(index)`、`get_scene(is_group, is_unique_session)`。
- **核心函数**：无
- **关键常量**：无
- **依赖**：`enum`

---

## 四、`cli/` 目录（12 个）

### 1. `cli/__init__.py`
- **职责**：cli 包入口，导出 `__version__`。
- **核心类**：无
- **核心函数**：无
- **关键常量**：`__version__`、`__all__`。
- **依赖**：`astrbot.__version__`。

### 2. `cli/__main__.py`
- **职责**：CLI 入口，定义 click group `cli` 与 `help` 命令，注册 `init` / `run` / `help` / `plug` / `conf` / `password` 子命令。
- **核心类**：无
- **核心函数**：
  - `cli()`（`@click.group()`）— 顶层命令组，打印 logo 与版本。
  - `help(command_name)`（`@click.command()`）— 显示通用或指定命令帮助。
- **关键常量**：`logo_tmpl`。
- **依赖**：`sys`、`click`；`.`（`__version__`）、`.commands`（`conf` / `init` / `password` / `plug` / `run`）。

### 3. `cli/commands/__init__.py`
- **职责**：commands 子包入口，导出 `conf` / `init` / `password` / `plug` / `run` click 命令。
- **核心类**：无
- **核心函数**：无
- **关键常量**：`__all__`。
- **依赖**：`.cmd_conf.conf`、`.cmd_init.init`、`.cmd_password.password`、`.cmd_plug.plug`、`.cmd_run.run`。

### 4. `cli/commands/cmd_run.py`
- **职责**：`astrbot run` 命令，加锁运行 AstrBot（`InitialLoader.start`），支持 `--reload` / `--port` / `--reset-password`。
- **核心类**：无
- **核心函数**：
  - `run(reload, port, reset_password)`（`@click.command()`）— 运行 AstrBot（设置环境变量、文件锁、`asyncio.run`）。
  - `run_astrbot(astrbot_root)`（async）— 实际启动逻辑（检查 dashboard、构建 `LogBroker` / `InitialLoader`）。
- **关键常量**：`DASHBOARD_RESET_PASSWORD_ENV`。
- **依赖**：`asyncio`、`os`、`sys`、`traceback`、`pathlib`、`click`、`filelock`（`FileLock` / `Timeout`）；`..utils`（`check_astrbot_root` / `check_dashboard` / `get_astrbot_root`）；动态 `astrbot.core`（`LogBroker` / `LogManager` / `db_helper` / `logger`）、`astrbot.core.initial_loader.InitialLoader`。

### 5. `cli/commands/cmd_init.py`
- **职责**：`astrbot init` 命令，初始化目录结构与配置，检查 / 下载 dashboard。
- **核心类**：无
- **核心函数**：
  - `init()`（`@click.command()`）— 初始化 AstrBot（文件锁 + `asyncio.run`）。
  - `initialize_astrbot(astrbot_root)`（async）— 创建 `.astrbot` / `data` / `data/config` / `data/plugins` / `data/temp` 目录。
  - `check_dashboard(astrbot_root)`（async）— 检查 dashboard。
  - `_initialize_config_from_env(astrbot_root)` — 从环境变量初始化 `cmd_config.json`。
- **关键常量**：`DASHBOARD_INITIAL_PASSWORD_ENV`。
- **依赖**：`asyncio`、`os`、`pathlib`、`click`、`filelock`；`..utils`（动态 `get_astrbot_root`）；动态 `astrbot.core.config.astrbot_config.AstrBotConfig`。

### 6. `cli/commands/cmd_password.py`
- **职责**：`astrbot password` 命令，交互式修改 dashboard 密码（可选用户名）。
- **核心类**：无
- **核心函数**：`password(username)`（`@click.command(name="password")`）。
- **关键常量**：无
- **依赖**：`click`；`.cmd_conf`（`_load_config` / `_save_config` / `_set_dashboard_password` / `_set_nested_item` / `_validate_dashboard_password` / `_validate_dashboard_username`）。

### 7. `cli/commands/cmd_conf.py`
- **职责**：`astrbot conf` 命令组（`set` / `get`），配置项校验与读写 `cmd_config.json`。
- **核心类**：无
- **核心函数**：
  - `conf()`（`@click.group(name="conf")`）— 配置管理命令组。
  - `set_config(key, value)`（`@conf.command(name="set")`）— 设置配置项。
  - `get_config(key)`（`@conf.command(name="get")`）— 获取配置项。
  - `_load_config()` / `_save_config(config)` — 加载 / 保存配置文件。
  - `_set_nested_item(obj, path, value)` / `_get_nested_item(obj, path)` — 嵌套字典读写。
  - `_set_dashboard_password(config, raw_password)` — 设置 dashboard 密码哈希并清除迁移标志。
  - 校验函数：`_validate_log_level`、`_validate_dashboard_port`、`_validate_dashboard_username`、`_validate_dashboard_password`、`_validate_timezone`、`_validate_callback_api_base`。
- **关键常量**：`CONFIG_VALIDATORS`（配置键 → 校验函数映射）。
- **依赖**：`json`、`zoneinfo`、`collections.abc.Callable`、`typing`、`click`；`..utils`（`check_astrbot_root` / `get_astrbot_root`）；动态 `astrbot.core.config.default.DEFAULT_CONFIG`、`astrbot.core.utils.auth_password`。

### 8. `cli/commands/cmd_plug.py`
- **职责**：`astrbot plug` 命令组（`new` / `list` / `install` / `remove` / `update` / `search`），插件管理。
- **核心类**：无
- **核心函数**：
  - `plug()`（`@click.group()`）— 插件管理命令组。
  - `new(name)`（`@plug.command()`）— 新建插件（从 helloworld 模板下载并改写 metadata）。
  - `list(all)`（`@plug.command()`）— 列出插件。
  - `install(name, local_path, proxy)`（`@plug.command()`）— 安装插件。
  - `remove(name)`（`@plug.command()`）— 移除插件。
  - `update(name, proxy)`（`@plug.command()`）— 更新插件。
  - `search(query)`（`@plug.command()`）— 搜索插件。
  - `_get_data_path()`、`display_plugins(plugins, title, color)`。
- **关键常量**：无
- **依赖**：`re`、`shutil`、`pathlib`、`click`；`..utils`（`PluginStatus` / `build_plug_list` / `check_astrbot_root` / `get_astrbot_root` / `get_git_repo` / `install_local_plugin` / `manage_plugin`）。

### 9. `cli/utils/__init__.py`
- **职责**：utils 子包入口，导出 `basic` / `plugin` / `version_comparator` 的工具函数与类。
- **核心类**：无（透传 `PluginStatus` / `VersionComparator`）
- **核心函数**：无（透传 `build_plug_list` / `check_astrbot_root` / `check_dashboard` / `get_astrbot_root` / `get_git_repo` / `install_local_plugin` / `manage_plugin`）
- **关键常量**：`__all__`。
- **依赖**：`.basic`、`.plugin`、`.version_comparator`。

### 10. `cli/utils/basic.py`
- **职责**：基础工具，AstrBot 根目录检查 / 获取、dashboard 检查与下载。
- **核心类**：无
- **核心函数**：
  - `check_astrbot_root(path)` — 检查是否 AstrBot 根目录（`.astrbot` 存在）。
  - `get_astrbot_root()` — 返回当前工作目录。
  - `check_dashboard(astrbot_root)`（async）— 检查 / 下载 / 更新 dashboard（支持 wheel 内置 dist 跳过下载）。
- **关键常量**：`_BUNDLED_DIST`（wheel 内置 dashboard dist 路径）。
- **依赖**：`pathlib`、`click`；动态 `astrbot.core.config.default.VERSION`、`astrbot.core.utils.io`（`download_dashboard` / `get_dashboard_version`）、`.version_comparator.VersionComparator`。

### 11. `cli/utils/plugin.py`
- **职责**：插件管理工具，git 仓库下载、metadata 解析、插件列表构建、本地插件安装、插件管理（更新 / 移除）。
- **核心类**：
  - `PluginStatus(str, Enum)` — `INSTALLED` / `NEED_UPDATE` / `NOT_INSTALLED` / `NOT_PUBLISHED`。
- **核心函数**：
  - `get_git_repo(url, target_path, proxy)` — 从 git 仓库下载并解压（优先 release，回退 master/main 分支）。
  - `load_yaml_metadata(plugin_dir)` — 加载 `metadata.yaml`。
  - `build_plug_list(plugins_dir)` — 构建插件列表（含状态判定）。
  - `install_local_plugin(...)` — 安装本地插件。
  - `manage_plugin(...)` — 管理插件（更新 / 移除）。
  - `_validate_plugin_dir_name(plugin_name, source_path)`、`_cleanup_local_plugin_target(target_path)`、`_copy_local_plugin(source_path, plugins_dir, target_path)`。
- **关键常量**：`LOCAL_PLUGIN_COPY_IGNORE`（本地插件复制忽略模式）。
- **依赖**：`shutil`、`tempfile`、`uuid`、`zipfile`、`pathlib`、`click`、`httpx`、`yaml`；`.version_comparator.VersionComparator`。

### 12. `cli/utils/version_comparator.py`
- **职责**：语义化版本比较器（从 `astrbot.core.utils.version_comparator` 复制）。
- **核心类**：
  - `VersionComparator` — 静态方法：`compare_version(v1, v2)`（返回 1 / -1 / 0）、`_split_prerelease(prerelease)`。
- **核心函数**：无
- **关键常量**：无
- **依赖**：`re`

---

## 附：覆盖统计

| 目录 | 文件数 | 文件清单 |
| --- | --- | --- |
| `core/` 顶层 | 26（唯一文件） | `__init__`、`log`、`exceptions`、`sentinels`、`initial_loader`、`core_lifecycle`、`event_bus`、`astr_agent_hooks`、`astr_agent_context`、`astr_main_agent`、`astr_agent_run_util`、`astr_agent_tool_exec`、`astr_main_agent_resources`、`astrbot_config_mgr`、`conversation_mgr`、`platform_message_history_mgr`、`persona_mgr`、`persona_error_reply`、`file_token_service`、`desktop_runtime`、`updator`、`zip_updator`、`workspace`、`umop_config_router`、`umo_alias`、`subagent_orchestrator` |
| `api/` | 10 | `__init__`、`all`、`web`、`message_components`、`event/__init__`、`event/filter/__init__`、`platform/__init__`、`provider/__init__`、`star/__init__`、`util/__init__` |
| `builtin_stars/` | 12 | `astrbot/main`、`astrbot/group_chat_context`、`builtin_commands/main`、`builtin_commands/commands/__init__`、`commands/admin`、`commands/conversation`、`commands/help`、`commands/name`、`commands/provider`、`commands/setunset`、`commands/sid`、`commands/utils/rst_scene` |
| `cli/` | 12 | `__init__`、`__main__`、`commands/__init__`、`commands/cmd_run`、`commands/cmd_init`、`commands/cmd_password`、`commands/cmd_conf`、`commands/cmd_plug`、`utils/__init__`、`utils/basic`、`utils/plugin`、`utils/version_comparator` |
| **合计** | **60** | （任务列出的 21 个 core 文件 + Glob 额外发现的 `zip_updator` / `workspace` / `umop_config_router` / `umo_alias` / `subagent_orchestrator`，全部覆盖） |


---

## 章节二：core/db + core/config + core/message + core/star + core/knowledge_base

# AstrBot core 其他模块逐文件详解（db / config / message / star / knowledge_base）

本文档对 AstrBot core 层中除 `provider`、`platform`、`agent` 等已单独分析模块之外的五个核心模块进行逐文件详解。这五个模块分别承担：数据持久化（`db`）、配置管理（`config`）、消息组件与事件结果（`message`）、插件系统（`star`）以及知识库（`knowledge_base`）。每个文件均按 **职责 / 核心类 / 核心函数 / 关键常量 / 依赖** 五个小节展开，力求覆盖类的字段、方法签名、关键逻辑与跨模块依赖关系。

---

## 一、db 模块（数据持久化层）

`db` 模块负责 AstrBot 的全部持久化需求，分为两大部分：一是基于 SQLite + SQLModel/SQLAlchemy 的关系型主库（会话、人格、统计、偏好、API Key、Cron 任务、平台会话等），二是基于 FAISS + SQLite 的向量数据库（用于知识库检索）。此外还包含从 v3 到 v4 的一系列数据库迁移脚本。

### 1. `db/__init__.py`

- **职责**：定义数据库抽象基类 `BaseDatabase`，声明所有关系型数据库操作的标准接口（抽象方法），并管理异步引擎与会话工厂。
- **核心类**：
  - `BaseDatabase(abc.ABC)`：所有数据库实现（目前仅 `SQLiteDatabase`）的基类。
    - 字段：`DATABASE_URL`、`engine`（`AsyncEngine`）、`AsyncSessionLocal`（`async_sessionmaker`）。
    - 方法：`initialize()`、`get_db()`（异步上下文管理器，懒初始化）。
    - 抽象方法（按功能分组）：
      - 平台统计：`insert_platform_stats`、`count_platform_stats`、`get_platform_stats`。
      - Provider 统计：`insert_provider_stat`。
      - 会话管理：`get_conversations`、`get_conversation_by_id`、`get_all_conversations`、`get_filtered_conversations`、`create_conversation`、`update_conversation`、`delete_conversation`、`delete_conversations_by_user_id`。
      - 平台消息历史：`insert_platform_message_history`、`update_platform_message_history`、`delete_platform_message_history_by_id`、`delete_platform_message_offset`、`get_platform_message_history`、`get_platform_message_history_by_id`。
      - WebChat 子线程：`create_webchat_thread`、`get_webchat_thread_by_id`、`get_webchat_threads_by_parent_session`、`get_webchat_thread_by_parent_message_and_text`、`delete_webchat_thread`、`delete_webchat_threads_by_parent_session`、`delete_webchat_threads_by_parent_message_ids`。
      - 附件：`insert_attachment`、`get_attachment_by_id`、`get_attachments`、`delete_attachment`、`delete_attachments`。
      - API Key：`create_api_key`、`list_api_keys`、`get_api_key_by_id`、`get_active_api_key_by_hash`、`touch_api_key`、`revoke_api_key`、`delete_api_key`。
      - 人格：`insert_persona`、`get_persona_by_id`、`get_personas`、`update_persona`、`delete_persona`。
      - 人格文件夹：`insert_persona_folder`、`get_persona_folder_by_id`、`get_persona_folders`、`get_all_persona_folders`、`update_persona_folder`、`delete_persona_folder`、`move_persona_to_folder`、`get_personas_by_folder`、`batch_update_sort_order`。
      - 偏好：`insert_preference_or_update`、`get_preference`、`get_preferences`、`remove_preference`、`clear_preferences`。
      - 指令配置：`get_command_configs`、`get_command_config`、`upsert_command_config`、`delete_command_config`、`delete_command_configs`、`list_command_conflicts`、`upsert_command_conflict`、`delete_command_conflicts`。
      - 会话对话：`get_session_conversations`。
      - Cron 任务：`create_cron_job`、`update_cron_job`、`delete_cron_job`、`get_cron_job`、`list_cron_jobs`。
      - 平台会话：`create_platform_session`、`get_platform_session_by_id`、`get_platform_sessions_by_ids`、`get_platform_sessions_by_creator`、`get_platform_sessions_by_creator_paginated`、`update_platform_session`、`delete_platform_session`。
      - UMO 别名：`upsert_umo_alias`、`get_umo_alias`、`get_umo_aliases`。
      - ChatUI 项目：`create_chatui_project`、`get_chatui_project_by_id`、`get_chatui_projects_by_creator`、`update_chatui_project`、`delete_chatui_project`、`add_session_to_project`、`remove_session_from_project`、`get_project_sessions`、`get_project_by_session`。
    - 已废弃方法（`@deprecated`）：`get_base_stats`、`get_total_message_count`、`get_grouped_base_stats`。
- **核心函数**：无模块级函数。
- **关键常量**：无。
- **依赖**：`abc`、`datetime`、`typing`、`contextlib.asynccontextmanager`、`dataclasses`、`deprecated`、`sqlalchemy.ext.asyncio`（`AsyncSession`、`async_sessionmaker`、`create_async_engine`）、`astrbot.core.db.po`（全部 ORM 模型）、`astrbot.core.sentinels.NOT_GIVEN`。

### 2. `db/po.py`

- **职责**：定义所有关系型数据库的 ORM 模型（SQLModel 表）以及部分数据传输对象（`Conversation`、`Personality`、`Platform`、`Stats`）。
- **核心类**：
  - `TimestampMixin(SQLModel)`：混入类，提供 `created_at`、`updated_at` 字段及自动更新。
  - `PlatformStat`（表 `platform_stats`）：平台使用统计，含 `timestamp`、`platform_id`、`platform_type`、`count`，唯一约束 `(timestamp, platform_id, platform_type)`。
  - `ProviderStat`（表 `provider_stats`）：每次 LLM 调用的统计，含 `agent_type`、`status`、`umo`、`conversation_id`、`provider_id`、`provider_model`、token 各项（`token_input_other`、`token_input_cached`、`token_output`）、时间项（`start_time`、`end_time`、`time_to_first_token`）。
  - `ConversationV2`（表 `conversations`）：LLM 对话，`content` 为 JSON 格式的 OpenAI 消息列表，含 `conversation_id`、`platform_id`、`user_id`、`title`、`persona_id`、`token_usage`。
  - `PersonaFolder`（表 `persona_folders`）：人格文件夹，支持递归层级（`parent_id`），含 `name`、`description`、`sort_order`。
  - `Persona`（表 `personas`）：人格，含 `persona_id`、`system_prompt`、`begin_dialogs`、`tools`、`skills`、`custom_error_message`、`folder_id`、`sort_order`。
  - `CronJob`（表 `cron_jobs`）：定时任务定义，含 `job_id`、`name`、`job_type`、`cron_expression`、`timezone`、`payload`、`enabled`、`persistent`、`run_once`、`status`、`next_run_time`、`last_run_at`、`last_error`。
  - `Preference`（表 `preferences`）：偏好设置，含 `scope`、`scope_id`、`key`、`value`（JSON），唯一约束 `(scope, scope_id, key)`。
  - `PlatformMessageHistory`（表 `platform_message_history`）：平台消息历史，含 `platform_id`、`user_id`、`sender_id`、`sender_name`、`content`（JSON）、`llm_checkpoint_id`。
  - `WebChatThread`（表 `webchat_threads`）：WebChat 侧线程，含 `thread_id`、`creator`、`parent_session_id`、`parent_message_id`、`base_checkpoint_id`、`selected_text`。
  - `PlatformSession`（表 `platform_sessions`）：平台会话，含 `session_id`、`platform_id`、`creator`、`display_name`、`is_group`。
  - `UmoAlias`（表 `umo_aliases`）：UMO 别名，含 `umo`、`creator_sender_id`、`auto_name`、`user_alias`。
  - `Attachment`（表 `attachments`）：附件，含 `attachment_id`、`path`、`type`、`mime_type`。
  - `ApiKey`（表 `api_keys`）：API Key，含 `key_id`、`name`、`key_hash`、`key_prefix`、`scopes`、`created_by`、`last_used_at`、`expires_at`、`revoked_at`。
  - `DashboardTrustedDevice`（表 `dashboard_trusted_devices`）：仪表盘可信设备，含 `token_hash`、`totp_secret_hash`、`expires_at`。
  - `ChatUIProject`（表 `chatui_projects`）：ChatUI 项目，含 `project_id`、`creator`、`emoji`、`title`、`description`、`workspace_type`、`workspace_path`。
  - `SessionProjectRelation`（表 `session_project_relations`）：会话-项目关系，含 `session_id`、`project_id`。
  - `CommandConfig`（表 `command_configs`）：指令配置覆盖，含 `handler_full_name`（主键）、`plugin_name`、`module_path`、`original_command`、`resolved_command`、`enabled`、`keep_original_alias`、`conflict_key`、`resolution_strategy`、`auto_managed`。
  - `CommandConflict`（表 `command_conflicts`）：指令冲突追踪，含 `conflict_key`、`handler_full_name`、`plugin_name`、`status`、`resolution`、`resolved_command`、`auto_generated`。
  - `Conversation`（dataclass）：旧版对话对象（非表），含 `platform_id`、`user_id`、`cid`、`history`、`title`、`persona_id`、`token_usage`。
  - `Personality`（TypedDict）：旧版人格（已废弃）。
  - `Platform`（dataclass，已废弃）：平台统计。
  - `Stats`（dataclass，已废弃）：统计数据。
- **核心函数**：无。
- **关键常量**：各表的 `__tablename__` 字符串。
- **依赖**：`uuid`、`dataclasses`、`datetime`、`typing`、`sqlmodel`（`JSON`、`Field`、`SQLModel`、`Text`、`UniqueConstraint`）。

### 3. `db/sqlite.py`

- **职责**：`SQLiteDatabase`——`BaseDatabase` 的 SQLite 具体实现，实现全部抽象方法，并负责建表、列前向兼容迁移、SQLite 性能参数配置。
- **核心类**：
  - `SQLiteDatabase(BaseDatabase)`：
    - `__init__(db_path)`：设置 `DATABASE_URL = sqlite+aiosqlite:///...`，调用父类初始化引擎。
    - `initialize()`：`create_all` 建表 + PRAGMA 优化（WAL、busy_timeout=30000、synchronous=NORMAL、cache_size、temp_store=MEMORY、mmap_size、optimize）+ 列前向兼容（`_ensure_persona_folder_columns`、`_ensure_persona_skills_column`、`_ensure_persona_custom_error_message_column`、`_ensure_platform_message_history_checkpoint_column`、`_ensure_chatui_project_workspace_columns`）。
    - 实现 `BaseDatabase` 的全部抽象方法，使用 `sqlmodel` 的 `select`/`delete`/`update`/`func` 等。
- **核心函数**：无模块级函数。
- **关键常量**：`CRON_FIELD_NOT_SET = object()`（用于区分"未传入"与 `None`）。
- **依赖**：`asyncio`、`threading`、`typing`、`datetime`、`sqlalchemy`（`CursorResult`、`Row`、`text`）、`sqlalchemy.ext.asyncio.AsyncSession`、`sqlmodel`（`col`、`delete`、`desc`、`func`、`or_`、`select`、`text`、`update`）、`astrbot.core.db.BaseDatabase`、`astrbot.core.db.po.*`、`astrbot.core.sentinels.NOT_GIVEN`。

### 4. `db/vec_db/base.py`

- **职责**：定义向量数据库抽象基类 `BaseVecDB` 及检索结果数据类 `Result`。
- **核心类**：
  - `Result`（dataclass）：`similarity: float`、`data: dict`。
  - `BaseVecDB`：
    - `initialize()`：初始化（空实现）。
    - 抽象方法：`insert`、`insert_batch`、`retrieve`、`delete`、`close`。
- **核心函数**：无。
- **关键常量**：无。
- **依赖**：`abc`、`dataclasses`。

### 5. `db/vec_db/faiss_impl/__init__.py`

- **职责**：包初始化，通过 `__getattr__` 懒加载 `FaissVecDB`。
- **核心类**：无。
- **核心函数**：`__getattr__(name)`。
- **关键常量**：`__all__ = ["FaissVecDB"]`。
- **依赖**：`.vec_db.FaissVecDB`。

### 6. `db/vec_db/faiss_impl/vec_db.py`

- **职责**：`FaissVecDB`——基于 FAISS 的向量数据库实现，协调文档存储（`DocumentStorage`）与向量存储（`EmbeddingStorage`），提供插入、批量插入、检索、删除、统计功能，支持 Rerank 与失败回滚。
- **核心类**：
  - `FaissVecDB(BaseVecDB)`：
    - `__init__(doc_store_path, index_store_path, embedding_provider, rerank_provider=None)`：创建 `DocumentStorage` 和 `EmbeddingStorage`。
    - `initialize()`：初始化文档存储。
    - `insert(content, metadata, id)`：单条插入，生成向量并写入。
    - `insert_batch(contents, metadatas, ids, batch_size, tasks_limit, max_retries, progress_callback)`：批量插入，含向量维度校验、`KnowledgeBaseUploadError` 包装、`_rollback_partial_insert` 补偿清理。
    - `retrieve(query, k, fetch_k, rerank, metadata_filters)`：稠密检索，归一化分数 `1.0 - (scores / 2.0)`，可选 Rerank。
    - `_rollback_partial_insert(ids, int_ids)`：FAISS 写入失败后回滚文档存储。
    - `delete(doc_id)`：删除单条文档块。
    - `count_documents(metadata_filter)`：统计文档数。
    - `delete_documents(metadata_filters)`：按元数据批量删除。
    - `close()`。
- **核心函数**：无模块级函数。
- **关键常量**：无。
- **依赖**：`time`、`uuid`、`numpy`、`astrbot.logger`、`astrbot.core.exceptions.KnowledgeBaseUploadError`、`astrbot.core.provider.provider.EmbeddingProvider`/`RerankProvider`、`..base.BaseVecDB`/`Result`、`.document_storage.DocumentStorage`、`.embedding_storage.EmbeddingStorage`。

### 7. `db/vec_db/faiss_impl/document_storage.py`

- **职责**：`DocumentStorage`——基于 SQLite 的文档（文本块）存储，管理 `documents` 表及 FTS5 全文检索索引，支持元数据 JSON 过滤、批量增删改、稀疏检索（`search_sparse`）。
- **核心类**：
  - `BaseDocModel(SQLModel, table=False)`：定义共享 `MetaData`。
  - `Document`（表 `documents`）：`id`、`doc_id`、`text`、`metadata_`（列名 `metadata`）、`created_at`、`updated_at`。
  - `DocumentStorage`：
    - `__init__(db_path)`：配置 `DATABASE_URL`、引擎、会话工厂、FTS5 状态标志。
    - `initialize()`：建表、添加生成列（`kb_doc_id`、`user_id`，从 `metadata` JSON 提取）、创建索引、`_initialize_fts5`。
    - `_initialize_fts5`/`_create_fts5_table`/`_inspect_fts5_table`：FTS5 表的创建与兼容性检查，支持 `contentless_delete=1`。
    - `connect()`/`get_session()`：连接管理。
    - `get_documents(metadata_filters, ids, offset, limit)`：按 `json_extract` 过滤查询。
    - `insert_document`/`insert_documents_batch`：插入文档并同步 FTS 索引。
    - `delete_document_by_doc_id`/`delete_documents`：删除文档及 FTS 行。
    - `get_document_by_doc_id`/`update_document_by_doc_id`：单条查询/更新。
    - `count_documents`：计数。
    - `ensure_fts_index`/`rebuild_fts_index`：FTS 索引一致性检查与重建。
    - `search_sparse(query_tokens, limit)`：FTS5 BM25 稀疏检索，返回 `None` 时回退内存 BM25。
    - FTS 内部方法：`_insert_fts_row`/`_insert_fts_rows_batch`/`_delete_fts_row`/`_delete_fts_rows_batch`/`_fts_row_exists`/`_existing_fts_rowids`。
    - `get_user_ids()`、`_document_to_dict()`、`close()`。
    - `stopwords` 属性：懒加载停用词表。
- **核心函数**：无模块级函数。
- **关键常量**：`FTS_TABLE_NAME = "documents_fts"`、`FTS_REBUILD_BATCH_SIZE = 1000`。
- **依赖**：`json`、`os`、`contextlib.asynccontextmanager`、`datetime`、`pathlib.Path`、`sqlalchemy`（`Column`、`Text`、`bindparam`）、`sqlalchemy.ext.asyncio`（`AsyncEngine`、`AsyncSession`、`create_async_engine`）、`sqlalchemy.orm.sessionmaker`、`sqlmodel`（`Field`、`MetaData`、`SQLModel`、`col`、`func`、`select`、`text`）、`astrbot.core.logger`、`astrbot.core.knowledge_base.retrieval.tokenizer`（`build_fts5_or_query`、`load_stopwords`、`to_fts5_search_text`）。

### 8. `db/vec_db/faiss_impl/embedding_storage.py`

- **职责**：`EmbeddingStorage`——基于 FAISS 的向量索引存储，负责向量的插入、批量插入、L2 归一化搜索、删除与持久化。
- **核心类**：
  - `EmbeddingStorage`：
    - `__init__(dimension, path)`：加载或创建 `IndexFlatL2` + `IndexIDMap`。
    - `insert(vector, id)`：单条插入，维度校验。
    - `insert_batch(vectors, ids)`：批量插入。
    - `search(vector, k)`：L2 归一化后搜索，返回 `(distances, indices)`。
    - `delete(ids)`：按 ID 删除向量。
    - `save_index()`：持久化索引到磁盘。
- **核心函数**：无。
- **关键常量**：无。
- **依赖**：`os`、`numpy`、`faiss`（懒导入，缺失时抛 `ImportError` 提示安装 `faiss-cpu`/`faiss-gpu`）。

### 9. `db/migration/helper.py`

- **职责**：v3→v4 数据库迁移的入口协调器，检查迁移条件并依次调用各子迁移函数。
- **核心函数**：
  - `check_migration_needed_v4(db_helper)`：检查 `data_v3.db` 是否存在且偏好中无 `migration_done_v4` 标记。
  - `do_migration_v4(db_helper, platform_id_map, astrbot_config)`：执行会话表、人格数据、WebChat 数据、偏好设置、平台统计表的迁移，最后标记完成。
- **关键常量**：无。
- **依赖**：`os`、`astrbot.api`（`logger`、`sp`）、`astrbot.core.config.AstrBotConfig`、`astrbot.core.db.BaseDatabase`、`astrbot.core.utils.astrbot_path.get_astrbot_data_path`、`.migra_3_to_4.*`。

### 10. `db/migration/migra_3_to_4.py`

- **职责**：v3→v4 的具体迁移逻辑，包括会话表迁移、人格数据迁移、WebChat 数据迁移、偏好设置迁移、平台统计表迁移。
- **核心函数**：
  - `get_platform_id`/`get_platform_type(platform_id_map, old_platform_name)`：通过映射表获取新平台 ID/类型。
  - `migration_conversation_table(db_helper, platform_id_map)`：从 v3 数据库读取旧会话，写入 v4 `conversations` 表。
  - `migration_persona_data(db_helper, astrbot_config)`：迁移人格数据。
  - `migration_webchat_data(db_helper, platform_id_map)`：迁移 WebChat 数据。
  - `migration_preferences(db_helper, platform_id_map)`：迁移偏好设置。
  - `migration_platform_table(db_helper, platform_id_map)`：迁移平台统计表。
- **关键常量**：无。
- **依赖**：`datetime`、`json`、`sqlalchemy.text`、`sqlalchemy.ext.asyncio.AsyncSession`、`astrbot.api`（`logger`、`sp`）、`astrbot.core.config.AstrBotConfig`、`astrbot.core.config.default.DB_PATH`、`astrbot.core.db.po.ConversationV2`/`PlatformMessageHistory`、`astrbot.core.platform.astr_message_event.MessageSesion`、`..BaseDatabase`、`.shared_preferences_v3.sp`、`.sqlite_v3.SQLiteDatabase`。

### 11. `db/migration/migra_45_to_46.py`

- **职责**：v4.5→v4.6 配置迁移，将 `abconf_data` 中的 `umop` 字段提取为 `umo→conf_id` 路由映射。
- **核心函数**：
  - `migrate_45_to_46(acm, ucr)`：检查是否含 `umop` 字段，提取映射，更新 `abconf_mapping` 与 `UmopConfigRouter`。
- **关键常量**：无。
- **依赖**：`astrbot.api`（`logger`、`sp`）、`astrbot.core.astrbot_config_mgr.AstrBotConfigManager`、`astrbot.core.umop_config_router.UmopConfigRouter`。

### 12. `db/migration/migra_token_usage.py`

- **职责**：为 `conversations` 表添加 `token_usage` 列的迁移脚本。
- **核心函数**：
  - `migrate_token_usage(db_helper)`：检查迁移标记，检查列是否存在，`ALTER TABLE` 添加 `token_usage INTEGER NOT NULL DEFAULT 0`，标记完成。
- **关键常量**：无。
- **依赖**：`sqlalchemy.text`、`astrbot.api`（`logger`、`sp`）、`astrbot.core.db.BaseDatabase`。

### 13. `db/migration/migra_webchat_session.py`

- **职责**：从 `platform_message_history` 创建 `PlatformSession` 记录的迁移脚本。
- **核心函数**：
  - `migrate_webchat_session(db_helper)`：查询 webchat 平台的唯一 `user_id`，关联 `conversations` 表的 `title` 作为 `display_name`，批量创建 `PlatformSession`。
- **关键常量**：无。
- **依赖**：`sqlalchemy`（`func`、`select`）、`sqlmodel.col`、`astrbot.api`（`logger`、`sp`）、`astrbot.core.db.BaseDatabase`、`astrbot.core.db.po.ConversationV2`/`PlatformMessageHistory`/`PlatformSession`。

### 14. `db/migration/sqlite_v3.py`

- **职责**：v3 版本的 SQLite 数据库实现（仅用于迁移读取旧数据），定义旧表结构 `INIT_SQL` 与 `Conversation` dataclass。
- **核心类**：
  - `Conversation`（dataclass）：旧版对话存储结构。
  - `SQLiteDatabase`（v3）：v3 数据库实现（通过 `INIT_SQL` 建表）。
- **核心函数**：无（具体方法在类内）。
- **关键常量**：`INIT_SQL`（v3 建表 SQL：`platform`、`llm`、`plugin`、`command`、`llm_history`、`atri_vision` 等表）。
- **依赖**：`sqlite3`、`time`、`dataclasses`、`typing`、`astrbot.core.db.po.Platform`/`Stats`。

### 15. `db/migration/shared_preferences_v3.py`

- **职责**：v3 版本的共享偏好存储（`SharedPreferences`），用于迁移时读取旧偏好数据。
- **核心类**：`SharedPreferences`（v3 实现，基于 SQLite 的键值存储）。
- **核心函数**：无。
- **关键常量**：`sp`（模块级单例实例）。
- **依赖**：`sqlite3`、`astrbot.core.db.po`（参考）。（具体实现细节需查看完整文件。）

---

## 二、config 模块（配置管理）

`config` 模块负责 AstrBot 的主配置文件（`cmd_config.json`）的加载、校验、持久化，默认配置定义，以及配置元数据的国际化键转换。

### 1. `config/__init__.py`

- **职责**：包初始化，导出 `AstrBotConfig`、`DB_PATH`、`DEFAULT_CONFIG`、`VERSION`。
- **核心类**：无。
- **核心函数**：无。
- **关键常量**：`__all__`。
- **依赖**：`.astrbot_config.*`、`.default.DB_PATH`/`DEFAULT_CONFIG`/`VERSION`。

### 2. `config/astrbot_config.py`

- **职责**：`AstrBotConfig`——AstrBot 主配置类，继承 `dict`，支持点号访问、配置完整性校验（递归补全缺失项、修正顺序）、原子化异步/同步保存（临时文件 + `os.replace`）、Schema 到默认配置的转换、Dashboard 密码管理。
- **核心类**：
  - `RateLimitStrategy(enum.Enum)`：`STALL`、`DISCARD`。
  - `AstrBotConfig(dict)`：
    - 字段（通过 `object.__setattr__` 避免 dict 存储）：`config_path`、`default_config`、`schema`、`_save_state_lock`、`_save_commit_lock`、`_save_revision`、`_save_committed_revision`。
    - `__init__(config_path, default_config, schema)`：加载或创建配置文件，处理 UTF-8 BOM，检查完整性，管理 Dashboard 密码（重置/生成/标记修改）。
    - `_reset_generated_dashboard_password(conf)`：生成并哈希密码。
    - `_consume_reset_dashboard_password_flag()`：读取并清除环境变量 `ASTRBOT_RESET_DASHBOARD_PASSWORD`。
    - `_resolve_initial_dashboard_password()`：从环境变量或随机生成。
    - `_config_schema_to_default_config(schema)`：递归解析 Schema 生成默认配置。
    - `check_config_integrity(refer_conf, conf, path)`：递归比对，补全缺失项，移除多余项，修正顺序，返回是否有变更。
    - `save_config(replace_config, indent)`：同步保存（快照 + 临时文件 + `os.replace`）。
    - `save_config_async(replace_config, indent)`：异步保存（`asyncio.to_thread`）。
    - `_prepare_config_snapshot(replace_config)`：深拷贝快照并分配 revision。
    - `_write_config_snapshot(snapshot, revision, indent)`：原子写入，revision 版本控制防止旧快照覆盖。
    - `__getattr__`/`__setattr__`/`__delattr__`：支持点号访问。
    - `check_exist()`。
- **核心函数**：无模块级函数。
- **关键常量**：`ASTRBOT_CONFIG_PATH`、`DASHBOARD_INITIAL_PASSWORD_ENV`、`DASHBOARD_RESET_PASSWORD_ENV`。
- **依赖**：`asyncio`、`copy`、`enum`、`json`、`logging`、`os`、`tempfile`、`threading`、`astrbot.core.utils.astrbot_path.get_astrbot_data_path`、`astrbot.core.utils.auth_password.*`、`.default.DEFAULT_CONFIG`/`DEFAULT_VALUE_MAP`。

### 3. `config/default.py`

- **职责**：定义 AstrBot 的默认配置 `DEFAULT_CONFIG`、默认值映射 `DEFAULT_VALUE_MAP`、版本号 `VERSION`、数据库路径 `DB_PATH` 等路径常量。
- **核心类**：无（主要为字典/字符串常量）。
- **核心函数**：无。
- **关键常量**：
  - `VERSION`：AstrBot 版本号字符串。
  - `DB_PATH`：主数据库路径（`data_v4.db`）。
  - `DEFAULT_CONFIG`：完整的默认配置字典（含 `dashboard`、`platform`、`provider`、`provider_settings`、`personality`、`provider_lts`、`webchat`、`server`、`import_to_path`、`wake_prefix` 等顶层键）。
  - `DEFAULT_VALUE_MAP`：配置类型到默认值的映射（`string`→`""`、`int`→`0`、`float`→`0.0`、`bool`→`False`、`list`→`[]`、`object`→`{}`、`template_list`→`[]`）。
- **依赖**：`os`、`astrbot.core.utils.astrbot_path.*`（路径工具）。（文件较大，包含数百行配置定义。）

### 4. `config/i18n_utils.py`

- **职责**：`ConfigMetadataI18n`——配置元数据国际化工具，将配置元数据中的 `description`、`hint`、`labels`、`name` 字段转换为国际化键（如 `ai_group.agent_runner.enable.description`）。
- **核心类**：
  - `ConfigMetadataI18n`：
    - `_get_i18n_key(group, section, field, attr)`：生成国际化键。
    - `convert_to_i18n_keys(metadata)`：递归转换配置元数据，处理 `items`、`template_schema` 嵌套结构。
- **核心函数**：无模块级函数。
- **关键常量**：无。
- **依赖**：`typing.Any`。

---

## 三、message 模块（消息组件与事件结果）

`message` 模块定义了 AstrBot 的消息组件体系（Plain、Image、At、Record、Video、File 等）以及消息链（`MessageChain`）和事件处理结果（`MessageEventResult`）。

### 1. `message/components.py`

- **职责**：定义所有消息组件类型（OneBot V11 兼容），包括纯文本、图片、语音、视频、文件、@、回复、戳一戳、合并转发等，提供文件路径/Base64/URL 的统一转换方法及文件服务注册。
- **核心类**：
  - `ComponentType(str, Enum)`：组件类型枚举（`Plain`、`Image`、`Record`、`Video`、`File`、`Face`、`At`、`Node`、`Nodes`、`Poke`、`Reply`、`Forward`、`RPS`、`Dice`、`Shake`、`Share`、`Contact`、`Location`、`Music`、`Json`、`Unknown`）。
  - `BaseMessageComponent(BaseModel)`：基类，含 `type` 字段、`__repr_args__`（截断 base64/超长字段）、`toDict()`、`to_dict()`。
  - `Plain`：纯文本，`text: str`。
  - `Face`：表情，`id: int`。
  - `Record`：语音，`file`/`url`/`text`/`path`，工厂方法 `fromFileSystem`/`fromURL`/`fromBase64`，`_resolve_file_source`（多源 fallback）、`convert_to_file_path`/`convert_to_base64`/`register_to_file_service`。
  - `Video`：视频，`file`/`url`/`cover`/`path`，类似 Record 的转换方法。
  - `At`：@，`qq: int|str`、`name`。
  - `AtAll(At)`：@所有人，`qq="all"`。
  - `RPS`/`Dice`/`Shake`：TODO 占位。
  - `Share`：分享，`url`/`title`/`content`/`image`。
  - `Contact`/`Location`：TODO 占位。
  - `Music`：音乐，`_type`/`id`/`url`/`audio`/`title`/`content`/`image`。
  - `Image`：图片，`file`/`url`/`path`，工厂方法 `fromURL`/`fromFileSystem`/`fromBase64`/`fromBytes`/`fromIO`，`convert_to_file_path`/`convert_to_base64`/`register_to_file_service`。
  - `Reply`：回复，`id`/`chain`/`sender_id`/`sender_nickname`/`time`/`message_str`。
  - `Poke`：戳一戳，`_type`/`id`/`qq`，`target_id()` 规范化。
  - `Forward`：合并转发，`id`。
  - `Node`：合并转发节点，`id`/`name`/`uin`/`content`/`seq`/`time`，`to_dict()` 递归转换子组件。
  - `Nodes`：节点集合，`nodes: list[Node]`。
  - `Json`：JSON 消息，`data: dict`。
  - `Unknown`：未知，`text`。
  - `File`：文件，`name`/`file_`/`url`，`file` property（同步下载，异步上下文警告）、`get_file()`（异步下载）、`register_to_file_service`、`to_dict()`。
- **核心函数**：
  - `_sanitize_file_component_name(name)`：清理文件名中的非法字符。
- **关键常量**：`ComponentTypes`（字符串到类的映射字典）。
- **依赖**：`asyncio`、`base64`、`json`、`os`、`sys`、`uuid`、`enum`、`pathlib`、`pydantic`（或 `pydantic.v1`，根据 Python 版本）、`astrbot.core`（`astrbot_config`、`file_token_service`、`logger`）、`astrbot.core.utils.astrbot_path.get_astrbot_temp_path`、`astrbot.core.utils.io.download_file`、`astrbot.core.utils.media_utils.*`。

### 2. `message/message_event_result.py`

- **职责**：定义 `MessageChain`（消息链）与 `MessageEventResult`（事件处理结果），以及结果类型枚举。
- **核心类**：
  - `MessageChain`（dataclass）：`chain: list[BaseMessageComponent]`、`use_t2i_: bool|None`、`use_markdown_: bool|None`、`type: str|None`。
    - `derive(chain)`：基于当前链创建新链，继承元数据。
    - 链式构造方法：`message()`、`at()`、`at_all()`、`error()`（已废弃）、`url_image()`、`file_image()`、`base64_image()`。
    - `use_t2i(use_t2i)`、`use_markdown(use)`：设置渲染选项。
    - `get_plain_text(with_other_comps_mark)`：提取纯文本。
    - `squash_plain()`：合并所有 Plain 段。
  - `EventResultType(enum.Enum)`：`CONTINUE`、`STOP`。
  - `ResultContentType(enum.Enum)`：`LLM_RESULT`、`AGENT_RUNNER_ERROR`、`GENERAL_RESULT`、`STREAMING_RESULT`、`STREAMING_FINISH`。
  - `MessageEventResult(MessageChain)`：`result_type`、`result_content_type`、`async_stream`。
    - `stop_event()`/`continue_event()`/`is_stopped()`：事件传播控制。
    - `set_async_stream(stream)`：设置流式输出。
    - `set_result_content_type(typ)`、`is_llm_result()`、`is_model_result()`。
  - `CommandResult = MessageEventResult`：向后兼容别名。
- **核心函数**：无模块级函数。
- **关键常量**：`CommandResult`。
- **依赖**：`enum`、`collections.abc.AsyncGenerator`、`dataclasses`、`typing_extensions.deprecated`、`astrbot.core.message.components.*`（`At`、`AtAll`、`BaseMessageComponent`、`Image`、`Json`、`Plain`）。

---

## 四、star 模块（插件系统）

`star` 模块是 AstrBot 插件系统的核心，包含插件基类、元数据、注册装饰器、事件过滤器、插件管理器（加载/重载/启停/安装/卸载）、上下文（依赖注入）、指令管理、会话级插件/服务管理器等。

### 1. `star/__init__.py`

- **职责**：包初始化，导出 `Star`、`Context`、`PluginManager`、`StarTools`、`StarMetadata`、`star_map`、`star_registry`、`Provider`。
- **核心类**：无。
- **核心函数**：无。
- **关键常量**：`__all__`。
- **依赖**：`astrbot.core.provider.Provider`、`.base.Star`、`.context.Context`、`.star.StarMetadata`/`star_map`/`star_registry`、`.star_manager.PluginManager`、`.star_tools.StarTools`。

### 2. `star/base.py`

- **职责**：`Star`——所有插件的基类，继承 `CommandParserMixin` 与 `PluginKVStoreMixin`，通过 `__init_subclass__` 自动注册插件元数据，提供文本转图片、HTML 渲染、生命周期钩子。
- **核心类**：
  - `Star`：
    - 类属性：`author`、`name`、`context`。
    - `__init__(context, config)`。
    - `_get_context_config()`：安全获取配置。
    - `__init_subclass__(cls)`：自动创建/更新 `StarMetadata` 并注册到 `star_map`/`star_registry`。
    - `text_to_image(text, return_url)`：文本转图片（读取 `t2i_active_template`）。
    - `html_render(tmpl, data, return_url, options)`：渲染自定义 HTML 模板。
    - `initialize()`/`terminate()`：生命周期钩子（子类覆写）。
    - `__del__()`：已废弃。
- **核心函数**：无模块级函数。
- **关键常量**：无。
- **依赖**：`logging`、`typing`、`astrbot.core.html_renderer`、`astrbot.core.utils.command_parser.CommandParserMixin`、`astrbot.core.utils.plugin_kv_store.PluginKVStoreMixin`、`.star.StarMetadata`/`star_map`/`star_registry`。

### 3. `star/star.py`

- **职责**：定义插件元数据 `StarMetadata` 及全局注册表 `star_map`、`star_registry`。
- **核心类**：
  - `StarMetadata`（dataclass）：插件元数据，含 `name`、`author`、`desc`、`short_desc`、`version`、`repo`、`star_cls_type`、`module_path`、`star_cls`、`module`、`root_dir_name`、`reserved`、`activated`、`config`、`star_handler_full_names`、`display_name`、`logo_path`、`support_platforms`、`astrbot_version`、`i18n`、`pages`。
    - `plugin_id` 属性：`{author}/{name}` 规范化。
- **核心函数**：无。
- **关键常量**：`star_registry: list[StarMetadata]`、`star_map: dict[str, StarMetadata]`（key 为模块路径）。
- **依赖**：`dataclasses`、`types.ModuleType`、`typing`、`astrbot.core.config.AstrBotConfig`。

### 4. `star/star_handler.py`

- **职责**：定义 Handler 注册表 `StarHandlerRegistry`、Handler 元数据 `StarHandlerMetadata`、事件类型枚举 `EventType`。
- **核心类**：
  - `StarHandlerRegistry(Generic[T])`：
    - `append(handler)`：按优先级（`extras_configs["priority"]`，默认 0）有序添加。
    - `get_handlers_by_event_type(event_type, only_activated, plugins_name)`：按事件类型/激活状态/插件白名单过滤，多个 `@overload` 声明类型。
    - `get_handler_by_full_name(full_name)`、`get_handlers_by_module_name(module_name)`、`clear()`、`remove(handler)`、`__iter__`、`__len__`。
  - `EventType(enum.Enum)`：`OnAstrBotLoadedEvent`、`OnPlatformLoadedEvent`、`AdapterMessageEvent`、`OnWaitingLLMRequestEvent`、`OnLLMRequestEvent`、`OnLLMResponseEvent`、`OnAgentBeginEvent`、`OnAgentDoneEvent`、`OnDecoratingResultEvent`、`OnCallingFuncToolEvent`、`OnUsingLLMToolEvent`、`OnLLMToolRespondEvent`、`OnAfterMessageSentEvent`、`OnPluginErrorEvent`、`OnPluginLoadedEvent`、`OnPluginUnloadedEvent`。
  - `StarHandlerMetadata`（Generic dataclass）：`event_type`、`handler_full_name`、`handler_name`、`handler_module_path`、`handler`、`event_filters`、`desc`、`extras_configs`、`enabled`。
- **核心函数**：无模块级函数。
- **关键常量**：`star_handlers_registry = StarHandlerRegistry()`（全局单例）。
- **依赖**：`enum`、`collections.abc`、`dataclasses`、`typing`、`.filter.HandlerFilter`、`.star.star_map`。

### 5. `star/context.py`

- **职责**：`Context`——暴露给插件的接口上下文（依赖注入容器），聚合数据库、Provider 管理器、平台管理器、会话管理器、人格管理器、知识库管理器、Cron 管理器等，提供消息发送、LLM 工具管理、Web API 注册等能力。
- **核心类**：
  - `PlatformManagerProtocol(Protocol)`：平台管理器协议。
  - `Context`：
    - 类属性：`registered_web_apis`、`_register_tasks`、`_star_manager`。
    - `__init__(event_queue, config, db, provider_manager, platform_manager, conversation_manager, message_history_manager, persona_manager, astrbot_config_mgr, knowledge_base_manager, cron_manager, subagent_orchestrator)`：注入所有核心管理器。
    - 提供对各类管理器的属性访问（`_db`、`_config`、`provider_manager`、`platform_manager`、`conversation_manager`、`message_history_manager`、`persona_manager`、`knowledge_base_manager`、`cron_manager` 等）。
    - 消息发送、LLM 工具激活/停用/注册/注销、Web API 注册等方法。
    - 模块路径解析辅助函数：`_split_module_path`、`_plugin_root_from_module_parts`、`_plugin_root_from_metadata`、`_registered_plugin_module_path`、`_legacy_plugin_module_path`、`_resolve_tool_handler_module_path`。
- **核心函数**：上述模块级辅助函数。
- **关键常量**：`_PLUGIN_MODULE_FLAGS = {"builtin_stars", "plugins"}`、`WebApiHandler`、`RegisteredWebApi` 类型别名。
- **依赖**：`logging`、`asyncio.Queue`、`collections.abc`、`typing`、`deprecated`、`astrbot.core.agent.*`、`astrbot.core.astrbot_config_mgr.AstrBotConfigManager`、`astrbot.core.config.astrbot_config.AstrBotConfig`、`astrbot.core.conversation_mgr.ConversationManager`、`astrbot.core.db.BaseDatabase`、`astrbot.core.knowledge_base.kb_mgr.KnowledgeBaseManager`、`astrbot.core.message.message_event_result.MessageChain`、`astrbot.core.persona_mgr.PersonaManager`、`astrbot.core.platform.Platform`、`astrbot.core.platform.astr_message_event.*`、`astrbot.core.platform_message_history_mgr.PlatformMessageHistoryManager`、`astrbot.core.provider.*`、`astrbot.core.star.filter.platform_adapter_type.*`、`astrbot.core.subagent_orchestrator.SubAgentOrchestrator`、`astrbot.core.utils.astrbot_path.*`、`..exceptions.ProviderNotFoundError`、`.filter.command.CommandFilter`、`.filter.regex.RegexFilter`、`.star.StarMetadata`/`star_map`/`star_registry`、`.star_handler.EventType`/`StarHandlerMetadata`/`star_handlers_registry`。

### 6. `star/star_manager.py`

- **职责**：`PluginManager`——插件管理器，负责插件的加载、重载、启停、安装、卸载、依赖安装、热重载（`watchfiles`）、版本兼容性检查等。
- **核心类**：
  - `PluginVersionUnsupportedError`/`PluginDependencyInstallError`：异常类。
  - `ImportDependencyRecoveryMode(Enum)`：`DISABLED`、`PRELOAD_AND_RECOVER`、`RECOVER_ON_FAILURE`、`REINSTALL_ON_FAILURE`。
  - `ImportDependencyRecoveryState`（dataclass）：依赖恢复状态。
  - `PluginManager`：核心管理器类（文件较大，含 `_load_plugin`、`reload_plugin`、`turn_off_plugin`、`install_plugin`、`uninstall_plugin`、`_reloading_plugin`、热重载监听等方法）。
- **核心函数**：无模块级函数。
- **关键常量**：`PLUGIN_TOOL_STATE_MIGRATION_KEY`。
- **依赖**：`asyncio`、`contextlib`、`functools`、`inspect`、`json`、`keyword`、`logging`、`os`、`sys`、`tempfile`、`traceback`、`dataclasses`、`enum`、`pathlib`、`types`、`yaml`、`packaging.specifiers`/`packaging.version`、`astrbot.core.*`、`astrbot.core.agent.handoff.*`、`astrbot.core.config.*`、`astrbot.core.platform.register.unregister_platform_adapters_by_module`、`astrbot.core.provider.register.llm_tools`、`astrbot.core.utils.*`、`.StarMetadata`、`.command_management.sync_command_configs`、`.context.Context`、`.error_messages.format_plugin_error`、`.filter.permission.*`、`.star.star_map`/`star_registry`、`.star_handler.EventType`/`star_handlers_registry`、`.updator.PLUGIN_METADATA_FILENAMES`/`PluginUpdator`、`watchfiles`（可选）。

### 7. `star/star_tools.py`

- **职责**：`StarTools`——插件便捷工具类（类方法），提供跨会话消息发送、消息/事件创建与提交、LLM 工具管理、插件数据目录获取。
- **核心类**：
  - `StarTools`：
    - `_context: ClassVar[Context|None]`。
    - `initialize(context)`：初始化上下文引用。
    - `send_message(session, message_chain)`：按 UMO 发送消息。
    - `create_message(type, self_id, session_id, sender, message, message_str, ...)`：创建 `AstrBotMessage`。
    - `create_event(abm, platform, is_wake)`：创建并提交事件到目标平台。
    - `activate_llm_tool(name)`/`deactivate_llm_tool(name)`/`register_llm_tool(...)`/`unregister_llm_tool(name)`：LLM 工具管理。
    - `get_data_dir(plugin_name)`：获取/创建插件数据目录（`data/plugin_data/{plugin_name}`），支持调用栈自动推断插件名。
- **核心函数**：无模块级函数。
- **关键常量**：无。
- **依赖**：`inspect`、`os`、`uuid`、`pathlib`、`typing`、`astrbot.api.platform.*`、`astrbot.core.message.components.BaseMessageComponent`、`astrbot.core.message.message_event_result.MessageChain`、`astrbot.core.platform.astr_message_event.MessageSesion`、`astrbot.core.star.context.Context`、`astrbot.core.star.star.star_map`、`astrbot.core.utils.astrbot_path.get_astrbot_data_path`、`astrbot.core.utils.io.ensure_dir`。

### 8. `star/config.py`

- **职责**：已过时的插件配置文件管理（基于 JSON 文件的 `config/{namespace}.json`），提供 `load_config`、`put_config`、`update_config`。
- **核心函数**：
  - `load_config(namespace)`：加载配置文件，返回 `{key: value}` 字典。
  - `put_config(namespace, name, key, value, description)`：写入配置项（仅当 key 不存在时）。
  - `update_config(namespace, key, value)`：更新配置项。
- **关键常量**：无。
- **依赖**：`json`、`os`、`astrbot.core.utils.astrbot_path.get_astrbot_data_path`。

### 9. `star/command_management.py`

- **职责**：指令配置管理，同步指令配置到数据库、指令启停、冲突解决。
- **核心类**：
  - `CommandDescriptor`（dataclass）：指令描述符，含 `handler`、`filter_ref`、`handler_full_name`、`plugin_name`、`command_type`、`original_command`、`effective_command`、`aliases`、`permission`、`enabled`、`is_group`、`is_sub_command`、`reserved`、`config`、`has_conflict`、`sub_commands` 等。
- **核心函数**：
  - `sync_command_configs()`：收集描述符，绑定数据库配置，清理过期配置。
  - `toggle_command(handler_full_name, enabled)`：切换指令启停。
  - 其他指令管理函数（文件较大，含冲突解决逻辑）。
- **关键常量**：无。
- **依赖**：`collections.defaultdict`、`dataclasses`、`typing`、`astrbot.api.sp`、`astrbot.core.db_helper`/`logger`、`astrbot.core.db.po.CommandConfig`、`.filter.command.CommandFilter`、`.filter.command_group.CommandGroupFilter`、`.filter.permission.*`、`.star.star_map`、`.star_handler.StarHandlerMetadata`/`star_handlers_registry`。

### 10. `star/error_messages.py`

- **职责**：插件管理流程的共享错误消息模板。
- **核心函数**：
  - `format_plugin_error(key, **kwargs)`：按模板格式化错误消息。
- **关键常量**：`PLUGIN_ERROR_TEMPLATES`（含 `not_found_in_failed_list`、`reserved_plugin_cannot_uninstall`、`failed_plugin_dir_remove_error`）。
- **依赖**：无外部依赖。

### 11. `star/updator.py`

- **职责**：`PluginUpdator`——插件更新器，继承 `RepoZipUpdator`，负责从 GitHub 仓库或下载链接安装/更新插件，处理 ZIP 压缩包的下载、校验、解压。
- **核心类**：
  - `PluginUpdator(RepoZipUpdator)`：
    - `__init__(repo_mirror, verify)`。
    - `get_plugin_store_address()`。
    - `install(repo_url, proxy, download_url)`：下载并解压到插件目录。
    - `update(plugin, proxy, download_url)`：更新已安装插件。
    - `find_plugin_metadata_entry(entries)`：在 ZIP 条目中查找元数据文件。
    - 其他校验/解压方法。
- **核心函数**：无模块级函数。
- **关键常量**：`PLUGIN_METADATA_FILENAMES = ("metadata.yaml", "metadata.yml")`、`PLUGIN_METADATA_REQUIRED_FIELDS = ("name", "desc", "version", "author")`。
- **依赖**：`os`、`zipfile`、`yaml`、`astrbot.core.logger`、`astrbot.core.utils.astrbot_path.get_astrbot_plugin_path`、`astrbot.core.utils.io.ensure_dir`/`remove_dir`、`..star.star.StarMetadata`、`..updator.RepoZipUpdator`。

### 12. `star/session_plugin_manager.py`

- **职责**：`SessionPluginManager`——管理会话级别的插件启停状态，基于共享偏好（`sp`）存储每个 UMO 的启用/禁用插件列表。
- **核心类**：
  - `SessionPluginManager`：
    - `is_plugin_enabled_for_session(session_id, plugin_name)`：检查插件在会话中是否启用（默认启用）。
    - `filter_handlers_by_session(event, handlers)`：根据会话配置过滤处理器列表。
- **核心函数**：无模块级函数。
- **关键常量**：无。
- **依赖**：`astrbot.core.logger`/`sp`、`astrbot.core.platform.astr_message_event.AstrMessageEvent`、`astrbot.core.star.star.star_map`。

### 13. `star/session_llm_manager.py`

- **职责**：`SessionServiceManager`——管理会话级别的 LLM/TTS 等服务启停状态。
- **核心类**：
  - `SessionServiceManager`：
    - `is_llm_enabled_for_session(session_id)`：检查 LLM 是否启用（默认启用）。
    - `set_llm_status_for_session(session_id, enabled)`：设置 LLM 启停。
    - `should_process_llm_request(event)`：检查是否应处理 LLM 请求。
- **核心函数**：无模块级函数。
- **关键常量**：无。
- **依赖**：`astrbot.core.logger`/`sp`、`astrbot.core.platform.astr_message_event.AstrMessageEvent`。

### 14. `star/register/__init__.py`

- **职责**：导出所有注册装饰器。
- **核心函数**：无（仅重新导出）。
- **关键常量**：`__all__`（含所有 `register_*` 函数名）。
- **依赖**：`.star.register_star`、`.star_handler.*`。

### 15. `star/register/star.py`

- **职责**：`register_star` 装饰器（已废弃），用于手动注册插件元数据。
- **核心函数**：
  - `register_star(name, author, desc, version, repo)`：装饰器工厂，创建/更新 `StarMetadata`，首次调用时发出 `DeprecationWarning`。
- **关键常量**：`_warned_register_star`（模块级标志，确保只警告一次）。
- **依赖**：`warnings`、`astrbot.core.star.star.StarMetadata`/`star_map`。

### 16. `star/register/star_handler.py`

- **职责**：所有 Handler 注册装饰器的实现，包括指令、指令组、自定义过滤器、事件类型、平台适配器、正则、权限、LLM 工具、Agent 以及各类生命周期 Hook（`on_astrbot_loaded`、`on_llm_request`、`on_agent_begin` 等）。
- **核心类**：
  - `RegisteringCommandable`：指令组级联注册辅助对象，含 `group`/`command`/`custom_filter` 方法。
  - `RegisteringAgent`：Agent 注册辅助对象，含 `llm_tool` 方法。
- **核心函数**：
  - `get_handler_full_name(awaitable)`：`f"{module}_{name}"`。
  - `get_handler_or_create(handler, event_type, dont_add, **kwargs)`：获取或创建 `StarHandlerMetadata`。
  - `register_command(command_name, sub_command, alias, **kwargs)`：注册指令装饰器。
  - `register_command_group(command_group_name, sub_command, alias, **kwargs)`：注册指令组装饰器。
  - `register_custom_filter(custom_type_filter, *args, **kwargs)`：注册自定义过滤器。
  - `register_event_message_type(event_message_type, **kwargs)`。
  - `register_platform_adapter_type(platform_adapter_type, **kwargs)`。
  - `register_regex(regex, **kwargs)`。
  - `register_permission_type(permission_type, raise_error, **kwargs)`。
  - `register_on_astrbot_loaded`/`register_on_platform_loaded`/`register_on_plugin_error`/`register_on_plugin_loaded`/`register_on_plugin_unloaded`/`register_on_waiting_llm_request`/`register_on_llm_request`/`register_on_llm_response`/`register_on_agent_begin`/`register_on_agent_done`/`register_on_using_llm_tool`/`register_on_llm_tool_respond`/`register_on_decorating_result`/`register_after_message_sent`：各类 Hook 装饰器。
  - `register_llm_tool(name, **kwargs)`：注册函数调用工具，解析 docstring 生成参数 schema，支持 Agent 专属工具。
  - `register_agent(name, instruction, tools, run_hooks)`：注册 Agent，创建 `HandoffTool`。
- **关键常量**：无。
- **依赖**：`re`、`collections.abc`、`typing`、`docstring_parser`、`astrbot.core.logger`、`astrbot.core.agent.*`（`Agent`、`HandoffTool`、`BaseAgentRunHooks`、`FunctionTool`）、`astrbot.core.message.message_event_result.MessageEventResult`、`astrbot.core.provider.func_tool_manager.PY_TO_JSON_TYPE`/`SUPPORTED_TYPES`、`astrbot.core.provider.register.llm_tools`、`..filter.*`、`..star_handler.EventType`/`StarHandlerMetadata`/`star_handlers_registry`。

### 17. `star/filter/__init__.py`

- **职责**：定义过滤器抽象基类 `HandlerFilter`，导出相关类型。
- **核心类**：
  - `HandlerFilter(abc.ABC)`：`filter(event, cfg) -> bool`。
- **核心函数**：无。
- **关键常量**：`__all__`。
- **依赖**：`abc`、`astrbot.core.config.AstrBotConfig`、`astrbot.core.platform.astr_message_event.AstrMessageEvent`、`astrbot.core.platform.message_type.MessageType`。

### 18. `star/filter/command.py`

- **职责**：`CommandFilter`——标准指令过滤器，解析指令名/别名、匹配消息前缀、验证并转换参数类型（支持 `GreedyStr` 贪婪匹配、Optional/Union 类型、bool/int/float 转换）。
- **核心类**：
  - `GreedyStr(str)`：标记贪婪文本参数。
  - `CommandFilter(HandlerFilter)`：
    - `__init__(command_name, alias, handler_md, parent_command_names)`。
    - `init_handler_md(handle_md)`：通过 `inspect.signature` 解析 handler 参数（跳过 `self`/`event`）。
    - `get_complete_command_names()`：生成 `parent + command` 全名列表（含别名），带缓存。
    - `validate_and_convert_params(params, param_type)`：参数类型转换，支持 GreedyStr、默认值、Union/Optional。
    - `filter(event, cfg)`：匹配指令前缀，解析参数，设置 `event.set_extra("parsed_params", params)`。
- **核心函数**：
  - `unwrap_optional(annotation)`：去掉 `Optional[T]`/`Union[T, None]`/`T|None`。
- **关键常量**：无。
- **依赖**：`inspect`、`re`、`types`、`typing`、`astrbot.core.config.AstrBotConfig`、`astrbot.core.platform.astr_message_event.AstrMessageEvent`、`..star_handler.StarHandlerMetadata`、`.custom_filter.CustomFilter`。

### 19. `star/filter/command_group.py`

- **职责**：`CommandGroupFilter`——指令组过滤器，管理子指令/子指令组的树形结构，支持指令树打印、自定义过滤器。
- **核心类**：
  - `CommandGroupFilter(HandlerFilter)`：
    - `__init__(group_name, alias, parent_group)`。
    - `add_sub_command_filter(sub_command_filter)`、`add_custom_filter(custom_filter)`。
    - `get_complete_command_names()`：递归拼接父级指令名。
    - `print_cmd_tree(sub_command_filters, prefix, event, cfg)`：树形打印指令帮助。
    - `custom_filter_ok(event, cfg)`、`startswith(message_str)`、`equals(message_str)`。
    - `filter(event, cfg)`：匹配指令组前缀，仅匹配时抛出参数不足错误（打印子指令树）。
- **核心函数**：无。
- **关键常量**：无。
- **依赖**：`__future__.annotations`、`astrbot.core.config.AstrBotConfig`、`astrbot.core.platform.astr_message_event.AstrMessageEvent`、`.`/`.command`/`.custom_filter`。

### 20. `star/filter/regex.py`

- **职责**：`RegexFilter`——正则表达式过滤器，不受 `wake_prefix` 制约。
- **核心类**：
  - `RegexFilter(HandlerFilter)`：`__init__(regex)` 编译正则，`filter` 使用 `regex.search`。
- **核心函数**：无。
- **关键常量**：无。
- **依赖**：`re`、`astrbot.core.config.AstrBotConfig`、`astrbot.core.platform.astr_message_event.AstrMessageEvent`、`.`。

### 21. `star/filter/permission.py`

- **职责**：`PermissionTypeFilter`——权限过滤器，支持 `ADMIN`/`MEMBER` 权限校验。
- **核心类**：
  - `PermissionType(enum.Flag)`：`ADMIN`、`MEMBER`。
  - `PermissionTypeFilter(HandlerFilter)`：`filter` 检查 `event.is_admin()`（ADMIN 权限时）。
- **核心函数**：无。
- **关键常量**：无。
- **依赖**：`enum`、`astrbot.core.config.AstrBotConfig`、`astrbot.core.platform.astr_message_event.AstrMessageEvent`、`.`。

### 22. `star/filter/event_message_type.py`

- **职责**：`EventMessageTypeFilter`——消息类型过滤器（群消息/私聊消息/其他）。
- **核心类**：
  - `EventMessageType(enum.Flag)`：`GROUP_MESSAGE`、`PRIVATE_MESSAGE`、`OTHER_MESSAGE`、`ALL`。
  - `EventMessageTypeFilter(HandlerFilter)`：`filter` 通过位运算检查消息类型。
- **核心函数**：无。
- **关键常量**：`MESSAGE_TYPE_2_EVENT_MESSAGE_TYPE`（`MessageType` → `EventMessageType` 映射）。
- **依赖**：`enum`、`astrbot.core.config.AstrBotConfig`、`astrbot.core.platform.astr_message_event.AstrMessageEvent`、`astrbot.core.platform.message_type.MessageType`、`.`。

### 23. `star/filter/platform_adapter_type.py`

- **职责**：`PlatformAdapterTypeFilter`——平台适配器类型过滤器，限制 Handler 仅在特定平台生效。
- **核心类**：
  - `PlatformAdapterType(enum.Flag)`：所有支持平台（AIOCQHTTP、QQOFFICIAL、TELEGRAM、WECOM、LARK、DINGTALK、DISCORD、SLACK、KOOK、VOCECHAT、WEIXIN_OFFICIAL_ACCOUNT、SATORI、MISSKEY、LINE、MATRIX、WEIXIN_OC、MATTERMOST、WEBCHAT、ALL）。
  - `PlatformAdapterTypeFilter(HandlerFilter)`：支持字符串或枚举构造，`filter` 通过位运算检查平台。
- **核心函数**：无。
- **关键常量**：`ADAPTER_NAME_2_TYPE`（平台 ID 字符串 → `PlatformAdapterType` 映射）。
- **依赖**：`enum`、`astrbot.core.config.AstrBotConfig`、`astrbot.core.platform.astr_message_event.AstrMessageEvent`、`.`。

### 24. `star/filter/custom_filter.py`

- **职责**：自定义过滤器体系，支持 `&`（AND）和 `|`（OR）组合运算，通过元类 `CustomFilterMeta` 实现类级别的 `&`/`|` 运算符重载。
- **核心类**：
  - `CustomFilterMeta(ABCMeta)`：实现 `__and__`/`__or__` 类方法。
  - `CustomFilter(HandlerFilter, metaclass=CustomFilterMeta)`：抽象基类，`__init__(raise_error, **kwargs)`，实例级 `__or__`/`__and__`。
  - `CustomFilterOr(CustomFilter)`：OR 组合，`filter` 返回 `f1 or f2`。
  - `CustomFilterAnd(CustomFilter)`：AND 组合，`filter` 返回 `f1 and f2`。
- **核心函数**：无。
- **关键常量**：无。
- **依赖**：`abc`、`astrbot.core.config.AstrBotConfig`、`astrbot.core.platform.astr_message_event.AstrMessageEvent`、`.`。

---

## 五、knowledge_base 模块（知识库）

`knowledge_base 模块是 AstrBot 的 RAG（检索增强生成）子系统，包含知识库管理器、文档上传/处理助手、SQLite 元数据库、向量数据库集成、文档解析器（PDF/EPUB/Markdown/TXT/URL）、文本分块器（固定大小/递归字符/Markdown 感知）以及混合检索器（稠密 + 稀疏 BM25 + RRF 融合 + Rerank）。

### 1. `knowledge_base/kb_mgr.py`

- **职责**：`KnowledgeBaseManager`——知识库管理器，协调元数据库、检索管理器与多个 `KBHelper` 实例，提供知识库 CRUD、文档检索、URL 上传等统一接口。
- **核心类**：
  - `KnowledgeBaseManager`：
    - `__init__(provider_manager)`：初始化 `kb_insts: dict[str, KBHelper]`。
    - `initialize()`：初始化元数据库、检索管理器（`SparseRetriever` + `RankFusion` + `RetrievalManager`），加载所有知识库。
    - `_init_kb_database()`：创建 `KBSQLiteDatabase`，初始化并执行 v1 迁移。
    - `load_kbs()`：从数据库加载所有知识库记录，为每个创建 `KBHelper` 并初始化（失败时记录 `init_error`）。
    - `create_kb(kb_name, description, emoji, embedding_provider_id, ...)`：创建知识库（名称唯一性检查、`IntegrityError` 处理）。
    - `get_kb(kb_id)`/`get_kb_by_name(kb_name)`：获取实例。
    - `delete_kb(kb_id)`：删除知识库及向量数据库文件。
    - `list_kbs()`：列出所有知识库。
    - `update_kb(kb_id, ...)`：更新知识库配置（失败回滚到旧配置，成功时切换到新 helper 并终止旧 helper）。
    - `retrieve(query, kb_names, top_k_fusion, top_m_final)`：跨知识库混合检索，格式化上下文文本。
    - `_format_context(results)`：格式化检索结果为 LLM 上下文。
    - `terminate()`：终止所有知识库实例并关闭元数据库。
    - `upload_from_url(kb_id, url, ...)`：从 URL 上传文档。
- **核心函数**：无模块级函数。
- **关键常量**：`FILES_PATH`、`DB_PATH`、`CHUNKER = RecursiveCharacterChunker()`。
- **依赖**：`pathlib.Path`、`sqlalchemy.exc.IntegrityError`、`astrbot.core.logger`、`astrbot.core.provider.manager.ProviderManager`、`astrbot.core.utils.astrbot_path.get_astrbot_knowledge_base_path`、`.chunking.recursive.RecursiveCharacterChunker`、`.kb_db_sqlite.KBSQLiteDatabase`、`.kb_helper.KBHelper`、`.models.KBDocument`/`KnowledgeBase`、`.retrieval.manager.RetrievalManager`/`RetrievalResult`、`.retrieval.rank_fusion.RankFusion`、`.retrieval.sparse_retriever.SparseRetriever`。

### 2. `knowledge_base/kb_helper.py`

- **职责**：`KBHelper`——单个知识库的处理助手，负责向量数据库初始化、文档上传（解析→分块→向量化→存储→元数据提交→统计刷新）、文档/块管理、URL 上传、失败补偿清理；另有 `RateLimiter` 速率限制器和 LLM 文本修复函数。
- **核心类**：
  - `RateLimiter`：基于 `max_rpm` 的异步速率限制器（`__aenter__`/`__aexit__`）。
  - `KBHelper`：
    - `__init__(kb_db, kb, provider_manager, kb_root_dir, chunker)`：初始化目录（`kb_dir`、`kb_medias_dir`、`kb_files_dir`）。
    - `initialize()`/`get_ep()`/`get_rp()`：获取 Embedding/Rerank Provider。
    - `_ensure_vec_db()`：创建 `FaissVecDB` 并初始化。
    - `delete_vec_db()`/`terminate()`：清理资源。
    - `upload_document(file_name, file_content, file_type, chunk_size, chunk_overlap, batch_size, tasks_limit, max_retries, progress_callback, pre_chunked_text)`：核心上传流程，含补偿清理（`_cleanup_failed_upload`）、`KnowledgeBaseUploadError` 分阶段错误包装。
    - `_cleanup_failed_upload(doc_id, media_paths)`：多存储写入失败后的最佳努力回滚（先删向量/文档块，再删元数据，最后删媒体文件）。
    - `list_documents(offset, limit, search)`/`count_documents(search)`/`get_document(doc_id)`/`delete_document(doc_id)`/`delete_chunk(chunk_id, doc_id)`：文档/块管理。
    - `refresh_kb()`/`refresh_document(doc_id)`：刷新统计数据。
    - `get_chunks_by_doc_id(doc_id, offset, limit)`/`get_chunk_count_by_doc_id(doc_id)`：块查询。
    - `_save_media(doc_id, media_type, file_name, content, mime_type)`：保存媒体文件。
    - `upload_from_url(url, ...)`：URL 上传（Tavily 提取→可选清洗→复用 `upload_document`）。
- **核心函数**：
  - `_repair_and_translate_chunk_with_retry(chunk, repair_llm_service, rate_limiter, max_retries)`：使用 LLM 修复/翻译文本块，解析 `<repaired_text>`/`<discard_chunk />` 标签。
  - `_compact_chunks(chunks)`：去除空白块。
- **关键常量**：无。
- **依赖**：`asyncio`、`json`、`re`、`time`、`uuid`、`pathlib.Path`、`typing.TYPE_CHECKING`、`aiofiles`、`astrbot.core.logger`、`astrbot.core.db.vec_db.base.BaseVecDB`、`astrbot.core.exceptions.KnowledgeBaseUploadError`、`astrbot.core.provider.manager.ProviderManager`、`astrbot.core.provider.provider.EmbeddingProvider`/`RerankProvider`/`Provider`、`.chunking.base.BaseChunker`/`.markdown.MarkdownChunker`/`.recursive.RecursiveCharacterChunker`、`.kb_db_sqlite.KBSQLiteDatabase`、`.models.KBDocument`/`KBMedia`/`KnowledgeBase`、`.parsers.url_parser.extract_text_from_url`、`.parsers.util.select_parser`、`.prompts.TEXT_REPAIR_SYSTEM_PROMPT`。

### 3. `knowledge_base/kb_db_sqlite.py`

- **职责**：`KBSQLiteDatabase`——知识库元数据库（SQLite + SQLAlchemy 异步），管理知识库、文档、多媒体的 CRUD 与统计。
- **核心类**：
  - `KBSQLiteDatabase`：
    - `__init__(db_path)`：创建异步引擎与会话工厂。
    - `get_db()`：异步上下文管理器。
    - `initialize()`：建表 + SQLite 性能参数（WAL、synchronous=NORMAL、cache_size、temp_store=MEMORY、mmap_size、optimize）。
    - `migrate_to_v1()`：创建知识库/文档/多媒体表的索引。
    - `close()`。
    - 知识库查询：`get_kb_by_id`、`get_kb_by_name`、`list_kbs`、`count_kbs`。
    - 文档查询：`get_document_by_id`、`list_documents_by_kb(kb_id, offset, limit, search)`、`count_documents_by_kb(kb_id, search)`、`get_document_with_metadata(doc_id)`、`get_documents_with_metadata_batch(doc_ids)`（分片查询避免 SQLite 999 参数上限）。
    - 文档删除：`delete_document_by_id(doc_id, vec_db)`（删除多媒体记录、文档记录、向量）。
    - 多媒体查询：`list_media_by_doc(doc_id)`、`get_media_by_id(media_id)`。
    - `update_kb_stats(kb_id, vec_db)`：更新知识库统计（`doc_count` 子查询 + `chunk_count` 从向量库获取）。
- **核心函数**：无模块级函数。
- **关键常量**：无。
- **依赖**：`contextlib.asynccontextmanager`、`pathlib.Path`、`typing.TYPE_CHECKING`、`sqlalchemy`（`delete`、`func`、`select`、`text`、`update`）、`sqlalchemy.ext.asyncio`（`AsyncSession`、`async_sessionmaker`、`create_async_engine`）、`sqlmodel`（`col`、`desc`）、`astrbot.core.logger`、`astrbot.core.knowledge_base.models.*`、`astrbot.core.utils.astrbot_path.get_astrbot_knowledge_base_path`。

### 4. `knowledge_base/models.py`

- **职责**：定义知识库元数据的 ORM 模型（`KnowledgeBase`、`KBDocument`、`KBMedia`）。
- **核心类**：
  - `BaseKBModel(SQLModel, table=False)`：共享 `MetaData`。
  - `KnowledgeBase`（表 `knowledge_bases`）：`id`、`kb_id`（UUID）、`kb_name`（唯一）、`description`、`emoji`、`embedding_provider_id`、`rerank_provider_id`、`chunk_size`、`chunk_overlap`、`top_k_dense`、`top_k_sparse`、`top_m_final`、`created_at`、`updated_at`、`doc_count`、`chunk_count`。
  - `KBDocument`（表 `kb_documents`）：`id`、`doc_id`（UUID）、`kb_id`、`doc_name`、`file_type`、`file_size`、`file_path`、`chunk_count`、`media_count`、`created_at`、`updated_at`。
  - `KBMedia`（表 `kb_media`）：`id`、`media_id`（UUID）、`doc_id`、`kb_id`、`media_type`、`file_name`、`file_path`、`file_size`、`mime_type`、`created_at`。
- **核心函数**：无。
- **关键常量**：各表 `__tablename__`。
- **依赖**：`uuid`、`datetime`、`sqlmodel`（`Field`、`MetaData`、`SQLModel`、`Text`、`UniqueConstraint`）。

### 5. `knowledge_base/prompts.py`

- **职责**：定义文本修复 LLM 的系统提示词。
- **核心函数**：无。
- **关键常量**：`TEXT_REPAIR_SYSTEM_PROMPT`（指导 LLM 作为"数字档案管理员"，从噪声文本中提取信号、修复文本、支持多主题分割，输出 `<repaired_text>` 或 `<discard_chunk />` 标签，**不翻译**保持原文语言）。
- **依赖**：无。

### 6. `knowledge_base/parsers/__init__.py`

- **职责**：导出解析器类 `BaseParser`、`EpubParser`、`PDFParser`、`TextParser`、`MediaItem`、`ParseResult`。
- **核心类**：无（重新导出）。
- **关键常量**：`__all__`。
- **依赖**：`.base.*`、`.epub_parser.EpubParser`、`.pdf_parser.PDFParser`、`.text_parser.TextParser`。

### 7. `knowledge_base/parsers/base.py`

- **职责**：定义文档解析器抽象基类 `BaseParser` 及数据类 `MediaItem`、`ParseResult`。
- **核心类**：
  - `MediaItem`（dataclass）：`media_type`、`file_name`、`content: bytes`、`mime_type`。
  - `ParseResult`（dataclass）：`text: str`、`media: list[MediaItem]`。
  - `BaseParser(ABC)`：抽象方法 `parse(file_content, file_name) -> ParseResult`。
- **核心函数**：无。
- **关键常量**：无。
- **依赖**：`abc`、`dataclasses`。

### 8. `knowledge_base/parsers/util.py`

- **职责**：解析器选择工具函数。
- **核心函数**：
  - `select_parser(ext)`：按扩展名返回对应解析器（`.md`/`.txt`/`.xlsx`/`.docx` 等 → `MarkitdownParser`；`.epub` → `EpubParser`；`.pdf` → `PDFParser`）。
- **关键常量**：无。
- **依赖**：`.base.BaseParser`、各具体解析器（懒导入）。

### 9. `knowledge_base/parsers/text_parser.py`

- **职责**：`TextParser`——TXT/MD 文本解析器，支持多种编码自动检测。
- **核心类**：
  - `TextParser(BaseParser)`：`parse` 依次尝试 `utf-8`/`gbk`/`gb2312`/`gb18030` 解码，无多媒体。
- **核心函数**：无。
- **关键常量**：无。
- **依赖**：`astrbot.core.knowledge_base.parsers.base.BaseParser`/`ParseResult`。

### 10. `knowledge_base/parsers/pdf_parser.py`

- **职责**：`PDFParser`——PDF 文档解析器，提取文本和嵌入图片。
- **核心类**：
  - `PDFParser(BaseParser)`：`parse` 使用 `pypdf.PdfReader`，逐页提取文本，从 `/Resources`/`/XObject` 提取图片（支持 `/DCTDecode`→jpg、`/FlateDecode`→png），单页/单图失败不影响整体。
- **核心函数**：无。
- **关键常量**：无。
- **依赖**：`io`、`pypdf.PdfReader`、`astrbot.core.knowledge_base.parsers.base.*`。

### 11. `knowledge_base/parsers/markitdown_parser.py`

- **职责**：`MarkitdownParser`——使用 `markitdown_no_magika` 解析 docx/xls/xlsx/md 等格式，转换为 Markdown 文本。
- **核心类**：
  - `MarkitdownParser(BaseParser)`：`parse` 使用 `MarkItDown(enable_plugins=False)` 转换 `BytesIO`，返回 Markdown 文本（无多媒体）。
- **核心函数**：无。
- **关键常量**：无。
- **依赖**：`io`、`os`、`markitdown_no_magika.MarkItDown`/`StreamInfo`、`astrbot.core.knowledge_base.parsers.base.*`。

### 12. `knowledge_base/parsers/epub_parser.py`

- **职责**：`EpubParser`——EPUB 文档解析器，在 `MarkitdownParser` 基础上进行深度清洗（去除元数据头、目录、脚注链接、噪声行、重复行、空图片链接）。
- **核心类**：
  - `EpubParser(BaseParser)`：`parse` 调用 `MarkitdownParser`，再通过 `_strip_head`→`_strip_links`→`_sanitize` 清洗。
- **核心函数**：
  - `_n(s)`：HTML 反转义与空白规范化。
  - `_is_internal(href)`：判断内部链接。
  - `_is_toc_line(s)`：判断目录行。
  - `_strip_head(text)`：去除元数据头和目录。
  - `_strip_links(text)`：清理内部链接（保留标签文本，删除脚注）。
  - `_img_alt(m)`：处理图片 alt 文本（去除通用/文件名 alt）。
  - `_sanitize(text)`：去除噪声行、分隔线、重复行，压缩空行。
- **关键常量**：大量正则常量（`_KEYS`、`_META_RE`、`_TOC_HEAD_RE`、`_LINK_RE`、`_IMG_RE`、`_EMPTY_IMG_LINK_RE`、`_FOOTNOTE_LABEL_RE`、`_FOOTNOTE_HREF_RE`、`_DOTTED_TOC_RE`、`_SEP_RE`、`_NOISE_RE`、`_GENERIC_ALT_RE`、`_FILENAME_ALT_RE`）。
- **依赖**：`html`、`re`、`astrbot.core.knowledge_base.parsers.base.BaseParser`/`ParseResult`、`.markitdown_parser.MarkitdownParser`。

### 13. `knowledge_base/parsers/url_parser.py`

- **职责**：URL 内容提取器，通过 Tavily API 从网页提取主要文本，支持 API 密钥轮换。
- **核心类**：
  - `URLExtractor`：
    - `__init__(tavily_keys)`：初始化密钥列表与轮换锁。
    - `_get_tavily_key()`：并发安全的密钥轮换。
    - `extract_text_from_url(url)`：调用 Tavily `/extract` API，返回 `raw_content`。
- **核心函数**：
  - `extract_text_from_url(url, tavily_keys)`：向后兼容的函数接口。
- **关键常量**：无。
- **依赖**：`asyncio`、`aiohttp`。

### 14. `knowledge_base/chunking/__init__.py`

- **职责**：导出分块器类 `BaseChunker`、`FixedSizeChunker`、`MarkdownChunker`。
- **核心类**：无（重新导出）。
- **关键常量**：`__all__`。
- **依赖**：`.base.BaseChunker`、`.fixed_size.FixedSizeChunker`、`.markdown.MarkdownChunker`。

### 15. `knowledge_base/chunking/base.py`

- **职责**：`BaseChunker`——分块器抽象基类。
- **核心类**：
  - `BaseChunker(ABC)`：抽象方法 `chunk(text, **kwargs) -> list[str]`。
- **核心函数**：无。
- **关键常量**：无。
- **依赖**：`abc`。

### 16. `knowledge_base/chunking/fixed_size.py`

- **职责**：`FixedSizeChunker`——固定大小分块器，按字符数滑动窗口分块，支持重叠。
- **核心类**：
  - `FixedSizeChunker(BaseChunker)`：
    - `__init__(chunk_size=512, chunk_overlap=50)`。
    - `chunk(text, **kwargs)`：滑动窗口，防止 `chunk_overlap >= chunk_size` 时的无限循环。
- **核心函数**：无。
- **关键常量**：无。
- **依赖**：`.base.BaseChunker`。

### 17. `knowledge_base/chunking/recursive.py`

- **职责**：`RecursiveCharacterChunker`——递归字符分块器，按分隔符优先级（段落→换行→中文句号→中文逗号→英文句号→逗号→空格→字符）递归分割，支持重叠。
- **核心类**：
  - `RecursiveCharacterChunker(BaseChunker)`：
    - `__init__(chunk_size=500, chunk_overlap=100, length_function=len, is_separator_regex=False, separators=None)`：默认分隔符列表。
    - `chunk(text, **kwargs)`：递归分割，超长片段递归处理，累积合并 + 重叠处理。
    - `_split_by_character(text, chunk_size, overlap)`：字符级分割（最后兜底）。
- **核心函数**：无。
- **关键常量**：默认 `separators` 列表。
- **依赖**：`collections.abc.Callable`、`.base.BaseChunker`。

### 18. `knowledge_base/chunking/markdown.py`

- **职责**：`MarkdownChunker`——Markdown 感知分块器，按标题层级切分文档，保持章节语义完整性，超长章节内部递归分割，支持标题上下文前缀、纯标题节合并、短块合并。
- **核心类**：
  - `_Section`（dataclass）：`heading_path: list[str]`、`text: str`、`has_body: bool`。
  - `MarkdownChunker(BaseChunker)`：
    - `__init__(chunk_size=1024, chunk_overlap=50, include_heading_context=True, max_heading_depth=4, min_chunk_size=0, continuation_prefix="...")`：创建 `_fallback_chunker = RecursiveCharacterChunker`。
    - `chunk(text, **kwargs)`：解析章节→转 chunk→合并纯标题节→合并短块。
    - `_estimate_prefix_length(heading_path)`：估算标题前缀长度。
    - `_sections_to_chunks(sections, chunk_size, chunk_overlap)`：章节转 chunk，超长章节递归分割（扣除前缀长度）。
    - `_build_context_prefix(heading_path)`/`_apply_heading_context(heading_path, content, is_continuation)`：标题上下文前缀构建。
    - `_merge_heading_only_chunks(raw_chunks, chunk_size)`：合并纯标题节到下一个有正文的 chunk。
    - `_merge_short_chunks(chunks, chunk_size)`：合并低于 `min_chunk_size` 的相邻 chunk。
    - `_parse_sections(text)`：解析 Markdown 标题层级（跳过围栏代码块），维护标题栈。
    - `_find_fenced_code_ranges(text)`：标记围栏代码块范围。
    - `_is_in_fenced_block(pos, ranges)`：判断位置是否在代码块内。
- **核心函数**：无模块级函数。
- **关键常量**：无。
- **依赖**：`re`、`dataclasses`、`.base.BaseChunker`、`.recursive.RecursiveCharacterChunker`。

### 19. `knowledge_base/retrieval/__init__.py`

- **职责**：检索模块包初始化，通过 `__getattr__` 懒加载 `RetrievalManager`、`RetrievalResult`、`FusedResult`、`RankFusion`、`SparseResult`、`SparseRetriever`。
- **核心类**：无。
- **核心函数**：`__getattr__(name)`。
- **关键常量**：`__all__`。
- **依赖**：`.manager`/`.rank_fusion`/`.sparse_retriever`（懒加载）。

### 20. `knowledge_base/retrieval/manager.py`

- **职责**：`RetrievalManager`——检索管理器，协调稠密检索、稀疏检索、RRF 融合、Rerank 重排序的完整混合检索流程。
- **核心类**：
  - `RetrievalResult`（dataclass）：`chunk_id`、`doc_id`、`doc_name`、`kb_id`、`kb_name`、`content`、`score`、`metadata`。
  - `RetrievalManager`：
    - `__init__(sparse_retriever, rank_fusion, kb_db)`。
    - `retrieve(query, kb_ids, kb_id_helper_map, top_k_fusion, top_m_final)`：混合检索流程（1.稠密→2.稀疏→3.RRF融合→4.元数据批量获取→5.Rerank），含各阶段耗时日志。
    - `_dense_retrieve(query, kb_ids, kb_options)`：为每个知识库独立稠密检索，按相似度排序合并。
    - `_rerank(query, results, top_k, rerank_provider)`：调用 Rerank Provider 重排序。
- **核心函数**：无模块级函数。
- **关键常量**：无。
- **依赖**：`time`、`dataclasses`、`typing.TYPE_CHECKING`、`astrbot.logger`、`astrbot.core.db.vec_db.base.Result`、`astrbot.core.knowledge_base.kb_db_sqlite.KBSQLiteDatabase`、`astrbot.core.knowledge_base.retrieval.rank_fusion.RankFusion`、`astrbot.core.knowledge_base.retrieval.sparse_retriever.SparseRetriever`、`astrbot.core.provider.provider.RerankProvider`、`..kb_helper.KBHelper`。

### 21. `knowledge_base/retrieval/sparse_retriever.py`

- **职责**：`SparseRetriever`——BM25 稀疏检索器，优先使用 FTS5 稀疏检索，失败时回退到内存 BM25。
- **核心类**：
  - `SparseResult`（dataclass）：`chunk_index`、`chunk_id`、`doc_id`、`kb_id`、`content`、`score`。
  - `SparseRetriever`：
    - `__init__(kb_db)`：初始化 BM25 索引缓存与停用词。
    - `retrieve(query, kb_ids, kb_options)`：FTS5 优先检索，失败 KB 回退 `_retrieve_with_bm25`。
    - `_retrieve_with_bm25(query, kb_ids, kb_options)`：内存 BM25 检索（加载全量文档→分词→建索引→检索）。
- **核心函数**：无模块级函数。
- **关键常量**：无。
- **依赖**：`json`、`os`、`dataclasses`、`typing.TYPE_CHECKING`、`rank_bm25.BM25Okapi`、`astrbot.core.knowledge_base.kb_db_sqlite.KBSQLiteDatabase`、`astrbot.core.knowledge_base.retrieval.tokenizer.load_stopwords`/`tokenize_text`。

### 22. `knowledge_base/retrieval/rank_fusion.py`

- **职责**：`RankFusion`——检索结果融合器，使用 Reciprocal Rank Fusion (RRF) 算法融合稠密与稀疏检索结果。
- **核心类**：
  - `FusedResult`（dataclass）：`chunk_id`、`chunk_index`、`doc_id`、`kb_id`、`content`、`score`。
  - `RankFusion`：
    - `__init__(kb_db, k=60)`：`k` 为 RRF 平滑参数。
    - `fuse(dense_results, sparse_results, top_k)`：RRF 公式 `score(doc) = sum(1/(k+rank_i))`，统一 chunk_id（稠密结果需从 metadata JSON 提取），优先从稀疏结果获取完整信息。
- **核心函数**：无模块级函数。
- **关键常量**：无。
- **依赖**：`json`、`dataclasses`、`astrbot.core.db.vec_db.base.Result`、`astrbot.core.knowledge_base.kb_db_sqlite.KBSQLiteDatabase`、`astrbot.core.knowledge_base.retrieval.sparse_retriever.SparseResult`。

### 23. `knowledge_base/retrieval/tokenizer.py`

- **职责**：分词工具函数，使用 jieba 分词 + 停用词过滤，提供 FTS5 查询构建辅助。
- **核心函数**：
  - `load_stopwords(path)`：从文件加载停用词集合。
  - `tokenize_text(text, stopwords)`：jieba 分词 + 停用词/非词字符过滤。
  - `to_fts5_search_text(text, stopwords)`：将文本转为 FTS5 索引用的空格分隔 token 串。
  - `quote_fts5_token(token)`：FTS5 token 转义（双引号转义）。
  - `build_fts5_or_query(tokens)`：构建 FTS5 OR 查询字符串。
- **关键常量**：`_TERM_PATTERN`（匹配词字符的正则）。
- **依赖**：`re`、`pathlib.Path`、`re.Pattern`、`jieba`。

---

## 附：模块间依赖关系总结

```
knowledge_base
  ├── kb_mgr ──→ kb_helper, kb_db_sqlite, retrieval.manager/rank_fusion/sparse_retriever, chunking.recursive, models
  ├── kb_helper ──→ db.vec_db.faiss_impl.vec_db(FaissVecDB), parsers.*, chunking.*, prompts, models, kb_db_sqlite
  ├── retrieval ──→ db.vec_db.base(Result), kb_db_sqlite, sparse_retriever, rank_fusion, tokenizer(jieba)
  ├── parsers ──→ base, util(select_parser), pdf_parser(pypdf), markitdown_parser, epub_parser, text_parser, url_parser(aiohttp/Tavily)
  └── chunking ──→ base, fixed_size, recursive, markdown(→recursive)

db
  ├── __init__(BaseDatabase) ──→ po, sentinels
  ├── sqlite(SQLiteDatabase) ──→ BaseDatabase, po
  ├── vec_db/base(BaseVecDB, Result)
  └── vec_db/faiss_impl ──→ vec_db.base, document_storage(SQLite+FTS5), embedding_storage(FAISS), vec_db(FaissVecDB)

config
  ├── __init__ ──→ astrbot_config, default
  ├── astrbot_config(AstrBotConfig) ──→ default(DEFAULT_CONFIG/DEFAULT_VALUE_MAP), utils.auth_password
  ├── default ──→ utils.astrbot_path
  └── i18n_utils(ConfigMetadataI18n)

message
  ├── components ──→ pydantic, utils.media_utils, file_token_service, astrbot_config
  └── message_event_result ──→ components

star
  ├── base(Star) ──→ star(StarMetadata/star_map), utils.command_parser/plugin_kv_store, html_renderer
  ├── star(StarMetadata) ──→ config.AstrBotConfig
  ├── star_handler(StarHandlerRegistry/EventType/StarHandlerMetadata) ──→ filter, star.star_map
  ├── context(Context) ──→ 几乎所有 core 管理器（db/provider/platform/conversation/persona/knowledge_base/cron/subagent）
  ├── star_manager(PluginManager) ──→ context, star/star_handler, updator, command_management, config.default(VERSION)
  ├── register/star_handler ──→ star_handler, filter.*(所有过滤器), agent.*, provider.func_tool_manager/register
  └── filter/* ──→ filter/__init__(HandlerFilter), platform.astr_message_event, config.AstrBotConfig
```

**关键设计要点**：

1. **双数据库架构**：关系型主库（`SQLiteDatabase`，会话/人格/统计）与向量库（`FaissVecDB`，知识库文档块）分离，知识库另有独立的元数据库（`KBSQLiteDatabase`）。
2. **异步优先**：所有数据库操作均使用 `sqlalchemy.ext.asyncio` + `aiosqlite`。
3. **补偿性事务**：跨存储写入（文档块/向量/元数据）无法共享事务，通过 `_rollback_partial_insert`、`_cleanup_failed_upload` 等方法实现最佳努力回滚。
4. **混合检索**：稠密（FAISS L2）+ 稀疏（FTS5 BM25，回退内存 BM25）+ RRF 融合 + Rerank 四阶段流水线。
5. **插件自动注册**：通过 `__init_subclass__` 自动识别 `Star` 子类，装饰器声明式注册 Handler 与过滤器。
6. **配置原子化持久化**：`AstrBotConfig` 使用临时文件 + `os.replace` + revision 版本控制实现并发安全的原子写入。


---

## 章节三：core/pipeline（处理管道）

# AstrBot core/pipeline 模块逐文件详解

本文档对 `astrbot/core/pipeline` 模块下全部 **25 个 `.py` 文件** 进行逐文件、逐类、逐方法的详尽分析。分析范围覆盖：顶层模块（7 个）、各类检查 stage（4 个）、内容安全检查子包（5 个）、预处理/结果装饰/响应 stage（3 个）、以及核心的 process_stage 子包（6 个）。分析仅依据实际读到的源码内容，不杜撰任何 API 或字段。

整体架构上，pipeline 采用 **洋葱模型**：`PipelineScheduler` 按 `STAGES_ORDER` 顺序调度各个 `Stage` 实例；每个 Stage 的 `process()` 既可以是普通协程，也可以是异步生成器。若是异步生成器，则在每次 `yield` 处暂停并递归执行后续阶段，待后续阶段全部完成后再恢复执行后置逻辑——这正是洋葱模型"前/后置处理"的核心。Stage 通过 `@register_stage` 装饰器注册到全局 `registered_stages` 列表；`bootstrap.ensure_builtin_stages_registered()` 负责在调度器初始化时按需导入各内置 stage 模块。

---

## 顶层模块（pipeline/）

### `pipeline/__init__.py`
- **职责**: pipeline 包的对外导出门面。刻意**避免在 import 时急切导入所有 stage 子模块**（防止循环导入），转而通过 **懒加载属性解析** (`__getattr__`) 在首次访问某个 stage 类时才动态 `import_module`，以保持向后兼容。
- **核心类**: 无。
- **核心函数**:
  - `__getattr__(name: str) -> Any` — 模块级 PEP 562 懒加载钩子。当访问的 `name` 不在 `_LAZY_EXPORTS` 中时抛 `AttributeError`；否则从 `_LAZY_EXPORTS[name]` 取出 `(module_path, attr_name)`，`import_module` 后 `getattr` 得到目标对象，并将其缓存回 `globals()[name]` 后返回。
  - `__dir__() -> list[str]` — 返回 `globals()` 与 `__all__` 的并集排序结果，便于 `dir()` 与 IDE 自动补全。
- **关键常量**:
  - `_LAZY_EXPORTS: dict[str, tuple[str, str]]` — 懒加载映射表，键为类名（如 `"ContentSafetyCheckStage"`、`"PreProcessStage"`、`"ProcessStage"`、`"RateLimitStage"`、`"RespondStage"`、`"ResultDecorateStage"`、`"SessionStatusCheckStage"`、`"WakingCheckStage"`、`"WhitelistCheckStage"`），值为 `(模块完整路径, 属性名)` 二元组。
  - `__all__` — 导出列表，包含上述 9 个 Stage 类名，加上 `STAGES_ORDER`、`EventResultType`、`MessageEventResult`。
- **依赖**:
  - 标准库：`importlib.import_module`、`typing`（`TYPE_CHECKING`、`Any`）、`from __future__ import annotations`。
  - astrbot 内部：`astrbot.core.message.message_event_result`（`EventResultType`、`MessageEventResult`）。
  - 相对导入：`.stage_order.STAGES_ORDER`。`TYPE_CHECKING` 块下对 9 个 stage 子模块的导入仅用于静态分析。

### `pipeline/bootstrap.py`
- **职责**: 提供"确保所有内置 pipeline stage 已被导入并注册到 `registered_stages`"的引导工具。通过幂等标志位 `_builtin_stages_registered` 避免重复导入。
- **核心类**: 无。
- **核心函数**:
  - `ensure_builtin_stages_registered() -> None` — 幂等函数。若 `_builtin_stages_registered` 已为 True 直接返回；否则先用集合推导检查 `registered_stages` 中各 `stage_cls.__name__` 是否已包含 `_EXPECTED_STAGE_NAMES` 全部名字——若已包含则置标志位返回；否则逐个 `import_module` `_BUILTIN_STAGE_MODULES` 中的模块，让 `@register_stage` 装饰器完成注册，最后置 `_builtin_stages_registered = True`。
- **关键常量**:
  - `_BUILTIN_STAGE_MODULES: tuple[str, ...]` — 9 个内置 stage 模块的完整点分路径，顺序为 waking_check → whitelist_check → session_status_check → rate_limit_check → content_safety_check → preprocess_stage → process_stage → result_decorate → respond。
  - `_EXPECTED_STAGE_NAMES: set[str]` — 期望注册的 9 个类名集合（`WakingCheckStage`、`WhitelistCheckStage`、`SessionStatusCheckStage`、`RateLimitStage`、`ContentSafetyCheckStage`、`PreProcessStage`、`ProcessStage`、`ResultDecorateStage`、`RespondStage`）。
  - `_builtin_stages_registered: bool = False` — 模块级幂等标志。
  - `__all__ = ["ensure_builtin_stages_registered"]`。
- **依赖**:
  - 标准库：`importlib.import_module`。
  - 相对导入：`.stage.registered_stages`。

### `pipeline/context.py`
- **职责**: 定义管道执行所需的上下文对象 `PipelineContext`，承载全局配置、插件管理器以及调用 handler / 事件钩子的可调用对象。
- **核心类**:
  - `@dataclass PipelineContext` — 职责：作为各 Stage 初始化时拿到的"上下文快照"，传递配置和插件管理器，并直接把 `call_handler`、`call_event_hook` 暴露为字段方便调用。
    - 关键属性: `astrbot_config: AstrBotConfig`（AstrBot 配置对象）；`plugin_manager: PluginManager`（插件管理器对象）；`astrbot_config_id: str`（无默认值）；`call_handler = call_handler`（类属性赋值，引用 `context_utils.call_handler`）；`call_event_hook = call_event_hook`（同上）。
    - 关键方法: 无（dataclass 自动生成 `__init__`）。
- **核心函数**: 无。
- **关键常量**: 无。
- **依赖**:
  - 标准库：`dataclasses.dataclass`、`typing.TYPE_CHECKING`、`from __future__ import annotations`。
  - astrbot 内部：`astrbot.core.config.AstrBotConfig`；`TYPE_CHECKING` 下 `astrbot.core.star.PluginManager`。
  - 相对导入：`.context_utils`（`call_event_hook`、`call_handler`）。

### `pipeline/context_utils.py`
- **职责**: 提供两个核心异步工具函数——`call_handler` 负责执行单个插件 handler 并按洋葱模型处理其返回结果；`call_event_hook` 负责按注册顺序调用某事件类型的所有钩子函数并检测事件是否被停止。
- **核心类**: 无。
- **核心函数**:
  - `async call_handler(event, handler, *args, **kwargs) -> AsyncGenerator[Any, None]` — 执行事件处理函数并处理其返回结果。支持两类 handler：(1) **异步生成器**（实现洋葱模型：每次 `yield` 把控制权交回上层，返回值只能是 `MessageEventResult`/`CommandResult` 或 `None`）；(2) **协程**（执行一次并处理返回值）。流程：先 `handler(event, *args, **kwargs)` 得到 `ready_to_call`（捕获 `TypeError` 记录插件参数不匹配错误）；若 `ready_to_call` 为空直接 `return`。若 `inspect.isasyncgen`：`async for ret in ready_to_call`，命中 `MessageEventResult | CommandResult` 时 `event.set_result(ret)` 后 `yield`，否则 `yield ret`；若整个生成器从未 `yield` 过则补一次 `yield`。若 `inspect.iscoroutine`：`await` 拿到 `ret`，同样按类型分流后 `yield`。异常时记录 `Previous Error` 后 `raise`。
  - `async call_event_hook(event, hook_type, *args, **kwargs) -> bool` — 调用事件钩子函数。通过 `star_handlers_registry.get_handlers_by_event_type(hook_type, plugins_name=event.plugins_name)` 取得 handler 列表，逐个 `await handler.handler(event, *args, **kwargs)`，异常用 `traceback.format_exc()` 记录但**不中断**循环。每次调用后检查 `event.is_stopped()`——若停止则记录日志并返回 `True`。最终返回 `event.is_stopped()`。
- **关键常量**: 无。
- **依赖**:
  - 标准库：`inspect`、`traceback`、`typing as T`。
  - astrbot 内部：`astrbot.logger`；`astrbot.core.message.message_event_result`（`CommandResult`、`MessageEventResult`）；`astrbot.core.platform.astr_message_event.AstrMessageEvent`；`astrbot.core.star.star.star_map`；`astrbot.core.star.star_handler`（`EventType`、`star_handlers_registry`）。

### `pipeline/scheduler.py`
- **职责**: 管道调度器 `PipelineScheduler`——按 `STAGES_ORDER` 顺序对 `registered_stages` 排序、实例化并初始化所有阶段，并通过递归执行 `_process_stages` 实现**洋葱模型**核心调度；同时负责活动事件注册表的登记/注销与临时文件清理。
- **核心类**:
  - `PipelineScheduler` — 职责：管道调度器，负责调度各个阶段的执行。
    - 关键属性: `ctx`（`PipelineContext` 上下文对象）；`stages: list`（存储阶段实例）。
    - 关键方法:
      - `__init__(self, context: PipelineContext) -> None` — 调用 `ensure_builtin_stages_registered()`，再以 `STAGES_ORDER.index(x.__name__)` 为 key 对 `registered_stages` 排序；保存 `self.ctx = context`；`self.stages = []`。
      - `async initialize(self) -> None` — 遍历 `registered_stages`，逐个 `stage_cls()` → `await stage_instance.initialize(self.ctx)` → `self.stages.append(stage_instance)`。
      - `async _process_stages(self, event, from_stage=0) -> None` — 依次执行阶段。`for i in range(from_stage, len(self.stages))`：取 `stage = self.stages[i]`，调用 `coroutine = stage.process(event)`。若 `isinstance(coroutine, AsyncGenerator)`：`async for _ in coroutine`，在每个 `yield` 暂停点检查 `event.is_stopped()`（停止则 `break`），否则**递归** `await self._process_stages(event, i + 1)` 处理所有后续阶段，递归返回后再次检查 `is_stopped` 决定是否 `break`。若不是生成器（普通协程）：`await coroutine` 后检查 `is_stopped` 决定是否 `break`。
      - `async execute(self, event: AstrMessageEvent) -> None` — 执行 pipeline 入口。先 `active_event_registry.register(event)`；`try` 内 `await self._process_stages(event)`，对 `WebChatMessageEvent | WecomAIBotMessageEvent` 调用 `await event.send(None)` 发送空消息；`finally` 内 `event.cleanup_temporary_local_files()` 并 `active_event_registry.unregister(event)`。
- **核心函数**: 无。
- **关键常量**: 无。
- **依赖**:
  - 标准库：`collections.abc.AsyncGenerator`。
  - astrbot 内部：`astrbot.core.logger`；`astrbot.core.platform.AstrMessageEvent`；`astrbot.core.platform.sources.webchat.webchat_event.WebChatMessageEvent`；`astrbot.core.platform.sources.wecom_ai_bot.wecomai_event.WecomAIBotMessageEvent`；`astrbot.core.utils.active_event_registry.active_event_registry`。
  - 相对导入：`.bootstrap.ensure_builtin_stages_registered`、`.context.PipelineContext`、`.stage.registered_stages`、`.stage_order.STAGES_ORDER`。

### `pipeline/stage.py`
- **职责**: 定义 Stage 抽象基类、`@register_stage` 装饰器以及全局注册表 `registered_stages`。
- **核心类**:
  - `Stage(abc.ABC)` — 职责：描述一个 Pipeline 的某个阶段，是所有具体 stage 的基类。
    - 关键属性: 无实例属性。
    - 关键方法:
      - `@abc.abstractmethod async initialize(self, ctx: PipelineContext) -> None` — 初始化阶段，接收 `PipelineContext`。
      - `@abc.abstractmethod async process(self, event: AstrMessageEvent) -> None | AsyncGenerator[None]` — 处理事件，返回 `None` 表示不需要继续处理，返回异步生成器表示需要继续处理（进入下一阶段）。两个方法均 `raise NotImplementedError`。
- **核心函数**:
  - `register_stage(cls)` — 简单装饰器：把 `cls` 追加到 `registered_stages` 列表后返回 `cls`（不包裹，保留原类）。
- **关键常量**:
  - `registered_stages: list[type[Stage]] = []` — 全局已注册的 Stage 实现类类型列表。
- **依赖**:
  - 标准库：`abc`、`collections.abc.AsyncGenerator`、`from __future__ import annotations`。
  - astrbot 内部：`astrbot.core.platform.astr_message_event.AstrMessageEvent`。
  - 相对导入：`.context.PipelineContext`。

### `pipeline/stage_order.py`
- **职责**: 定义 pipeline 各 stage 的执行顺序常量 `STAGES_ORDER`。
- **核心类**: 无。
- **核心函数**: 无。
- **关键常量**:
  - `STAGES_ORDER: list[str]` — 9 个 stage 类名的有序列表，依次为：`"WakingCheckStage"`（检查是否需要唤醒）、`"WhitelistCheckStage"`（检查是否在群聊/私聊白名单）、`"SessionStatusCheckStage"`（检查会话是否整体启用）、`"RateLimitStage"`（检查会话是否超过频率限制）、`"ContentSafetyCheckStage"`（检查内容安全）、`"PreProcessStage"`（预处理）、`"ProcessStage"`（交由 Stars/插件处理或 LLM 调用）、`"ResultDecorateStage"`（处理结果，如添加回复前缀、t2i、转语音等）、`"RespondStage"`（发送消息）。
  - `__all__ = ["STAGES_ORDER"]`。
- **依赖**: 无（纯常量模块）。

---

## 唤醒 / 白名单 / 会话状态 / 限流 检查 stages

### `pipeline/waking_check/stage.py`
- **职责**: `WakingCheckStage`——pipeline 第一阶段，判断当前消息是否"唤醒"机器人。唤醒条件包括：被 `@`/`@全体`/被引用回复、消息以 `wake_prefix` 开头（且群聊中首段 At 不是指向他人）、私聊默认唤醒（可配置）、插件 handler filter 通过。同时负责 unique session 改写、忽略机器人自身消息、识别 admin 身份、按 `plugin_set` 过滤启用的插件、通过 `SessionPluginManager` 过滤会话级插件 handler，并把激活的 handler 与解析出的参数写入 event extras；若最终未唤醒则 `stop_event()`。
- **核心类**:
  - `@register_stage WakingCheckStage(Stage)` — 职责：见上。文档字符串列出 5 类唤醒条件。
    - 关键属性（由 `initialize` 设置）: `self.ctx`；`self.no_permission_reply`（`platform_settings.no_permission_reply`，默认 True）；`self.friend_message_needs_wake_prefix`（私聊是否需要 wake_prefix，默认 False）；`self.ignore_bot_self_message`（默认 False）；`self.ignore_at_all`（默认 False）；`self.disable_builtin_commands`（顶层 `disable_builtin_commands`，默认 False）；`self.unique_session`（`platform_settings.unique_session`，默认 False）。
    - 关键方法:
      - `async initialize(self, ctx: PipelineContext) -> None` — 读取上述配置项。
      - `async process(self, event) -> None | AsyncGenerator[None, None]` — 完整唤醒判定流程：(1) 若 `unique_session` 且为群消息，用 `build_unique_session_id(event)` 改写 `event.session_id`；(2) 忽略机器人自身消息（`get_self_id() == get_sender_id()` 时 `stop_event()` 返回）；(3) 去除 `message_str` 首尾空白，遍历 `admins_id` 标记 `event.role = "admin"`；(4) 遍历 `wake_prefix`：若 `message_str.startswith(wake_prefix)`，且群聊中首段 At 既不是 bot 也不是 all 则不唤醒并 `break`，否则置 `is_wake/is_at_or_wake_command = True` 并截掉前缀；(5) 若未唤醒，遍历消息段检测 `At(self_id)` / `AtAll`（受 `ignore_at_all` 控制）/ `Reply(sender_id == self_id)`；(6) 私聊且（`not friend_message_needs_wake_prefix` 或平台为 `webchat`）则唤醒；(7) 遍历 `EventType.AdapterMessageEvent` 类型 handler（按 `event.plugins_name` 过滤，受 `disable_builtin_commands` 跳过内置命令模块）：对每个 handler 的 `event_filters` 做 AND 逻辑——`PermissionTypeFilter` 单独处理（权限不足时按 `raise_error` 与 `no_permission_reply` 决定是否提示并 `stop_event()` 返回），其它 filter 失败则 `break`；filter 抛异常时 `event.send` 报错并 `stop_event()`；通过后若无 `CommandGroupFilter` 则加入 `activated_handlers`，并从 `event.get_extra("parsed_params")` 收集到 `handlers_parsed_params[handler.handler_full_name]`，最后 `event._extras.pop("parsed_params", None)`；(8) 调 `SessionPluginManager.filter_handlers_by_session` 过滤；(9) `set_extra("activated_handlers", ...)` 与 `set_extra("handlers_parsed_params", ...)`；(10) 若 `not is_wake` 则 `event.stop_event()`。
- **核心函数**:
  - `build_unique_session_id(event: AstrMessageEvent) -> str | None` — 根据 `event.get_platform_name()` 从 `UNIQUE_SESSION_ID_BUILDERS` 取出对应的 builder lambda 并执行；无对应 builder 返回 `None`。
- **关键常量**:
  - `UNIQUE_SESSION_ID_BUILDERS: dict[str, Callable[[AstrMessageEvent], str | None]]` — 各平台 unique session id 构造器映射，键为平台名：`"aiocqhttp"` → `f"{sender_id}_{group_id}"`；`"slack"` → 同上；`"dingtalk"` → `sender_id`；`"qq_official"` → `sender_id`；`"qq_official_webhook"` → `sender_id`；`"lark"` → `f"{sender_id}%{group_id}"`；`"misskey"` → `f"{session_id}_{sender_id}"`；`"matrix"` → `f"{sender_id}_{group_id or session_id}"`。
- **依赖**:
  - 标准库：`collections.abc`（`AsyncGenerator`、`Callable`）。
  - astrbot 内部：`astrbot.logger`；`astrbot.core.message.components`（`At`、`AtAll`、`Reply`）；`astrbot.core.message.message_event_result`（`MessageChain`、`MessageEventResult`）；`astrbot.core.platform.astr_message_event.AstrMessageEvent`；`astrbot.core.platform.message_type.MessageType`；`astrbot.core.star.filter.command_group.CommandGroupFilter`；`astrbot.core.star.filter.permission.PermissionTypeFilter`；`astrbot.core.star.session_plugin_manager.SessionPluginManager`；`astrbot.core.star.star.star_map`；`astrbot.core.star.star_handler`（`EventType`、`star_handlers_registry`）。
  - 相对导入：`..context.PipelineContext`、`..stage`（`Stage`、`register_stage`）。

### `pipeline/whitelist_check/stage.py`
- **职责**: `WhitelistCheckStage`——检查消息来源（`unified_msg_origin` 或 `group_id`）是否在白名单内；若未启用或白名单为空或来自 webchat 则豁免；并支持管理员在群聊/私聊中豁免白名单检查。未通过则 `stop_event()`。
- **核心类**:
  - `@register_stage WhitelistCheckStage(Stage)` — 职责：检查是否在群聊/私聊白名单。
    - 关键属性（由 `initialize` 设置）: `self.enable_whitelist_check`（`platform_settings.enable_id_white_list`）；`self.whitelist`（`platform_settings.id_whitelist`，已 strip、去空、转 str）；`self.wl_ignore_admin_on_group`；`self.wl_ignore_admin_on_friend`；`self.wl_log`（`platform_settings.id_whitelist_log`）。
    - 关键方法:
      - `async initialize(self, ctx) -> None` — 读取上述配置。
      - `async process(self, event) -> None | AsyncGenerator[None, None]` — 未启用 / 白名单为空 / 平台为 `webchat` 时直接 `return`；若 `wl_ignore_admin_on_group` 且 `event.role == "admin"` 且为群消息则 `return`；`wl_ignore_admin_on_friend` 同理对私聊；若 `event.unified_msg_origin not in self.whitelist and str(event.get_group_id()).strip() not in self.whitelist`，则按 `wl_log` 记录日志并 `event.stop_event()`。
- **核心函数**: 无。
- **关键常量**: 无。
- **依赖**:
  - 标准库：`collections.abc.AsyncGenerator`。
  - astrbot 内部：`astrbot.core.logger`；`astrbot.core.platform.astr_message_event.AstrMessageEvent`；`astrbot.core.platform.message_type.MessageType`。
  - 相对导入：`..context.PipelineContext`、`..stage`（`Stage`、`register_stage`）。

### `pipeline/session_status_check/stage.py`
- **职责**: `SessionStatusCheckStage`——检查会话是否被整体启用；若 `SessionServiceManager.is_session_enabled(umo)` 为 False，则作为 #2309 的 workaround：当无当前会话 id 时新建会话，然后 `stop_event()`。
- **核心类**:
  - `@register_stage SessionStatusCheckStage(Stage)` — 职责：检查会话是否整体启用。
    - 关键属性: `self.ctx`；`self.conv_mgr = ctx.plugin_manager.context.conversation_manager`。
    - 关键方法:
      - `async initialize(self, ctx) -> None` — 保存 ctx 与 conversation manager。
      - `async process(self, event) -> None | AsyncGenerator[None, None]` — 若 `not await SessionServiceManager.is_session_enabled(event.unified_msg_origin)`：记录 debug 日志；通过 `self.conv_mgr.get_curr_conversation_id(umo)` 取 `conv_id`，若不存在则 `await self.conv_mgr.new_conversation(umo, platform_id=event.get_platform_id())`；最后 `event.stop_event()`。
- **核心函数**: 无。
- **关键常量**: 无。
- **依赖**:
  - 标准库：`collections.abc.AsyncGenerator`。
  - astrbot 内部：`astrbot.core.logger`；`astrbot.core.platform.astr_message_event.AstrMessageEvent`；`astrbot.core.star.session_llm_manager.SessionServiceManager`。
  - 相对导入：`..context.PipelineContext`、`..stage`（`Stage`、`register_stage`）。

### `pipeline/rate_limit_check/stage.py`
- **职责**: `RateLimitStage`——基于 **Fixed Window 算法** 的会话级限流器。每个会话维护一个时间戳 `deque` 和一把 `asyncio.Lock`；触发限流时根据 `strategy` 选择 **stall**（睡眠到下一窗口后自动恢复）或 **discard**（直接丢弃，`stop_event()`）。
- **核心类**:
  - `@register_stage RateLimitStage(Stage)` — 职责：限流检查。
    - 关键属性（`__init__`）: `self.event_timestamps: defaultdict[str, deque[datetime]] = defaultdict(deque)`；`self.locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)`；`self.rate_limit_count: int = 0`；`self.rate_limit_time: timedelta = timedelta(0)`。
    - 关键属性（`initialize` 追加）: `self.rate_limit_count`（`platform_settings.rate_limit.count`）；`self.rate_limit_time`（按 `time` 秒构造的 `timedelta`）；`self.rl_strategy`（`platform_settings.rate_limit.strategy`，stall 或 discard）。
    - 关键方法:
      - `__init__(self) -> None` — 初始化上述容器与默认值。
      - `async initialize(self, ctx) -> None` — 读取限流参数与策略。
      - `async process(self, event) -> None | AsyncGenerator[None, None]` — `session_id = event.session_id`，`now = datetime.now()`。`async with self.locks[session_id]` 进入循环：取 `timestamps = self.event_timestamps[session_id]`，`_remove_expired_timestamps(timestamps, now)`；若 `rate_limit_count <= 0` 则 `break`；若 `len(timestamps) < rate_limit_count` 则 `timestamps.append(now)` 并 `break`；否则计算 `next_window_time = timestamps[0] + rate_limit_time` 与 `stall_duration = (next_window_time - now).total_seconds() + 0.3`。`match self.rl_strategy`：`STALL.value` 分支记录日志并 `await asyncio.sleep(stall_duration)`、刷新 `now` 后继续循环；`DISCARD.value` 分支记录日志并 `return event.stop_event()`。
      - `_remove_expired_timestamps(self, timestamps: deque[datetime], now: datetime) -> None` — `expiry_threshold = now - self.rate_limit_time`，`while timestamps and timestamps[0] < expiry_threshold: timestamps.popleft()`。
- **核心函数**: 无。
- **关键常量**: 无。
- **依赖**:
  - 标准库：`asyncio`、`collections`（`defaultdict`、`deque`）、`collections.abc.AsyncGenerator`、`datetime`（`datetime`、`timedelta`）。
  - astrbot 内部：`astrbot.core.logger`；`astrbot.core.config.astrbot_config.RateLimitStrategy`；`astrbot.core.platform.astr_message_event.AstrMessageEvent`。
  - 相对导入：`..context.PipelineContext`、`..stage`（`Stage`、`register_stage`）。

---

## content_safety_check 子包（5 个文件）

### `pipeline/content_safety_check/stage.py`
- **职责**: `ContentSafetyCheckStage`——pipeline 第 5 阶段，调用 `StrategySelector.check(text)` 对当前消息文本（或外部传入的 `check_text`）做内容安全检查。检查失败时，若消息是唤醒指令则设置一条阻断结果并 `yield`（让结果装饰/响应阶段处理），随后 `stop_event()` 并记录日志。当前仅检查文本。
- **核心类**:
  - `@register_stage ContentSafetyCheckStage(Stage)` — 职责：检查内容安全（当前只检查文本）。
    - 关键属性: `self.strategy_selector = StrategySelector(config)`（`config = ctx.astrbot_config["content_safety"]`）。
    - 关键方法:
      - `async initialize(self, ctx) -> None` — 用 `content_safety` 配置构造 `StrategySelector`。
      - `async process(self, event, check_text: str | None = None) -> AsyncGenerator[None, None]` — `text = check_text if check_text else event.get_message_str()`；`ok, info = self.strategy_selector.check(text)`；若 `not ok`：当 `event.is_at_or_wake_command` 时 `event.set_result(MessageEventResult().message("Your message or the model response contains inappropriate content and has been blocked."))` 并 `yield`；随后 `event.stop_event()`、记录 `Content safety check failed: {info}` 后 `return`。注意 `process` 是异步生成器（带 `yield`），故可被 result_decorate 阶段以 `async for _ in stage.process(event, check_text=...)` 形式复用。
- **核心函数**: 无。
- **关键常量**: 无。
- **依赖**:
  - 标准库：`collections.abc.AsyncGenerator`。
  - astrbot 内部：`astrbot.core.logger`；`astrbot.core.message.message_event_result.MessageEventResult`；`astrbot.core.platform.astr_message_event.AstrMessageEvent`。
  - 相对导入：`..context.PipelineContext`、`..stage`（`Stage`、`register_stage`）、`.strategies.strategy.StrategySelector`。

### `pipeline/content_safety_check/strategies/__init__.py`
- **职责**: 定义内容安全策略的抽象基类 `ContentSafetyStrategy`，统一 `check` 接口签名。
- **核心类**:
  - `ContentSafetyStrategy(abc.ABC)` — 职责：内容安全策略抽象基类。
    - 关键属性: 无。
    - 关键方法: `@abc.abstractmethod def check(self, content: str) -> tuple[bool, str]` — `raise NotImplementedError`。约定返回 `(ok, info)`：`ok` 为 True 表示通过，`info` 为失败原因描述。
- **核心函数**: 无。
- **关键常量**: 无。
- **依赖**: 标准库 `abc`。

### `pipeline/content_safety_check/strategies/strategy.py`
- **职责**: `StrategySelector`——根据配置懒加载并组合启用的内容安全策略（关键词策略 + 百度 AIP 策略），统一执行 `check`，遇到首个失败策略即短路返回。
- **核心类**:
  - `StrategySelector` — 职责：策略选择器，按配置装配多个 `ContentSafetyStrategy` 实例并顺序执行。
    - 关键属性: `self.enabled_strategies: list[ContentSafetyStrategy] = []`。
    - 关键方法:
      - `__init__(self, config: dict) -> None` — 若 `config["internal_keywords"]["enable"]`：从 `.keywords` 懒导入 `KeywordsStrategy`，用 `config["internal_keywords"]["extra_keywords"]` 构造并 append。若 `config["baidu_aip"]["enable"]`：`try` 从 `.baidu_aip` 懒导入 `BaiduAipStrategy`（`ImportError` 时 warning 提示安装 `baidu-aip` 并 `return`），用 `app_id`/`api_key`/`secret_key` 构造并 append。
      - `def check(self, content: str) -> tuple[bool, str]` — 顺序遍历 `enabled_strategies`，任一返回 `(False, info)` 立即返回；全部通过返回 `(True, "")`。
- **核心函数**: 无。
- **关键常量**: 无。
- **依赖**:
  - astrbot 内部：`astrbot.logger`。
  - 相对导入：`from . import ContentSafetyStrategy`（即 `strategies/__init__.py` 的基类）。`.keywords.KeywordsStrategy`、`.baidu_aip.BaiduAipStrategy` 为懒导入。

### `pipeline/content_safety_check/strategies/keywords.py`
- **职责**: `KeywordsStrategy`——基于关键词正则匹配的内部内容安全策略；命中任一关键词即判定不合规。
- **核心类**:
  - `KeywordsStrategy(ContentSafetyStrategy)` — 职责：关键词阻断策略。
    - 关键属性: `self.keywords: list = []`（构造时 extend `extra_keywords`；`extra_keywords` 为 `None` 时视为空列表）。源码中存在被注释的从 `unfit_words` 文件 base64 解码加载内置关键词的逻辑（当前未启用）。
    - 关键方法: `def check(self, content: str) -> tuple[bool, str]` — 遍历 `self.keywords`，`re.search(keyword, content)` 命中则返回 `(False, "Content safety check failed because a blocked keyword was matched.")`；全部未命中返回 `(True, "")`。注意 `keyword` 本身作为正则模式使用。
- **核心函数**: 无。
- **关键常量**: 无。
- **依赖**: 标准库 `re`；相对导入 `from . import ContentSafetyStrategy`。

### `pipeline/content_safety_check/strategies/baidu_aip.py`
- **职责**: `BaiduAipStrategy`——基于百度智能云内容审核（`AipContentCensor`）的文本审核策略。需要先 `pip install baidu-aip`。
- **核心类**:
  - `BaiduAipStrategy(ContentSafetyStrategy)` — 职责：百度 AIP 文本内容审核。
    - 关键属性: `self.app_id`、`self.api_key`、`self.secret_key`、`self.client = AipContentCensor(app_id, api_key, secret_key)`。
    - 关键方法: `def check(self, content: str) -> tuple[bool, str]` — `res = self.client.textCensorUserDefined(content)`。若 `"conclusionType" not in res` 返回 `(False, "")`；若 `res["conclusionType"] == 1` 返回 `(True, "")`（合规）；若 `"data" not in res` 返回 `(False, "")`；否则统计违规数 `count = len(res["data"])`，构造 `info`：首行 `"Baidu content moderation found {count} violations:\n"`，逐条追加 `cast(dict[str, Any], i).get('msg', '')` + `;\n`，末尾追加 `"\nEvaluation: " + res["conclusion"]`，返回 `(False, info)`。
- **核心函数**: 无。
- **关键常量**: 无。
- **依赖**:
  - 标准库：`typing`（`Any`、`cast`）。
  - 第三方：`aip.AipContentCensor`（来自 `baidu-aip` 包）。
  - 相对导入：`from . import ContentSafetyStrategy`。

---

## preprocess_stage / result_decorate / respond stages

### `pipeline/preprocess_stage/stage.py`
- **职责**: `PreProcessStage`——pipeline 第 6 阶段，执行真正的"预处理"：(1) 平台 pre-ack emoji（telegram/lark/discord 在唤醒消息上 react 一个随机表情）；(2) 路径映射 `platform_settings.path_mapping`（对 `Record`/`Image` 段的 `url` 做 `from_:to_` 替换，支持 `file://` URI）；(3) 媒体归一化：把 `Record` 转 WAV（`ensure_wav`）、`Image` 转 JPEG（`ensure_jpeg`），并对 `Reply` 链内的同类型段做同样处理，过程中通过 `_track_temp_media` 把落在 AstrBot temp 目录下的临时文件登记到事件以便清理；(4) STT 语音转文本（`provider_stt_settings.enable`），对消息链及 Reply 链中的 `Record` 段调用当前会话的 STT provider，成功则替换为 `Plain` 并追加到 `message_str`；含 napcat 文件未就绪的 5 次 0.5s 重试逻辑。
- **核心类**:
  - `@register_stage PreProcessStage(Stage)` — 职责：处理事件之前的预处理。
    - 关键属性（`initialize`）: `self.ctx`；`self.config = ctx.astrbot_config`；`self.plugin_manager`；`self.stt_settings: dict = config.get("provider_stt_settings", {})`；`self.platform_settings: dict = config.get("platform_settings", {})`。
    - 关键方法:
      - `async initialize(self, ctx) -> None` — 读取上述配置。
      - `@staticmethod _track_temp_media(event, media_path: str) -> None` — 把 `media_path` 解析为绝对路径，若位于 `get_astrbot_temp_path()` 之下则调 `event.track_temporary_local_file(str(path))`；捕获 `OSError`/`ValueError` 静默返回。
      - `async process(self, event) -> None | AsyncGenerator[None, None]` — 顺序执行：pre-ack emoji（条件：`platform_specific.<platform>.pre_ack_emoji.enable` 且平台属于 `{telegram, lark, discord}` 且有 emojis 且 `is_at_or_wake_command`，调 `event.react(random.choice(emojis))`，失败 warning）；路径映射；顶层 `Record`/`Image` 归一化（`convert_to_file_path` → `_track_temp_media` → `ensure_wav`/`ensure_jpeg` → `_track_temp_media` → 写回 `file`/`path`/`url`，异常 warning）；`Reply` 链内同类型归一化；STT：定义嵌套协程 `_stt_record(record_comp, is_reply=False)`（5 次重试，`FileNotFoundError` 时 `asyncio.sleep(0.5)`，成功返回 `Plain(result)` 并 log，失败返回 `None`），对消息链及 Reply 链中的 `Record` 段执行 STT，成功则替换并累加 `event.message_str`/`event.message_obj.message_str`。
- **核心函数**: 无（仅类内嵌套函数 `_stt_record`）。
- **关键常量**: 无。
- **依赖**:
  - 标准库：`asyncio`、`random`、`traceback`、`collections.abc.AsyncGenerator`、`pathlib.Path`。
  - astrbot 内部：`astrbot.core.logger`；`astrbot.core.message.components`（`Image`、`Plain`、`Record`、`Reply`）；`astrbot.core.platform.astr_message_event.AstrMessageEvent`；`astrbot.core.utils.astrbot_path.get_astrbot_temp_path`；`astrbot.core.utils.media_utils`（`describe_media_ref`、`ensure_jpeg`、`ensure_wav`、`file_uri_to_path`、`is_file_uri`）。
  - 相对导入：`..context.PipelineContext`、`..stage`（`Stage`、`register_stage`）。

### `pipeline/result_decorate/stage.py`
- **职责**: `ResultDecorateStage`——pipeline 第 8 阶段，对将要发送的结果做装饰：回复内容安全复检（仅非流式 LLM 结果）、`OnDecoratingResultEvent` 事件钩子、回复前缀、分段回复（按词或正则切分 + 清洗规则）、TTS（含 dual output、file_service 注册、概率触发、reasoning 注入）、文本转图片（超过字数阈值时渲染为图片，支持 network/本地/file_service）、aiocqhttp 合并转发（超过 `forward_threshold` 字数时包成单个 `Node`）、@回复与引用回复装饰。流式结果（`STREAMING_RESULT`）直接返回；流式结束（`STREAMING_FINISH`）跳过大部分装饰。
- **核心类**:
  - `@register_stage ResultDecorateStage(Stage)` — 职责：结果装饰。
    - 关键属性（`initialize`，按配置项分组）:
      - 基础: `self.ctx`；`self.reply_prefix`；`self.reply_with_mention`；`self.reply_with_quote`。
      - 文转图: `self.t2i_word_threshold`（强制 `max(int, 50)`，异常回退 150）；`self.t2i_strategy`；`self.t2i_use_network = (strategy == "remote")`；`self.t2i_active_template`。
      - 转发: `self.forward_threshold`（`platform_settings.forward_threshold`）。
      - TTS: `self.tts_trigger_probability`（clamp 到 `[0.0, 1.0]`，异常回退 1.0）。
      - 分段回复: `self.words_count_threshold`；`self.enable_segmented_reply`；`self.only_llm_result`；`self.split_mode`（默认 `"regex"`）；`self.regex`；`self.split_words`（默认 `["。", "？", "！", "~", "…"]`）；`self.split_words_pattern`（按 `split_words` 长度倒序拼接为 `(.*?(word1|word2|...)|.+$)` 的 `re.DOTALL` 编译对象，`split_words` 为空时为 `None`）；`self.content_cleanup_rule`。
      - 内容安全复检: `self.content_safe_check_reply`（`content_safety.also_use_in_response`）；`self.content_safe_check_stage`（若启用则遍历 `registered_stages` 找到 `ContentSafetyCheckStage` 类，实例化并 `await initialize(ctx)`）。
      - reasoning: `self.show_reasoning`（`provider_settings.display_reasoning_text`）。
    - 关键方法:
      - `async initialize(self, ctx) -> None` — 读取上述全部配置；按需实例化 `ContentSafetyCheckStage`。
      - `def _split_text_by_words(self, text: str) -> list[str]` — 用 `self.split_words_pattern.findall(text)` 分段；对每个分段元组取 `content = seg[0]`，去掉结尾的分段词，strip 后非空则收集；空 `split_words_pattern` 时返回 `[text]`；结果为空时返回 `[text]`。
      - `async process(self, event) -> None | AsyncGenerator[None, None]` — 主流程：取 `result = event.get_result()`，为空或 `chain` 空则 `return`；`STREAMING_RESULT` 直接 `return`；`is_stream = (result_content_type == STREAMING_FINISH)`。**回复内容安全复检**：条件 `content_safe_check_reply and content_safe_check_stage and result.is_llm_result() and not is_stream`，把所有 `Plain` 拼成 `text`，以 `async for _ in self.content_safe_check_stage.process(event, check_text=text): yield` 调用复检（复检失败会 `stop_event`，但本段 yield 后续仍会继续，由后续 is_stopped 检查阻断）。**OnDecoratingResultEvent 钩子**：取该类型 handler 列表逐个 `await handler.handler(event)`，流式时 warning；每个 handler 后重新取 result，为空则 debug；`is_stopped` 则记录 info 并 `return`。`is_stream` 时 `return`。**再取一次 result**（插件可能替换 chain）。`len(result.chain) > 0` 时依次：回复前缀（仅给首个 `Plain` 加前缀）；分段回复（平台非 `qq_official_webhook`/`weixin_official_account`/`dingtalk`，且 `only_llm_result` 条件成立时，对每个 `Plain` 若 `len(text) > words_count_threshold` 不分段直接保留，否则按 `split_mode` 选 `_split_text_by_words` 或正则 `findall(self.regex, ..., re.DOTALL | re.MULTILINE)`（正则异常回退默认 `.*?[。？！~…]+|.+$`），再用 `content_cleanup_rule` `re.sub` 清洗（异常时把 rule 置 `None`），strip 后非空追加为 `Plain(seg)`，非 `Plain` 段直接保留，最后 `result.chain = new_chain`）；TTS（`should_tts = provider_tts_settings.enable and result.is_llm_result() and SessionServiceManager.should_process_tts_request(event) and random.random() <= tts_trigger_probability and tts_provider`，should_tts 但无 provider 时 warning；`not should_tts and show_reasoning and _llm_reasoning_content` 时按平台注入 reasoning（lark 用 `Json` 折叠面板，其它用 `Plain("🤔 思考: ...")`）；should_tts 且有 provider 时遍历 chain 把 `Plain(len(text) > 1)` 转 `Record`，含 file_service 注册、`dual_output` 同时保留原文、异常回退原文）；文转图（`elif (result.use_t2i_ is None and t2i) or result.use_t2i_`：拼接开头连续 `Plain` 段，`len > t2i_word_threshold` 时 `html_renderer.render_t2i(plain_str, return_url=True, use_network=..., template_name=...)`，超 3s warning，http URL 用 `Image.fromURL`，否则按 `t2i_use_file_service` 走 file_service 或 `Image.fromFileSystem`，渲染异常直接 `return`）；aiocqhttp 转发（统计 `Plain` 字数 `> forward_threshold` 时包成 `Node(uin=self_id, name="AstrBot", content=[*result.chain])`，`result.chain = [node]`）；@回复 / 引用回复（`can_decorate = all(isinstance(item, (Plain, Image)) for item in result.chain)`，群聊且 `reply_with_mention` 时在 chain 头部插 `At(qq=sender_id, name=sender_name)` 并给后续首个 `Plain` 加 `\n` 前缀，`reply_with_quote` 时在头部插 `Reply(id=message_obj.message_id)`）。
- **核心函数**: 无。
- **关键常量**: 无（`supported` 局部集合 `{"telegram", "lark", "discord"}` 在 process 内）。
- **依赖**:
  - 标准库：`random`、`re`、`time`、`traceback`、`collections.abc.AsyncGenerator`。
  - astrbot 内部：`astrbot.core`（`file_token_service`、`html_renderer`、`logger`）；`astrbot.core.message.components`（`At`、`Image`、`Json`、`Node`、`Plain`、`Record`、`Reply`）；`astrbot.core.message.message_event_result.ResultContentType`；`astrbot.core.pipeline.content_safety_check.stage.ContentSafetyCheckStage`；`astrbot.core.platform.astr_message_event.AstrMessageEvent`；`astrbot.core.platform.message_type.MessageType`；`astrbot.core.star.session_llm_manager.SessionServiceManager`；`astrbot.core.star.star.star_map`；`astrbot.core.star.star_handler`（`EventType`、`star_handlers_registry`）。
  - 相对导入：`..context.PipelineContext`、`..stage`（`Stage`、`register_stage`、`registered_stages`）。

### `pipeline/respond/stage.py`
- **职责**: `RespondStage`——pipeline 末段，真正把结果发送出去。负责：去重（已通过 `send_message_to_user` 投递过相同纯文本则跳过）、流式结果直接 `send_streaming`、路径映射（对 `File` 段）、空消息链检测与跳过、清理空 `Plain` 段、分段回复的逐段定时发送（log 或 random 间隔）、`Record` 强制单独发送、纯 Reply/At 链跳过、`OnAfterMessageSentEvent` 钩子、最终 `clear_result`。
- **核心类**:
  - `@register_stage RespondStage(Stage)` — 职责：发送消息。
    - 类属性: `_component_validators: dict[type, Callable]` — 组件类型到"非空判断函数"的映射，覆盖 `Plain`（`text and text.strip()`）、`Face`（`id is not None`）、`Record`/`Video`（`bool(file)`）、`At`（`bool(qq) or bool(name)`）、`Image`（`bool(file)`）、`Reply`（`bool(id) and sender_id is not None`）、`Poke`（`target_id() is not None`）、`Node`（`bool(content)`）、`Nodes`（`bool(nodes)`）、`File`（`bool(file_) or bool(url)`）、`Json`（`bool(data)`）、`Share`（`bool(url) or bool(title)`）、`Music`（按 `_type` 区分 custom 与非 custom）、`Forward`（`bool(id)`）、`Location`（`lat and lon is not None`）、`Contact`（`_type and id`）、`Shake`/`Dice`/`RPS`（恒 True）、`Unknown`（`text and text.strip()`）。
    - 关键属性（`initialize`）: `self.ctx`；`self.config`；`self.platform_settings`；`self.reply_with_mention`；`self.reply_with_quote`；`self.enable_seg`；`self.only_llm_result`；`self.interval_method`；`self.log_base`；`self.interval = [1.5, 3.5]`（启用分段时尝试解析 `segmented_reply.interval` 字符串覆盖）。
    - 关键方法:
      - `async initialize(self, ctx) -> None` — 读取上述配置，解析 `interval` 字符串为 `[float, float]`，异常时 error。
      - `async _word_cnt(self, text: str) -> int` — 全 ASCII 时按空白分词计数，否则按字母数字字符计数。
      - `async _calc_comp_interval(self, comp: BaseMessageComponent) -> float` — `interval_method == "log"` 时：`Plain` 用 `math.log(wc + 1, log_base)` 加 `random.uniform(i, i+0.5)`，非 `Plain` 返回 `random.uniform(1, 1.75)`；否则 `random.uniform(self.interval[0], self.interval[1])`。
      - `async _is_empty_message_chain(self, chain: list) -> bool` — 链空返回 True；遍历组件，按 `_component_validators[type(comp)]` 判定，任一非空即返回 False；全空返回 True。
      - `def is_seg_reply_required(self, event) -> bool` — `enable_seg` 为 False 或 result 为 None 返回 False；`only_llm_result and not is_model_result()` 返回 False；平台属于 `qq_official_webhook`/`weixin_official_account`/`dingtalk` 返回 False；否则 True。
      - `def _extract_comp(self, raw_chain, extract_types: set[ComponentType], modify_raw_chain: bool = True)` — 按 `comp.type` 抽取指定类型组件；`modify_raw_chain=True` 时就地用 `raw_chain[:] = remaining` 移除已抽取项；返回抽取列表。
      - `async process(self, event) -> None | AsyncGenerator[None, None]` — 流程：取 `result`，为空 `return`；若 `_streaming_finished` 已置位 `return`（防重复发送）；`STREAMING_FINISH` 时置 `_streaming_finished=True` 并 `return`；去重检查（取 `_send_message_to_user_current_session_plain_texts` extra，若 `result.get_plain_text().strip()` 命中且 chain 全为 Plain/Reply/At 则跳过并 log）；log "Prepare to send"；`STREAMING_RESULT` 时按 `unsupported_streaming_strategy` 决定 `realtime_segmenting` 并 `await event.send_streaming(result.async_stream, realtime_segmenting)` 后 `return`。`len(result.chain) > 0` 时：路径映射（仅 `File` 段，`path_Mapping(mappings, component.file)`）；空链检测（`_is_empty_message_chain` 异常时 warning 不阻断）；移除空 `Plain` 段。**发送**：`need_separately = {ComponentType.Record}`；若 `is_seg_reply_required(event)`：先抽出 header（Reply/At）并 modify_raw_chain，若 chain 空则 warning 并 `return`（#2670 修复）；遍历 `result.chain`，每个组件 `await asyncio.sleep(await self._calc_comp_interval(comp))`，`Record` 单独 `event.send(result.derive([comp]))`，其余 `event.send(result.derive([*header_comps, comp]))` 后 `header_comps.clear()`，异常 error 不中断。**非分段**：若 chain 全为 Reply/At 则 warning 并 `return`（#2670）；抽出 `Record` 等单独组件逐个 `event.send`；剩余 chain 调 `event.send(result.derive(result.chain))`；异常均 error。最后 `if await call_event_hook(event, EventType.OnAfterMessageSentEvent): return`，再 `event.clear_result()`。
- **核心函数**: 无。
- **关键常量**: 类属性 `_component_validators`（见上）。
- **依赖**:
  - 标准库：`asyncio`、`math`、`random`、`collections.abc.AsyncGenerator`。
  - astrbot 内部：`astrbot.core.message.components as Comp`；`astrbot.core.logger`；`astrbot.core.message.components`（`BaseMessageComponent`、`ComponentType`）；`astrbot.core.message.message_event_result`（`MessageChain`、`ResultContentType`）；`astrbot.core.platform.astr_message_event.AstrMessageEvent`；`astrbot.core.star.star_handler.EventType`；`astrbot.core.utils.path_util.path_Mapping`。
  - 相对导入：`..context`（`PipelineContext`、`call_event_hook`）、`..stage`（`Stage`、`register_stage`）。

---

## process_stage 子包（6 个文件）

### `pipeline/process_stage/stage.py`
- **职责**: `ProcessStage`——pipeline 第 7 阶段，编排"插件 handler 调用"与"LLM/Agent 调用"。先看 `event.get_extra("activated_handlers")` 是否非空，非空则交给 `StarRequestSubStage` 处理；若 star handler 以 `ProviderRequest` 形式 yield（Handler 显式请求 LLM），则把请求存入 `provider_request` extra 并交给 `AgentRequestSubStage` 处理。随后在 `provider_settings.enable` 启用且事件未被发送操作占用、是唤醒指令、且未显式 `call_llm` 时，按需再次进入 `AgentRequestSubStage`。
- **核心类**:
  - `@register_stage ProcessStage(Stage)` — 职责：处理事件。
    - 关键属性: `self.ctx`；`self.config = ctx.astrbot_config`；`self.plugin_manager`；`self.agent_sub_stage = AgentRequestSubStage()`（已 `await initialize(ctx)`）；`self.star_request_sub_stage = StarRequestSubStage()`（已 `await initialize(ctx)`）。
    - 关键方法:
      - `async initialize(self, ctx) -> None` — 创建并初始化两个子 stage。
      - `async process(self, event) -> None | AsyncGenerator[None, None]` — 取 `activated_handlers: list[StarHandlerMetadata] = event.get_extra("activated_handlers")`。若非空：`async for resp in self.star_request_sub_stage.process(event)`：若 `isinstance(resp, ProviderRequest)`：`event.set_extra("provider_request", resp)`，`async for _ in self.agent_sub_stage.process(event): _t = True; yield`，若 `_t` 为 False 补一次 `yield`；否则直接 `yield`。若 `provider_settings.enable` 为 False 则 `return`。若 `not event._has_send_oper and event.is_at_or_wake_command and not event.call_llm`：当 `event.get_result() and not event.is_stopped()` 或 `not event.get_result()` 时，`async for _ in self.agent_sub_stage.process(event): yield`。
- **核心函数**: 无。
- **关键常量**: 无。
- **依赖**:
  - 标准库：`collections.abc.AsyncGenerator`。
  - astrbot 内部：`astrbot.core.platform.astr_message_event.AstrMessageEvent`；`astrbot.core.provider.entities.ProviderRequest`；`astrbot.core.star.star_handler.StarHandlerMetadata`。
  - 相对导入：`..context.PipelineContext`、`..stage`（`Stage`、`register_stage`）、`.method.agent_request.AgentRequestSubStage`、`.method.star_request.StarRequestSubStage`。

### `pipeline/process_stage/follow_up.py`
- **职责**: 提供"追问（follow-up）捕获"机制：当某个 UMO（`unified_msg_origin`）已有活跃 agent runner 在运行时，把同一发送者的新消息捕获为该 runner 的 follow-up 输入；并通过 UMO 级的 `asyncio.Condition` + 序号状态机实现**严格按到达顺序**恢复主流程（避免 wake-order drift）。维护两张模块级表：`_ACTIVE_AGENT_RUNNERS`（UMO → 活跃 runner）与 `_FOLLOW_UP_ORDER_STATE`（UMO → 顺序状态 dict）。
- **核心类**:
  - `@dataclass(slots=True) FollowUpCapture` — 职责：一次追问捕获的上下文快照。
    - 关键属性: `umo: str`；`ticket: FollowUpTicket`；`order_seq: int`；`monitor_task: asyncio.Task[None]`；`target_run_id: str | None = None`。
- **核心函数**:
  - `_event_follow_up_text(event) -> str` — 取 `event.get_message_str()`（strip 后非空即用），否则回退到 `event.get_message_outline().strip()`。
  - `register_active_runner(umo, runner) -> None` — `_ACTIVE_AGENT_RUNNERS[umo] = runner`。
  - `unregister_active_runner(umo, runner) -> None` — 仅当表中存的 runner 是同一个时才 `pop`。
  - `_get_follow_up_order_state(umo) -> dict[str, object]` — 懒初始化状态 dict，含 `condition`（`asyncio.Condition`）、`statuses`（seq→状态 字典）、`next_order`（单调递增的序号分配器，从 0 起）、`next_turn`（当前允许继续主流程的 seq，从 0 起）。
  - `_advance_follow_up_turn_locked(state) -> None` — 在持锁状态下，跳过所有 `consumed`/`finished` 的 slot，把 `next_turn` 推进到第一个未完成 slot（或越界）。
  - `_allocate_follow_up_order(umo) -> int` — 分配新 seq：取 `next_order` 当前值作为 seq，`next_order += 1`，`statuses[seq] = "pending"`，返回 seq。
  - `async _mark_follow_up_consumed(umo, seq) -> None` — 持 `condition` 锁，若 `statuses[seq]` 存在且非 `finished` 则置 `consumed`，调 `_advance_follow_up_turn_locked`，`notify_all`；若 `statuses` 已空且无活跃 runner 则 `pop` 该 UMO 状态。
  - `async _activate_and_wait_follow_up_turn(umo, seq) -> None` — 持锁置 `statuses[seq] = "active"`，循环等待直到 `next_turn == seq`（严格排队：只有队首才能继续），否则 `await condition.wait()`。
  - `async _finish_follow_up_turn(umo, seq) -> None` — 持锁置 `statuses[seq] = "finished"`，`_advance_follow_up_turn_locked`，`notify_all`；同样在空且无 runner 时 `pop` UMO 状态。
  - `async _monitor_follow_up_ticket(umo, ticket, order_seq) -> None` — `await ticket.resolved.wait()`，若 `ticket.consumed` 则立即 `_mark_follow_up_consumed(umo, order_seq)`（避免唤醒顺序漂移）。
  - `try_capture_follow_up(event) -> FollowUpCapture | None` — 取 `sender_id`，空则 None；从 `_ACTIVE_AGENT_RUNNERS` 取 runner，无则 None；从 `runner.run_context.context.event` 取活跃事件及其 `sender_id`，不匹配则 None；若活跃事件带 `agent_stop_requested` extra 则 None；调 `runner.follow_up(message_text=_event_follow_up_text(event))` 取 ticket，无则 None；`order_seq = _allocate_follow_up_order(umo)`；`asyncio.create_task(_monitor_follow_up_ticket(...))`；log "Captured follow-up message..."；返回 `FollowUpCapture(...)`，`target_run_id` 在活跃事件有 `message_id` 时取 `str(message_id)`。
  - `async prepare_follow_up_capture(capture) -> tuple[bool, bool]` — `await capture.ticket.resolved.wait()`；若 `ticket.consumed`：调 `_mark_follow_up_consumed` 返回 `(True, False)`；否则 `_activate_and_wait_follow_up_turn` 返回 `(False, True)`。
  - `async finalize_follow_up_capture(capture, *, activated, consumed_marked) -> None` — 取消未完成的 `monitor_task`（吞 `CancelledError`）；`activated` 时 `_finish_follow_up_turn`；`not consumed_marked` 时 `_mark_follow_up_consumed`。
- **关键常量**:
  - `_ACTIVE_AGENT_RUNNERS: dict[str, AgentRunner] = {}` — UMO → 活跃 runner 映射。
  - `_FOLLOW_UP_ORDER_STATE: dict[str, dict[str, object]] = {}` — UMO → 顺序状态 dict（字段 `condition`/`statuses`/`next_order`/`next_turn`，状态值 `"pending"|"active"|"consumed"|"finished"`）。
- **依赖**:
  - 标准库：`asyncio`、`dataclasses.dataclass`、`from __future__ import annotations`。
  - astrbot 内部：`astrbot.logger`；`astrbot.core.agent.runners.tool_loop_agent_runner.FollowUpTicket`；`astrbot.core.astr_agent_run_util.AgentRunner`；`astrbot.core.platform.astr_message_event.AstrMessageEvent`。

### `pipeline/process_stage/method/agent_request.py`
- **职责**: `AgentRequestSubStage`——LLM/Agent 调用入口子阶段。负责剥离"LLM 唤醒前缀"中与 bot 唤醒前缀重叠的部分、根据 `agent_runner_type` 选择 `InternalAgentSubStage`（local）或 `ThirdPartyAgentSubStage`、检查 `provider_settings.enable` 与 `SessionServiceManager.should_process_llm_request`，并把实际处理委托给所选子 stage。
- **核心类**:
  - `AgentRequestSubStage(Stage)` — 职责：Agent 请求子阶段。
    - 关键属性: `self.ctx`；`self.config`；`self.bot_wake_prefixs: list[str] = config["wake_prefix"]`；`self.prov_wake_prefix: str = config["provider_settings"]["wake_prefix"]`（剥离与 bot 前缀重叠部分后的 LLM 唤醒前缀）；`self.agent_sub_stage`（`InternalAgentSubStage` 或 `ThirdPartyAgentSubStage`）。
    - 关键方法:
      - `async initialize(self, ctx) -> None` — 取前缀；对每个 `bwp in bot_wake_prefixs`，若 `prov_wake_prefix.startswith(bwp)` 则 log 并截掉重叠前缀；按 `agent_runner_type`（`"local"` → Internal，否则 ThirdParty）构造子 stage 并 `await initialize(ctx)`。
      - `async process(self, event) -> AsyncGenerator[None, None]` — 若 `not provider_settings["enable"]`：debug 跳过并 `return`；若 `not await SessionServiceManager.should_process_llm_request(event)`：debug 跳过并 `return`；`async for resp in self.agent_sub_stage.process(event, self.prov_wake_prefix): yield resp`。
- **核心函数**: 无。
- **关键常量**: 无。
- **依赖**:
  - 标准库：`collections.abc.AsyncGenerator`。
  - astrbot 内部：`astrbot.core.logger`；`astrbot.core.platform.astr_message_event.AstrMessageEvent`；`astrbot.core.star.session_llm_manager.SessionServiceManager`。
  - 相对导入：`...context.PipelineContext`、`..stage.Stage`、`.agent_sub_stages.internal.InternalAgentSubStage`、`.agent_sub_stages.third_party.ThirdPartyAgentSubStage`。

### `pipeline/process_stage/method/star_request.py`
- **职责**: `StarRequestSubStage`——调用被激活的插件 handler（Stars）。遍历 `activated_handlers`，对每个 handler 用 `call_handler` 执行，按洋葱模型 yield 其返回值；handler 抛异常时触发 `OnPluginErrorEvent` 钩子，并在唤醒指令下回写一条错误结果给用户；handler 间通过 `event.clear_result()` 隔离上一个 handler 的结果；任一 handler `stop_event()` 则中断循环。
- **核心类**:
  - `StarRequestSubStage(Stage)` — 职责：本地 Agent 模式的 AstrBot 插件调用 Stage。
    - 关键属性: `self.prompt_prefix = config["provider_settings"]["prompt_prefix"]`；`self.identifier = config["provider_settings"]["identifier"]`；`self.ctx`。（注：`prompt_prefix`/`identifier` 在本文件中未被使用，仅读取保存。）
    - 关键方法:
      - `async initialize(self, ctx) -> None` — 读取上述配置。
      - `async process(self, event) -> AsyncGenerator[Any, None]` — 取 `activated_handlers` 与 `handlers_parsed_params`（空则 `{}`）。`for handler in activated_handlers`：`event.is_stopped()` 时 `break`；`params = handlers_parsed_params.get(handler.handler_full_name, {})`；`md = star_map.get(handler.handler_module_path)`，无则 warning `continue`；debug 日志；`try`：`wrapper = call_handler(event, handler.handler, **params)`，`async for ret in wrapper: yield ret`，再检查 `is_stopped` 决定 `break`，未停则 `event.clear_result()`；`except Exception as e`：`traceback_text = traceback.format_exc()`，error 日志；`await call_event_hook(event, EventType.OnPluginErrorEvent, md.name, handler.handler_name, e, traceback_text)`；若 `not is_stopped and is_at_or_wake_command`：构造 `":(\n\n在调用插件 {md.name} 的处理函数 {handler.handler_name} 时出现异常：{e}"`，`event.set_result(MessageEventResult().message(ret))`，`yield`，`event.clear_result()`；最后 `event.stop_event()`。
- **核心函数**: 无。
- **关键常量**: 无。
- **依赖**:
  - 标准库：`traceback`、`collections.abc.AsyncGenerator`、`typing.Any`。
  - astrbot 内部：`astrbot.core.logger`；`astrbot.core.message.message_event_result.MessageEventResult`；`astrbot.core.platform.astr_message_event.AstrMessageEvent`；`astrbot.core.star.star.star_map`；`astrbot.core.star.star_handler`（`EventType`、`StarHandlerMetadata`）。
  - 相对导入：`...context`（`PipelineContext`、`call_event_hook`、`call_handler`）、`..stage.Stage`。

### `pipeline/process_stage/method/agent_sub_stages/internal.py`
- **职责**: `InternalAgentSubStage`——本地（local）Agent 模式的 LLM 调用子阶段。负责：追问捕获与严格顺序恢复、typing 状态、`OnWaitingLLMRequestEvent`/`OnLLMRequestEvent` 钩子、会话锁、`build_main_agent` 构建主 agent、恶意 host 拦截（`decoded_blocked`）、Live Mode（带 TTS 的 `run_live_agent`）、流式（`run_agent` + `STREAMING_RESULT`/`STREAMING_FINISH`）、非流式（`run_agent` 逐步 yield）、trace 记录、metrics 上报、历史记录持久化（`_save_to_history`）、provider stats 落库（`_record_internal_agent_stats`）、persona 自定义错误消息兜底。还包含模块级恶意 host 黑名单常量。
- **核心类**:
  - `InternalAgentSubStage(Stage)` — 职责：本地 Agent 模式的 LLM 调用 Stage。
    - 关键属性（`initialize`，按分组）:
      - 基础: `self.ctx`；`self.streaming_response`；`self.unsupported_streaming_strategy`；`self.max_step`（默认 30，含 #2622 的 bool 兜底）；`self.tool_call_timeout`（默认 60）；`self.tool_schema_mode`（默认 `"full"`，非 `skills_like`/`full` 时 warning 回退 `full`）；`self.show_tool_use`（默认 True）；`self.show_tool_call_result`（默认 False）；`self.buffer_intermediate_messages`（默认 False）；`self.show_reasoning`；`self.sanitize_context_by_modalities`（默认 False）；`self.kb_agentic_mode`。
      - 文件抽取: `self.file_extract_enabled`；`self.file_extract_prov`（默认 `moonshotai`）；`self.file_extract_msh_api_key`。
      - 上下文管理: `self.context_limit_reached_strategy`（默认 `truncate_by_turns`）；`self.llm_compress_instruction`；`self.llm_compress_keep_recent_ratio`（默认 0.15）；`self.llm_compress_provider_id`；`self.max_context_length`；`self.dequeue_context_length`（`min(max(1, val), max_context_length - 1)`，<=0 时回退 1）；`self.fallback_max_context_tokens`（默认 128000）。
      - 安全: `self.llm_safety_mode`（默认 True）；`self.safety_mode_strategy`（默认 `system_prompt`）。
      - 其它: `self.computer_use_runtime`；`self.sandbox_cfg`；`self.add_cron_tools`（`proactive_capability.add_cron_tools`，默认 True）；`self.conv_manager`；`self.main_agent_cfg: MainAgentBuildConfig`（用上述全部字段 + `provider_settings`、`subagent_orchestrator`、`timezone`、`max_quoted_fallback_images` 默认 20 构造）。
    - 关键方法:
      - `async initialize(self, ctx) -> None` — 读取上述配置并构造 `MainAgentBuildConfig`。
      - `async _send_llm_error_message(self, event, message: object) -> None` — `await event.send(MessageChain().message(str(message)))`。
      - `async process(self, event, provider_wake_prefix: str) -> AsyncGenerator[None, None]` — 主流程。初始化 `follow_up_capture=None`、`follow_up_consumed_marked=False`、`follow_up_activated=False`、`typing_requested=False`。`try`：决定 `streaming_response`（可被 `event.get_extra("enable_streaming")` 覆盖）；检测 `has_provider_request`/`has_valid_message`/`has_media_content`（`Image`/`File`/`Record`/`Video`）/`has_reply`，全为 False 时 debug 跳过 `return`。`follow_up_capture = try_capture_follow_up(event)`；若有 capture：`prepare_follow_up_capture` 拿到 `(consumed_marked, activated)`；若 consumed_marked：`set_extra("_follow_up_captured", {"target_run_id": ...})` 并 `return`。`try: typing_requested=True; await event.send_typing()` 失败 warning。`OnWaitingLLMRequestEvent` 钩子停则 `return`。`async with session_lock_manager.acquire_lock(umo)`：`agent_runner=None; runner_registered=False; try`：`build_cfg = replace(self.main_agent_cfg, provider_wake_prefix=..., streaming_response=...)`；`build_result = await build_main_agent(event=event, plugin_context=..., config=build_cfg, apply_reset=False)`；为 None 时取 `LLM_ERROR_MESSAGE_EXTRA_KEY` 错误消息发送后 `return`。取 `agent_runner`/`req`/`provider`/`reset_coro`。**恶意 host 拦截**：`api_base = provider.provider_config.get("api_base", "")`，对 `decoded_blocked` 中每个 host，若在 `api_base` 中则 error + 发送错误消息 + `return`。`stream_to_general = (unsupported_streaming_strategy == "turn_off" and not event.platform_meta.support_streaming_message)`。`OnLLMRequestEvent` 钩子（带 `req`）停则关闭 `reset_coro` 并 `return`。`if reset_coro: await reset_coro`。`register_active_runner(umo, agent_runner); runner_registered=True`。`action_type = event.get_extra("action_type")`。`event.trace.record("astr_agent_prepare", system_prompt=req.system_prompt, tools=req.func_tool.names() if req.func_tool else [], stream=streaming_response, chat_provider={id, model})`。**Live Mode**（`action_type == "live"`）：log；取 `tts_provider`，无则 warning；`event.set_result(MessageEventResult().set_result_content_type(STREAMING_RESULT).set_async_stream(run_live_agent(agent_runner, tts_provider, max_step, show_tool_use, show_tool_call_result, show_reasoning=..., buffer_intermediate_messages=...)))`；`yield`；若 `agent_runner.done() and (not is_stopped or was_aborted)`：`_save_to_history(...)`。**流式**（`streaming_response and not stream_to_general`）：`set_result` 为 `STREAMING_RESULT` + `run_agent(...)` 异步流；`yield`；若 `agent_runner.done()` 且 `final_llm_resp := agent_runner.get_final_llm_resp()` 存在：根据 `completion_text`/`result_chain`/空 构造 `chain`，`set_result(MessageEventResult(chain=chain, result_content_type=STREAMING_FINISH))`。**非流式**：`async for _ in run_agent(agent_runner, max_step, show_tool_use, show_tool_call_result, stream_to_general, show_reasoning=..., buffer_intermediate_messages=...): yield`。`final_resp = agent_runner.get_final_llm_resp()`；`event.trace.record("astr_agent_complete", stats=..., resp=final_resp.completion_text if final_resp else None)`；`asyncio.create_task(_record_internal_agent_stats(event, req, agent_runner, final_resp))`；若 `not is_stopped or was_aborted`：`_save_to_history(...)`；`asyncio.create_task(Metric.upload(llm_tick=1, model_name=provider.get_model(), provider_type=provider.meta().type))`。`finally`：`runner_registered and agent_runner is not None` 时 `unregister_active_runner(umo, agent_runner)`。`except Exception as e`：error 日志；`custom_error_message = extract_persona_custom_error_message_from_event(event)`；`error_text = custom_error_message or f"Error occurred while processing agent request: {e}"`；`await event.send(MessageChain().message(error_text))`。`finally`：`typing_requested` 时 `try: await event.stop_typing()`；`follow_up_capture` 时 `await finalize_follow_up_capture(capture, activated=follow_up_activated, consumed_marked=follow_up_consumed_marked)`。
      - `async _save_to_history(self, event, req: ProviderRequest, llm_response: LLMResponse | None, all_messages: list[Message], runner_stats: AgentStats | None, user_aborted: bool = False) -> None` — `not req or not req.conversation` 时 `return`；`not llm_response and not user_aborted` 时 `return`；若 `llm_response.role != "assistant"`：`not user_aborted` 时 `return`，否则补造 `LLMResponse(role="assistant", completion_text=llm_response.completion_text or "")`；`llm_response is None` 时补造空 assistant。`not completion_text and not req.tool_calls_result and not user_aborted` 时 debug 跳过。构造 `messages_to_save`：跳过首个 system 消息、跳过 `_no_save` 的 assistant/user。`checkpoint_id = event.get_extra("llm_checkpoint_id")`；`message_to_save = dump_messages_with_checkpoints(messages_to_save)`；若 `checkpoint_id` 是非空 str 则追加 `CheckpointMessageSegment(content=CheckpointData(id=checkpoint_id)).model_dump()`。`token_usage = llm_response.usage.total if llm_response.usage else None`（注释里有 `runner_stats.token_usage.total` 备选）；`await self.conv_manager.update_conversation(umo, req.conversation.cid, history=message_to_save, token_usage=token_usage)`。
- **核心函数**:
  - `async _record_internal_agent_stats(event, req: ProviderRequest | None, agent_runner: AgentRunner | None, final_resp: LLMResponse | None) -> None` — 持久化 provider stats。`agent_runner is None` 时 `return`；`provider`/`stats` 任一为 None 时 `return`；`try`：取 `provider_config`、`conversation_id`（`req.conversation.cid` 或 None）；按 `was_aborted()` → `"aborted"`、`final_resp.role == "err"` → `"error"`、否则 `"completed"` 决定 `status`；`await db_helper.insert_provider_stat(umo=..., conversation_id=..., provider_id=provider_config.get("id","") or provider.meta().id, provider_model=provider.get_model(), status=..., stats=stats.to_dict(), agent_type="internal")`；`except Exception` warning。
- **关键常量**:
  - `BLOCKED: set[str] = {"dGZid2h2d3IuY2xvdWQuc2VhbG9zLmlv", "a291cmljaGF0"}` — base64 编码的恶意 host 集合。
  - `decoded_blocked: list[str]` — 对 `BLOCKED` 解码得到的明文 host 列表（用于拦截 LLM provider 的 `api_base`）。
- **依赖**:
  - 标准库：`asyncio`、`base64`、`collections.abc.AsyncGenerator`、`dataclasses.replace`。
  - astrbot 内部：`astrbot.core`（`db_helper`、`logger`）；`astrbot.core.agent.message`（`CheckpointData`、`CheckpointMessageSegment`、`Message`、`dump_messages_with_checkpoints`）；`astrbot.core.agent.response.AgentStats`；`astrbot.core.astr_main_agent`（`LLM_ERROR_MESSAGE_EXTRA_KEY`、`MainAgentBuildConfig`、`MainAgentBuildResult`、`build_main_agent`）；`astrbot.core.message.components`（`File`、`Image`、`Record`、`Reply`、`Video`）；`astrbot.core.message.message_event_result`（`MessageChain`、`MessageEventResult`、`ResultContentType`）；`astrbot.core.persona_error_reply.extract_persona_custom_error_message_from_event`；`astrbot.core.pipeline.stage.Stage`；`astrbot.core.platform.astr_message_event.AstrMessageEvent`；`astrbot.core.provider.entities`（`LLMResponse`、`ProviderRequest`）；`astrbot.core.star.star_handler.EventType`；`astrbot.core.utils.metrics.Metric`；`astrbot.core.utils.session_lock.session_lock_manager`。
  - 相对导入：`.....astr_agent_run_util`（`AgentRunner`、`run_agent`、`run_live_agent`）、`....context`（`PipelineContext`、`call_event_hook`）、`...follow_up`（`FollowUpCapture`、`finalize_follow_up_capture`、`prepare_follow_up_capture`、`register_active_runner`、`try_capture_follow_up`、`unregister_active_runner`）。

### `pipeline/process_stage/method/agent_sub_stages/third_party.py`
- **职责**: `ThirdPartyAgentSubStage`——第三方 Agent Runner（Dify / Coze / Dashscope / DeerFlow）的 LLM 调用子阶段。负责：provider 唤醒前缀校验、从 `astrbot_config["provider"]` 取 provider 配置、构造 `ProviderRequest`（含 Image/Record 转 base64/路径）、解析 persona 自定义错误消息、`OnLLMRequestEvent` 钩子、按 `runner_type` 实例化对应 runner、`runner.reset`、流式（`_handle_streaming_response` + watchdog）与非流式（`_handle_non_streaming_response`）两条路径、runner 资源清理（`close_runner_once`）、metrics 上报。还提供模块级工具：`run_third_party_agent`、`_RunnerResultAggregator`、`_start_stream_watchdog`、`_close_runner_if_supported`。
- **核心类**:
  - `ThirdPartyAgentSubStage(Stage)` — 职责：第三方 Agent 调用 Stage。
    - 关键属性（`initialize`）: `self.ctx`；`self.conf = ctx.astrbot_config`；`self.runner_type = conf["provider_settings"]["agent_runner_type"]`；`self.prov_id = conf["provider_settings"].get(AGENT_RUNNER_TYPE_KEY.get(self.runner_type, ""), "")`；`self.streaming_response`；`self.unsupported_streaming_strategy`；`self.stream_consumption_close_timeout_sec: int`（`coerce_int_config` 解析 `third_party_stream_consumption_close_timeout_sec`，默认 30，min 1）。
    - 关键方法:
      - `async initialize(self, ctx) -> None` — 读取上述配置。
      - `async _resolve_persona_custom_error_message(self, event) -> str | None` — `try`：`conversation_persona_id = await resolve_event_conversation_persona_id(event, conversation_manager)`；`return await resolve_persona_custom_error_message(event=event, persona_manager=..., provider_settings=conf["provider_settings"], conversation_persona_id=...)`；`except Exception` debug 返回 None。
      - `async _handle_streaming_response(self, *, runner, event, custom_error_message, close_runner_once, mark_stream_consumed) -> AsyncGenerator[None, None]` — `aggregator = _RunnerResultAggregator()`；定义内部 `_stream_runner_chain()`：先 `mark_stream_consumed()`，`async for chain, is_error in run_third_party_agent(runner, stream_to_general=False, custom_error_message=...)`：`aggregator.add_chunk(chain, is_error)`，`is_error` 时 `set_extra(THIRD_PARTY_RUNNER_ERROR_EXTRA_KEY, True)`，`yield chain`；`finally: await close_runner_once()`。`event.set_result(MessageEventResult().set_result_content_type(STREAMING_RESULT).set_async_stream(_stream_runner_chain()))`；`yield`；若 `runner.done()`：`final_chain, is_runner_error = aggregator.finalize(runner.get_final_llm_resp())`；`set_extra(THIRD_PARTY_RUNNER_ERROR_EXTRA_KEY, is_runner_error)`；`set_result(MessageEventResult(chain=final_chain, result_content_type=STREAMING_FINISH))`。
      - `async _handle_non_streaming_response(self, *, runner, event, stream_to_general, custom_error_message) -> AsyncGenerator[None, None]` — `aggregator = _RunnerResultAggregator()`；`async for chain, is_error in run_third_party_agent(runner, stream_to_general=..., custom_error_message=...)`：`aggregator.add_chunk`，`is_error` 时 set extra，`yield`；`final_chain, is_runner_error = aggregator.finalize(runner.get_final_llm_resp())`；`set_extra(THIRD_PARTY_RUNNER_ERROR_EXTRA_KEY, is_runner_error)`；`result_content_type = AGENT_RUNNER_ERROR if is_runner_error else LLM_RESULT`；`set_result(MessageEventResult(chain=final_chain, result_content_type=...))`；再 `yield` 一次保持调度器进度一致。
      - `async process(self, event, provider_wake_prefix: str) -> AsyncGenerator[None, None]` — `req = None`；若 `provider_wake_prefix` 且 `not event.message_str.startswith(...)` `return`。`self.prov_cfg = next((p for p in astrbot_config["provider"] if p["id"] == self.prov_id), {})`；无 `prov_id` / 无 `prov_cfg` 时 error 并 `return`。构造 `req = ProviderRequest()`：`session_id = umo`；`prompt = event.message_str[len(provider_wake_prefix):]`；遍历 `event.message_obj.message`：`Image` → `convert_to_base64` 入 `req.image_urls`，`Record` → `convert_to_file_path` 入 `req.audio_urls`。`prompt` 与图片/音频皆空时 `return`。`custom_error_message = await self._resolve_persona_custom_error_message(event)`；`set_persona_custom_error_message_on_event(event, custom_error_message)`。`OnLLMRequestEvent` 钩子（带 req）停则 `return`。按 `runner_type` 实例化：`"dify"` → `DifyAgentRunner[AstrAgentContext]()`；`"coze"` → `CozeAgentRunner[...]()`；`"dashscope"` → `DashscopeAgentRunner[...]()`；`DEERFLOW_PROVIDER_TYPE` → `DeerFlowAgentRunner[...]()`；其它 `raise ValueError`。构造 `astr_agent_ctx = AstrAgentContext(context=plugin_manager.context, event=event)`。决定 `streaming_response`（可被 extra 覆盖）、`stream_to_general`、`streaming_used = streaming_response and not stream_to_general`。`runner_closed=False; stream_consumed=False; stream_watchdog_task=None`；定义 `close_runner_once()` 与 `mark_stream_consumed()` 闭包。`try`：`await runner.reset(request=req, run_context=AgentContextWrapper(context=astr_agent_ctx, tool_call_timeout=120), agent_hooks=MAIN_AGENT_HOOKS, provider_config=self.prov_cfg, streaming=streaming_response)`；`streaming_used` 时启动 `_start_stream_watchdog(...)` 并 `async for _ in self._handle_streaming_response(...): yield`；否则 `async for _ in self._handle_non_streaming_response(...): yield`。`finally`：watchdog 未完成且（已消费或已关闭）时 `cancel`；`not streaming_used` 时 `await close_runner_once()`。最后 `asyncio.create_task(Metric.upload(llm_tick=1, model_name=self.runner_type, provider_type=self.runner_type))`。
  - `_RunnerResultAggregator` — 职责：聚合第三方 runner 流式/非流式产出的 chain 与错误标志。
    - 关键属性: `self.merged_chain: list = []`；`self.has_error = False`。
    - 关键方法:
      - `add_chunk(self, chain: MessageChain, is_error: bool) -> None` — `merged_chain.extend(chain.chain or [])`；`is_error` 时 `has_error = True`。
      - `finalize(self, final_resp: LLMResponse | None) -> tuple[list, bool]` — `not final_resp or not final_resp.result_chain`：有 `merged_chain` 时 warning `RUNNER_NO_FINAL_RESPONSE_LOG` 返回 `(merged_chain, has_error)`；否则 warning `RUNNER_NO_RESULT_LOG`，构造 `RUNNER_NO_RESULT_FALLBACK_MESSAGE` chain 返回 `(..., True)`。否则 `final_chain = final_resp.result_chain.chain or []`；`is_runner_error = has_error or final_resp.role == "err"`；返回 `(final_chain, is_runner_error)`。
- **核心函数**:
  - `async run_third_party_agent(runner: BaseAgentRunner, stream_to_general: bool = False, custom_error_message: str | None = None) -> AsyncGenerator[tuple[MessageChain, bool], None]` — 运行第三方 agent runner 并转换响应。`async for resp in runner.step_until_done(max_step=30)`：`resp.type == "streaming_delta"` → `stream_to_general` 时 `continue`，否则 `yield resp.data["chain"], False`；`"llm_result"` → `stream_to_general` 时 `yield resp.data["chain"], False`；`"err"` → `yield resp.data["chain"], True`。`except Exception as e`：error 日志；`err_msg = custom_error_message or (默认格式含 Error Type 与 Message)`；`yield MessageChain().message(err_msg), True`。
  - `_start_stream_watchdog(*, timeout_sec: int, is_stream_consumed: Callable[[], bool], close_runner_once: Callable[[], Awaitable[None]]) -> asyncio.Task[None]` — 创建并返回 watchdog task：`await asyncio.sleep(timeout_sec)`（被 cancel 时 `return`），醒来后若 `not is_stream_consumed()` 则 warning 并 `await close_runner_once()`（异常 warning）。
  - `async _close_runner_if_supported(runner: BaseAgentRunner) -> None` — 取 `runner.close`，不可调用则 `return`；`close_result = close_callable()`，`inspect.isawaitable` 时 `await`；异常 warning。
- **关键常量**:
  - `AGENT_RUNNER_TYPE_KEY: dict = {"dify": "dify_agent_runner_provider_id", "coze": "coze_agent_runner_provider_id", "dashscope": "dashscope_agent_runner_provider_id", DEERFLOW_PROVIDER_TYPE: DEERFLOW_AGENT_RUNNER_PROVIDER_ID_KEY}` — runner 类型到配置 provider id 键名的映射。
  - `THIRD_PARTY_RUNNER_ERROR_EXTRA_KEY = "_third_party_runner_error"`。
  - `STREAM_CONSUMPTION_CLOSE_TIMEOUT_SEC = 30`。
  - `RUNNER_NO_RESULT_FALLBACK_MESSAGE = "Agent Runner did not return any result."`。
  - `RUNNER_NO_FINAL_RESPONSE_LOG = "Agent Runner returned no final response, fallback to streamed error/result chain."`。
  - `RUNNER_NO_RESULT_LOG = "Agent Runner did not return final result."`。
- **依赖**:
  - 标准库：`asyncio`、`inspect`、`collections.abc`（`AsyncGenerator`、`Awaitable`、`Callable`）、`typing.TYPE_CHECKING`。
  - astrbot 内部：`astrbot.core`（`astrbot_config`、`logger`）；`astrbot.core.agent.runners.coze.coze_agent_runner.CozeAgentRunner`；`astrbot.core.agent.runners.dashscope.dashscope_agent_runner.DashscopeAgentRunner`；`astrbot.core.agent.runners.deerflow.constants`（`DEERFLOW_AGENT_RUNNER_PROVIDER_ID_KEY`、`DEERFLOW_PROVIDER_TYPE`）；`astrbot.core.agent.runners.deerflow.deerflow_agent_runner.DeerFlowAgentRunner`；`astrbot.core.agent.runners.dify.dify_agent_runner.DifyAgentRunner`；`astrbot.core.astr_agent_hooks.MAIN_AGENT_HOOKS`；`astrbot.core.message.components`（`Image`、`Record`）；`astrbot.core.message.message_event_result`（`MessageChain`、`MessageEventResult`、`ResultContentType`）；`astrbot.core.persona_error_reply`（`resolve_event_conversation_persona_id`、`resolve_persona_custom_error_message`、`set_persona_custom_error_message_on_event`）；`astrbot.core.pipeline.stage.Stage`；`astrbot.core.platform.astr_message_event.AstrMessageEvent`；`astrbot.core.provider.entities.ProviderRequest`；`astrbot.core.star.star_handler.EventType`；`astrbot.core.utils.config_number.coerce_int_config`；`astrbot.core.utils.metrics.Metric`。
  - `TYPE_CHECKING` 下：`astrbot.core.agent.runners.base.BaseAgentRunner`、`astrbot.core.provider.entities.LLMResponse`。
  - 相对导入：`.....astr_agent_context`（`AgentContextWrapper`、`AstrAgentContext`）、`....context`（`PipelineContext`、`call_event_hook`）。

---

## 附：阶段执行顺序与归属速查

| 顺序 | Stage 类名 | 所在文件 | 一句话职责 |
|---|---|---|---|
| 1 | `WakingCheckStage` | `waking_check/stage.py` | 判断是否唤醒机器人，激活插件 handler |
| 2 | `WhitelistCheckStage` | `whitelist_check/stage.py` | 会话白名单检查 |
| 3 | `SessionStatusCheckStage` | `session_status_check/stage.py` | 会话整体启用状态检查 |
| 4 | `RateLimitStage` | `rate_limit_check/stage.py` | Fixed Window 会话限流（stall/discard） |
| 5 | `ContentSafetyCheckStage` | `content_safety_check/stage.py` | 文本内容安全检查（关键词 / 百度 AIP） |
| 6 | `PreProcessStage` | `preprocess_stage/stage.py` | 路径映射、媒体归一化、STT |
| 7 | `ProcessStage` | `process_stage/stage.py` | 插件 handler 调用 + LLM/Agent 调用编排 |
| 8 | `ResultDecorateStage` | `result_decorate/stage.py` | 前缀、分段、TTS、t2i、转发、@/引用装饰 |
| 9 | `RespondStage` | `respond/stage.py` | 实际发送（含分段定时、流式、去重） |

`ProcessStage` 内部委托 `StarRequestSubStage`（插件调用）与 `AgentRequestSubStage`（LLM 调用）；后者再按 `agent_runner_type` 委托 `InternalAgentSubStage`（local）或 `ThirdPartyAgentSubStage`（dify/coze/dashscope/deerflow）。`InternalAgentSubStage` 借助 `follow_up.py` 的追问捕获机制处理同一会话的连续消息。


---

## 章节四：core/platform（平台适配）

# AstrBot core/platform 模块逐文件详解

本文档对 AstrBot 平台模块（`astrbot/core/platform`）下的每一个 `.py` 文件进行逐文件、逐结构的详尽分析，覆盖约 70 个 `.py` 文件。内容按"核心平台文件"与"平台适配器源码（`sources/` 子目录，按平台分组）"两大板块组织。

对于每个文件，分析包含以下小节（视文件实际内容酌情增减）：

- **职责**：该文件在整个平台层中承担的角色。
- **核心类**：定义的主要类及其作用。
- **核心函数/方法**：关键函数与方法的功能说明。
- **关键常量**：模块级常量、枚举值。
- **依赖**：导入的第三方库与 AstrBot 内部模块。

> 说明：平台适配器普遍遵循同一套范式（继承 `Platform`/`AstrMessageEvent`，实现 `run`/`terminate`/`convert_message`/`send`/`send_streaming` 等），因此对于模式高度相似的适配器，在保留全部关键类名、方法名与常量的前提下，描述会适度精简，避免重复铺陈。

---

## 一、核心平台文件 (`core/platform/`)

### `__init__.py`

- **职责**：平台模块的公共出口，聚合对外暴露的核心数据结构与基类。
- **导出**：`AstrBotMessage`、`AstrMessageEvent`、`Group`、`MessageMember`、`MessageType`、`Platform`、`PlatformMetadata`（通过 `__all__` 声明）。
- **依赖**：从同目录的 `astr_message_event`、`astrbot_message`、`platform`、`platform_metadata` 导入。

### `platform.py`

- **职责**：定义所有平台适配器的抽象基类 `Platform`，统一适配器生命周期、状态管理、事件提交与统一 Webhook 接口。
- **核心类**：
  - `PlatformStatus(Enum)`：平台运行状态枚举，取值 `PENDING`/`RUNNING`/`ERROR`/`STOPPED`。
  - `PlatformError`（`@dataclass`）：平台错误信息，字段 `message`、`timestamp`、`traceback`。
  - `Platform(abc.ABC)`：适配器抽象基类。
- **`Platform` 关键成员**：
  - `__init__(config, event_queue)`：保存 `config`、`_event_queue`，生成 `client_self_id`（uuid），初始化状态为 `PENDING`。
  - 属性 `status`/`errors`/`last_error`：运行状态与错误访问。
  - `record_error(message, traceback_str)`、`clear_errors()`：错误记录与清除。
  - `unified_webhook()`：判断是否启用统一 Webhook 模式（`unified_webhook_mode` 且 `webhook_uuid` 同时存在）。
  - `get_stats()`：返回平台统计信息字典（含 id、状态、错误数、最近错误、元数据等）。
  - 抽象方法 `run()`（返回协程）、`meta()`（返回 `PlatformMetadata`）。
  - `terminate()`：默认空实现，供子类重写。
  - `send_by_session(session, message_chain)`：通过可持久化会话发送消息，默认触发 `Metric.upload`。
  - `commit_event(event)`：将 `AstrMessageEvent` 放入事件队列。
  - `create_event(message)`：默认构造一个基础 `AstrMessageEvent`，供子类重写。
  - `get_client()`：返回平台客户端对象（默认返回 `None`）。
  - `webhook_callback(request)`：统一 Webhook 回调入口，默认抛出 `NotImplementedError`。
- **依赖**：`asyncio`、`uuid`、`dataclasses`、`datetime`、`enum`；AstrBot 的 `MessageChain`、`Metric`、`AstrMessageEvent`、`AstrBotMessage`、`MessageSesion`、`PlatformMetadata`。

### `astr_message_event.py`

- **职责**：定义消息事件基类 `AstrMessageEvent`，是所有平台事件类的共同父类，封装消息结果、会话、流式发送、LLM 请求、临时文件清理等通用能力。
- **核心类**：`AstrMessageEvent(abc.ABC)`。
- **关键属性**：`message_str`、`message_obj`、`platform_meta`、`role`、`is_wake`、`is_at_or_wake_command`、`_extras`、`_force_stopped`、`session`(`MessageSession`)、`unified_msg_origin`、`_result`(`MessageEventResult`)、`created_at`、`trace`/`span`(`TraceSpan`)、`_has_send_oper`、`call_llm`、`_temporary_local_files`、`plugins_name`。
- **核心方法**：
  - 会话/身份：`get_platform_name()`、`get_platform_id()`、`get_session_id()`、`get_group_id()`、`get_self_id()`、`get_sender_id()`、`get_sender_name()`、`get_message_type()`、`is_private_chat()`、`is_wake_up()`、`is_admin()`。
  - 消息：`get_message_str()`、`get_messages()`、`get_message_outline()`（将消息链转为概要字符串，图片→`[图片]`，At→`[At:id]` 等）、`_outline_chain(chain)`。
  - 额外信息：`set_extra`/`get_extra`/`clear_extra`。
  - 临时文件：`track_temporary_local_file(path)`、`cleanup_temporary_local_files()`。
  - 结果控制：`set_result(result)`、`stop_event()`、`continue_event()`、`is_stopped()`、`should_call_llm(call_llm)`、`get_result()`、`clear_result()`、`make_result()`、`plain_result(text)`、`image_result(url_or_path)`、`chain_result(chain)`。
  - LLM 请求：`request_llm(prompt, ...)` 返回 `ProviderRequest`。
  - 发送：`send(message)`（默认触发 `Metric.upload`，使用 BLAKE2 哈希 sender_id）、`send_streaming(generator, use_fallback)`（默认仅打点）、`send_typing()`/`stop_typing()`（默认空）、`react(emoji)`（默认发送一条包含表情的文本）、`get_group(group_id)`。
  - 流式 Fallback：`process_buffer(buffer, pattern)`，按正则切分缓冲区并逐段发送，用于不支持流式的平台。
- **依赖**：`abc`、`asyncio`、`hashlib`、`os`、`re`、`uuid`、`time`；`ToolSet`、`Conversation`、消息组件（`At`/`AtAll`/`Face`/`Forward`/`Image`/`Plain`/`Reply` 等）、`MessageChain`/`MessageEventResult`、`MessageType`、`ProviderRequest`、`Metric`、`TraceSpan`。

### `astrbot_message.py`

- **职责**：定义 AstrBot 统一消息对象 `AstrBotMessage` 及其关联数据结构 `MessageMember`、`Group`。
- **核心类**：
  - `MessageMember`（`@dataclass`）：字段 `user_id`、`nickname`。
  - `Group`（`@dataclass`）：字段 `group_id`、`group_name`、`group_avatar`、`group_owner`、`group_admins`、`members`。
  - `AstrBotMessage`：统一消息对象，属性 `type`(`MessageType`)、`self_id`、`session_id`、`message_id`、`group`、`sender`、`message`(消息链)、`message_str`、`raw_message`、`timestamp`；提供 `group_id` 属性（向后兼容，读写委托给 `Group`）。
- **依赖**：`time`、`dataclasses`；`BaseMessageComponent`、`MessageType`。

### `manager.py`

- **职责**：平台管理器 `PlatformManager`，负责按配置动态加载、运行、终止各平台适配器实例，并维护任务与统计。
- **核心类**：
  - `PlatformTasks`（`@dataclass`）：字段 `run`、`wrapper`（两个 `asyncio.Task`）。
  - `PlatformManager`：管理器主体。
- **`PlatformManager` 关键方法**：
  - `__init__(config, event_queue)`：保存 `astrbot_config`、`platforms_config`、`settings`、`event_queue`，初始化 `platform_insts`、`_inst_map`、`_platform_tasks`。
  - `_is_valid_platform_id`/`_sanitize_platform_id`：校验/清洗平台 ID（不允许包含 `:` 或 `!`）。
  - `_start_platform_task(task_name, inst)`：创建 `run` 与 `wrapper` 两个任务。
  - `_stop_platform_task(client_id)`/`_terminate_inst_and_tasks(inst)`：停止任务并调用 `inst.terminate()`。
  - `initialize()`：遍历配置初始化所有适配器，并额外启动一个 `WebChatAdapter`。
  - `load_platform(platform_config)`：根据 `type` 动态导入对应适配器模块（`match-case` 覆盖 aiocqhttp/qq_official/qq_official_webhook/lark/dingtalk/telegram/wecom/wecom_ai_bot/weixin_official_account/discord/misskey/weixin_oc/slack/satori/line/kook/mattermost），从 `platform_cls_map` 实例化并启动；加载完成后触发 `OnPlatformLoadedEvent` 钩子。
  - `_task_wrapper(task, platform)`：包装运行任务，设置状态、捕获异常并 `record_error`。
  - `reload(platform_config)`/`terminate_platform(platform_id)`/`terminate()`：重载、终止单个或全部平台。
  - `get_insts()`/`get_all_stats()`：获取实例列表与汇总统计。
- **依赖**：`asyncio`、`traceback`、`dataclasses`；`AstrBotConfig`、`star_handlers_registry`/`star_map`/`EventType`、`ensure_platform_webhook_config`、`Platform`/`PlatformStatus`、`platform_cls_map`、`WebChatAdapter`。

### `message_session.py`

- **职责**：定义消息会话标识 `MessageSession`，作为消息来源的唯一标识串。
- **核心类**：`MessageSession`（`@dataclass`），字段 `platform_name`、`message_type`(`MessageType`)、`session_id`，`platform_id` 在 `__post_init__` 中自动等于 `platform_name`。
- **关键方法**：`__str__()` 返回 `platform_id:message_type:session_id`；静态方法 `from_str(session_str)` 反向解析。
- **兼容**：`MessageSesion = MessageSession`（向后兼容别名）。
- **依赖**：`dataclasses`；`MessageType`。

### `message_type.py`

- **职责**：定义消息类型枚举。
- **核心类**：`MessageType(Enum)`，取值 `GROUP_MESSAGE="GroupMessage"`、`FRIEND_MESSAGE="FriendMessage"`、`OTHER_MESSAGE="OtherMessage"`。
- **依赖**：`enum`。

### `platform_metadata.py`

- **职责**：定义平台元数据结构。
- **核心类**：`PlatformMetadata`（`@dataclass`），字段 `name`、`description`、`id`、`default_config_tmpl`、`adapter_display_name`、`logo_path`、`support_streaming_message`(默认 `True`)、`support_proactive_message`(默认 `True`)、`module_path`、`i18n_resources`、`config_metadata`。
- **依赖**：`dataclasses`。

### `register.py`

- **职责**：提供平台适配器注册装饰器与注册表维护，支持插件热重载时按模块路径注销。
- **模块级变量**：`platform_registry: list[PlatformMetadata]`、`platform_cls_map: dict[str, type]`。
- **核心函数**：
  - `register_platform_adapter(adapter_name, desc, default_config_tmpl=None, adapter_display_name=None, logo_path=None, support_streaming_message=True, i18n_resources=None, config_metadata=None)`：带参装饰器，构造 `PlatformMetadata` 并登记到注册表；重名会抛 `ValueError`；自动为默认配置补充 `type`/`enable`/`id`。
  - `unregister_platform_adapters_by_module(module_path_prefix)`：根据模块路径前缀注销适配器，返回被注销的适配器名称列表。
- **依赖**：`astrbot.core.logger`；`PlatformMetadata`。

### `webhook_server.py`

- **职责**：基于 FastAPI + Hypercorn 的轻量 Webhook 服务器，供需要 HTTP 回调的平台适配器复用。
- **核心类/函数**：
  - `WebhookRequest`：对 FastAPI `Request` 的薄封装，提供 `args`、`headers`、`method`、`json`、`get_data()`、`get_json(force, silent)`。
  - `webhook_response_from_result(result)`：将适配器回调返回值转换为 FastAPI 响应（支持 `Response`、`tuple`、`dict`/`list`、`str`/`bytes`）。
  - `FastAPIWebhookServer`：封装 `FastAPI` 应用；方法 `add_url_rule(path, view_func, methods)`、`route(path, methods)` 装饰器、`run_task(host, port, shutdown_trigger)`（通过 `hypercorn.asyncio.serve` 启动）、`shutdown()`。
- **依赖**：`inspect`；`fastapi.FastAPI`/`Request`/`Response`/`JSONResponse`；`hypercorn.asyncio.serve`、`hypercorn.config.Config`。

---

## 二、平台适配器源码 (`core/platform/sources/`)

### 2.1 aiocqhttp/ (OneBot v11)

#### `aiocqhttp/aiocqhttp_platform_adapter.py`

- **职责**：OneBot v11 标准适配器，支持反向 WebSocket，对接 NapCat/Lagrange/go-cqhttp 等协议端。
- **核心类**：`AiocqhttpAdapter(Platform)`，注册名 `aiocqhttp`，`support_streaming_message=False`。
- **关键方法**：
  - `__init__`：读取 `ws_reverse_host`/`ws_reverse_port`/`ws_reverse_token`，创建 `CQHttp` 实例；注册 `on_request`/`on_notice`/`on_message("group")`/`on_message("private")`/`on_websocket_connection` 回调。
  - `send_by_session(session, message_chain)`：根据会话类型调用 `AiocqhttpMessageEvent.send_message`。
  - `convert_message(event)`：按 `post_type` 分发到 `_convert_handle_message_event`/`_convert_handle_notice_event`/`_convert_handle_request_event`；屏蔽 QQ 管家（user_id `2854196310`）。
  - `_convert_handle_message_event(event, get_reply=True)`：解析 OneBot 消息段（text/file/reply/at/mface/markdown 等），处理 @用户信息查询、回复消息嵌套、文件 URL 获取（区分 Lagrange 与 NapCat）。
  - `run()`：启动 `bot.run_task`，默认 `0.0.0.0:6199`。
  - `terminate()`：设置 `shutdown_event` 并关闭反向 WS 连接（`_close_reverse_ws_connections`）。
  - `create_event(message)`：构造 `AiocqhttpMessageEvent`。
- **依赖**：`aiocqhttp.CQHttp`/`Event`/`ActionFailed`；AstrBot 消息组件、`AiocqhttpMessageEvent`。

#### `aiocqhttp/aiocqhttp_message_event.py`

- **职责**：aiocqhttp 消息事件实现，负责将 `MessageChain` 转为 OneBot 消息段并发送。
- **核心类**：`AiocqhttpMessageEvent(AstrMessageEvent)`。
- **关键方法**：
  - `_from_segment_to_dict(segment)`：将消息组件转为 OneBot dict（Image/Record 转 base64，File 处理绝对路径转 `file:` URI）。
  - `_parse_onebot_json(message_chain)`：解析为 OneBot JSON 段列表，At 后自动插入空格。
  - `_dispatch_send(bot, event, is_group, session_id, messages)`：按群/私聊调用 `send_group_msg`/`send_private_msg`，兜底 `bot.send`。
  - `send_message(cls, bot, message_chain, event, is_group, session_id)`：统一发送入口，处理合并转发（`Node`/`Nodes`）与文件消息的分段发送。
  - `send(message)`：从 `raw_message` 取 event 并调用 `send_message`。
  - `send_streaming(generator, use_fallback)`：默认缓冲合并发送；`use_fallback=True` 时按句末标点切分逐段发送。
  - `get_group(group_id)`：通过 `get_group_info`/`get_group_member_list` 构造 `Group` 对象。
- **依赖**：`aiocqhttp.CQHttp`/`Event`；`At`/`File`/`Image`/`Node`/`Nodes`/`Plain`/`Record`/`Video`、`Group`/`MessageMember`。

### 2.2 dingtalk/ (钉钉)

#### `dingtalk/dingtalk_adapter.py`

- **职责**：钉钉机器人官方 API 适配器，基于 `dingtalk-stream` WebSocket 长连接，支持流式消息标记。
- **关键常量**：`DINGTALK_RECONNECT_INITIAL_DELAY=10`、`DINGTALK_RECONNECT_MAX_DELAY=300`、`DINGTALK_RECONNECT_STABLE_SECONDS=300`；`_dingtalk_reconnect_delay(retry_count)` 指数退避。
- **核心类**：
  - `MyEventHandler(dingtalk_stream.EventHandler)`：通用事件处理器。
  - `DingtalkPlatformAdapter(Platform)`：注册名 `dingtalk`，`support_streaming_message=True`。内部定义 `AstrCallbackClient(ChatbotHandler)` 处理聊天消息回调。
- **关键方法**：
  - `__init__`：读取 `client_id`/`client_secret`，创建 `DingTalkStreamClient` 并注册回调。
  - `_id_to_sid(dingtalk_id)`：剥离 `$:LWCP_v1:$` 前缀。
  - `convert_msg(message)`：解析 text/picture/richText/audio|voice/file 类型消息，下载文件（`download_ding_file`）。
  - `_remember_sender_binding`：将私聊 sender_id 与 staff_id 映射持久化到 `sp`。
  - `send_by_session`/`send_message_chain_with_incoming`：通过 HTTP API 发送群消息（`groupMessages/send`）或私聊消息（`oToMessages/batchSend`）。
  - `_send_message_chain(target_type, target_id, robot_code, message_chain, at_str)`：按组件类型发送 sampleMarkdown/sampleImageMsg/sampleAudio/sampleVideo/sampleFile。
  - `upload_media(file_path, media_type)`/`upload_image(image)`：上传媒体文件获取 `media_id`。
  - `_prepare_voice_for_dingtalk(input_path)`：语音优先转 OGG(Opus)，失败回退 AMR。
  - `get_access_token()`：通过 SDK 或直接调用 OAuth2 接口获取 token。
  - `run()`：在独立线程中运行 SDK `start()`，带重连与指数退避。
  - `terminate()`：通过 monkey-patch `open_connection` 抛 `KeyboardInterrupt("Graceful shutdown")` 实现优雅关闭。
- **依赖**：`aiohttp`、`dingtalk_stream`；`MediaResolver`/`convert_audio_format`/`convert_video_format`/`extract_video_cover`/`get_media_duration`、`sp`、`DingtalkMessageEvent`。

#### `dingtalk/dingtalk_event.py`

- **职责**：钉钉消息事件实现。
- **核心类**：`DingtalkMessageEvent(AstrMessageEvent)`，持有 `client` 与 `adapter`。
- **关键方法**：`send(message)` 委托 `adapter.send_message_chain_with_incoming`；`send_streaming` 缓冲合并后调用 `send`。

#### `dingtalk/app_registration.py`

- **职责**：钉钉应用扫码注册流程（device code 流），用于无应用时扫码创建钉钉应用。
- **核心类**：`DingtalkAppRegistration`（`@dataclass`，字段 `device_code`/`user_code`/`verification_uri`/`verification_uri_complete`/`expires_in`/`interval`）。
- **关键函数**：`dingtalk_registration_base_url()`/`dingtalk_registration_source()`（读取环境变量，默认 `https://oapi.dingtalk.com`/`DING_DWS_CLAW`）、`_post_registration(path, payload)`、`request_dingtalk_app_registration()`（init→begin）、`poll_dingtalk_app_registration_once(device_code)`、`dingtalk_registration_poll_result(raw)`（解析 WAITING/SUCCESS/FAIL/EXPIRED）。
- **依赖**：`aiohttp`。

### 2.3 discord/ (Discord)

#### `discord/discord_platform_adapter.py`

- **职责**：基于 Pycord 的 Discord 适配器，支持斜杠指令注册与 @唤醒。
- **核心类**：`DiscordPlatformAdapter(Platform)`，注册名 `discord`，`support_streaming_message=False`。
- **关键方法**：
  - `__init__`：读取 `discord_token`/`discord_proxy`/`discord_allow_bot_messages`/`discord_command_register`/`discord_guild_id_for_debug`/`discord_activity_name`。
  - `run()`：创建 `DiscordBotClient`，设置 `on_message_received`/`on_ready_once_callback`（在其中调用 `_collect_and_register_commands` 与 `change_presence`），启动轮询并等待关闭。
  - `convert_message(data)`：剥离 User/Role Mention，处理 attachments（image/audio/file），音频转 wav。
  - `handle_msg(message, followup_webhook)`：判断斜杠指令或 @提及，设置 `is_wake`/`is_at_or_wake_command`。
  - `_collect_and_register_commands()`：从 `star_handlers_registry` 收集指令，创建 `discord.SlashCommand`（带 `params` 选项），调用 `sync_commands()`；处理每日指令配额错误（code 30034）。
  - `_create_dynamic_callback(cmd_name)`：为每个指令创建回调，先 `ctx.defer()`（2.5s 超时），再构建 `AstrBotMessage` 并交给 `handle_msg`。
  - `_extract_command_info(event_filter, handler_metadata)`：从 `CommandFilter`/`CommandGroupFilter` 提取指令名与描述，校验 Discord 斜杠指令命名规范。
  - `send_by_session`/`terminate`：通过 channel 发送；终止时清理指令、取消轮询任务、关闭客户端。
- **依赖**：`discord`(Pycord)、`DiscordBotClient`、`DiscordPlatformEvent`、`CommandFilter`/`CommandGroupFilter`/`star_handlers_registry`。

#### `discord/discord_platform_event.py`

- **职责**：Discord 消息事件实现（基于摘要信息，处理消息发送与流式回退）。
- **核心类**：`DiscordPlatformEvent(AstrMessageEvent)`，持有 `client` 与可选 `interaction_followup_webhook`。
- **说明**：支持通过 `send` 发送文本/图片/音频/文件/视频；`send_streaming` 采用缓冲合并发送；斜杠指令场景通过 followup webhook 回复。

#### `discord/client.py`

- **职责**：封装 Pycord 客户端 `DiscordBotClient`，管理连接、消息接收与指令同步。
- **核心类**：`DiscordBotClient`。
- **说明**：提供 `start_polling()`、`on_message_received` 回调、`on_ready_once_callback` 钩子、`change_presence`、`sync_commands` 等能力，处理代理与 bot 消息过滤。

#### `discord/components.py`

- **职责**：Discord 相关组件辅助定义（如消息构建、附件处理等辅助工具）。
- **说明**：为适配器与事件类提供共享的组件级工具函数。

### 2.4 kook/ (KOOK)

#### `kook/kook_adapter.py`

- **职责**：KOOK（原 Kaiheila）适配器，基于 WebSocket，支持 KMarkdown 与卡片消息。
- **关键常量**：`KOOK_AT_SELECTOR_REGEX`（匹配 `(met|rol)xxx(tag)`）、`AT_MENTION_PREFIX_REGEX`。
- **核心类**：`KookPlatformAdapter(Platform)`，注册名 `kook`。
- **关键方法**：
  - `__init__`：构造 `KookConfig`、`KookClient`、`KookRolesRecord`。
  - `_on_received(event)`：处理 KMARKDOWN/CARD 消息与 SYSTEM 事件（角色更新时清缓存）。
  - `run()`/`_main_loop()`：连接与重连，指数退避，超过 `max_consecutive_failures` 停止。
  - `convert_message(data)`：按 `channel_type`（GROUP/PERSON/BROADCAST）设置会话类型，按 `type`（KMARKDOWN/CARD）解析。
  - `_parse_kmarkdown_message(data)`：解析 KMarkdown，处理 @用户与 @角色（角色匹配 bot 时替换为 bot_id）。
  - `_parse_card_message(data)`：解析卡片消息，提取 Section/Container/ImageGroup/Header/File 模块。
  - `_convert_text_message_to_component(content, raw_content, mention_role_part, guild_id, mention_name_map)`：将 KMarkdown 转为消息组件，处理角色 mention 与 bot 自身判断。
  - `send_by_session`/`create_event`/`handle_msg`。
- **依赖**：`KookClient`/`KookConfig`/`KookEvent`/`KookRolesRecord`/`kook_types` 多个类、`MediaResolver`。

#### `kook/kook_client.py`

- **职责**：KOOK WebSocket 客户端封装，管理连接、心跳、Bot 信息获取与 HTTP 调用。
- **核心类**：`KookClient`。
- **说明**：提供 `connect()`/`close()`/`get_bot_info()`/`wait_until_closed()`/`http_client` 等能力，维护 `bot_id`/`bot_nickname`/`bot_username`。

#### `kook/kook_config.py`

- **职责**：KOOK 适配器配置类，基于 pydantic。
- **核心类**：`KookConfig`，从 dict 构造，包含 token、id、重连参数（`max_consecutive_failures`、`max_retry_delay`）等字段，提供 `pretty_jsons()`。

#### `kook/kook_event.py`

- **职责**：KOOK 消息事件实现。
- **核心类**：`KookEvent(AstrMessageEvent)`，持有 `KookClient`。
- **说明**：`send` 将 `MessageChain` 转为 KOOK 消息（KMarkdown/卡片），支持文本/图片/文件/音频/视频；`send_streaming` 缓冲合并发送。

#### `kook/kook_types.py`

- **职责**：KOOK 协议数据模型定义，基于 pydantic。
- **关键常量/类**：
  - `KookApiPaths`：API 路径常量（`BASE_URL`、`USER_ME`、`GATEWAY_INDEX`、`ASSET_CREATE`、`CHANNEL_MESSAGE_CREATE`、`DIRECT_MESSAGE_CREATE` 等）。
  - 枚举：`KookMentionTagName`(`met`/`rol`)、`KookMessageType`(TEXT=1, IMAGE=2, VIDEO=3, FILE=4, AUDIO=8, KMARKDOWN=9, CARD=10, SYSTEM=255)、`KookModuleType`、`KookRoleExtraType`。
  - 类型别名：`ThemeType`、`SizeType`、`SectionMode`、`CountdownMode`。
  - 数据类基类：`KookBaseReceiveDataClass`/`KookBaseSendDataClass`（控制 `to_dict`/`to_json` 的 `exclude_none`/`exclude_unset` 默认值）。
  - 卡片模型：`KookCardModelBase`、`PlainTextElement`、`KmarkdownElement`、`ImageElement`、`ButtonElement`、`ParagraphStructure`、`HeaderModule`、`SectionModule`、`ImageGroupModule`、`ContainerModule`、`ActionGroupModule`、`ContextModule`、`DividerModule`、`FileModule`、`CountdownModule`、`InviteModule`，以及联合类型 `AnyElement`/`AnyModule`。
- **依赖**：`pydantic`。

#### `kook/kook_roles_record.py`

- **职责**：KOOK 频道角色缓存管理，用于判断 bot 是否属于某角色。
- **核心类**：`KookRolesRecord`。
- **说明**：提供 `has_role_in_channel(role_id, guild_id)`、`clear_guild_roles_cache(guild_id)`、`set_bot_id(bot_id)`，通过 `/user/view` 接口获取 bot 在频道下的角色列表并缓存。

### 2.5 lark/ (飞书)

#### `lark/lark_adapter.py`

- **职责**：飞书机器人官方 API 适配器，支持 WebSocket 与 Webhook 两种连接模式，支持流式消息。
- **核心类**：`LarkPlatformAdapter(Platform)`，注册名 `lark`，`support_streaming_message=True`。
- **关键方法**：
  - `__init__`：读取 `app_id`/`app_secret`/`domain`/`lark_connection_mode`；创建 `lark.ws.Client` 与 `lark.Client`；注册 `P2ImMessageReceiveV1` 事件处理器；webhook 模式下创建 `LarkWebhookServer`；维护 `event_id_timestamps` 去重。
  - `_download_message_resource(message_id, file_key, resource_type)`：下载消息资源（图片/文件/音频/视频）。
  - `_download_file_resource_to_temp(...)`：下载到临时文件。
  - `convert_msg(event)`：解析飞书消息（text/post/image/file/audio/media），处理 @mention、回复引用、富文本。
  - `_parse_message_components(message_id, message_type, content, at_map)`：按消息类型解析为消息组件。
  - `_build_at_map(mentions)`、`_parse_post_content(content)`、`_build_message_str_from_components`。
  - `_build_reply_from_parent_id(parent_message_id)`：获取引用消息详情构造 `Reply`。
  - `handle_webhook_event`/`webhook_callback`：Webhook 模式入口。
  - `run()`/`terminate()`。
- **依赖**：`lark_oapi`（`lark.ws.Client`、`lark.Client`、`im.v1` 接口）、`bot_info.request_lark_bot_info`、`LarkWebhookServer`、`LarkMessageEvent`、`MediaResolver`。

#### `lark/lark_event.py`

- **职责**：飞书消息事件实现，支持 CardKit 流式卡片、可折叠推理面板、文件/图片/音频/视频上传与发送。
- **核心类**：`LarkMessageEvent(AstrMessageEvent)`，持有 `lark.Client`。
- **关键方法**：
  - `_send_im_message(lark_client, content, msg_type, reply_message_id, receive_id, receive_id_type)`：通用 IM 消息发送（回复 `areply` 或主动 `acreate`）。
  - `_upload_lark_file(lark_client, path, file_type, duration)`：上传文件获取 `file_key`。
  - `_convert_to_lark(message, lark_client)`：将 `MessageChain` 转为飞书富文本结构（md/at/img，File/Record/Video 单独发送）。
  - `_build_collapsible_panel_element`/`_build_reasoning_collapsible_panel`/`_build_reasoning_card`：构造可折叠推理面板卡片。
  - `_send_interactive_card(card_json, ...)`：通过 CardKit 创建并发送卡片。
  - `send(message)`：按组件类型分发发送（Plain/Image/File/Record/Video/Json 推理面板）。
  - `send_streaming(generator, use_fallback)`：使用 CardKit 流式卡片（创建→增量更新→关闭），信号驱动发送循环 `_sender_loop`。
- **依赖**：`lark_oapi`（`cardkit.v1`、`im.v1`）、`MediaResolver`/`convert_audio_to_opus`/`convert_video_format`/`get_media_duration`、`Metric`。

#### `lark/bot_info.py`

- **职责**：获取飞书机器人信息（bot_name、open_id）。
- **关键函数**：`request_lark_bot_info(lark_api)`，调用 `auth/v3/app_access_token` 与 `contact/v3/bot` 接口。

#### `lark/server.py`

- **职责**：飞书 Webhook 服务器封装。
- **核心类**：`LarkWebhookServer`，基于 `FastAPIWebhookServer`，注册 `/lark/webhook` 路由，处理飞书事件回调。

#### `lark/app_registration.py`

- **职责**：飞书应用注册辅助（与钉钉类似，用于扫码或创建应用流程）。
- **说明**：提供飞书应用凭证获取相关流程函数。

### 2.6 line/ (LINE)

#### `line/line_adapter.py`

- **职责**：LINE Messaging API 适配器，基于 Webhook，支持 HMAC-SHA256 签名校验与事件去重。
- **核心类**：`LinePlatformAdapter(Platform)`，注册名 `line`。
- **关键方法**：`convert_message(event)` 解析 text/image/video/audio/file/sticker；`_is_duplicate_event(event_id)` 滑动窗口去重；`_build_file_component(message_id, type)` 下载 LINE 内容；Webhook 回调入口 `webhook_callback`。
- **依赖**：`line_api`、`line_event`、`aiohttp`。

#### `line/line_api.py`

- **职责**：LINE Messaging API 客户端封装。
- **核心类**：`LineApi`。
- **说明**：提供消息发送、内容下载、签名验证、广播消息等接口封装，使用 `Bearer` token 鉴权。

#### `line/line_event.py`

- **职责**：LINE 消息事件实现。
- **核心类**：`LineMessageEvent(AstrMessageEvent)`。
- **说明**：`send` 支持 text/image/video/audio/file/sticker；`send_streaming` 缓冲合并发送。

### 2.7 mattermost/ (Mattermost)

#### `mattermost/__init__.py`

- **职责**：空模块标记文件（包标识）。
- **说明**：内容为空，仅用于使 `mattermost` 目录成为 Python 包。

#### `mattermost/mattermost_adapter.py`

- **职责**：Mattermost 适配器，基于 WebSocket 长连接。
- **核心类**：`MattermostPlatformAdapter(Platform)`，注册名 `mattermost`。
- **关键方法**：`convert_message` 解析 Mattermost 事件；`run` 启动 WebSocket 连接；`send_by_session` 发送消息。
- **依赖**：`client`、`mattermost_event`。

#### `mattermost/mattermost_event.py`

- **职责**：Mattermost 消息事件实现。
- **核心类**：`MattermostMessageEvent(AstrMessageEvent)`。
- **说明**：支持文本/图片/文件发送，`send_streaming` 缓冲合并。

#### `mattermost/client.py`

- **职责**：Mattermost WebSocket 客户端封装。
- **核心类**：Mattermost 客户端类。
- **说明**：管理 WebSocket 连接、心跳、事件分发与 REST API 调用。

### 2.8 misskey/ (Misskey)

#### `misskey/misskey_adapter.py`

- **职责**：Misskey 适配器，基于 WebSocket。
- **核心类**：`MisskeyPlatformAdapter(Platform)`，注册名 `misskey`。
- **关键方法**：`convert_message` 解析 Misskey 通知/消息；`run` 启动连接；处理重连与限速重试。
- **依赖**：`misskey_api`、`misskey_event`、`misskey_utils`。

#### `misskey/misskey_api.py`

- **职责**：Misskey API 客户端封装。
- **核心类**：`MisskeyAPI`。
- **关键方法**：`_make_request` 使用 `retry_async` 装饰器处理限速（指数退避）；提供消息发送、文件上传、用户信息查询等接口。
- **依赖**：`aiohttp`/`websockets`（带导入错误处理与安装提示）。

#### `misskey/misskey_event.py`

- **职责**：Misskey 消息事件实现。
- **核心类**：`MisskeyMessageEvent(AstrMessageEvent)`。
- **说明**：支持文本/图片/文件发送。

#### `misskey/misskey_utils.py`

- **职责**：Misskey 工具函数（消息解析、格式转换等辅助逻辑）。

### 2.9 qqofficial/ (QQ 官方机器人)

#### `qqofficial/qqofficial_platform_adapter.py`

- **职责**：QQ 机器人官方 API 适配器，基于 `botpy`（qq-botpy）WebSocket，支持频道/群/C2C 消息。
- **核心类**：
  - `PatchedMessage`/`PatchedDirectMessage`/`PatchedC2CMessage`/`PatchedGroupMessage`：继承 botpy 消息类，额外保留 `raw_data`/`message_type`/`msg_elements` 字段。
  - `_ensure_group_message_create_parser()`：向 botpy `ConnectionState` 注册 patched 解析器，保留引用消息原始字段。
  - `ManagedBotWebSocket(BotWebSocket)`：关闭时根据是否正在关闭决定是否重连。
  - `botClient(Client)`：QQ 机器人客户端，实现 `on_group_at_message_create`/`on_group_message_create`/`on_at_message_create`/`on_direct_message_create`/`on_c2c_message_create` 回调，`bot_connect`/`shutdown` 管理 WebSocket 生命周期。
  - `QQOfficialPlatformAdapter(Platform)`：注册名 `qq_official`。
- **关键方法**：
  - `__init__`：读取 `appid`/`secret`/`enable_group_c2c`/`enable_guild_direct_message`，构造 `botpy.Intents` 与 `botClient`。
  - `_parse_from_qqofficial(message, message_type, force_group_mention)`：静态方法，解析频道/群/C2C 消息，处理 @mention、引用消息（含 `msg_elements` 解析）、附件（图片/音频/视频/文件）、QQ 表情消息（`<faceType=...>` 解析）。
  - `_parse_face_message(content)`：解析 QQ 表情标签的 base64 ext 字段。
  - `_append_attachments(msg, attachments)`：按 content_type/扩展名分类附件。
  - `send_by_session`/`_send_by_session_common`：按场景（group/channel/friend）调用对应 API（`post_group_message`/`post_message`/`post_c2c_message`），处理图片/语音/视频/文件上传与 `msg_id`/`msg_seq`。
  - `remember_session_message_id`/`remember_session_scene`：缓存会话最近 msg_id 与场景。
  - `run()`：`self.client.start(appid, secret)`。
  - `terminate()`：`self.client.shutdown()`。
- **依赖**：`botpy`、`botpy.message`、`MediaResolver`、`QQOfficialMessageEvent`。

#### `qqofficial/qqofficial_message_event.py`

- **职责**：QQ 官方消息事件实现。
- **核心类**：`QQOfficialMessageEvent(AstrMessageEvent)`。
- **关键方法**：`_split_message_chain_by_media(message_chain)`（拆分消息链）、`_parse_to_qqofficial(message_chain)`（解析为 plain/image/record/video/file）、`upload_group_and_c2c_image`/`upload_group_and_c2c_media`（上传媒体）、`post_c2c_message`（发送 C2C 消息）、`send`/`send_streaming`。
- **说明**：包含对 `aiohttp` v3.12+ 兼容性补丁（为 `_FormData` 添加 `_is_processed` 属性）。

#### `qqofficial/login_registration.py`

- **职责**：QQ 官方机器人登录/注册辅助流程。
- **说明**：提供扫码登录或应用注册相关流程函数。

### 2.10 qqofficial_webhook/ (QQ 官方 Webhook)

#### `qqofficial_webhook/qo_webhook_adapter.py`

- **职责**：QQ 官方机器人 Webhook 模式适配器，通过 HTTP 回调接收消息。
- **核心类**：`QQOfficialWebhookPlatformAdapter(Platform)`，注册名 `qq_official_webhook`。
- **说明**：复用 `QQOfficialPlatformAdapter` 的消息解析逻辑，通过 `qo_webhook_server` 接收回调；支持统一 Webhook 模式。

#### `qqofficial_webhook/qo_webhook_event.py`

- **职责**：QQ 官方 Webhook 消息事件实现。
- **核心类**：`QQOfficialWebhookMessageEvent(AstrMessageEvent)`。
- **说明**：消息发送逻辑与 `QQOfficialMessageEvent` 类似。

#### `qqofficial_webhook/qo_webhook_server.py`

- **职责**：QQ 官方 Webhook 服务器封装。
- **核心类**：`QQOfficialWebhookServer`，基于 `FastAPIWebhookServer`。
- **说明**：注册回调路由，处理签名校验与事件分发。

### 2.11 satori/ (Satori)

#### `satori/satori_adapter.py`

- **职责**：Satori 协议适配器（跨平台通用协议）。
- **核心类**：`SatoriPlatformAdapter(Platform)`，注册名 `satori`。
- **说明**：通过 Satori 协议的 WebSocket/HTTP 接收与发送消息，`convert_message` 解析 Satori 事件结构为 `AstrBotMessage`。

#### `satori/satori_event.py`

- **职责**：Satori 消息事件实现。
- **核心类**：`SatoriMessageEvent(AstrMessageEvent)`。
- **说明**：支持文本/图片/音频/视频/文件发送，`send_streaming` 缓冲合并。

### 2.12 slack/ (Slack)

#### `slack/slack_adapter.py`

- **职责**：Slack 适配器，支持 Socket Mode 与 Webhook Mode。
- **核心类**：`SlackAdapter(Platform)`，注册名 `slack`，`support_streaming_message=False`。
- **关键方法**：
  - `__init__`：读取 `bot_token`/`app_token`/`signing_secret`/`slack_connection_mode`（socket/webhook）/webhook 相关配置；校验必需字段；创建 `AsyncWebClient`。
  - `convert_message(event)`：解析 text/blocks/files，处理 @mention（`<@id>`）、富文本块（rich_text_section/rich_text_list）、频道提及、链接、emoji；通过 `conversations_info` 判断群/私聊。
  - `_parse_blocks(blocks)`：解析 Slack blocks 格式为消息组件。
  - `_handle_socket_event(req)`/`_handle_webhook_event(event_data)`：处理消息事件，忽略 bot_message/编辑/删除。
  - `get_bot_user_id()`/`get_file_base64(url)`。
  - `run()`：按模式启动 `SlackSocketClient` 或 `SlackWebhookClient`，支持统一 Webhook 模式。
  - `webhook_callback(request)`：统一 Webhook 入口。
  - `unified_webhook()`：判断统一 Webhook 模式。
- **依赖**：`slack_sdk`（`AsyncWebClient`、`SocketModeRequest`）、`aiohttp`、`SlackSocketClient`/`SlackWebhookClient`、`SlackMessageEvent`。

#### `slack/client.py`

- **职责**：Slack Socket Mode 与 Webhook 客户端封装。
- **核心类**：`SlackSocketClient`（基于 Socket Mode，管理 WebSocket 连接与事件分发）、`SlackWebhookClient`（基于 FastAPI Webhook 服务器，处理签名校验）。
- **说明**：`SlackWebhookClient` 在初始化时校验 URL，无效 URL 抛 `WecomAIBotWebhookError`（此处为 Slack 自有异常）。

#### `slack/slack_event.py`

- **职责**：Slack 消息事件实现。
- **核心类**：`SlackMessageEvent(AstrMessageEvent)`，持有 `AsyncWebClient`。
- **关键方法**：`_parse_slack_blocks(message_chain, web_client)` 将 `MessageChain` 转为 Slack blocks kit 格式，回退纯文本；`send` 通过 `chat_postMessage` 发送；`send_streaming` 缓冲合并。

### 2.13 telegram/ (Telegram)

#### `telegram/tg_adapter.py`

- **职责**：Telegram Bot API 适配器，基于 `python-telegram-bot` 长轮询，支持指令注册、媒体组聚合、轮询自动恢复。
- **核心类**：`TelegramPlatformAdapter(Platform)`，注册名 `telegram`。
- **关键方法/成员**：
  - `__init__`：读取 `telegram_token`/`telegram_api_base_url`/`telegram_file_base_url`/`telegram_command_register`/`telegram_command_auto_refresh`/`telegram_polling_restart_delay`/媒体组超时参数；创建 `AsyncIOScheduler`；初始化 `media_group_cache`。
  - `_build_application()`：通过 `ApplicationBuilder` 构造 PTB 应用，注册 `MessageHandler`。
  - `run()`：启动轮询，带自动恢复（`_on_polling_error` 累计 `NetworkError` 达阈值后 `_recreate_application`）；`Forbidden`/`InvalidToken` 直接停止。
  - `register_commands()`/`collect_commands()`：从 `star_handlers_registry` 收集指令，去重后通过 `set_my_commands` 注册到 Telegram；`_extract_command_info` 校验指令名（`^[a-z0-9_]+$`，≤32 字符）。
  - `message_handler(update, context)`：媒体组走 `handle_media_group_message`，普通消息走 `convert_message`。
  - `convert_message(update, context, get_reply=True)`：解析 text/voice/photo/sticker/document/video，处理 @mention、命令前缀剥离、回复引用、Topic 群组（`message_thread_id`）。
  - `handle_media_group_message(update, context)`：缓存媒体组成员，使用 APScheduler debounce（`media_group_timeout`/`media_group_max_wait`）后 `process_media_group` 合并发送。
  - `send_by_session`/`terminate`。
- **依赖**：`telegram`(PTB)、`apscheduler`、`CommandFilter`/`CommandGroupFilter`/`star_handlers_registry`、`TelegramPlatformEvent`、`MediaResolver`。

#### `telegram/tg_event.py`

- **职责**：Telegram 消息事件实现，支持流式草稿（私聊 `sendMessageDraft`）与编辑消息（群聊 `edit_message_text`）两种流式模式。
- **核心类**：`TelegramPlatformEvent(AstrMessageEvent)`。
- **关键常量**：`MAX_MESSAGE_LENGTH=4096`、`SPLIT_PATTERNS`（paragraph/line/sentence/word）、`ACTION_BY_TYPE`（组件类型到 ChatAction 的映射）、`_TELEGRAM_DRAFT_ID_MAX`。
- **关键方法**：
  - `_split_message(text)`：按段落/行/句/词切分长文本。
  - `_send_text_chunks(client, text, payload)`：markdownify 后以 MarkdownV2 发送，失败回退纯文本。
  - `_send_chat_action`/`_get_chat_action_for_chain`/`_send_media_with_action`：发送聊天状态动作（typing/upload_photo 等）。
  - `_send_voice_with_fallback`：语音发送，用户隐私禁止语音时回退为 document。
  - `send_with_client(client, message, user_name)`：类方法，按组件发送（Plain/Image/GIF/File/Record/Video）。
  - `send(message)`、`send_typing()`、`react(emoji, big)`（支持普通 emoji、自定义表情、取消反应）。
  - `send_streaming(generator, use_fallback)`：私聊用 `_send_streaming_draft`（`sendMessageDraft` + 信号驱动发送循环），群聊用 `_send_streaming_edit`（`send_message` + `edit_message_text` 节流编辑）。
  - `_send_message_draft(chat_id, draft_id, text, ...)`：通过 `client.send_message_draft` 发送草稿。
  - `_process_chain_items(chain, payload, user_name, message_thread_id, on_text)`：处理流式中的各类组件。
- **依赖**：`telegramify_markdown`、`telegram`（`ReactionTypeEmoji`/`ReactionTypeCustomEmoji`/`ChatAction`/`ExtBot`）、`Metric`。

### 2.14 webchat/ (WebChat)

#### `webchat/webchat_adapter.py`

- **职责**：WebChat 适配器（AstrBot 内置 Web 聊天），基于内部队列通信，支持主动消息推送与消息历史持久化。
- **核心类**：
  - `QueueListener`：注册回调并保持适配器任务存活，等待 `stop_event`。
  - `WebChatAdapter(Platform)`：注册名 `webchat`，`support_proactive_message=True`。
- **关键方法**：
  - `__init__`：创建 `imgs_dir`/`attachments_dir`，初始化 `metadata` 与 `_shutdown_event`，引用全局 `webchat_queue_mgr`。
  - `send_by_session(session, message_chain)`：查找活跃请求队列，通过 `WebChatMessageEvent._send` 流式发送；无活跃队列时直接持久化（`_save_proactive_message`）。
  - `_save_proactive_message(conversation_id, message_chain)`：将消息转为 storage parts 并写入 `PlatformMessageHistory`。
  - `_get_message_history(message_id)`/`_parse_message_parts(message_parts, depth, max_depth)`：解析消息段（含 reply 递归解析）。
  - `convert_message(data)`：将 `(username, cid, payload)` 转为 `AstrBotMessage`，session_id 格式 `webchat!{username}!{cid}`。
  - `run()`：启动 `QueueListener`。
  - `create_event(message)`：构造 `WebChatMessageEvent`，解析 payload 中的 flags（`resolve_webchat_request_flags`）、`selected_provider`/`selected_model`/`action_type`/`llm_checkpoint_id`/`thread_selected_text` 等额外信息。
- **依赖**：`db_helper`、`PlatformMessageHistory`、`message_parts_helper`、`request_flags`、`WebChatMessageEvent`、`webchat_queue_mgr`。

#### `webchat/webchat_event.py`

- **职责**：WebChat 消息事件实现，通过队列向 Web 前端推送消息。
- **核心类**：`WebChatMessageEvent(AstrMessageEvent)`。
- **关键方法**：
  - `_send(message_id, message, session_id, streaming, emit_complete)`：静态方法，按组件类型（Plain/Json/Image/Record/File）将消息放入 `webchat_queue_mgr` 的 back_queue；图片/语音/文件保存到 `attachments_dir` 并以 `[IMAGE]filename`/`[RECORD]filename`/`[FILE]filename|original_name` 格式标记；`emit_complete` 时发送 complete 信号。
  - `send(message)`：处理 `None` 消息时发送 `follow_up_captured`；否则调用 `_send`。
  - `send_typing()`：发送 `run_started` 信号。
  - `send_streaming(generator, use_fallback)`：处理音频流（`audio_chunk`）与文本流，累积 `final_data`/`reasoning_content`，结束时发送 complete 信号。
- **依赖**：`base64`、`uuid`、`webchat_queue_mgr`、`MediaResolver`/`detect_image_mime_type_async`/`MEDIA_MIME_EXTENSIONS`。

#### `webchat/webchat_queue_mgr.py`

- **职责**：WebChat 全局队列管理器，维护会话输入队列与请求响应队列。
- **核心类**：`WebChatQueueMgr`；模块级单例 `webchat_queue_mgr = WebChatQueueMgr()`。
- **关键成员**：`queues`（conversation_id→输入队列）、`back_queues`（request_id→响应队列）、`_conversation_back_requests`/`_request_conversation`（双向映射）、`_queue_close_events`/`_back_queue_close_events`/`_listener_tasks`/`_listener_callback`。
- **关键方法**：
  - `get_or_create_queue(conversation_id)`/`get_or_create_back_queue(request_id, conversation_id)`。
  - `put_back_queue(request_id, data)`：写入响应，队列满或关闭时返回 `False`，支持与 close_event 竞争。
  - `remove_back_queue(request_id)`/`remove_queue(conversation_id)`/`remove_queues(conversation_id)`。
  - `list_back_request_ids(conversation_id)`、`has_queue(conversation_id)`。
  - `set_listener(callback)`/`clear_listener()`：设置全局监听回调，为每个队列启动监听任务。
  - `_start_listener_if_needed(conversation_id)`/`_listen_to_queue(conversation_id, queue, close_event)`：监听输入队列并与 close_event 竞争。

#### `webchat/message_parts_helper.py`

- **职责**：WebChat 消息段与 `MessageChain` 组件的双向转换、附件持久化辅助。
- **关键常量**：`MEDIA_PART_TYPES = {"image", "record", "file", "video"}`；类型别名 `AttachmentGetter`/`AttachmentInserter`/`ReplyHistoryGetter`。
- **关键函数**：
  - `_safe_display_filename(filename)`：安全的 basename 处理。
  - `strip_message_parts_path_fields(message_parts)`：移除 `path` 字段。
  - `webchat_message_parts_have_content(message_parts)`：判断是否有实质内容。
  - `parse_webchat_message_parts(message_parts, *, strict, include_empty_plain, verify_media_path_exists, reply_history_getter, current_depth, max_reply_depth, cast_reply_id_to_str)`：解析为 `(components, text_parts, has_content)`，支持 reply 递归解析、媒体路径校验、音频转 wav。
  - `build_webchat_message_parts(message_payload, *, get_attachment_by_id, strict)`：从前端 payload 构建 storage parts，通过 `get_attachment_by_id` 解析附件。
  - `webchat_message_parts_to_message_chain(message_parts, *, strict)`：转为 `MessageChain`。
  - `build_message_chain_from_payload(message_payload, *, get_attachment_by_id, strict)`：组合构建流程。
  - `create_attachment_part_from_existing_file(filename, *, attach_type, insert_attachment, attachments_dir, fallback_dirs, display_name)`：从已存在文件创建附件 part。
  - `message_chain_to_storage_message_parts(message_chain, *, insert_attachment, attachments_dir)`：将 `MessageChain` 转为 storage parts（复制文件到 attachments_dir 并插入附件记录）。
  - `_copy_file_to_attachment_part(...)`：内部辅助，复制文件并创建附件 part。
- **依赖**：`Attachment`、消息组件、`MessageChain`、`MediaResolver`、`mimetypes`/`shutil`/`uuid`。

#### `webchat/request_flags.py`

- **职责**：解析 WebChat 请求 flags（支持 legacy 顶层字段回退）。
- **关键常量**：`WEBCHAT_REQUEST_FLAG_DEFAULTS = {"enable_inline_genui": True, "enable_default_system_prompt": True, "enable_streaming": True}`。
- **核心函数**：`resolve_webchat_request_flags(payload)`：`flags` dict 优先，其次顶层字段，最后默认值，返回完整的 bool 映射。

### 2.15 wecom/ (企业微信)

#### `wecom/wecom_adapter.py`

- **职责**：企业微信适配器，支持企业微信应用与微信客服（KF）两种模式，基于 Webhook 回调与 `wechatpy`。
- **关键常量**：`WECHAT_KF_TEXT_CONTENT_DEDUP_TTL_SECONDS = 15`。
- **核心类**：
  - `WecomServer`：Webhook 服务器，注册 `/callback/command`（GET 验证 + POST 回调），使用 `WeChatCrypto` 解密；`handle_verify`/`handle_callback` 可被统一 Webhook 复用。
  - `WecomPlatformAdapter(Platform)`：注册名 `wecom`，`support_streaming_message=False`。
- **关键方法**：
  - `__init__`：读取 `api_base_url`（自动补全 `/cgi-bin/`）、`unified_webhook_mode`、`corpid`/`secret`/`token`/`encoding_aes_key`；创建 `WeChatClient`；若配置 `kf_name` 则注入 `WeChatKF`/`WeChatKFMessage` API；设置回调处理 `kf_msg_or_event` 事件与普通消息。
  - `_is_duplicate_wechat_kf_text_message(session_id, text)`：15 秒滑动窗口去重。
  - `send_by_session`：KF 模式不支持主动发送；应用模式构造 `AstrBotMessage` 并通过 event 发送。
  - `convert_message(msg)`：解析 `TextMessage`/`ImageMessage`/`VoiceMessage`（下载并转 wav）。
  - `convert_wechat_kf_message(msg)`：解析微信客服 text/image/voice/file 消息，下载媒体（`_extract_wecom_media_filename` 从 Content-Disposition 提取文件名）。
  - `run()`：KF 模式下获取客服账号列表与联系二维码；统一 Webhook 模式等待关闭，否则启动独立服务器。
  - `webhook_callback(request)`：统一 Webhook 入口，按 GET/POST 分发。
- **依赖**：`wechatpy`（`WeChatClient`/`parse_message`/`WeChatCrypto`/消息类/`InvalidSignatureException`）、`FastAPIWebhookServer`、`WecomPlatformEvent`、`WeChatKF`/`WeChatKFMessage`、`MediaResolver`/`detect_image_mime_type_async`/`MEDIA_MIME_EXTENSIONS`。

#### `wecom/wecom_event.py`

- **职责**：企业微信消息事件实现，支持应用消息与客服消息发送。
- **核心类**：`WecomPlatformEvent(AstrMessageEvent)`，持有 `WeChatClient`。
- **关键方法**：
  - `split_plain(plain)`：长文本按 2048 字符切分，优先在标点处断句。
  - `send(message)`：区分 KF 模式与应用模式：
    - KF：通过 `WeChatKFMessage` 发送 text/image/voice（转 amr）/file/video，errcode 40096 时回退到普通消息 API。
    - 应用：通过 `client.message.send_text/send_image/send_voice/send_file/send_video` 发送。
  - `send_streaming(generator, use_fallback)`：缓冲合并后 `send`。
- **依赖**：`wechatpy`、`convert_audio_to_amr`、`WeChatKFMessage`。

#### `wecom/wecom_kf.py`

- **职责**：微信客服 API 封装（基于 `wechatpy` 的 `BaseWeChatAPI`）。
- **核心类**：`WeChatKF`。
- **关键方法**：`sync_msg`（同步消息）、`get_service_state`/`trans_service_state`（会话状态）、`get_servicer_list`/`add_servicer`/`del_servicer`（接待人员）、`batchget_customer`（客户信息）、`get_account_list`/`account_update`（客服账号）、`add_contact_way`（联系链接）、`get_upgrade_service_config`/`upgrade_service`/`cancel_upgrade_service`（升级服务）、`send_msg_on_event`（事件响应消息）、`get_corp_statistic`/`get_servicer_statistic`（统计）。
- **说明**：MIT 许可，源自 wechatpy 扩展。

#### `wecom/wecom_kf_message.py`

- **职责**：微信客服消息发送 API 封装。
- **核心类**：`WeChatKFMessage`（继承 `BaseWeChatAPI`）。
- **关键方法**：`send`（通用发送）、`send_text`、`send_image`、`send_voice`、`send_video`、`send_file`、`send_articles_link`、`send_msgmenu`（菜单消息）、`send_location`、`send_miniprogram`。
- **依赖**：`optionaldict`、`wechatpy.client.api.base.BaseWeChatAPI`。

### 2.16 wecom_ai_bot/ (企业微信 AI 助手)

#### `wecom_ai_bot/wecomai_adapter.py`

- **职责**：企业微信 AI 助手（智能机器人）适配器，支持 Webhook 与长连接两种模式，支持流式消息。
- **核心类**：`WecomAIBotAdapter(Platform)`，注册名 `wecom_ai_bot`。
- **说明**：根据 `wecom_ai_bot_connection_mode` 选择 Webhook（`WecomAIBotWebhookClient`）或长连接（`WecomAIBotLongConnectionClient`）；处理消息加密（AES + `WXBizJsonMsgCrypt`）；支持统一 Webhook 模式。

#### `wecom_ai_bot/wecomai_event.py`

- **职责**：企业微信 AI 助手消息事件实现。
- **核心类**：`WecomAIBotMessageEvent(AstrMessageEvent)`。
- **说明**：支持文本/图片/文件发送，流式消息通过增量更新实现。

#### `wecom_ai_bot/wecomai_api.py`

- **职责**：企业微信 AI 助手 REST API 客户端封装。
- **核心类**：`WecomAIBotAPI`。
- **说明**：提供消息发送、素材上传、用户信息查询等接口。

#### `wecom_ai_bot/wecomai_long_connection.py`

- **职责**：企业微信 AI 助手长连接客户端。
- **核心类**：`WecomAIBotLongConnectionClient`。
- **关键方法**：`start()` 带指数退避重连，管理心跳与命令重试。

#### `wecom_ai_bot/wecomai_queue_mgr.py`

- **职责**：企业微信 AI 助手队列管理器（类似 WebChat 的队列管理）。
- **核心类**：`WecomAIBotQueueMgr`。
- **说明**：维护请求-响应队列映射，支持流式推送。

#### `wecom_ai_bot/wecomai_server.py`

- **职责**：企业微信 AI 助手 Webhook 服务器封装。
- **核心类**：`WecomAIBotServer`，基于 `FastAPIWebhookServer`。
- **说明**：注册回调路由，处理消息解密与签名校验。

#### `wecom_ai_bot/wecomai_utils.py`

- **职责**：企业微信 AI 助手工具函数（加解密辅助、格式转换等）。

#### `wecom_ai_bot/wecomai_webhook.py`

- **职责**：企业微信 AI 助手 Webhook 客户端。
- **核心类**：`WecomAIBotWebhookClient`。
- **说明**：初始化时校验 URL，无效 URL 抛 `WecomAIBotWebhookError`；处理 Webhook 回调。

#### `wecom_ai_bot/WXBizJsonMsgCrypt.py`

- **职责**：企业微信消息加解密（JSON 格式），实现 AES-CBC 加解密与签名校验。
- **核心类**：`WXBizJsonCrypt`/`WXBizMsgCrypt` 等。
- **说明**：源自企业微信官方加解密 SDK。

#### `wecom_ai_bot/ierror.py`

- **职责**：企业微信加解密错误码定义。
- **说明**：定义 `WXBizMsgCrypt` 使用的错误码常量。

#### `wecom_ai_bot/__init__.py`

- **职责**：包标识文件，可能导出部分公共接口。
- **说明**：模块标记。

### 2.17 weixin_oc/ (微信个人号)

#### `weixin_oc/weixin_oc_adapter.py`

- **职责**：微信个人号（基于 WeixinOC 协议）适配器，支持扫码登录、消息转换与媒体处理。
- **核心类**：`WeixinOCAdapter(Platform)`，注册名 `weixin_oc`。
- **关键方法**：
  - `convert_wechat_kf_message(msg)`：解析 text/image/voice/file 消息，处理 15 秒内重复文本消息去重（`_is_duplicate_wechat_kf_text_message`）。
  - 消息发送：支持主动发送与被动回复模式（`active_send_mode`）。
  - 登录流程：QR 码登录、心跳保活。
  - 媒体处理：图片/语音/文件下载与格式转换。
- **依赖**：`weixin_oc_client`、`weixin_oc_event`、`login_registration`。

#### `weixin_oc/weixin_oc_event.py`

- **职责**：微信个人号消息事件实现。
- **核心类**：`WeixinOCMessageEvent(AstrMessageEvent)`。
- **关键方法**：`send(message)` 处理 `active_send_mode`：主动模式直接发送，被动模式将文本切分（`split_plain`）后缓存到 `message_out["cached_xml"]`；支持 Plain/Image/Record/File/Video。
- **说明**：流式消息通过缓存合并实现。

#### `weixin_oc/weixin_oc_client.py`

- **职责**：微信个人号 API 客户端封装。
- **核心类**：`WeixinOCClient`。
- **说明**：提供消息发送、媒体上传、登录态管理等接口。

#### `weixin_oc/login_registration.py`

- **职责**：微信个人号登录注册流程（扫码登录）。
- **说明**：提供 QR 码生成、登录状态轮询等流程函数。

### 2.18 weixin_official_account/ (微信公众号)

#### `weixin_official_account/weixin_offacc_adapter.py`

- **职责**：微信公众号适配器，基于 Webhook 回调与 `wechatpy`。
- **核心类**：`WeixinOfficialAccountPlatformAdapter(Platform)`，注册名 `weixin_official_account`。
- **关键方法**：
  - `convert_message(event)`：解析 `TextMessage`/`ImageMessage`/`VoiceMessage`/`VideoMessage` 等，转换为 `AstrBotMessage`。
  - `_remember_sender_binding(message, abm)`：记录发送者绑定。
  - Webhook 回调处理与签名校验。
  - 媒体下载与格式转换（语音转 wav）。
- **依赖**：`wechatpy`、`weixin_offacc_event`、`FastAPIWebhookServer`。

#### `weixin_official_account/weixin_offacc_event.py`

- **职责**：微信公众号消息事件实现。
- **核心类**：`WeixinOfficialAccountMessageEvent(AstrMessageEvent)`。
- **说明**：`send` 支持文本/图片/语音/视频/图文消息；被动回复模式下构造 XML 响应；`send_streaming` 缓冲合并。

---

## 三、总结

### 平台层整体架构

1. **统一抽象**：所有平台适配器继承 `Platform`，所有消息事件继承 `AstrMessageEvent`，所有消息统一为 `AstrBotMessage`，会话统一为 `MessageSession`。这构成了平台层的"四件套"抽象。

2. **注册机制**：通过 `@register_platform_adapter` 装饰器登记到 `platform_cls_map`/`platform_registry`，`PlatformManager` 根据配置 `type` 动态导入并实例化。

3. **生命周期**：`PlatformManager` 负责适配器的加载（`load_platform`）、运行（`_start_platform_task` + `_task_wrapper`）、终止（`terminate_platform`/`terminate`），并通过 `PlatformStatus` 跟踪状态。

4. **事件流转**：适配器 `convert_message` → `AstrBotMessage` → `create_event` → `commit_event`（入 `_event_queue`）→ EventBus 消费 → 处理器通过 `event.send`/`event.send_streaming` 回写 → 适配器事件类调用平台 API 发送。

5. **连接模式**：适配器支持多种连接模式——反向 WS（aiocqhttp）、WS 长连接（kook/lark/qqofficial/mattermost/misskey/satori/dingtalk）、Webhook（line/slack/wecom/lark/weixin_official_account/wecom_ai_bot）、长轮询（telegram）、内部队列（webchat）。多个平台支持"统一 Webhook 模式"以复用 Dashboard 的 Webhook 端点。

6. **流式消息**：lark（CardKit 流式卡片）、telegram（sendMessageDraft 私聊 / edit_message_text 群聊）、webchat/wecom_ai_bot（队列推送）、dingtalk（缓冲合并）等支持流式输出；不支持真实流式的平台通过 `send_streaming` 缓冲合并或 `process_buffer` 分段发送作为回退。

7. **安全机制**：wecom/wecom_ai_bot/weixin_official_account 使用 `WeChatCrypto`/`WXBizJsonMsgCrypt` 进行 AES 加解密；line/slack/wecom 等进行签名校验；telegram 使用 Bot Token 鉴权。

8. **指令注册**：telegram 与 discord 支持将 AstrBot 注册的指令同步到平台原生命令系统（`set_my_commands`/`sync_commands`），并支持定期刷新与去重。

9. **扩展点**：`webhook_callback` 统一 Webhook 入口、`send_by_session` 主动消息推送、`get_group` 群信息查询、`react` 表情回应等能力由各适配器按需实现。


---

## 章节五：core/provider（LLM/TTS/STT Provider）

# AstrBot core/provider 模块逐文件详解

本文档对 `astrbot/core/provider` 模块下的全部 49 个 `.py` 文件进行了逐文件、逐类、逐方法的详尽分析。分析范围覆盖 8 个核心抽象/管理文件、41 个位于 `sources/` 子目录的具体厂商适配器（含 13 个 LLM 对话适配器、4 个 Embedding 适配器、5 个 Rerank 适配器、13 个 TTS 适配器、5 个 STT 适配器，以及 2 个公共工具文件）。

所有内容均基于实际源码阅读，未做臆测。核心抽象文件（`provider.py`、`manager.py`、`entities.py`、`entites.py`、`func_tool_manager.py`、`modalities.py`、`register.py`、`__init__.py`）记录最为详尽；厂商适配器按类别分组，每个适配器的类、关键方法、关键常量、依赖均有记录。

---

## 一、核心文件（core/provider 根目录）

### `core/provider/__init__.py`
- **职责**: 包初始化文件，对外导出 Provider 抽象层最核心的三个符号 `Provider`、`ProviderMetaData`、`STTProvider`，作为该包的公共入口。
- **核心类**: 无（仅做 re-export）
- **核心函数**: 无
- **关键常量**: `__all__ = ["Provider", "ProviderMetaData", "STTProvider"]`
- **依赖**:
  - 相对导入: `.entities`（`ProviderMetaData`）、`.provider`（`Provider`、`STTProvider`）

### `core/provider/provider.py`
- **职责**: 定义 Provider 体系的全部抽象基类。它定义了所有类型提供商（LLM 对话、STT、TTS、Embedding、Rerank）的统一抽象接口、生命周期测试方法（`test`）、模型元数据获取（`meta`）、以及若干通用辅助方法（上下文清理、批量 embedding、流式 TTS 默认实现）。是整个 provider 模块的抽象基石。
- **核心类**:
  - `AbstractProvider(abc.ABC)` — 职责: 所有 Provider 的最底层抽象基类，持有 `provider_config` 与 `model_name`，提供 `set_model/get_model/meta/test` 通用能力。
    - 关键属性: `model_name: str`、`provider_config: dict`
    - 关键方法:
      - `set_model(model_name: str) -> None` — 设置当前模型名
      - `get_model() -> str` — 获取当前模型名
      - `meta() -> ProviderMeta` — 根据 `provider_config["type"]` 从 `provider_cls_map` 查注册元数据，构造 `ProviderMeta` 返回；未注册抛 `ValueError`
      - `async test() -> None` — 默认空实现（占位）
  - `Provider(AbstractProvider)` — 职责: **LLM 文本对话**提供商抽象。定义 `text_chat`（非流式）与 `text_chat_stream`（流式）抽象方法，以及 Key 管理、模型列表获取、上下文清理等通用逻辑。
    - 关键属性: `provider_settings: dict`
    - 关键方法（抽象）:
      - `get_current_key() -> str`（抽象）
      - `set_key(key: str) -> None`（抽象）
      - `async get_models() -> list[str]`（抽象）— 获得支持的模型列表
      - `async text_chat(prompt, session_id, image_urls, audio_urls, func_tool: ToolSet, contexts, system_prompt, tool_calls_result, model, extra_user_content_parts, tool_choice: Literal["auto","required"], request_max_retries, **kwargs) -> LLMResponse`（抽象）— 非流式对话
      - `async text_chat_stream(...) -> AsyncGenerator[LLMResponse, None]` — 流式对话（默认 `raise NotImplementedError`，含 `yield None` 以满足 typing）
    - 关键方法（具体）:
      - `get_keys() -> list[str]` — 从 `provider_config["key"]` 取 Key 列表
      - `async pop_record(context: list) -> None` — 弹出 context 中前 2 条非 system 记录（用于上下文超限回退）
      - `_ensure_message_to_dicts(messages) -> list[dict]` — 将 `Message` 对象/`dict` 列表统一为 `dict`，跳过 checkpoint 消息
      - `async test(timeout: float = 45.0) -> None` — 用 `text_chat(prompt="REPLY PONG ONLY")` + `asyncio.wait_for` 做健康检查
  - `STTProvider(AbstractProvider)` — 职责: **语音转文字**抽象。
    - 关键属性: `provider_config`、`provider_settings`
    - 关键方法:
      - `async get_text(audio_url: str) -> str`（抽象）
      - `async test() -> None` — 用内置 `samples/stt_health_check.wav` 调 `get_text`
  - `TTSProvider(AbstractProvider)` — 职责: **文字转语音**抽象，含流式 TTS 的默认实现。
    - 关键属性: `provider_config`、`provider_settings`
    - 关键方法:
      - `support_stream() -> bool` — 默认 `False`，子类可重写启用流式
      - `async get_audio(text: str) -> str`（抽象）— 返回音频文件路径
      - `async get_audio_stream(text_queue: asyncio.Queue[str|None], audio_queue: asyncio.Queue[bytes|tuple[str,bytes]|None]) -> None` — 流式 TTS 默认实现：累积 text_queue 文本，收到 `None` 时调 `get_audio` 一次性生成并塞入 audio_queue，最后塞 `None` 结束
      - `async test() -> None` — 调 `get_audio("hi")`，校验文件存在且非空，最后删除测试文件；空文件抛异常提示检查 group_id 等
  - `EmbeddingProvider(AbstractProvider)` — 职责: **文本向量化**抽象，含分批并发嵌入能力。
    - 关键属性: `provider_config`、`provider_settings`
    - 关键方法:
      - `async get_embedding(text: str) -> list[float]`（抽象）
      - `async get_embeddings(text: list[str]) -> list[list[float]]`（抽象）— 批量
      - `get_dim() -> int`（抽象）— 向量维度
      - `async test() -> None` — 调 `get_embedding("astrbot")`
      - `async get_embeddings_batch(texts, batch_size=16, tasks_limit=3, max_retries=3, progress_callback=None) -> list[list[float]]` — 分批并发嵌入，带信号量限流、指数退避重试、进度回调；失败批次聚合抛异常
  - `RerankProvider(AbstractProvider)` — 职责: **重排序**抽象。
    - 关键属性: `provider_config`、`provider_settings`
    - 关键方法:
      - `async rerank(query: str, documents: list[str], top_n: int|None=None) -> list[RerankResult]`（抽象）
      - `async test() -> None` — 调 `rerank("Apple", ["apple","banana"])`，空结果抛异常
- **核心函数**: 无（仅类型别名 `Providers: TypeAlias = Union["Provider","STTProvider","TTSProvider","EmbeddingProvider","RerankProvider"]`）
- **关键常量**: `Providers`（类型别名）
- **依赖**:
  - 标准库: `abc`、`asyncio`、`os`、`collections.abc.AsyncGenerator`、`typing`（`Literal, TypeAlias, Union`）
  - astrbot 内部: `astrbot.core.agent.message`（`ContentPart, Message, is_checkpoint_message`）、`astrbot.core.agent.tool`（`ToolSet`）、`astrbot.core.provider.entities`（`LLMResponse, ProviderMeta, RerankResult, ToolCallsResult`）、`astrbot.core.provider.register`（`provider_cls_map`）、`astrbot.core.utils.astrbot_path`（`get_astrbot_path`）

### `core/provider/entities.py`
- **职责**: 定义 provider 模块所有数据实体/数据类，包括 `ProviderType` 枚举、`ProviderMeta`/`ProviderMetaData` 元数据、`ToolCallsResult` 工具调用结果、`ProviderRequest` 统一请求载荷、`TokenUsage` token 用量、`LLMResponse` LLM 响应、`RerankResult` 重排结果。是 provider 模块的数据契约层。
- **核心类**:
  - `ProviderType(enum.Enum)` — 职责: 提供商能力类型枚举。
    - 枚举值: `CHAT_COMPLETION="chat_completion"`、`SPEECH_TO_TEXT="speech_to_text"`、`TEXT_TO_SPEECH="text_to_speech"`、`EMBEDDING="embedding"`、`RERANK="rerank"`
  - `ProviderMeta`（`@dataclass`）— 职责: 单个 provider 实例的元数据。
    - 字段: `id: str`、`model: str|None`、`type: str`、`provider_type: ProviderType = CHAT_COMPLETION`
  - `ProviderMetaData(ProviderMeta)`（`@dataclass`）— 职责: 用于**注册**的 provider 适配器元数据（在 ProviderMeta 基础上扩展）。
    - 新增字段: `desc: str=""`、`cls_type: Any=None`、`default_config_tmpl: dict|None=None`、`provider_display_name: str|None=None`
  - `ToolCallsResult`（`@dataclass`）— 职责: 一次工具调用结果（调用信息 + 结果列表），可转 OpenAI 消息格式。
    - 字段: `tool_calls_info: AssistantMessageSegment`、`tool_calls_result: list[ToolCallMessageSegment]`
    - 方法: `to_openai_messages() -> list[dict]`、`to_openai_messages_model() -> list[...]`
  - `ProviderRequest`（`@dataclass`）— 职责: 统一的对话请求载荷，封装 prompt、图片/音频 URL、上下文、工具、系统提示、关联对话等。
    - 字段: `prompt`、`session_id`、`image_urls`、`audio_urls`、`extra_user_content_parts`、`func_tool`、`contexts`、`system_prompt`、`conversation`、`tool_calls_result`、`model`
    - 方法:
      - `append_tool_calls_result(tool_calls_result) -> None` — 追加工具调用结果
      - `_print_friendly_context()` — 折叠多模态内容为简短标记用于打印
      - `async assemble_context() -> dict` — 将 prompt/image_urls/audio_urls + extra parts 包装成统一消息（base64 化图片/音频），单文本时降级为简单格式
  - `TokenUsage`（`@dataclass`）— 职责: token 用量统计（区分缓存/非缓存输入、输出）。
    - 字段: `input_other: int=0`、`input_cached: int=0`、`output: int=0`
    - 属性: `total`、`input`
    - 运算: `__add__`、`__sub__`
  - `LLMResponse`（`@dataclass`）— 职责: LLM 响应封装，支持流式 chunk 与完整结果两种模式，包含文本/工具调用/推理内容/原始 completion/usage。
    - 字段: `role`、`result_chain: MessageChain|None`、`tools_call_args/name/ids/extra_content`、`reasoning_content`、`reasoning_signature`、`raw_completion`、`_completion_text`、`is_chunk`、`id`、`usage: TokenUsage|None`
    - 关键方法:
      - `completion_text`（property/setter）— 优先从 `result_chain` 取纯文本，setter 会清空 Plain 组件重设
      - `to_openai_tool_calls() -> list[dict]`（已废弃，转 dict）
      - `to_openai_to_calls_model() -> list[ToolCall]`（转 pydantic 模型）
  - `RerankResult`（`@dataclass`）— 职责: 单条重排结果。
    - 字段: `index: int`、`relevance_score: float`
- **核心函数**: 无
- **关键常量**: 无（`ProviderType` 枚举即为关键常量）
- **依赖**:
  - 标准库: `enum`、`json`、`dataclasses`、`typing.Any`、`__future__`
  - 第三方: `anthropic.types.Message`、`google.genai.types.GenerateContentResponse`、`openai.types.chat.chat_completion.ChatCompletion`
  - astrbot 内部: `astrbot.core.message.components as Comp`、`astrbot`（`logger`）、`astrbot.core.agent.message`（`AssistantMessageSegment, ContentPart, ToolCall, ToolCallMessageSegment, is_checkpoint_message`）、`astrbot.core.agent.tool`（`ToolSet`）、`astrbot.core.db.po`（`Conversation`）、`astrbot.core.message.message_event_result`（`MessageChain`）、`astrbot.core.utils.media_utils`（`MediaResolver`）

### `core/provider/entites.py`（注意：旧拼写，已废弃的兼容入口）
- **职责**: 旧文件名（拼写错误 `entites`），作为向后兼容的 re-export 入口，从 `entities`（新拼写）重新导出核心数据类。代码注释表明这是为兼容性保留。
- **核心类**: 无（仅 re-export）
- **核心函数**: 无
- **关键常量**: `__all__ = ["AssistantMessageSegment","LLMResponse","ProviderMetaData","ProviderRequest","ProviderType","ToolCallMessageSegment","ToolCallsResult"]`
- **依赖**:
  - 相对导入: `astrbot.core.provider.entities`（导入全部上述符号）
  - 注意：与 `entities.py` 不同，此处还额外导出了 `AssistantMessageSegment`、`ProviderRequest`、`ToolCallMessageSegment`，说明旧代码依赖这些符号从此处导入

### `core/provider/modalities.py`
- **职责**: 根据模型支持的多模态能力（image/audio/tool_use）对上下文消息进行清洗/降级，移除模型不支持的图片/音频/工具调用内容，确保发给不支持的模型时不出错。是上下文多模态适配层。
- **核心类**:
  - `ContextSanitizeStats`（`@dataclass(slots=True)`）— 职责: 记录清洗统计。
    - 字段: `fixed_image_blocks: int=0`、`fixed_audio_blocks: int=0`、`fixed_tool_messages: int=0`、`removed_tool_calls: int=0`
    - 属性: `changed -> bool` — 是否发生任何修改
- **核心函数**:
  - `_message_to_dict(message) -> dict|None` — 将 `Message`/`dict` 统一为 `dict`（深拷贝）
  - `sanitize_contexts_by_modalities(contexts, modalities: list[str]|None) -> tuple[list[dict], ContextSanitizeStats]` — 核心清洗函数：若 modalities 为空或全支持则原样拷贝；否则对 tool 消息降级为 user+占位文本、移除 assistant 的 tool_calls、将不支持的 image_url/audio_url 块替换为 `[Image]`/`[Audio]` 文本占位
  - `_tool_result_placeholder(content: Any) -> str` — 将工具结果内容转为 `[Tool result]\n...` 占位文本
  - `log_context_sanitize_stats(stats) -> None` — debug 级别记录清洗统计
- **关键常量**: 无
- **依赖**:
  - 标准库: `copy`、`collections.abc.Sequence`、`dataclasses`、`typing.Any`、`__future__`
  - astrbot 内部: `astrbot`（`logger`）、`astrbot.core.agent.message`（`Message`）

### `core/provider/register.py`
- **职责**: Provider 适配器注册中心。维护全局注册表 `provider_registry` 与 `provider_cls_map`，提供 `register_provider_adapter` 装饰器，用于将具体厂商适配器类注册到全局表，供 `ProviderManager` 按类型名实例化。同时持有全局 `llm_tools = FuncCall()` 实例。
- **核心类**: 无
- **核心函数**:
  - `register_provider_adapter(provider_type_name: str, desc: str, provider_type: ProviderType = CHAT_COMPLETION, default_config_tmpl: dict|None=None, provider_display_name: str|None=None)` — 带参装饰器工厂：检查重名冲突，给 `default_config_tmpl` 补 `type/enable/id` 必备字段，构造 `ProviderMetaData` 加入 `provider_registry` 与 `provider_cls_map`，返回原类
- **关键常量**:
  - `provider_registry: list[ProviderMetaData]` — 注册列表
  - `provider_cls_map: dict[str, ProviderMetaData]` — 类型名→元数据映射
  - `llm_tools = FuncCall()` — 全局函数工具管理器实例（`FuncCall` 是 `FunctionToolManager` 的别名）
- **依赖**:
  - astrbot 内部: `astrbot.core`（`logger`）、`.entities`（`ProviderMetaData, ProviderType`）、`.func_tool_manager`（`FuncCall`）

### `core/provider/func_tool_manager.py`
- **职责**: 函数工具管理器（FuncCall）。管理 LLM 函数调用工具的生命周期（添加/删除/查询/激活/停用）、内置工具、MCP（Model Context Protocol）服务的初始化/启用/禁用/同步、工具权限守卫（`_PermissionGuardedTool`）、以及 OpenAI/Anthropic/Google 三种风格的工具描述生成。是 function-calling 与 MCP 的核心调度器。
- **核心类**:
  - `MCPInitError(Exception)` — MCP 初始化失败基类
  - `MCPInitTimeoutError(asyncio.TimeoutError, MCPInitError)` — MCP 初始化超时
  - `MCPAllServicesFailedError(MCPInitError)` — 全部 MCP 服务失败
  - `MCPShutdownTimeoutError(asyncio.TimeoutError)` — 关闭超时（携带 `names`、`timeout`）
  - `MCPInitSummary`（`@dataclass`）— MCP 初始化摘要（`total/success/failed`）
  - `_MCPServerRuntime`（`@dataclass`）— 单个 MCP 服务的运行时（`name/client/shutdown_event/lifecycle_task`）
  - `_MCPClientDictView(Mapping[str, MCPClient])` — MCP 客户端只读视图
  - `_PermissionGuardedTool(FunctionTool)` — 职责: 非内置工具的权限守卫代理，`handler` 故意置 `None` 让执行器走 `call()`，在 `call()` 中先查权限再委托给被包裹工具的 `handler`/`call`/`run`。
    - 关键属性: `_wrapped`、`_mgr`、`active`、`handler_module_path`
    - 关键方法: `async call(context, **kwargs) -> Any` — 检查 `_check_tool_permission`，按 handler→call→run 顺序调用
  - `FunctionToolManager` — 职责: 核心管理器。维护 `func_list`（插件/MCP 工具）、`builtin_func_list`（内置工具）、MCP 运行时；提供工具 CRUD、MCP 生命周期、权限校验、工具集构建、多风格 schema 生成。
    - 关键属性: `func_list`、`builtin_func_list`、`_mcp_server_runtime`、`_runtime_lock`、`_init_timeout_default`、`_enable_timeout_default`
    - 关键方法（工具管理）:
      - `empty() -> bool`
      - `spec_to_func(name, func_args, desc, handler) -> FuncTool` — 由参数规格构造 `FuncTool`
      - `add_func(name, func_args, desc, handler) -> None` — 添加（先 remove 同名）
      - `remove_func(name) -> None`
      - `get_func(name) -> FuncTool|None` — 优先返回激活的同名工具，退化取最后一个，再退化查内置
      - `get_builtin_tool(tool: str|type) -> FuncTool` — 懒加载内置工具实例
      - `iter_builtin_tools() -> list[FuncTool]`
      - `is_builtin_tool(name) -> bool`
      - `get_full_tool_set() -> ToolSet` — 用 `_PermissionGuardedTool` 包裹所有非内置工具
      - `deactivate_llm_tool(name) -> bool` / `activate_llm_tool(name, star_map) -> bool` — 停用/激活并持久化到 `sp`
    - 关键方法（MCP）:
      - `async init_mcp_clients(raise_on_all_failed=False) -> MCPInitSummary` — 读 `mcp_server.json`，并发初始化所有 active 的 MCP 服务
      - `async _start_mcp_server(name, cfg, *, shutdown_event, timeout) -> None` — 幂等启动单个 MCP（连接→注册工具→等待 shutdown 事件→清理）
      - `async _shutdown_runtimes(runtimes, timeout, *, strict=True) -> list[str]` — 关闭运行时并等待 lifecycle task
      - `async _cleanup_mcp_client_safely(mcp_client, name) -> None`
      - `async _terminate_mcp_client(name) -> None`
      - `async test_mcp_server_connection(config) -> list[str]`（静态）— 测试连接并返回工具名
      - `async enable_mcp_server(name, config, shutdown_event=None, timeout=None) -> None` — 动态启用单个 MCP
      - `async disable_mcp_server(name=None, timeout=10) -> None` — 禁用单个或全部
      - `async sync_modelscope_mcp_servers(access_token) -> None` — 从 ModelScope 同步 MCP 配置
      - `mcp_config_path`（property）、`load_mcp_config()`、`save_mcp_config(config) -> bool`
    - 关键方法（权限）:
      - `_default_permission(tool_name) -> str` — 默认 `"member"`
      - `_check_tool_permission(tool_name, context) -> str|None` — 从 `sp` 读 `tool_permissions._default`，admin 权限校验 `event.is_admin()`
    - 关键方法（schema）:
      - `get_func_desc_openai_style(omit_empty_parameter_field=False) -> list`
      - `get_func_desc_anthropic_style() -> list`
      - `get_func_desc_google_genai_style() -> dict`
- **核心函数**:
  - `_resolve_timeout(timeout, *, env_name, default) -> float` — 超时解析（显式参数>环境变量>默认，钳制到 `MAX_MCP_TIMEOUT_SECONDS`）
  - `_prepare_config(config) -> dict` — 处理 `mcpServers` 嵌套格式
  - `async _quick_test_mcp_connection(config) -> tuple[bool, str]` — 快速 HTTP 可达性测试
- **关键常量**:
  - `DEFAULT_MCP_CONFIG = {"mcpServers": {}}`
  - `DEFAULT_MCP_INIT_TIMEOUT_SECONDS = 180.0`
  - `DEFAULT_ENABLE_MCP_TIMEOUT_SECONDS = 180.0`
  - `MCP_INIT_TIMEOUT_ENV = "ASTRBOT_MCP_INIT_TIMEOUT"`
  - `ENABLE_MCP_TIMEOUT_ENV = "ASTRBOT_MCP_ENABLE_TIMEOUT"`
  - `MAX_MCP_TIMEOUT_SECONDS = 300.0`
  - `SUPPORTED_TYPES = ["string","number","object","array","boolean"]`
  - `PY_TO_JSON_TYPE = {...}`
  - `FuncTool = FunctionTool`（别名）
  - `FuncCall = FunctionToolManager`（别名，模块末尾）
- **依赖**:
  - 标准库: `asyncio`、`copy`、`json`、`os`、`threading`、`urllib.parse`、`collections.abc`、`dataclasses`、`types.MappingProxyType`、`typing`、`__future__`
  - 第三方: `aiohttp`
  - astrbot 内部: `astrbot`（`logger`）、`astrbot.core`（`sp`）、`astrbot.core.agent.mcp_client`（`MCPClient, MCPTool`）、`astrbot.core.agent.tool`（`FunctionTool, ToolSet`）、`astrbot.core.tools.registry`（`ensure_builtin_tools_loaded, get_builtin_tool_class, get_builtin_tool_name, iter_builtin_tool_classes`）、`astrbot.core.utils.astrbot_path`（`get_astrbot_data_path`）、`astrbot.core.utils.config_number`（`coerce_int_config`）、`astrbot.core.utils.network_utils`（`is_connection_error`）

### `core/provider/manager.py`
- **职责**: `ProviderManager`——所有 Provider 实例的生命周期管理器。负责按配置实例化/加载/重载/终止各类 provider、维护默认 provider 指针、提供按类型/按用户会话（umo）查询当前 provider、provider 配置增删改、环境变量 Key 解析、以及与 MCP 初始化的后台任务协调。是 provider 模块的运行时调度核心。
- **核心类**:
  - `HasInitialize`（`@runtime_checkable Protocol`）— 职责: 鸭子类型协议，声明 `async initialize() -> None`，用于判断 provider 实例是否需要异步初始化。
  - `ProviderManager` — 职责: 核心管理器。
    - 关键属性: `reload_lock`、`resource_lock`、`persona_mgr`、`acm`、`providers_config`、`provider_sources_config`、`provider_settings`、`provider_stt_settings`、`provider_tts_settings`、`provider_insts`、`stt_provider_insts`、`tts_provider_insts`、`embedding_provider_insts`、`rerank_provider_insts`、`inst_map`、`llm_tools`、`curr_provider_inst`、`curr_stt_provider_inst`、`curr_tts_provider_inst`、`db_helper`
    - 关键方法:
      - `set_provider_change_callback(cb)` / `register_provider_change_hook(hook)` / `_notify_provider_changed(...)` — provider 切换回调/钩子机制
      - `persona_configs`/`personas`/`selected_default_persona`（property）— 代理到 `persona_mgr`
      - `async set_provider(provider_id, provider_type, umo=None) -> None` — 设置默认 provider（支持 umo 会话隔离，写入 `sp`）
      - `get_provider_by_id(provider_id) -> Providers|None`
      - `get_using_provider(provider_type, umo=None) -> Providers|None` — 按 umo 优先取，回退默认配置
      - `async initialize() -> None` — 逐个加载 provider，恢复默认指针，后台启动 MCP 初始化
      - `dynamic_import_provider(type: str) -> None` — 巨型 `match` 语句，按类型名动态导入对应模块（覆盖全部适配器，确保装饰器注册执行）
      - `get_merged_provider_config(provider_config) -> dict` — 合并 provider_source 配置
      - `get_provider_config_by_id(provider_id, *, merged=False) -> dict|None`
      - `_resolve_env_key_list(provider_config) -> dict` — 解析 `$ENV`/`${ENV}` 形式的环境变量 Key
      - `async load_provider(provider_config) -> None` — 合并配置→动态导入→按 `provider_type` 实例化→`HasInitialize` 则 `initialize()`→加入对应实例列表→设置默认指针
      - `async reload(provider_config) -> None` — 终止后重新加载，并清理已不存在的 provider
      - `get_insts() -> list`
      - `async terminate_provider(provider_id) -> None` — 从各列表移除并调 `terminate()`
      - `async delete_provider(provider_id=None, provider_source_id=None) -> None`
      - `async update_provider(origin_provider_id, new_config) -> None`
      - `async create_provider(new_config) -> None`
      - `async terminate() -> None` — 取消 MCP 任务、终止所有 provider、禁用所有 MCP
- **核心函数**: 无
- **关键常量**: 无
- **依赖**:
  - 标准库: `asyncio`、`copy`、`os`、`traceback`、`collections.abc`（`Callable`）、`typing`（`Protocol, runtime_checkable`）
  - astrbot 内部: `astrbot.core`（`astrbot_config, logger, sp`）、`astrbot.core.astrbot_config_mgr`（`AstrBotConfigManager`）、`astrbot.core.db`（`BaseDatabase`）、`astrbot.core.utils.error_redaction`（`safe_error`）、`..persona_mgr`（`PersonaManager`）、`.entities`（`ProviderType`）、`.provider`（`EmbeddingProvider, Provider, Providers, RerankProvider, STTProvider, TTSProvider`）、`.register`（`llm_tools, provider_cls_map`）

---

## 二、LLM 对话提供商适配器（sources/）

本组 13 个文件均继承自 `Provider`（`openai_source.py`/`anthropic_source.py`/`gemini_source.py` 三个基础适配器）或它们的子类，通过 `register_provider_adapter` 装饰器注册。三者共享统一抽象接口 `text_chat`/`text_chat_stream`/`get_models`/`get_current_key`/`set_key`/`assemble_context`/`terminate`。

### `sources/openai_source.py`
- **职责**: OpenAI 官方 API（及所有 OpenAI 兼容接口）对话适配器，是绝大多数兼容厂商适配器的基类。处理多 Key 轮转、图片/音频多模态、function-calling、流式/非流式、上下文长度超限回退、图片审核/不支持 VLM 时降级为纯文本重试、assistant 空消息清洗、reasoning_content 提取、tool_calls 解析、Ollama/NVIDIA/DeepSeek/MiMo/Gemini 等厂商特化适配。
- **核心类**:
  - `ProviderOpenAIOfficial(Provider)` — 注册名 `openai_chat_completion`。
    - 关键属性: `chosen_api_key`、`api_keys`、`timeout`、`custom_headers`、`client`（`AsyncOpenAI`/`AsyncAzureOpenAI`）、`default_params`、`reasoning_key`（默认 `"reasoning_content"`）
    - 关键方法:
      - `__init__` — 据是否有 `api_version` 选择 Azure 或 OpenAI 客户端
      - `_ollama_disable_thinking_enabled() -> bool`
      - `_apply_provider_specific_request_overrides(payloads, extra_body)` — NVIDIA minimax-m3 max_tokens、Ollama `reasoning_effort=none`
      - `async get_models() -> list[str]`
      - `_sanitize_assistant_messages(payloads)`（静态）— 过滤空 assistant 消息、清理孤儿 tool 消息
      - `async _query(payloads, tools, *, request_max_retries) -> LLMResponse` — 非流式查询
      - `async _query_stream(payloads, tools, *, request_max_retries) -> AsyncGenerator[LLMResponse]` — 流式查询，用 `ChatCompletionStreamState` 累积
      - `_extract_reasoning_content(completion) -> str|None`
      - `_extract_usage(usage) -> TokenUsage`
      - `_normalize_content(raw_content, strip=True) -> str`（静态）— 处理 str/list/dict 多种 content 格式
      - `async _parse_openai_completion(completion, tools) -> LLMResponse` — 解析 `ChatCompletion`，含 `<think>` 标签提取、refusal、tool_calls、`content_filter` 异常
      - `async _prepare_chat_payload(...) -> tuple[payloads, context_query]`
      - `_finally_convert_payload(payloads)` — think→reasoning_content 转换、DeepSeek v4/MiMo 推理模型回填 `reasoning_content`、Gemini tool 结果包 JSON
      - `async _handle_api_error(...)` — 429 换 Key、context length 弹记录、not VLM/审核/invalid attachment 降级纯文本、不支持 function calling 去工具
      - `async text_chat(...) -> LLMResponse` — 含 10 次重试循环
      - `async text_chat_stream(...) -> AsyncGenerator[LLMResponse]`
      - `async _remove_image_from_context(contexts)`、`get_current_key()`、`get_keys()`、`set_key(key)`、`async assemble_context(...)`、`async encode_image_bs64(image_url)`、`async terminate()`
- **核心函数**: 多个私有静态/类方法（`_truncate_error_text_candidate`、`_safe_json_dump`、`_get_image_moderation_error_patterns`、`_extract_error_text_candidates`、`_is_content_moderated_upload_error`、`_context_contains_image`、`_is_invalid_attachment_error`、`_resolve_image_part`、`_resolve_audio_part`、`_transform_content_part` 等）
- **关键常量**: `_ERROR_TEXT_CANDIDATE_MAX_CHARS = 4096`
- **依赖**: `httpx`、`openai`（`AsyncAzureOpenAI, AsyncOpenAI, ChatCompletionStreamState, ChatCompletion, ChatCompletionChunk, CompletionUsage`）、astrbot 内部（`astrbot.api.provider.Provider`、`astrbot.core.agent.message`、`astrbot.core.exceptions.EmptyModelOutputError`、`astrbot.core.provider.entities`、`astrbot.core.utils.media_utils`、`astrbot.core.utils.network_utils`、`astrbot.core.utils.string_utils`）、`.request_retry.retry_provider_request`、`..register.register_provider_adapter`

### `sources/anthropic_source.py`
- **职责**: Anthropic Claude API 对话适配器，是 Kimi Code / Xiaomi Token Plan / MiniMax Token Plan 的基类。处理 OpenAI→Anthropic 消息格式转换（图片 base64+MIME 检测、tool_use/tool_result 块、thinking 块+signature）、prompt 缓存断点、thinking config、连续同角色消息合并、孤儿 tool_result 清理、流式事件解析。
- **核心类**:
  - `ProviderAnthropic(Provider)` — 注册名 `anthropic_chat_completion`。
    - 关键属性: `base_url`、`timeout`、`thinking_config`、`custom_headers`、`chosen_api_key`、`api_keys`、`client`（`AsyncAnthropic`）
    - 关键方法:
      - `_init_api_key(provider_config)`、`_create_http_client(provider_config)`
      - `_apply_thinking_config(payloads)` — adaptive/budget 两种模式
      - `_prepare_payload(messages) -> (system_prompt, new_messages)` — OpenAI→Anthropic 格式转换
      - `_merge_consecutive_anthropic_messages(messages)`（静态）— 合并连续同角色消息，tool_result 前置
      - `_sanitize_assistant_messages(payloads)`（静态）— 移除孤儿 tool_result
      - `_extract_usage(usage) -> TokenUsage`、`_update_usage(token_usage, usage)`
      - `_normalize_tool_choice(tool_choice) -> dict`（静态）— `required→any` 等
      - `_apply_explicit_prompt_cache_breakpoints(payloads)`（类方法）
      - `async _query(payloads, tools, *, request_max_retries) -> LLMResponse` — 非流式，解析 text/thinking/tool_use 块
      - `async _query_stream(payloads, tools, *, request_max_retries) -> AsyncGenerator[LLMResponse]` — 流式，处理 content_block_start/delta/stop、message_delta
      - `async text_chat(...)` / `async text_chat_stream(...)`
      - `_detect_image_mime_type(data) -> str` — magic bytes 检测 PNG/JPEG/GIF/WEBP
      - `async assemble_context(...)`、`async encode_image_bs64(image_url) -> tuple[str,str]`、`get_current_key()`、`async get_models()`、`set_key(key)`、`async terminate()`
- **核心函数**: `_ensure_usable_response`（静态）、`_normalize_custom_headers`（静态）、`_resolve_custom_headers`（类方法）
- **关键常量**: `_PROMPT_CACHE_CONTROL = {"type": "ephemeral"}`
- **依赖**: `anthropic`（`AsyncAnthropic, Message, MessageDeltaUsage, Usage`）、`httpx`、astrbot 内部（同 OpenAI）、`.request_retry.retry_provider_request, retry_provider_request_context`

### `sources/gemini_source.py`
- **职责**: Google Gemini 对话适配器。处理 OpenAI→Gemini Content 转换（含 thought_signature、function_call/response）、安全设置、thinking config（2.5 系 budget / 3 系列 level）、原生 code execution/search/url_context 工具、recitation 重试、多模态输出回退、流式累积。
- **核心类**:
  - `SuppressNonTextPartsWarning(logging.Filter)` — 过滤 Gemini SDK 非文本部分警告
  - `ProviderGoogleGenAI(Provider)` — 注册名 `googlegenai_chat_completion`。
    - 关键属性: `api_keys`、`chosen_api_key`、`timeout`、`api_base`、`_http_client`、`_stale_http_clients`、`client`（`genai.Client().aio`）、`safety_settings`
    - 关键方法:
      - `_init_client()`、`_init_safety_settings()`
      - `async _handle_api_error(e, keys) -> bool` — 429/invalid key 换 Key
      - `async _prepare_query_config(payloads, tools, tool_choice, system_instruction, modalities, temperature) -> types.GenerateContentConfig` — 含 native coderunner/search/url_context、thinking config、tool_config
      - `_prepare_conversation(payloads) -> list[types.Content]` — OpenAI→Gemini Content 转换
      - `_extract_reasoning_content(candidate) -> str`、`_extract_usage(usage_metadata) -> TokenUsage`
      - `_process_content_parts(candidate, llm_response, *, validate_output=True) -> MessageChain` — 处理 text/thinking/function_call/inline_data/thought_signature
      - `async _query(...)` — 非流式，recitation 时升温重试
      - `async _query_stream(...)` — 流式累积
      - `async text_chat(...)` / `async text_chat_stream(...)` — 10 次重试
      - `async get_models()`、`get_current_key()`、`get_keys()`、`set_key(key)`（会 `_init_client`）、`async assemble_context(...)`、`async encode_image_bs64(image_url)`、`async terminate()`
- **核心函数**: 无模块级函数（`_ensure_usable_response` 为静态方法）
- **关键常量**: `CATEGORY_MAPPING`（HarmCategory 映射）、`THRESHOLD_MAPPING`（HarmBlockThreshold 映射）
- **依赖**: `httpx`、`google.genai`（`genai, types`）、`google.genai.errors.APIError`、astrbot 内部（同上）、`.request_retry.retry_provider_request`

### `sources/groq_source.py`
- **职责**: Groq 对话适配器，继承 `ProviderOpenAIOfficial`。仅覆盖 `reasoning_key="reasoning"` 并在 `_finally_convert_payload` 中移除 assistant 历史的 `reasoning_content`/`reasoning`（Groq 拒绝这些字段）。注册名 `groq_chat_completion`。
- **核心类**: `ProviderGroq(ProviderOpenAIOfficial)`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `..register.register_provider_adapter`、`.openai_source.ProviderOpenAIOfficial`

### `sources/kimi_code_source.py`
- **职责**: Kimi Code 对话适配器，继承 `ProviderAnthropic`。固定 `api_base` 为 Kimi coding 端点、默认模型 `kimi-for-coding`、注入 `User-Agent: claude-code/0.1.0` 头。注册名 `kimi_code_chat_completion`。
- **核心类**: `ProviderKimiCode(ProviderAnthropic)`
- **核心函数**: 无
- **关键常量**: `KIMI_CODE_API_BASE`、`KIMI_CODE_DEFAULT_MODEL`、`KIMI_CODE_USER_AGENT`
- **依赖**: `..register.register_provider_adapter`、`.anthropic_source.ProviderAnthropic`

### `sources/longcat_source.py`
- **职责**: LongCat（美团）对话适配器，继承 `ProviderOpenAIOfficial`。仅规范化 `api_base`（默认 `https://api.longcat.chat/openai/v1`，处理 `/openai`→`/openai/v1`）。注册名 `longcat_chat_completion`。
- **核心类**: `ProviderLongCat(ProviderOpenAIOfficial)`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `..register.register_provider_adapter`、`.openai_source.ProviderOpenAIOfficial`

### `sources/oai_aihubmix_source.py`
- **职责**: AIHubMix 对话适配器，继承 `ProviderOpenAIOfficial`。仅注入 `APP-Code` 头享折扣。注册名 `aihubmix_chat_completion`。
- **核心类**: `ProviderAIHubMix(ProviderOpenAIOfficial)`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `..register.register_provider_adapter`、`.openai_source.ProviderOpenAIOfficial`

### `sources/openrouter_source.py`
- **职责**: OpenRouter 对话适配器，继承 `ProviderOpenAIOfficial`。注入 `HTTP-Referer`/`X-OpenRouter-Title`/`X-OpenRouter-Categories` 头，`reasoning_key="reasoning"`。注册名 `openrouter_chat_completion`。
- **核心类**: `ProviderOpenRouter(ProviderOpenAIOfficial)`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `..register.register_provider_adapter`、`.openai_source.ProviderOpenAIOfficial`

### `sources/xai_source.py`
- **职责**: xAI（Grok）对话适配器，继承 `ProviderOpenAIOfficial`。当 `xai_native_search` 开启时注入 `search_parameters={"mode":"auto"}` 启用 Live Search。注册名 `xai_chat_completion`。
- **核心类**: `ProviderXAI(ProviderOpenAIOfficial)`
  - 关键方法: `_maybe_inject_xai_search(payloads)`、`_finally_convert_payload(payloads)`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `..register.register_provider_adapter`、`.openai_source.ProviderOpenAIOfficial`

### `sources/xiaomi_source.py`
- **职责**: 小米 MiMo 对话适配器（OpenAI 兼容），继承 `ProviderOpenAIOfficial`。默认 `api_base` 指向小米端点，`get_models` 失败时回退硬编码模型列表。注册名 `xiaomi_chat_completion`。
- **核心类**: `ProviderXiaomi(ProviderOpenAIOfficial)`
- **核心函数**: 无
- **关键常量**: `XIAOMI_MODELS`（5 个 mimo-v2 系列模型列表）
- **依赖**: `astrbot.logger`、`.openai_source.ProviderOpenAIOfficial`、`..register.register_provider_adapter`

### `sources/xiaomi_token_plan_source.py`
- **职责**: 小米 Token Plan 对话适配器，继承 `ProviderAnthropic`。固定 `api_base` 为 Token Plan 的 anthropic 端点，注入 `Authorization: Bearer <token>` 头，`get_models` 返回硬编码列表。注册名 `xiaomi_token_plan`。
- **核心类**: `ProviderXiaomiTokenPlan(ProviderAnthropic)`
- **核心函数**: 无
- **关键常量**: `XIAOMI_TOKEN_PLAN_MODELS`（同 `XIAOMI_MODELS`）
- **依赖**: `astrbot.logger`、`.anthropic_source.ProviderAnthropic`、`..register.register_provider_adapter`

### `sources/minimax_token_plan_source.py`
- **职责**: MiniMax Token Plan 对话适配器，继承 `ProviderAnthropic`。固定 `api_base` 为 MiniMax anthropic 端点，注入 Bearer 头，`get_models` 动态从 `/v1/models` 拉取。注册名 `minimax_token_plan`。
- **核心类**: `ProviderMiniMaxTokenPlan(ProviderAnthropic)`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `httpx`、`astrbot.logger`、`.anthropic_source.ProviderAnthropic`、`..register.register_provider_adapter`

### `sources/zhipu_source.py`
- **职责**: 智谱 Chat Completion 适配器，继承 `ProviderOpenAIOfficial`。注释说明最初为 glm-4v-flash 适配，现已无特殊逻辑。注册名 `zhipu_chat_completion`。
- **核心类**: `ProviderZhipu(ProviderOpenAIOfficial)`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `..register.register_provider_adapter`、`.openai_source.ProviderOpenAIOfficial`

---

## 三、Embedding 提供商适配器（sources/）

本组 4 个文件均继承 `EmbeddingProvider`，实现 `get_embedding`/`get_embeddings`/`get_dim`，注册类型 `ProviderType.EMBEDDING`。

### `sources/openai_embedding_source.py`
- **职责**: OpenAI（及兼容）Embedding 适配器。支持 `embedding_dimensions_mode`（auto/always/never）自动判断是否发送 `dimensions` 参数（仅 OpenAI 官方 text-embedding-3 系与 SiliconFlow qwen 系发送）。
- **核心类**: `OpenAIEmbeddingProvider(EmbeddingProvider)` — 注册名 `openai_embedding`。
  - 关键方法: `get_embedding(text)`、`get_embeddings(text)`、`_embedding_kwargs() -> dict`、`get_dim() -> int`、`async terminate()`
- **核心函数**: `_normalize_api_base(api_base) -> str` — 规范化 api_base（补 `/v1`、去 `/embeddings`）
- **关键常量**: 无
- **依赖**: `httpx`、`openai.AsyncOpenAI`、`astrbot.logger`、`..entities.ProviderType`、`..provider.EmbeddingProvider`、`..register.register_provider_adapter`

### `sources/gemini_embedding_source.py`
- **职责**: Google Gemini Embedding 适配器，使用 `genai.Client` 的 `embed_content`。默认模型 `gemini-embedding-exp-03-07`，默认维度 768。
- **核心类**: `GeminiEmbeddingProvider(EmbeddingProvider)` — 注册名 `gemini_embedding`。
  - 关键方法: `get_embedding(text)`、`get_embeddings(text)`（构造 `Content` 列表）、`get_dim() -> int`（默认 768）、`async terminate()`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `google.genai`（`genai, types`）、`google.genai.errors.APIError`、`astrbot.logger`、`..entities.ProviderType`、`..provider.EmbeddingProvider`、`..register.register_provider_adapter`

### `sources/nvidia_embedding_source.py`
- **职责**: NVIDIA NIM Embedding 适配器，用 `aiohttp` 直接请求 `/embeddings`。默认模型 `nvidia/llama-nemotron-embed-1b-v2`，支持 `input_type`。
- **核心类**: `NvidiaEmbeddingProvider(EmbeddingProvider)` — 注册名 `nvidia_embedding`。
  - 关键方法: `_get_client()`、`_build_payload(text)`、`_parse_response(response_data)`、`get_embedding(text)`（委托 `get_embeddings`）、`get_embeddings(text)`、`get_dim() -> int`、`async terminate()`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `aiohttp`、`astrbot.logger`、`..entities.ProviderType`、`..provider.EmbeddingProvider`、`..register.register_provider_adapter`

### `sources/ollama_embedding_source.py`
- **职责**: Ollama 本地 Embedding 适配器，请求 `/api/embed`。默认模型 `nomic-embed-text`，支持 `dimensions`。
- **核心类**: `OllamaEmbeddingProvider(EmbeddingProvider)` — 注册名 `ollama_embedding`。
  - 关键方法: `_get_client()`、`_build_payload(text)`、`get_embedding(text)`、`get_embeddings(text)`、`get_dim() -> int`、`async terminate()`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `aiohttp`、`astrbot.logger`、`..entities.ProviderType`、`..provider.EmbeddingProvider`、`..register.register_provider_adapter`

---

## 四、Rerank 提供商适配器（sources/）

本组 5 个文件均继承 `RerankProvider`，实现 `rerank(query, documents, top_n) -> list[RerankResult]`，注册类型 `ProviderType.RERANK`。

### `sources/vllm_rerank_source.py`
- **职责**: vLLM Rerank 适配器，请求 `/v1/rerank`（可配 `rerank_api_suffix`）。默认模型 `BAAI/bge-reranker-base`。
- **核心类**: `VLLMRerankProvider(RerankProvider)` — 注册名 `vllm_rerank`。
  - 关键方法: `async rerank(query, documents, top_n=None)`、`async terminate()`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `aiohttp`、`astrbot.logger`、`..entities.ProviderType, RerankResult`、`..provider.RerankProvider`、`..register.register_provider_adapter`

### `sources/xinference_rerank_source.py`
- **职责**: Xinference Rerank 适配器，使用 `xinference_client` SDK，支持 `launch_model_if_not_running` 自动拉起模型。
- **核心类**: `XinferenceRerankProvider(RerankProvider)` — 注册名 `xinference_rerank`。
  - 关键方法: `async initialize()` — 连接客户端、查找/拉起模型、获取 model handle；`async rerank(...)`、`async terminate()`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `xinference_client.client.restful.async_restful_client`（`AsyncClient, AsyncRESTfulRerankModelHandle`）、`astrbot.logger`、`..entities.ProviderType, RerankResult`、`..provider.RerankProvider`、`..register.register_provider_adapter`

### `sources/bailian_rerank_source.py`
- **职责**: 阿里云百炼 Rerank 适配器，支持 `qwen3-rerank` 与兼容 API 两种请求格式，文档数截断 500。
- **核心类**:
  - `BailianRerankError(Exception)` / `BailianAPIError` / `BailianNetworkError` — 异常层级
  - `BailianRerankProvider(RerankProvider)` — 注册名 `bailian_rerank`。
    - 关键方法: `_build_payload(query, documents, top_n)`（区分 qwen3-rerank 与兼容格式）、`_parse_results(data)`（区分 compatible-api）、`_log_usage(data)`、`async rerank(...)`、`async terminate()`
- **核心函数**: 无
- **关键常量**: `QWEN3_RERANK_MODEL = "qwen3-rerank"`
- **依赖**: `os`、`aiohttp`、`astrbot.logger`、`..entities.ProviderType, RerankResult`、`..provider.RerankProvider`、`..register.register_provider_adapter`

### `sources/nvidia_rerank_source.py`
- **职责**: NVIDIA Rerank 适配器，请求 NVIDIA retrieval 端点。根据模型名（是否含 `/`）动态构建 URL 路径，结果按分数降序排序。
- **核心类**: `NvidiaRerankProvider(RerankProvider)` — 注册名 `nvidia_rerank`。
  - 关键方法: `_get_client()`、`_get_endpoint() -> str`、`_build_payload(query, documents)`、`_parse_results(response_data, top_n)`、`_log_usage(data)`、`async rerank(...)`、`async terminate()`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `aiohttp`、`astrbot.logger`、`..entities.ProviderType, RerankResult`、`..provider.RerankProvider`、`..register.register_provider_adapter`

### `sources/tei_rerank_source.py`
- **职责**: HuggingFace TEI（Text Embeddings Inference）Rerank 适配器，请求 `/rerank`，支持 `truncate`/`truncation_direction`/`raw_scores`/`return_text`，覆盖 `test()` 调 `/health`。
- **核心类**: `TEIRerankProvider(RerankProvider)` — 注册名 `tei_rerank`。
  - 关键方法: `async rerank(...)`、`async test()`（调 `/health` + rerank）、`async terminate()`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `aiohttp`、`astrbot.logger`、`..entities.ProviderType, RerankResult`、`..provider.RerankProvider`、`..register.register_provider_adapter`

---

## 五、TTS 提供商适配器（sources/）

本组 13 个文件均继承 `TTSProvider`，实现 `get_audio(text) -> str`（返回音频文件路径），注册类型 `ProviderType.TEXT_TO_SPEECH`。部分支持流式（重写 `support_stream` 与 `get_audio_stream`）。

### `sources/azure_tts_source.py`
- **职责**: Azure TTS 适配器，支持两种后端：原生 Azure（`AzureNativeProvider`，订阅密钥+region+SSML）与 OTTS 第三方（`OTTSProvider`，签名鉴权）。根据 key 格式（32/84 位字母数字 或 `other[...]` JSON）自动选择。
- **核心类**:
  - `OTTSProvider` — 第三方 OTTS 后端，时间同步+MD5 签名，`async with` 上下文管理 httpx 客户端
  - `AzureNativeProvider(TTSProvider)` — 原生 Azure，token 刷新（540s 有效期），SSML 合成
  - `AzureTTSProvider(TTSProvider)` — 注册名 `azure_tts`。`_parse_provider(key_value, config)` 据格式选择后端，`get_audio` 委托给选定后端
- **核心函数**: 无
- **关键常量**: `TEMP_DIR`、`AZURE_TTS_SUBSCRIPTION_KEY_PATTERN`
- **依赖**: `asyncio`、`hashlib`、`json`、`re`、`secrets`、`time`、`uuid`、`xml.sax.saxutils.escape`、`httpx`（`AsyncClient, Timeout`）、`astrbot.logger`、`astrbot.core.config.default.VERSION`、`astrbot.core.utils.astrbot_path`、`..entities.ProviderType`、`..provider.TTSProvider`、`..register.register_provider_adapter`

### `sources/dashscope_tts.py`
- **职责**: 阿里 Dashscope TTS 适配器，支持 CosyVoice（`SpeechSynthesizer`）与 Qwen TTS（`MultiModalConversation`）两种模型，按模型名前缀自动选择。
- **核心类**: `ProviderDashscopeTTSAPI(TTSProvider)` — 注册名 `dashscope_tts`。
  - 关键方法: `async get_audio(text)`、`_call_qwen_tts(model, text)`、`_synthesize_with_qwen_tts(model, text)`、`_extract_audio_from_response(response)`、`_download_audio_from_url(url)`、`_synthesize_with_cosyvoice(model, text)`、`_is_qwen_tts_model(model)`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `asyncio`、`base64`、`os`、`uuid`、`aiohttp`、`dashscope`、`dashscope.audio.tts_v2`（`AudioFormat, SpeechSynthesizer`）、`astrbot.core.utils.astrbot_path`、`..entities.ProviderType`、`..provider.TTSProvider`、`..register.register_provider_adapter`

### `sources/edge_tts_source.py`
- **职责**: Microsoft Edge TTS 适配器（免费），生成 MP3 后用 pyffmpeg 或 ffmpeg 命令行转 WAV（24kHz 单声道 PCM）。
- **核心类**: `ProviderEdgeTTS(TTSProvider)` — 注册名 `edge_tts`。
  - 关键方法: `async get_audio(text)` — 用 `edge_tts.Communicate.save` 再转 wav
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `asyncio`、`os`、`subprocess`、`uuid`、`edge_tts`、`astrbot.core.logger`、`astrbot.core.utils.astrbot_path`、`..entities.ProviderType`、`..provider.TTSProvider`、`..register.register_provider_adapter`

### `sources/elevenlabs_tts_source.py`
- **职责**: ElevenLabs TTS 适配器，请求 `/text-to-speech/{voice_id}`，支持 mp3/wav/opus 输出（拒绝 raw 格式），可选 voice_settings（stability/similarity_boost/style/use_speaker_boost）。
- **核心类**: `ProviderElevenLabsTTSAPI(TTSProvider)` — 注册名 `elevenlabs_tts_api`。
  - 关键方法: `_output_extension() -> str`、`async get_audio(text)`、`async terminate()`
- **核心函数**: `_parse_optional_float(provider_config, cfg_name) -> float|None`、`_parse_bool(provider_config, cfg_name) -> bool`、`_normalize_timeout(value) -> int`、`_validate_output_format(output_format) -> None`
- **关键常量**: `SUPPORTED_CONTAINER_OUTPUT_PREFIXES = ("mp3","wav","opus")`、`RAW_AUDIO_OUTPUT_PREFIXES = ("pcm","ulaw","alaw")`
- **依赖**: `uuid`、`pathlib.Path`、`httpx`、`astrbot.logger`、`astrbot.core.utils.astrbot_path`、`..entities.ProviderType`、`..provider.TTSProvider`、`..register.register_provider_adapter`

### `sources/fishaudio_tts_api_source.py`
- **职责**: FishAudio TTS 适配器，请求 `/tts`，使用 msgpack 编码 `ServeTTSRequest`，支持 reference_id（32 位十六进制）或按角色名查询。
- **核心类**:
  - `ServeReferenceAudio(BaseModel)` — 参考音频模型
  - `ServeTTSRequest(BaseModel)` — TTS 请求模型（text/chunk_length/format/mp3_bitrate/references/reference_id/normalize/latency）
  - `ProviderFishAudioTTSAPI(TTSProvider)` — 注册名 `fishaudio_tts_api`。
    - 关键方法: `_get_reference_id_by_character(character)`、`_validate_reference_id(reference_id)`、`_generate_request(text)`、`async get_audio(text)`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `os`、`re`、`uuid`、`ormsgpack`、`httpx.AsyncClient`、`pydantic`（`BaseModel, conint`）、`astrbot.logger`、`astrbot.core.utils.astrbot_path`、`..entities.ProviderType`、`..provider.TTSProvider`、`..register.register_provider_adapter`

### `sources/gemini_tts_source.py`
- **职责**: Gemini TTS 适配器，用 `generate_content` + `response_modalities=["AUDIO"]` + `PrebuiltVoiceConfig`，输出 24kHz 16bit mono WAV。
- **核心类**: `ProviderGeminiTTSAPI(TTSProvider)` — 注册名 `gemini_tts`。
  - 关键方法: `async get_audio(text)` — 写 WAV 文件、`async terminate()`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `os`、`uuid`、`wave`、`google.genai`（`genai, types`）、`astrbot.logger`、`astrbot.core.utils.astrbot_path`、`..entities.ProviderType`、`..provider.TTSProvider`、`..register.register_provider_adapter`

### `sources/genie_tts.py`
- **职责**: Genie TTS 适配器（本地 ONNX 模型），需安装 `genie_tts` 包。支持流式（`support_stream=True`），在 `get_audio_stream` 中按文本块生成 WAV bytes 入队。
- **核心类**: `GenieTTSProvider(TTSProvider)` — 注册名 `genie_tts`。
  - 关键方法: `support_stream() -> True`、`async get_audio(text)`（executor 内调 `genie.tts`）、`async get_audio_stream(text_queue, audio_queue)`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `asyncio`、`os`、`uuid`、`astrbot.core.logger`、`astrbot.core.provider.entities.ProviderType`、`astrbot.core.provider.provider.TTSProvider`、`astrbot.core.provider.register.register_provider_adapter`、`astrbot.core.utils.astrbot_path`、`genie_tts`（可选导入）

### `sources/gsv_selfhosted_source.py`
- **职责**: GPT-SoVITS 自托管 TTS 适配器，请求本地 `/tts` 端点，初始化时设置 GPT/SoVITS 模型权重路径。
- **核心类**: `ProviderGSVTTS(TTSProvider)` — 注册名 `gsv_tts_selfhost`。
  - 关键方法: `async initialize()` — 创建 session + `_set_model_weights`；`get_session()`、`_make_request(endpoint, params, retries=3)`、`_set_model_weights()`、`async get_audio(text)`、`build_synthesis_params(text)`、`async terminate()`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `asyncio`、`os`、`uuid`、`aiohttp`、`astrbot.logger`、`astrbot.core.utils.astrbot_path`、`..entities.ProviderType`、`..provider.TTSProvider`、`..register.register_provider_adapter`

### `sources/gsvi_tts_source.py`
- **职责**: GSVI TTS API 适配器，请求 `/infer_single`，返回 audio_url 后下载。
- **核心类**: `ProviderGSVITTS(TTSProvider)` — 注册名 `gsvi_tts_api`。
  - 关键方法: `async get_audio(text)`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `uuid`、`pathlib.Path`、`aiohttp`、`astrbot.core.utils.astrbot_path`、`..entities.ProviderType`、`..provider.TTSProvider`、`..register.register_provider_adapter`

### `sources/minimax_tts_api_source.py`
- **职责**: MiniMax TTS 适配器，SSE 流式请求 `/t2a_v2`，解析 hex 编码的音频数据。支持 timber_weight、voice_setting、audio_setting。
- **核心类**: `ProviderMiniMaxTTSAPI(TTSProvider)` — 注册名 `minimax_tts_api`。
  - 关键方法: `_build_tts_stream_body(text)`、`_call_tts_stream(text) -> AsyncIterator[str]`、`_audio_play(audio_stream) -> bytes`、`async get_audio(text)`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `json`、`os`、`uuid`、`aiohttp`、`astrbot.api.logger`、`astrbot.core.utils.astrbot_path`、`..entities.ProviderType`、`..provider.TTSProvider`、`..register.register_provider_adapter`

### `sources/mimo_tts_api_source.py`
- **职责**: 小米 MiMo TTS 适配器，复用 `mimo_api_common` 工具，请求 `/chat/completions`，支持 style_prompt/dialect/seed_text，voice design 模型不发送 voice 参数。
- **核心类**: `ProviderMiMoTTSAPI(TTSProvider)` — 注册名 `mimo_tts_api`。
  - 关键方法: `_build_user_prompt()`、`_build_style_prefix()`（唱歌特殊处理 `<style>唱歌</style>`）、`_build_assistant_content(text)`、`_build_payload(text)`、`async get_audio(text)`、`async terminate()`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `base64`、`uuid`、`..entities.ProviderType`、`..provider.TTSProvider`、`..register.register_provider_adapter`、`.mimo_api_common`（多个常量与函数）

### `sources/openai_tts_api_source.py`
- **职责**: OpenAI TTS 适配器，用 `AsyncOpenAI.audio.speech.with_streaming_response.create` 流式生成 WAV。
- **核心类**: `ProviderOpenAITTSAPI(TTSProvider)` — 注册名 `openai_tts_api`。
  - 关键方法: `async get_audio(text)`、`async terminate()`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `os`、`uuid`、`httpx`、`openai`（`NOT_GIVEN, AsyncOpenAI`）、`astrbot.logger`、`astrbot.core.utils.astrbot_path`、`..entities.ProviderType`、`..provider.TTSProvider`、`..register.register_provider_adapter`

### `sources/volcengine_tts.py`
- **职责**: 火山引擎 TTS 适配器，请求 `/api/v1/tts`，返回 base64 编码 mp3，写入文件。
- **核心类**: `ProviderVolcengineTTS(TTSProvider)` — 注册名 `volcengine_tts`。
  - 关键方法: `_build_request_payload(text)`、`async get_audio(text)`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `asyncio`、`base64`、`json`、`os`、`traceback`、`uuid`、`aiohttp`、`astrbot.logger`、`astrbot.core.utils.astrbot_path`、`..entities.ProviderType`、`..provider.TTSProvider`、`..register.register_provider_adapter`

---

## 六、STT 提供商适配器（sources/）

本组 5 个文件均继承 `STTProvider`，实现 `get_text(audio_url) -> str`，注册类型 `ProviderType.SPEECH_TO_TEXT`。

### `sources/mimo_stt_api_source.py`
- **职责**: 小米 MiMo STT 适配器，复用 `mimo_api_common`，请求 `/chat/completions`。区分 ASR 模型（裸音频）与多模态模型（音频+文本指令）两种消息格式。
- **核心类**: `ProviderMiMoSTTAPI(STTProvider)` — 注册名 `mimo_stt_api`。
  - 关键方法: `_is_asr_model() -> bool`、`_build_messages(audio_data_url) -> list[dict]`、`async get_text(audio_url)`（finally 清理临时文件）、`async terminate()`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `..entities.ProviderType`、`..provider.STTProvider`、`..register.register_provider_adapter`、`.mimo_api_common`（多个常量与函数）

### `sources/sensevoice_selfhosted_source.py`
- **职责**: SenseVoice 自托管 STT 适配器，使用 `funasr_onnx.SenseVoiceSmall` 本地推理，支持情绪提取（`is_emotion`），`rich_transcription_postprocess` 后处理。
- **核心类**: `ProviderSenseVoiceSTTSelfHost(STTProvider)` — 注册名 `sensevoice_stt_selfhost`。
  - 关键方法: `async initialize()` — executor 加载模型；`async get_text(audio_url)` — executor 调模型，正则提取情绪
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `asyncio`、`re`、`funasr_onnx`（`SenseVoiceSmall`）、`funasr_onnx.utils.postprocess_utils`（`rich_transcription_postprocess`）、`astrbot.core.logger`、`astrbot.core.utils.media_utils.MediaResolver`、`..entities.ProviderType`、`..provider.STTProvider`、`..register.register_provider_adapter`

### `sources/whisper_api_source.py`
- **职责**: OpenAI Whisper API 适配器，用 `AsyncOpenAI.audio.transcriptions.create`。
- **核心类**: `ProviderOpenAIWhisperAPI(STTProvider)` — 注册名 `openai_whisper_api`。
  - 关键方法: `async get_text(audio_url)` — MediaResolver 转 wav 后调用、`async terminate()`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `openai`（`NOT_GIVEN, AsyncOpenAI`）、`astrbot.core.utils.media_utils.MediaResolver`、`..entities.ProviderType`、`..provider.STTProvider`、`..register.register_provider_adapter`

### `sources/whisper_selfhosted_source.py`
- **职责**: OpenAI Whisper 自托管适配器，使用 `whisper.load_model` 本地推理，支持 device（cpu/mps）配置与回退。
- **核心类**: `ProviderOpenAIWhisperSelfHost(STTProvider)` — 注册名 `openai_whisper_selfhost`。
  - 关键方法: `_resolve_device() -> str`（mps 可用性检查）、`async initialize()` — executor 加载模型；`async get_text(audio_url)` — executor 调 `transcribe`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `asyncio`、`functools.partial`、`whisper`、`astrbot.core.logger`、`astrbot.core.utils.media_utils.MediaResolver`、`..entities.ProviderType`、`..provider.STTProvider`、`..register.register_provider_adapter`

### `sources/xinference_stt_provider.py`
- **职责**: Xinference STT 适配器，使用 `xinference_client`，支持 `launch_model_if_not_running`。因官方 async client 实现有问题，直接用 `aiohttp` 走 `/v1/audio/transcriptions`（OpenAI 兼容）。
- **核心类**: `ProviderXinferenceSTT(STTProvider)` — 注册名 `xinference_stt`。
  - 关键方法: `async initialize()` — 连接/拉起模型；`async get_text(audio_url)` — MediaResolver 转 wav，FormData 上传；`async terminate()`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `aiohttp`、`xinference_client.client.restful.async_restful_client.AsyncClient`、`astrbot.core.logger`、`astrbot.core.utils.media_utils.MediaResolver`、`..entities.ProviderType`、`..provider.STTProvider`、`..register.register_provider_adapter`

---

## 七、公共工具文件（sources/）

### `sources/request_retry.py`
- **职责**: Provider 请求重试公共工具。基于 `tenacity` 实现异步重试，针对可重试错误（连接错误、`APIConnectionError`/`APITimeoutError`、特定 HTTP 状态码 408/409/429/500/502/503/504/529 及 5xx）进行指数退避重试。提供普通调用与异步上下文管理器两种用法。
- **核心类**: 无
- **核心函数**:
  - `_get_status_code(error) -> int|None` — 从 `status_code`/`status`/`code`/`response.status_code` 属性取状态码
  - `_is_retryable_provider_request_error(error, *, retry_rate_limits) -> bool` — 判断是否可重试（连接错误、特定异常类型名、状态码；429 受 `retry_rate_limits` 控制）
  - `_log_retry(provider_label, retry_state, max_attempts) -> None`
  - `_build_retrying(provider_label, *, retry_rate_limits, max_attempts) -> AsyncRetrying` — 构造 tenacity 重试器
  - `async retry_provider_request(provider_label, request_factory, *, retry_rate_limits=True, max_attempts=None) -> T` — 重试执行 awaitable
  - `async retry_provider_request_context(provider_label, context_manager_factory, *, retry_rate_limits=True, max_attempts=None) -> AsyncIterator[T]` — 重试执行异步上下文管理器
- **关键常量**:
  - `REQUEST_RETRY_ATTEMPTS = 5`
  - `REQUEST_RETRY_WAIT_MIN_S = 0.2`
  - `REQUEST_RETRY_WAIT_MAX_S = 30`
  - `REQUEST_RETRY_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504, 529}`
  - `T = TypeVar("T")`
- **依赖**:
  - 标准库: `collections.abc`（`AsyncIterator, Awaitable, Callable`）、`contextlib`（`AbstractAsyncContextManager, asynccontextmanager`）、`typing.TypeVar`
  - 第三方: `tenacity`（`AsyncRetrying, RetryCallState, retry_if_exception, stop_after_attempt, wait_exponential`）
  - astrbot 内部: `astrbot.logger`、`astrbot.core.utils.config_number.coerce_int_config`、`astrbot.core.utils.network_utils.is_connection_error`

### `sources/mimo_api_common.py`
- **职责**: 小米 MiMo TTS/STT 共享工具与常量。提供默认 API 基址/模型/语音/系统提示常量、HTTP 客户端构造、URL 拼接、音频输入预处理（WAV 格式校验，拒绝 SILK 等非 WAV 数据）、临时文件清理。
- **核心类**: `MiMoAPIError(Exception)`
- **核心函数**:
  - `normalize_timeout(timeout) -> int|None` — 超时规范化
  - `build_headers(api_key) -> dict[str, str]` — 构造 Bearer 头
  - `get_temp_dir() -> Path` — 获取临时目录
  - `create_http_client(timeout, proxy) -> httpx.AsyncClient` — 创建带代理的 httpx 客户端
  - `build_api_url(api_base) -> str` — 拼接 `/chat/completions`
  - `async prepare_audio_input(audio_source) -> tuple[str, list[Path]]` — 音频→base64 data URL，校验 WAV
  - `_decode_base64_header(base64_data) -> bytes` — 解码头部用于格式检测
  - `_validate_wav_payload(base64_data, audio_source) -> None` — 校验 RIFF/WAVE，拒绝 SILK
  - `cleanup_files(paths) -> None` — 清理临时文件
- **关键常量**:
  - `DEFAULT_MIMO_API_BASE = "https://api.xiaomimimo.com/v1"`
  - `DEFAULT_MIMO_TTS_MODEL = "mimo-v2-tts"`
  - `DEFAULT_MIMO_TTS_VOICE = "mimo_default"`
  - `DEFAULT_MIMO_TTS_SEED_TEXT = "Hello, MiMo, have you had lunch?"`
  - `DEFAULT_MIMO_STT_MODEL = "mimo-v2.5-asr"`
  - `DEFAULT_MIMO_STT_SYSTEM_PROMPT`、`DEFAULT_MIMO_STT_USER_PROMPT`
- **依赖**:
  - 标准库: `base64`、`pathlib.Path`
  - 第三方: `httpx`
  - astrbot 内部: `astrbot.logger`、`astrbot.core.utils.astrbot_path.get_astrbot_temp_path`、`astrbot.core.utils.media_utils`（`MediaResolver, describe_media_ref`）

---

## 附录：架构关系总结

**继承关系**:
- `AbstractProvider` → `Provider`（LLM）、`STTProvider`、`TTSProvider`、`EmbeddingProvider`、`RerankProvider`
- LLM 适配器: `ProviderOpenAIOfficial`（openai/groq/longcat/aihubmix/openrouter/xai/xiaomi/zhipu 的基类）、`ProviderAnthropic`（anthropic/kimi_code/xiaomi_token_plan/minimax_token_plan 的基类）、`ProviderGoogleGenAI`（gemini）

**注册机制**: `@register_provider_adapter(type_name, desc, provider_type, default_config_tmpl, provider_display_name)` 装饰器 → 写入 `provider_registry` + `provider_cls_map` → `ProviderManager.dynamic_import_provider` 按 type 名导入模块触发注册 → `load_provider` 按 `provider_cls_map[type]` 实例化。

**重试机制**: 所有 LLM 适配器通过 `retry_provider_request`（tenacity）统一重试；`ProviderOpenAIOfficial` 另有 10 次 Key 轮转/上下文回退重试层。

**多模态适配**: `modalities.py` 在上下文发送前清洗不支持的模态；各 LLM 适配器在 `_prepare_payload`/`_prepare_conversation` 中做格式转换（OpenAI image_url/audio_url ↔ Anthropic image source ↔ Gemini Part.from_bytes）。

**MCP 集成**: `FunctionToolManager` 管理 MCP 服务生命周期，工具经 `_PermissionGuardedTool` 包裹后进入 `ToolSet`，权限从 `sp.tool_permissions._default` 读取。

**Key 管理**: `ProviderManager._resolve_env_key_list` 支持 `$ENV`/`${ENV}` 环境变量引用；多 Key 列表轮转由各 LLM 适配器在 429 等错误时处理。


---

## 章节六：core/agent 根目录与 context

# AstrBot Agent 模块逐文件详解（Part 1）

分析目录：`c:\Users\xwzwO\Documents\GitHub\astrbot_plugin_my_demo\.venv\lib\site-packages\astrbot\core\agent`

> 说明：`agent/` 根目录与 `agent/context/` 子目录均为 **命名空间包**（namespace package），均**不存在 `__init__.py` 文件**。任务列表中的 `agent/__init__.py` 与 `agent/context/__init__.py` 实际缺失，下面不再单独列出。

---

## 一、agent 根目录文件

### `agent/agent.py`
- **职责**: 定义 Agent 数据类，作为 Agent 的核心声明式描述（名称、指令、工具、钩子、开场白）。
- **核心类**:
  - `Agent(Generic[TContext])` — 基类 `dataclass`，Generic[TContext]
    - 职责：声明式描述一个 Agent 的配置（供 runner 使用）
    - 关键属性：`name: str`、`instructions: str | None`、`tools: list[str | FunctionTool] | None`、`run_hooks: BaseAgentRunHooks[TContext] | None`、`begin_dialogs: list[Any] | None`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `.hooks.BaseAgentRunHooks`、`.run_context.TContext`、`.tool.FunctionTool`

---

### `agent/run_context.py`
- **职责**: 定义 Agent 运行时上下文包装类 `ContextWrapper`，承载运行间状态、消息上下文与工具超时。
- **核心类**:
  - `ContextWrapper(Generic[TContext])` — pydantic dataclass，Generic[TContext]
    - 职责：在 Agent 运行期间传递额外数据/状态，并维护 LLM 消息上下文
    - 关键属性：`context: TContext`（用户自定义上下文）、`messages: list[Message]`（由 runner 自动维护）、`tool_call_timeout: int = 120`（工具调用超时秒数）
- **核心函数**: 无
- **关键常量**:
  - `TContext = TypeVar("TContext", default=Any)` — 上下文类型变量
  - `NoContext = ContextWrapper[None]` — 无上下文类型的便捷别名
- **依赖**: `.message.Message`

---

### `agent/message.py`
- **职责**: 定义 LLM 对话消息模型与多模态内容片段（受 MoonshotAI/kosong 启发，Apache-2.0），并提供 checkpoint 内部消息的绑定/转储工具函数。
- **核心类**:
  - `ContentPart(BaseModel)` — 所有内容片段的基类
    - 职责：注册子类（按 `type` 字段）并通过 pydantic 自定义 schema 实现 dict → 子类的反序列化派发
    - 关键属性：`type: Literal["text","think","image_url","audio_url"]`、`_no_save: bool`（PrivateAttr，标记仅供 provider 使用、不持久化）
    - 关键方法：
      - `__init_subclass__` — 自动将子类按 `type` 注册到 `__content_part_registry`
      - `__get_pydantic_core_schema__` — 自定义校验：dict 含 `type` 时派发到对应子类
      - `mark_as_temp()` — 标记为 provider-facing only，不持久化
      - `model_dump_for_context()` — 序列化，含 `_no_save` 标记
  - `TextPart(ContentPart)` — 文本片段，`type="text"`，`text: str`
  - `ThinkPart(ContentPart)` — 思考片段，`type="think"`，`think: str`、`encrypted: str | None`
    - `merge_in_place(other)` — 合并另一 ThinkPart（仅当自身未加密）
  - `ImageURLPart(ContentPart)` — 图片 URL 片段，内嵌 `ImageURL`（`url`、`id`）
  - `AudioURLPart(ContentPart)` — 音频 URL 片段，内嵌 `AudioURL`（`url`、`id`）
  - `ToolCall(BaseModel)` — 工具调用请求
    - 内嵌 `FunctionBody`（`name`、`arguments`）
    - 属性：`type="function"`、`id: str`、`function: FunctionBody`、`extra_content: dict | None`
    - `serialize(handler)` — 自定义序列化，`extra_content` 为 None 时移除该字段
  - `ToolCallPart(BaseModel)` — 工具调用参数片段（`arguments_part`）
  - `CheckpointData(BaseModel)` — 内部 checkpoint 数据（`id: str`）
  - `Message(BaseModel)` — 对话消息
    - 属性：`role`（system/user/assistant/tool/_checkpoint）、`content`、`tool_calls`、`tool_call_id`、`_no_save`、`_checkpoint_after`
    - `check_content_required()` — model_validator：校验 content 与 role 的组合合法性
    - `serialize(handler)` — 自定义序列化，移除 None 字段
  - `AssistantMessageSegment(Message)` — role 固定为 "assistant"
  - `ToolCallMessageSegment(Message)` — role 固定为 "tool"
  - `UserMessageSegment(Message)` — role 固定为 "user"
  - `SystemMessageSegment(Message)` — role 固定为 "system"
  - `CheckpointMessageSegment(Message)` — role 固定为 "_checkpoint"，content 为 CheckpointData
- **核心函数**:
  - `is_checkpoint_message(message)` — 判断是否为内部 checkpoint 消息
  - `get_checkpoint_id(message)` — 从 checkpoint 消息提取 id
  - `strip_checkpoint_messages(history)` — 从 provider-facing 历史中移除 checkpoint 消息
  - `_get_checkpoint_data(message)` — 内部：取出 CheckpointData 对象
  - `bind_checkpoint_messages(history)` — 加载持久化历史，将 checkpoint 段绑定到前一条消息的 `_checkpoint_after`
  - `dump_messages_with_checkpoints(messages)` — 转储运行时消息并重新插入绑定的 checkpoint 段
- **关键常量**:
  - `CHECKPOINT_ROLE = "_checkpoint"` — checkpoint 角色字符串
  - `ContentPartT = TypeVar("ContentPartT", bound="ContentPart")`
- **依赖**: pydantic、pydantic_core；无 astrbot 内部模块依赖（被其他模块依赖）

---

### `agent/response.py`
- **职责**: 定义 Agent 响应数据结构与运行统计（token、耗时）。
- **核心类**:
  - `AgentResponseData(T.TypedDict)` — 响应数据，字段 `chain: MessageChain`
  - `AgentResponse` — dataclass，字段 `type: str`、`data: AgentResponseData`
  - `AgentStats` — dataclass，运行统计
    - 属性：`token_usage: TokenUsage`、`current_context_tokens: int`、`start_time`、`end_time`、`time_to_first_token`
    - `duration` property — end_time - start_time
    - `to_dict()` — 转字典
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `astrbot.core.message.message_event_result.MessageChain`、`astrbot.core.provider.entities.TokenUsage`

---

### `agent/hooks.py`
- **职责**: 定义 Agent 运行生命周期钩子的基类（开始、工具开始/结束、结束）。
- **核心类**:
  - `BaseAgentRunHooks(Generic[TContext])` — 钩子基类
    - 职责：提供 Agent 运行各阶段的空实现钩子，供子类覆盖
    - 关键方法：
      - `on_agent_begin(run_context)` — Agent 开始时
      - `on_tool_start(run_context, tool, tool_args)` — 工具调用前
      - `on_tool_end(run_context, tool, tool_args, tool_result)` — 工具调用后
      - `on_agent_done(run_context, llm_response)` — Agent 结束时
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `mcp`、`astrbot.core.agent.tool.FunctionTool`、`astrbot.core.provider.entities.LLMResponse`、`.run_context.ContextWrapper/TContext`

---

### `agent/tool.py`
- **职责**: 定义函数调用工具的 schema、可调用工具 `FunctionTool`，以及工具集合 `ToolSet`（含 OpenAI/Anthropic/Google 多种 API schema 转换）。
- **核心类**:
  - `ToolSchema` — pydantic dataclass，工具 schema
    - 属性：`name`、`description`、`parameters: ParametersType`（JSON Schema）
    - `validate_parameters()` — 用 jsonschema 校验 parameters 符合 Draft 2020-12 元 schema
  - `FunctionTool(ToolSchema, Generic[TContext])` — 可调用工具
    - 属性：`handler`（async callable）、`handler_module_path`、`active: bool = True`、`is_background_task: bool = False`
    - `__repr__()` — 工具表示
    - `call(context, **kwargs)` — 执行工具（默认抛 NotImplementedError，子类或 handler 实现）
  - `ToolSet` — pydantic dataclass，工具集合
    - 属性：`tools: list[FunctionTool]`
    - 关键方法：
      - `empty()` — 是否为空
      - `add_tool(tool)` — 添加工具，同名按 active 状态覆盖
      - `remove_tool(name)` — 按名移除
      - `get_tool(name)` — 按名获取
      - `get_light_tool_set()` — 仅 name/description 的轻量集合
      - `get_param_only_tool_set()` — 仅 name/parameters（无 description）
      - `add_func/remove_func/get_func` — 已废弃（@deprecated 4.0.0）
      - `func_list` property — 工具列表
      - `openai_schema(omit_empty_parameter_field=False)` — 转 OpenAI function calling schema
      - `anthropic_schema()` — 转 Anthropic schema
      - `google_schema()` — 转 Google GenAI schema（含 `convert_schema` 内部函数处理类型/格式兼容）
      - `get_func_desc_*` — 已废弃（@deprecated 4.0.0）
      - `names()` — 工具名列表
      - `merge(other)` — 合并另一 ToolSet
      - `__len__/__bool__/__iter__/__repr__/__str__`
- **核心函数**: 无
- **关键常量**:
  - `ParametersType = dict[str, Any]`
  - `ToolExecResult = str | mcp.types.CallToolResult`
- **依赖**: `jsonschema`、`mcp`、`deprecated`、pydantic；`astrbot.core.message.message_event_result.MessageEventResult`；`.run_context.ContextWrapper/TContext`

---

### `agent/tool_executor.py`
- **职责**: 定义工具执行器的抽象基类 `BaseFunctionToolExecutor`。
- **核心类**:
  - `BaseFunctionToolExecutor(Generic[TContext])` — 工具执行器基类
    - 职责：定义工具执行的统一接口
    - 关键方法：
      - `execute(cls, tool, run_context, **tool_args)` — classmethod async，返回 `AsyncGenerator[Any | CallToolResult, None]`（默认空实现 `...`）
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `mcp`；`.run_context.ContextWrapper/TContext`、`.tool.FunctionTool`

---

### `agent/tool_image_cache.py`
- **职责**: 工具调用返回图片的缓存管理（单例），允许 LLM 在发送给用户前审阅图片；存储于 `data/temp/tool_images/`。
- **核心类**:
  - `CachedImage` — dataclass，缓存图片元数据
    - 属性：`tool_call_id`、`tool_name`、`file_path`、`mime_type`、`created_at`
  - `ToolImageCache` — 单例缓存管理器
    - 关键 ClassVar：`_instance`、`CACHE_DIR_NAME = "tool_images"`、`CACHE_EXPIRY = 3600`（1 小时）
    - `__new__()` — 单例创建
    - `__init__()` — 初始化缓存目录
    - `_get_file_extension(mime_type)` — MIME → 扩展名
    - `save_image(base64_data, tool_call_id, tool_name, index, mime_type)` — 解码 base64 并保存，返回 CachedImage
    - `get_image_base64_by_path(file_path, mime_type)` — 读取文件并返回 (base64, mime_type)
    - `cleanup_expired()` — 清理过期缓存，返回清理数量
- **核心函数**: 无
- **关键常量**: 
  - `tool_image_cache = ToolImageCache()` — 全局单例
- **依赖**: `astrbot.logger`、`astrbot.core.utils.astrbot_path.get_astrbot_temp_path`

---

### `agent/handoff.py`
- **职责**: 定义 `HandoffTool`，用于将任务委托（handoff）给另一个 Agent（SubAgent 编排用）。
- **核心类**:
  - `HandoffTool(FunctionTool, Generic[TContext])` — 任务移交工具
    - 职责：作为 FunctionTool 暴露给主 Agent，调用时将请求转给子 Agent
    - 关键属性：`agent: Agent`（移交目标）、`provider_id: str | None`（可选 provider 覆盖）
    - 关键方法：
      - `__init__(agent, parameters, tool_description, **kwargs)` — 工具名 `transfer_to_{agent.name}`，默认描述/参数
      - `default_parameters()` — 默认参数 schema（input / image_urls / background_task）
      - `default_description(agent_name)` — 默认描述 "Delegate tasks to {agent_name} agent..."
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `.agent.Agent`、`.run_context.TContext`、`.tool.FunctionTool`

---

### `agent/mcp_client.py`
- **职责**: MCP（Model Context Protocol）客户端实现，含 stdio/SSE/Streamable HTTP 连接、安全校验、重连机制，以及将 MCP 工具包装为 `FunctionTool`。
- **核心类**:
  - `MCPClient` — MCP 客户端
    - 职责：管理到 MCP server 的连接生命周期、工具列举、带重连的工具调用
    - 关键属性：`session`、`_connection_task`、`_old_connection_tasks`、`exit_stack`、`name`、`active`、`tools`、`server_errlogs`、`running_event`、`_mcp_server_config`、`_server_name`、`_reconnect_lock`、`_reconnecting`
    - 关键方法：
      - `_run_connection(mcp_server_config, name, ready)` — 在专用 task 中持有连接生命周期（避免跨 task 退出 anyio cancel scope）
      - `connect_to_server(mcp_server_config, name)` — 连接 MCP server（按 url/transport 选择 SSE 或 Streamable HTTP，否则 stdio）
      - `_do_connect(mcp_server_config, name)` — 实际建立连接（SSE / streamable_http / stdio），含 logging_callback
      - `list_tools_and_save()` — 列举工具并保存到 self.tools
      - `_cancel_connection_task(task)` — 取消并跟踪旧连接 task
      - `_reconnect()` — 重连（带 lock 防并发）
      - `call_tool_with_reconnect(tool_name, arguments, read_timeout_seconds)` — 调用工具，ClosedResourceError 时重连 + tenacity 重试（最多 2 次）
      - `cleanup()` — 清理资源、取消所有连接 task
  - `MCPTool(FunctionTool, Generic[TContext])` — MCP 工具的 FunctionTool 包装
    - 职责：将 mcp.Tool 包装为 FunctionTool，`call()` 委托给 MCPClient
    - 关键属性：`mcp_tool`、`mcp_client`、`mcp_server_name`
    - `call(context, **kwargs)` — 调用 `mcp_client.call_tool_with_reconnect`
- **核心函数**:
  - `_prepare_config(config)` — 处理嵌套 `mcpServers` 配置
  - `_normalize_stdio_command_name(command)` — 归一化 stdio 命令名（去后缀、小写）
  - `_get_stdio_command_allowlist()` — 获取允许的 stdio 命令白名单（默认 + 环境变量 `ASTRBOT_MCP_STDIO_ALLOWED_COMMANDS` 覆盖）
  - `_is_stdio_config(config)` — 判断是否为 stdio 配置
  - `_validate_stdio_args(command_name, args)` — 校验 stdio 参数（禁止 python -c / node -e 等内联执行；禁止 docker 危险参数）
  - `validate_mcp_stdio_config(config)` — 校验 stdio MCP 配置（命令非空、无 shell 元字符、不在拒绝列表、在白名单内、env 类型正确）
  - `_prepare_stdio_env(config)` — Windows 下保留可执行文件解析的环境变量
  - `_merge_environment_variables(env)` — 合并环境变量（Windows 大小写不敏感处理）
  - `_quick_test_mcp_connection(config)` — 快速测试 MCP server 连通性（streamable_http 用 POST initialize，其他用 GET）
  - `_normalize_mcp_input_schema(schema)` — 归一化非标准 MCP JSON Schema（将属性级 `required: bool` 提升到父级 `required` 数组）
- **关键常量**:
  - `_DEFAULT_STDIO_COMMAND_ALLOWLIST` — 默认允许的 stdio 命令（python/node/uv 等运行时）
  - `_DENIED_STDIO_COMMANDS` — 拒绝的命令（bash/sh/cmd/powershell/curl/wget/ssh/rm/sudo 等）
  - `_SHELL_META_RE` — shell 元字符正则
  - `_PYTHON_INLINE_CODE_FLAGS = frozenset({"-c"})`
  - `_JS_INLINE_CODE_FLAGS = frozenset({"-e","--eval","-p","--print"})`
  - `_DENIED_DOCKER_ARGS` — 拒绝的 docker 参数（--privileged/--pid=host/--network=host 等）
  - `_STDIO_ALLOWLIST_ENV = "ASTRBOT_MCP_STDIO_ALLOWED_COMMANDS"`
- **依赖**: `httpx`、`tenacity`、`aiohttp`、`anyio`、`mcp`（含 `sse_client`、`streamable_http_client`、`ClientSession`、`StdioServerParameters`、`stdio_client`）；`astrbot.logger`、`astrbot.core.agent.run_context.ContextWrapper`、`astrbot.core.utils.log_pipe.LogPipe`；`.run_context.TContext`、`.tool.FunctionTool`

---

## 二、agent/context 子目录文件

### `agent/context/config.py`
- **职责**: 定义上下文管理的配置数据类 `ContextConfig`（最大 token、最大轮次、压缩参数、自定义计数器/压缩器）。
- **核心类**:
  - `ContextConfig` — dataclass，上下文配置
    - 属性：
      - `max_context_tokens: int = 0`（≤0 表示无限制）
      - `enforce_max_turns: int = -1`（-1 无限制，压缩前执行）
      - `truncate_turns: int = 1`（触发截断时一次丢弃的轮数）
      - `llm_compress_instruction: str | None`
      - `llm_compress_keep_recent_ratio: float = 0.15`
      - `llm_compress_provider: "Provider | None"`（None 则用截断策略）
      - `custom_token_counter: TokenCounter | None`
      - `custom_compressor: ContextCompressor | None`
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `.compressor.ContextCompressor`、`.token_counter.TokenCounter`；TYPE_CHECKING 下 `astrbot.core.provider.provider.Provider`

---

### `agent/context/token_counter.py`
- **职责**: 定义 token 计数协议 `TokenCounter` 与默认估算实现 `EstimateTokenCounter`（支持多模态）。
- **核心类**:
  - `TokenCounter(Protocol)` — runtime_checkable 协议
    - `count_tokens(messages, trusted_token_usage=0) -> int` — 计数接口
  - `EstimateTokenCounter` — 估算实现
    - 职责：基于字符类型估算 token；支持图片/音频/思考片段
    - `count_tokens(messages, trusted_token_usage=0)` — trusted > 0 时直接返回；否则累加各消息 token
    - `_estimate_tokens(text)` — 中文 ×0.6 + 其他 ×0.3
- **核心函数**: 无
- **关键常量**:
  - `IMAGE_TOKEN_ESTIMATE = 765` — 图片 token 估算（保守中位数）
  - `AUDIO_TOKEN_ESTIMATE = 500` — 音频 token 估算
- **依赖**: `..message.AudioURLPart/ImageURLPart/Message/TextPart/ThinkPart`

---

### `agent/context/truncator.py`
- **职责**: 上下文截断器，按轮次/最旧/对半截断消息列表，并修复 tool_calls 与 tool 响应的配对合法性。
- **核心类**:
  - `ContextTruncator` — 截断器
    - 关键方法：
      - `_has_tool_calls(message)` — 判断 assistant 消息是否含 tool_calls
      - `_split_system_rest(messages)` staticmethod — 拆分 system 与非 system 消息
      - `_ensure_user_message(system_messages, truncated, original_messages)` staticmethod — 确保 system 后紧跟 user 消息（满足 Zhipu 等 API 要求）
      - `fix_messages(messages)` — 修复 tool/tool_calls 配对：丢弃孤立的 tool 消息，保留有效 assistant(tool_calls)+tool 链
      - `truncate_by_turns(messages, keep_most_recent_turns, drop_turns=1)` — 按轮次截断，保留最近 N 轮
      - `truncate_by_dropping_oldest_turns(messages, drop_turns=1)` — 丢弃最旧 N 轮
      - `truncate_by_halving(messages)` — 对半截断保留最近一半
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `..message.Message`

---

### `agent/context/compressor.py`
- **职责**: 定义上下文压缩器协议与两种实现：按轮次截断压缩、LLM 摘要压缩。
- **核心类**:
  - `ContextCompressor(Protocol)` — runtime_checkable 协议
    - `should_compress(messages, current_tokens, max_tokens) -> bool`
    - `__call__(messages) -> list[Message]`（async）
  - `TruncateByTurnsCompressor` — 按轮次截断压缩实现
    - 属性：`truncate_turns: int = 1`、`compression_threshold: float = 0.82`
    - `should_compress(...)` — 使用率 > threshold 时触发
    - `__call__(messages)` — 调用 `ContextTruncator.truncate_by_dropping_oldest_turns`
  - `LLMSummaryCompressor` — LLM 摘要压缩实现
    - 属性：`provider`、`keep_recent_ratio`（clamp 0-0.3）、`compression_threshold`、`token_counter`、`instruction_text`
    - ClassVar：`TASK_CONTINUATION_INSTRUCTION`（任务延续指令）
    - `should_compress(...)` — 同上
    - `_split_recent_rounds_by_token_ratio(rounds, total_tokens)` — 按 token 预算将轮次拆为待摘要历史 + 保留的近期上下文（round 粒度）
    - `__call__(messages)` — 用 `split_into_rounds` 分轮，生成摘要（失败则原样返回兜底截断），构造 system+摘要对+近期轮次的结果
- **核心函数**:
  - `_extract_system_messages(messages)` — 提取前导 system 消息
- **关键常量**: 无（`TASK_CONTINUATION_INSTRUCTION` 为类属性）
- **依赖**: `astrbot.core.provider.modalities.log_context_sanitize_stats/sanitize_contexts_by_modalities`；`astrbot.core.provider.provider.Provider`（TYPE_CHECKING）；`astrbot.logger`；`..message.Message`、`.token_counter.EstimateTokenCounter/TokenCounter`、`..context.truncator.ContextTruncator`；运行时导入 `.round_utils.split_into_rounds`

---

### `agent/context/manager.py`
- **职责**: 上下文压缩管理器 `ContextManager`，按配置协调「轮次截断 → token 压缩 → 兜底对半截断」流程。
- **核心类**:
  - `ContextManager` — 压缩管理器
    - 属性：`config: ContextConfig`、`token_counter`、`truncator: ContextTruncator`、`compressor`（按配置选 custom/LLM/TruncateByTurns）
    - 关键方法：
      - `__init__(config)` — 初始化 token_counter/truncator/compressor（优先 custom，其次 llm_compress_provider，最后 TruncateByTurnsCompressor）
      - `process(messages, trusted_token_usage=0)` async — 主流程：1) enforce_max_turns 截断；2) max_context_tokens > 0 时计数并按需压缩；异常时返回原消息
      - `_run_compression(messages, prev_tokens)` async — 执行压缩 + 二次检查；仍超限则 `truncate_by_halving` 兜底
- **核心函数**: 无
- **关键常量**: 无
- **依赖**: `astrbot.logger`；`..message.Message`；`.compressor.LLMSummaryCompressor/TruncateByTurnsCompressor`、`.config.ContextConfig`、`.token_counter.EstimateTokenCounter`、`.truncator.ContextTruncator`

---

### `agent/context/round_utils.py`
- **职责**: 基于轮次的工具函数，供 LTM 压缩与 LLMSummaryCompressor 共享（分轮、渲染为文本）。
- **核心类**: 无
- **核心函数**:
  - `_segment_role(seg)` — 取段角色（Message 或 dict）
  - `split_into_rounds(contexts)` — 将扁平 contexts 按 user 段切分为逻辑轮次列表
  - `_content_to_text(content)` — 将 content（list/ContentPart/其他）转为 JSON 字符串
  - `_segment_content(seg)` — 取段内容（content 或 tool_calls）
  - `rounds_to_text(rounds)` — 将轮次渲染为 `--- Round i ---` 格式的纯文本（供 LLM 摘要）
- **关键常量**:
  - `RoundSegment = dict[str, Any] | Message` — 轮次段类型别名
- **依赖**: `..message.ContentPart/Message/ToolCall`

---

## 三、模块关系速览

- **入口数据模型**：`agent.py`（Agent 声明）+ `run_context.py`（ContextWrapper 运行态）+ `message.py`（消息与内容片段）+ `response.py`（响应与统计）
- **工具体系**：`tool.py`（FunctionTool/ToolSet/schema 转换）→ `tool_executor.py`（执行接口）→ `mcp_client.py`（MCP 工具实现）→ `handoff.py`（Agent 移交工具）→ `tool_image_cache.py`（工具图片缓存）
- **生命周期**：`hooks.py`（BaseAgentRunHooks）由 runner 调用
- **上下文管理**（`context/` 子目录）：`config.py`（配置）→ `manager.py`（流程编排）→ `token_counter.py`（计数）+ `truncator.py`（截断）+ `compressor.py`（压缩：截断/LLM 摘要）+ `round_utils.py`（分轮工具）
- **MCP 安全**：`mcp_client.py` 内置 stdio 命令白名单/拒绝列表、shell 元字符校验、docker 危险参数校验，并支持环境变量 `ASTRBOT_MCP_STDIO_ALLOWED_COMMANDS` 覆盖白名单


---

## 章节七：core/agent/runners（运行器）

# AstrBot `agent/runners` 目录逐文件详解

分析目标目录（Windows 绝对路径）：
`c:\Users\xwzwO\Documents\GitHub\astrbot_plugin_my_demo\.venv\lib\site-packages\astrbot\core\agent\runners`

本目录是 AstrBot Agent 框架的"运行器（Runner）"实现层，定义了不同类型 Agent 的执行循环。所有 Runner 均继承自 `base.py` 中的 `BaseAgentRunner` 抽象基类，遵循 `reset → step → step_until_done → done` 的统一生命周期。

---

## 1. `runners/__init__.py`

- **职责**：包入口，仅导出 `BaseAgentRunner` 抽象基类供上层使用。
- **核心内容**：
  - `from .base import BaseAgentRunner`
  - `__all__ = ["BaseAgentRunner"]`
- **依赖**：`runners/base.py`
- **说明**：未导出具体子类（`ToolLoopAgentRunner`、`CozeAgentRunner` 等），具体实现需通过各自子模块路径导入。

---

## 2. `runners/base.py`

- **职责**：定义所有 Agent Runner 的抽象基类与状态机枚举。
- **核心类**：

  ### `AgentState(Enum)`
  - 基类：`enum.Enum`（使用 `auto()`）
  - 职责：表示 Agent 运行状态机
  - 枚举值：`IDLE`（初始）、`RUNNING`（处理中）、`DONE`（完成）、`ERROR`（错误）

  ### `BaseAgentRunner(T.Generic[TContext])`
  - 基类：`typing.Generic[TContext]`
  - 职责：所有 Runner 的抽象基类，定义统一生命周期接口
  - 关键抽象方法：
    - `async reset(run_context, agent_hooks, **kwargs) -> None`：重置 Agent 到初始状态，新运行前调用
    - `async step() -> AsyncGenerator[AgentResponse, None]`：处理单个步骤
    - `async step_until_done(max_step) -> AsyncGenerator[AgentResponse, None]`：循环执行直到完成
    - `done() -> bool`：检查是否完成
    - `get_final_llm_resp() -> LLMResponse | None`：获取最终 LLM 响应
  - 关键普通方法：
    - `_transition_state(new_state: AgentState) -> None`：状态转换，带 debug 日志（依赖 `logger`），通过比较 `self._state` 切换
  - 关键属性（子类应设置）：`self._state`
- **依赖**：
  - 标准库：`abc`、`typing`、`enum`
  - astrbot：`astrbot.logger`、`astrbot.core.provider.entities.LLMResponse`
  - 相对包：`..hooks.BaseAgentRunHooks`、`..response.AgentResponse`、`..run_context.ContextWrapper / TContext`
- **关键常量**：无

---

## 3. `runners/tool_loop_agent_runner.py`（约 1470+ 行，大文件）

- **职责**：实现 AstrBot 内置的"工具循环（Tool-Loop）"Agent Runner，是默认且最核心的 Runner。负责 LLM 调用、流式输出、工具调用执行、上下文压缩、Fallback Provider、跟进消息（follow-up）、重复工具检测、工具结果溢出处理、skills_like 工具 schema 模式、用户中断等复杂逻辑。
- **核心类**：

  ### `_HandleFunctionToolsResult`（dataclass, slots=True）
  - 职责：封装 `_handle_function_tools` 的单次产出结果（一种三态联合体）
  - 字段：`kind: Literal["message_chain","tool_call_result_blocks","cached_image"]`、`message_chain`、`tool_call_result_blocks`、`cached_image`
  - 工厂类方法：`from_message_chain(chain)`、`from_tool_call_result_blocks(blocks)`、`from_cached_image(image)`

  ### `FollowUpTicket`（dataclass, slots=True）
  - 职责：表示一条在工具执行期间到达的"跟进消息"票据
  - 字段：`seq: int`、`text: str`、`consumed: bool = False`、`resolved: asyncio.Event`

  ### `_ToolExecutionInterrupted(Exception)`
  - 职责：自定义异常，工具执行被用户停止请求中断时抛出

  ### `ToolLoopAgentRunner(BaseAgentRunner[TContext])`
  - 基类：`BaseAgentRunner[TContext]`
  - 职责：实现完整工具循环 Agent；持有 Provider、上下文管理器、工具执行器、Hooks、流式状态等
  - 关键类常量（节选）：
    - `TOOL_RESULT_MAX_ESTIMATED_TOKENS = 27_500`
    - `TOOL_RESULT_PREVIEW_MAX_ESTIMATED_TOKENS = 7000`
    - `EMPTY_OUTPUT_RETRY_ATTEMPTS = 3`、`EMPTY_OUTPUT_RETRY_WAIT_MIN_S = 1`、`EMPTY_OUTPUT_RETRY_WAIT_MAX_S = 4`
    - `USER_INTERRUPTION_MESSAGE`：用户中断时插入的提示
    - `FOLLOW_UP_NOTICE_TEMPLATE`：跟进消息注入模板
    - `MAX_STEPS_REACHED_PROMPT`：达到最大步数后强制总结的提示
    - `SKILLS_LIKE_REQUERY_INSTRUCTION_TEMPLATE`、`SKILLS_LIKE_REQUERY_REPAIR_INSTRUCTION`：skills_like 模式的二阶段工具调用指令
    - `REPEATED_TOOL_NOTICE_L1/L2/L3_THRESHOLD = 3/4/5` 及对应 `*_TEMPLATE`：重复工具调用的分级提醒
    - `MALFORMED_TOOL_NAME_PLACEHOLDER = "__malformed_tool_name__"`
    - `TOOL_RESULT_OVERFLOW_NOTICE_TEMPLATE`：工具结果溢出落盘后的提示
  - 关键方法（按功能分组）：

    **生命周期 / 状态**
    - `async reset(provider, request, run_context, tool_executor, agent_hooks, streaming=False, enforce_max_turns=-1, llm_compress_instruction, llm_compress_keep_recent_ratio=0.15, llm_compress_provider, truncate_turns=1, custom_token_counter, custom_compressor, tool_schema_mode="full", fallback_providers, request_max_retries, tool_result_overflow_dir, read_tool, **kwargs)`：初始化所有运行态。构建 `ContextConfig` 与 `ContextManager`；去重 fallback providers；处理 `skills_like` 模式（用 light/param-only tool schema 替换 `req.func_tool`）；通过 `bind_checkpoint_messages` + `_assemble_request_context_for_provider` 组装初始 messages；初始化 `AgentStats`
    - `async step()`（override）：核心单步。流程：IDLE 时触发 `on_agent_begin` → 切到 RUNNING → 用 `request_context_manager.process` 压缩上下文 → `_iter_llm_responses_with_fallback` 流式拉取 → 对 chunk 流式 yield `streaming_delta` → 检测停止 → 处理最终 LLM 响应（err/无工具调用直接完成/有工具调用进入 `_handle_function_tools`）→ skills_like 模式下先 `_resolve_tool_exec` 再query → yield `llm_result` / `tool_call_result` / `agent_stats`
    - `async step_until_done(max_step)`（override）：循环 step；若达上限未完成，清空 `req.func_tool`、注入 `MAX_STEPS_REACHED_PROMPT`，再跑最后一步
    - `done()`（override）：`_state in (DONE, ERROR)`
    - `request_stop()`：设置 `_abort_signal`
    - `_is_stop_requested()`：查询 `_abort_signal.is_set()`
    - `was_aborted()`：返回 `_aborted`
    - `get_final_llm_resp()`（override）：返回 `self.final_llm_resp`
    - `async _finalize_aborted_step(llm_resp=None)`：用户中断时收尾，构造 `aborted` 类型响应，调用 `on_agent_done`

    **LLM 调用 / Provider 适配**
    - `async _iter_llm_responses(*, include_model=True)`：组装 payload（contexts、func_tool、session_id、extra_user_content_parts、abort_signal、request_max_retries），按 `streaming` 调用 `provider.text_chat_stream` 或 `provider.text_chat`
    - `async _iter_llm_responses_with_fallback()`：用 `tenacity.AsyncRetrying`（针对 `EmptyModelOutputError`，指数退避）+ 多 Provider fallback 候选链；切换 provider 时记录日志；对响应做 `_sanitize_malformed_tool_calls`；全部失败时构造 err LLMResponse
    - `_sanitize_contexts_for_provider(contexts)`：依据 provider 的 `modalities` 调 `sanitize_contexts_by_modalities` 过滤上下文
    - `_func_tool_for_provider()`：若 provider 的 `modalities` 不含 `tool_use` 则清空工具
    - `async _assemble_request_context_for_provider(request)`：按 modalities 决定是否保留 image/audio，调 `request.assemble_context`
    - `_simple_print_message_role(tag, messages)`：debug 打印消息角色摘要

    **工具执行**
    - `async _handle_function_tools(req, llm_response)`：迭代执行 LLM 返回的每个工具调用。yield `tool_call` 通知 → 解析工具（skills_like 模式从 raw tool set 取）→ 参数过滤（只传 `parameters.properties` 的键）→ `on_tool_start` hook → `tool_executor.execute` → 通过 `_iter_tool_executor_results` 消费 MCP `CallToolResult`：处理 `TextContent` / `ImageContent`（落盘到 `tool_image_cache`）/ `EmbeddedResource`（TextResourceContents / 图片 BlobResourceContents）；组装 `ToolCallMessageSegment`；对超长结果走 `_materialize_large_tool_result` + `_truncate_tool_result_preview`；最终 yield `tool_call_result_blocks` / `cached_image` / `message_chain`
    - `async _iter_tool_executor_results(executor)`：异步迭代工具执行器结果，监听 `_abort_signal`，中断时抛 `_ToolExecutionInterrupted`
    - `async _close_executor(executor)`：调用 `executor.aclose()`
    - `async _resolve_tool_exec(llm_resp)`：skills_like 模式下用 param-only 工具 schema 二次请求 LLM；若仍无工具调用且无有意义回复，再用 `SKILLS_LIKE_REQUERY_REPAIR_INSTRUCTION` 修复重试；返回 `(LLMResponse, ToolSet)`
    - `_build_tool_requery_context(tool_names, extra_instruction=None)`：为 skills_like 二次请求构造 contexts，注入 requery instruction
    - `_build_tool_subset(tool_set, tool_names)`：从 ToolSet 子集化
    - `_sanitize_malformed_tool_calls(llm_resp)`：修正畸形工具名
    - `_track_tool_call_streak(tool_name, normalized_args)`：跟踪相同工具+相同参数的连续次数（`_same_tool_streak`）
    - `_build_repeated_tool_call_guidance(tool_name, streak)`：按 L1/L2/L3 阈值返回对应提醒模板
    - `@staticmethod _has_meaningful_assistant_reply(llm_resp)`：判断是否有非空文本回复

    **工具结果处理 / 溢出**
    - `async _write_tool_result_overflow_file(...)`：将超大工具结果写入 `tool_result_overflow_dir` 落盘文件
    - `async _materialize_large_tool_result(...)`：超大结果物化（落盘 + 截断 preview + 注入 `TOOL_RESULT_OVERFLOW_NOTICE_TEMPLATE`）
    - `_truncate_tool_result_preview(...)`：按 `TOOL_RESULT_PREVIEW_MAX_ESTIMATED_TOKENS` 截断 preview
    - `_read_tool_hint()`：返回 read_tool 名称提示

    **跟进消息（follow-up）**
    - `follow_up(*, message_text)`：入队一条跟进消息票据
    - `_resolve_unconsumed_follow_ups()`：将未消费票据标记 resolved
    - `_consume_follow_up_notice()`：取出并标记 consumed，返回格式化提醒文本
    - `_merge_follow_up_notice(content)`：把跟进提醒合并到工具结果内容

    **完成 / 错误**
    - `async _complete_with_assistant_response(llm_resp)`：无工具调用时的正常收尾，构造 assistant message，触发 `on_agent_done`
    - `_get_persona_custom_error_message()`：从 event extras 读取 persona 自定义错误文案

  - 关键实例属性（reset 中设置）：
    - `req`、`streaming`、`enforce_max_turns`、`llm_compress_*`、`truncate_turns`、`custom_token_counter`、`custom_compressor`、`request_max_retries`、`tool_result_overflow_dir`、`read_tool`、`_tool_result_token_counter`
    - `request_context_manager_config`、`request_context_manager`
    - `provider`、`fallback_providers`
    - `final_llm_resp`、`_state`、`tool_executor`、`agent_hooks`、`run_context`
    - `_aborted`、`_abort_signal`、`_pending_follow_ups`、`_follow_up_seq`、`_last_tool_name`、`_last_tool_args`、`_same_tool_streak`
    - `tool_schema_mode`、`_tool_schema_param_set`、`_skill_like_raw_tool_set`
    - `stats: AgentStats`
- **核心函数（顶层）**：`ToolExecutorResultT = T.TypeVar("ToolExecutorResultT")`（类型变量）
- **依赖**：
  - 标准库：`asyncio`、`copy`、`sys`、`time`、`traceback`、`typing`、`uuid`、`contextlib.suppress`、`dataclasses`、`pathlib.Path`
  - 第三方：`mcp.types`（`BlobResourceContents`、`CallToolResult`、`EmbeddedResource`、`ImageContent`、`TextContent`、`TextResourceContents`）、`tenacity`（`AsyncRetrying`、`retry_if_exception_type`、`stop_after_attempt`、`wait_exponential`）
  - astrbot：`astrbot.logger`、`astrbot.core.agent.message`（`ImageURLPart`、`TextPart`、`ThinkPart`、`AssistantMessageSegment`、`Message`、`ToolCallMessageSegment`、`bind_checkpoint_messages`）、`astrbot.core.agent.tool`（`FunctionTool`、`ToolSet`）、`astrbot.core.agent.tool_image_cache.tool_image_cache`、`astrbot.core.exceptions.EmptyModelOutputError`、`astrbot.core.message.components.Json`、`astrbot.core.message.message_event_result.MessageChain`、`astrbot.core.persona_error_reply.extract_persona_custom_error_message_from_event`、`astrbot.core.provider.entities`（`LLMResponse`、`ProviderRequest`、`ToolCallsResult`）、`astrbot.core.provider.modalities`（`log_context_sanitize_stats`、`sanitize_contexts_by_modalities`）、`astrbot.core.provider.provider.Provider`
  - 相对包：`..context.compressor.ContextCompressor`、`..context.config.ContextConfig`、`..context.manager.ContextManager`、`..context.token_counter`（`EstimateTokenCounter`、`TokenCounter`）、`..hooks.BaseAgentRunHooks`、`..response`（`AgentResponseData`、`AgentStats`）、`..run_context`（`ContextWrapper`、`TContext`）、`..tool_executor.BaseFunctionToolExecutor`、`.base`（`AgentResponse`、`AgentState`、`BaseAgentRunner`）
  - 兼容：`typing.override`（3.12+）或 `typing_extensions.override`

---

## 4. `runners/coze/coze_agent_runner.py`

- **职责**：接入 Coze（扣子）开放平台 Bot 的 Agent Runner，通过 SSE 流式调用 Coze `/v3/chat`，支持图片上传与会话延续。
- **核心类**：

  ### `CozeAgentRunner(BaseAgentRunner[TContext])`
  - 基类：`BaseAgentRunner[TContext]`
  - 职责：将 Coze Bot 包装成 AstrBot Agent
  - 关键方法：
    - `async reset(request, run_context, agent_hooks, provider_config, **kwargs)`（override）：校验并读取配置 `coze_api_key`、`bot_id`、`coze_api_base`（默认 `https://api.coze.cn`，需 http/https 前缀）、`timeout`（默认 120）、`auto_save_history`（默认 True）；创建 `CozeAPIClient`；初始化 `file_id_cache`
    - `async step()`（override）：触发 `on_agent_begin` → 调 `_execute_coze_request` → 异常转 ERROR + err 响应；finally 关闭 `api_client`
    - `async step_until_done(max_step=30)`（override）：循环 step 直到 done
    - `async _execute_coze_request()`：核心执行。从 `sp` 读取 `coze_conversation_id`；按 `auto_save_history` 决定是否传 system prompt 与历史 contexts（处理历史中的图片上传）；构造当前消息（多模态走 `object_string` content_type）；调用 `api_client.chat_messages` 流式消费 SSE：`conversation.chat.created`（保存 conversation_id）、`conversation.message.delta`（累积 + 流式 yield）、`conversation.message.completed`、`conversation.chat.completed`（break）、`error`（抛异常）；最终构造 `LLMResponse(result_chain=...)` + `on_agent_done` + yield `llm_result`
    - `async _download_and_upload_image(image_url, session_id=None)`：用 MD5 哈希做 file_id 缓存，调 `MediaResolver.to_bytes()` 下载，再 `api_client.upload_file`
    - `done()`（override）：`_state in (DONE, ERROR)`
    - `get_final_llm_resp()`（override）：返回 `self.final_llm_resp`
  - 关键属性：`req`、`streaming`、`final_llm_resp`、`_state`、`agent_hooks`、`run_context`、`api_key`、`bot_id`、`api_base`、`timeout`、`auto_save_history`、`api_client: CozeAPIClient`、`file_id_cache`
- **核心函数（顶层）**：无
- **关键常量**：无（默认值内联）
- **依赖**：
  - 标准库：`json`、`sys`、`typing`
  - astrbot：`astrbot.core.message.components`（as `Comp`）、`astrbot.logger`、`astrbot.core.sp`、`astrbot.core.message.message_event_result.MessageChain`、`astrbot.core.provider.entities`（`LLMResponse`、`ProviderRequest`）、`astrbot.core.utils.media_utils`（`MediaResolver`、`describe_media_ref`）
  - 相对包：`...hooks.BaseAgentRunHooks`、`...message.is_checkpoint_message`、`...response.AgentResponseData`、`...run_context`（`ContextWrapper`、`TContext`）、`..base`（`AgentResponse`、`AgentState`、`BaseAgentRunner`）、`.coze_api_client.CozeAPIClient`
  - 兼容：`typing.override` 或 `typing_extensions.override`

---

## 5. `runners/coze/coze_api_client.py`

- **职责**：Coze 平台 HTTP/SSE 客户端封装，提供文件上传、图片下载、流式 chat、上下文清理、消息列表查询等 API。
- **核心类**：

  ### `CozeAPIClient`
  - 基类：无（普通类）
  - 职责：基于 `aiohttp` 的 Coze API 客户端，懒加载 session
  - 关键方法：
    - `__init__(api_key, api_base="https://api.coze.cn")`：保存配置，`session=None`
    - `async _ensure_session()`：懒创建 `aiohttp.ClientSession`，配置 `TCPConnector`（按 http/https 切换 ssl）、超时（total 120 / connect 30 / sock_read 120）、headers（`Authorization: Bearer`、`Accept: text/event-stream`）
    - `async upload_file(file_data: bytes) -> str`：POST `/v1/files/upload`，multipart 上传，返回 `data.id`；401 抛认证错误；非 0 code 抛业务错误
    - `async download_image(image_url) -> bytes`：GET 下载图片字节
    - `async chat_messages(bot_id, user_id, additional_messages=None, conversation_id=None, auto_save_history=True, stream=True, timeout=120) -> AsyncGenerator[dict, None]`：POST `/v3/chat` 流式调用，手写 SSE 解析（按行解析 `event:` / `data:`，遇到空行 yield 一个 `{event, data}`，跳过 `[DONE]`）；401 抛认证错误
    - `async clear_context(conversation_id)`：POST `/v3/conversation/message/clear_context`
    - `async get_message_list(conversation_id, order="desc", limit=10, offset=0)`：GET `/v3/conversation/message/list`
    - `async close()`：关闭 session
  - 关键属性：`api_key`、`api_base`、`session`
- **核心函数（顶层）**：无（文件末尾有 `if __name__ == "__main__"` 测试块 `test_coze_api_client`）
- **关键常量**：默认 api_base `"https://api.coze.cn"`；连接器参数（`limit=100`、`limit_per_host=30`、`keepalive_timeout=30`）等内联
- **依赖**：
  - 标准库：`asyncio`、`io`、`json`、`collections.abc.AsyncGenerator`、`typing.Any`
  - 第三方：`aiohttp`
  - astrbot：`astrbot.core.logger`

---

## 6. `runners/dashscope/dashscope_agent_runner.py`

- **职责**：接入阿里云百炼（DashScope）Application Agent 的 Runner，通过 `dashscope.Application.call` 调用，支持流式/非流式、RAG 引用、会话变量、多轮会话。
- **核心类**：

  ### `DashscopeAgentRunner(BaseAgentRunner[TContext])`
  - 基类：`BaseAgentRunner[TContext]`
  - 职责：将阿里云百炼智能体应用包装为 AstrBot Agent
  - 关键方法：
    - `async reset(request, run_context, agent_hooks, provider_config, **kwargs)`（override）：校验 `dashscope_api_key`、`dashscope_app_id`、`dashscope_app_type`；读取 `variables`、`rag_options`（拆出 `output_reference`）、`timeout`（默认 120）
    - `has_rag_options() -> bool`：判断 `rag_options` 是否有 `pipeline_ids` 或 `file_ids`
    - `async step()`（override）：触发 `on_agent_begin` → 调 `_execute_dashscope_request` → 异常转 ERROR + err 响应
    - `async step_until_done(max_step=30)`（override）：循环 step
    - `_consume_sync_generator(response, response_queue)`：在线程中消费 dashscope 同步 generator，把 chunk 放入 `queue.Queue`（流式逐个 put，非流式整体 put），异常 put `("error", e)`，结束 put `("done", None)`
    - `async _process_stream_chunk(chunk, output_text) -> tuple[str, list|None, AgentResponse|None]`：处理单个 `ApplicationResponse`。状态码非 200 转 ERROR；提取 `output.text` 并用正则把 `<ref>[N]</ref>` 改写为 `[N]`；流式时构造 `streaming_delta`；返回 doc_references
    - `_format_doc_references(doc_references) -> str`：格式化 RAG 引用为 "回答来源:" 文本
    - `async _build_request_payload(prompt, session_id, contexts, system_prompt) -> dict`：从 `sp` 读 `dashscope_conversation_id` 和 `session_variables`；对 `agent`/`dialog-workflow` 且无 RAG 的多轮类型构造带 `session_id` 的 payload，否则构造带 `rag_options` 的非多轮 payload；统一 `incremental_output=True`
    - `async _handle_streaming_response(response, session_id)`：用后台线程 + 队列桥接同步 generator 到异步流；逐 chunk 处理；保存 `session_id` 到 `sp`；按 `output_reference` 追加 RAG 引用；构造最终 `LLMResponse` + `on_agent_done` + yield `llm_result`
    - `async _execute_dashscope_request()`：图片输入告警忽略；构建 payload；非流式时 `incremental_output=False`；`functools.partial(Application.call, **payload)` 在 executor 中同步调用；交给 `_handle_streaming_response`
    - `done()`（override）：`_state in (DONE, ERROR)`
    - `get_final_llm_resp()`（override）：返回 `self.final_llm_resp`
  - 关键属性：`req`、`streaming`、`final_llm_resp`、`_state`、`agent_hooks`、`run_context`、`api_key`、`app_id`、`dashscope_app_type`、`variables`、`rag_options`、`output_reference`、`timeout`
- **核心函数（顶层）**：无
- **关键常量**：无（默认值内联，如 `timeout=120`、`max_step=30`）
- **依赖**：
  - 标准库：`asyncio`、`functools`、`queue`、`re`、`sys`、`threading`、`typing`
  - 第三方：`dashscope.Application`、`dashscope.app.application_response.ApplicationResponse`
  - astrbot：`astrbot.core.message.components`（as `Comp`）、`astrbot.core`（`logger`、`sp`）、`astrbot.core.message.message_event_result.MessageChain`、`astrbot.core.provider.entities`（`LLMResponse`、`ProviderRequest`）
  - 相对包：`...hooks.BaseAgentRunHooks`、`...response.AgentResponseData`、`...run_context`（`ContextWrapper`、`TContext`）、`..base`（`AgentResponse`、`AgentState`、`BaseAgentRunner`）
  - 兼容：`typing.override` 或 `typing_extensions.override`

---

## 7. `runners/deerflow/constants.py`

- **职责**：DeerFlow 集成相关常量定义。
- **关键常量**：
  - `DEERFLOW_PROVIDER_TYPE = "deerflow"`
  - `DEERFLOW_THREAD_ID_KEY = "deerflow_thread_id"`（sp 存储 key）
  - `DEERFLOW_SESSION_PREFIX = "deerflow-ephemeral"`（无 session_id 时的前缀）
  - `DEERFLOW_AGENT_RUNNER_PROVIDER_ID_KEY = "deerflow_agent_runner_provider_id"`
- **核心类 / 函数**：无
- **依赖**：无

---

## 8. `runners/deerflow/deerflow_agent_runner.py`

- **职责**：接入 DeerFlow（基于 LangGraph HTTP API）的 Agent Runner，通过 SSE 流式调用 `/api/langgraph/threads/{id}/runs/stream`，支持 thread 复用、values/messages-tuple/custom 三种 stream_mode 事件处理、澄清提问（clarification）、子任务失败汇总、流式增量、超时部分返回等。
- **核心类**：

  ### `DeerFlowAgentRunner(BaseAgentRunner[TContext])`
  - 基类：`BaseAgentRunner[TContext]`
  - 职责：DeerFlow LangGraph Agent 执行器
  - 内部 dataclass：
    - `_RunnerConfig`（frozen）：`api_base`、`api_key`、`auth_header`、`proxy`、`assistant_id`、`model_name`、`thinking_enabled`、`plan_mode`、`subagent_enabled`、`max_concurrent_subagents`、`timeout`、`recursion_limit`
    - `_StreamState`：流式状态容器。字段：`latest_text`、`prev_text_for_streaming`、`clarification_text`、`task_failures: list[str]`、`seen_message_ids: set[str]`、`seen_message_order: deque[str]`、`no_id_message_fingerprints: dict[int,str]`、`baseline_initialized`、`has_values_text`、`run_values_messages: list[dict]`、`timed_out`
    - `_FinalResult`（frozen）：`chain: MessageChain`、`role: str`
  - 类常量：`_MAX_VALUES_HISTORY = 200`
  - 关键方法：
    - `_format_exception(err) -> str`：异常格式化，特殊处理 TimeoutError
    - `async close()`：显式关闭 `api_client`（长生命周期 worker 用）
    - `async _notify_agent_done_hook()`：安全触发 `on_agent_done`
    - `async _finish_with_result(chain, role) -> AgentResponse`：正常完成收尾
    - `async _finish_with_error(err_msg) -> AgentResponse`：错误完成收尾
    - `_parse_runner_config(provider_config) -> _RunnerConfig`：解析配置，校验 `deerflow_api_base`（默认 `http://127.0.0.1:2026`，需 http/https 前缀）、`proxy`、`deerflow_assistant_id`（默认 `lead_agent`）、`deerflow_model_name`、`deerflow_thinking_enabled`、`deerflow_plan_mode`、`deerflow_subagent_enabled`、`deerflow_max_concurrent_subagents`（默认 3，min 1）、`timeout`（默认 300）、`deerflow_recursion_limit`（默认 1000）；用 `coerce_int_config` 强类型
    - `async _load_config_and_client(provider_config)`：把 config 落到 self 属性；按 `(api_base, api_key, auth_header, proxy)` 签名复用或重建 `DeerFlowAPIClient`
    - `async reset(...)`（override）：基础初始化 + 调 `_load_config_and_client`
    - `async step()`（override）：触发 `on_agent_begin` → 调 `_execute_deerflow_request` → `asyncio.CancelledError` 透传，其他异常走 `_finish_with_error`
    - `async step_until_done(max_step=30)`（override）：`max_step<=0` 抛错；循环 step；超限抛 `RuntimeError`
    - `_extract_new_messages_from_values(values_messages, state)`：基于 message id 或指纹去重提取新消息
    - `_fingerprint_message(message)`：SHA1 指纹
    - `_remember_seen_message_id(state, msg_id)`：维护 `_MAX_VALUES_HISTORY` 上限的 LRU seen 集合
    - `async _ensure_thread_id(session_id) -> str`：从 `sp` 读 `DEERFLOW_THREAD_ID_KEY`，无则 `api_client.create_thread` 并持久化
    - `_build_messages(prompt, image_urls, system_prompt)`：构造 messages（用 `build_user_content`）
    - `async _build_messages_resolved(...)`：用 `build_user_content_resolved` 物化图片引用
    - `_build_runtime_configurable(thread_id)`：构造 `configurable`（thread_id、thinking_enabled、is_plan_mode、subagent_enabled、max_concurrent_subagents、model_name）
    - `_build_payload(...)` / `async _build_payload_resolved(...)`：构造 stream 请求 payload（`assistant_id`、`input.messages`、`stream_mode=["values","messages-tuple","custom"]`、`context`、`config.recursion_limit` + `config.configurable`）
    - `_update_text_and_maybe_stream(*, state, new_full_text=None, delta_text=None) -> list[AgentResponse]`：增量/全量两种模式下的流式 delta 推送
    - `_handle_values_event(data, state) -> list[AgentResponse]`：处理 values 事件，baseline 初始化 + 去重提取新消息 + 抽取最新 AI 文本与 clarification
    - `_handle_message_event(data, state) -> AgentResponse | None`：处理 messages-tuple 事件，提取 AI delta 与 clarification
    - `_build_final_result(state) -> _FinalResult`：组装最终 chain（优先 clarification → AI message content → latest_text → task failure 汇总 → 空响应兜底）；超时追加 note；role 按 `timed_out`/`failures_only` 决定
    - `_emit_non_plain_components_at_end(final_chain) -> AgentResponse | None`：流式模式下末尾补发非 Plain 组件（如 Image）
    - `async _execute_deerflow_request()`：核心执行。`_ensure_thread_id` → `_build_payload_resolved` → `_StreamState` → `api_client.stream_run` 消费事件：`values` / `messages-tuple|messages|message` / `custom`（收集 task_failures）/ `error`（抛）/ `end`（break）；`TimeoutError` 标记 `timed_out` 并部分返回；最终 `_build_final_result` + 流式补发 + `_finish_with_result`
    - `done()`（override）：`_state in (DONE, ERROR)`
    - `get_final_llm_resp()`（override）：返回 `self.final_llm_resp`
  - 关键属性：`req`、`streaming`、`final_llm_resp`、`_state`、`agent_hooks`、`run_context`、`api_base`、`api_key`、`auth_header`、`proxy`、`assistant_id`、`model_name`、`thinking_enabled`、`plan_mode`、`subagent_enabled`、`max_concurrent_subagents`、`timeout`、`recursion_limit`、`api_client: DeerFlowAPIClient`、`_api_client_signature`
- **核心函数（顶层）**：无
- **关键常量**：`_MAX_VALUES_HISTORY = 200`
- **依赖**：
  - 标准库：`asyncio`、`hashlib`、`json`、`sys`、`typing`、`collections.deque`、`dataclasses`、`uuid.uuid4`
  - astrbot：`astrbot.core.message.components`（as `Comp`）、`astrbot.logger`、`astrbot.core.sp`、`astrbot.core.message.message_event_result.MessageChain`、`astrbot.core.provider.entities`（`LLMResponse`、`ProviderRequest`）、`astrbot.core.utils.config_number.coerce_int_config`
  - 相对包：`...hooks.BaseAgentRunHooks`、`...response.AgentResponseData`、`...run_context`（`ContextWrapper`、`TContext`）、`..base`（`AgentResponse`、`AgentState`、`BaseAgentRunner`）、`.constants`（`DEERFLOW_SESSION_PREFIX`、`DEERFLOW_THREAD_ID_KEY`）、`.deerflow_api_client.DeerFlowAPIClient`、`.deerflow_content_mapper`（`build_chain_from_ai_content`、`build_user_content`、`build_user_content_resolved`、`image_component_from_url`）、`.deerflow_stream_utils`（多个提取函数）
  - 兼容：`typing.override` 或 `typing_extensions.override`

---

## 9. `runners/deerflow/deerflow_api_client.py`

- **职责**：DeerFlow LangGraph HTTP API 客户端，提供 thread 创建/删除与流式 run，内置健壮的 SSE 解析（容错解码、缓冲上限保护、多 JSON 片段合并）。
- **核心类**：

  ### `DeerFlowAPIError(Exception)`
  - 职责：DeerFlow API 错误，携带 `operation`、`status`、`body`、`url`、`thread_id` 上下文

  ### `DeerFlowAPIClient`
  - 基类：无（普通类，支持 `async with`）
  - 职责：DeerFlow LangGraph HTTP 客户端，显式生命周期管理
  - 关键方法：
    - `__init__(api_base="http://127.0.0.1:2026", api_key="", auth_header="", proxy=None)`：规整化 api_base（去尾斜杠）、proxy；按 `auth_header`（优先）或 `api_key` 设置 `Authorization` header
    - `_get_session() -> ClientSession`：懒创建 `aiohttp.ClientSession(trust_env=True)`；已关闭抛 `RuntimeError`
    - `async __aenter__()` / `async __aexit__(...)`：上下文管理
    - `async create_thread(timeout=20) -> dict`：POST `/api/langgraph/threads`，`{"metadata": {}}`，非 200/201 抛 `DeerFlowAPIError`
    - `async delete_thread(thread_id, timeout=20)`：DELETE `/api/threads/{thread_id}`，200/202/204/404 视为成功
    - `async stream_run(thread_id, payload, timeout=120) -> AsyncGenerator[dict, None]`：POST `/api/langgraph/threads/{thread_id}/runs/stream`，headers 含 `Accept: text/event-stream`；用 `ClientTimeout(total=None, connect=min(timeout,30), sock_connect=min(timeout,30), sock_read=timeout)` 避免长流被 total timeout 杀；非 200 抛 `DeerFlowAPIError`；通过 `_stream_sse` 解析 SSE
    - `async close()`：best-effort 关闭 session
    - `__del__()`：仅诊断警告（未关闭时打 warning，不保证清理）
    - `@property is_closed -> bool`
  - 关键属性：`api_base`、`_session`、`_closed`、`proxy`、`headers`
- **核心函数（顶层）**：
  - `_normalize_sse_newlines(text) -> str`：CRLF/CR → LF
  - `_parse_sse_data_lines(data_lines) -> Any`：合并多行 data；JSON 解析失败时尝试逐行解析（兼容 LangGraph 多片段 tuple payload），最终回退原始字符串
  - `_parse_sse_block(block) -> dict | None`：解析单个 SSE 块为 `{event, data}`，默认 event 名 `"message"`
  - `async _stream_sse(resp) -> AsyncGenerator[dict, None]`：用 `codecs.getincrementaldecoder("utf-8")("replace")` 容错解码；按 `\n\n` 切块；缓冲超过 `SSE_MAX_BUFFER_CHARS` 强制刷新防内存膨胀；结尾 flush 残余
- **关键常量**：`SSE_MAX_BUFFER_CHARS = 1_048_576`
- **依赖**：
  - 标准库：`codecs`、`json`、`collections.abc.AsyncGenerator`、`typing.Any`
  - 第三方：`aiohttp`（`ClientResponse`、`ClientSession`、`ClientTimeout`）
  - astrbot：`astrbot.core.logger`

---

## 10. `runners/deerflow/deerflow_content_mapper.py`

- **职责**：DeerFlow 消息内容与 AstrBot 消息组件（`Comp`）之间的双向映射：构造用户多模态内容、解析 AI 内容为 `MessageChain`、图片引用解析与组件转换。
- **核心函数（顶层）**：
  - `is_likely_base64_image(value: str) -> bool`：启发式判断字符串是否为合法 base64 图片（无空格、长度≥32、长度 4 的倍数、字符集合法、可 `b64decode(validate=True)`）
  - `build_user_content(prompt: str, image_urls: list[str]) -> Any`：构造 DeerFlow 用户内容。无图返回纯文本；有图返回多模态 list，支持 http/https/data: URI 与裸 base64（转 `data:image/png;base64,...`）；统计跳过的无效图片并插入提示文本
  - `async build_user_content_resolved(prompt, image_urls) -> Any`：与 `build_user_content` 类似，但用 `resolve_media_ref_to_base64_data` 物化所有图片引用（本地路径、HTTP(S)、file URI、base64://、data URI、裸 base64），转 data URL
  - `image_component_from_url(url) -> Comp.Image | None`：把 URL 或 data:base64 转为 `Comp.Image`（`fromURL` / `fromBase64`）
  - `append_components_from_content(content, components, image_resolver)`：递归把 AI content（str / list / dict，含 `type=text`/`image_url`/嵌套 `content`/`kwargs.content`）追加为 `Comp.Plain` / `Comp.Image`
  - `build_chain_from_ai_content(content, image_resolver) -> MessageChain`：用 `append_components_from_content` 组装，空时回退 `extract_text` 兜底
- **核心类**：无
- **关键常量**：无
- **依赖**：
  - 标准库：`base64`、`collections.abc.Callable`、`typing.Any`
  - astrbot：`astrbot.core.message.components`（as `Comp`）、`astrbot.logger`、`astrbot.core.message.message_event_result.MessageChain`、`astrbot.core.utils.media_utils`（`describe_media_ref`、`resolve_media_ref_to_base64_data`）
  - 相对包：`.deerflow_stream_utils.extract_text`

---

## 11. `runners/deerflow/deerflow_stream_utils.py`

- **职责**：DeerFlow 流式事件的纯函数工具集，从 LangGraph 多变的事件 payload 中提取消息、AI 文本、澄清提问、任务失败等结构化信息。
- **核心函数（顶层）**：
  - `extract_text(content) -> str`：从 str/dict/list（含 `text`、`content`、`kwargs.content`、`type=text`）递归提取纯文本
  - `extract_messages_from_values_data(data) -> list`：从 values 事件的多种 payload 形态（dict/`data.values`/list）中提取 `messages` 列表
  - `is_ai_message(message) -> bool`：判断是否为 AI/assistant 消息（role 或 type 含 `assistant`/`ai`/`aimessage`/`aimessagechunk`，且不含 human/tool/system）
  - `extract_latest_ai_text(messages) -> str`：反向扫描取最新 AI 消息文本
  - `extract_latest_ai_message(messages) -> dict | None`：反向扫描取最新 AI 消息对象
  - `is_clarification_tool_message(message) -> bool`：是否为 `ask_clarification` 工具消息
  - `extract_latest_clarification_text(messages) -> str`：取最新澄清文本
  - `get_message_id(message) -> str`：取消息 id（字符串）
  - `extract_event_message_obj(data) -> dict | None`：从 messages-tuple 事件（可能为 `[msg, metadata]` 或 `{"data": {...}}`）提取消息对象
  - `extract_ai_delta_from_event_data(data) -> str`：从事件 data 提取 AI delta 文本
  - `extract_clarification_from_event_data(data) -> str`：从事件 data 提取澄清文本
  - `_iter_custom_event_items(data) -> list[dict]`：把 custom 事件 data 规整为 dict 列表（支持嵌套 list/tuple）
  - `extract_task_failures_from_custom_event(data) -> list[str]`：从 custom 事件提取 `task_failed`/`task_timed_out` 失败项（task_id + error 文本）
  - `build_task_failure_summary(failures) -> str`：去重后汇总失败项为单条/多条文案
- **核心类**：无
- **关键常量**：无
- **依赖**：
  - 标准库：`typing`、`collections.abc.Iterable`
  - 第三方/astrbot：无（纯函数模块）

---

## 12. `runners/dify/dify_agent_runner.py`

- **职责**：接入 Dify 平台的 Agent Runner，支持 `chat`/`agent`/`chatflow`/`workflow` 四种 API 类型，处理图片上传、会话变量、流式与非流式、workflow 多模态输出解析。
- **核心类**：

  ### `DifyAgentRunner(BaseAgentRunner[TContext])`
  - 基类：`BaseAgentRunner[TContext]`
  - 职责：将 Dify 应用包装为 AstrBot Agent
  - 关键方法：
    - `async reset(...)`（override）：读取 `dify_api_key`、`dify_api_base`（默认 `https://api.dify.ai/v1`）、`dify_api_type`（默认 `chat`）、`dify_workflow_output_key`（默认 `astrbot_wf_output`）、`dify_query_input_key`（默认 `astrbot_text_query`）、`variables`、`timeout`（默认 60）；创建 `DifyAPIClient`
    - `async step()`（override）：触发 `on_agent_begin` → 调 `_execute_dify_request` → 异常转 ERROR + err 响应；finally 关闭 `api_client`
    - `async step_until_done(max_step=30)`（override）：循环 step
    - `async _upload_image_for_dify(image_url, session_id) -> dict | None`：用 `MediaResolver.to_base64_data(strict=True)` 预处理图片，调 `api_client.file_upload`，返回 Dify files payload 项（`type=image`、`transfer_method=local_file`、`upload_file_id`）
    - `async _execute_dify_request()`：核心执行。读 `dify_conversation_id`；上传图片得 `files_payload`；合并 `variables` + `session_variables` + `system_prompt`；按 `api_type` 分支：
      - `chat`/`agent`/`chatflow`：调 `chat_messages`，消费 SSE：`message`/`agent_message`（累积 answer、保存 conversation_id、流式 yield `streaming_delta`）、`message_end`（break）、`error`（抛）
      - `workflow`：调 `workflow_run`，按事件 `workflow_started`/`node_finished`/`text_chunk`（流式 yield）/`workflow_finished`（校验 error 与 `workflow_output_key`）处理
      - 未知类型抛错
    - `async parse_dify_result(chunk) -> MessageChain`：解析最终结果。字符串 → `Plain`；dict → 从 `data.outputs[workflow_output_key]` 取输出（str/list/其他），list 适配 Dify HTTP 节点 `Array[File]`（`dify_model_identity == "__dify__file__"`）；扫描 `data.files` 解析为 `Image`/`Record`（音频转 wav）/`Video`/`File`
    - `done()`（override）：`_state in (DONE, ERROR)`
    - `get_final_llm_resp()`（override）：返回 `self.final_llm_resp`
  - 关键属性：`req`、`streaming`、`final_llm_resp`、`_state`、`agent_hooks`、`run_context`、`api_key`、`api_base`、`api_type`、`workflow_output_key`、`dify_query_input_key`、`variables`、`timeout`、`api_client: DifyAPIClient`
- **核心函数（顶层）**：无
- **关键常量**：无（默认值内联，如 `dify_api_base="https://api.dify.ai/v1"`、`dify_api_type="chat"`、`dify_workflow_output_key="astrbot_wf_output"`、`dify_query_input_key="astrbot_text_query"`、`timeout=60`、`max_step=30`）
- **依赖**：
  - 标准库：`sys`、`typing`
  - astrbot：`astrbot.core.message.components`（as `Comp`）、`astrbot.core`（`logger`、`sp`）、`astrbot.core.message.message_event_result.MessageChain`、`astrbot.core.provider.entities`（`LLMResponse`、`ProviderRequest`）、`astrbot.core.utils.media_utils.MediaResolver`
  - 相对包：`...hooks.BaseAgentRunHooks`、`...response.AgentResponseData`、`...run_context`（`ContextWrapper`、`TContext`）、`..base`（`AgentResponse`、`AgentState`、`BaseAgentRunner`）、`.dify_api_client.DifyAPIClient`
  - 兼容：`typing.override` 或 `typing_extensions.override`

---

## 13. `runners/dify/dify_api_client.py`

- **职责**：Dify 平台 HTTP/SSE 客户端封装，提供 chat-messages、workflow run、文件上传、会话列表/删除/重命名等 API。
- **核心类**：

  ### `DifyAPIClient`
  - 基类：无（普通类）
  - 职责：基于 `aiohttp` 的 Dify API 客户端
  - 关键方法：
    - `__init__(api_key, api_base="https://api.dify.ai/v1")`：创建 `ClientSession(trust_env=True)`，headers 含 `Authorization: Bearer`
    - `async chat_messages(inputs, query, user, response_mode="streaming", conversation_id="", files=None, timeout=60) -> AsyncGenerator[dict, None]`：POST `/chat-messages`，非 200 抛错，通过 `_stream_sse` yield 事件
    - `async workflow_run(inputs, user, response_mode="streaming", files=None, timeout=60)`：POST `/workflows/run`，同上
    - `async file_upload(user, file_path=None, file_data=None, file_name=None, mime_type=None) -> dict`：POST `/files/upload`，用 `FormData` 上传（支持 bytes 或文件路径），返回 `{"id": ...}`；状态非 200/201 抛错
    - `async close()`：关闭 session
    - `async get_chat_convs(user, limit=20)`：GET `/conversations`
    - `async delete_chat_conv(user, conversation_id)`：DELETE `/conversations/{conversation_id}`
    - `async rename(conversation_id, name, user, auto_generate=False)`：POST `/conversations/{conversation_id}/name`
  - 关键属性：`api_key`、`api_base`、`session`、`headers`
- **核心函数（顶层）**：
  - `async _stream_sse(resp) -> AsyncGenerator[dict, None]`：Dify SSE 解析。用 `codecs.getincrementaldecoder("utf-8")()` 解码；按 `\n\n` 切块；只处理以 `data:` 开头的块，`json.loads` 解析，失败打 warning 丢弃；结尾 flush 残余
- **关键常量**：默认 `api_base="https://api.dify.ai/v1"`
- **依赖**：
  - 标准库：`codecs`、`json`、`collections.abc.AsyncGenerator`、`typing.Any`、`os`（file_upload 内联）
  - 第三方：`aiohttp`（`ClientResponse`、`ClientSession`、`FormData`）
  - astrbot：`astrbot.core.logger`

---

## 总体架构小结

1. **抽象层（`base.py`）**：`BaseAgentRunner` + `AgentState` 状态机，定义 `reset/step/step_until_done/done/get_final_llm_resp` 五大抽象接口与 `_transition_state` 工具方法。

2. **默认实现（`tool_loop_agent_runner.py`）**：`ToolLoopAgentRunner` 是功能最完整的内置 Runner，承担 LLM 调用 + 工具循环 + 上下文压缩 + 多 Provider fallback + 流式 + 中断 + 跟进消息 + 重复工具检测 + 工具结果溢出落盘 + skills_like 二阶段工具 schema 等复杂职责，是 AstrBot Agent 能力的核心。

3. **第三方平台 Runner（coze/dashscope/deerflow/dify）**：均为远程 HTTP/SSE Agent 服务的适配器，统一遵循 BaseAgentRunner 接口。它们的 `step_until_done` 通常只是简单循环 `step`（因为远程平台自身已封装工具循环），核心逻辑集中在 `_execute_*_request` 与对应的 `*_api_client` 中。会话延续均通过 `astrbot.core.sp`（持久化存储）保存各自的 `*_conversation_id` / `*_thread_id`。

4. **API Client 分层**：coze/dify/deerflow 各有独立 `*_api_client.py`，封装平台 HTTP 与 SSE 解析。其中 `deerflow_api_client` 的 SSE 解析最健壮（容错解码、缓冲上限、多 JSON 片段合并），`coze_api_client` 与 `dify_api_client` 则是手写按行解析。

5. **DeerFlow 子模块拆分最细**：`deerflow` 目录下除 runner 与 api_client 外，还有 `constants.py`（常量）、`deerflow_content_mapper.py`（消息↔组件映射）、`deerflow_stream_utils.py`（流式事件纯函数工具），体现了 DeerFlow 事件结构复杂、需要专门解析层的设计。

6. **统一依赖模式**：所有 Runner 通过相对导入 `..base`、`...hooks`、`...response`、`...run_context` 复用 Agent 框架抽象；通过 `astrbot.core.sp` 做会话持久化；通过 `astrbot.core.provider.entities`（`LLMResponse`、`ProviderRequest`）与 `astrbot.core.message.message_event_result.MessageChain` 与上层消息体系对接；Python 3.12+ 用 `typing.override`，低版本回退 `typing_extensions.override`。


---

## 章节八：core/tools + core/computer + core/backup + core/skills + core/cron

# AstrBot 核心模块逐文件详解

分析范围：`astrbot/core/` 下 5 个子目录共 42 个 `.py` 文件。

- 1. `tools/`（14 文件，含 `computer_tools/` 与 `computer_tools/shipyard_neo/`）
- 2. `computer/`（18 文件，含 `booters/` 与 `olayer/`）
- 3. `backup/`（4 文件）
- 4. `skills/`（3 文件）
- 5. `cron/`（3 文件）

> 注：`tools/` 与 `tools/computer_tools/` 顶层均无 `__init__.py`，模块入口由 `registry.py` 提供。

---

## 1. `tools/` 目录

### 1.1 `tools/registry.py`

- **职责**：内置工具（builtin tool）的注册中心与配置规则评估器，统一管理所有 `@builtin_tool` 装饰的工具类，并基于配置条件决定工具是否在某个会话配置下启用。
- **核心类**：
  - `BuiltinToolConfigCondition`（基类 `dataclass(frozen=True)`）：单个配置条件，支持 `equals`/`in`/`truthy`/`custom` 操作符；关键方法 `evaluate(config)` 返回条件匹配结果字典。
  - `BuiltinToolConfigRule`（基类 `dataclass(frozen=True)`）：规则集合，可包含多个 condition 或自定义 evaluator；关键方法 `evaluate(config)` 返回条件结果列表。
- **核心函数**：
  - `builtin_tool(tool_cls=None, *, config=None)`：装饰器，将 `FunctionTool` 子类注册到全局表，可选附带配置规则。
  - `ensure_builtin_tools_loaded()`：惰性导入 `_BUILTIN_TOOL_MODULES` 中列出的 5 个工具模块。
  - `get_builtin_tool_class(name)` / `get_builtin_tool_name(tool_cls)` / `iter_builtin_tool_classes()`：按名称或类查询已注册工具。
  - `get_builtin_tool_config_rule(name)`：取工具对应的配置规则。
  - `get_builtin_tool_config_statuses(tool_name, config_entries)` / `get_builtin_tool_config_tags(...)`：对多份配置评估工具启用状态。
  - `_evaluate_send_message_tool(config)`：专门评估 `send_message_to_user` 工具在平台配置下是否支持主动消息。
  - `_build_rule_from_config_map(config_map)`：把简单的 `key->expected` 映射转成 `BuiltinToolConfigRule`。
- **关键常量**：
  - `_BUILTIN_TOOL_MODULES`：5 个内置工具模块路径元组（computer_tools、cron_tools、knowledge_base_tools、message_tools、web_search_tools）。
  - `_BUILTIN_TOOL_CONFIG_RULES`：工具名→规则的全局字典。
  - `_builtin_tool_classes_by_name` / `_builtin_tool_names_by_class`：双向映射表。
- **依赖**：`astrbot.core.agent.tool.FunctionTool`，标准库 `importlib`/`dataclasses`/`typing`。

---

### 1.2 `tools/message_tools.py`

- **职责**：定义 `send_message_to_user` 工具，让 Agent 可向当前会话或其它会话发送文本、图片、语音、视频、文件、@用户 等多类型消息组件。
- **核心类**：
  - `SendMessageToUserTool(FunctionTool[AstrAgentContext])`：name=`send_message_to_user`；关键方法 `call(context, **kwargs)` 组装消息组件并调用 `context.send_message`；`_resolve_path_from_sandbox(...)` 将沙箱路径或本地路径解析为可发送的本地文件路径（含权限校验）。
- **核心函数**（模块级私有）：
  - `_file_send_allowed_roots(umo, current_workspace_root)`：计算允许发送文件的根目录元组。
  - `_is_path_within(path, roots)`：判断路径是否落在允许根目录内。
  - `_is_restricted_local_env(context)`：判断本地运行时是否处于受限（非 admin 且 require_admin）环境。
  - `_can_send_local_file(context, local_path, current_workspace_root)`：综合判断本地文件是否可发送。
- **关键常量**：无模块级常量；参数 schema 内嵌于 dataclass。
- **依赖**：`astrbot.core.message.components`、`astrbot.core.computer.computer_client.get_booter`、`computer_tools.fs._remote_basename`、`computer_tools.util`（check_admin_permission/is_local_runtime/workspace_root*）、`astrbot.core.platform.message_session.MessageSession`、`pydantic`。

---

### 1.3 `tools/web_search_tools.py`

- **职责**：实现多家搜索引擎（Tavily / BoCha / Brave / Firecrawl / Baidu AI Search / Exa）的网页搜索与网页内容提取工具，带 API key 轮转与失败转移。
- **核心类**：
  - `_KeyRotator`（`std_dataclass`）：并发安全的 round-robin API key 轮转器；关键方法 `async get(provider_settings)`。
  - `SearchResult`（`std_dataclass`）：标准化搜索结果（title/url/snippet/favicon）。
  - `TavilyWebSearchTool(FunctionTool)`：name=`web_search_tavily`，调用 Tavily Search API。
  - `TavilyExtractWebPageTool(FunctionTool)`：name=`tavily_extract_web_page`，提取网页内容。
  - `BochaWebSearchTool(FunctionTool)`：name=`web_search_bocha`。
  - `BraveWebSearchTool(FunctionTool)`：name=`web_search_brave`。
  - `FirecrawlWebSearchTool(FunctionTool)`：name=`web_search_firecrawl`。
  - `FirecrawlExtractWebPageTool(FunctionTool)`：name=`firecrawl_extract_web_page`，抓取网页。
  - `BaiduWebSearchTool(FunctionTool)`：name=`web_search_baidu`，基于百度 AI 搜索。
  - `ExaWebSearchTool(FunctionTool)`：name=`web_search_exa`，Exa 语义/关键词搜索。
  - `ExaGetContentsTool(FunctionTool)`：name=`exa_get_contents`，Exa 内容提取。
- **核心函数**：
  - `normalize_legacy_web_search_config(cfg)`：把旧版单 key 配置迁移为列表形式，并禁用不再支持的 default provider。
  - `_get_runtime(context)`：从 context 取出 cfg/provider_settings/umo。
  - `_cache_favicon(url, favicon)`：缓存站点图标到 `sp.temporary_cache`。
  - `_search_result_payload(results)`：把 SearchResult 列表序列化为带索引的 JSON。
  - `_tavily_search` / `_tavily_extract` / `_bocha_search` / `_brave_search` / `_firecrawl_search` / `_firecrawl_scrape` / `_baidu_search` / `_exa_search` / `_exa_get_contents`：各家 API 的异步调用实现，均带 key 轮转与可重试 HTTP 状态码（401/403/429/432）失败转移。
- **关键常量**：
  - `WEB_SEARCH_TOOL_NAMES`：9 个工具名列表。
  - `_RETRYABLE_HTTP_STATUSES`：`frozenset({401, 403, 429, 432})`。
  - 6 个 provider 配置字典（`_TAVILY_WEB_SEARCH_TOOL_CONFIG` 等）。
  - 5 个 `_KeyRotator` 单例。
- **依赖**：`aiohttp`、`pydantic`、`astrbot.core`（logger/sp）、`astrbot.core.agent.tool`、`astrbot.core.tools.registry.builtin_tool`。

---

### 1.4 `tools/cron_tools.py`

- **职责**：定义 `future_task` 工具，让 Agent 可创建/编辑/删除/列出未来定时任务（cron 或一次性 run_at）。
- **核心类**：
  - `FutureTaskTool(FunctionTool[AstrAgentContext])`：name=`future_task`，action ∈ {create, edit, delete, list}；关键方法 `call(context, **kwargs)` 通过 `context.context.context.cron_manager` 操作任务，并对 edit/delete/list 做发送者归属校验。
- **核心函数**（模块级私有）：
  - `_extract_job_session(job)` / `_extract_job_sender(job)`：从 job.payload 取 session/sender_id。
  - `_job_belongs_to_current_sender(job, current_umo, current_sender_id)`：判断任务是否属于当前发送者。
  - `_parse_run_at(run_at)`：ISO 字符串转 datetime。
- **关键常量**：`_CRON_TOOL_CONFIG = {"provider_settings.proactive_capability.add_cron_tools": True}`。
- **依赖**：`astrbot.core.cron.manager.CronJobSchedulingError`、`astrbot.core.tools.registry.builtin_tool`、`pydantic`。

---

### 1.5 `tools/knowledge_base_tools.py`

- **职责**：定义知识库查询工具 `astr_kb_search`，并提供会话级/全局级知识库检索的复用函数。
- **核心类**：
  - `KnowledgeBaseQueryTool(FunctionTool[AstrAgentContext])`：name=`astr_kb_search`；`call(context, **kwargs)` 调用 `retrieve_knowledge_base` 返回检索到的上下文文本。
- **核心函数**：
  - `check_all_kb(kb_list)`：检查所有知识库是否为空。
  - `retrieve_knowledge_base(query, umo, context)`：综合会话级 kb_config（`sp.session_get`）与全局配置，调用 `kb_mgr.retrieve` 注入知识上下文。
- **关键常量**：`_KNOWLEDGE_BASE_TOOL_CONFIG = {"kb_agentic_mode": True}`。
- **依赖**：`astrbot.api`（logger/sp）、`astrbot.core.knowledge_base.kb_helper.KBHelper`、`astrbot.core.star.context.Context`、`astrbot.core.tools.registry.builtin_tool`。

---

### 1.6 `tools/computer_tools/__init__.py`

- **职责**：聚合 `computer_tools` 子包所有工具类与工具函数，对外统一导出。
- **核心类**：无定义，仅 re-export。
- **核心函数**：re-export `normalize_umo_for_workspace`、`check_admin_permission`。
- **关键常量**：`__all__` 列出 25 个导出符号（工具类 + 两个工具函数）。
- **依赖**：相对导入 `.cua`/`.fs`/`.python`/`.shell`/`.shipyard_neo`/`.util`。

---

### 1.7 `tools/computer_tools/util.py`

- **职责**：computer_tools 子包共享的工具函数：工作区根路径解析、运行时类型判断、admin 权限校验。
- **核心类**：无。
- **核心函数**：
  - `workspace_root(umo)`：返回旧的按会话工作区根目录。
  - `workspace_root_for_context(context)`：基于 db 解析（失败回退到旧路径）工作区根。
  - `is_local_runtime(context)`：判断 `computer_use_runtime` 是否为 `local`。
  - `check_admin_permission(context, operation_name)`：若 `computer_use_require_admin=True` 且非 admin，返回错误字符串；否则返回 None。
- **关键常量**：无。
- **依赖**：`astrbot.core.db.BaseDatabase`、`astrbot.core.utils.astrbot_path`、`astrbot.core.workspace`（normalize_umo_for_workspace/resolve_workspace_root_for_umo）。

---

### 1.8 `tools/computer_tools/fs.py`

- **职责**：文件系统类工具实现（读/写/编辑/grep/上传/下载），含本地与沙箱运行时的路径解析、权限边界与硬链接防护。
- **核心类**：
  - `FileReadTool(FunctionTool)`：name=`astrbot_file_read_tool`，支持文本/图片/PDF/docx/epub；关键方法 `call(...)`、`_validate_read_window(...)`。
  - `FileWriteTool(FunctionTool)`：name=`astrbot_file_write_tool`，写 UTF-8 文本。
  - `FileEditTool(FunctionTool)`：name=`astrbot_file_edit_tool`，字符串替换编辑。
  - `GrepTool(FunctionTool)`：name=`astrbot_grep_tool`，基于 ripgrep 搜索；关键方法 `_resolve_context_options`、`_split_output_groups`、`_apply_result_limit`、`_normalize_search_paths`。
  - `FileUploadTool(FunctionTool)`：name=`astrbot_upload_file`，仅沙箱运行时，主机→沙箱。
  - `FileDownloadTool(FunctionTool)`：name=`astrbot_download_file`，仅沙箱运行时，沙箱→主机并可选发送给用户。
- **核心函数**（模块级私有，较多）：
  - `_remote_basename(path)`：规范化分隔符后取 basename。
  - `_restricted_env_path_labels(umo, *, include_plugin_skills, current_workspace_root)`：返回受限环境下允许目录的可读标签列表。
  - `get_astrbot_workspaces_path()`：兼容性封装。
  - `_workspace_root(umo)` / `_plugin_skill_roots()` / `_read_allowed_roots(umo, ...)` / `_write_allowed_roots(umo, ...)`：计算允许读/写的根目录元组。
  - `_is_restricted_env(context)`：判断本地+非 admin 受限环境。
  - `_resolve_tool_path(...)` / `_resolve_user_path(...)`：路径解析（相对路径在工作区根下解析）。
  - `_is_path_within_allowed_roots(...)`：路径边界校验。
  - `_reject_multi_link_file(path)`：拒绝多硬链接文件（防止别名越权）。
  - `_normalize_rw_path(...)`：综合路径规范化 + 受限校验 + 多链接拒绝。
  - `_decode_escaped_text(value)`：解码工具参数中的转义控制序列。
- **关键常量**：
  - `_COMPUTER_RUNTIME_TOOL_CONFIG = {"provider_settings.computer_use_runtime": ("local", "sandbox")}`。
  - `_SANDBOX_RUNTIME_TOOL_CONFIG = {"provider_settings.computer_use_runtime": "sandbox"}`。
  - `_IMAGE_FILE_SUFFIXES`：图片后缀集合。
  - 文件顶部 docstring 详述各运行时/角色下的路径访问策略。
- **依赖**：`astrbot.api`（FunctionTool/logger）、`astrbot.core.computer.computer_client.get_booter`、`astrbot.core.computer.file_read_utils.read_file_tool_result`、`astrbot.core.message.components`（File/Image）、`astrbot.core.utils.astrbot_path`、`.util`、`..registry.builtin_tool`。

---

### 1.9 `tools/computer_tools/shell.py`

- **职责**：定义 shell 执行工具 `astrbot_execute_shell`，支持前台/后台运行、超时、环境变量，并自动重定向后台命令输出到日志文件。
- **核心类**：
  - `ExecuteShellTool(FunctionTool)`：name=`astrbot_execute_shell`；关键方法 `call(...)` 调用 `sb.shell.exec`，本地运行时设置 cwd 为工作区根，后台模式重定向 stdout 到文件。
- **核心函数**（模块级私有）：
  - `_quote_redirect_path(path, *, local_runtime)`：跨平台安全引用重定向路径（Windows 用双引号转义）。
  - `_build_background_output_path(*, local_runtime)`：生成后台输出日志文件路径。
  - `_redirect_background_stdout_command(command, *, output_path, local_runtime)`：包装命令以重定向 stdout/stderr。
  - `_is_self_detached_command(command)`：检测命令是否已自带后台化（nohup/setsid/`&` 等），避免重复包装。
- **关键常量**：`_COMPUTER_RUNTIME_TOOL_CONFIG`（同 fs.py）。
- **依赖**：`astrbot.api.FunctionTool`、`astrbot.core.computer.computer_client.get_booter`、`astrbot.core.utils.astrbot_path.get_astrbot_system_tmp_path`、`.util`、`..registry.builtin_tool`。

---

### 1.10 `tools/computer_tools/python.py`

- **职责**：定义 Python 执行工具：沙箱运行时用 IPython（`astrbot_execute_ipython`），本地运行时用子进程 Python（`astrbot_execute_python`）。
- **核心类**：
  - `PythonTool(FunctionTool)`：name=`astrbot_execute_ipython`，沙箱 IPython 执行；`call(...)` 调用 `sb.python.exec`。
  - `LocalPythonTool(FunctionTool)`：name=`astrbot_execute_python`，本地子进程执行；`call(...)` 调用 `get_local_booter().python.exec` 并设置 cwd 为工作区根。
- **核心函数**：
  - `handle_result(result, event)`：把执行结果（output/error/images/text）转成 `mcp.types.CallToolResult`，webchat 平台额外发送 base64 图片。
- **关键常量**：
  - `_OS_NAME`：`platform.system()`。
  - `_SANDBOX_PYTHON_TOOL_CONFIG` / `_LOCAL_PYTHON_TOOL_CONFIG`。
  - `param_schema`：code/silent/timeout 参数 schema。
- **依赖**：`mcp`、`astrbot.api.FunctionTool`、`astrbot.core.computer.computer_client`（get_booter/get_local_booter）、`astrbot.core.message.message_event_result.MessageChain`、`.util`、`..registry.builtin_tool`。

---

### 1.11 `tools/computer_tools/cua.py`

- **职责**：定义 CUA（Computer Use Agent）沙箱的 GUI 自动化工具：截图、鼠标点击、键盘输入。
- **核心类**：
  - `CuaScreenshotTool(FunctionTool)`：name=`astrbot_cua_screenshot`；`call(...)` 截图并可选发送给用户/返回图片给 LLM。
  - `CuaMouseClickTool(FunctionTool)`：name=`astrbot_cua_mouse_click`；`call(...)` 点击坐标。
  - `CuaKeyboardTypeTool(FunctionTool)`：name=`astrbot_cua_keyboard_type`；`call(...)` 输入文本。
- **核心函数**（模块级私有）：
  - `_to_json(data)` / `_exception_detail(error)`：序列化与错误格式化。
  - `_get_gui_component(context)`：从 booter 取 `gui` 组件，缺失则报错。
  - `_new_screenshot_path(umo)`：生成截图文件路径（基于 uuid5 前缀 + uuid4）。
- **关键常量**：`_CUA_TOOL_CONFIG = {"provider_settings.computer_use_runtime": "sandbox", "provider_settings.sandbox.booter": "cua"}`。
- **依赖**：`mcp`、`astrbot.api.FunctionTool`、`astrbot.core.computer.computer_client.get_booter`、`astrbot.core.message.message_event_result.MessageChain`、`astrbot.core.utils.astrbot_path.get_astrbot_temp_path`、`.util.check_admin_permission`、`..registry.builtin_tool`。

---

### 1.12 `tools/computer_tools/shipyard_neo/__init__.py`

- **职责**：聚合 shipyard_neo 子包工具，导出浏览器执行类与 Neo skill 生命周期类。
- **核心类**：无定义，re-export。
- **关键常量**：`__all__` 列出 14 个工具类名。
- **依赖**：相对导入 `.browser` 与 `.neo_skills`。

---

### 1.13 `tools/computer_tools/shipyard_neo/browser.py`

- **职责**：定义基于 Shipyard Neo 沙箱的浏览器自动化工具：单命令执行、批量执行、按 skill_key 运行已发布技能。
- **核心类**：
  - `BrowserExecTool(FunctionTool)`：name=`astrbot_execute_browser`；`call(...)` 调用 `browser.exec`。
  - `BrowserBatchExecTool(FunctionTool)`：name=`astrbot_execute_browser_batch`；`call(...)` 调用 `browser.exec_batch`。
  - `RunBrowserSkillTool(FunctionTool)`：name=`astrbot_run_browser_skill`；`call(...)` 调用 `browser.run_skill`。
- **核心函数**：
  - `_to_json(data)`：JSON 序列化。
  - `_get_browser_component(context)`：从 booter 取 `browser` 组件，缺失则报错提示切换到 shipyard_neo。
- **关键常量**：`_SHIPYARD_NEO_TOOL_CONFIG = {"provider_settings.computer_use_runtime": "sandbox", "provider_settings.sandbox.booter": "shipyard_neo"}`。
- **依赖**：`astrbot.api.FunctionTool`、`astrbot.core.computer.computer_client.get_booter`、`.util.check_admin_permission`（上级）、`..registry.builtin_tool`（上级）。

---

### 1.14 `tools/computer_tools/shipyard_neo/neo_skills.py`

- **职责**：定义 Neo skill 生命周期工具集：执行历史查询/标注、skill payload 创建/查询、candidate 创建/列表/评估/提升、release 列表/回滚/同步到本地。
- **核心类**：
  - `NeoSkillToolBase(FunctionTool)`：基类；关键方法 `_run(context, neo_call, error_action)` 统一做权限校验、取 client/sandbox、执行并序列化结果。
  - `GetExecutionHistoryTool(NeoSkillToolBase)`：name=`astrbot_get_execution_history`，查询沙箱执行历史。
  - `AnnotateExecutionTool(NeoSkillToolBase)`：name=`astrbot_annotate_execution`，标注执行历史。
  - `CreateSkillPayloadTool(NeoSkillToolBase)`：name=`astrbot_create_skill_payload`，skill 作者流程 step 1/3，创建不可变 payload 返回 payload_ref。
  - `GetSkillPayloadTool(NeoSkillToolBase)`：name=`astrbot_get_skill_payload`，按 payload_ref 取 payload。
  - `CreateSkillCandidateTool(NeoSkillToolBase)`：name=`astrbot_create_skill_candidate`，step 2/3，绑定执行证据与 skill_key。
  - `ListSkillCandidatesTool(NeoSkillToolBase)`：name=`astrbot_list_skill_candidates`。
  - `EvaluateSkillCandidateTool(NeoSkillToolBase)`：name=`astrbot_evaluate_skill_candidate`。
  - `PromoteSkillCandidateTool(NeoSkillToolBase)`：name=`astrbot_promote_skill_candidate`，step 3/3，提升到 canary/stable，stable+sync_to_local 时调用 `NeoSkillSyncManager.promote_with_optional_sync`，失败自动回滚。
  - `ListSkillReleasesTool(NeoSkillToolBase)`：name=`astrbot_list_skill_releases`。
  - `RollbackSkillReleaseTool(NeoSkillToolBase)`：name=`astrbot_rollback_skill_release`。
  - `SyncSkillReleaseTool(NeoSkillToolBase)`：name=`astrbot_sync_skill_release`，同步 stable release 到本地 SKILL.md。
- **核心函数**：
  - `_to_jsonable(model_like)` / `_to_json_text(data)`：递归把 pydantic/dataclass 转可序列化对象再转 JSON 字符串。
  - `_get_neo_context(context)`：从 booter 取 `bay_client` 与 `sandbox`，缺失则报错。
  - `_sync_release_to_dict(client, *, release_id, skill_key, require_stable)`：调用 `NeoSkillSyncManager.sync_release` 并转 dict。
- **关键常量**：`_SHIPYARD_NEO_TOOL_CONFIG`（同 browser.py）。
- **依赖**：`astrbot.api.FunctionTool`、`astrbot.core.computer.computer_client.get_booter`、`astrbot.core.skills.neo_skill_sync.NeoSkillSyncManager`、`.util.check_admin_permission`（上级）、`..registry.builtin_tool`（上级）。

---

## 2. `computer/` 目录

### 2.1 `computer/computer_client.py`

- **职责**：沙箱 booter 的会话级管理入口，根据配置选择 booter 类型（local/shipyard/shipyard_neo/cua/boxlite）创建/复用沙箱，并把本地 skills 同步到沙箱。
- **核心类**：
  - `_CUAIdleState`（`dataclass(slots=True)`）：CUA 空闲清理任务状态（expires_at + task）。
- **核心函数**：
  - `get_booter(context, session_id)`：核心入口，按配置创建/复用 booter，启动后调用 `_sync_skills_to_sandbox`，对 cua 启用空闲清理。
  - `get_local_booter()`：单例返回 `LocalBooter`。
  - `sync_skills_to_active_sandboxes()`：对所有活跃沙箱会话尽力同步 skills。
  - `_get_cua_idle_timeout(config)` / `_clear_cua_idle_state(session_id)` / `_schedule_cua_idle_cleanup(session_id, timeout)`：CUA 空闲超时清理调度。
  - `_collect_sync_skill_dirs()`：收集需要同步的本地+插件 skill 目录。
  - `_build_python_exec_command(script)` / `_build_apply_sync_command()` / `_build_scan_command()` / `_build_sync_and_scan_command()`：生成在沙箱内执行的 Python 脚本（apply 阶段解压替换 managed skill，scan 阶段扫描 SKILL.md 元数据）。
  - `_apply_skills_to_sandbox(booter)` / `_scan_sandbox_skills(booter)` / `_sync_skills_to_sandbox(booter)`：打包本地 skill 为 zip 上传到沙箱并刷新缓存。
  - `_discover_bay_credentials(endpoint)`：从 credentials.json 自动发现 Bay API key（搜索 BAY_DATA_DIR/mono-repo/cwd）。
  - `_normalize_shell_exec_result(result)` / `_shell_exec_succeeded(result)` / `_format_exec_error_detail(result)` / `_decode_sync_payload(stdout)` / `_update_sandbox_skills_cache(payload)`：结果归一化与缓存更新辅助。
- **关键常量**：
  - `session_booter`：会话→booter 全局字典。
  - `local_booter`：单例。
  - `cua_idle_state`：会话→空闲状态字典。
  - `_MANAGED_SKILLS_FILE = ".astrbot_managed_skills.json"`。
- **依赖**：`astrbot.core.skills.skill_manager`（SkillManager/SANDBOX_SKILLS_ROOT）、`astrbot.core.star.context.Context`、`.booters.base.ComputerBooter`、`.booters.local.LocalBooter`，并按需惰性导入各 booter 子类。

---

### 2.2 `computer/file_read_utils.py`

- **职责**：文件读取工具的统一实现，支持本地与沙箱模式，自动探测文件类型（文本/图片/二进制）、编码、解析 PDF/docx/epub，并对超大输出做 token/字节限制与转换存储。
- **核心类**：
  - `FileProbe`（`dataclass(frozen=True)`）：文件探测结果（kind/encoding/mime_type/size_bytes）。
  - `ParsedDocument`（`dataclass(frozen=True)`）：已解析文档（kind∈docx/epub/pdf + file_bytes + text）。
- **核心函数**：
  - `read_file_tool_result(booter, *, local_mode, path, offset, limit, workspace_dir)`：主入口，根据探测结果分发到文本/图片/文档读取路径。
  - `detect_text_encoding(sample)`：通过 BOM + 多编码尝试 + 可打印字符比例判断文本编码。
  - `read_local_text_range_sync(path, *, encoding, offset, limit)` / `read_local_text_range(...)`：本地按行窗口读取文本。
  - `_build_probe_script(path)` / `_build_text_read_script(...)` / `_build_image_read_script(path)`：生成沙箱内运行的 Python 探测/读取脚本。
  - `_exec_python_json(booter, script, *, action)`：在沙箱执行 Python 并解析 JSON 输出。
  - `_probe_local_file(path)` / `_read_local_image_base64(path)` / `_read_local_file_bytes(path)`：本地文件读取辅助。
  - `_compress_image_bytes_to_base64(data)`：压缩图片为 JPEG base64。
  - `_detect_image_mime(sample)` / `_looks_like_known_binary(sample)` / `_looks_like_pdf(...)` / `_looks_like_zip_container(sample)` / `_is_docx_bytes(...)` / `_is_epub_bytes(...)`：文件类型魔术字节判断。
  - `_parse_local_supported_document(path, sample)`：本地文档解析分发。
  - `_parse_local_docx_text` / `_parse_local_pdf_text` / `_parse_local_epub_text`：调用对应 parser。
  - `_validate_text_output(content)` / `_validate_full_text_read_request(probe)` / `_text_exceeds_read_thresholds(content)` / `_slice_text_by_lines(...)`：输出大小校验与切片。
  - `_store_converted_text_for_workspace(...)` / `_build_converted_text_notice(...)` / `_read_local_supported_document_result(...)`：超大文档转换存储与提示。
- **关键常量**：
  - `_MAX_FILE_READ_BYTES = 128*1024`、`_MAX_FILE_READ_TOKENS = 25_000`、`_MAX_TEXT_FILE_FULL_READ_BYTES = 256*1024`、`_FILE_SNIFF_BYTES = 512`。
  - `_TEXT_ENCODINGS`、`_UTF_BOMS`、`_ZIP_MAGIC_PREFIXES`、`_BINARY_MAGIC_PREFIXES`。
  - `_TOKEN_COUNTER = EstimateTokenCounter()`。
- **依赖**：`mcp`、`astrbot.core.agent.context.token_counter.EstimateTokenCounter`、`astrbot.core.agent.message.Message`、`astrbot.core.utils.media_utils`、`astrbot.core.utils.astrbot_path`、`.booters.base.ComputerBooter`，惰性导入 markitdown/pdf/epub parser。

---

### 2.3 `computer/olayer/__init__.py`

- **职责**：聚合 olayer 子包的 5 个组件 Protocol，统一导出。
- **核心类**：无定义，re-export 5 个 Protocol。
- **关键常量**：`__all__`。
- **依赖**：相对导入 5 个子模块。

---

### 2.4 `computer/olayer/shell.py`

- **职责**：定义 Shell 操作组件 Protocol。
- **核心类**：
  - `ShellComponent(Protocol)`：关键方法 `async exec(command, cwd, env, timeout, shell, background) -> dict`。
- **关键常量**：无。
- **依赖**：`typing.Protocol`。

---

### 2.5 `computer/olayer/python.py`

- **职责**：定义 Python/IPython 操作组件 Protocol。
- **核心类**：
  - `PythonComponent(Protocol)`：关键方法 `async exec(code, kernel_id, timeout, silent, cwd) -> dict`。
- **关键常量**：无。
- **依赖**：`typing.Protocol`。

---

### 2.6 `computer/olayer/filesystem.py`

- **职责**：定义文件系统操作组件 Protocol，包含 create/read/search/edit/write/delete/list_dir 全套方法签名。
- **核心类**：
  - `FileSystemComponent(Protocol)`：关键方法 `create_file`/`read_file`/`search_files`/`edit_file`/`write_file`/`delete_file`/`list_dir`。
- **关键常量**：无。
- **依赖**：`typing.Protocol`。

---

### 2.7 `computer/olayer/gui.py`

- **职责**：定义桌面 GUI 自动化组件 Protocol。
- **核心类**：
  - `GUIComponent(Protocol)`：关键方法 `screenshot(path)`/`click(x, y, button)`/`type_text(text)`/`press_key(key)`。
- **关键常量**：无。
- **依赖**：`typing.Protocol`。

---

### 2.8 `computer/olayer/browser.py`

- **职责**：定义浏览器自动化组件 Protocol。
- **核心类**：
  - `BrowserComponent(Protocol)`：关键方法 `exec(cmd, ...)`/`exec_batch(commands, ...)`/`run_skill(skill_key, ...)`。
- **关键常量**：无。
- **依赖**：`typing.Protocol`。

---

### 2.9 `computer/booters/base.py`

- **职责**：定义所有 booter 的抽象基类 `ComputerBooter`，声明 fs/python/shell/browser/gui/capabilities 属性与 boot/shutdown/upload_file/download_file/available 方法签名。
- **核心类**：
  - `ComputerBooter`：抽象基类；关键属性 `fs`/`python`/`shell`/`capabilities`(默认 None)/`browser`(默认 None)/`gui`(默认 None)；关键方法 `boot(session_id)`/`shutdown(**kwargs)`/`upload_file(path, file_name)`/`download_file(remote_path, local_path)`/`available()`（均为 `...` 占位）。
- **关键常量**：无。
- **依赖**：`..olayer`（5 个组件 Protocol）。

---

### 2.10 `computer/booters/local.py`

- **职责**：本地运行时 booter，用子进程执行 shell/python，用本地文件系统实现 fs 组件，并屏蔽危险命令。
- **核心类**：
  - `LocalShellComponent(ShellComponent)`：`async exec(...)` 通过 `subprocess.Popen` 执行，后台模式用 DEVNULL，前台捕获 stdout/stderr，Windows 用 taskkill 终止超时进程。
  - `LocalPythonComponent(PythonComponent)`：`async exec(...)` 用 `[python, "-c", code]` 子进程执行。
  - `LocalFileSystemComponent(FileSystemComponent)`：实现 create_file/read_file/search_files/edit_file/write_file/delete_file/list_dir；search_files 在 Python<3.14 用 `python_ripgrep.search`，否则调用 `rg` 可执行文件。
  - `LocalBooter(ComputerBooter)`：组合上述三个组件；`boot`/`shutdown` 仅日志；`upload_file`/`download_file` 抛 NotImplementedError；`available()` 返回 True。
- **核心函数**（模块级）：
  - `_is_safe_command(command)`：基于 `_BLOCKED_COMMAND_PATTERNS` 黑名单拦截危险命令。
  - `_decode_bytes_with_fallback(output, *, preferred_encoding)`：多编码回退解码字节。
  - `_decode_shell_output(output)`：shell 输出解码封装。
- **关键常量**：`_BLOCKED_COMMAND_PATTERNS`（rm -rf/mkfs/dd/shutdown/sudo/kill -9 等）。
- **依赖**：`python_ripgrep`（条件导入）、`astrbot.api.logger`、`astrbot.core.computer.file_read_utils`、`astrbot.core.utils.astrbot_path`、`..olayer`、`.base.ComputerBooter`、`.shipyard_search_file_util._truncate_long_lines`。

---

### 2.11 `computer/booters/boxlite.py`

- **职责**：基于 `boxlite` 库在本地 Docker 启动一个 `soulter/shipyard-ship` 容器作为沙箱，并复用 shipyard 的 shell/python/fs 组件。
- **核心类**：
  - `MockShipyardSandboxClient`：模拟 shipyard 沙箱客户端，通过 HTTP 与本地 boxlite 容器通信；关键方法 `_exec_operation`/`upload_file`/`wait_healthy`。
  - `BoxliteBooter(ComputerBooter)`：`boot(session_id)` 启动 boxlite SimpleBox（随机端口映射 8123），用 MockShipyardSandboxClient 构造 shipyard 组件并等待健康检查；`shutdown()` 停止容器；`upload_file` 转发到 mocked 客户端。
- **核心函数**：无模块级函数。
- **关键常量**：无（image/port 等内嵌）。
- **依赖**：`aiohttp`、`boxlite`、`shipyard`（FileSystemComponent/PythonComponent/ShellComponent）、`astrbot.api.logger`、`..olayer`、`.base.ComputerBooter`、`.shipyard.ShipyardFileSystemWrapper`。

---

### 2.12 `computer/booters/bay_manager.py`

- **职责**：通过 Docker Engine API 自动启动/复用/停止 Bay 容器（Shipyard Neo 的本地零配置模式），并读取自动签发的 API key。
- **核心类**：
  - `BayContainerManager`：关键方法 `ensure_running()`（查找/重启/创建带 `astrbot.bay.managed` 标签的容器，返回 endpoint URL）、`wait_healthy(timeout)`（轮询 `/health`）、`read_credentials()`（从容器文件系统读取 credentials.json 取 api_key）、`close_client()`、`stop()`，私有 `_find_managed_container()`/`_pull_image_if_needed()`。
- **核心函数**：无模块级函数。
- **关键常量**：
  - `BAY_IMAGE = "ghcr.io/astrbotdevs/shipyard-neo-bay:latest"`。
  - `BAY_CONTAINER_NAME = "astrbot-bay"`。
  - `BAY_LABEL = "astrbot.bay.managed"`。
  - `BAY_PORT = 8114`。
  - `HEALTH_TIMEOUT_S = 60`、`HEALTH_POLL_INTERVAL_S = 2`。
- **依赖**：`aiodocker`、`aiohttp`、`astrbot.api.logger`。

---

### 2.13 `computer/booters/shipyard.py`

- **职责**：基于 `shipyard` SDK 的 booter 实现，封装 shell/fs 组件以适配 AstrBot 接口。
- **核心类**：
  - `ShipyardShellWrapper`：包装 shipyard ShellComponent，支持 env 前缀注入与 background 命令改造；`async exec(...)` 归一化返回结构。
  - `ShipyardFileSystemWrapper`：包装 shipyard FileSystemComponent，search_files 委托给 `search_files_via_shell`，其余直接转发。
  - `ShipyardBooter(ComputerBooter)`：`__init__(endpoint_url, access_token, ttl, session_num)`；`boot(session_id)` 调用 `ShipyardClient.create_ship` 创建 ship 并组装组件；`shutdown()` 仅日志；`upload_file`/`download_file` 转发；`available()` 检查 ship 状态。
- **核心函数**：`_maybe_model_dump(value)`：把 pydantic/dict 转 dict。
- **关键常量**：无。
- **依赖**：`shipyard`（ShipyardClient/Spec/FileSystemComponent）、`astrbot.api.logger`、`..olayer`、`.base.ComputerBooter`、`.shell_background.build_detached_shell_command`、`.shipyard_search_file_util.search_files_via_shell`。

---

### 2.14 `computer/booters/shipyard_search_file_util.py`

- **职责**：沙箱内文件搜索的 shell 命令构建与执行工具，优先用 ripgrep，回退到 grep，并对超长行做截断。
- **核心函数**：
  - `_truncate_long_lines(text)`：按 `_MAX_SEARCH_LINE_COLUMNS` 截断每行。
  - `_build_rg_command(...)` / `_build_grep_command(...)`：构建 rg/grep 命令参数列表。
  - `_quote_command(command)`：`shlex.join`。
  - `build_search_command(...)`：生成 `if command -v rg ... elif grep ... fi` 的 shell 复合命令。
  - `search_files_via_shell(shell, *, pattern, path, glob, after_context, before_context, timeout)`：执行搜索命令并归一化结果（exit 0/1 视为成功）。
- **关键常量**：`_MAX_SEARCH_LINE_COLUMNS = 1000`。
- **依赖**：`shlex`、`..olayer.ShellComponent`。

---

### 2.15 `computer/booters/shell_background.py`

- **职责**：构建后台分离运行的 shell 命令字符串。
- **核心函数**：
  - `build_detached_shell_command(command)`：用 `python3 -c` 启动一个 `bash -lc` 子进程，重定向 stdio 并 `start_new_session=True`，输出 pid。
- **关键常量**：`_BACKGROUND_SPAWN_SCRIPT`：内联的 Python 启动脚本。
- **依赖**：`shlex`。

---

### 2.16 `computer/booters/cua_defaults.py`

- **职责**：定义 CUA booter 的默认配置与配置键映射。
- **核心函数**：无。
- **关键常量**：
  - `CUA_DEFAULT_CONFIG`：默认 image=linux/os_type=linux/ttl=3600/idle_timeout=0/telemetry_enabled=False/local=True/api_key=""。
  - `CUA_CONFIG_KEYS`：sandbox_cfg 键名映射（cua_image/cua_os_type/cua_ttl/cua_telemetry_enabled/cua_local/cua_api_key）。
- **依赖**：无。

---

### 2.17 `computer/booters/cua.py`

- **职责**：基于 `cua` SDK 的 booter 实现，适配多种 CUA 沙箱后端的 shell/python/fs/gui 组件，包含 POSIX shell 回退与多组件方法名兼容。
- **核心类**：
  - `ProcessResult`（`dataclass(slots=True)`）：归一化进程结果（stdout/stderr/exit_code/success）。
  - `CuaShellComponent(ShellComponent)`：`async exec(...)`，支持 background（仅 POSIX），通过 `_exec_raw` 调用 sandbox.shell.exec/run 并归一化结果。
  - `CuaPythonComponent(PythonComponent)`：`async exec(...)`，优先用 sandbox.python，否则回退到 `python3 -` shell 执行。
  - `CuaFileSystemComponent(FileSystemComponent)`：优先用原生 files/filesystem 组件，缺失则回退到 `_PosixShellFileSystem`；edit_file 通过 read+replace+write 实现。
  - `_PosixShellFileSystem(FileSystemComponent)`：POSIX shell 回退实现（cat/rm -rf/ls/base64 写入）。
  - `CuaGUIComponent(GUIComponent)`：screenshot/click/type_text/press_key，通过 `_resolve_component_method` 兼容多种 SDK 方法名。
  - `_CuaRuntime`（`dataclass(slots=True)`）：运行时聚合（sandbox_cm/sandbox/shell/python/fs/gui）。
  - `CuaBooter(ComputerBooter)`：`__init__(image, os_type, ttl, telemetry_enabled, local, api_key)`；`boot(session_id)` 用 `cua.Image`/`Sandbox.ephemeral` 启动沙箱；`capabilities` 属性动态探测；`upload_file`/`download_file` 多策略（原生/upload/write_bytes/base64 shell）；`available()` 通过 echo 探针检查健康。
- **核心函数**（模块级私有，较多）：
  - `build_cua_booter_kwargs(sandbox_cfg)`：从配置字典构造 booter 参数。
  - `_maybe_await(value)`：自动 await。
  - `_write_base64_via_shell(shell, path, data)`：base64 分块通过 shell heredoc 写文件。
  - `_maybe_model_dump(value)`：多形态转 dict（dict/dataclass/pydantic/.dict()/属性提取）。
  - `_slice_content_by_lines(content, *, offset, limit)`：按行切片。
  - `_normalize_process_result(raw)`：把各种进程返回形态归一化为 ProcessResult。
  - `_is_missing_python3_error(stderr)` / `_python3_requirement_error(operation, stderr)` / `_normalize_with_python3_requirement(raw, operation)`：python3 缺失错误识别与改写。
  - `_exec_python3_or_error(shell, code, *, operation, timeout)`：通过 shell 执行 python3 heredoc。
  - `_is_posix_os_type(os_type)` / `_posix_fs_error_message(os_type)` / `_non_posix_filesystem_result(...)` / `_raise_non_posix_filesystem_error(...)`：POSIX 校验。
  - `_resolve_component_method(component, method_names)` / `_missing_component_method_error(...)` / `_has_component_method(root, component_name, method_name)` / `_resolve_files_components(sandbox)` / `_resolve_files_method(components, method_names)` / `_normalize_native_upload_result(raw, file_name)`：组件方法名兼容解析。
  - `_write_result(path, result)`：写入结果归一化。
  - `_list_dir_via_shell(shell, path, show_hidden)`：ls 命令回退。
  - `_build_cua_background_command(command)`：后台命令构造。
  - `_screenshot_to_bytes(raw)`：把多种截图返回形态（bytes/str/data:/PIL/model_dump）转 bytes。
- **关键常量**：`_POSIX_OS_TYPES = {"linux", "darwin", "macos"}`、`_CUA_SANDBOX_HEALTH_PROBE = "_astrbot_cua_ok_"`、`_CUA_BACKGROUND_LAUNCHER`。
- **依赖**：`cua`（惰性导入 Image/Sandbox）、`astrbot.api.logger`、`..olayer`、`.base.ComputerBooter`、`.cua_defaults`、`.shipyard_search_file_util.search_files_via_shell`。

---

### 2.18 `computer/booters/shipyard_neo.py`

- **职责**：基于 `shipyard_neo` SDK（BayClient/Sandbox）的 booter 实现，支持自动启动 Bay 容器、就绪状态轮询、组件适配与 skill 同步。
- **核心类**：
  - `NeoPythonComponent(PythonComponent)`：`async exec(...)` 调用 `sandbox.python.exec`，归一化 output/error/images 结构。
  - `NeoShellComponent(ShellComponent)`：`async exec(...)` 调用 `sandbox.shell.exec`，支持 env 前缀与 background 命令改造。
  - `NeoFileSystemComponent(FileSystemComponent)`：调用 `sandbox.filesystem.*`，search_files 委托 `search_files_via_shell`，edit_file 通过 read+replace+write 实现，create_file 委托 write_file。
  - `NeoBrowserComponent(BrowserComponent)`：调用 `sandbox.browser.exec`/`exec_batch`/`run_skill`。
  - `ShipyardNeoBooter(ComputerBooter)`：核心 booter；关键属性 `bay_client`/`sandbox`/`capabilities`/`is_auto_mode`；关键方法 `boot(session_id)`（auto 模式启动 Bay 容器→创建 BayClient→create_sandbox→`_wait_until_ready`→组装组件）、`shutdown(*, delete_sandbox=False)`、`_wait_until_ready(sandbox)`（轮询状态，FAILED/EXPIRED/超时则删除沙箱）、`_resolve_profile(client)`、`available()`、`upload_file`/`download_file`。
- **核心函数**：`_maybe_model_dump(value)` / `_slice_content_by_lines(content, *, offset, limit)`。
- **关键常量**：`ShipyardNeoBooter.AUTO_SENTINEL = "__auto__"`、`ShipyardNeoBooter.DEFAULT_PROFILE = "python-default"`。
- **依赖**：`shipyard_neo`（惰性导入 BayClient/Sandbox）、`astrbot.api.logger`、`..olayer`、`.base.ComputerBooter`、`.shell_background.build_detached_shell_command`、`.shipyard_search_file_util.search_files_via_shell`、`.bay_manager.BayContainerManager`（惰性）。

---

## 3. `backup/` 目录

### 3.1 `backup/__init__.py`

- **职责**：备份模块入口，re-export 导出器/导入器与共享常量。
- **核心类**：无定义，re-export `AstrBotExporter`/`AstrBotImporter`/`ImportPreCheckResult`。
- **关键常量**：`__all__`。
- **依赖**：相对导入 `.constants`/`.exporter`/`.importer`。

---

### 3.2 `backup/constants.py`

- **职责**：备份模块共享常量：数据库模型映射、备份目录映射、清单版本号。
- **核心类**：无。
- **核心函数**：
  - `get_backup_directories()`：返回 7 个需备份目录的字典（plugins/plugin_data/config/t2i_templates/webchat/temp/skills）。
- **关键常量**：
  - `MAIN_DB_MODELS`：13 张主库表→SQLModel 类映射（platform_stats/conversations/personas/persona_folders/preferences/platform_message_history/platform_sessions/webchat_threads/chatui_projects/session_project_relations/attachments/command_configs/command_conflicts）。
  - `KB_METADATA_MODELS`：3 张知识库元数据表→模型映射（knowledge_bases/kb_documents/kb_media）。
  - `BACKUP_MANIFEST_VERSION = "1.1"`。
- **依赖**：`sqlmodel.SQLModel`、`astrbot.core.db.po`（13 个 ORM 模型）、`astrbot.core.knowledge_base.models`（3 个 KB 模型）、`astrbot.core.utils.astrbot_path`（7 个路径函数）。

---

### 3.3 `backup/exporter.py`

- **职责**：把主数据库、知识库（元数据+文档+FAISS 索引+媒体）、配置、附件、插件等目录打包为带校验和的 ZIP 备份文件。
- **核心类**：
  - `AstrBotExporter`：关键方法 `export_all(output_dir, progress_callback)` 主流程；私有方法 `_export_main_database()`/`_export_kb_metadata()`/`_export_kb_documents(kb_helper)`/`_export_faiss_index(zf, kb_helper, kb_id)`/`_export_kb_media_files(...)`/`_export_directories(zf)`/`_export_attachments(zf, attachments)`/`_model_to_dict(record)`/`_add_checksum(path, content)`/`_generate_manifest(...)`。
- **核心函数**：无模块级函数。
- **关键常量**：`CMD_CONFIG_FILE_PATH`。
- **依赖**：`sqlalchemy.select`、`astrbot.core.logger`、`astrbot.core.config.default.VERSION`、`astrbot.core.db.BaseDatabase`、`astrbot.core.utils.astrbot_path`、`.constants`，惰性导入 `FaissVecDB`。

---

### 3.4 `backup/importer.py`

- **职责**：从 ZIP 备份文件恢复数据，含版本兼容性预检查（主版本必须一致，小版本警告）、replace 模式清空后导入、路径遍历防护、platform_stats 重复键聚合。
- **核心类**：
  - `ImportPreCheckResult`（`dataclass`）：预检查结果（valid/can_import/version_status/backup_version/current_version/backup_time/confirm_message/warnings/error/backup_summary）；`to_dict()`。
  - `ImportResult`：导入结果（success/imported_tables/imported_files/imported_directories/warnings/errors）；`add_warning`/`add_error`/`to_dict()`。
  - `DatabaseClearError(RuntimeError)`：清库失败异常。
  - `_InvalidCountWarnLimiter`：platform_stats 非法 count 告警限速器。
  - `AstrBotImporter`：关键方法 `pre_check(zip_path)`、`import_all(zip_path, mode, progress_callback)`；私有方法 `_check_version_compatibility(backup_version)`/`_validate_version(manifest)`/`_clear_main_db()`/`_clear_kb_data()`/`_import_main_database(data)`/`_preprocess_main_table_rows(table_name, rows)`/`_merge_platform_stats_rows(rows)`/`_normalize_platform_stats_entry(...)`/`_normalize_platform_stats_timestamp(value)`/`_import_knowledge_bases(...)`/`_import_kb_documents(kb_id, doc_data)`/`_import_attachments(...)`/`_import_directories(...)`/`_convert_datetime_fields(row, model_class)`。
- **核心函数**：
  - `_get_major_version(version_str)`：提取前两位主版本。
  - `_validate_path_within(target_path, base_dir)`：路径遍历防护（CWE-22）。
  - `_load_platform_stats_invalid_count_warn_limit()`：从环境变量读取告警上限。
- **关键常量**：
  - `CMD_CONFIG_FILE_PATH`、`KB_PATH`。
  - `DEFAULT_PLATFORM_STATS_INVALID_COUNT_WARN_LIMIT = 5`。
  - `PLATFORM_STATS_INVALID_COUNT_WARN_LIMIT_ENV`。
  - `PLATFORM_STATS_INVALID_COUNT_WARN_LIMIT`。
- **依赖**：`sqlalchemy.delete`、`astrbot.core.logger`、`astrbot.core.config.default.VERSION`、`astrbot.core.db.BaseDatabase`、`astrbot.core.utils.astrbot_path`、`astrbot.core.utils.io.ensure_dir`、`astrbot.core.utils.version_comparator.VersionComparator`、`.constants`，惰性导入 `DocumentStorage`。

---

## 4. `skills/` 目录

### 4.1 `skills/__init__.py`

- **职责**：skills 模块入口，re-export `SkillInfo`/`SkillManager`/`build_skills_prompt`。
- **核心类**：无定义。
- **关键常量**：`__all__`。
- **依赖**：相对导入 `.skill_manager`。

---

### 4.2 `skills/skill_manager.py`

- **职责**：本地/插件/工作区/沙箱 skill 的发现、配置、激活、删除、安装与系统提示词构建；维护沙箱 skill 缓存以支持离线 UI 一致性。
- **核心类**：
  - `SkillInfo`（`dataclass`）：skill 元信息（name/description/path/active/source_type/source_label/local_exists/sandbox_exists/plugin_name/readonly）。
  - `SkillManager`：关键方法 `list_skills(*, active_only, runtime, show_sandbox_path)`（聚合本地+插件+沙箱缓存 skill）、`list_workspace_skills(workspace_root)`（会话工作区 skill）、`set_sandbox_skills_cache(skills)`、`get_sandbox_skills_cache_status()`、`is_sandbox_only_skill(name)`、`is_plugin_skill(name)`、`set_skill_active(name, active)`、`delete_skill(name)`、`install_skill_from_zip(zip_path, *, overwrite, skill_name_hint)`；私有方法 `_iter_plugin_skill_dirs()`/`_get_plugin_skill_dir(name)`/`_load_config()`/`_save_config(config)`/`_load_sandbox_skills_cache()`/`_save_sandbox_skills_cache(cache)`/`_remove_skill_from_sandbox_cache(name)`。
- **核心函数**（模块级）：
  - `_normalize_skill_name(name)`：空白转下划线。
  - `_default_sandbox_skill_path(name)`：默认沙箱路径 `/workspace/skills/<name>/SKILL.md`。
  - `_normalize_cached_sandbox_skill_path(name, path)`：校验并归一化缓存中的沙箱路径（防 `..` 越权）。
  - `_is_ignored_zip_entry(name)`：忽略 `__MACOSX`。
  - `_normalize_skill_markdown_path(skill_dir, *, rename_legacy)`：返回规范 `SKILL.md` 路径，旧 `skill.md` 可就地重命名。
  - `_parse_frontmatter_description(text)`：解析 SKILL.md YAML frontmatter 取 description。
  - `_is_windows_prompt_path(path)` / `_sanitize_prompt_path_for_prompt(path)` / `_sanitize_prompt_description(description)` / `_sanitize_skill_display_name(name)` / `_build_skill_read_command_example(path)`：提示词安全净化（防注入）。
  - `build_skills_prompt(skills)`：构建 skill 清单系统提示词（渐进式披露规则）。
- **关键常量**：
  - `SKILLS_CONFIG_FILENAME = "skills.json"`。
  - `SANDBOX_SKILLS_CACHE_FILENAME = "sandbox_skills_cache.json"`。
  - `DEFAULT_SKILLS_CONFIG = {"skills": {}}`。
  - `SANDBOX_SKILLS_ROOT = "skills"`、`SANDBOX_WORKSPACE_ROOT = "/workspace"`、`WORKSPACE_SKILLS_ROOT = "skills"`。
  - `WORKSPACE_SKILL_FRONTMATTER_MAX_CHARS = 64*1024`。
  - `_SANDBOX_SKILLS_CACHE_VERSION = 1`。
  - `_SKILL_NAME_RE = re.compile(r"^[\w.-]+$")`。
  - 多个路径安全正则 `_SAFE_PATH_RE`/`_WINDOWS_DRIVE_PATH_RE`/`_WINDOWS_UNC_PATH_RE`/`_CONTROL_CHARS_RE`。
- **依赖**：`yaml`、`astrbot.core.utils.astrbot_path`。

---

### 4.3 `skills/neo_skill_sync.py`

- **职责**：把 Shipyard Neo 上发布的 stable skill release 同步到本地 `SKILL.md`，维护 skill_key→local_skill_name 映射，并在 promote 时可选同步+失败自动回滚。
- **核心类**：
  - `NeoSkillSyncResult`（`dataclass`）：同步结果（skill_key/local_skill_name/release_id/candidate_id/payload_ref/map_path/synced_at）。
  - `NeoSkillSyncManager`：关键方法 `sync_release(client, *, release_id, skill_key, require_stable)`（查找 release→取 candidate→取 payload→写本地 SKILL.md→更新映射→激活→同步到活跃沙箱）、`promote_with_optional_sync(client, *, candidate_id, stage, sync_to_local)`（promote 后可选同步，失败自动 rollback）、`sync_result_to_dict(result)`（静态）、`normalize_skill_name(skill_key)`（静态，加 `neo_` 前缀）；私有方法 `_load_map()`/`_save_map(data)`/`_resolve_local_skill_name(skill_key, mapping)`/`_find_release(client, *, release_id)`/`_find_active_stable_release(client, *, skill_key)`。
- **核心函数**：
  - `_now_iso()`：UTC ISO 时间。
  - `_to_jsonable(model_like)`：pydantic/dict 转 dict。
  - `_parse_frontmatter(text)`：简易 frontmatter 解析（name/description）。
  - `_derive_description(markdown_body)`：从 markdown 正文推导描述（优先 `## 描述`/`## description` 段）。
  - `_ensure_skill_frontmatter(markdown, *, skill_name, skill_key)`：确保 SKILL.md 有合法 frontmatter。
- **关键常量**：`_MAP_VERSION = 1`、`_MAP_FILE_NAME = "neo_skill_map.json"`、`_SKILL_NAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")`。
- **依赖**：`astrbot.core.computer.computer_client.sync_skills_to_active_sandboxes`、`astrbot.core.skills.skill_manager.SkillManager`、`astrbot.core.utils.astrbot_path.get_astrbot_skills_path`。

---

## 5. `cron/` 目录

### 5.1 `cron/__init__.py`

- **职责**：cron 模块入口，re-export `CronJobManager`。
- **核心类**：无定义。
- **关键常量**：`__all__ = ["CronJobManager"]`。
- **依赖**：相对导入 `.manager`。

---

### 5.2 `cron/events.py`

- **职责**：定义 cron 任务触发主 Agent 时使用的合成事件 `CronMessageEvent`。
- **核心类**：
  - `CronMessageEvent(AstrMessageEvent)`：`__init__(*, context, session, message, sender_id, sender_name, extras, message_type)` 构造 `AstrBotMessage` 与 `PlatformMetadata(name="cron")`；设置 `is_at_or_wake_command=True`/`is_wake=True`；`async send(message)` 通过 context.send_message 发送；`async send_streaming(generator, use_fallback)` 逐条发送。
- **核心函数**：无模块级函数。
- **关键常量**：无。
- **依赖**：`astrbot.core.message.components.Plain`、`astrbot.core.message.message_event_result.MessageChain`、`astrbot.core.platform.astr_message_event.AstrMessageEvent`、`astrbot.core.platform.astrbot_message`（AstrBotMessage/MessageMember）、`astrbot.core.platform.message_session.MessageSession`、`astrbot.core.platform.message_type.MessageType`、`astrbot.core.platform.platform_metadata.PlatformMetadata`。

---

### 5.3 `cron/manager.py`

- **职责**：基于 APScheduler 的中央定时任务调度器，支持 basic（注册处理器）与 active_agent（唤醒主 Agent 执行）两类任务，含 cron 表达式 weekday 归一化、一次性任务、状态持久化与主 Agent 唤醒流程。
- **核心类**：
  - `CronJobSchedulingError(Exception)`：调度失败异常。
  - `CronJobManager`：关键属性 `db`/`scheduler`(AsyncIOScheduler)/`_basic_handlers`/`_lock`/`_started`；关键方法 `start(ctx)`（启动调度器并 sync_from_db）、`shutdown()`、`sync_from_db()`、`add_basic_job(...)`、`add_active_job(...)`、`update_job(job_id, **kwargs)`、`delete_job(job_id)`、`list_jobs(job_type)`、`run_job_now(job_id)`；私有方法 `_remove_scheduled(job_id)`、`_schedule_job(job)`（构造 DateTrigger/CronTrigger，归一化 weekday，add_job）、`_get_next_run_time(job_id)`、`_run_job(job_id, *, ignore_enabled, delete_run_once)`、`_run_basic_job(job)`、`_run_active_agent_job(job, start_time)`、`_woke_main_agent(*, message, session_str, extras, delivery_session_str)`（构造 CronMessageEvent→build_main_agent→step_until_done→persist_agent_history）。
- **核心函数**：
  - `_normalize_crontab_day_of_week(day_of_week)`：把标准 crontab（Sunday=0/7）weekday 字段展开为 APScheduler 兼容的星期名（mon/tue/...），支持 `*`/范围/步长/逗号列表。
- **关键常量**：
  - `_CRONTAB_WEEKDAY_NAMES = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")`。
  - `_CRONTAB_WEEKDAY_PATTERN`：匹配 weekday 字段的正则。
- **依赖**：`apscheduler`（AsyncIOScheduler/CronTrigger/DateTrigger）、`astrbot.core.agent.tool.ToolSet`、`astrbot.core.cron.events.CronMessageEvent`、`astrbot.core.db.BaseDatabase`、`astrbot.core.db.po.CronJob`、`astrbot.core.platform.message_session.MessageSession`、`astrbot.core.platform.message_type.MessageType`、`astrbot.core.provider.entites.ProviderRequest`、`astrbot.core.utils.history_saver.persist_agent_history`，惰性导入 `astrbot.core.astr_main_agent` 与 `SendMessageToUserTool`。

---

## 覆盖性核对

| 目录 | 文件数 | 已分析 |
|------|--------|--------|
| `tools/`（含子目录） | 14 | ✅ 全部 |
| `computer/`（含子目录） | 18 | ✅ 全部 |
| `backup/` | 4 | ✅ 全部 |
| `skills/` | 3 | ✅ 全部 |
| `cron/` | 3 | ✅ 全部 |
| **合计** | **42** | **42** |

> 备注：
> - `tools/` 与 `tools/computer_tools/` 顶层无 `__init__.py`（Glob 未返回），`registry.py` 是 tools 包的隐式入口。
> - `computer/` 顶层同样无 `__init__.py`，`computer_client.py` 是隐式入口。
> - `computer/olayer/`、`computer/booters/`、`backup/`、`skills/`、`cron/` 均有 `__init__.py`。

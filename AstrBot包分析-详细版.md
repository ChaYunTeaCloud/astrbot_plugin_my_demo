# AstrBot v4.26.7 包完整架构分析（超详细版）

> 本文档基于 `.venv/Lib/site-packages/astrbot` 源码的**深度分析**，覆盖包的完整目录结构、类层次、方法签名、数据流、调用关系、配置体系、内部机制、关键实现细节等。
> 每个章节均附带关键源码片段，帮助开发者从源代码级理解 AstrBot 框架。

---

## 目录

- [一、包总览与目录树](#一包总览与目录树)
- [二、核心启动流程与生命周期](#二核心启动流程与生命周期)
- [三、全局单例与公共资源](#三全局单例与公共资源)
- [四、配置系统详解](#四配置系统详解)
- [五、管道系统详解（Pipeline）](#五管道系统详解pipeline)
- [六、9 个 Stage 逐个剖析](#六9-个-stage-逐个剖析)
- [七、插件系统详解（Star）](#七插件系统详解star)
- [八、Agent 系统详解](#八agent-系统详解)
- [九、Provider 体系详解](#九provider-体系详解)
- [十、平台适配体系详解](#十平台适配体系详解)
- [十一、事件总线与消息流](#十一事件总线与消息流)
- [十二、Dashboard 架构详解](#十二dashboard-架构详解)
- [十三、数据库层详解](#十三数据库层详解)
- [十四、内置工具集（Builtin Tools）](#十四内置工具集builtin-tools)
- [十五、子系统总览](#十五子系统总览)
- [十六、全局注册表汇总](#十六全局注册表汇总)
- [十七、主 Agent 构建流程（build_main_agent）](#十七主-agent-构建流程build_main_agent)
- [十八、配置项完整参考](#十八配置项完整参考)
- [十九、消息组件与事件模型](#十九消息组件与事件模型)
- [二十、AstrBot 核心数据流全景图](#二十astrbot-核心数据流全景图)

---

## 一、包总览与目录树

```
astrbot/  (v4.26.7)
├── __init__.py                          # 版本号定义 + 根 logger
├── api/                                 # 🌐 插件开发者公共 API
│   ├── __init__.py                      # 聚合导出
│   ├── all.py                           # 全量 API 聚合
│   ├── message_components.py            # 消息组件（MessageChain, At, Node, Plain, Image, Record, Reply, Forward, Json, Face, Video, File）
│   ├── web.py                           # Web 相关 API
│   ├── event/__init__.py                # 事件 API
│   ├── platform/__init__.py             # 平台 API
│   ├── provider/__init__.py              # Provider API
│   ├── star/__init__.py                  # 插件 API
│   └── util/__init__.py                  # 工具 API
│
├── core/                                # ⚙️ 核心引擎层
│   ├── __init__.py                      # 全局单例（astrbot_config, html_renderer, db_helper, sp, file_token_service, pip_installer）
│   ├── astrbot_config_mgr.py            # AstrBotConfigManager 多配置管理
│   ├── core_lifecycle.py                # AstrBotCoreLifecycle 启动/停止/重启
│   ├── initial_loader.py                # 初始加载器
│   ├── event_bus.py                     # EventBus 事件总线
│   ├── exceptions.py                   # 异常定义
│   ├── log.py                           # 日志系统（LogBroker, LogManager）
│   ├── conversation_mgr.py              # ConversationManager 会话管理
│   ├── persona_mgr.py                  # PersonaManager 人格管理
│   ├── persona_error_reply.py           # Persona 错误回复工具
│   ├── platform_message_history_mgr.py  # 平台消息历史
│   ├── subagent_orchestrator.py         # SubAgentOrchestrator 子 Agent 编排
│   ├── umop_config_router.py            # UmopConfigRouter
│   ├── umo_alias.py                    # UMO 别名管理
│   ├── updator.py                      # AstrBotUpdator 版本更新
│   ├── astr_agent_context.py            # Agent 上下文封装
│   ├── astr_agent_hooks.py              # MAIN_AGENT_HOOKS
│   ├── astr_agent_run_util.py           # AgentRunner / run_agent / run_live_agent
│   ├── astr_agent_tool_exec.py          # FunctionToolExecutor
│   ├── astr_main_agent.py              # MainAgentBuildConfig / build_main_agent
│   ├── astr_main_agent_resources.py     # System Prompt 常量
│   ├── desktop_runtime.py               # 桌面运行时
│   ├── file_token_service.py            # 文件令牌服务
│   ├── workspace.py                     # 工作区管理
│   │
│   ├── config/                          # 📝 配置子系统
│   │   ├── __init__.py
│   │   ├── astrbot_config.py            # AstrBotConfig(dict) 配置类
│   │   ├── default.py                   # DEFAULT_CONFIG / VERSION / DB_PATH
│   │   └── i18n_utils.py                # 国际化工具
│   │
│   ├── db/                              # 💾 数据库子系统
│   │   ├── __init__.py                  # BaseDatabase 抽象基类
│   │   ├── sqlite.py                    # SQLiteDatabase 实现
│   │   ├── po.py                        # 持久化对象（SQLModel Models）
│   │   ├── migration/                   # 数据库迁移脚本
│   │   │   ├── helper.py
│   │   │   ├── migra_3_to_4.py
│   │   │   ├── migra_45_to_46.py
│   │   │   ├── migra_token_usage.py
│   │   │   ├── migra_webchat_session.py
│   │   │   ├── shared_preferences_v3.py
│   │   │   └── sqlite_v3.py
│   │   └── vec_db/                      # 向量数据库
│   │       ├── base.py
│   │       └── faiss_impl/
│   │           ├── __init__.py
│   │           ├── vec_db.py            # FaissVecDatabase
│   │           ├── document_storage.py
│   │           └── embedding_storage.py
│   │
│   ├── platform/                        # 📱 平台适配层
│   │   ├── platform.py                  # Platform(ABC) 抽象基类 + PlatformStatus + PlatformError
│   │   ├── astr_message_event.py        # AstrMessageEvent(ABC) 事件基类
│   │   ├── astrbot_message.py           # AstrBotMessage 消息模型
│   │   ├── message_type.py              # MessageType 枚举
│   │   ├── message_session.py           # MessageSession / MessageSesion
│   │   ├── platform_metadata.py        # PlatformMetadata 元数据
│   │   ├── register.py                  # register_platform_adapter 装饰器
│   │   ├── manager.py                   # PlatformManager 管理器
│   │   ├── webhook_server.py            # Webhook 服务器
│   │   └── sources/                     # 20+ 平台实现（见第十章）
│   │
│   ├── provider/                        # 🤖 LLM Provider 层
│   │   ├── provider.py                  # AbstractProvider / Provider / STTProvider / TTSProvider / EmbeddingProvider / RerankProvider
│   │   ├── manager.py                   # ProviderManager 管理器
│   │   ├── register.py                  # register_provider_adapter 装饰器 + llm_tools
│   │   ├── entities.py / entites.py     # 数据实体（LLMResponse, ProviderRequest, ToolCallsResult, ToolCall, ProviderType, ProviderMeta 等）
│   │   ├── func_tool_manager.py         # FuncCall, FunctionTool 管理
│   │   ├── modalities.py               # 模态处理
│   │   └── sources/                     # 50+ Provider 实现
│   │
│   ├── star/                            # 🔌 插件(Star)系统
│   │   ├── base.py                      # Star 插件基类
│   │   ├── context.py                   # Context 上下文
│   │   ├── star.py                      # StarMetadata, star_map, star_registry
│   │   ├── star_manager.py              # PluginManager 管理器
│   │   ├── star_handler.py              # StarHandlerMetadata, StarHandlerRegistry, EventType
│   │   ├── star_tools.py                # StarTools 工具集
│   │   ├── config.py                    # 插件配置
│   │   ├── command_management.py        # 命令管理
│   │   ├── updator.py                   # 插件更新器
│   │   ├── session_llm_manager.py       # SessionServiceManager
│   │   ├── session_plugin_manager.py    # SessionPluginManager
│   │   ├── error_messages.py            # 错误消息格式化
│   │   ├── register/                    # 注册装饰器
│   │   │   ├── __init__.py
│   │   │   ├── star.py                  # register_star (已废弃)
│   │   │   └── star_handler.py          # register_command, register_agent 等
│   │   └── filter/                      # 事件过滤器
│   │       ├── __init__.py              # HandlerFilter 基类
│   │       ├── command.py               # CommandFilter
│   │       ├── command_group.py         # CommandGroupFilter
│   │       ├── regex.py                 # RegexFilter
│   │       ├── permission.py            # PermissionType, PermissionTypeFilter
│   │       ├── event_message_type.py    # EventMessageType, EventMessageTypeFilter
│   │       ├── platform_adapter_type.py # PlatformAdapterType, PlatformAdapterTypeFilter
│   │       └── custom_filter.py         # CustomFilter, CustomFilterAnd, CustomFilterOr
│   │
│   ├── pipeline/                        # 🔄 管道系统
│   │   ├── stage.py                     # Stage(ABC), register_stage, registered_stages
│   │   ├── stage_order.py               # STAGES_ORDER 执行顺序
│   │   ├── scheduler.py                 # PipelineScheduler 管道调度器
│   │   ├── bootstrap.py                 # ensure_builtin_stages_registered
│   │   ├── context.py                   # PipelineContext
│   │   ├── context_utils.py             # call_event_hook, call_handler
│   │   ├── waking_check/stage.py         # Stage 1: WakingCheckStage
│   │   ├── whitelist_check/stage.py     # Stage 2: WhitelistCheckStage
│   │   ├── session_status_check/stage.py # Stage 3: SessionStatusCheckStage
│   │   ├── rate_limit_check/stage.py    # Stage 4: RateLimitStage
│   │   ├── content_safety_check/stage.py # Stage 5: ContentSafetyCheckStage
│   │   │   └── strategies/              # keywords.py, baidu_aip.py, strategy.py
│   │   ├── preprocess_stage/stage.py    # Stage 6: PreProcessStage
│   │   ├── process_stage/               # Stage 7: ProcessStage
│   │   │   ├── stage.py
│   │   │   ├── follow_up.py              # Follow-up 机制
│   │   │   └── method/
│   │   │       ├── star_request.py       # StarRequestSubStage
│   │   │       ├── agent_request.py      # AgentRequestSubStage
│   │   │       └── agent_sub_stages/
│   │   │           ├── internal.py       # InternalAgentSubStage（本地）
│   │   │           └── third_party.py    # ThirdPartyAgentSubStage（第三方）
│   │   ├── result_decorate/stage.py     # Stage 8: ResultDecorateStage
│   │   └── respond/stage.py             # Stage 9: RespondStage
│   │
│   ├── agent/                           # 🧠 Agent 系统
│   │   ├── agent.py                     # Agent 数据类
│   │   ├── hooks.py                     # BaseAgentRunHooks
│   │   ├── message.py                   # Message, ContentPart, AssistantMessageSegment, ToolCallMessageSegment
│   │   ├── response.py                  # AgentResponse, AgentResponseData, AgentStats
│   │   ├── run_context.py               # TContext, ContextWrapper
│   │   ├── tool.py                      # ToolSchema, FunctionTool, ToolSet
│   │   ├── tool_executor.py             # BaseFunctionToolExecutor
│   │   ├── handoff.py                   # HandoffTool（子 Agent 切换工具）
│   │   ├── mcp_client.py                # MCP 客户端封装
│   │   ├── tool_image_cache.py          # 工具图片缓存
│   │   ├── context/                     # Agent 上下文管理
│   │   │   ├── manager.py               # ContextManager
│   │   │   ├── compressor.py            # ContextCompressor
│   │   │   ├── token_counter.py         # TokenCounter, EstimateTokenCounter
│   │   │   ├── truncator.py             # ContextTruncator
│   │   │   ├── round_utils.py
│   │   │   └── config.py                # ContextConfig
│   │   └── runners/                     # Agent 运行器
│   │       ├── base.py                  # AgentState, BaseAgentRunner(ABC)
│   │       ├── tool_loop_agent_runner.py # ToolLoopAgentRunner
│   │       ├── coze/                    # CozeAgentRunner
│   │       ├── dashscope/               # DashScopeAgentRunner
│   │       ├── deerflow/                # DeerflowAgentRunner
│   │       └── dify/                    # DifyAgentRunner
│   │
│   ├── knowledge_base/                  # 📚 知识库系统
│   ├── computer/                        # 💻 Computer Use 系统
│   ├── skills/                          # 🎯 Skill 系统
│   ├── tools/                           # 🔧 内置工具集
│   │   ├── registry.py                  # builtin_tool 装饰器
│   │   ├── computer_tools/              # CUA 工具（Browser, Shell, Python, FileSystem）
│   │   ├── cron_tools.py                # FutureTaskTool
│   │   ├── knowledge_base_tools.py      # KnowledgeBaseQueryTool
│   │   ├── message_tools.py             # SendMessageToUserTool
│   │   └── web_search_tools.py          # 多种 Web 搜索工具
│   ├── message/                         # 消息组件
│   │   ├── components.py                # 所有消息组件类
│   │   └── message_event_result.py       # MessageEventResult, MessageChain, ResultContentType
│   ├── cron/                            # ⏰ Cron 定时任务
│   ├── backup/                          # 💾 备份导入导出
│   └── utils/                           # 🔧 工具函数
│
├── dashboard/                           # 🖥️ Web Dashboard (FastAPI + Hypercorn)
│   ├── server.py                        # AstrBotDashboard 服务器
│   ├── asgi_runtime.py                  # ASGI 运行时
│   ├── schemas.py                       # Pydantic 数据模型
│   ├── responses.py                     # 响应封装
│   ├── password_state.py                # 密码状态管理
│   ├── plugin_page_auth.py              # 插件页面认证
│   ├── utils.py                         # Dashboard 工具
│   └── services/                        # 业务逻辑层（30+ Service）
│
├── builtin_stars/                       # 📦 内置插件
│   ├── astrbot/                         # 核心聊天插件
│   └── builtin_commands/                # 内置命令插件
│
├── utils/                               # 顶层工具
│
└── cli/                                 # 🛠️ CLI 工具
    ├── __main__.py                      # python -m astrbot.cli
    ├── commands/                        # CLI 子命令（init, run, conf, plug, password）
    └── utils/
```

---

## 二、核心启动流程与生命周期

### 2.1 `astrbot/__init__.py` — 版本号

```python
import logging
__version__ = "4.26.7"
logger = logging.getLogger("astrbot")
```

### 2.2 `core/__init__.py` — 全局单例初始化

```python
# 在 import 时立即创建的全局单例:
astrbot_config: AstrBotConfig = AstrBotConfig()
t2i_base_url = astrbot_config.get("t2i_endpoint", "https://t2i.soulter.top/text2img")
html_renderer = HtmlRenderer(t2i_base_url)
logger = LogManager.GetLogger(log_name="astrbot")
LogManager.configure_logger(logger, astrbot_config)
LogManager.configure_trace_logger(astrbot_config)
db_helper: SQLiteDatabase = SQLiteDatabase(DB_PATH)
sp = SharedPreferences(db_helper=db_helper)
file_token_service = FileTokenService()
pip_installer = PipInstaller(
    astrbot_config.get("pip_install_arg", ""),
    astrbot_config.get("pypi_index_url", None),
)
```

**关键点**：
- 所有单例在**模块 import 时即实例化**，整个生命周期内共享。
- `astrbot_config` 是一个 `AstrBotConfig(dict)` 对象，可通过点号操作符访问任意层级配置。
- `db_helper` 是 SQLite 数据库封装，基于 `BaseDatabase` 抽象基类。
- `sp` (SharedPreferences) 基于数据库的偏好设置存储。
- `html_renderer` 用于文本转图片（T2I）。

### 2.3 `AstrBotCoreLifecycle` 启动步骤

```
1. __init__(log_broker, db)
   │  - 初始化日志代理
   │  - 设置 HTTP 代理
   │
2. async _init_components()
   │  按顺序初始化所有管理器:
   │  ├── AstrBotConfigManager        (多配置管理)
   │  ├── PersonaManager              (人格管理)
   │  ├── ProviderManager             (LLM Provider 管理)
   │  ├── PlatformManager             (平台管理)
   │  ├── ConversationManager         (会话管理)
   │  ├── PlatformMessageHistoryManager (消息历史)
   │  ├── KnowledgeBaseManager        (知识库)
   │  ├── CronJobManager              (定时任务)
   │  ├── SubAgentOrchestrator        (子 Agent 编排)
   │  ├── PluginManager               (插件管理)
   │  └── EventBus                    (事件总线)
   │
3. async _init_pipeline()
   │  为每个配置创建 PipelineScheduler:
   │  ├── PipelineContext(astrbot_config, plugin_manager)
   │  ├── PipelineScheduler(context) → 初始化 9 个 Stage
   │  └── mapping[config_id] = scheduler
   │
4. async _load_plugins()
   │  PluginManager.load()
   │  ├── 扫描 plugins/ 目录
   │  ├── 导入模块 (__init_subclass__ 自动注册)
   │  ├── 加载 metadata.yaml
   │  ├── 版本兼容性检查
   │  └── 实例化 + 绑定 Handler + 激活 LLM 工具
   │
5. async _start_platforms()
   │  PlatformManager.start_all()
   │  └── 启动所有已注册的平台适配器
   │
6. async _start_event_bus()
   │  asyncio.create_task(event_bus.dispatch())
   │  └── 无限循环: 从队列取事件 → 创建 pipeline task
   │
7. async _fire_loaded_events()
   │  触发 OnAstrBotLoadedEvent → OnPlatformLoadedEvent → OnPluginLoadedEvent
   │
8. Dashboard 启动
   │  AstrBotDashboard.run()
   │  └── Hypercorn ASGI 服务器
   │
9. 进入主循环 (await asyncio.Event().wait())
```

---

## 三、全局单例与公共资源

### 3.1 单例列表

| 单例 | 类型 | 说明 |
|------|------|------|
| `astrbot_config` | `AstrBotConfig` | 全局主配置（可多份） |
| `html_renderer` | `HtmlRenderer` | T2I 渲染器 |
| `logger` | `logging.Logger` | 根 logger |
| `db_helper` | `SQLiteDatabase` | SQLite 数据库 |
| `sp` | `SharedPreferences` | 偏好设置存储 |
| `file_token_service` | `FileTokenService` | 文件令牌服务 |
| `pip_installer` | `PipInstaller` | pip 安装器 |

### 3.2 `LogManager` 日志系统

```python
# log.py
class LogManager:
    @staticmethod
    def GetLogger(log_name="astrbot") -> logging.Logger: ...

    @staticmethod
    def configure_logger(logger: logging.Logger, config: dict) -> None: ...

    @staticmethod
    def configure_trace_logger(config: dict) -> None: ...

class LogBroker:
    """日志代理，用于转发到 Dashboard 等消费者"""
```

### 3.3 `FileTokenService`

为文件上传/下载提供一次性令牌，用于 Dashboard 与插件页面的文件访问鉴权。

### 3.4 `PipInstaller`

```python
class PipInstaller:
    async def install(self, requirements_path: str, ...) -> None: ...
    def prefer_installed_dependencies(self, requirements_path: str) -> None: ...
```

---

## 四、配置系统详解

### 4.1 `AstrBotConfig` 类

```python
class AstrBotConfig(dict):
    """继承自 dict，支持点号操作符访问（通过 __getattr__ / __setattr__）"""

    config_path: str                 # JSON 文件路径
    default_config: dict             # 默认配置
    schema: dict | None              # 配置 Schema（JSON Schema）
    _save_state_lock: Lock           # 状态锁
    _save_commit_lock: Lock          # 提交锁
    _save_revision: int              # 保存版本号
    _generated_dashboard_password: str | None  # 初始随机密码

    def __init__(self, config_path=None, default_config=None, schema=None):
        # 1. 如果 schema 存在 → _config_schema_to_default_config()
        # 2. 如果配置文件不存在 → 写入默认配置
        # 3. 读取 JSON 配置文件
        # 4. check_config_integrity() → 插入缺失的默认值
        # 5. 检查 Dashboard 密码是否需要重置
        # 6. 保存最终配置

    def __getattr__(self, name):
        """将属性访问映射到 dict key"""

    def save_config(self) -> None:
        """保存到 JSON 文件（带版本号保护）"""

    def check_config_integrity(self) -> None:
        """插入默认配置中存在但用户配置中缺失的字段"""
```

### 4.2 `AstrBotConfigManager` 多配置管理

```python
class AstrBotConfigManager:
    """管理多个 AstrBotConfig 实例（多配置文件）"""

    configs: dict[str, AstrBotConfig]
    primary_config: AstrBotConfig

    def get_conf_info(self, umo: str) -> tuple[str, AstrBotConfig]:
        """根据 unified_msg_origin 获取对应配置"""

    def new_config(self, config_id: str) -> AstrBotConfig: ...
    def delete_config(self, config_id: str) -> None: ...
```

### 4.3 `DEFAULT_CONFIG` 默认配置结构

```jsonc
{
  "config_version": 2,
  "admins_id": ["astrbot"],
  "dashboard": {
    "enable": true,
    "username": "astrbot",
    "password": "",
    "host": "0.0.0.0",
    "port": 6185,
    "disable_access_log": true,
    "ssl": { "enable": false, "cert_file": "", "key_file": "", "ca_certs": "" },
    "totp": { "enable": false, "secret": "" },
    "auth_rate_limit": { "enable": true, "average_interval": 1.0, "max_burst": 3 },
    "trust_proxy_headers": false,
    "jwt_secret": ""
  },
  "platform_settings": {
    "unique_session": false,
    "rate_limit": { "time": 60, "count": 30, "strategy": "stall" },
    "reply_prefix": "",
    "forward_threshold": 1500,
    "enable_id_white_list": true,
    "id_whitelist": [],
    "wl_ignore_admin_on_group": true,
    "wl_ignore_admin_on_friend": true,
    "reply_with_mention": false,
    "reply_with_quote": false,
    "path_mapping": [],
    "segmented_reply": {
      "enable": false,
      "only_llm_result": true,
      "interval_method": "random",
      "interval": "1.5,3.5",
      "log_base": 2.6,
      "words_count_threshold": 150,
      "split_mode": "regex",
      "regex": ".*?[。？！~…]+|.+$",
      "split_words": ["。","？","！","~","…"],
      "content_cleanup_rule": ""
    },
    "no_permission_reply": true,
    "friend_message_needs_wake_prefix": false,
    "ignore_bot_self_message": false,
    "ignore_at_all": false,
    "platform_specific": {}
  },
  "provider_sources": [],
  "provider": [],
  "provider_settings": {
    "enable": true,
    "default_provider_id": "",
    "fallback_chat_models": [],
    "request_max_retries": 5,
    "provider_pool": ["*"],
    "wake_prefix": "",
    "web_search": false,
    "agent_runner_type": "local",
    "max_agent_step": 30,
    "tool_call_timeout": 120,
    "streaming_response": false,
    "unsupported_streaming_strategy": "turn_off",
    "display_reasoning_text": false,
    "identifier": false,
    "prompt_prefix": "{{prompt}}",
    "context_limit_reached_strategy": "llm_compress",
    "max_context_length": -1,
    "dequeue_context_length": 1,
    "fallback_max_context_tokens": 128000,
    "sandbox": { /* ... */ },
    "computer_use_runtime": "none",
    "image_compress_enabled": true,
    "image_compress_options": { "max_size": 1280, "quality": 0.75 },
    "tool_schema_mode": "full",
    "show_tool_use_status": true,
    "show_tool_call_result": false,
    "buffer_intermediate_messages": false,
    "proactive_capability": { "add_cron_tools": true },
    "quoted_message_parser": { /* ... */ }
  },
  "subagent_orchestrator": {
    "main_enable": false,
    "remove_main_duplicate_tools": false,
    "router_system_prompt": "You are a task router...",
    "agents": []
  },
  "provider_stt_settings": { "enable": false, "provider_id": "" },
  "provider_tts_settings": {
    "enable": false, "provider_id": "",
    "dual_output": false, "use_file_service": false,
    "trigger_probability": 1.0
  },
  "content_safety": {
    "also_use_in_response": false,
    "internal_keywords": { "enable": true, "extra_keywords": [] },
    "baidu_aip": { "enable": false, "app_id": "", "api_key": "", "secret_key": "" }
  },
  "t2i": false,
  "t2i_word_threshold": 150,
  "t2i_strategy": "remote",
  "t2i_active_template": "base",
  "cron": { "enable": true, "allow_inline_expression": false },
  "http_proxy": "",
  "no_proxy": ["localhost", "127.0.0.1", "::1", "10.*", "192.168.*"],
  "plugin_set": ["*"],
  "disable_builtin_commands": false,
  "plugins_pip_install_index_url": "https://pypi.org/simple",
  "kb_agentic_mode": false,
  "timezone": "Asia/Shanghai"
}
```

---

## 五、管道系统详解（Pipeline）

### 5.1 核心设计思想

AstrBot 的管道系统基于**洋葱模型（Onion Model）**实现，每个 Stage 可以：
- 返回 `None`：同步阶段，执行完直接进入下一个 Stage。
- 返回 `AsyncGenerator`：异步生成器，形成洋葱模型结构——**前置逻辑**在 `yield` 之前执行，**后置逻辑**在递归返回后执行。

```
Stage1.process(event)  返回 AsyncGenerator
    │
    ├── 前置逻辑 (yield 之前)
    │     │
    │     ▼
    │   Stage2.process(event) 返回 AsyncGenerator
    │     ├── 前置逻辑
    │     │     │
    │     │     ▼
    │     │   Stage3.process(event) ...
    │     │     │
    │     │     ▼
    │     ├── 后置逻辑 (yield 之后)
    │     │
    ├── 后置逻辑 (yield 之后)
    │
    ▼
  返回最终结果
```

### 5.2 `Stage` 基类

```python
# pipeline/stage.py
registered_stages: list[type[Stage]] = []  # 全局注册表

def register_stage(cls):
    """装饰器，将 Stage 类注册到全局列表"""
    registered_stages.append(cls)
    return cls

class Stage(abc.ABC):
    @abc.abstractmethod
    async def initialize(self, ctx: PipelineContext) -> None: ...

    @abc.abstractmethod
    async def process(self, event: AstrMessageEvent) -> None | AsyncGenerator[None]: ...
```

### 5.3 `PipelineScheduler` 调度器

```python
class PipelineScheduler:
    def __init__(self, context: PipelineContext) -> None:
        ensure_builtin_stages_registered()
        registered_stages.sort(key=lambda x: STAGES_ORDER.index(x.__name__))
        self.ctx = context
        self.stages = []

    async def initialize(self) -> None:
        for stage_cls in registered_stages:
            stage_instance = stage_cls()
            await stage_instance.initialize(self.ctx)
            self.stages.append(stage_instance)

    async def _process_stages(self, event, from_stage=0):
        """递归实现洋葱模型"""
        for i in range(from_stage, len(self.stages)):
            stage = self.stages[i]
            coroutine = stage.process(event)

            if isinstance(coroutine, AsyncGenerator):
                async for _ in coroutine:
                    if event.is_stopped(): break
                    await self._process_stages(event, i + 1)  # 递归
                    if event.is_stopped(): break
            else:
                await coroutine
                if event.is_stopped(): break

    async def execute(self, event):
        active_event_registry.register(event)
        try:
            await self._process_stages(event)
            if isinstance(event, (WebChatMessageEvent, WecomAIBotMessageEvent)):
                await event.send(None)
        finally:
            event.cleanup_temporary_local_files()
            active_event_registry.unregister(event)
```

### 5.4 `PipelineContext` 管道上下文

```python
@dataclass
class PipelineContext:
    astrbot_config: AstrBotConfig          # AstrBot 配置
    plugin_manager: PluginManager          # 插件管理器
    astrbot_config_id: str                 # 配置 ID
    call_handler = call_handler            # 调用 Handler 工具函数
    call_event_hook = call_event_hook      # 调用事件钩子工具函数
```

### 5.5 `STAGES_ORDER` 执行顺序

```python
# pipeline/stage_order.py
STAGES_ORDER = [
    "WakingCheckStage",
    "WhitelistCheckStage",
    "SessionStatusCheckStage",
    "RateLimitStage",
    "ContentSafetyCheckStage",
    "PreProcessStage",
    "ProcessStage",
    "ResultDecorateStage",
    "RespondStage",
]
```

### 5.6 `bootstrap.py` — Stage 自动加载

```python
_BUILTIN_STAGE_MODULES = (
    "astrbot.core.pipeline.waking_check.stage",
    "astrbot.core.pipeline.whitelist_check.stage",
    "astrbot.core.pipeline.session_status_check.stage",
    "astrbot.core.pipeline.rate_limit_check.stage",
    "astrbot.core.pipeline.content_safety_check.stage",
    "astrbot.core.pipeline.preprocess_stage.stage",
    "astrbot.core.pipeline.process_stage.stage",
    "astrbot.core.pipeline.result_decorate.stage",
    "astrbot.core.pipeline.respond.stage",
)

def ensure_builtin_stages_registered():
    """通过 import_module 触发 @register_stage 装饰器"""
    for module_path in _BUILTIN_STAGE_MODULES:
        import_module(module_path)
```

### 5.7 `call_handler` 与 `call_event_hook`

```python
# pipeline/context_utils.py
async def call_event_hook(event, event_type, *args):
    """遍历注册的 Agent 钩子，按顺序调用"""

async def call_handler(event, handler, **params):
    """调用 Handler 函数（处理流式/非流式结果）"""
```

---

## 六、9 个 Stage 逐个剖析

### 6.1 Stage 1: `WakingCheckStage`（唤醒检查）

**文件**: `pipeline/waking_check/stage.py`

**功能**: 判断消息是否应该被"唤醒"（触发后续处理）。

```python
UNIQUE_SESSION_ID_BUILDERS = {
    "aiocqhttp": lambda e: f"{e.get_sender_id()}_{e.get_group_id()}",
    "slack": lambda e: f"{e.get_sender_id()}_{e.get_group_id()}",
    "dingtalk": lambda e: e.get_sender_id(),
    "qq_official": lambda e: e.get_sender_id(),
    "lark": lambda e: f"{e.get_sender_id()}%{e.get_group_id()}",
    "misskey": lambda e: f"{e.get_session_id()}_{e.get_sender_id()}",
    "matrix": lambda e: f"{e.get_sender_id()}_{e.get_group_id() or e.get_session_id()}",
}
```

**唤醒条件**（按顺序检查）:
1. 唯一会话 ID 构建（`unique_session` 开启时）
2. 忽略机器人自身消息
3. 设置 sender 身份（`admin` / `member`）
4. 检查 `wake_prefix` 前缀
5. 检查 @机器人 / @全体成员 / 引用机器人
6. 私聊自动唤醒（除 `friend_message_needs_wake_prefix` 开启）
7. 遍历所有 Handler 的过滤器链（AND 逻辑）
8. `SessionPluginManager.filter_handlers_by_session()` 过滤
9. 不满足唤醒条件 → `event.stop_event()`

**权限错误处理**:
```python
if permission_not_pass:
    if not permission_filter_raise_error:
        continue
    if self.no_permission_reply:
        await event.send(MessageChain().message(
            f"您(ID: {event.get_sender_id()})的权限不足以使用此指令..."
        ))
    event.stop_event()
```

### 6.2 Stage 2: `WhitelistCheckStage`（白名单检查）

**文件**: `pipeline/whitelist_check/stage.py`

检查 `enable_id_white_list` 与 `id_whitelist` 配置。管理员在群聊/私聊可豁免。

### 6.3 Stage 3: `SessionStatusCheckStage`（会话状态检查）

通过 `SessionServiceManager.is_session_enabled()` 判断当前会话是否禁用了 AI 能力。

### 6.4 Stage 4: `RateLimitStage`（频率限制）

**算法**: Fixed Window（固定窗口）

```python
class RateLimitStage(Stage):
    event_timestamps: defaultdict[str, deque]   # 每个 UMO 的时间戳
    locks: defaultdict[str, Lock]               # 每个 UMO 的锁
    rl_strategy: STALL | DISCARD

    async def process(self, event):
        # 1. 获取当前窗口内的时间戳
        # 2. 移除超过 time 秒的记录
        # 3. 如果计数 >= limit:
        #    - STALL: await asyncio.sleep(wait_time)
        #    - DISCARD: event.stop_event()
```

### 6.5 Stage 5: `ContentSafetyCheckStage`（内容安全检查）

**架构**: 策略模式（Strategy）

```python
class StrategySelector:
    strategies: list[ContentSafetyStrategy]

    def check(self, text: str) -> bool:
        """按顺序执行所有策略，任一不通过则返回 False"""

class InternalKeywordsStrategy(ContentSafetyStrategy):
    """基于内部关键词"""

class BaiduAIPStrategy(ContentSafetyStrategy):
    """基于百度 AI API"""
```

### 6.6 Stage 6: `PreProcessStage`（预处理）

**主要处理**:
- `pre_ack_emoji` 平台特异表情
- `path_mapping` 路径映射
- Record → WAV 格式转换
- Image → JPEG 格式转换
- Reply 链内 Record/Image 同样处理
- STT（语音转文本）调用 `STTProvider.get_text()`，失败重试 5 次
- Record 组件替换为 Plain（转写后的文本）

### 6.7 Stage 7: `ProcessStage`（核心处理）

**文件**: `pipeline/process_stage/stage.py`

包含两个子阶段：

```python
async def process(self, event):
    # 7a. StarRequestSubStage（插件调用）
    if activated_handlers:
        async for resp in self.star_request_sub_stage.process(event):
            if isinstance(resp, ProviderRequest):
                # Handler 的 LLM 请求 → 传给 Agent 子阶段
                event.set_extra("provider_request", resp)
                async for _ in self.agent_sub_stage.process(event):
                    yield
            else:
                yield

    # 7b. AgentRequestSubStage（LLM 调用）
    if 启用 LLM and is_at_or_wake_command and not call_llm:
        if event.get_result() or not event.get_result():
            async for _ in self.agent_sub_stage.process(event):
                yield
```

#### 6.7.1 `StarRequestSubStage`

遍历 `activated_handlers`，调用 `call_handler(event, handler, **params)`。捕获异常并触发 `OnPluginErrorEvent` 钩子。

#### 6.7.2 `AgentRequestSubStage`

根据 `agent_runner_type` 配置选择：
- `"local"` → `InternalAgentSubStage`
- 其他 → `ThirdPartyAgentSubStage`

#### 6.7.3 `InternalAgentSubStage`

这是本地 Agent 的核心实现，主要流程：

```python
async def process(self, event, provider_wake_prefix):
    # 1. 检查消息有效性（空消息、媒体内容、回复等）
    # 2. try_capture_follow_up(event) 跟进机制
    # 3. await call_event_hook(event, OnWaitingLLMRequestEvent)
    # 4. session_lock_manager.acquire_lock(umo) 会话锁
    # 5. build_main_agent(event, plugin_context, config)
    #    └── MainAgentBuildResult(agent_runner, provider_request, provider, reset_coro)
    # 6. 安全检查：blocked API base 拦截
    # 7. call_event_hook(event, OnLLMRequestEvent, req)
    # 8. reset_coro 应用 reset
    # 9. 根据情况选择流式/非流式：
    #    - Live Mode → run_live_agent (带 TTS)
    #    - 流式响应 → run_agent + STREAMING_RESULT
    #    - 其他 → run_agent 异步迭代
    # 10. 保存历史记录 _save_to_history()
    # 11. Metric.upload() 上报
```

**关键配置项**:
- `max_agent_step` (默认 30): 最大 Agent 步骤数
- `tool_call_timeout` (默认 120): 工具调用超时
- `streaming_response`: 是否流式响应
- `tool_schema_mode`: `full` 或 `skills_like`
- `context_limit_reached_strategy`: `llm_compress` 等
- `max_context_length`: 最大上下文长度（-1 表示无限）
- `computer_use_runtime`: `none` / `local` / `sandbox`

#### 6.7.4 Follow-up 跟进机制

```python
# pipeline/process_stage/follow_up.py
class FollowUpCapture:
    """捕获等待 Agent 完成的跟进请求"""

def try_capture_follow_up(event) -> FollowUpCapture | None: ...
def prepare_follow_up_capture(capture) -> tuple[bool, bool]: ...
def finalize_follow_up_capture(capture, activated, consumed_marked) -> None: ...
def register_active_runner(umo, agent_runner) -> None: ...
def unregister_active_runner(umo, agent_runner) -> None: ...
```

### 6.8 Stage 8: `ResultDecorateStage`（结果装饰）

**处理链**:
1. 内容安全复检（可选）
2. `OnDecoratingResultEvent` 钩子
3. `reply_prefix` 添加
4. 分段回复（`segmented_reply`）
5. `reasoning` 内容注入（🤔思考）
6. TTS 转换（概率触发）
7. T2I 转换（文本转图片）
8. 触发转发消息（QQ >1500 字）
9. At 回复 / 引用回复

### 6.9 Stage 9: `RespondStage`（发送消息）

**核心逻辑**:
- 流式结果处理（`STREAMING_RESULT` / `STREAMING_FINISH`）
- 分段回复发送（每个组件间随机间隔）
- 路径映射（Result 也需要）
- 空消息链检查
- `OnAfterMessageSentEvent` 钩子
- `event.clear_result()`

**组件校验**: `_component_validators` 支持 20+ 组件类型校验。

---

## 七、插件系统详解（Star System）

### 7.1 `Star` 基类与自动注册

**核心文件**: `core/star/base.py`, `core/star/star.py`

```python
# core/star/star.py
star_map: dict[str, StarMetadata] = {}       # module_path -> metadata
star_registry: list[StarMetadata] = []        # 有序注册表

@dataclass
class StarMetadata:
    """插件元信息，每个插件的"身份证""""
    star_cls_type: type[Star] | None = None
    module_path: str                           # 模块路径
    name: str = ""
    author: str = ""
    version: str = ""
    activated: bool = False
    reserved: bool = False
    config: dict = field(default_factory=dict)
    star_activated: bool = True
    # ... 更多字段
```

**`Star.__init_subclass__` 自动注册机制**:

```python
class Star(CommandParserMixin, PluginKVStoreMixin):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not star_map.get(cls.__module__):
            metadata = StarMetadata(
                star_cls_type=cls,
                module_path=cls.__module__,
            )
            star_map[cls.__module__] = metadata
            star_registry.append(metadata)
        else:
            star_map[cls.__module__].star_cls_type = cls
            star_map[cls.__module__].module_path = cls.__module__
```

**生命周期方法**:
- `async initialize(self)` — 插件被激活时调用（注册事件、初始化资源）
- `async terminate(self)` — 插件被禁用/重载时调用（释放资源）

**工具方法**:
- `text_to_image(text, return_url)` — 将文本渲染为图片（基于配置的 T2I 模板）
- `html_render(tmpl, data, return_url, options)` — 自定义 HTML 模板渲染为图片

### 7.2 `Context` 插件上下文

```python
# core/star/context.py
class Context:
    star: Star                          # 插件实例
    astrob: AstrBot                     # AstrBot 主对象
    get_config: Callable                # 获取插件专属配置
    register_tool: Callable             # 注册 LLM 工具
    register_event_listener: Callable   # 注册事件监听器
    register_commands: Callable         # 注册命令

    async def register_tool(self, tool: FunctionTool) -> None: ...
    async def register_event_listener(
        self,
        event_type: EventType,
        handler: Callable,
        priority: int = 0,
    ) -> None: ...
    async def register_commands(
        self,
        event_message_type: MessageType,
        command_alias: str,
        description: str,
        priority: int = 0,
    ) -> Callable[[Callable], Callable]: ...
```

### 7.3 Handler 注册机制

#### 7.3.1 `StarHandlerMetadata`

```python
@dataclass
class StarHandlerMetadata(Generic[H]):
    event_type: EventType                  # 事件类型
    handler_full_name: str                 # "{module}_{name}"
    handler_name: str                     # 方法名
    handler_module_path: str              # 模块路径
    handler: H                            # 异步处理函数
    event_filters: list[HandlerFilter]    # 过滤器链（AND 逻辑）
    desc: str = ""
    extras_configs: dict                  # priority 等扩展
    enabled: bool = True

    def __lt__(self, other):
        return self.extras_configs.get("priority", 0) < other.extras_configs.get("priority", 0)
```

#### 7.3.2 `StarHandlerRegistry`

```python
class StarHandlerRegistry(Generic[T]):
    """全局 Handler 注册表，按优先级排序"""
    star_handlers_map: dict[str, StarHandlerMetadata]
    _handlers: list[StarHandlerMetadata]

    def append(self, handler) -> None:
        self.star_handlers_map[handler.handler_full_name] = handler
        self._handlers.append(handler)
        self._handlers.sort(key=lambda h: -h.extras_configs["priority"])

    def get_handlers_by_event_type(
        self, event_type, only_activated=True, plugins_name=None
    ) -> list[StarHandlerMetadata]:
        """按事件类型 + 插件激活状态 + 白名单过滤"""
```

#### 7.3.3 14 种事件类型（EventType）

```python
class EventType(enum.Enum):
    OnAstrBotLoadedEvent = auto()       # AstrBot 加载完成
    OnPlatformLoadedEvent = auto()      # 平台加载完成
    AdapterMessageEvent = auto()        # 收到消息（最常用）
    OnWaitingLLMRequestEvent = auto()   # 等待调用 LLM
    OnLLMRequestEvent = auto()          # LLM 请求（可修改请求）
    OnLLMResponseEvent = auto()         # LLM 响应
    OnAgentBeginEvent = auto()          # Agent 开始
    OnAgentDoneEvent = auto()           # Agent 结束
    OnDecoratingResultEvent = auto()    # 结果装饰
    OnCallingFuncToolEvent = auto()     # 调用函数工具
    OnUsingLLMToolEvent = auto()        # 使用 LLM 工具
    OnLLMToolRespondEvent = auto()      # LLM 工具响应
    OnAfterMessageSentEvent = auto()   # 消息发送完成
    OnPluginErrorEvent = auto()         # 插件错误
    OnPluginLoadedEvent = auto()        # 插件加载完成
    OnPluginUnloadedEvent = auto()     # 插件卸载完成
```

### 7.4 过滤器系统（HandlerFilter）

#### 7.4.1 过滤器基类

```python
class HandlerFilter(abc.ABC):
    @abc.abstractmethod
    def filter(self, event: AstrMessageEvent, cfg: AstrBotConfig) -> bool:
        """返回 True 表示"通过"，False 表示"过滤掉" """
```

#### 7.4.2 5 种内置过滤器

**`CommandFilter`（命令过滤器）**:
```python
class CommandFilter(HandlerFilter):
    command_alias: str                    # 命令别名
    command_aliases: list[str]            # 别名列表（OR）
    ignore_prefix: bool = False           # 忽略前缀匹配
    require_prefix: bool = False          # 必须带前缀
```

**`CommandGroupFilter`（命令分组）**: 多个命令共享同一 handler。

**`RegexFilter`（正则过滤器）**:
```python
class RegexFilter(HandlerFilter):
    regex: str                            # 正则表达式
    use_search: bool = False              # search vs match
```

**`PermissionFilter`（权限过滤器）**:
```python
class PermissionFilter(HandlerFilter):
    permission_type: Literal["admin", "member"]
```

**`EventMessageTypeFilter`（消息类型过滤器）**:
```python
class EventMessageTypeFilter(HandlerFilter):
    event_message_type: MessageType
```

**`PlatformAdapterTypeFilter`（平台适配器过滤器）**: 限制仅在特定平台生效。

**过滤链 AND 逻辑**: 所有过滤器必须全部通过才算通过。

### 7.5 `PluginManager` 插件管理器

**文件**: `core/star/star_manager.py`

**核心流程**:
1. 扫描 `plugins/` 目录
2. `importlib` 动态加载每个插件模块
3. 查找 `Star` 子类并注册
4. 调用 `star.initialize()`
5. 激活的插件的 Handler 加入 `star_handlers_registry`

**依赖管理**: 支持 `requirements.txt` 自动安装。

**插件配置**: 每个插件可配置独立的 `config`，Dashboard 通过 WebUI 管理。

### 7.6 `PluginKVStoreMixin` — 插件 KV 存储

```python
class PluginKVStoreMixin:
    """所有 Star 可继承的 KV 存储能力"""
    async def set(self, key: str, value: Any) -> None: ...
    async def get(self, key: str, default: Any = None) -> Any: ...
    async def delete(self, key: str) -> None: ...
```

### 7.7 `CommandParserMixin` — 命令解析

```python
class CommandParserMixin:
    """命令字符串解析 mixin"""
    @staticmethod
    def parse(command: str) -> list[str]: ...
```

### 7.8 `SessionPluginManager` — 会话级插件管理

```python
class SessionPluginManager:
    filter_handlers_by_session(handlers, event) -> list[StarHandlerMetadata]
```

用于在不同会话中启用/禁用不同插件。

---

## 八、Agent 系统详解

### 8.1 Agent 核心架构

```
┌───────────────────────────────────────────────────────┐
│                     Agent 系统                          │
├───────────────────────────────────────────────────────┤
│                                                       │
│   ┌──────────────┐    ┌──────────────┐                │
│   │  AgentRun    │    │ ToolExecutor │                │
│   │  Context     │◄───►              │                │
│   └──────┬───────┘    └──────┬───────┘                │
│          │                   │                         │
│          ▼                   ▼                         │
│   ┌──────────────┐    ┌──────────────┐                │
│   │   Agent      │    │   ToolSet    │                │
│   │  Message     │    │ (FunctionTool)│               │
│   └──────────────┘    └──────────────┘                │
│                                                       │
│   ┌──────────────────────────────────────┐            │
│   │         AgentRunner (Runners)          │            │
│   │  ├─ ToolLoopAgentRunner (本地)         │            │
│   │  ├─ CozeAgentRunner (扣子)             │            │
│   │  ├─ DashScopeAgentRunner (阿里百炼)    │            │
│   │  ├─ DeerFlowAgentRunner               │            │
│   │  └─ DifyAgentRunner                   │            │
│   └──────────────────────────────────────┘            │
└───────────────────────────────────────────────────────┘
```

### 8.2 `ToolLoopAgentRunner` — ReAct 循环 Agent

**核心文件**: `core/agent/runners/tool_loop_agent_runner.py`

**ReAct 循环流程**:
```
while state != DONE:
    1. 调用 LLM（text_chat / text_chat_stream）
    2. 解析响应:
       - 有 tool_calls → 执行工具 → 回写结果 → 循环
       - 无 tool_calls → 生成最终回复 → 结束
    3. 状态流转: IDLE → THINKING → CALLING_TOOL → THINKING → DONE
```

**关键常量**:
```python
TOOL_RESULT_MAX_ESTIMATED_TOKENS = 27_500      # 工具结果最大估算 tokens
TOOL_RESULT_PREVIEW_MAX_ESTIMATED_TOKENS = 7000  # 预览最大估算 tokens
EMPTY_OUTPUT_RETRY_ATTEMPTS = 3               # 空输出重试次数
MAX_STEPS_REACHED_PROMPT = "Maximum tool call limit reached..."
```

**状态机**:
```python
class AgentState(enum.Enum):
    IDLE = auto()
    THINKING = auto()
    CALLING_TOOL = auto()
    DONE = auto()
    ERROR = auto()
```

**核心 `reset()` 方法**:
```python
async def reset(self, provider, request, run_context,
                tool_executor, agent_hooks, streaming,
                enforce_max_turns=-1,
                llm_compress_instruction=None,
                llm_compress_provider=None,
                truncate_turns=1,
                tool_schema_mode="full",  # "full" | "skills_like"
                fallback_providers=None,
                **kwargs):
```

**Skills-like 工具模式**:
```python
if tool_schema_mode == "skills_like":
    light_set = tool_set.get_light_tool_set()     # 仅保留 name+desc
    param_set = tool_set.get_param_only_tool_set() # 仅保留 name+params
    self.req.func_tool = light_set                # 首轮用轻量 schema
    # 第二轮用 param_set（需重新请求）
```

**重复工具检测**:
```python
REPEATED_TOOL_NOTICE_L1_THRESHOLD = 3   # 3 次 → 温柔提醒
REPEATED_TOOL_NOTICE_L2_THRESHOLD = 4   # 4 次 → 重要提醒
REPEATED_TOOL_NOTICE_L3_THRESHOLD = 5   # 5 次 → 严重警告
```

### 8.3 Agent Message 体系

**文件**: `core/agent/message.py`

```python
class ContentPart(BaseModel):
    type: str

class TextPart(ContentPart):
    type: Literal["text"] = "text"
    text: str

class ImageURLPart(ContentPart):
    type: Literal["image_url"] = "image_url"
    image_url: dict

class ThinkPart(ContentPart):
    type: Literal["think"] = "think"
    think: str
    encrypted: str | None = None

class ToolCall(ContentPart):
    type: Literal["tool_call"] = "tool_call"
    id: str
    function: FunctionBody

class ToolCallMessageSegment(BaseModel):
    role: Literal["tool"]
    tool_call_id: str
    content: str | list[dict]

class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: list[ContentPart] | str | None
```

### 8.4 Tool 工具系统

**文件**: `core/agent/tool.py`

**`ToolSchema`（工具 Schema）**:
```python
@dataclass
class ToolSchema:
    name: str
    description: str
    parameters: dict    # JSON Schema 格式
```

**`FunctionTool`（可调用工具）**:
```python
@dataclass
class FunctionTool(ToolSchema, Generic[TContext]):
    handler: Callable | None                  # 异步处理函数
    handler_module_path: str | None = None
    active: bool = True
    is_background_task: bool = False          # 后台任务模式

    async def call(self, context, **kwargs) -> ToolExecResult: ...
```

**`ToolSet`（工具集合）**:
```python
@dataclass
class ToolSet:
    tools: list[FunctionTool]

    def add_tool(self, tool) -> None: ...     # 按 active 状态智能覆盖
    def remove_tool(self, name) -> None: ...
    def get_light_tool_set(self) -> ToolSet: ...     # 轻量版（仅 name+desc）
    def get_param_only_tool_set(self) -> ToolSet: ... # 仅参数版

    # 多格式导出
    def openai_schema(self) -> list[dict]: ...
    def anthropic_schema(self) -> list[dict]: ...
    def google_schema(self) -> dict: ...
```

### 8.5 Agent Context 系统

**文件**: `core/agent/context/`

```python
class ContextConfig:
    max_context_tokens: int = 0      # 0 表示关闭 token 限制
    enforce_max_turns: int = -1
    truncate_turns: int = 1
    llm_compress_instruction: str | None
    llm_compress_provider: Provider | None

class ContextManager:
    async def add_message(self, msg: Message) -> None: ...
    async def get_context(self) -> list[Message]: ...

class ContextCompressor:
    async def compress(self, messages: list[Message]) -> list[Message]: ...

class Truncator:
    def truncate(self, messages: list[Message], turns: int) -> list[Message]: ...

class TokenCounter:
    async def count_tokens(self, text: str) -> int: ...

class EstimateTokenCounter(TokenCounter):
    """估算 token 数（无需请求 LLM）"""
```

### 8.6 Agent Hooks

**文件**: `core/agent/hooks.py`

```python
class BaseAgentRunHooks:
    async def on_agent_begin(self, run_context, request) -> None: ...
    async def on_agent_done(self, run_context, llm_resp) -> None: ...
    async def on_think_start(self, run_context) -> None: ...
    async def on_think_end(self, run_context) -> None: ...
    async def on_tool_call(self, run_context, tool_call) -> None: ...
    async def on_tool_result(self, run_context, result) -> None: ...
    async def on_stream_chunk(self, run_context, chunk) -> None: ...
```

### 8.7 MCP (Model Context Protocol) 支持

**文件**: `core/agent/mcp_client.py`

```python
class MCPClient:
    """支持 MCP 协议的工具扩展"""
    async def connect(self, server_url: str) -> None: ...
    async def list_tools(self) -> list[ToolSchema]: ...
    async def call_tool(self, name: str, args: dict) -> str | None: ...
```

### 8.8 Agent Response 数据结构

```python
@dataclass
class AgentStats:
    start_time: float
    end_time: float | None = None
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    steps: int = 0

@dataclass
class AgentResponseData:
    messages: list[Message]
    stats: AgentStats
    llm_responses: list[LLMResponse]
```

---

## 九、Provider 体系详解

### 9.1 Provider 类继承关系

```
AbstractProvider (abc.ABC)
├── Provider              # Chat 大模型对话
├── STTProvider           # 语音转文本
├── TTSProvider           # 文本转语音
├── EmbeddingProvider     # 文本向量嵌入
└── RerankProvider        # 重排序

Providers = Union[Provider, STTProvider, TTSProvider, EmbeddingProvider, RerankProvider]
```

### 9.2 `AbstractProvider` 基类

```python
class AbstractProvider(abc.ABC):
    def __init__(self, provider_config: dict) -> None:
        self.model_name = ""
        self.provider_config = provider_config

    def set_model(self, model_name) -> None: ...
    def get_model(self) -> str: ...
    def meta(self) -> ProviderMeta: ...
    async def test(self) -> None: ...
```

### 9.3 `Provider`（Chat Provider）— 最常用

```python
class Provider(AbstractProvider):
    async def text_chat(
        self,
        prompt=None,
        session_id=None,
        image_urls=None,
        audio_urls=None,
        func_tool: ToolSet | None = None,
        contexts: list[Message] | list[dict] | None = None,
        system_prompt: str | None = None,
        tool_calls_result: ToolCallsResult | None = None,
        model: str | None = None,
        extra_user_content_parts: list[ContentPart] | None = None,
        tool_choice: Literal["auto", "required"] = "auto",
        request_max_retries: int | None = None,
        **kwargs,
    ) -> LLMResponse: ...

    async def text_chat_stream(...) -> AsyncGenerator[LLMResponse, None]: ...
```

### 9.4 `STTProvider`（语音转文本）

```python
class STTProvider(AbstractProvider):
    @abc.abstractmethod
    async def get_text(self, audio_url: str) -> str: ...
```

### 9.5 `TTSProvider`（文本转语音）

```python
class TTSProvider(AbstractProvider):
    def support_stream(self) -> bool: return False

    @abc.abstractmethod
    async def get_audio(self, text: str) -> str: ...

    async def get_audio_stream(
        self,
        text_queue: asyncio.Queue,
        audio_queue: asyncio.Queue,
    ) -> None: ...
```

### 9.6 `EmbeddingProvider`（文本向量）

```python
class EmbeddingProvider(AbstractProvider):
    async def get_embedding(self, text: str) -> list[float]: ...
    async def get_embeddings(self, text: list[str]) -> list[list[float]]: ...
    def get_dim(self) -> int: ...

    async def get_embeddings_batch(
        self, texts, batch_size=16, tasks_limit=3,
        max_retries=3, progress_callback=None,
    ) -> list[list[float]]: ...
```

### 9.7 `RerankProvider`（重排序）

```python
class RerankProvider(AbstractProvider):
    async def rerank(
        self, query: str, documents: list[str], top_n: int | None = None
    ) -> list[RerankResult]: ...
```

### 9.8 Provider 注册机制

**文件**: `core/provider/register.py`

```python
provider_registry: list[ProviderMetaData] = []
provider_cls_map: dict[str, ProviderMetaData] = {}

def register_provider_adapter(
    provider_type_name: str,
    desc: str,
    provider_type: ProviderType = ProviderType.CHAT_COMPLETION,
    default_config_tmpl: dict | None = None,
    provider_display_name: str | None = None,
):
    """装饰器，注册一个 Provider 适配器"""
    def decorator(cls):
        pm = ProviderMetaData(
            id="default",
            model=None,
            type=provider_type_name,
            desc=desc,
            provider_type=provider_type,
            cls_type=cls,
            default_config_tmpl=default_config_tmpl,
            provider_display_name=provider_display_name,
        )
        provider_registry.append(pm)
        provider_cls_map[provider_type_name] = pm
        return cls
    return decorator
```

### 9.9 `ProviderMetaData` 注册元数据

```python
@dataclass
class ProviderMetaData(ProviderMeta):
    desc: str = ""
    cls_type: Any = None
    default_config_tmpl: dict | None = None
    provider_display_name: str | None = None
```

### 9.10 `ProviderRequest` 请求封装

**文件**: `core/provider/entities.py`

```python
@dataclass
class ProviderRequest:
    prompt: str | None = None
    session_id: str | None = ""
    image_urls: list[str] = field(default_factory=list)
    audio_urls: list[str] = field(default_factory=list)
    extra_user_content_parts: list[ContentPart] = field(default_factory=list)
    func_tool: ToolSet | None = None
    contexts: list[dict] = field(default_factory=list)
    system_prompt: str = ""
    conversation: Conversation | None = None
    tool_calls_result: list[ToolCallsResult] | None = None
    model: str | None = None

    async def assemble_context(self) -> dict:
        """将请求包装成统一消息格式（支持多模态）"""
```

### 9.11 `LLMResponse` 响应封装

```python
@dataclass
class LLMResponse:
    role: str
    result_chain: MessageChain | None = None
    tools_call_args: list[dict] = field(default_factory=list)
    tools_call_name: list[str] = field(default_factory=list)
    tools_call_ids: list[str] = field(default_factory=list)
    reasoning_content: str | None = None
    reasoning_signature: str | None = None
    raw_completion: (ChatCompletion | GenerateContentResponse | AnthropicMessage | None) = None
    is_chunk: bool = False
    id: str | None = None
    usage: TokenUsage | None = None
```

### 9.12 40+ 内置 Provider 适配器

**Chat Providers**:
- `openai_source.py`, `azure_source.py`, `anthropic_source.py`, `gemini_source.py`
- `zhipu_source.py`, `dashscope_source.py`, `volcengine_source.py`, `xai_source.py`
- `kimi_code_source.py`, `longcat_source.py`, `groq_source.py`, `openrouter_source.py`
- `ollama_source.py`, `oai_aihubmix_source.py`, `mimo_source.py`, `xiaomi_source.py`
- `gsv_selfhosted_source.py`, `gitee_ai_source.py`

**TTS Providers**:
- `edge_tts_source.py`, `azure_tts_source.py`, `openai_tts_api_source.py`
- `elevenlabs_tts_source.py`, `fishaudio_tts_api_source.py`, `dashscope_tts.py`
- `volcengine_tts.py`, `genie_tts.py`, `mimo_tts_api_source.py`, `gsvi_tts_source.py`, `minimax_tts_api_source.py`

**STT Providers**:
- `whisper_api_source.py`, `whisper_selfhosted_source.py`
- `sensevoice_selfhosted_source.py`, `mimo_stt_api_source.py`, `xinference_stt_provider.py`

**Embedding Providers**:
- `openai_embedding_source.py`, `ollama_embedding_source.py`
- `gemini_embedding_source.py`, `nvidia_embedding_source.py`

**Rerank Providers**:
- `bailian_rerank_source.py`, `nvidia_rerank_source.py`, `tei_rerank_source.py`
- `vllm_rerank_source.py`, `xinference_rerank_source.py`

### 9.13 `ProviderManager`

**文件**: `core/provider/manager.py`

```python
class ProviderManager:
    """管理所有 Provider 实例"""
    def __init__(self, providers_config: list[dict]) -> None: ...
    async def initialize(self) -> None: ...
    def get_provider(self, provider_id: str) -> Provider | None: ...
    def get_providers_by_type(self, provider_type: ProviderType) -> list[Providers]: ...
```

---

## 十、事件总线与平台适配

### 10.1 `EventBus` 事件总线

**文件**: `core/event_bus.py`

```python
class EventBus:
    def __init__(self, event_queue, pipeline_scheduler_mapping, astrbot_config_mgr):
        self.event_queue = event_queue                       # asyncio.Queue
        self.pipeline_scheduler_mapping = pipeline_scheduler_mapping  # conf_id → scheduler
        self._pending_tasks: set[asyncio.Task] = set()       # 防 GC

    async def dispatch(self) -> None:
        while True:
            event = await self.event_queue.get()
            conf_info = self.astrbot_config_mgr.get_conf_info(event.unified_msg_origin)
            scheduler = self.pipeline_scheduler_mapping.get(conf_id)
            task = asyncio.create_task(scheduler.execute(event))
            self._pending_tasks.add(task)
            task.add_done_callback(self._on_task_done)
```

### 10.2 `Platform` 平台基类

**文件**: `core/platform/platform.py`

```python
class Platform(abc.ABC):
    def __init__(self, platform_config: dict):
        self.platform_config = platform_config
        self.platform_id = platform_config.get("id", "unknown")
        self.platform_name = platform_config.get("name", "Unknown")

    @abc.abstractmethod
    async def connect(self) -> None: ...

    @abc.abstractmethod
    async def disconnect(self) -> None: ...

    @abc.abstractmethod
    async def send_message(self, event: AstrMessageEvent, message: MessageChain) -> None: ...

    @abc.abstractmethod
    async def handle_event(self, event: AstrMessageEvent) -> None:
        """将事件推送到 EventBus"""
        await self.event_queue.put(event)
```

### 10.3 `AstrMessageEvent` 消息事件基类

**文件**: `core/platform/astr_message_event.py`

```python
class AstrMessageEvent:
    # 唯一消息来源标识
    unified_msg_origin: str

    # 核心方法
    async def send(self, result: str | MessageChain | None = None) -> None: ...
    async def stop_propagation(self) -> None: ...
    def is_stopped(self) -> bool: ...

    # 获取信息
    def get_sender_id(self) -> str: ...
    def get_sender_name(self) -> str | None: ...
    def get_group_id(self) -> str | None: ...
    def get_session_id(self) -> str: ...
    def get_platform_id(self) -> str: ...
    def get_platform_name(self) -> str: ...
    def get_message(self) -> str: ...
    def get_message_id(self) -> str: ...
    def get_message_type(self) -> MessageType: ...
    def is_admin(self) -> bool: ...
    def is_group(self) -> bool: ...
    def is_private(self) -> bool: ...
    def is_wake_up(self) -> bool: ...
    def get_result(self) -> MessageChain | None: ...

    # 结果设置
    def set_result(self, result: str | MessageChain) -> None: ...
    def stop_event(self) -> None: ...

    # 组件处理
    def get_message_components(self) -> list[Component]: ...
    def get_record_urls(self) -> list[str]: ...
    def get_image_urls(self) -> list[str]: ...
```

### 10.4 支持的平台（30+）

**即时通讯**:
- QQ (aiocqhttp)
- QQ 官方 (qqofficial, qqofficial_webhook)
- 微信 (weixin_oc, weixin_official_account)
- 企业微信 (wecom, wecom_ai_bot)
- Telegram, Discord, Kook, Slack, LINE
- 钉钉 (dingtalk), 飞书 (lark)
- Mattermost, Misskey, Matrix
- Satori (通用协议)

**Web 交互**:
- WebChat (网页聊天)
- Wecom AI Bot (企业微信 AI Bot)

**平台管理器**: `PlatformManager` 负责加载所有平台适配器。

### 10.5 平台注册装饰器

```python
# core/platform/register.py
def register_platform_adapter(platform_name: str, desc: str, default_config_tmpl: dict = None):
    """装饰器，注册一个平台适配器"""
    def decorator(cls):
        platform_registry.append(PlatformMetaData(
            type=platform_name, cls_type=cls, desc=desc,
            default_config_tmpl=default_config_tmpl,
        ))
        return cls
    return decorator
```

---

## 十一、消息体系

### 11.1 消息组件（Components）

**文件**: `core/message/components.py`

```python
class Component(abc.ABC):
    @abc.abstractmethod
    def to_dict(self) -> dict: ...

class Plain(Component):
    """纯文本"""
    text: str

class At(Component):
    """@某人"""
    target: str
    display: str = ""
    rank: Literal["admin", "member"] = "member"

class AtAll(Component):
    """@全体成员"""

class Image(Component):
    """图片"""
    url: str | None = None
    path: str | None = None
    data: bytes | None = None

class Record(Component):
    """语音"""
    url: str | None = None
    path: str | None = None

class Video(Component):
    """视频"""

class Reply(Component):
    """回复消息"""
    id: str
    message: str | None = None

class Node(Component):
    """节点消息（用于合并转发）"""

class Json(Component):
    """JSON 消息"""
    data: dict

class Face(Component):
    """表情"""
    id: str

class Markdown(Component):
    """Markdown"""
    content: str

class CQCode(Component):
    """CQ 码（QQ 专用）"""
```

### 11.2 `MessageChain` 消息链

```python
class MessageChain:
    chain: list[Component]

    @classmethod
    def create(cls) -> MessageChain: ...

    def append(self, comp: Component) -> MessageChain: ...
    def message(self, text: str) -> MessageChain: ...   # 快捷添加 Plain
    def at(self, target: str, display="") -> MessageChain: ...
    def at_all(self) -> MessageChain: ...
    def image(self, url) -> MessageChain: ...
    def record(self, url) -> MessageChain: ...
    def reply(self, id) -> MessageChain: ...
    def markdown(self, content) -> MessageChain: ...
    def json(self, data) -> MessageChain: ...

    def get_plain_text(self) -> str: ...
    def to_dict(self) -> dict: ...
```

### 11.3 `MessageEventResult`

```python
class MessageEventResult:
    """Stage 返回的结果容器"""
    STREAMING_RESULT = "streaming_result"
    STREAMING_FINISH = "streaming_finish"
```

---

## 十二、数据库系统

### 12.1 SQLite 数据库

**文件**: `core/db/sqlite.py`

```python
class AstrBotDatabase:
    def __init__(self, db_path: str) -> None: ...
    async def initialize(self) -> None: ...

    # 对话管理
    async def get_conversations(self, cid: str) -> list[Conversation]: ...
    async def add_conversation(self, conv: Conversation) -> None: ...
    async def update_conversation(self, conv: Conversation) -> None: ...
    async def delete_conversation(self, cid: str) -> None: ...

    # 会话管理
    async def get_sessions(self) -> list[Session]: ...
    async def toggle_session(self, session_id: str, enabled: bool) -> None: ...

    # 配置存储
    async def get_shared_preferences(self) -> list[SharedPreference]: ...
    async def set_shared_preference(self, key: str, value: str) -> None: ...

    # WebChat
    async def get_webchat_sessions(self) -> list[WebChatSession]: ...

    # Token 用量
    async def add_token_usage(self, usage: TokenUsageRecord) -> None: ...
    async def get_token_usage(self, start, end) -> list[TokenUsageRecord]: ...
```

### 12.2 数据库迁移

**目录**: `core/db/migration/`

```
migra_3_to_4.py           # v3 → v4 升级
migra_45_to_46.py         # v4.5 → v4.6 升级
migra_token_usage.py      # Token 用量表
migra_webchat_session.py  # WebChat 会话表
shared_preferences_v3.py  # 共享偏好设置
sqlite_v3.py              # SQLite v3 建表
helper.py                # 迁移辅助函数
```

### 12.3 向量数据库（FAISS）

**目录**: `core/db/vec_db/faiss_impl/`

```python
class FaissVecDB:
    """基于 FAISS 的向量数据库实现"""
    async def add_documents(self, documents) -> None: ...
    async def search(self, query_embedding, top_k) -> list[SearchResult]: ...
    async def delete(self, doc_ids) -> None: ...
```

### 12.4 持久化对象（PO）

**文件**: `core/db/po.py`

```python
@dataclass
class Conversation:
    cid: str
    message_id: str
    role: str
    content: str
    created_at: float
    token_usage: int = 0

@dataclass
class Session:
    session_id: str
    enabled: bool
    last_active: float

@dataclass
class SharedPreference:
    key: str
    value: str

@dataclass
class WebChatSession:
    session_id: str
    user_id: str
    created_at: float

@dataclass
class TokenUsageRecord:
    id: int
    provider_id: str
    model: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    created_at: float
```

---

## 十三、Dashboard 管理后台

### 13.1 架构

```
┌───────────────────────────────────────────┐
│            Dashboard (FastAPI)             │
├───────────────────────────────────────────┤
│                                           │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Auth    │  │   API    │  │  Static   │ │
│  │ Router  │  │  Routes  │  │  Files    │ │
│  └─────────┘  └──────────┘  └──────────┘ │
│                                           │
│  ┌──────────────────────────────────────┐ │
│  │          Service 层                    │ │
│  │  (PluginService, ProviderService, ...) │ │
│  └──────────────────────────────────────┘ │
│                                           │
│  ┌──────────────────────────────────────┐ │
│  │          WebSocket (实时通信)          │ │
│  └──────────────────────────────────────┘ │
└───────────────────────────────────────────┘
```

### 13.2 核心文件

- `dashboard/server.py` — FastAPI 应用主入口
- `dashboard/routers/` — 路由层
- `dashboard/services/` — 服务层
- `dashboard/auth/` — 认证系统

### 13.3 主要 API 路由

- `/api/auth/login` — 登录
- `/api/plugins/list` — 插件列表
- `/api/plugins/install` — 安装插件
- `/api/plugins/uninstall` — 卸载插件
- `/api/providers/list` — Provider 列表
- `/api/providers/test` — Provider 测试
- `/api/config/get` — 获取配置
- `/api/config/update` — 更新配置
- `/api/logs/stream` — 日志流

### 13.4 WebSocket 实时通信

- 日志实时推送
- 插件状态变化
- 配置变化广播

---

## 十四、配置系统

### 14.1 `AstrBotConfig`

**文件**: `core/config/astrbot_config.py`

```python
class AstrBotConfig:
    def __init__(self, config_path: str):
        self._config_path = config_path
        self._config = {}
        self._load_config()

    def get(self, key: str, default=None): ...
    def set(self, key: str, value: Any) -> None: ...
    async def save(self) -> None: ...
    def to_dict(self) -> dict: ...
```

### 14.2 `AstrBotConfigManager`

```python
class AstrBotConfigManager:
    """管理多配置实例（多配置文件场景）"""
    def get_conf_info(self, unified_msg_origin: str) -> dict: ...
    def get_conf(self, conf_id: str) -> AstrBotConfig | None: ...
```

### 14.3 默认配置

**文件**: `core/config/default.py`

包括 40+ 项默认配置：
- `prefix`、`wake_prefix`、`unified_msg_origin`
- `enable_llm`、`provider_config`、`provider_settings`
- `streaming_response`、`tool_call_timeout`、`max_agent_step`
- `rate_limit`、`content_safety`、`enable_id_white_list`
- `segemented_reply`、`reply_prefix`、`pre_ack_emoji`
- `tts`、`stt`、`t2i`、`computer_use`
- `knowledge_base`、`sub_agent`、`handoff`
- 等等...

---

## 十五、工具系统（内置工具）

### 15.1 工具注册表

**文件**: `core/tools/registry.py`

```python
tools_registry: dict[str, type[FunctionTool]] = {}

def register_tool(cls):
    tools_registry[cls.__name__] = cls
    return cls
```

### 15.2 工具分类

**`message_tools.py`**: 消息相关工具
- `send_message_tool` — 发送消息
- `get_session_info_tool` — 获取会话信息

**`web_search_tools.py`**: 搜索工具
- `web_search_tool` — 网络搜索
- `web_fetch_tool` — 网页抓取

**`knowledge_base_tools.py`**: 知识库工具
- `kb_search_tool` — 知识库搜索

**`cron_tools.py`**: 定时任务工具
- `cron_create_tool` — 创建定时任务
- `cron_list_tool` — 列出定时任务
- `cron_delete_tool` — 删除定时任务

**`computer_tools/`**: 计算机使用工具
- `cua.py` — 计算机使用（鼠标键盘）
- `fs.py` — 文件系统操作
- `python.py` — Python 代码执行
- `shell.py` — Shell 命令执行
- `browser.py` — 浏览器操作

### 15.3 MCP 扩展机制

```python
class MCPClient:
    async def connect(self, url: str) -> None: ...
    async def disconnect(self) -> None: ...
    async def list_tools(self) -> list[ToolSchema]: ...
    async def call_tool(self, name: str, args: dict) -> CallToolResult: ...
```

---

## 十六、知识库系统

### 16.1 架构

```
┌─────────────────────────────────────────────┐
│               知识库系统                      │
├─────────────────────────────────────────────┤
│                                              │
│  ┌────────────┐  ┌────────────┐             │
│  │  Parser     │  │  Chunking  │             │
│  │  (解析器)   │  │  (分块器)  │             │
│  └──────┬─────┘  └──────┬─────┘             │
│         │                │                   │
│         ▼                ▼                   │
│  ┌────────────────────────────┐             │
│  │        Embedding 向量化      │             │
│  └──────────────┬─────────────┘             │
│                 │                            │
│                 ▼                            │
│  ┌────────────────────────────┐             │
│  │     Vector DB (FAISS)       │             │
│  └──────────────┬─────────────┘             │
│                 │                            │
│                 ▼                            │
│  ┌────────────────────────────┐             │
│  │     Retrieval (检索+重排)    │             │
│  └────────────────────────────┘             │
└─────────────────────────────────────────────┘
```

### 16.2 文档解析器

**目录**: `knowledge_base/parsers/`

```python
class BaseParser(abc.ABC):
    async def parse(self, source: str) -> list[Document]: ...

class PDFParser(BaseParser): ...
class EPUBParser(BaseParser): ...
class MarkItDownParser(BaseParser): ...  # 通用
class TextParser(BaseParser): ...
class URLParser(BaseParser): ...         # 网页
```

### 16.3 分块策略

**目录**: `knowledge_base/chunking/`

```python
class BaseChunking(abc.ABC):
    def chunk(self, content: str) -> list[str]: ...

class FixedSizeChunking(BaseChunking): ...    # 固定大小
class MarkdownChunking(BaseChunking): ...    # Markdown 感知
class RecursiveChunking(BaseChunking): ...   # 递归分块
```

### 16.4 检索系统

**目录**: `knowledge_base/retrieval/`

```python
class KBRetrievalManager:
    async def retrieve(self, query, kb_id, top_k) -> list[RetrievedChunk]: ...
    async def rerank(self, query, chunks, top_n) -> list[RerankResult]: ...
```

**高级特性**:
- 混合检索（稀疏 + 稠密）
- 重排序（Rerank）
- `rank_fusion.py` — 多方法融合排序
- `sparse_retriever.py` — BM25 稀疏检索
- `tokenizer.py` — 中文分词

---

## 十七、其他子系统

### 17.1 子 Agent 编排

**文件**: `core/subagent_orchestrator.py`

```python
class SubAgentOrchestrator:
    """子 Agent 编排器，用于多 Agent 协作"""
    async def orchestrate(self, main_agent, sub_agents, task) -> None: ...
```

### 17.2 Agent Handoff

**文件**: `core/agent/handoff.py`

```python
class HandoffManager:
    """Agent 任务切换/交接"""
    async def handoff(self, from_agent, to_agent, context) -> None: ...
```

### 17.3 Computer Use Runtime

**目录**: `core/computer/booters/`

支持的运行时：
- `local.py` — 本地计算机
- `sandbox.py` — 沙箱环境
- `cua.py` — Computer Use Agent
- `boxlite.py` — BoxLite 容器
- `shipyard.py` / `shipyard_neo.py` — Shipyard 运行时
- `bay_manager.py` — Bay 管理器
- `shell_background.py` — Shell 后台任务

### 17.4 备份系统

**目录**: `core/backup/`

```python
class BackupExporter:
    async def export(self, data, output_path) -> None: ...

class BackupImporter:
    async def import(self, input_path) -> dict: ...
```

### 17.5 技能系统（Skills）

**文件**: `core/skills/skill_manager.py`

```python
class SkillManager:
    """技能管理，支持 Neo 风格的技能同步"""
    async def load_skills(self) -> None: ...
    async def execute_skill(self, name: str, args: dict) -> Any: ...
```

---

## 十八、核心文件索引

### 18.1 入口与启动
- `core/__init__.py` — 包入口
- `core/astrbot_config_mgr.py` — 配置管理器
- `core/initial_loader.py` — 初始化加载器
- `core/core_lifecycle.py` — 核心生命周期

### 18.2 主 Agent 构建
- `core/astr_main_agent.py` — 主 Agent 构建逻辑
- `core/astr_agent_context.py` — Agent 上下文
- `core/astr_agent_hooks.py` — Agent 钩子
- `core/astr_agent_run_util.py` — Agent 运行工具
- `core/astr_agent_tool_exec.py` — Agent 工具执行

### 18.3 会话与历史
- `core/conversation_mgr.py` — 对话历史管理
- `core/platform_message_history_mgr.py` — 平台消息历史
- `core/persona_mgr.py` — Persona 管理

### 18.4 工具与 Hook 入口
- `core/astr_main_agent_resources.py` — 主 Agent 资源
- `core/tools/registry.py` — 工具注册表

### 18.5 UMO（统一消息对象）
- `core/umo_alias.py` — UMO 别名映射
- `core/umop_config_router.py` — UMO 配置路由

### 18.6 其他
- `core/desktop_runtime.py` — 桌面运行时
- `core/file_token_service.py` — 文件 Token 服务
- `core/exceptions.py` — 异常定义
- `core/sentinels.py` — 哨兵值
- `core/log.py` — 日志系统
- `core/updator.py` — 更新检查

---

## 十九、数据流总图

```
┌────────────────────────────────────────────────────────────────────┐
│                        用户消息生命周期                              │
└────────────────────────────────────────────────────────────────────┘

  用户发送消息
       │
       ▼
  ┌──────────┐    推送     ┌──────────┐    创建任务    ┌──────────────┐
  │  Platform │─────────► │ EventBus │─────────────► │ Scheduler    │
  │ (适配器)  │            │ (事件总线)│              │ (调度器)     │
  └──────────┘            └──────────┘              └──────┬───────┘
                                                           │
                                                           ▼
                                              ┌────────────────────┐
                                              │  洋葱模型递归执行  │
                                              │  _process_stages() │
                                              └──────────┬─────────┘
                                                         │
    ┌────────────────────────────────────────────────────┼──────────┐
    │                                                    │          │
    ▼                                                    ▼          ▼
 WakingCheck                                       后续 Stages...  └──► Respond
 (唤醒检查)                                          │                    (发送)
    │                                                │                  ▲
    ▼                                                ▼                  │
 WhitelistCheck                                 PreProcess          ResultDecorate
 (白名单检查)                                   (预处理)             (结果装饰)
    │                                                │                  ▲
    ▼                                                ▼                  │
 SessionStatusCheck                          ProcessStage             │
 (会话状态)                                   │    │                    │
    │                                        │    │                    │
    ▼                                        │    ├──► StarRequest    │
 RateLimit                                   │    │    (插件调用)      │
 (频率限制)                                   │    │                    │
    │                                        │    ├──► AgentRequest   │
    ▼                                        │    │    (LLM 调用)     │
 ContentSafetyCheck                          │    │                    │
 (内容安全)                                    │    ▼                    │
                                             │  LLM Provider           │
                                             │  (text_chat/stream)    │
                                             │    │                    │
                                             │    ▼                    │
                                             │  ToolLoopAgentRunner    │
                                             │  ┌─────────────────┐    │
                                             │  │ ReAct 循环      │    │
                                             │  │ 1. 调用 LLM     │    │
                                             │  │ 2. 解析 tool_calls│  │
                                             │  │ 3. 执行工具     │    │
                                             │  │ 4. 回写结果     │    │
                                             │  │ 5. 循环/结束    │    │
                                             │  └─────────────────┘    │
                                             └──────────────────────────┘
```

---

## 二十、AstrBot 插件开发指南（速查）

### 20.1 最小插件模板

```python
from astrbot.api.star import register, Star
from astrbot.api.event import filter

@register(
    name="my_demo",
    author="YourName",
    version="1.0.0",
    description="我的第一个 AstrBot 插件",
)
class MyDemoPlugin(Star):
    def __init__(self, context):
        super().__init__(context)

    @filter.command("hello")
    async def hello_command(self, event):
        await event.reply("Hello, AstrBot!")
```

### 20.2 注册 LLM 工具

```python
from astrbot.api.star import Star, Context
from astrbot.api.event import on_message
from astrbot.core.agent.tool import FunctionTool

class MyPlugin(Star):
    async def register_tools(self):
        tool = FunctionTool(
            name="get_weather",
            description="获取指定城市的天气",
            parameters={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称",
                    }
                },
                "required": ["city"],
            },
            handler=self.get_weather,
        )
        await self.context.register_tool(tool)

    async def get_weather(self, city: str) -> str:
        return f"{city}今天天气晴朗，温度 25°C"
```

### 20.3 注册事件监听

```python
class MyPlugin(Star):
    async def on_load(self):
        await self.context.register_event_listener(
            event_type=EventType.OnLLMRequestEvent,
            handler=self.on_llm_request,
        )

    async def on_llm_request(self, event, request):
        # 修改请求
        request.system_prompt = "你是一个友好的助手"
```

### 20.4 使用插件 KV 存储

```python
class MyPlugin(Star, PluginKVStoreMixin):
    async def set_data(self, key, value):
        await self.kv_set(key, value)

    async def get_data(self, key):
        return await self.kv_get(key)
```

---

## 二十一、附录：Provider 类型列举

### 21.1 `ProviderType` 枚举

```python
class ProviderType(enum.Enum):
    CHAT_COMPLETION = "chat_completion"
    SPEECH_TO_TEXT = "speech_to_text"
    TEXT_TO_SPEECH = "text_to_speech"
    EMBEDDING = "embedding"
    RERANK = "rerank"
```

### 21.2 常用 Provider 速查表

| Provider 类型 | 类名 | 文件 | 说明 |
|--------------|------|------|------|
| `openai` | `OpenAISource` | `openai_source.py` | OpenAI 兼容 |
| `azure` | `AzureSource` | `azure_source.py` | Azure OpenAI |
| `anthropic` | `AnthropicSource` | `anthropic_source.py` | Claude 系列 |
| `gemini` | `GeminiSource` | `gemini_source.py` | Google Gemini |
| `zhipu` | `ZhipuSource` | `zhipu_source.py` | 智谱 AI |
| `dashscope` | `DashScopeSource` | `dashscope_source.py` | 阿里百炼 |
| `volcengine` | `VolcengineSource` | `volcengine_source.py` | 火山引擎 |
| `xai` | `XAISource` | `xai_source.py` | X.AI |
| `ollama` | `OllamaSource` | `ollama_source.py` | Ollama 本地 |
| `groq` | `GroqSource` | `groq_source.py` | Groq |
| `openrouter` | `OpenRouterSource` | `openrouter_source.py` | OpenRouter |
| `kimi_code` | `KimiCodeSource` | `kimi_code_source.py` | Kimi Code |
| `longcat` | `LongCatSource` | `longcat_source.py` | LongCat |
| `xiaomi` | `XiaomiSource` | `xiaomi_source.py` | 小米 AI |

### 21.3 Provider 配置示例

```json
{
  "provider_config": [
    {
      "id": "my_provider",
      "type": "openai",
      "enable": true,
      "key": ["sk-xxx"],
      "model": "gpt-4o",
      "api_base": "https://api.openai.com/v1",
      "max_context_tokens": 128000
    }
  ]
}
```

---

## 二十二、总结

AstrBot 是一个**高度模块化、插件化**的 AI 聊天机器人框架，其核心设计哲学包括：

1. **洋葱模型管道** — 9 个 Stage 形成可插拔的消息处理链，每个 Stage 都可以独立开发、替换、扩展。

2. **插件优先架构** — `Star` 基类通过 `__init_subclass__` 自动注册，开发者只需继承即可接入全部能力。

3. **多 Provider 抽象** — 5 种 Provider 基类覆盖 Chat/STT/TTS/Embedding/Rerank，40+ 适配器实现主流 AI 服务。

4. **ReAct Agent 循环** — `ToolLoopAgentRunner` 实现完整的工具调用循环，支持 Skills-like 双阶段工具模式、重复工具检测、Token 压缩、Follow-up 跟进。

5. **多平台适配** — 30+ 平台适配器覆盖主流 IM 渠道，通过 `EventBus` 解耦平台与业务逻辑。

6. **知识库/RAG** — 完整的文档解析→分块→向量化→检索→重排序流水线。

7. **Dashboard 管理后台** — FastAPI + WebSocket 提供实时可视化管理。

整个包的代码组织清晰，职责分层明确，是学习 AI Agent 框架与聊天机器人开发的优秀参考。

---

**（文档结束）**


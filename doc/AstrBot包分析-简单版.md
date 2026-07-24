# AstrBot v4.26.7 包完整架构分析

## 一、顶层模块总览

```
astrbot/                              # 根包 (版本 4.26.7)
├── __init__.py                       # 仅定义 __version__ = "4.26.7" 和 logger
│
├── api/                              # 🌐 公共 API 层 (给插件开发者用)
│   ├── __init__.py                   # 导出: logger, sp, AstrBotConfig, Star, agent, llm_tool, html_renderer 等
│   ├── all.py                        # 聚合所有 API
│   ├── message_components.py         # 消息组件 (MessageChain, At, Node 等)
│   ├── web.py                        # Web API 相关
│   ├── event/                        # 事件相关 API
│   ├── platform/                     # 平台相关 API
│   ├── provider/                     # Provider 相关 API
│   ├── star/                         # 插件(Star)相关 API
│   └── util/                         # 工具类 API
│
├── core/                             # ⚙️ 核心引擎层 (内部实现)
│   ├── __init__.py                   # 初始化全局单例: astrbot_config, html_renderer, logger, db_helper, sp, file_token_service, pip_installer
│   │
│   ├── config/                       # 📝 配置系统
│   │   ├── astrbot_config.py         # AstrBotConfig 主配置类
│   │   ├── default.py                # 默认配置常量 + DB_PATH, VERSION
│   │   ├── i18n_utils.py             # 国际化工具
│   │   └── __init__.py
│   │
│   ├── db/                           # 💾 数据库层
│   │   ├── sqlite.py                 # SQLite 实现
│   │   ├── po.py                     # 持久化对象
│   │   ├── migration/                # 数据库迁移脚本
│   │   └── vec_db/                   # 向量数据库 (faiss 实现)
│   │
│   ├── platform/                     # 📱 平台适配层 (20+ 平台)
│   │   ├── platform.py               # Platform 抽象基类
│   │   ├── astr_message_event.py     # AstrMessageEvent 事件类
│   │   ├── astrbot_message.py        # AstrBotMessage 消息模型
│   │   ├── platform_metadata.py      # PlatformMetadata 平台元数据
│   │   ├── manager.py                # PlatformManager 平台管理器
│   │   ├── register.py               # 平台适配器注册装饰器
│   │   ├── webhook_server.py         # Webhook 服务器
│   │   └── sources/                  # 各平台具体实现:
│   │       ├── aiocqhttp/            # QQ OneBot
│   │       ├── dingtalk/             # 钉钉
│   │       ├── discord/              # Discord
│   │       ├── kook/                 # Kook
│   │       ├── lark/                 # 飞书
│   │       ├── telegram/             # Telegram
│   │       ├── webchat/              # Web 聊天
│   │       ├── wecom/                # 企业微信
│   │       ├── weixin_oc/            # 微信公众号
│   │       ├── ... 等
│   │
│   ├── provider/                     # 🤖 LLM Provider 层
│   │   ├── provider.py               # Provider/STTProvider/TTSProvider/EmbeddingProvider/RerankProvider 抽象基类
│   │   ├── manager.py                # ProviderManager 管理器
│   │   ├── register.py               # Provider 注册装饰器 + llm_tools (FuncCall)
│   │   ├── entities.py               # LLMResponse, ProviderRequest, ToolCallsResult 等实体
│   │   ├── func_tool_manager.py      # FunctionTool 管理器
│   │   ├── modalities.py             # 模态处理
│   │   └── sources/                  # 各 Provider 具体实现 (50+ 个):
│   │       ├── openai_source.py      # OpenAI
│   │       ├── zhipu_source.py       # 智谱
│   │       ├── dashscope_tts.py      # 阿里 DashScope TTS
│   │       ├── ... 等
│   │
│   ├── star/                         # 🔌 插件(Star)系统
│   │   ├── base.py                   # Star 插件基类 (所有插件继承此)
│   │   ├── context.py                # Context 上下文 (插件与框架交互的唯一入口)
│   │   ├── star.py                   # StarMetadata 数据类 + star_map/star_registry 全局注册表
│   │   ├── star_manager.py           # PluginManager: 发现→加载→热重载→卸载生命周期
│   │   ├── star_handler.py           # StarHandlerMetadata + StarHandlerRegistry + EventType
│   │   ├── star_tools.py             # StarTools 工具集
│   │   ├── register/                 # 注册装饰器:
│   │   │   ├── __init__.py           # 导出所有装饰器 (register_command, register_agent, register_llm_tool 等)
│   │   │   ├── star.py               # register_star (已废弃)
│   │   │   └── star_handler.py       # 各种 handler 注册装饰器实现
│   │   ├── filter/                   # 事件过滤器:
│   │   │   ├── command.py            # 命令过滤器
│   │   │   ├── regex.py              # 正则过滤器
│   │   │   ├── permission.py         # 权限过滤器
│   │   │   ├── custom_filter.py      # 自定义过滤器
│   │   │   └── ...
│   │   ├── config.py                 # 插件配置
│   │   ├── command_management.py     # 命令管理
│   │   ├── updator.py                # 插件更新器
│   │   └── session_llm_manager.py    # 会话 LLM 管理器
│   │
│   ├── pipeline/                     # 🔄 消息处理管道 (核心流水线)
│   │   ├── stage.py                  # Stage 抽象基类 + registered_stages 注册表
│   │   ├── stage_order.py            # STAGES_ORDER 执行顺序定义
│   │   ├── scheduler.py             # PipelineScheduler 管道调度器 (洋葱模型)
│   │   ├── bootstrap.py              # 内置 Stage 自动注册
│   │   ├── context.py                # PipelineContext 管道上下文
│   │   └── (9 个内置 Stage):
│   │       ├── waking_check/         # ① 唤醒检查
│   │       ├── whitelist_check/      # ② 白名单检查
│   │       ├── session_status_check/ # ③ 会话状态检查
│   │       ├── rate_limit_check/     # ④ 频率限制
│   │       ├── content_safety_check/ # ⑤ 内容安全
│   │       ├── preprocess_stage/     # ⑥ 预处理
│   │       ├── process_stage/        # ⑦ 核心处理 (插件/LLM 调用)
│   │       ├── result_decorate/     # ⑧ 结果装饰
│   │       └── respond/              # ⑨ 发送消息
│   │
│   ├── agent/                        # 🧠 Agent 系统
│   │   ├── agent.py                  # Agent 数据类
│   │   ├── hooks.py                  # BaseAgentRunHooks 钩子
│   │   ├── message.py                # Message 消息模型
│   │   ├── response.py               # AgentResponse 响应模型
│   │   ├── run_context.py            # TContext 运行上下文
│   │   ├── tool.py                   # FunctionTool, ToolSet
│   │   ├── tool_executor.py          # BaseFunctionToolExecutor
│   │   ├── handoff.py                # FunctionTool, HandoffTool
│   │   ├── mcp_client.py             # MCP 客户端
│   │   ├── context/                  # Agent 上下文管理:
│   │   │   ├── manager.py            # ContextManager
│   │   │   ├── compressor.py         # ContextCompressor
│   │   │   ├── token_counter.py      # TokenCounter
│   │   │   └── ...
│   │   └── runners/                  # Agent 运行器:
│   │       ├── base.py               # BaseAgentRunner 抽象基类
│   │       ├── tool_loop_agent_runner.py  # ToolLoopAgentRunner (核心循环)
│   │       └── coze/, dashscope/, deerflow/, dify/  # 第三方 Agent 平台
│   │
│   ├── knowledge_base/               # 📚 知识库系统
│   │   ├── kb_mgr.py                 # KnowledgeBaseManager
│   │   ├── kb_db_sqlite.py           # 知识库 SQLite 存储
│   │   ├── models.py                 # 知识库数据模型
│   │   ├── parsers/                  # 文件解析器 (PDF, EPUB, Markdown, URL)
│   │   ├── chunking/                 # 文本分块策略
│   │   └── retrieval/                # 检索与重排序
│   │
│   ├── computer/                     # 💻 Computer Use 系统
│   │   ├── computer_client.py        # ComputerClient
│   │   ├── booters/                  # 启动器 (CUA, BoxLite, Shipyard 等)
│   │   └── olayer/                   # 操作层 (browser, filesystem, gui, python, shell)
│   │
│   ├── skills/                       # 🎯 Skill 技能系统
│   │   ├── skill_manager.py          # SkillManager 技能管理器
│   │   └── neo_skill_sync.py         # Neo 技能同步
│   │
│   ├── cron/                         # ⏰ Cron 定时任务
│   │   ├── manager.py                # CronJobManager
│   │   └── events.py                 # Cron 事件
│   │
│   ├── conversation_mgr.py           # 💬 会话管理器
│   ├── persona_mgr.py                # 🎭 人格管理器
│   ├── platform_message_history_mgr.py # 📜 平台消息历史
│   ├── event_bus.py                   # 🚌 事件总线 (队列→调度器分发)
│   ├── core_lifecycle.py             # 🔁 核心生命周期 (启动/停止/重启)
│   ├── initial_loader.py             # 📥 初始加载器
│   ├── astrbot_config_mgr.py          # ⚙️ AstrBot 配置管理器
│   ├── exceptions.py                 # ❌ 异常定义
│   ├── log.py                        # 📋 日志系统
│   └── ...
│
├── dashboard/                        # 🖥️ Web Dashboard (FastAPI)
│   ├── server.py                     # Dashboard 服务器
│   ├── asgi_runtime.py               # ASGI 运行时
│   ├── router.py                     # API 路由
│   ├── schemas.py                    # Pydantic 模型
│   ├── api/                          # API 路由处理函数
│   ├── services/                     # 业务逻辑层 (25+ 服务)
│   └── ...
│
├── builtin_stars/                    # 📦 内置插件
│   ├── astrbot/                      # 核心聊天插件
│   └── builtin_commands/             # 内置命令插件
│
└── cli/                              # 🛠️ CLI 工具
    ├── __main__.py                   # 入口
    ├── commands/                     # CLI 子命令 (init, run, conf, plug, password)
    └── utils/                        # CLI 工具函数
```

---

## 二、核心数据流与模块关系图

### 下行链路 （消息处理后发送）数据流图

```
                     ┌─────────────────────────────────────────┐
                     │          AstrBotCoreLifecycle           │
                     │     (核心生命周期: 启动/停止/重启)       │
                     └──────────────────┬──────────────────────┘
                                        │ 初始化
          ┌─────────────────────────────┼──────────────────────────────┐
          │                             │                              │
          ▼                             ▼                              ▼
  ┌───────────────┐          ┌─────────────────┐              ┌─────────────────┐
  │  EventBus     │          │  PluginManager  │              │ ProviderManager │
  │  (事件总线)   │          │  (插件管理器)   │              │  (模型提供商)   │
  └───────┬───────┘          └────────┬────────┘              └────────┬────────┘
          │                            │                              │
          │ 消息队列                   │ 发现/加载/热重载               │ 注册/获取
          ▼                            ▼                              ▼
  ┌───────────────┐          ┌─────────────────┐              ┌─────────────────┐
  │PipelineScheduler│         │  Star (插件)    │              │    Provider     │
  │  (管道调度器)  │          │  ┌───────────┐  │              │  (LLM 提供商)   │
  └───────┬───────┘          │  │CommandP...│  │              └────────┬────────┘
          │                   │  │PluginKV.. │  │                       │
          │ 9 个 Stage        │  └───────────┘  │                       │ text_chat()
          │ 洋葱模型          │       ▲          │                       ▼
          ▼                   │       │继承      │              ┌─────────────────┐
  ┌──────────────────────┐   │  ┌────┴─────┐   │              │  Agent 系统     │
  │ 1.WakingCheck        │   │  │  Context  │   │              │  ┌───────────┐  │
  │ 2.WhitelistCheck     │   │  │ (上下文)  │◄──┼──────────────│  │ToolLoop.. │  │
  │ 3.SessionStatusCheck │   │  └──────────┘   │              │  │AgentRunner│  │
  │ 4.RateLimitCheck     │   │       ▲          │              │  └───────────┘  │
  │ 5.ContentSafetyCheck │   │       │提供       │              │       │        │
  │ 6.PreProcess         │   │       │          │              │       │调用     │
  │ 7.Process (插件/LLM) │───┼───────┘          │              │       ▼        │
  │ 8.ResultDecorate     │   │                  │              │  ┌───────────┐  │
  │ 9.Respond (发送)     │   │                  │              │  │  Tool    │  │
  └──────────────────────┘   │                  │              │  │ (Function │  │
                              │                  │              │  │  Tool)   │  │
                              │                  │              │  └───────────┘  │
                              ▼                  ▼              └─────────────────┘
                     ┌──────────────────────────────┐
                     │    Platform (平台适配器)     │
                     │  ┌────────────────────────┐  │
                     │  │ 20+ 平台实现:           │  │
                     │  │ QQ/Discord/Telegram/... │  │
                     │  └────────────────────────┘  │
                     └──────────────────────────────┘
```

### 完整的数据流图

```
                    ┌─────────────────────────────────────────────┐
                    │          AstrBotCoreLifecycle               │
                    └─────────────────┬───────────────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
              ▼                       ▼                       ▼
     ┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
     │  PlatformManager │     │  EventBus    │     │ PluginManager   │
     │  (独立管理器)    │     │  (事件总线)  │     │  (Star 管理器)  │
     └────────┬─────────┘     └──────┬───────┘     └────────┬────────┘
              │                      │                      │
              │ ① 上行：接收消息     │                      │
              │    Platform 收到 IM  │                      │
              │    消息 → 封装为     │                      │
              │    AstrMessageEvent  │                      │
              │    → 投入队列        │                      │
              └──────────────────────►                      │
                                       │                    │
                                       ▼                    ▼
                              ┌─────────────────────────────────┐
                              │      PipelineScheduler         │
                              │   (9 Stage 管道处理)           │
                              │                                 │
                              │  ② Stage 7: Process            │
                              │     → 调用 Star Handler        │
                              │     (业务逻辑处理)             │
                              │                                 │
                              │  ③ Stage 9: Respond            │
                              │     → 调用 Platform.send()     │
                              │     (发回 IM)                  │
                              └────────────────┬────────────────┘
                                               │
                                               │ ④ 下行：发送消息
                                               │
                                               ▼
                                       ┌─────────────────┐
                                       │ Platform.send() │ ──→ IM 平台
                                       └─────────────────┘
```

---

## 三、关键模块间的调用/依赖关系

| 源模块 | → | 目标模块 | 关系说明 |
|--------|---|---------|---------|
| `core/__init__.py` | → | `config`, `db`, `utils` | **初始化全局单例**: astrbot_config, db_helper, sp, html_renderer |
| `core_lifecycle.py` | → | **所有管理器** | 组装整个系统: ProviderManager, PlatformManager, PluginManager, PipelineScheduler, EventBus |
| `event_bus.py` | → | `pipeline/scheduler.py` | 从事件队列取事件 → 分发给 PipelineScheduler |
| `pipeline/scheduler.py` | → | `pipeline/stage.py` | 按 STAGES_ORDER 顺序执行 Stage 洋葱模型 |
| `pipeline/process_stage/` | → | `star/star_handler.py` | 查找匹配的插件 Handler 并调用 |
| `star/base.py` | → | `star/star.py` | `__init_subclass__` 自动注册 Star 子类到 star_map |
| `star/star_manager.py` | → | `star/star.py`, `star_handler.py` | 管理插件生命周期: 加载→绑定 handler→卸载→清理 |
| `star/context.py` | → | `provider/manager.py`, `platform/manager.py` | Context 作为插件 API 门面，转发请求 |
| `provider/provider.py` | → | `provider/register.py` | Provider 通过装饰器注册到 provider_cls_map |
| `agent/runners/tool_loop_agent_runner.py` | → | `provider/provider.py` | 调用 Provider.text_chat() 与 LLM 交互 |
| `agent/runners/tool_loop_agent_runner.py` | → | `agent/tool_executor.py` | 执行 FunctionTool 调用 |
| `platform/platform.py` | → | `event_bus.py` | Platform 将消息事件提交到事件队列 |
| `dashboard/services/` | → | 几乎所有 core 模块 | Dashboard 服务层作为 Web UI 与核心的桥梁 |

---

## 四、核心设计模式总结

1. **装饰器注册模式** — 插件通过 `@register_*` 装饰器声明式注册命令、事件处理器、LLM 工具等
2. **自动发现模式** — `Star.__init_subclass__` 自动识别插件子类，无需手动注册
3. **洋葱模型管道** — Pipeline 的 Stage 支持 `AsyncGenerator` 实现洋葱模型（前置→递归→后置）
4. **事件驱动架构** — Platform → EventBus → PipelineScheduler 异步分发
5. **全局单例模式** — `core/__init__.py` 创建全局唯一的 config、db、sp、logger 等
6. **Provider 抽象层** — 统一的 Provider 接口支持 Chat/TTS/STT/Embedding/Rerank 五种类型
7. **Agent Tool Loop** — ToolLoopAgentRunner 实现 ReAct 风格的工具调用循环，支持流式、fallback、context 压缩等

---

## 五、插件开发者视角的关键入口

### 5.1 插件基类: `Star`

文件位置: `astrbot.core.star.base.Star`

```python
class Star(CommandParserMixin, PluginKVStoreMixin):
    """所有插件（Star）的父类，所有插件都应该继承于这个类"""
    
    async def initialize(self) -> None:
        """当插件被激活时会调用这个方法"""
    
    async def terminate(self) -> None:
        """当插件被禁用、重载插件时会调用这个方法"""
```

### 5.2 上下文: `Context`

文件位置: `astrbot.core.star.context.Context`

Context 是插件与 AstrBot 框架交互的**唯一入口**，提供:
- `llm_generate()` — 直接调用 LLM 生成回复
- `tool_loop_agent()` — 运行 Agent 循环（支持工具调用）
- `get_config()` — 获取配置
- `send_message()` — 主动发送消息
- `get_all_stars()` / `get_registered_star()` — 获取其他插件信息
- `get_using_provider()` / `get_current_chat_provider_id()` — 获取当前模型
- `get_provider_by_id()` / `get_all_providers()` — 获取 Provider
- `add_llm_tools()` — 动态添加 LLM 工具
- `register_web_api()` — 注册 Web API
- `get_event_queue()` — 获取事件队列（已弃用）

### 5.3 注册装饰器

文件位置: `astrbot.core.star.register.*`

| 装饰器 | 用途 | 对应 EventType |
|--------|------|---------------|
| `@register_command` | 注册命令处理器 | `AdapterMessageEvent` |
| `@register_command_group` | 注册命令组 | `AdapterMessageEvent` |
| `@register_regex` | 注册正则匹配处理器 | `AdapterMessageEvent` |
| `@register_agent` | 注册 Agent 事件处理器 | `OnAgentBeginEvent` / `OnAgentDoneEvent` |
| `@register_llm_tool` | 注册 LLM 函数调用工具 | `OnLLMRequestEvent` |
| `@register_on_llm_request` | LLM 请求前拦截 | `OnLLMRequestEvent` |
| `@register_on_llm_response` | LLM 响应后拦截 | `OnLLMResponseEvent` |
| `@register_on_decorating_result` | 结果装饰拦截 | `OnDecoratingResultEvent` |
| `@register_on_after_message_sent` | 消息发送后拦截 | `OnAfterMessageSentEvent` |
| `@register_on_astrbot_loaded` | AstrBot 加载完成 | `OnAstrBotLoadedEvent` |
| `@register_on_platform_loaded` | 平台加载完成 | `OnPlatformLoadedEvent` |
| `@register_on_plugin_error` | 插件错误处理 | `OnPluginErrorEvent` |
| `@register_on_plugin_loaded` | 插件加载完成 | `OnPluginLoadedEvent` |
| `@register_on_plugin_unloaded` | 插件卸载完成 | `OnPluginUnloadedEvent` |
| `@register_on_using_llm_tool` | 使用 LLM 工具时 | `OnUsingLLMToolEvent` |
| `@register_on_llm_tool_respond` | LLM 工具响应时 | `OnLLMToolRespondEvent` |
| `@register_on_waiting_llm_request` | 等待 LLM 请求时 | `OnWaitingLLMRequestEvent` |
| `@register_custom_filter` | 自定义过滤器 | 配合其他装饰器使用 |
| `@register_permission_type` | 权限类型过滤 | 配合命令装饰器使用 |
| `@register_event_message_type` | 消息类型过滤 | 配合命令装饰器使用 |
| `@register_platform_adapter_type` | 平台类型过滤 | 配合命令装饰器使用 |

### 5.4 插件生命周期

```
PluginManager.load()
    │
    ├── 1. _get_plugin_modules()          # 扫描插件目录，发现所有插件
    │
    ├── 2. _import_plugin_with_dependency_recovery()  # 导入插件模块（含依赖恢复）
    │
    ├── 3. Star.__init_subclass__()       # 自动注册 Star 子类到 star_map
    │
    ├── 4. _load_plugin_metadata()        # 从 metadata.yaml 加载元数据
    │
    ├── 5. _validate_astrbot_version_specifier()  # 版本兼容性检查
    │
    ├── 6. 实例化插件类                    # metadata.star_cls_type(context, config)
    │
    ├── 7. 绑定 Handler                   # functools.partial(handler, star_cls)
    │
    └── 8. activate_llm_tool()            # 激活 LLM 工具
```

### 5.5 消息处理管道流程

```
用户消息 → Platform.commit_event()
         → EventBus.dispatch()
         → PipelineScheduler.execute()
         → Stage 1: WakingCheck         (是否需要唤醒)
         → Stage 2: WhitelistCheck      (是否在白名单)
         → Stage 3: SessionStatusCheck  (会话是否启用)
         → Stage 4: RateLimitStage      (频率限制检查)
         → Stage 5: ContentSafetyCheck (内容安全检查)
         → Stage 6: PreProcessStage     (预处理)
         → Stage 7: ProcessStage       (核心处理: 匹配插件命令/LLM调用)
         → Stage 8: ResultDecorateStage(结果装饰: t2i/前缀/语音)
         → Stage 9: RespondStage       (发送消息到 Platform)
         → Platform.send_by_session()  (实际下发消息)
```

### 5.6 API 层导出

文件位置: `astrbot.api.__init__`

```python
from astrbot import logger                    # 日志
from astrbot.core import sp                   # SharedPreferences (全局偏好设置)
from astrbot.core.config.astrbot_config import AstrBotConfig  # 配置类
from astrbot.core.star.register import register_agent as agent  # Agent 注册装饰器
from astrbot.core.star.register import register_llm_tool as llm_tool  # LLM 工具注册装饰器
from astrbot.core.agent.tool import FunctionTool, ToolSet  # 工具类
from astrbot.core.agent.tool_executor import BaseFunctionToolExecutor  # 工具执行器
```

插件开发者通常只需 `from astrbot.api import ...` 即可获取所有必要的 API。

---

## 六、关键全局注册表

| 注册表 | 位置 | 类型 | 说明 |
|--------|------|------|------|
| `star_map` | `core/star/star.py` | `dict[str, StarMetadata]` | 模块路径 → 插件元数据 |
| `star_registry` | `core/star/star.py` | `list[StarMetadata]` | 所有已注册插件的有序列表 |
| `star_handlers_registry` | `core/star/star_handler.py` | `StarHandlerRegistry` | 所有已注册的事件处理器 |
| `provider_registry` | `core/provider/register.py` | `list[ProviderMetaData]` | 所有已注册的 Provider 类型 |
| `provider_cls_map` | `core/provider/register.py` | `dict[str, ProviderMetaData]` | Provider 类型名 → 元数据 |
| `llm_tools` | `core/provider/register.py` | `FuncCall` | 所有已注册的 LLM 函数工具 |
| `registered_stages` | `core/pipeline/stage.py` | `list[type[Stage]]` | 所有已注册的 Pipeline Stage |
| `registered_web_apis` | `core/star/context.py` | `list[RegisteredWebApi]` | 插件注册的 Web API |
| `_INSTANCES` | `core/platform/manager.py` | - | 平台适配器实例管理 |

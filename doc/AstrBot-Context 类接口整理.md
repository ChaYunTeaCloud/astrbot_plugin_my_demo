# AstrBot Context 类接口整理

> 源码路径：`.venv/Lib/site-packages/astrbot/core/star/context.py`
> Context 是 Star 插件与 AstrBot 框架沟通的桥梁，所有方法均为插件开发者提供。

---

## 一、LLM 调用

- `llm_generate(chat_provider_id, prompt, image_urls, audio_urls, tools, system_prompt, contexts, **kwargs)`
  - 直接调用指定 Provider 的 LLM 生成响应。不会自动执行工具调用，需用 `tool_loop_agent()` 实现 Agent 循环
  - 参数：
    - `chat_provider_id`: 要使用的聊天模型 ID
    - `prompt`: 发送给 LLM 的文本（若传了 `contexts`，prompt 会作为最后一条用户消息追加）
    - `image_urls`: 图片 URL 列表
    - `audio_urls`: 音频 URL 或本地路径列表
    - `tools`: 可供 LLM 调用的工具集 (`ToolSet`)
    - `system_prompt`: 系统提示词，始终作为第一条 system message
    - `contexts`: 多轮对话历史 (`list[Message]`)

- `tool_loop_agent(event, chat_provider_id, prompt, ..., max_steps, tool_call_timeout, **kwargs)`
  - Agent 循环调用：LLM 自动判断何时调用工具、何时返回最终答案。支持流式输出、Agent 钩子等
  - 参数：
    - `max_steps`: Agent 最多循环步数（默认 30）
    - `tool_call_timeout`: 单次工具调用超时时间（默认 120 秒）
    - `stream`: 是否流式输出
    - `agent_hooks`: Agent 执行期间的钩子

---

## 二、Provider（模型提供商）管理

### 2.1 获取 Provider

- `get_provider_by_id(provider_id)`
  - 按 ID 获取指定 Provider 实例，找不到返回 `None`

- `get_using_provider(umo)`
  - 获取当前正在使用的聊天模型 Provider

- `get_using_tts_provider(umo)`
  - 获取当前正在使用的 TTS Provider

- `get_using_stt_provider(umo)`
  - 获取当前正在使用的 STT Provider

- `get_current_chat_provider_id(umo)`
  - 获取当前使用的聊天模型 ID（字符串）

### 2.2 批量获取 Provider

- `get_all_providers()`
  - 获取所有 Chat 类型 Provider

- `get_all_tts_providers()`
  - 获取所有 TTS Provider

- `get_all_stt_providers()`
  - 获取所有 STT Provider

- `get_all_embedding_providers()`
  - 获取所有 Embedding Provider

### 2.3 注册 Provider

- `register_provider(provider)`
  - 动态注册一个新的 Chat 类型 Provider

> `umo` 参数：unified_message_origin，会话来源标识。若启用了提供商隔离，会返回该会话专属的 Provider。

---

## 三、LLM 工具（Function Tool）管理

- `get_llm_tool_manager()`
  - 获取 `FunctionToolManager`，用于管理所有已注册的 Function-calling 工具

- `add_llm_tools(*tools)`
  - 添加一个或多个 LLM 工具（`FunctionTool` 对象）。若重名会替换旧工具

- `activate_llm_tool(name)`
  - 激活指定名称的工具（默认已激活）

- `deactivate_llm_tool(name)`
  - 停用指定名称的工具

- ~~`register_llm_tool(name, func_args, desc, func_obj)`~~
  - 已弃用，改用 `@llm_tool` 装饰器

- ~~`unregister_llm_tool(name)`~~
  - 已弃用

---

## 四、Star 插件管理

- `get_registered_star(star_name)`
  - 按名称查找已注册的插件，返回 `StarMetadata`

- `get_all_stars()`
  - 获取当前所有已加载插件的 `StarMetadata` 列表

---

## 五、配置

- `get_config(umo)`
  - 获取 AstrBot 配置。不传 `umo` 返回默认配置，传 `umo` 返回会话专属配置

---

## 六、消息发送

- `send_message(session, message_chain)`
  - 主动发送消息到指定会话。`session` 可传字符串（如 `event.unified_msg_origin`）或 `MessageSesion` 对象。找到匹配平台返回 `True`，未找到返回 `False`

  > 注意：`qq_official` 平台不支持此方法。

---

## 七、平台适配器

- `get_platform_inst(platform_id)`
  - 按 ID 获取平台适配器实例（推荐）

- ~~`get_platform(platform_type)`~~
  - 已弃用（v4.0.0+），改用 `get_platform_inst`

---

## 八、数据库

- `get_db()`
  - 获取 `BaseDatabase` 实例，用于数据库操作

---

## 九、Web API 注册

- `register_web_api(route, view_handler, methods, desc)`
  - 注册一个 Web API 路由
  - 参数：
    - `route`: API 路由路径
    - `view_handler`: 异步处理函数
    - `methods`: HTTP 方法列表
    - `desc`: API 描述

---

## 十、事件队列

- `get_event_queue()`
  - 获取内部事件队列（`asyncio.Queue`）

---

## 十一、公开属性（直接访问）

以下属性在 `__init__` 时初始化，可直接通过 `self.context.xxx` 访问：

- `provider_manager` (`ProviderManager`) — 模型提供商管理器
- `platform_manager` (`PlatformManagerProtocol`) — 平台适配器管理器
- `conversation_manager` (`ConversationManager`) — 会话管理器
- `message_history_manager` (`PlatformMessageHistoryManager`) — 消息历史管理器
- `persona_manager` (`PersonaManager`) — 人格设定管理器
- `astrbot_config_mgr` (`AstrBotConfigManager`) — 配置文件管理器
- `kb_manager` (`KnowledgeBaseManager`) — 知识库管理器
- `cron_manager` (`CronJobManager`) — 定时任务管理器
- `subagent_orchestrator` (`SubAgentOrchestrator`) — 子 Agent 编排器

---

## 十二、已弃用方法

- `register_llm_tool()` → 使用 `@llm_tool` 装饰器
- `unregister_llm_tool()` → 不再需要，改用装饰器后自动管理
- `register_commands()` → 使用 `@filter.command()` 装饰器
- `register_task()` → 使用 `@filter.on_llm_request()` 或初始化时启动任务
- `get_platform()` → 改用 `get_platform_inst(platform_id)`

---

## 快速参考：插件开发最常用的接口

```python
# 调 LLM
resp = await self.context.llm_generate(chat_provider_id="xxx", prompt="你好")

# 发消息
await self.context.send_message(event.unified_msg_origin, MessageChain().add("文本内容"))

# 取配置
cfg = self.context.get_config()

# 获取平台实例
platform = self.context.get_platform_inst(event.get_platform_id())

# 获取当前 Provider
provider = self.context.get_using_provider(event.unified_msg_origin)
```
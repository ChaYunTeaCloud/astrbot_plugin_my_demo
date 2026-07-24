# astrbot.api 包详细分析

> 源码路径：`.venv/Lib/site-packages/astrbot/api/`
> `astrbot.api` 是 AstrBot 暴露给插件开发者的**官方稳定 API 层**。插件应该**只从此包导入**所有需要的类、函数和装饰器，不直接依赖 `astrbot.core` 下的内部实现。
> 这样做的好处是：当 AstrBot 内部重构时，`api` 层会保持向后兼容，你的插件不会因为底层变动而崩溃。

---

## 包结构总览

```
astrbot/api/
├── __init__.py          # 顶层导出：基础工具类 + 装饰器
├── all.py               # 大杂烩：一揽子导出所有常用 API
├── message_components.py # 消息组件（图片/文本/文件等）
├── web.py               # Web API 相关：请求/响应/文件上传
├── event/
│   ├── __init__.py      # 事件相关：AstrMessageEvent、MessageChain 等
│   └── filter/
│       └── __init__.py  # 装饰器集合：@filter.command()、@filter.on_llm_request() 等
├── platform/
│   └── __init__.py      # 平台适配器基类 + 注册函数
├── provider/
│   └── __init__.py      # Provider 基类 + 数据实体
├── star/
│   └── __init__.py      # Star 基类 + Context + 注册函数
└── util/
    └── __init__.py      # 工具类：会话等待器
```

---

## 一、`astrbot.api` — 顶层入口

从 `astrbot.api` 直接导入的基础模块。

### 导出清单

| 名称 | 类型 | 说明 |
|------|------|------|
| `logger` | 对象 | AstrBot 全局日志记录器，用于插件打印日志 |
| `sp` | 对象 | 特殊工具集（具体用途需查文档） |
| `html_renderer` | 对象 | HTML 渲染器，用于生成富文本消息 |
| `AstrBotConfig` | 类 | AstrBot 配置对象（通过 Context.get_config() 获取） |
| `FunctionTool` | 类 | LLM 函数调用工具的封装类 |
| `ToolSet` | 类 | 工具集合，用于将多个工具打包传给 LLM |
| `BaseFunctionToolExecutor` | 类 | 工具执行器基类 |
| `llm_tool` | 装饰器 | 注册 LLM 工具（同 `@filter.llm_tool()`） |
| `agent` | 装饰器 | 注册 Agent |

### 使用示例

```python
from astrbot.api import logger, llm_tool

logger.info("插件加载成功")

@llm_tool()
async def my_tool(query: str) -> str:
    return f"你说了: {query}"
```

---

## 二、`astrbot.api.event` — 事件与消息

提供事件对象、消息链、结果类型等核心数据结构。

### 导出清单

| 名称 | 类型 | 说明 |
|------|------|------|
| `AstrMessageEvent` | 类 | 消息事件对象，包含发送者、消息内容、会话等所有上下文信息 |
| `MessageChain` | 类 | 消息链，用于构建/发送复杂消息（文本+图片+At 等） |
| `MessageEventResult` | 类 | 消息事件的处理结果 |
| `CommandResult` | 类 | 命令处理结果 |
| `EventResultType` | 枚举 | 结果类型枚举 |
| `ResultContentType` | 枚举 | 结果内容类型枚举 |

### 使用示例

```python
from astrbot.api.event import AstrMessageEvent, MessageChain

# 在 Handler 中接收 event
async def my_handler(event: AstrMessageEvent):
    # 获取原始消息
    message = event.message
    
    # 构建回复
    result = event.make_result()
    result.message(MessageChain().add("回复内容"))
    return result
```

---

## 三、`astrbot.api.event.filter` — 装饰器集合

这是插件开发中**使用频率最高**的模块。提供了所有注册事件处理器的装饰器。

### 3.1 命令与正则

| 装饰器 | 说明 |
|--------|------|
| `@filter.command(name, desc, priority=1, ...)` | 注册命令处理器。当用户发送匹配命令时触发 |
| `@filter.command_group(name, ...)` | 注册命令组，多个子命令可挂在同一个组下 |
| `@filter.regex(pattern)` | 使用正则表达式匹配消息触发 |

### 3.2 LLM 相关

| 装饰器 | 说明 |
|--------|------|
| `@filter.llm_tool()` | 注册一个 LLM 函数调用工具 |
| `@filter.on_llm_request()` | 当 LLM 请求发出时触发（可拦截/修改请求） |
| `@filter.on_llm_response()` | 当 LLM 响应返回时触发 |
| `@filter.on_agent_begin()` | Agent 开始执行时触发 |
| `@filter.on_agent_done()` | Agent 执行完成时触发 |
| `@filter.on_using_llm_tool()` | 当 LLM 正在使用工具时触发 |
| `@filter.on_llm_tool_respond()` | 当 LLM 工具返回结果时触发 |
| `@filter.on_waiting_llm_request()` | 等待 LLM 请求时触发 |

### 3.3 生命周期事件

| 装饰器 | 说明 |
|--------|------|
| `@filter.on_astrbot_loaded()` | AstrBot 加载完成时触发 |
| `@filter.on_platform_loaded()` | 平台适配器加载完成时触发 |
| `@filter.on_plugin_loaded()` | 插件加载完成时触发 |
| `@filter.on_plugin_unloaded()` | 插件卸载时触发 |
| `@filter.on_plugin_error()` | 插件发生错误时触发 |

### 3.4 消息处理

| 装饰器 | 说明 |
|--------|------|
| `@filter.event_message_type(type)` | 按消息类型过滤（群聊/私聊/全部） |
| `@filter.platform_adapter_type(type)` | 按平台适配器类型过滤 |
| `@filter.permission_type(type)` | 按权限类型过滤（管理员/普通用户） |
| `@filter.custom_filter(filter)` | 使用自定义过滤器 |
| `@filter.on_decorating_result()` | 结果装饰时触发（可修改最终回复） |
| `@filter.after_message_sent()` | 消息发送完成后触发 |

### 3.5 过滤器类

| 类 | 说明 |
|----|------|
| `EventMessageType` | 消息类型枚举：GROUP、PRIVATE、ALL |
| `EventMessageTypeFilter` | 按消息类型过滤的过滤器 |
| `PermissionType` | 权限类型枚举 |
| `PermissionTypeFilter` | 按权限过滤的过滤器 |
| `PlatformAdapterType` | 平台类型枚举 |
| `PlatformAdapterTypeFilter` | 按平台类型过滤的过滤器 |
| `CustomFilter` | 自定义过滤器基类 |

### 使用示例

```python
from astrbot.api.event import filter

@filter.command(name="hello", desc="打招呼")
@filter.event_message_type(EventMessageType.ALL)
async def hello_command(event):
    return event.make_result().message("你好！")

@filter.on_llm_request()
async def before_llm(event):
    logger.info(f"LLM 请求: {event.message}")
```

---

## 四、`astrbot.api.platform` — 平台适配器

用于开发自定义平台适配器（如对接新的 IM 平台）。

### 导出清单

| 名称 | 类型 | 说明 |
|------|------|------|
| `Platform` | 抽象基类 | 所有平台适配器的父类，需实现 `run()` 和 `meta()` 方法 |
| `PlatformMetadata` | 类 | 平台元数据（ID、名称、描述等） |
| `AstrBotMessage` | 类 | 平台消息对象 |
| `AstrMessageEvent` | 类 | 消息事件（同 `astrbot.api.event` 中的） |
| `MessageMember` | 类 | 消息成员（发送者/接收者信息） |
| `MessageType` | 枚举 | 消息类型 |
| `Group` | 类 | 群聊信息 |
| `register_platform_adapter` | 装饰器 | 注册平台适配器到全局注册表 |

### 使用示例

```python
from astrbot.api.platform import Platform, PlatformMetadata, register_platform_adapter

@register_platform_adapter()
class MyCustomPlatform(Platform):
    def meta(self) -> PlatformMetadata:
        return PlatformMetadata(
            id="my_platform",
            name="我的平台",
        )
    
    async def run(self):
        # 启动平台连接
        pass
```

---

## 五、`astrbot.api.provider` — Provider 接口

用于开发自定义 LLM Provider（如对接新的 AI 服务商）。

### 导出清单

| 名称 | 类型 | 说明 |
|------|------|------|
| `Provider` | 类 | 文本对话 Provider 基类 |
| `STTProvider` | 类 | 语音转文字 Provider 基类 |
| `ProviderMetaData` | 类 | Provider 元数据 |
| `ProviderRequest` | 类 | Provider 请求对象 |
| `LLMResponse` | 类 | LLM 响应对象 |
| `ProviderType` | 枚举 | Provider 类型（CHAT_COMPLETION、TEXT_TO_SPEECH 等） |
| `Personality` | 类 | 人格设定数据模型 |

---

## 六、`astrbot.api.star` — Star 插件基类

插件的核心基类和注册机制。

### 导出清单

| 名称 | 类型 | 说明 |
|------|------|------|
| `Star` | 类 | 所有插件的父类。插件必须继承此类 |
| `StarTools` | 类 | 插件工具集合 |
| `Context` | 类 | 插件上下文（同 `astrbot.core.star.Context`） |
| `register` | 装饰器 | 注册 Star 插件 |
| 配置相关函数 | — | `load_config()`、`put_config()`、`update_config()`（已过时） |

### 使用示例

```python
from astrbot.api.star import Star, Context

class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
    
    async def initialize(self):
        pass
```

---

## 七、`astrbot.api.message_components` — 消息组件

从 `astrbot.core.message.components` 重新导出的所有消息组件类。用于构建 `MessageChain`。

### 主要组件类型

| 组件 | 说明 |
|------|------|
| `Plain(text)` | 纯文本 |
| `Image(url/file/path)` | 图片 |
| `Record(url/file/path)` | 音频 |
| `Video(url/file/path)` | 视频 |
| `File(url/file/path)` | 文件附件 |
| `Face(id)` | QQ 表情 |
| `At(qq)` | @某人 |
| `Reply(message_id)` | 引用回复 |
| `Forward(id)` | 转发消息 |
| `Music(title)` | 音乐分享 |
| `Json(data)` | JSON 消息 |

### 使用示例

```python
from astrbot.api import message_components
from astrbot.api.event import MessageChain

chain = MessageChain()
chain.add(message_components.Plain(text="你好"))
chain.add(message_components.Image(url="https://example.com/pic.png"))
chain.add(message_components.At(qq=123456))
```

---

## 八、`astrbot.api.web` — Web API 开发

用于为插件注册 Web API 路由，提供 HTTP 接口服务。

### 8.1 请求对象

| 类/对象 | 说明 |
|---------|------|
| `request` | 模块级代理对象，在 Web Handler 内部可直接使用，自动绑定当前请求 |
| `PluginRequest` | 请求封装类，包含 method、path、headers、cookies、query、body()、json()、form()、files() |
| `PluginUploadFile` | 上传文件封装类，支持 save()、read()、write()、seek()、close() |
| `PluginMultiDict` | 支持重复 key 的字典类，用于 query/form/files 参数 |

### 8.2 响应构建

| 函数 | 说明 |
|------|------|
| `json_response(data, status_code, headers)` | 构建 JSON 响应 |
| `error_response(message, status_code, data, headers)` | 构建标准错误响应（格式：`{"status": "error", "message": ...}`） |
| `file_response(path, filename, content_type, headers)` | 构建文件下载响应 |
| `stream_response(content, content_type, status_code, headers)` | 构建流式响应（SSE 等） |

### 使用示例

```python
from astrbot.api.web import request, json_response, error_response

# 在 Star 初始化时注册
class MyPlugin(Star):
    async def initialize(self):
        self.context.register_web_api(
            route="/api/my_plugin/data",
            view_handler=self.handle_get_data,
            methods=["GET"],
            desc="获取数据",
        )
    
    async def handle_get_data(self):
        data = request.query.get("key")
        if not data:
            return error_response("缺少参数 key")
        return json_response({"result": f"收到: {data}"})
```

---

## 九、`astrbot.api.util` — 工具类

提供会话等待器，用于实现"等待用户回复"的交互式对话。

### 导出清单

| 名称 | 类型 | 说明 |
|------|------|------|
| `SessionWaiter` | 类 | 会话等待器，用于阻塞等待特定会话的下一条消息 |
| `SessionController` | 类 | 会话控制器，用于提前结束等待 |
| `session_waiter` | 装饰器/上下文管理器 | 简化使用的装饰器版本 |

### 使用示例

```python
from astrbot.api.util import session_waiter, SessionController

@filter.command(name="ask", desc="提问")
async def ask_command(event):
    result = event.make_result()
    result.message("请输入你的名字：")
    
    async with session_waiter(event, timeout=30) as controller:
        if controller.timed_out:
            result.message("超时了")
            return result
        # 用户回复的消息会自动传到下一次 handler
        ...
```

---

## 十、`astrbot.api.all` — 一揽子导入

如果觉得分开导入太麻烦，可以用一行代码导入所有常用 API：

```python
from astrbot.api.all import *
```

这会一次性导入：
- `AstrBotConfig`、`logger`、`html_renderer`
- `MessageEventResult`、`MessageChain`、`CommandResult`、`EventResultType`
- `AstrMessageEvent`
- `Star`、`Context`、`register`、`StarTools`
- 所有 `filter` 装饰器
- `EventMessageTypeFilter`、`EventMessageType`
- `PlatformAdapterTypeFilter`、`PlatformAdapterType`
- 平台相关类（`Platform`、`PlatformMetadata` 等）
- 消息组件（通过 `message_components` 通配导入）

> 注意：通配导入在大型项目中可能导致命名冲突，建议仅在小型插件或快速原型中使用。

---

## 总结：插件开发导入范式

```python
# 最常用的导入组合
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Star, Context

# 如果需要 LLM 工具
from astrbot.api import llm_tool, FunctionTool, ToolSet

# 如果需要 Web API
from astrbot.api.web import request, json_response

# 如果需要消息组件
from astrbot.api import message_components
```
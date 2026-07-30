# AstrBot API 速查表

> 快速查询 AstrBot 插件开发中可导入的模块、类和函数。

---

## 一、主入口导入

### 直接从 `astrbot.api` 导入

```python
from astrbot.api import (
    AstrBotConfig,           # 配置类
    BaseFunctionToolExecutor, # 基础工具执行器
    FunctionTool,            # 工具类
    ToolSet,                 # 工具集合
    agent,                   # @register_agent 装饰器
    html_renderer,           # HTML 渲染器
    llm_tool,                # @register_llm_tool 装饰器
    logger,                  # 日志记录器（自动路由到插件日志）
    sp,                      # 系统提示词工具
)
```

### 从 `astrbot.api.all` 一键导入

```python
from astrbot.api.all import *
# 或具体导入
from astrbot.api.all import (
    # 配置
    AstrBotConfig,
    
    # 日志
    logger,
    
    # 事件相关
    MessageEventResult,
    MessageChain,
    CommandResult,
    EventResultType,
    AstrMessageEvent,
    
    # 装饰器
    command,
    command_group,
    event_message_type,
    regex,
    platform_adapter_type,
    register,               # 注册插件
    llm_tool,
    
    # Star 类
    Context,
    Star,
    
    # Provider 相关
    Provider,
    ProviderMetaData,
    Personality,
    
    # Platform 相关
    Platform,
    AstrBotMessage,
    MessageMember,
    MessageType,
    PlatformMetadata,
    register_platform_adapter,
    
    # 消息组件
    Plain,
    Face,
    Image,
    File,
    At,
    # ... 其他消息组件
)
```

---

## 二、按模块分类

### 2.1 Star 相关（插件核心）

**导入路径**: `from astrbot.api.star import ...`

| 名称 | 类型 | 说明 |
|------|------|------|
| `Context` | 类 | 插件上下文，提供各种 API 访问 |
| `Star` | 类 | 插件基类 |
| `StarTools` | 类 | 插件工具集 |
| `register` | 装饰器 | 注册插件 (`@register_star`) |

```python
from astrbot.api.star import Context, Star, register

@register
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
```

### 2.2 Event 相关（事件与消息）

**导入路径**: `from astrbot.api.event import ...`

| 名称 | 类型 | 说明 |
|------|------|------|
| `AstrMessageEvent` | 类 | AstrBot 消息事件 |
| `MessageEventResult` | 类 | 事件处理结果 |
| `MessageChain` | 类 | 消息链（可迭代多个组件） |
| `CommandResult` | 类 | 命令执行结果 |
| `EventResultType` | 枚举 | 事件结果类型 |
| `ResultContentType` | 枚举 | 结果内容类型 |

```python
from astrbot.api.event import (
    AstrMessageEvent,
    MessageEventResult,
    MessageChain,
    CommandResult,
    EventResultType,
)
```

### 2.3 Event Filter（过滤器与装饰器）

**导入路径**: `from astrbot.api.event.filter import ...`

#### 过滤器类

| 名称 | 类型 | 说明 |
|------|------|------|
| `EventMessageTypeFilter` | 类 | 按消息类型过滤 |
| `PlatformAdapterTypeFilter` | 类 | 按平台适配器类型过滤 |
| `PermissionTypeFilter` | 类 | 按权限类型过滤 |
| `CustomFilter` | 类 | 自定义过滤器基类 |

#### 枚举类型

| 名称 | 类型 | 说明 |
|------|------|------|
| `EventMessageType` | 枚举 | 事件消息类型 |
| `PlatformAdapterType` | 枚举 | 平台适配器类型 |
| `PermissionType` | 枚举 | 权限类型 |

#### 装饰器（按执行时机）

| 装饰器 | 说明 |
|--------|------|
| `@command` | 注册命令 |
| `@command_group` | 注册命令组 |
| `@regex` | 注册正则匹配 |
| `@event_message_type` | 按消息类型注册 |
| `@platform_adapter_type` | 按平台类型注册 |
| `@custom_filter` | 自定义过滤器 |
| `@permission_type` | 按权限注册 |
| `@llm_tool` | 注册 LLM 工具 |
| `@on_llm_request` | LLM 请求前触发 |
| `@on_llm_response` | LLM 响应后触发 |
| `@on_llm_tool_respond` | LLM 工具响应时触发 |
| `@on_using_llm_tool` | 使用 LLM 工具时触发 |
| `@on_waiting_llm_request` | 等待 LLM 请求时触发 |
| `@on_agent_begin` | Agent 开始执行时触发 |
| `@on_agent_done` | Agent 完成执行时触发 |
| `@on_plugin_loaded` | 插件加载后触发 |
| `@on_plugin_unloaded` | 插件卸载后触发 |
| `@on_plugin_error` | 插件错误时触发 |
| `@on_platform_loaded` | 平台加载后触发 |
| `@on_astrbot_loaded` | AstrBot 加载后触发 |
| `@on_decorating_result` | 装饰结果时触发 |
| `@after_message_sent` | 消息发送后触发 |

```python
from astrbot.api.event.filter import command, on_llm_request

@command("test")
async def test_command(self, event):
    pass

@on_llm_request
async def before_llm(self, event):
    pass
```

### 2.4 Provider 相关（模型提供商）

**导入路径**: `from astrbot.api.provider import ...`

| 名称 | 类型 | 说明 |
|------|------|------|
| `Provider` | 类 | Provider 基类 |
| `STTProvider` | 类 | 语音转文字 Provider |
| `ProviderMetaData` | 类 | Provider 元数据 |
| `ProviderRequest` | 类 | Provider 请求 |
| `LLMResponse` | 类 | LLM 响应 |
| `ProviderType` | 枚举 | Provider 类型 |
| `Personality` | 类 | 人格配置 |

```python
from astrbot.api.provider import (
    Provider,
    ProviderMetaData,
    ProviderRequest,
    LLMResponse,
    ProviderType,
)
```

### 2.5 Platform 相关（平台适配）

**导入路径**: `from astrbot.api.platform import ...`

| 名称 | 类型 | 说明 |
|------|------|------|
| `Platform` | 类 | 平台基类 |
| `AstrBotMessage` | 类 | AstrBot 消息 |
| `AstrMessageEvent` | 类 | AstrBot 消息事件 |
| `MessageMember` | 类 | 消息成员 |
| `MessageType` | 枚举 | 消息类型 |
| `PlatformMetadata` | 类 | 平台元数据 |
| `Group` | 类 | 群组 |
| `register_platform_adapter` | 装饰器 | 注册平台适配器 |

```python
from astrbot.api.platform import (
    Platform,
    AstrBotMessage,
    MessageMember,
    MessageType,
    PlatformMetadata,
    register_platform_adapter,
)
```

### 2.6 消息组件

**导入路径**: `from astrbot.api.message_components import ...`

| 组件 | 说明 |
|------|------|
| `Plain` | 纯文本 |
| `Face` | 表情 |
| `Image` | 图片 |
| `File` | 文件 |
| `At` | @某人 |
| `AtAll` | @所有人 |
| `Reply` | 回复 |
| `Record` | 语音 |
| `Video` | 视频 |
| `Share` | 分享 |
| `Location` | 位置 |
| `Music` | 音乐 |
| `Json` | JSON 消息 |
| `Node` | 合并转发节点 |
| `Nodes` | 合并转发 |
| `RPS` | 石头剪刀布 |
| `Dice` | 骰子 |
| `Shake` | 戳一戳 |
| `Contact` | 名片 |
| `Poke` | 窗口抖动 |
| `Forward` | 转发 |
| `Unknown` | 未知消息 |

```python
from astrbot.api.message_components import Plain, Image, At

chain = [
    Plain(text="Hello"),
    At(user_id="123456"),
    Image(url="https://example.com/img.jpg"),
]
```

### 2.7 Util 工具

**导入路径**: `from astrbot.api.util import ...`

| 名称 | 类型 | 说明 |
|------|------|------|
| `SessionWaiter` | 类 | 会话等待器 |
| `SessionController` | 类 | 会话控制器 |
| `session_waiter` | 装饰器 | 注册会话等待 |

```python
from astrbot.api.util import session_waiter, SessionController

@session_waiter(timeout=60)
async def wait_for_reply(self, event):
    pass
```

---

## 三、常用导入场景

### 场景 1: 编写基础插件

```python
from astrbot.api import logger
from astrbot.api.star import Context, Star, register
from astrbot.api.event import AstrMessageEvent, MessageEventResult
from astrbot.api.event.filter import command

@register
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
    
    @command("hello")
    async def hello(self, event: AstrMessageEvent):
        logger.info(f"收到消息: {event.message_str}")
        yield event.make_result().message("Hello World!")
```

### 场景 2: 使用消息组件

```python
from astrbot.api.event import AstrMessageEvent
from astrbot.api.message_components import Plain, Image, At

async def send_rich_message(event: AstrMessageEvent):
    chain = [
        Plain(text="这是一条富文本消息\n"),
        At(user_id=event.get_sender_id()),
        Plain(text="\n请看这张图片:\n"),
        Image(url="https://example.com/pic.png"),
    ]
    yield event.make_result().message(chain)
```

### 场景 3: 注册 LLM 工具

```python
from astrbot.api import llm_tool
from astrbot.api.star import Context, Star, register

@register
class ToolPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
    
    @llm_tool
    async def get_time(self) -> str:
        """获取当前时间"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
```

### 场景 4: 使用过滤器

```python
from astrbot.api.event.filter import (
    command,
    event_message_type,
    EventMessageType,
)

@command("group_test")
@event_message_type(EventMessageType.GROUP)
async def group_only(self, event):
    """仅在群聊中生效"""
    yield event.make_result().message("这是群聊命令")
```

### 场景 5: 监听事件

```python
from astrbot.api.event.filter import (
    on_llm_request,
    on_plugin_loaded,
    on_astrbot_loaded,
)

@on_llm_request
async def before_llm_request(self, event):
    """在 LLM 请求前修改"""
    # 可以在这里修改 system_prompt 或 prompt
    pass

@on_plugin_loaded
async def on_my_plugin_loaded(self):
    """插件加载完成后"""
    pass

@on_astrbot_loaded
async def on_astrbot_ready(self):
    """AstrBot 完全启动后"""
    pass
```

---

## 四、完整导入路径表

| 类别 | 导入语句 |
|------|---------|
| **配置** | `from astrbot.api import AstrBotConfig` |
| **日志** | `from astrbot.api import logger` |
| **Star** | `from astrbot.api.star import Context, Star, register` |
| **事件** | `from astrbot.api.event import AstrMessageEvent, MessageEventResult, ...` |
| **过滤器** | `from astrbot.api.event.filter import command, regex, ...` |
| **装饰器** | `from astrbot.api.event.filter import llm_tool, on_llm_request, ...` |
| **Provider** | `from astrbot.api.provider import Provider, ProviderRequest, ...` |
| **Platform** | `from astrbot.api.platform import Platform, AstrBotMessage, ...` |
| **消息组件** | `from astrbot.api.message_components import Plain, Image, ...` |
| **工具** | `from astrbot.api.util import SessionWaiter, session_waiter` |
| **一键导入** | `from astrbot.api.all import *` |

---

## 五、注意事项

1. **`logger` 是特殊对象**：它会自动路由到调用插件的专用日志器，无需配置
2. **`from astrbot.api.all import *`** 方便但不推荐在生产代码中使用，可能导致命名冲突
3. **装饰器必须在方法上使用**：`@command`、`@llm_tool` 等必须装饰在 Star 类的方法上
4. **Context 必须通过 `__init__` 接收**：不要自己创建 Context 实例
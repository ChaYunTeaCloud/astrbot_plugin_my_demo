# AstrBot-Tool

## 一、Tool 是什么

Tool（工具）是让 LLM（大语言模型）能够**调用外部功能**的机制。类似于 ChatGPT 的 Function Calling，你可以定义一个工具，告诉 LLM "当用户问天气时，可以调用这个工具来获取天气信息"。

在 AstrBot 中，Tool 的本质是一个 `FunctionTool` 类。所有工具（包括内置工具、MCP 工具、插件工具）最终都是 `FunctionTool` 实例，存储在 `llm_tools.func_list` 中。

注册工具的方式：
- 继承 `FunctionTool[AstrAgentContext]` 类：灵活，支持完整的 JSON Schema 定义（官方推荐）
- `@filter.llm_tool` 装饰器：简洁，框架自动从 docstring 解析参数 schema（官方推荐）
- 手动创建 `FunctionTool(handler=...)`：灵活但需注意 handler 绑定，非官方推荐
- 动态注入（`@filter.on_llm_request` + `req.func_tool.add_tool()`）：按需注册，工具不暴露给全局，仅在特定请求中生效

## 二、核心类

### 1. ToolSchema（工具模式）

**文件**：../.venv/Lib/site-packages/astrbot/core/agent/tool.py#L20

定义工具的基本结构：
- `name`：工具名称
- `description`：工具描述（LLM 根据这个判断何时调用）
- `parameters`：参数的 JSON Schema

### 2. FunctionTool（函数工具）

**文件**：../.venv/Lib/site-packages/astrbot/core/agent/tool.py#L41

继承 `ToolSchema`，添加：
- `handler`：实际执行的异步函数
- `active`：是否激活
- `is_background_task`：是否为后台任务

### 3. ToolSet（工具集合）

**文件**：../.venv/Lib/site-packages/astrbot/core/agent/tool.py#L78

管理多个工具的集合，支持：
- 添加/删除/获取工具
- 转换为不同 LLM API 格式（OpenAI、Anthropic、Google GenAI）

## 三、@llm_tool 装饰器规则（重要）

### handler 参数规则

使用 `@llm_tool` 装饰器注册的工具，其 handler 函数的第一个参数固定是 `event: AstrMessageEvent`，后面才是工具的业务参数。

**重要**：`event` 不需要写在 `Args:` 中，因为它是框架自动注入的，不是 LLM 需要提供的参数。`Args:` 只用于描述 LLM 需要知道的业务参数。

```python
from astrbot.api.event import AstrMessageEvent

@llm_tool(name="my_tool")
async def my_tool_handler(self, event: AstrMessageEvent, param1: str, param2: int = 0) -> str:
    """工具描述
    
    Args:
        param1: 业务参数1
        param2: 业务参数2
    """
    # 可以通过 event 获取发送者、群信息等
    sender = event.get_sender()
    group_id = event.get_group_id()
    ...
    return "结果"
```bash

### 为什么 event 不在 Args 中？

因为 `event` 是框架在调用 handler 时自动从上下文中提取并注入的（见 `func_tool_manager.py#L254-L255`）：

```python
event = context.context.event
result = self._wrapped.handler(event, **kwargs)  # kwargs 才是 LLM 提供的业务参数
```json

如果把 `event` 写在 `Args:` 中，会导致 LLM 误认为需要提供这个参数，造成错误。

这与继承 `FunctionTool` 类的方式不同（后者通过 `context` 参数传递上下文）。

## 四、parameters 参数规则

`parameters` 是工具的参数 schema，用于描述工具的输入参数。它是一个 JSON Schema 对象，LLM 根据它来决定怎么调用你的工具。

### 基本结构

```python
parameters = {
    "type": "object",  # 必须是 object
    "properties": {
        "city": {
            "type": "string",
            "description": "城市名称"
        },
        "date": {
            "type": "string",
            "description": "日期",
            "format": "date-time"  # 可选
        }
    },
    "required": ["city"]  # 可选，必填字段列表
}
```json

### 常见类型

| type | 说明 | 示例 |
|------|------|------|
| `string` | 字符串 | `"hello"` |
| `number` | 浮点数 | `3.14` |
| `integer` | 整数 | `42` |
| `boolean` | 布尔值 | `true/false` |
| `array` | 数组 | `["a", "b"]` |
| `object` | 对象 | `{"key": "value"}` |

### 验证机制

`ToolSchema.validate_parameters()` 会验证 `parameters` 是否符合 JSON Schema 规范（文件：../.venv/Lib/site-packages/astrbot/core/agent/tool.py#L32）。如果随便写，会在创建 `FunctionTool` 时就报错。

## 五、使用方式

### 方式一：使用 @llm_tool 装饰器（推荐）

最简单的方式，框架自动完成注册和参数解析。

```python
from astrbot.api import llm_tool
from astrbot.api.event import AstrMessageEvent

class MyPlugin(Star):
    @llm_tool(name="get_weather")
    async def get_weather(self, event: AstrMessageEvent, city: str, date: str = "") -> str:
        """获取指定城市的天气信息
        
        Args:
            city: 城市名称
            date: 日期
        """
        weather = await fetch_weather(city, date)
        return f"{city}今天{weather}"
```bash

框架会自动：
1. 从装饰器参数中获取名称
2. 从函数注释中解析参数描述
3. 注册到 `star_handlers_registry`
4. 在 LLM 请求时自动添加到工具集

### 方式二：继承 FunctionTool 类

更灵活的方式，支持完整的 JSON Schema 定义和 `required` 字段。有两种写法可选：

#### 方案 A：使用 @dataclass（官方推荐）

```python
from pydantic import Field
from pydantic.dataclasses import dataclass
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext

@dataclass
class WeatherTool(FunctionTool[AstrAgentContext]):
    name: str = "get_weather"
    description: str = "获取指定城市的天气信息"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称"},
                "date": {"type": "string", "description": "日期（可选）"}
            },
            "required": ["city"]
        }
    )
    
    async def call(
        self, 
        context: ContextWrapper[AstrAgentContext], 
        **kwargs
    ) -> ToolExecResult:
        city = kwargs.get("city", "北京")
        date = kwargs.get("date", "")
        weather = await fetch_weather(city, date)
        return f"{city}今天{weather}"
```bash

#### 方案 B：使用 __init__（两种方案等价）

```python
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext

class WeatherTool(FunctionTool[AstrAgentContext]):
    def __init__(self):
        super().__init__(
            name="get_weather",
            description="获取指定城市的天气信息",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称"},
                    "date": {"type": "string", "description": "日期（可选）"}
                },
                "required": ["city"]
            }
        )
    
    async def call(
        self, 
        context: ContextWrapper[AstrAgentContext], 
        **kwargs
    ) -> ToolExecResult:
        city = kwargs.get("city", "北京")
        date = kwargs.get("date", "")
        weather = await fetch_weather(city, date)
        return f"{city}今天{weather}"
```bash

#### 两种方案的区别

| 特性 | 方案 A（@dataclass） | 方案 B（__init__） |
|------|---------------------|-------------------|
| 代码风格 | 声明式，用类属性定义字段 | 命令式，在 __init__ 中赋值 |
| 代码量 | 更简洁 | 稍冗长 |
| 功能等价 | 是 | 是 |

**两种方案功能完全等价**，`@dataclass` 会自动生成 `__init__` 方法。

### 方式三：手动创建 FunctionTool

如果你有特殊需求，可以手动创建 `FunctionTool` 并注册。

> **说明**：此方式是框架底层 API 支持的用法，官方文档中仅推荐方式一（`@dataclass` 继承）和方式二（`@llm_tool` 装饰器）。方式三提供了更灵活的控制，但需要手动处理 handler 的绑定问题（见下方注意事项）。
官方文档中 没有 提到手动创建 FunctionTool(handler=...) 并通过 self.context.add_llm_tools() 注册的方式。方式三是框架底层 API 支持的用法，但不是官方推荐的方式。

```python
from astrbot.api import FunctionTool
from astrbot.api.event import AstrMessageEvent

class MyPlugin(Star):
    def __init__(self, context):
        super().__init__(context)
        
        weather_tool = FunctionTool(
            name="get_weather",
            description="获取指定城市的天气信息",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称"},
                    "date": {"type": "string", "description": "日期（可选）"}
                },
                "required": ["city"]
            },
            handler=MyPlugin._get_weather_handler  # 必须传未绑定的类方法，不能是 self._get_weather_handler
        )
        
        # 注册到框架
        self.context.add_llm_tools(weather_tool)
    
    async def _get_weather_handler(self, event: AstrMessageEvent, city: str, date: str = "") -> str:
        """实际的 handler，第一个参数是 event"""
        weather = await fetch_weather(city, date)
        return f"{city}今天{weather}"
```text
**注意**：通过 `handler` 参数传入的函数，第一个参数必须是 `event`，这与 `@llm_tool` 装饰器的 handler 签名相同。且工具 handler 必须是类的方法 ，这样框架才能把插件实例绑定为第一个参数（self），让 handler 内部可以通过 self 访问插件的其他方法和属性。如果想用全局函数，唯一的办法是让它的第一个参数接收插件实例，但这样做既不优雅，也失去了面向对象的优势，不建议使用。

**重要**：handler 必须传入**未绑定的类方法**（`MyPlugin._get_weather_handler`），不能传入绑定方法（`self._get_weather_handler`）。

**原因**：框架在插件加载后会执行 handler 的重新绑定逻辑（见 star_manager.py#L1273-1298）。它会检查 `handler.__module__` 是否属于当前插件模块，如果是，则用 `functools.partial(handler, star_cls)` 把插件实例绑定为第一个参数（self）。

- 传入未绑定类方法 `MyPlugin._get_weather_handler`：partial 绑定后调用 `func(star_cls, event, **kwargs)`，self ← star_cls，event ← event，参数正确
- 传入绑定方法 `self._get_weather_handler`：partial 绑定后调用 `bound_method(star_cls, event, **kwargs)`，由于 self 已绑定，star_cls 会被当作 event，导致参数全部错位

这与 `@llm_tool` 装饰器的处理路径一致：装饰器注册时 handler 是未绑定函数，由框架在加载时统一绑定实例。

#### 绑定逻辑详细说明

不能传入：传入绑定方法 `self._get_weather_handler`的具体原因，
          
经过深入源码分析，**这种写法有问题**。让我解释原因。

##### 问题所在

假设传入的是 `handler=self._get_weather_handler`（绑定方法）。

../.venv/Lib/site-packages/astrbot/core/star/star_manager.py#L1273-1298 在每次插件加载后，会执行一段"handler 重新绑定"的修正逻辑：

```python
# star_manager.py#L1276-1298
if ft.handler and (
    getattr(ft.handler, "__module__", None) == metadata.module_path
    ...
):
    raw_handler = ft.handler.func if isinstance(ft.handler, functools.partial) else ft.handler
    ft.handler_module_path = metadata.module_path
    ft.handler = raw_handler
    if not plugin_disabled and metadata.star_cls is not None:
        ft.handler = functools.partial(raw_handler, metadata.star_cls)  # 关键问题
```text

这段逻辑的设计目的是为 `@llm_tool` 装饰器注册的**未绑定函数**服务的——把插件实例通过 `functools.partial` 绑定为第一个参数（self）。

##### 为什么会出错

当 `handler=self._get_weather_handler`（绑定方法）时：

1. `self._get_weather_handler.__module__` == 插件模块路径 → 匹配修正条件
2. 修正后：`ft.handler = functools.partial(self._get_weather_handler, star_cls)`
3. 工具被调用时（../.venv/Lib/site-packages/astrbot/core/provider/func_tool_manager.py#L253-255）：
```text
   handler(event, city="北京")
   = partial(self._get_weather_handler, star_cls)(event, city="北京")
   = self._get_weather_handler(star_cls, event, city="北京")
```text
4. 由于 `self._get_weather_handler` 已是绑定方法（self 已绑定），实际等价于：
```text
   _get_weather_handler(self, star_cls, event, "北京")
```text
   签名 `(self, event, city, date="")` 收到的是：
   - `event` ← `star_cls`（插件实例，类型错！）
   - `city` ← `event`（AstrMessageEvent，类型错！）
   - `date` ← `"北京"`

**参数全部错位**，运行时会因类型不匹配而报错。

##### 正确写法

handler 必须传入**未绑定**的类方法，让框架通过 `functools.partial` 完成实例绑定：

```python
handler=MyPlugin._get_weather_handler  # 未绑定的类方法，不是 self._get_weather_handler
```text

##### 总结

此写法 `handler=self._get_weather_handler`（绑定方法）是**错误的**。

核心原因在于 ../.venv/Lib/site-packages/astrbot/core/star/star_manager.py#L1273-1298 的 handler 重新绑定逻辑：

| 传入方式 | partial 绑定后调用 | 结果 |
|---------|-------------------|------|
| `MyPlugin._get_weather_handler`（未绑定） | `func(star_cls, event, **kwargs)` | self←star_cls, event←event ✓ |
| `self._get_weather_handler`（绑定方法） | `bound_method(star_cls, event, **kwargs)` | self 已绑定，star_cls 被当作 event ✗ |

这段修正逻辑是 `@llm_tool` 装饰器处理路径的一部分：装饰器注册时 handler 是未绑定函数，框架在插件加载时统一用 `functools.partial` 绑定插件实例。手动创建 FunctionTool 走的是同一条路径，所以 handler 也必须是未绑定的类方法。

文档已改为 `handler=MyPlugin._get_weather_handler` 并补充了原因说明。

## 六、Handler 返回值

工具 handler 的返回值有两种形式，框架会采用不同的处理策略。

### 6.1 两种返回值类型

工具 handler 的返回值支持两种形式：

| 返回值类型 | 说明 | 处理方式 |
|-----------|------|---------|
| `str` / `None` | 普通字符串 | 被包装成 `TextContent` 返回给 LLM，由 LLM 决定怎么回复用户 |
| `AsyncGenerator[MessageEventResult, None]` | 异步生成器，产出消息链 | 直接发送给用户，同时通知 LLM "工具已直接发送消息" |

`MessageEventResult` 是 AstrBot 的 消息链对象 ，继承自 `MessageChain` ，可以包含文本、图片、@等多种消息组件。

从 ../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py#L660-693 可以看到:

- 如果返回的是 str ：框架会把它包装成 mcp.types.TextContent 返回给 LLM，LLM 再决定怎么回复用户
- 如果返回的是 MessageEventResult （通过 yield ）：框架会 直接把消息发送给用户 （ event.send() ），同时 yield None 告诉 Agent Loop "工具已经直接发消息了，不用再让 LLM 回复了"

### 6.2 返回 str（常用）

最简单的方式，适合大多数工具场景。

```python
@llm_tool(name="get_weather")
async def get_weather(self, event: AstrMessageEvent, city: str) -> str:
    """获取天气"""
    weather = await fetch_weather(city)
    return f"{city}今天{weather}"  # 返回字符串
```bash

框架会把返回的字符串包装成 `TextContent` 返回给 LLM，LLM 拿到结果后再回复用户。

### 6.3 返回 MessageEventResult（高级）

当需要工具**直接给用户发消息**时使用，典型场景：
- 工具执行时间长，需要先给用户一个"正在处理"的提示
- 需要发送富文本消息（图片、卡片等）
- 不想让 LLM 再加工工具结果，直接展示给用户

```python
@llm_tool(name="get_weather")
async def get_weather(self, event: AstrMessageEvent, city: str) -> AsyncGenerator[MessageEventResult, None]:
    """获取天气"""
    yield event.plain_result("正在查询天气...")  # 先给用户一个提示
    weather = await fetch_weather(city)
    yield event.plain_result(f"{city}今天{weather}")  # 直接把结果发给用户
```text

当 handler 是异步生成器时，框架会：
1. 每次 `yield` 的 `MessageEventResult` 都直接发送给用户（`event.send()`）
2. yield `None` 告诉 Agent Loop "工具已经直接发消息了，不用再让 LLM 回复了"

### 6.4 两种返回值对比

| 维度 | `str` 返回值 | `MessageEventResult` 返回值 |
|------|-------------|---------------------------|
| 复杂度 | 简单 | 较复杂 |
| 消息流向 | 工具 → LLM → 用户 | 工具 → 用户 |
| 适用场景 | 大多数工具 | 需要直接交互的工具 |
| LLM 感知 | LLM 能看到结果并加工 | LLM 收到通知，不再回复 |
| 流式支持 | 不支持 | 支持（可多次 yield） |

**简单工具用 `str` 返回值就行，复杂交互场景才需要 `MessageEventResult`。**

> `MessageEventResult` 的详细接口说明参见 `AstrBot-Event 模块接口整理.md`。

### 6.5 set_result vs plain_result：不要混淆

`event.set_result()` 和 `event.plain_result()` 名字相似，但用途完全不同。

#### 工具 Handler 的返回值处理逻辑

框架对工具 Handler 和普通 Handler 的返回值处理方式不同：

| 维度 | 工具 Handler（@llm_tool） | 普通 Handler（@command 等） |
|------|-------------------------|---------------------------|
| 结果读取方式 | 直接看函数返回值 | 从 `event._result` 中读取 |
| `set_result` 是否有效 | 无效（返回 `None`） | 有效（设置 `event._result`） |
| `return plain_result(...)` | 有效（框架识别为 MessageEventResult） | 有效，但通常用 `set_result` |
| `yield plain_result(...)` | 有效（异步生成器） | 不支持 |

#### 场景一：`return event.plain_result(...)`

类型注解不决定行为，实际返回值的类型才决定行为。即使你注解了 `-> str`，只要实际返回的是 `MessageEventResult`，框架就会直接发给用户。

```python
@llm_tool(name="test")
async def test_tool(self, event, city) -> str:  # 注解是 str，但不影响
    return event.plain_result(f"{city}晴")  # 实际返回 MessageEventResult
```bash

框架用 `isinstance(ret, MessageEventResult)` 检查实际返回值，不看类型注解。

#### 场景二：只调用 `event.plain_result()` 但不 yield/return

`event.plain_result()` 只是**创建**了一个 `MessageEventResult` 对象，并没有发送。如果你不 yield 或 return 它，这个对象就被丢弃了。

```python
@llm_tool(name="test")
async def test_tool(self, event, city) -> str:
    event.plain_result("正在处理...")  # 创建了对象但没用，被丢弃
    return f"{city}晴"  # 实际返回 str，走 LLM 处理
```text

#### 三种写法对比

| 写法 | 实际返回值 | 框架行为 |
|------|----------|---------|
| `return "结果"` | `str` | 包装成 TextContent → LLM → 用户 |
| `return event.plain_result("结果")` | `MessageEventResult` | 直接发给用户，跳过 LLM |
| `event.plain_result("提示")` + `return "结果"` | `str` | plain_result 被丢弃，走 LLM 处理 |

#### 混合 yield 和 return

如果想先发提示给用户，再把结果交给 LLM 处理，可以混合使用 `yield` 和 `return`：

```python
async def test_tool(self, event, city):
    yield event.plain_result("正在处理...")  # 先发给用户
    result = await do_something(city)
    return result  # 返回给 LLM，由 LLM 转述给用户
```bash

框架会先通过 `yield` 发送消息给用户，然后通过 `return` 把结果交给 LLM 处理。

如果不写 yield，`event.plain_result("提示")` 就只是创建了一个 MessageEventResult 对象，但这个对象没有被赋值给任何变量，也没有被 return/yield，Python 会立即回收它。相当于这行代码什么都没做，属于无效代码。


#### set_result 在工具 Handler 中无效

```python
# 错误：set_result 返回 None，框架看不到 MessageEventResult
async def bad_tool(self, event, city):
    event.set_result(event.plain_result("结果"))
    return  # 等价于 return None

# 正确：直接 return MessageEventResult
async def good_tool(self, event, city):
    return event.plain_result("结果")

# 正确：yield MessageEventResult
async def good_tool_async(self, event, city):
    yield event.plain_result("结果")
```bash

#### set_result 的正确用法

`set_result` 应在非工具 Handler 中使用（如 `@filter.command`），框架会从 `event._result` 中读取结果：

```python
@filter.command("ban")
async def ban_handler(self, event):
    event.set_result(
        MessageEventResult()
            .message("你已被拉黑")
            .set_result_type(EventResultType.STOP)
    )
    return
```bash

### 6.6 什么时候需要用 MessageEventResult？

当你希望工具直接给用户发消息，而不是把结果返回给 LLM 让 LLM 转述时。典型场景：

- 工具执行时间长，需要先给用户一个"正在处理"的提示
- 需要发送富文本消息（图片、卡片等）
- 不想让 LLM 再加工工具结果，直接展示给用户

```python
# 返回 str：LLM 拿到结果后再回复用户
async def my_tool(self, event, query) -> str:
    return "查询结果：..."  # LLM 会把这个内容转述给用户

# 返回 MessageEventResult：工具直接发消息给用户
async def my_tool(self, event, query) -> AsyncGenerator[MessageEventResult, None]:
    yield event.plain_result("正在查询...")  # 先给用户一个提示
    result = await do_query(query)
    yield event.plain_result(f"查询结果：{result}")  # 直接把结果发给用户
```bash
简单工具用 str 返回值就行，复杂交互场景才需要 MessageEventResult 。

## 七、上下文相关类

继承 `FunctionTool` 时，需要理解几个上下文相关类。`@llm_tool` 方式不需要直接操作这些类。

### @dataclass 是什么？

`@dataclass` 是装饰器，用于将类转换为**数据类**。AstrBot 使用的是 Pydantic 版本（`from pydantic.dataclasses import dataclass`），它扩展了 Python 标准库的 dataclass，提供更强的数据验证能力。

使用 `@dataclass` 后，你可以直接在类体中用**类型注解 + 默认值**的方式定义字段，而不需要手动调用 `super().__init__()`。

### AstrAgentContext 是什么？

`AstrAgentContext` 是专门为 Tool 设计的上下文包装类，包含：

```python
@dataclass
class AstrAgentContext:
    context: Context          # 完整的 Star Context（配置、LLM 调用等）
    event: AstrMessageEvent   # 关联的消息事件
    extra: dict[str, str]     # 自定义扩展数据
```bash

### ContextWrapper 是什么？

`ContextWrapper` 是包裹 `AstrAgentContext` 的**外层容器**，额外提供了对话历史和超时控制功能。它是 Tool 的 `call` 方法实际接收的参数类型。

**文件**：../.venv/Lib/site-packages/astrbot/core/agent/run_context.py#L12

```python
@dataclass
class ContextWrapper(Generic[TContext]):
    context: TContext              # 被包装的上下文（AstrAgentContext）
    messages: list[Message]        # LLM 对话历史（由 Agent Runner 自动维护）
    tool_call_timeout: int = 120   # 工具调用超时时间（秒）
```bash

| 字段 | 用途 | 说明 |
|------|------|------|
| `context` | `AstrAgentContext` | 通过它可以访问 `Context` 和 `event` |
| `messages` | LLM 对话历史 | 由 Agent Runner 自动维护，用于上下文对话 |
| `tool_call_timeout` | 超时控制 | 控制工具调用的最大等待时间 |

**与 AstrAgentContext 的关系**：
- `ContextWrapper` 是外层容器，`context` 字段存储 `AstrAgentContext`
- 访问业务上下文需要通过 `context.context`（第一个是 ContextWrapper 的字段，第二个是 AstrAgentContext 的字段）

**对插件开发者来说，`ContextWrapper` 的主要用途确实是间接获取 `context` 和 `event`**。`messages` 和 `tool_call_timeout` 是框架额外提供的能力，大多数场景下用不到。

### 为什么使用泛型而不是直接传参？

`ContextWrapper` 使用了 `Generic[TContext]` 泛型设计，而不是直接固定为 `AstrAgentContext`。原因如下：

**框架扩展性**

框架内部接口（如 `BaseAgentRunner`、`BaseAgentRunHooks`）使用 `ContextWrapper[TContext]`，可以接受任意上下文类型。如果未来需要新增其他类型的 Agent（如不需要上下文的轻量 Agent），无需修改框架代码。

```python
# run_context.py#L22 - 预定义了无上下文的变体
NoContext = ContextWrapper[None]
```bash

**类型安全**

明确指定类型后（如 `ContextWrapper[AstrAgentContext]`），IDE 能正确推断 `context.context` 的类型，提供代码补全和错误检查。

**实际使用的类型**

| 类型 | 使用场景 |
|------|---------|
| `ContextWrapper[AstrAgentContext]` | 主流用法，所有插件工具和内置工具 |
| `ContextWrapper[None]` | `NoContext`，用于不需要上下文的场景 |
| `ContextWrapper[TContext]` | 泛型占位，用于框架内部接口定义 |

**对插件开发者的影响**

你不需要关心泛型设计的细节，直接使用 `ContextWrapper[AstrAgentContext]` 即可。泛型主要是框架层面的设计，为未来扩展预留空间。

### FunctionTool 的泛型设计

`FunctionTool` 同样使用了 `Generic[TContext]` 泛型设计，与 `ContextWrapper` 的思路完全一致。

**文件**：../.venv/Lib/site-packages/astrbot/core/agent/tool.py#L39

```python
class FunctionTool(ToolSchema, Generic[TContext]):
    async def call(self, context: ContextWrapper[TContext], **kwargs) -> ToolExecResult:
```text

**作用**：
- `TContext` 指定 `call` 方法接收的上下文类型
- 实际使用时指定为 `AstrAgentContext`，即 `FunctionTool[AstrAgentContext]`

**与 ContextWrapper 泛型的关系**：
- 两者配合使用：`FunctionTool[AstrAgentContext]` 的 `call` 方法接收 `ContextWrapper[AstrAgentContext]` 类型的参数
- 泛型参数在两层之间传递：`FunctionTool` 的 `TContext` 决定了 `ContextWrapper` 内包装的上下文类型

**为什么要做泛型而不是直接传参？**

与 `ContextWrapper` 相同的原因：
- **框架扩展性**：未来可支持其他上下文类型（如无上下文的轻量工具）
- **类型安全**：IDE 能正确推断 `call` 方法参数的类型

**实际使用**

```python
# 插件开发时直接指定 AstrAgentContext
class WeatherTool(FunctionTool[AstrAgentContext]):
    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
        ...
```text

**泛型设计总结**

| 类 | 泛型参数 | 实际使用 |
|---|---------|---------|
| `ContextWrapper[TContext]` | 被包装的上下文类型 | `AstrAgentContext` |
| `FunctionTool[TContext]` | `call` 方法接收的上下文类型 | `AstrAgentContext` |

两者配合：`FunctionTool[AstrAgentContext]` → `call(context: ContextWrapper[AstrAgentContext])`

对插件开发者来说，直接指定 `AstrAgentContext` 即可，无需关心泛型设计的细节。

### 上下文类的生命周期

#### ContextWrapper 每次 Agent 运行都创建新实例

每次 Agent 运行时，框架都会创建新的 `ContextWrapper` 实例，包装 `AstrAgentContext`：

```python
# context.py#L312 - tool_loop_agent 中
run_context=AgentContextWrapper(
    context=agent_context,        # 包装 AstrAgentContext
    tool_call_timeout=tool_call_timeout,  # 设置超时时间
)
```text

创建位置有三处：
- `Context.tool_loop_agent()` 方法中
- 主 Agent（`AstrMainAgent`）中
- 第三方 Agent（`ThirdPartyAgent`）中

**AgentContextWrapper 是 ContextWrapper[AstrAgentContext] 的别名**

```python
# astr_agent_context.py#L21
AgentContextWrapper = ContextWrapper[AstrAgentContext]
```bash

#### AstrAgentContext 每次调用都创建新实例

每次工具调用时，框架都会创建新的 `AstrAgentContext` 实例，包装当前的 `event`：

```python
# context.py#L287
agent_context = AstrAgentContext(
    context=self,   # 传入单例的 Context
    event=event,    # 传入当前的消息事件
    # extra 使用默认值 {}
)
```bash

创建位置有三处：
- `Context.tool_loop_agent()` 方法中
- 主 Agent（`AstrMainAgent`）中
- 第三方 Agent（`ThirdPartyAgent`）中

#### Context 是单例的

`Context` 在 AstrBot 启动时创建一次，所有插件共享：

```python
# core_lifecycle.py#L227
self.star_context = Context(
    self.event_queue,
    self.astrbot_config,
    self.db,
    self.provider_manager,
    ...
)
```bash

#### extra 是预留给开发者的扩展字段

`extra` 默认为空字典 `{}`，框架目前没有使用它。它的设计意图是让框架内部或插件在需要时可以存储额外信息，但实际中未被框架使用。

#### 生命周期总结

| 类 | 创建时机 | 生命周期 |
|---|---------|---------|
| `Context` | AstrBot 启动时 | 全局单例，整个生命周期不变 |
| `AstrAgentContext` | 每次工具调用时 | 短期，每次调用创建新实例 |
| `ContextWrapper[AstrAgentContext]` | 每次 Agent 运行时 | 短期，每次运行创建新实例 |

层级关系：
```text
ContextWrapper[AstrAgentContext]  ← 每次 Agent 运行创建
    ↓ 包装
AstrAgentContext                  ← 每次工具调用创建
    ↓ 包装
Context                          ← 全局单例
```bash

### 在 Tool 的 call 方法中访问

ContextWrapper 和 AstrAgentContext 都有一个名为 `context` 的字段，容易混淆。完整的访问链路如下：

```python
# 类结构对照
ContextWrapper[AstrAgentContext]:   # call 方法的参数
    context: AstrAgentContext        # ← 第一个 .context
    messages: list[Message]
    tool_call_timeout: int

AstrAgentContext:                    # context.context 的类型
    context: Context                # ← 第二个 .context
    event: AstrMessageEvent
    extra: dict[str, str]
```text

```python
async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
    # context 参数类型是 ContextWrapper[AstrAgentContext]
    # context.context 是 AstrAgentContext（ContextWrapper.context 字段）
    # context.context.context 是 Context（AstrAgentContext.context 字段）
    # context.context.event 是 AstrMessageEvent（AstrAgentContext.event 字段）
    # context.context.extra 是 dict（AstrAgentContext.extra 字段）
    # context.messages 是对话历史（ContextWrapper.messages 字段）
    
    ctx = context.context.context   # 获取原始 Star Context
    event = context.context.event   # 获取当前消息事件
    extra = context.context.extra   # 获取扩展数据
    messages = context.messages     # 获取对话历史
    ...
```bash

## 八、两种方式的对比与选择

### @llm_tool 方式与 ContextWrapper 的关系

使用 `@llm_tool` 装饰器注册的工具，**不需要直接操作 `ContextWrapper`**。

框架会自动从 `ContextWrapper` 中提取 `event`，并直接传给 `handler`（文件：../.venv/Lib/site-packages/astrbot/core/provider/func_tool_manager.py#L252-L255）：

```python
# @filter.llm_tool decorated tools have a handler attribute, which is the actual callable.
if self._wrapped.handler is not None:
    event = context.context.event  # 框架从 ContextWrapper 中提取 event
    result = self._wrapped.handler(event, **kwargs)  # 只传入 event 和业务参数
```bash

因此，`@llm_tool` 方式不需要 `ContextWrapper`，因为：
1. `event` 已通过方法参数传入
   - 框架自动从 `ContextWrapper[AstrAgentContext]` 中提取 `event`
   - 直接传给 handler 的第一个参数
2. `Context` 在 Star 初始化时就有了
   - 通过 `self.context` 访问（Star 基类的属性）
   - 不需要从 `ContextWrapper` 中获取
3. `ContextWrapper` 是框架内部使用的
   - 用于维护对话历史、超时控制等
   - 插件开发者无需直接操作

### @llm_tool 方式如何获取所需信息

| 信息 | 获取方式 |
|------|---------|
| `event`（AstrMessageEvent） | handler 的第一个参数，框架自动传入 |
| `context`（Context） | `self.context`（Star 基类的属性，初始化时已存在） |
| 对话历史 | 不需要（框架内部维护） |
| 工具调用超时 | 不需要（使用默认值） |

### 两种方式的对比

| 方面 | `@llm_tool` 装饰器（推荐） | 继承 `FunctionTool` |
|------|-------------------|---------------------|
| 代码复杂度 | 简洁，无需处理 ContextWrapper | 复杂，需要理解 ContextWrapper 层级 |
| handler 第一个参数 | `event`（AstrMessageEvent） | `context`（ContextWrapper[AstrAgentContext]） |
| 获取 Context | `self.context`（Star 基类） | `context.context.context`（从 ContextWrapper 中提取） |
| 获取 event | 直接通过参数 | `context.context.event` |
| 支持 required 字段 | ❌ 不支持 | ✅ 支持 |
| 获取对话历史 | 不需要 | `context.messages` |
| 获取超时设置 | 不需要 | `context.tool_call_timeout` |

### 什么时候用 @llm_tool？（绝大多数场景）

优先使用 `@llm_tool` 装饰器，因为：
- 代码更简洁
- 不需要处理 `ContextWrapper` 的复杂性
- 直接通过参数获取 `event`
- 通过 `self.context` 获取 `Context`

### 什么时候必须用 FunctionTool？

只有当你需要以下功能时，才使用继承 `FunctionTool` 的方式：
- **需要 `required` 字段限定必填参数**
- **需要复杂参数结构**（嵌套对象、数组、枚举等）
- 需要访问对话历史（`context.messages`）
- 需要控制工具调用超时

否则，`@llm_tool` 已经足够用了，而且更简洁。

## 九、handler 的注册与调用

### 注册方式

`@llm_tool` 装饰器会把 handler 注册为 `LLM_TOOL` 类型的 handler（文件：../.venv/Lib/site-packages/astrbot/core/star/register/star_handler.py#L586）：

```python
def register_llm_tool(name: str | None = None, **kwargs):
    def decorator(awaitable):
        # 解析 docstring，构建参数 schema
        # 注册为 LLM_TOOL 类型的 handler
        register_handler(
            func,
            handler_type=HandlerType.LLM_TOOL,
            name=name,
            desc=desc,
        )
        return func
    return decorator
```bash

### 调用方式

Tool 的 handler 不是通过 `call_event_hook()` 或 `call_handler()` 调用的，而是通过 **Agent 执行链**调用。

调用链路：
```text
Pipeline → ProcessStage
    ↓
检测到 LLM 返回了 tool_call
    ↓
ToolLoopAgentRunner 开始执行
    ↓
从 star_handlers_registry 中查找 LLM_TOOL 类型的 handler
    ↓
找到对应的 FunctionTool
    ↓
调用 FunctionTool.call(context, **parameters)
    ↓
返回结果给 LLM
```bash

文件：../.venv/Lib/site-packages/astrbot/core/agent/runners/tool_loop_agent_runner.py#L109

## 十、局限性

### @llm_tool 不支持 required 字段

`@llm_tool` 装饰器目前无法通过 `required` 关键字限定必填参数。即使你在函数签名中给参数加了默认值，框架也不会生成 `required` 字段，LLM 会认为所有参数都是可选的。

**函数签名的默认值无效**

```python
# 这样写，框架不会生成 required 字段
@llm_tool(name="get_user_info")
async def get_user_info(self, event: AstrMessageEvent, user_id: str, platform: str = "QQ") -> str:
    """查询用户信息
    
    Args:
        user_id: 用户ID（你以为这是必填的）
        platform: 平台类型（你以为这是可选的）
    """
```text

**实际生成的 JSON Schema**

```json
{
    "type": "object",
    "properties": {
        "user_id": {"type": "string", "description": "用户ID"},
        "platform": {"type": "string", "description": "平台类型"}
    }
    // 没有 required 字段！LLM 不知道 user_id 是必填的
}
```bash

**为什么默认值不起作用？**

`@llm_tool` 只解析 docstring 中的参数描述，**不检查函数签名中的默认值**。它不会根据参数是否有默认值来判断是否添加 `required` 字段。

### 原因分析

查看 `spec_to_func` 方法（../.venv/Lib/site-packages/astrbot/core/provider/func_tool_manager.py#L341）：

```python
def spec_to_func(self, name, func_args, desc, handler):
    params = {
        "type": "object",
        "properties": {},  # 只填充了 properties
        # 没有 required 字段！
    }
    for param in func_args:
        p = copy.deepcopy(param)
        p.pop("name", None)
        params["properties"][param["name"]] = p
    return FuncTool(name=name, parameters=params, description=desc, handler=handler)
```bash

它只构建了 `properties`，没有构建 `required` 字段。

### 如何解决？

如果你需要严格区分必填和可选参数，必须使用继承 `FunctionTool` 的方式，手动定义 JSON Schema：

```python
@dataclass
class GetUserInfoTool(FunctionTool[AstrAgentContext]):
    name: str = "get_user_info"
    description: str = "查询用户信息"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "用户ID"},
                "platform": {"type": "string", "description": "平台类型"}
            },
            "required": ["user_id"]  # 只有这里才能真正区分必填/可选
        }
    )
```bash

### 两种方式的对比

| 特性 | @llm_tool 装饰器 | 继承 FunctionTool |
|------|-----------------|-------------------|
| 必填参数限定 | 不支持（所有参数视为可选） | 支持 |
| 参数类型定义 | 通过 docstring 解析 | 手动定义 JSON Schema |
| 灵活性 | 低 | 高 |
| 易用性 | 高 | 低 |

### 解决方案选择

| 需求 | 推荐方式 |
|------|---------|
| 简单工具，不需要 required | @llm_tool 装饰器 |
| 需要 required 限定必填参数 | 继承 FunctionTool 类 |
| 需要复杂参数结构 | 继承 FunctionTool 类 |

### @llm_tool 的 handler 参数安全写法

由于 `@llm_tool` 不生成 `required` 字段，LLM 可能不传某些参数。如果 handler 中有**无默认值的命名参数**，LLM 不传时会报 `TypeError`。

**不安全的写法**

```python
@llm_tool(name="get_weather")
async def get_weather(self, event: AstrMessageEvent, city: str, date: str = "") -> str:
    # city 无默认值，如果 LLM 不传 city，会报 TypeError
    # date 有默认值，LLM 不传时安全
```text

**安全写法一：用 `**kwargs` + `.get()` 兜底（推荐）**

```python
@llm_tool(name="get_weather")
async def get_weather(self, event: AstrMessageEvent, **kwargs) -> str:
    """获取指定城市的天气信息
    
    Args:
        city(str): 城市名称（必填）
        date(str): 日期（可选）
    """
    city = kwargs.get("city", "北京")  # 兜底默认值
    date = kwargs.get("date", "今天")
    weather = await fetch_weather(city, date)
    return f"{city}{date}{weather}"
```text

**安全写法二：必填项用命名参数 + 可选项用 `**kwargs`**

```python
@llm_tool(name="get_weather")
async def get_weather(self, event: AstrMessageEvent, city: str, **kwargs) -> str:
    """获取指定城市的天气信息
    
    Args:
        city(str): 城市名称（必填）
        date(str): 日期（可选）
    """
    date = kwargs.get("date", "今天")
    weather = await fetch_weather(city, date)
    return f"{city}{date}{weather}"
```bash

这种写法下，`city` 是命名参数（LLM 必须传），`date` 通过 `**kwargs` 接收（LLM 可传可不传）。但注意：**这只是 Python 层面的强制**，JSON Schema 仍然没有 `required` 字段，LLM 不知道 `city` 是必填的。要真正强制，还是得用 `FunctionTool` 继承方式。

**重要：LLM 传参不看顺序，按名称匹配**。从 `func_tool_manager.py#L255` 可以看到，handler 调用时用的是 `handler(event, **kwargs)`，`**kwargs` 是 LLM 传来的命名参数字典，Python 按参数名匹配，与 `properties` 中的定义顺序无关。

### FunctionTool 继承时 `call` 方法的 `**kwargs`

继承 `FunctionTool` 实现 `call` 方法时，**必须用 `**kwargs` 接收业务参数**：

```python
async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
    city = kwargs.get("city", "北京")
    date = kwargs.get("date", "今天")
    ...
```text

如果定义成 `call(self, context, city, date)`，当 LLM 不传 `date`（即使 JSON Schema 声明了 `required`，LLM 也可能忽略）时，会报 `TypeError`。用 `**kwargs` + `.get()` 是最安全的写法。

## 十一、相关 API 和装饰器

### API 导出

**文件**：../.venv/Lib/site-packages/astrbot/api/__init__.py

| 导出 | 说明 |
|------|------|
| `FunctionTool` | 函数工具类 |
| `ToolSet` | 工具集合类 |
| `BaseFunctionToolExecutor` | 工具执行器基类 |
| `llm_tool` | 装饰器，用于注册 LLM 工具 |

### 相关装饰器

在 `api.event.filter` 中还有与 Tool 相关的装饰器：

| 装饰器 | 说明 |
|--------|------|
| `@llm_tool(name="xxx")` | 注册 LLM 工具（用于 `@llm_tool` 方式） |
| `@on_using_llm_tool()` | 监听工具被使用的事件 |
| `@on_llm_tool_respond()` | 监听工具响应事件 |

## 十二、动态控制工具

### 两种工具注册级别

在讲动态控制之前，需要理解两个级别的区别：

**全局注册**（`self.context.add_llm_tools()`）：
- 工具被添加到 `llm_tools.func_list`（全局工具列表）
- 所有 LLM 请求都会自动携带这些工具
- 适合所有场景都需要的通用工具

**请求级注入**（`req.func_tool.add_tool()`）：
- 工具只添加到当前请求的 `req.func_tool`
- 仅本次对话生效，下次请求不会自动携带
- 适合按需加载的场景（如权限相关、会话相关的工具）

简单说，二者的核心区别就是：
`self.context.add_llm_tools()` 是 全局注册 ，工具被添加到 llm_tools.func_list （全局工具列表）。
`req.func_tool.add_tool()` 是 请求级注入 ，工具只添加到当前请求的 req.func_tool （本次对话的工具集）。

### 执行顺序

1. build_main_agent 构建 req ，从 llm_tools.func_list （全局）合并工具到 req.func_tool （请求级）
2. _plugin_tool_fix 根据权限过滤 req.func_tool 中的工具
3. call_event_hook(event, EventType.OnLLMRequestEvent, req) → 调用你的 on_llm_request 处理器
4. 之后 req.func_tool 被传给 Provider 进行 LLM 调用

### 追踪源码进行验证的方法

1. 追踪 on_llm_request 的调用时机，以及 req.func_tool 是怎么构建的
2. 找 on_llm_request 被调用的地方，看 req.func_tool 是怎么构建的
3. 看 build_main_agent 是怎么构建 req.func_tool 的
4. 看 _plugin_tool_fix 和全局工具是怎么合并到 req.func_tool 的
5. 看全局工具（ llm_tools.func_list ）是怎么合并到 req.func_tool 的
6. 关键！能看到 tmgr.get_full_tool_set() 把全局工具注入了 req.func_tool 
7. 看 get_full_tool_set 是怎么实现的

### 为什么在 on_llm_request 中不能用 add_llm_tools？

执行顺序问题：`on_llm_request` 回调在工具集构建完成**之后**才执行。此时 `req.func_tool` 已经从全局列表合并了工具，你再往全局列表加工具，`req.func_tool` 不会再回头合并。所以必须直接往 `req.func_tool` 里加。

### 动态注入的用法

当你需要**按需提供工具**时（比如根据用户权限、会话状态决定是否提供某个工具）：

```python
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext

class MyPlugin(Star):
    def __init__(self, context):
        super().__init__(context)
        # 创建一次工具，复用
        self._weather_tool = FunctionTool(
            name="get_weather",
            description="获取指定城市的天气信息",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称"},
                    "date": {"type": "string", "description": "日期（可选）"}
                },
                "required": ["city"]
            },
            handler=MyPlugin._get_weather_handler  # 未绑定类方法
        )

    async def _get_weather_handler(self, event: AstrMessageEvent, **kwargs) -> str:
        city = kwargs.get("city", "北京")
        date = kwargs.get("date", "今天")
        weather = "晴"
        return f"{city}{date}{weather}"

    @filter.on_llm_request()
    async def _on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest) -> None:
        # 根据条件动态注入
        if some_condition:
            if req.func_tool is None:
                req.func_tool = ToolSet()
            req.func_tool.add_tool(self._weather_tool)
```bash

### 什么时候需要额外的 @on_llm_request？

当你需要**动态控制工具**时（比如根据用户权限决定是否提供某个工具）：

```python
from astrbot.api.event import AstrMessageEvent, filter

class MyPlugin(Star):
    @filter.llm_tool(name="admin_action")
    async def admin_action(self, event: AstrMessageEvent, action: str) -> str:
        """管理员操作
        
        Args:
            action: 要执行的操作
        """
        return f"执行: {action}"
    
    @filter.on_llm_request()
    async def conditional_tools(self, event, req):
        # 只有管理员才能使用管理工具
        if not is_admin(event):
            req.func_tool.remove_tool("admin_action")
```bash

这种方式与动态注入互补：工具已全局注册，但在 `on_llm_request` 中根据条件**移除**。

### 代码组织：工厂函数模式

当工具逻辑复杂、不想把所有实现都塞进 `main.py` 时，可以用**工厂函数**把工具创建逻辑分离到单独的文件中。

#### 核心思路

在 `tools.py`（或其他模块）中定义一个函数，接收 `context`（应用级对象），返回一个 `FunctionTool` 实例。handler 所需的 `event` 由框架在调用时自动注入，不需要从闭包中捕获。

**关键点：handler 的 `event` 参数由框架在执行时自动注入，工厂函数不需要接收 `event`。**

#### 示例

`tools.py`：

```python
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context
from astrbot.core.agent.tool import FunctionTool
import logging

logger = logging.getLogger(__name__)


def create_list_subagent_tool(context: Context) -> FunctionTool:
    """创建 list_subagent 工具（请求级注入专用）

    Args:
        context: 框架上下文（应用级，可安全缓存）

    Returns:
        FunctionTool 实例，可通过 req.func_tool.add_tool() 注入
    """

    async def _handler(event: AstrMessageEvent, **kwargs) -> str:
        """列出所有可用的子智能体"""
        logger.debug("list all sub agent")

        handoffs = context.subagent_orchestrator.handoffs
        if not handoffs:
            yield event.plain_result("当前没有可用的子智能体")
            return "当前没有可用的子智能体"

        result = []
        for h in handoffs:
            agent = h.agent
            result.append({
                "handoff_name": h.name,
                "agent_name": agent.name,
                "instructions": agent.instructions,
                "tools": agent.tools,
                "has_begin_dialogs": bool(agent.begin_dialogs),
                "provider_id": h.provider_id,
            })

        yield event.plain_result(f"已注册的 SubAgent: {result}")

    return FunctionTool(
        name="list_subagent",
        description="获取已有的 SubAgent 列表",
        parameters={
            "type": "object",
            "properties": {},
        },
        handler=_handler,
    )
```text

`main.py`：

```python
from .tools import create_list_subagent_tool

class SubAgentRouter(Star):
    def __init__(self, context):
        super().__init__(context)
        # 创建一次，缓存复用
        self._list_tool = create_list_subagent_tool(context)

    @filter.on_llm_request()
    async def _on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        if req.func_tool is None:
            req.func_tool = ToolSet()
        req.func_tool.add_tool(self._list_tool)
```json

#### 为什么不需要缓存 event？

handler 的签名是 `async def handler(event: AstrMessageEvent, **kwargs)`，框架在执行工具时会自动将当前请求的 `event` 作为第一个参数传入。因此：

- `event` 始终是请求级的，由框架负责注入
- 工厂函数只需接收应用级的 `context`，可安全缓存
- 返回的 `FunctionTool` 对象可在 `__init__` 中创建一次，所有请求复用

#### 不要在模块级缓存工具

**问题**：修改插件代码后，AstrBot 会重新加载模块，但 Python 的模块级变量在某些情况下不会完全重置，可能导致状态混乱。

**风险**：
1. **旧对象残留**：缓存的工具对象可能引用已失效的 `context` 或其他资源
2. **闭包捕获失效**：工厂函数的闭包捕获的是旧的 `context`，新请求可能用不到最新的配置
3. **调试困难**：状态不一致导致的 bug 很难定位，因为看起来代码是对的，但实际运行的是旧对象

**错误示例**：

```python
# tools.py - 不要这样做！
_myToolSet = ToolSet()  # 模块级缓存，插件重载时可能不重置

def create_list_subagent_tool(context: Context) -> FunctionTool:
    # 模块级缓存，风险很大
    if _myToolSet.get_tool("list_subagent"):
        return _myToolSet.get_tool("list_subagent")

    tool = FunctionTool(...)
    _myToolSet.add_tool(tool)
    return tool
```text

**正确做法**：在 `Star` 实例属性中缓存，插件重载时 `__init__` 会重新执行，自然重置。

```python
# tools.py - 工厂函数只负责创建，不缓存
def create_list_subagent_tool(context: Context) -> FunctionTool:
    async def _handler(event: AstrMessageEvent) -> str:
        ...
    return FunctionTool(...)

# main.py - 缓存在实例属性中
class MyPlugin(Star):
    def __init__(self, context):
        super().__init__(context)
        self._list_tool = create_list_subagent_tool(context)  # 实例级缓存，安全
```text

**正确做法二**：在 `tools.py` 中创建工具管理器类，负责缓存和管理工具。

`tools.py`：
```python
class SubAgentToolManager:
    """管理 SubAgent 相关工具的创建与缓存"""

    def __init__(self, context: Context):
        self._context = context
        self._toolset = ToolSet()  # 实例级缓存，不是模块级

    def get_list_subagent_tool(self) -> FunctionTool:
        """获取 list_subagent 工具（缓存复用）"""
        tool = self._toolset.get_tool("list_subagent")
        if tool:
            return tool

        # 创建并缓存
        context = self._context

        async def _handler(event: AstrMessageEvent) -> str:
            handoffs = context.subagent_orchestrator.handoffs
            result = [{"name": h.agent.name, "desc": h.description} for h in handoffs]
            return f"已有的 SubAgent 列表: {result}"

        tool = FunctionTool(
            name="list_subagent",
            description="获取已有的 SubAgent 列表",
            parameters={"type": "object", "properties": {}},
            handler=_handler,
        )
        self._toolset.add_tool(tool)
        return tool

    def get_call_subagent_tool(self) -> FunctionTool:
        """获取 call_subagent 工具（缓存复用）"""
        # 类似实现...
        pass
```text
然而在 main.py 中，还是建议创建一个实例级的管理器，插件重载时才可自然重置

`main.py`：
```python
from .tools import SubAgentToolManager

class SubAgentRouter(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 实例级管理器，插件重载时自然重置
        self._tool_mgr = SubAgentToolManager(context)

    @filter.on_llm_request()
    async def _on_llm_request(self, event, req):
        # 从管理器获取工具（缓存复用）
        tool = self._tool_mgr.get_list_subagent_tool()
        req.func_tool.add_tool(tool)
```json



#### 与全局注册的对比

| 维度 | 全局注册 (`@llm_tool`) | 工厂函数 + 请求级注入 |
|------|----------------------|---------------------|
| 可见性 | 所有请求自动可见 | 仅在 `on_llm_request` 中显式注入的请求可见 |
| 生命周期 | 跟随插件生命周期 | 跟随单次请求 |
| 代码位置 | `main.py` 的 Star 类中 | 任意模块（如 `tools.py`） |
| handler 的 event | 框架自动注入 | 框架自动注入（相同） |
| 适用场景 | 通用工具、所有请求都需要 | 按需加载、权限相关、会话相关 |

## 十三、工具管理器 FunctionToolManager

`FunctionToolManager`（../.venv/Lib/site-packages/astrbot/core/provider/func_tool_manager.py#L287）是 AstrBot 的**核心工具管理器**，负责统一管理所有 LLM 可调用的工具。它通过 `context.get_llm_tool_manager()` 获取。

### 两个独立的工具存储系统

`FunctionToolManager` 维护了两个独立的工具列表，这是理解工具系统的关键：

| 属性 | 类型 | 说明 |
|------|------|------|
| `func_list` | `list[FuncTool]` | 插件通过 `@llm_tool` 注册的工具 + MCP 工具。**不包含**系统内置工具 |
| `builtin_func_list` | `dict[type[FuncTool], FuncTool]` | 系统内置工具（按类缓存，按需创建）。通过 `get_builtin_tool()` 获取 |

二者的区别：
- `func_list` 中的工具通过 `get_full_tool_set()` 获取，会被 `_PermissionGuardedTool` 包装以支持权限检查
- `builtin_func_list` 中的工具通过 `get_builtin_tool()` 获取，按需实例化并缓存在字典中
- **`get_full_tool_set()` 只返回 `func_list` 中的工具，不包含 `builtin_func_list`**

这就是 SubAgent 工具集缺失问题的根本原因（详见 [AstrBot-SubAgent 机制.md 第五章](./AstrBot-SubAgent%20机制.md#L1102)）。

### 其他属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `_mcp_server_runtime` | `dict[str, _MCPServerRuntime]` | MCP 服务运行时元数据，按服务名索引 |
| `_mcp_server_runtime_view` | `MappingProxyType` | `_mcp_server_runtime` 的只读视图 |
| `_mcp_client_dict_view` | `_MCPClientDictView` | MCP 客户端字典的只读视图 |
| `_timeout_mismatch_warned` | `bool` | MCP 超时配置不匹配是否已警告过（防止重复警告） |
| `_timeout_warn_lock` | `threading.Lock` | 超时警告的线程锁（防止并发警告） |
| `_runtime_lock` | `asyncio.Lock` | MCP 运行时操作的异步锁 |
| `_mcp_starting` | `set[str]` | 正在启动中的 MCP 服务名集合（防止重复启动） |

### 核心方法

| 方法 | 签名 | 说明 |
|------|------|------|
| `add_func` | `(name, func_args, desc, handler) -> None` | 注册插件工具到 `func_list`。如果同名工具已存在会先移除 |
| `remove_func` | `(name) -> None` | 从 `func_list` 移除指定工具 |
| `get_func` | `(name) -> FuncTool \| None` | 按名查找工具。先查 `func_list`（优先返回已激活的），再退化查 `builtin_func_list` |
| `get_builtin_tool` | `(str \| type[FuncTool]) -> FuncTool` | 按类名或类获取内置工具。按需实例化并缓存在 `builtin_func_list` 中 |
| `iter_builtin_tools` | `() -> list[FuncTool]` | 遍历所有已注册的内置工具 |
| `get_full_tool_set` | `() -> ToolSet` | 获取完整工具集（仅包含 `func_list` 中的工具，不含内置工具）。工具会被 `_PermissionGuardedTool` 包装 |
| `is_builtin_tool` | `(name: str) -> bool` | 判断工具名是否为内置工具 |
| `spec_to_func` | `(name, func_args, desc, handler) -> FuncTool` | 将参数规范转换为 `FuncTool` 对象（内部方法） |
| `empty` | `() -> bool` | 判断 `func_list` 是否为空 |

### MCP 相关方法

| 方法 | 签名 | 说明 |
|------|------|------|
| `init_mcp_clients` | `(raise_on_all_failed=False) -> MCPInitSummary` | 从 `data/mcp_server.json` 初始化 MCP 客户端 |

### 使用示例

```python
# 获取工具管理器
tool_mgr = self.context.get_llm_tool_manager()

# 获取内置工具（按需实例化并缓存）
from astrbot.core.tools.builtin_tools import ExecuteShellTool
shell_tool = tool_mgr.get_builtin_tool(ExecuteShellTool)

# 按名查找工具
tool = tool_mgr.get_func("get_weather")

# 获取完整工具集（不含内置工具）
full_toolset = tool_mgr.get_full_tool_set()

# 判断是否为内置工具
is_builtin = tool_mgr.is_builtin_tool("astrbot_execute_shell")

# 遍历所有内置工具
all_builtin = tool_mgr.iter_builtin_tools()
```bash

### 与 ToolSet 的关系

`FunctionToolManager` 是工具的**注册中心**，`ToolSet` 是工具的**运行时容器**。

- `FunctionToolManager` 负责工具的注册、存储、查找和权限管理
- `ToolSet` 负责工具的去重、合并和序列化（转换为 LLM API 格式）
- `get_full_tool_set()` 将 `func_list` 中的工具包装后放入新的 `ToolSet` 返回
- 在 `on_llm_request` 中，通过 `req.func_tool.add_tool()` 向请求级 `ToolSet` 添加工具

### 内置工具的定义与导出位置

所有系统内置工具定义在 `astrbot.core.tools` 包下，所有内置工具类的注册中心是 `registry.py`，通过 `@builtin_tool` 装饰器注册到 `_builtin_tool_classes_by_name` 字典中（../.venv/Lib/site-packages/astrbot/core/tools/registry.py#L232）。
通过 `iter_builtin_tool_classes()` 可以获取所有已注册的工具类。

注意：工具管理器里面的 `builtin_func_list` 属性是**按需创建的缓存**，不是全量列表。它的 key 是工具类，value 是已实例化的对象。只有当调用 `get_builtin_tool(SomeToolClass)` 时，才会把该工具实例化并放入缓存。

#### 模块结构（5 个模块，38 个工具）

| 模块路径 | 包含的工具 |
|---------|-----------|
| `astrbot.core.tools.computer_tools` | 基础工具（shell、python、fs、cua）、Skill 工具、浏览器工具 |
| `astrbot.core.tools.cron_tools` | FutureTaskTool |
| `astrbot.core.tools.knowledge_base_tools` | KnowledgeBaseQueryTool |
| `astrbot.core.tools.message_tools` | SendMessageToUserTool |
| `astrbot.core.tools.web_search_tools` | Tavily、Bocha、Brave、Firecrawl、Baidu、Exa 等搜索工具 |

#### 共 **38 个内置工具**，分布在 5 个模块（截止至2026-7-30）

##### `computer_tools`（26 个）

| 工具类 | 文件 |
|--------|------|
| `ExecuteShellTool` | ../.venv/Lib/site-packages/astrbot/core/tools/computer_tools/shell.py#L54 |
| `PythonTool` (sandbox) | ../.venv/Lib/site-packages/astrbot/core/tools/computer_tools/python.py#L80 |
| `PythonTool` (local) | ../.venv/Lib/site-packages/astrbot/core/tools/computer_tools/python.py#L116 |
| `CuaScreenshotTool` | ../.venv/Lib/site-packages/astrbot/core/tools/computer_tools/cua.py#L50 |
| `CuaMouseClickTool` | ../.venv/Lib/site-packages/astrbot/core/tools/computer_tools/cua.py#L108 |
| `CuaKeyboardTypeTool` | ../.venv/Lib/site-packages/astrbot/core/tools/computer_tools/cua.py#L145 |
| `FileReadTool` | ../.venv/Lib/site-packages/astrbot/core/tools/computer_tools/fs.py#L295 |
| `FileWriteTool` | ../.venv/Lib/site-packages/astrbot/core/tools/computer_tools/fs.py#L392 |
| `FileEditTool` | ../.venv/Lib/site-packages/astrbot/core/tools/computer_tools/fs.py#L464 |
| `GrepTool` | ../.venv/Lib/site-packages/astrbot/core/tools/computer_tools/fs.py#L555 |
| `FileUploadTool` | ../.venv/Lib/site-packages/astrbot/core/tools/computer_tools/fs.py#L791 |
| `FileDownloadTool` | ../.venv/Lib/site-packages/astrbot/core/tools/computer_tools/fs.py#L857 |
| `RunBrowserSkillTool` | ../.venv/Lib/site-packages/astrbot/core/tools/computer_tools/shipyard_neo/neo_skills.py#L72 |
| `CreateSkillPayloadTool` | ../.venv/Lib/site-packages/astrbot/core/tools/computer_tools/shipyard_neo/neo_skills.py#L119 |
| `CreateSkillCandidateTool` | ../.venv/Lib/site-packages/astrbot/core/tools/computer_tools/shipyard_neo/neo_skills.py#L157 |
| ... 更多 Skill 工具 | neo_skills.py |
| `BrowserExecTool` | ../.venv/Lib/site-packages/astrbot/core/tools/computer_tools/shipyard_neo/browser.py#L37 |
| `BrowserBatchExecTool` | ../.venv/Lib/site-packages/astrbot/core/tools/computer_tools/shipyard_neo/browser.py#L95 |
| ... 更多浏览器工具 | browser.py |

##### `web_search_tools`（10 个）

| 工具类 | 文件 |
|--------|------|
| `TavilyWebSearchTool` | ../.venv/Lib/site-packages/astrbot/core/tools/web_search_tools.py#L587 |
| `BochaWebSearchTool` | ../.venv/Lib/site-packages/astrbot/core/tools/web_search_tools.py#L721 |
| `BraveWebSearchTool` | ../.venv/Lib/site-packages/astrbot/core/tools/web_search_tools.py#L785 |
| `FirecrawlWebSearchTool` | ../.venv/Lib/site-packages/astrbot/core/tools/web_search_tools.py#L843 |
| `BaiduWebSearchTool` | ../.venv/Lib/site-packages/astrbot/core/tools/web_search_tools.py#L961 |
| `ExaWebSearchTool` | ../.venv/Lib/site-packages/astrbot/core/tools/web_search_tools.py#L1086 |
| ... 各搜索工具的 Async 版本 | web_search_tools.py |

##### `cron_tools`（1 个）
- `FutureTaskTool` — ../.venv/Lib/site-packages/astrbot/core/tools/cron_tools.py#L49

##### `knowledge_base_tools`（1 个）
- `KnowledgeBaseQueryTool` — ../.venv/Lib/site-packages/astrbot/core/tools/knowledge_base_tools.py#L90

##### `message_tools`（1 个）
- `SendMessageToUserTool` — ../.venv/Lib/site-packages/astrbot/core/tools/message_tools.py#L75

#### 各模块文件详情

**`computer_tools` 模块**（astrbot/core/tools/computer_tools/）：

| 文件 | 工具 |
|------|------|
| `shell.py` | `ExecuteShellTool` |
| `python.py` | `PythonTool`（sandbox 版、local 版） |
| `fs.py` | `FileReadTool`、`FileWriteTool`、`FileEditTool`、`GrepTool`、`FileUploadTool`、`FileDownloadTool` |
| `cua.py` | `CuaScreenshotTool`、`CuaMouseClickTool`、`CuaKeyboardTypeTool` |
| `shipyard_neo/neo_skills.py` | `RunBrowserSkillTool`、`CreateSkillPayloadTool`、`CreateSkillCandidateTool` 等 11 个 Skill 工具 |
| `shipyard_neo/browser.py` | `BrowserExecTool`、`BrowserBatchExecTool` 等 3 个浏览器工具 |

**`web_search_tools` 模块**（../.venv/Lib/site-packages/astrbot/core/tools/web_search_tools.py）：

| 工具 | 说明 |
|------|------|
| `TavilyWebSearchTool` | Tavily 搜索（async + sync 两个版本） |
| `BochaWebSearchTool` | 博查搜索 |
| `BraveWebSearchTool` | Brave 搜索 |
| `FirecrawlWebSearchTool` | Firecrawl 搜索（async + sync 两个版本） |
| `BaiduWebSearchTool` | 百度搜索 |
| `ExaWebSearchTool` | Exa 搜索（async + sync 两个版本） |

#### 获取所有内置工具类的方法

```python
from astrbot.core.tools.registry import iter_builtin_tool_classes

# 获取所有已注册的内置工具类
for tool_cls in iter_builtin_tool_classes():
    print(tool_cls.__name__)
```bash

`iter_builtin_tool_classes()` 会自动调用 `ensure_builtin_tools_loaded()`，触发所有 5 个模块的 import，返回 `_builtin_tool_classes_by_name` 中的所有值（截止至2026-7-30，是全部 38 个工具类）。

#### registry.py 核心 API

| 函数 | 说明 |
|------|------|
| `builtin_tool(cls, config)` | 装饰器，注册内置工具类，可选配置条件 |
| `ensure_builtin_tools_loaded()` | 延迟加载所有内置工具模块（只执行一次） |
| `get_builtin_tool_class(name)` | 按名查找已注册的工具类 |
| `get_builtin_tool_name(tool_cls)` | 按类查找工具名 |
| `iter_builtin_tool_classes()` | 遍历所有已注册的工具类 |
| `get_builtin_tool_config_rule(name)` | 获取工具的配置规则（用于 WebUI 显示启用状态） |

#### 如何让 SubAgent 能使用全部内置工具
综上所述，想让 SubAgent 能使用全部内置工具，得先 iter_builtin_tool_classes 获取所有内置工具的字典，然后遍历它时通过 get_builtin_tool 获取对应工具的实例，全部添加进 toolset，也就是需要在 `HandoffTool.call()` 中手动添加 `tools=None`。

要让 SubAgent **真正调用**工具，是在 `tool_loop_agent` 的 `tools` 参数里把工具实例塞进去：

```python
toolset = ToolSet()

# 插件工具
for tool in tool_mgr.get_full_tool_set():
    if tool.active:
        toolset.add_tool(tool)

# 内置工具
for tool_cls in iter_builtin_tool_classes():
    toolset.add_tool(tool_mgr.get_builtin_tool(tool_cls))

# 调 SubAgent
llm_resp = await ctx.tool_loop_agent(
    event=event,
    tools=toolset,  # ← 这里
    ...
)
```text

完整的逻辑就是：

```python
toolset = ToolSet()

for tool_cls in iter_builtin_tool_classes():
    toolset.add_tool(tool_mgr.get_builtin_tool(tool_cls))
```bash

但说实话你不需要自己写这段——因为 handoff 执行时 `_get_runtime_computer_tools()` 已经把沙箱 8 件套加进去了，`get_full_tool_set()` 也加了插件工具。你真正缺的是 **Neo Skill 工具**（`astrbot_run_browser_skill`、`astrbot_create_skill_payload` 那堆）和 **Skill prompt 文本**。

Neo Skill 工具也是用 `@builtin_tool` 注册的，所以也在 `iter_builtin_tool_classes()` 的返回里。问题只是 handoff 执行时没把它们加进 toolset。你如果要自己接管的话，`iter_builtin_tool_classes` + `get_builtin_tool` 一把梭就能搞定工具这一层。

---

#### 进阶方案：工具管理器类（MyToolManager）

当需要为 SubAgent 注入**完整的内置工具集**时，可以创建一个工具管理器类来统一管理工具的创建、缓存和动态组合。

##### 设计思路

```text
┌─────────────────────────────────────────────────────┐
│                  MyToolManager                        │
│                                                       │
│  ┌─────────────────────────────────────────────────┐ │
│  │  _BUILTIN_TOOL_GROUPS (静态映射表)                │ │
│  │                                                   │ │
│  │  runtime_common: [5 个工具]                       │ │
│  │  sandbox_only:   [3 个工具]                       │ │
│  │  local_only:     [1 个工具]                       │ │
│  │  cua:            [3 个工具]                       │ │
│  │  neo_skill:      [12 个工具]                      │ │
│  │  browser:        [2 个工具]                       │ │
│  │  web_search:     [9 个工具]                       │ │
│  │  system:         [3 个工具]                       │ │
│  └─────────────────────────────────────────────────┘ │
│                                                       │
│  ┌─────────────────────────────────────────────────┐ │
│  │  _tool_set (实例级缓存)                           │ │
│  │  已创建的 FunctionTool 实例缓存                    │ │
│  └─────────────────────────────────────────────────┘ │
│                                                       │
│  方法:                                                │
│  ├── get_list_subagent_tool()  → 缓存创建 list 工具   │
│  ├── get_call_subagent_tool()  → 缓存创建 call 工具   │
│  ├── _get_computer_use_toolset() → 动态构建基础能力集  │
│  ├── _get_builtin_toolset_by_names() → 按名获取工具集  │
│  ├── _get_builtin_toolset_by_group_key() → 按组获取   │
│  └── _get_skills_prompt()      → 获取 Skill prompt   │
└─────────────────────────────────────────────────────┘
```bash

##### 核心特点

**1. 静态映射表**

```python
_BUILTIN_TOOL_GROUPS = {
    "runtime_common": [
        "astrbot_execute_shell",      # 执行 Shell 命令
        "astrbot_file_read_tool",     # 读取文件
        "astrbot_file_write_tool",    # 写入文件
        "astrbot_file_edit_tool",     # 编辑文件
        "astrbot_grep_tool",          # 搜索文件
    ],
    "sandbox_only": [
        "astrbot_execute_ipython",    # IPython（沙箱内）
        "astrbot_upload_file",        # 上传文件
        "astrbot_download_file",      # 下载文件
    ],
    "local_only": [
        "astrbot_execute_python",     # 本地 Python
    ],
    "cua": [
        "astrbot_cua_screenshot",     # CUA 截图
        "astrbot_cua_mouse_click",    # CUA 鼠标点击
        "astrbot_cua_keyboard_type",  # CUA 键盘输入
    ],
    "neo_skill": [
        "astrbot_get_execution_history",
        "astrbot_annotate_execution",
        "astrbot_create_skill_payload",
        # ... 更多 Neo Skill 工具
    ],
    "browser": [
        "astrbot_execute_browser",
        "astrbot_execute_browser_batch",
    ],
    "web_search": [
        "web_search_tavily",
        "tavily_extract_web_page",
        # ... 更多搜索工具
    ],
    "system": [
        "send_message_to_user",
        "future_task",
        "astr_kb_search",
    ],
}
```text

**2. 动态工具集组合**

```python
def _get_computer_use_toolset(self) -> ToolSet:
    """根据当前配置动态构建基础能力工具集"""
    runtime = self._cfg["provider_settings"]["computer_use_runtime"]
    booter = self._cfg["provider_settings"]["sandbox"]["booter"]

    names = list(self._BUILTIN_TOOL_GROUPS["runtime_common"])

    if runtime == "local":
        names += self._BUILTIN_TOOL_GROUPS["local_only"]
    else:  # sandbox
        names += self._BUILTIN_TOOL_GROUPS["sandbox_only"]
        if booter == "cua":
            names += self._BUILTIN_TOOL_GROUPS["cua"]

    return self._get_builtin_toolset_by_names(names)
```text

**3. 工具实例缓存**

```python
def get_call_subagent_tool(self) -> FunctionTool:
    """获取 call_subagent 工具（带缓存）"""
    tool = self._tool_set.get_tool("call_subagent")
    if tool:
        return tool  # 缓存命中，直接返回

    async def _handler(event: AstrMessageEvent, agent_name: str) -> str:
        # ... 工具逻辑
        pass

    tool = FunctionTool(
        name="call_subagent",
        description="调用指定 SubAgent",
        parameters={...},
        handler=_handler,
    )
    self._tool_set.add_tool(tool)  # 缓存
    return tool
```bash

##### 完整示例

```python
from astrbot.api import logger, FunctionTool, ToolSet
from astrbot.api.star import Context
from astrbot.api.event import AstrMessageEvent
from astrbot.core.skills import SkillManager, build_skills_prompt

class MyToolManager:
    """SubAgent 工具管理器"""

    # 系统内置工具分组映射表
    _BUILTIN_TOOL_GROUPS = {
        "runtime_common": [
            "astrbot_execute_shell",
            "astrbot_file_read_tool",
            "astrbot_file_write_tool",
            "astrbot_file_edit_tool",
            "astrbot_grep_tool",
        ],
        "sandbox_only": [
            "astrbot_execute_ipython",
            "astrbot_upload_file",
            "astrbot_download_file",
        ],
        "local_only": [
            "astrbot_execute_python",
        ],
        "cua": [
            "astrbot_cua_screenshot",
            "astrbot_cua_mouse_click",
            "astrbot_cua_keyboard_type",
        ],
        "neo_skill": [
            "astrbot_get_execution_history",
            "astrbot_create_skill_payload",
            # ... 更多
        ],
        "browser": [
            "astrbot_execute_browser",
            "astrbot_execute_browser_batch",
        ],
        "web_search": [
            "web_search_tavily",
            # ... 更多
        ],
        "system": [
            "send_message_to_user",
            "future_task",
            "astr_kb_search",
        ],
    }

    def __init__(self, context: Context):
        self._tool_set = ToolSet()   # 实例级缓存
        self._context = context
        self._cfg = context.get_config()

    def get_list_subagent_tool(self) -> FunctionTool:
        """获取 list_subagent 工具"""
        tool = self._tool_set.get_tool("list_subagent")
        if tool:
            return tool

        async def _handler(event: AstrMessageEvent) -> str:
            """获取现有的 SubAgent 列表"""
            handoffs = self._context.subagent_orchestrator.handoffs
            result = []
            for h in handoffs:
                agent = h.agent
                result.append({
                    "agent_name": agent.name,
                    "tool_description": h.description,
                    "tools": agent.tools,
                    "has_begin_dialogs": bool(agent.begin_dialogs),
                })
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
            # 获取 handoff
            handoff_tool = next(
                (h for h in self._context.subagent_orchestrator.handoffs
                 if h.agent.name == agent_name),
                None
            )
            if handoff_tool is None:
                return f"Agent {agent_name} 不存在"

            agent = handoff_tool.agent

            # 构建工具集
            toolset = ToolSet()

            # 1. 添加插件工具
            plugin_tools = self._context.get_llm_tool_manager().get_full_tool_set()
            for t in plugin_tools:
                if t.active:
                    toolset.add_tool(t)

            # 2. 添加基础能力工具（根据 runtime 配置）
            computer_use_tools = self._get_computer_use_toolset()
            for t in computer_use_tools:
                toolset.add_tool(t)

            # 3. 添加 Neo Skill 工具
            neo_skill_tools = self._get_builtin_toolset_by_group_key("neo_skill")
            for t in neo_skill_tools:
                toolset.add_tool(t)

            # 4. 添加浏览器工具
            browser_tools = self._get_builtin_toolset_by_group_key("browser")
            for t in browser_tools:
                toolset.add_tool(t)

            # 5. 添加搜索工具
            search_tools = self._get_builtin_toolset_by_group_key("web_search")
            for t in search_tools:
                toolset.add_tool(t)

            # 6. 添加系统工具
            system_tools = self._get_builtin_toolset_by_group_key("system")
            for t in system_tools:
                toolset.add_tool(t)

            # 7. 注入 Skill prompt
            skill_prompt = await self._get_skills_prompt(agent_name)
            system_prompt = (agent.instructions or "") + skill_prompt

            # 调用 SubAgent
            runtime = self._cfg["provider_settings"]["computer_use_runtime"]
            llm_resp = await self._context.tool_loop_agent(
                event=event,
                chat_provider_id=handoff_tool.provider_id or await self._context.get_current_chat_provider_id(event.unified_msg_origin),
                prompt=event.message_str,
                system_prompt=system_prompt,
                tools=toolset,
                contexts=agent.begin_dialogs,
            )
            return llm_resp.completion_text

        tool = FunctionTool(
            name="call_subagent",
            description="调用指定 SubAgent",
            parameters={
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string", "description": "要调用的 SubAgent 名称"},
                },
                "required": ["agent_name"],
            },
            handler=_handler,
        )
        self._tool_set.add_tool(tool)
        return tool

    def _get_computer_use_toolset(self) -> ToolSet:
        """根据当前配置获取基础能力工具集"""
        runtime = self._cfg["provider_settings"]["computer_use_runtime"]
        booter = self._cfg["provider_settings"]["sandbox"]["booter"]

        names = list(self._BUILTIN_TOOL_GROUPS["runtime_common"])

        if runtime == "local":
            names += self._BUILTIN_TOOL_GROUPS["local_only"]
        else:
            names += self._BUILTIN_TOOL_GROUPS["sandbox_only"]
            if booter == "cua":
                names += self._BUILTIN_TOOL_GROUPS["cua"]

        return self._get_builtin_toolset_by_names(names)

    def _get_builtin_toolset_by_names(self, names: list[str]) -> ToolSet:
        """根据工具名列表获取内置工具实例集合"""
        tool_set = ToolSet()
        tool_mgr = self._context.get_llm_tool_manager()
        for name in names:
            tool_set.add_tool(tool_mgr.get_builtin_tool(name))
        return tool_set

    def _get_builtin_toolset_by_group_key(self, key: str) -> ToolSet:
        """根据分组键获取内置工具实例集合"""
        names = self._BUILTIN_TOOL_GROUPS[key]
        return self._get_builtin_toolset_by_names(names)

    async def _get_skills_prompt(self, agent_name: str) -> str:
        """根据 Persona 的 skills 配置获取 Skill prompt"""
        # 1. 找到 agent 的 persona_id
        persona_id = None
        for item in self._cfg.get("subagent_orchestrator", {}).get("agents", []):
            if item.get("name") == agent_name:
                persona_id = item.get("persona_id")
                break
        if not persona_id:
            return ""

        # 2. 获取 Persona 数据
        try:
            persona = await self._context.persona_manager.get_persona(persona_id)
        except ValueError:
            return ""
        if not persona:
            return ""

        # 3. 获取 skills 白名单
        allowed_skills = persona.skills
        if allowed_skills is None or not allowed_skills:
            return ""

        # 4. 过滤可用 skill
        skill_mgr = SkillManager()
        runtime = self._cfg["provider_settings"]["computer_use_runtime"]
        skills = skill_mgr.list_skills(active_only=True, runtime=runtime)
        skills = [s for s in skills if s.name in allowed_skills]

        if not skills:
            return ""

        return build_skills_prompt(skills)
```bash

##### 使用方式

在插件的 `main.py` 中：

```python
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self._tool_mgr = MyToolManager(context)
        self.register_tool(self._tool_mgr.get_list_subagent_tool())
        self.register_tool(self._tool_mgr.get_call_subagent_tool())

    @filter.on_llm_request()
    async def on_llm_request(self, event, req):
        # 注入自定义工具给 MainAgent
        req.func_tool.add_tool(self._tool_mgr.get_list_subagent_tool())
        req.func_tool.add_tool(self._tool_mgr.get_call_subagent_tool())
```bash

##### 方案评估

| 优点 | 说明 |
|------|------|
| **集中管理** | 所有 SubAgent 相关工具的创建和注入逻辑集中在一个类中 |
| **动态适配** | 根据 runtime 配置动态组合工具集（sandbox vs local, cua vs not） |
| **实例缓存** | `_tool_set` 缓存已创建的工具实例，避免重复创建 |
| **分组清晰** | 静态映射表按功能分组，易于维护和扩展 |
| **可测试性好** | 工具逻辑封装在独立方法中，便于单元测试 |

| 注意事项 | 说明 |
|----------|------|
| **需同步维护** | `_BUILTIN_TOOL_GROUPS` 需要随 AstrBot 版本更新手动维护 |
| **硬编码工具名** | 工具名是字符串硬编码，如果 AstrBot 修改工具名会失效 |
| **Context 绑定** | 工具实例绑定到特定的 Context，不支持跨会话复用 |
| **`_get_skills_prompt`** | 需要导入 `astrbot.core.skills`（非 API 层），需注意版本兼容性 |

##### 替代方案对比

| 方案 | 优点 | 缺点 |
|------|------|------|
| **方案 A：MyToolManager 类** | 集中管理、动态适配、实例缓存 | 需手动维护映射表 |
| **方案 B：iter_builtin_tool_classes** | 自动发现所有内置工具，无需维护 | 无法按分组控制，注入了不需要的工具 |
| **方案 C：完全依赖框架** | 无需自定义代码 | SubAgent 缺失内置工具和 Skill（当前 Bug） |

**推荐**：方案 A 是当前阶段的最佳折中方案，既能灵活控制工具注入，又能适配不同 runtime 配置。

## 十四、总结

Tool 机制的核心流程：

```text
用户发送消息
    ↓
LLM 判断是否需要调用工具
    ↓
如果需要，LLM 返回 tool_call（工具调用请求）
    ↓
AstrBot Pipeline 处理 tool_call
    ↓
执行注册的工具 handler
    ↓
将工具结果返回给 LLM
    ↓
LLM 根据结果生成最终回复
```

关键信息总结：

| 问题 | 答案 |
|------|------|
| Tool handler 在哪里？ | 在 `star_handlers_registry` 中，类型为 `LLM_TOOL` |
| 如何触发调用？ | 由 Agent 执行链触发，不是普通事件驱动 |
| parameters 规则？ | JSON Schema 格式，有严格验证 |
| ToolSet 作用？ | 转换为不同 LLM API 格式 |
| handler 签名？ | 第一个参数固定是 `event: AstrMessageEvent`，后面是业务参数 |
| event 写在 Args 中？ | 不写，框架自动注入，不是 LLM 提供的参数 |
| @llm_tool 支持 required？ | 不支持，需要继承 FunctionTool 类 |

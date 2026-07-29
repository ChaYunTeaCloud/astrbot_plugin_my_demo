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

**文件**：astrbot/core/agent/tool.py#L20

定义工具的基本结构：
- `name`：工具名称
- `description`：工具描述（LLM 根据这个判断何时调用）
- `parameters`：参数的 JSON Schema

### 2. FunctionTool（函数工具）

**文件**：astrbot/core/agent/tool.py#L41

继承 `ToolSchema`，添加：
- `handler`：实际执行的异步函数
- `active`：是否激活
- `is_background_task`：是否为后台任务

### 3. ToolSet（工具集合）

**文件**：astrbot/core/agent/tool.py#L78

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
```

### 为什么 event 不在 Args 中？

因为 `event` 是框架在调用 handler 时自动从上下文中提取并注入的（见 `func_tool_manager.py#L254-L255`）：

```python
event = context.context.event
result = self._wrapped.handler(event, **kwargs)  # kwargs 才是 LLM 提供的业务参数
```

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
```

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

`ToolSchema.validate_parameters()` 会验证 `parameters` 是否符合 JSON Schema 规范（文件：astrbot/core/agent/tool.py#L32）。如果随便写，会在创建 `FunctionTool` 时就报错。

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
```

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
```

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
```

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
```
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

astrbot/core/star/star_manager.py#L1273-1298 在每次插件加载后，会执行一段"handler 重新绑定"的修正逻辑：

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
```

这段逻辑的设计目的是为 `@llm_tool` 装饰器注册的**未绑定函数**服务的——把插件实例通过 `functools.partial` 绑定为第一个参数（self）。

##### 为什么会出错

当 `handler=self._get_weather_handler`（绑定方法）时：

1. `self._get_weather_handler.__module__` == 插件模块路径 → 匹配修正条件
2. 修正后：`ft.handler = functools.partial(self._get_weather_handler, star_cls)`
3. 工具被调用时（astrbot/core/provider/func_tool_manager.py#L253-255）：
   ```
   handler(event, city="北京")
   = partial(self._get_weather_handler, star_cls)(event, city="北京")
   = self._get_weather_handler(star_cls, event, city="北京")
   ```
4. 由于 `self._get_weather_handler` 已是绑定方法（self 已绑定），实际等价于：
   ```
   _get_weather_handler(self, star_cls, event, "北京")
   ```
   签名 `(self, event, city, date="")` 收到的是：
   - `event` ← `star_cls`（插件实例，类型错！）
   - `city` ← `event`（AstrMessageEvent，类型错！）
   - `date` ← `"北京"`

**参数全部错位**，运行时会因类型不匹配而报错。

##### 正确写法

handler 必须传入**未绑定**的类方法，让框架通过 `functools.partial` 完成实例绑定：

```python
handler=MyPlugin._get_weather_handler  # 未绑定的类方法，不是 self._get_weather_handler
```

##### 总结

此写法 `handler=self._get_weather_handler`（绑定方法）是**错误的**。

核心原因在于 astrbot/core/star/star_manager.py#L1273-1298 的 handler 重新绑定逻辑：

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

从 astrbot\core\astr_agent_tool_exec.py#L660-693 可以看到:

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
```

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
```

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
```

框架用 `isinstance(ret, MessageEventResult)` 检查实际返回值，不看类型注解。

#### 场景二：只调用 `event.plain_result()` 但不 yield/return

`event.plain_result()` 只是**创建**了一个 `MessageEventResult` 对象，并没有发送。如果你不 yield 或 return 它，这个对象就被丢弃了。

```python
@llm_tool(name="test")
async def test_tool(self, event, city) -> str:
    event.plain_result("正在处理...")  # 创建了对象但没用，被丢弃
    return f"{city}晴"  # 实际返回 str，走 LLM 处理
```

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
```

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
```

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
```

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
```
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
```

### ContextWrapper 是什么？

`ContextWrapper` 是包裹 `AstrAgentContext` 的**外层容器**，额外提供了对话历史和超时控制功能。它是 Tool 的 `call` 方法实际接收的参数类型。

**文件**：astrbot/core/agent/run_context.py#L12

```python
@dataclass
class ContextWrapper(Generic[TContext]):
    context: TContext              # 被包装的上下文（AstrAgentContext）
    messages: list[Message]        # LLM 对话历史（由 Agent Runner 自动维护）
    tool_call_timeout: int = 120   # 工具调用超时时间（秒）
```

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
```

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

**文件**：astrbot/core/agent/tool.py#L39

```python
class FunctionTool(ToolSchema, Generic[TContext]):
    async def call(self, context: ContextWrapper[TContext], **kwargs) -> ToolExecResult:
```

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
```

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
```

创建位置有三处：
- `Context.tool_loop_agent()` 方法中
- 主 Agent（`AstrMainAgent`）中
- 第三方 Agent（`ThirdPartyAgent`）中

**AgentContextWrapper 是 ContextWrapper[AstrAgentContext] 的别名**

```python
# astr_agent_context.py#L21
AgentContextWrapper = ContextWrapper[AstrAgentContext]
```

#### AstrAgentContext 每次调用都创建新实例

每次工具调用时，框架都会创建新的 `AstrAgentContext` 实例，包装当前的 `event`：

```python
# context.py#L287
agent_context = AstrAgentContext(
    context=self,   # 传入单例的 Context
    event=event,    # 传入当前的消息事件
    # extra 使用默认值 {}
)
```

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
```

#### extra 是预留给开发者的扩展字段

`extra` 默认为空字典 `{}`，框架目前没有使用它。它的设计意图是让框架内部或插件在需要时可以存储额外信息，但实际中未被框架使用。

#### 生命周期总结

| 类 | 创建时机 | 生命周期 |
|---|---------|---------|
| `Context` | AstrBot 启动时 | 全局单例，整个生命周期不变 |
| `AstrAgentContext` | 每次工具调用时 | 短期，每次调用创建新实例 |
| `ContextWrapper[AstrAgentContext]` | 每次 Agent 运行时 | 短期，每次运行创建新实例 |

层级关系：
```
ContextWrapper[AstrAgentContext]  ← 每次 Agent 运行创建
    ↓ 包装
AstrAgentContext                  ← 每次工具调用创建
    ↓ 包装
Context                          ← 全局单例
```

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
```

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
```

## 八、两种方式的对比与选择

### @llm_tool 方式与 ContextWrapper 的关系

使用 `@llm_tool` 装饰器注册的工具，**不需要直接操作 `ContextWrapper`**。

框架会自动从 `ContextWrapper` 中提取 `event`，并直接传给 `handler`（文件：astrbot/core/provider/func_tool_manager.py#L252-L255）：

```python
# @filter.llm_tool decorated tools have a handler attribute, which is the actual callable.
if self._wrapped.handler is not None:
    event = context.context.event  # 框架从 ContextWrapper 中提取 event
    result = self._wrapped.handler(event, **kwargs)  # 只传入 event 和业务参数
```

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

`@llm_tool` 装饰器会把 handler 注册为 `LLM_TOOL` 类型的 handler（文件：astrbot/core/star/register/star_handler.py#L586）：

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
```

### 调用方式

Tool 的 handler 不是通过 `call_event_hook()` 或 `call_handler()` 调用的，而是通过 **Agent 执行链**调用。

调用链路：
```
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
```

文件：astrbot/core/agent/runners/tool_loop_agent_runner.py#L109

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
```

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
```

**为什么默认值不起作用？**

`@llm_tool` 只解析 docstring 中的参数描述，**不检查函数签名中的默认值**。它不会根据参数是否有默认值来判断是否添加 `required` 字段。

### 原因分析

查看 `spec_to_func` 方法（astrbot/core/provider/func_tool_manager.py#L341）：

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
```

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
```

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
```

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
```

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
```

这种写法下，`city` 是命名参数（LLM 必须传），`date` 通过 `**kwargs` 接收（LLM 可传可不传）。但注意：**这只是 Python 层面的强制**，JSON Schema 仍然没有 `required` 字段，LLM 不知道 `city` 是必填的。要真正强制，还是得用 `FunctionTool` 继承方式。

**重要：LLM 传参不看顺序，按名称匹配**。从 `func_tool_manager.py#L255` 可以看到，handler 调用时用的是 `handler(event, **kwargs)`，`**kwargs` 是 LLM 传来的命名参数字典，Python 按参数名匹配，与 `properties` 中的定义顺序无关。

### FunctionTool 继承时 `call` 方法的 `**kwargs`

继承 `FunctionTool` 实现 `call` 方法时，**必须用 `**kwargs` 接收业务参数**：

```python
async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
    city = kwargs.get("city", "北京")
    date = kwargs.get("date", "今天")
    ...
```

如果定义成 `call(self, context, city, date)`，当 LLM 不传 `date`（即使 JSON Schema 声明了 `required`，LLM 也可能忽略）时，会报 `TypeError`。用 `**kwargs` + `.get()` 是最安全的写法。

## 十一、相关 API 和装饰器

### API 导出

**文件**：astrbot/api/__init__.py

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
```

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
```

这种方式与动态注入互补：工具已全局注册，但在 `on_llm_request` 中根据条件**移除**。

## 总结

Tool 机制的核心流程：

```
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

# AstrBot-Tool

Tool 是 AstrBot 中连接 LLM 和插件功能的关键机制。
在 AstrBot 中，Tool的本质是一个【FunctionTool】类。
根据文档；【star/guides/ai.md】的描述，想注册自己的 Tool 有两种方式，且两种方式最终都是 `FunctionTool` 实例：

- `@dataclass` 方式：你直接继承 `FunctionTool[AstrAgentContext]`
- `@filter.llm_tool` 装饰器：框架在背后自动把你的函数包成 `FunctionTool`，从 docstring 解析参数 schema

本质上 `llm_tools.func_list` 里存的都是 `FunctionTool` 对象。

## 重要规则：`@llm_tool` 装饰器的 handler 参数

**使用 `@llm_tool` 装饰器注册的工具，其 handler 函数的第一个参数固定是 `event: AstrMessageEvent`，后面才是工具的业务参数。**

**注意**：`event` 不需要写在 `Args:` 中，因为它是框架自动注入的，不是 LLM 需要提供的参数。`Args:` 只用于描述 LLM 需要知道的业务参数。

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

**为什么 `event` 不在 Args 中？**

因为 `event` 是框架在调用 handler 时自动从上下文中提取并注入的（见 `func_tool_manager.py#L254-L255`）：
```python
event = context.context.event
result = self._wrapped.handler(event, **kwargs)  # kwargs 才是 LLM 提供的业务参数
```

如果把 `event` 写在 `Args:` 中，会导致 LLM 误认为需要提供这个参数，造成错误。

这与继承 `FunctionTool` 类的方式不同（后者通过 `context` 参数传递上下文）。

## 【FunctionTool[AstrAgentContext]】里面的【parameters】参数是做什么的？

告诉 LLM 这个工具需要哪些参数、什么类型、是否必填。标准的 JSON Schema 格式，LLM 根据它来决定怎么调用你的工具。

假如有 `list_sub_agents` 工具 `parameters` 里 `properties: {}`，意思是不需要任何参数，LLM 直接空着调就行

【parameters】参数是工具的参数 schema，用于描述工具的输入参数。
【parameters】参数是一个 `dict`，键是参数名，值是参数的描述。

## 一、Tool 是什么

Tool（工具）是让 LLM（大语言模型）能够**调用外部功能**的机制。类似于 ChatGPT 的 Function Calling，你可以定义一个工具，告诉 LLM "当用户问天气时，可以调用这个工具来获取天气信息"。

## 二、核心类

### 1. `ToolSchema`（工具模式）

**文件**：astrbot/core/agent/tool.py#L20

定义工具的基本结构：
- `name`：工具名称
- `description`：工具描述（LLM 根据这个判断何时调用）
- `parameters`：参数的 JSON Schema

### 2. `FunctionTool`（函数工具）

**文件**：astrbot/core/agent/tool.py#41

继承 `ToolSchema`，添加：
- `handler`：实际执行的异步函数
- `active`：是否激活
- `is_background_task`：是否为后台任务

### 3. `ToolSet`（工具集合）

**文件**：astrbot/core/agent/tool.py#78

管理多个工具的集合，支持：
- 添加/删除/获取工具
- 转换为不同 LLM API 格式（OpenAI、Anthropic、Google GenAI）

## 三、插件中如何使用

### 方式一：使用 `@llm_tool` 装饰器（推荐）

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

### 方式二：使用 `FunctionTool` 类

```python
from astrbot.api import FunctionTool, ToolSet

class MyPlugin(Star):
    def __init__(self, context):
        super().__init__(context)
        
        # 创建工具
        weather_tool = FunctionTool(
            name="get_weather",
            description="获取指定城市的天气信息",
            parameters={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称"
                    }
                },
                "required": ["city"]
            },
            handler=self._get_weather
        )
        
        # 添加到工具集
        self.tools = ToolSet([weather_tool])
    
    async def _get_weather(self, event: AstrMessageEvent, city: str, date: str = ""):
        weather = await fetch_weather(city, date)
        return f"{city}今天{weather}"
```

### 方式三：通过 Context 管理

```python
from astrbot.api.event import AstrMessageEvent

class MyPlugin(Star):
    @llm_tool(name="search_info")
    async def search_info(self, event: AstrMessageEvent, query: str) -> str:
        """搜索相关信息
        
        Args:
            query: 搜索关键词
        """
        results = await search(query)
        return json.dumps(results)
    
    # 在 on_llm_request 中添加工具
    @filter.on_llm_request()
    async def add_tools(self, event, req):
        # 获取当前会话的工具集
        tool_manager = self.context.get_llm_tool_manager()
        
        # 将插件的工具注册到当前会话
        tool_manager.add_tool(
            FunctionTool(
                name="my_tool",
                description="我的自定义工具",
                parameters={...},
                handler=self.my_handler
            )
        )
```

## 四、相关 API 导出

**文件**：astrbot/api/__init__.py

| 导出 | 说明 |
|------|------|
| `FunctionTool` | 函数工具类 |
| `ToolSet` | 工具集合类 |
| `BaseFunctionToolExecutor` | 工具执行器基类 |
| `llm_tool` | 装饰器，用于注册 LLM 工具 |

## 五、相关装饰器

在 `api.event.filter` 中还有：

| 装饰器 | 说明 |
|--------|------|
| `@llm_tool(name="xxx")` | 注册 LLM 工具 |
| `@on_using_llm_tool()` | 监听工具使用事件 |
| `@on_llm_tool_respond()` | 监听工具响应事件 |

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

**使用场景**：当你希望 AI 能够"使用"你的插件功能时（比如查询数据库、调用外部 API、执行特定操作），就需要用到 Tool。

# 其它问题

## 一、Tool 的 handler 在哪里？

Tool 的 handler **确实在 `star_handlers_registry` 中**，但它的调用方式不同。

### 注册方式

`@llm_tool` 装饰器会把 handler 注册为 `LLM_TOOL` 类型的 handler：

**文件**：astrbot/core/star/register/star_handler.py#580

```python
def register_llm_tool(
    name: str,
    desc: str = "",
    allow_reservation: bool = True,
):
    def decorator(func):
        # 注册为 LLM_TOOL 类型的 handler
        register_handler(
            func,
            handler_type=HandlerType.LLM_TOOL,  # 注意：这个类型
            name=name,
            desc=desc,
        )
        return func
    return decorator
```

### 调用方式

Tool 的 handler 不是通过 `call_event_hook()` 或 `call_handler()` 调用的，而是通过 **Agent 执行链**调用。

**调用链路**：
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

**文件**：astrbot/core/agent/runners/tool_loop_agent_runner.py#109

---

## 二、parameters 字段的规则

`parameters` 是 **JSON Schema** 格式，有严格规范。实际上就是一个 JSON Schema 对象。

### 基本结构

```python
parameters = {
    "type": "object",  # 必须是 object
    "properties": {
        "city": {
            "type": "string",  # string, number, integer, boolean, array
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

`ToolSchema.validate_parameters()` 会验证 `parameters` 是否符合 JSON Schema 规范：

**文件**：astrbot/core/agent/tool.py#32

```python
@model_validator(mode="after")
def validate_parameters(self) -> "ToolSchema":
    jsonschema.validate(
        self.parameters, jsonschema.Draft202012Validator.META_SCHEMA
    )
    return self
```

所以如果你随便写，会在创建 `FunctionTool` 时就报错。

---

## 三、ToolSet 的作用

你的理解基本正确。`ToolSet` 的核心作用就是**把自定义的工具转换为不同 LLM API 可以理解的格式**。

### 支持的格式

| 方法 | API 格式 |
|------|---------|
| `openai_schema()` | OpenAI 格式 |
| `anthropic_schema()` | Anthropic 格式 |
| `google_schema()` | Google GenAI 格式 |

### 实际使用

```python
tools = ToolSet([my_tool])

# 转换为 OpenAI 格式，发给 LLM
schema = tools.openai_schema()
# [{"type": "function", "function": {"name": "get_weather", "description": "...", "parameters": {...}}}]

# 转换为 Anthropic 格式
schema = tools.anthropic_schema()
# [{"name": "get_weather", "description": "...", "input_schema": {...}}]
```

这些格式转换是自动的，你不需要手动处理。

---

## 四、关于 `@llm_tool` 的 handler 参数

**重要**：`@llm_tool` 装饰器的 handler，**第一个参数固定是 `event: AstrMessageEvent`**，后面才是工具的业务参数。

### 正确的签名格式

```python
from astrbot.api import llm_tool
from astrbot.api.event import AstrMessageEvent

@llm_tool(name="get_weather")
async def get_weather(self, event: AstrMessageEvent, city: str, date: str = "") -> str:
    """获取指定城市的天气信息
    
    Args:
        city: 城市名称
        date: 日期
    """
    # event 可以用来获取发送者信息、群信息等
    sender = event.get_sender()
    weather = await fetch_weather(city, date)
    return f"{city}今天{weather}"
```

AstrBot 会**自动解析**参数并传给你的函数：
- `event`：固定第一个参数，由框架自动注入（不需要在 Args 中声明）
- `city`：对应工具的 `parameters.properties.city`
- `date`：对应工具的 `parameters.properties.date`
- 函数注释中的 Args 只用于描述业务参数，会被用来生成参数的 JSON Schema

### 方式二：继承 `FunctionTool` 类

这是官方文档推荐的方式，更灵活：

```python
from astrbot.api import FunctionTool, ToolExecResult
from astrbot.core.agent.run_context import ContextWrapper

class WeatherTool(FunctionTool):
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

### 方式三：手动创建 `FunctionTool`

如果你有特殊需求，可以手动创建：

```python
from astrbot.api import FunctionTool, ToolSet

def get_weather_handler(city: str = "北京", date: str = "") -> str:
    weather = fetch_weather(city, date)
    return f"{city}今天{weather}"

weather_tool = FunctionTool(
    name="get_weather",
    description="获取指定城市的天气信息",
    parameters={...},
    handler=get_weather_handler  # handler 的参数就是工具的参数
)
```

---

## 五、关于注册方式

你说得对，**`@llm_tool` 装饰器可以直接完成定义和注册**，不需要额外的 `@on_llm_request`。

### 简化版

```python
from astrbot.api.event import AstrMessageEvent

class MyPlugin(Star):
    @llm_tool(name="get_weather")
    async def get_weather(self, event: AstrMessageEvent, city: str) -> str:
        """获取天气
        
        Args:
            city: 城市
        """
        return f"{city}今天晴"
```

这就够了！AstrBot 会自动：
1. 从装饰器参数中获取名称
2. 从函数注释中解析参数描述
3. 注册到 `star_handlers_registry`
4. 在 LLM 请求时自动添加到工具集

### 什么时候需要 `@on_llm_request`？

当你需要**动态控制工具**时：

```python
from astrbot.api.event import AstrMessageEvent

class MyPlugin(Star):
    @llm_tool(name="admin_action")
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
            req.tools.remove_tool("admin_action")
```

---

## 总结

| 问题 | 答案 |
|------|------|
| Tool handler 在哪里？ | 在 `star_handlers_registry` 中，类型为 `LLM_TOOL` |
| 如何触发调用？ | 由 Agent 执行链触发，不是普通事件驱动 |
| parameters 规则？ | JSON Schema 格式，有严格验证 |
| ToolSet 作用？ | 转换为不同 LLM API 格式 |
| handler 签名？ | 第一个参数固定是 `event`，后面是业务参数 |
| 注册方式？ | `@llm_tool` 已足够，不需要额外注册 |

# @llm_tool 或 @filter.llm_tool 的局限性

让我查看一下 `@llm_tool` 装饰器是如何解析参数的：
通过分析源码，我发现了一个重要的问题：

## 当前 `@llm_tool` 的局限性

**`@llm_tool` 装饰器目前无法通过 `required` 关键字限定必填参数。**

简单说就是：
你可以在不使用 @filter.llm_tool 装饰器的情况下，定义一个工具，但是限定必填参数，非必填参数可以不填，如：
```python
    parameters={
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "城市名称"},
            "date": {"type": "string", "description": "日期（可选）"}
        },
        "required": ["city"]  # 必填字段
    },
```
但是你不能在 `@llm_tool` 中通过函数参数的默认值来区分必填和可选参数，因为 `@llm_tool` 装饰器的参数解析器不会生成 `required` 字段。即使你这样写：

```python
from astrbot.api.event import AstrMessageEvent

@llm_tool(name="get_weather")
async def get_weather(self, event: AstrMessageEvent, city: str, date: str = "") -> str:
    """获取指定城市的天气信息
    
    Args:
        city: 城市名称（必填）
        date: 日期（可选，默认为今天）
    """
```

框架只会生成 `properties`，不会生成 `required` 字段，LLM 会认为所有参数都是可选的。

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

它**只构建了 `properties`，没有构建 `required` 字段**。

### 两种方式的对比

| 特性 | `@llm_tool` 装饰器 | 继承 `FunctionTool` |
|------|-------------------|---------------------|
| 必填参数限定 | ❌ 不支持（所有参数都视为可选） | ✅ 支持 |
| 参数类型定义 | 通过 docstring 解析 | 手动定义 JSON Schema |
| 灵活性 | 低 | 高 |
| 易用性 | 高 | 低 |

---

## 解决方案

### 方案一：使用继承 `FunctionTool` 的方式

```python
from astrbot.api import FunctionTool, ToolExecResult
from astrbot.core.agent.run_context import ContextWrapper

class WeatherTool(FunctionTool):
    def __init__(self):
        super().__init__(
            name="get_weather",
            description="获取指定城市的天气信息",
            parameters={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称"
                    },
                    "date": {
                        "type": "string",
                        "description": "日期（可选）"
                    }
                },
                "required": ["city"]  # 只有 city 是必填的
            }
        )
    
    async def call(self, context: ContextWrapper, **kwargs) -> ToolExecResult:
        city = kwargs.get("city", "北京")
        date = kwargs.get("date", "")
        weather = await fetch_weather(city, date)
        return f"{city}今天{weather}"
```

### 方案二：在 `@llm_tool` 中通过函数签名的默认值区分

**目前不支持**。你只能通过函数参数的默认值来让 LLM 知道某个参数是可选的：

```python
from astrbot.api.event import AstrMessageEvent

@llm_tool(name="get_weather")
async def get_weather(self, event: AstrMessageEvent, city: str, date: str = "") -> str:
    """获取指定城市的天气信息
    
    Args:
        city: 城市名称
        date: 日期（可选，默认为今天）
    """
    weather = await fetch_weather(city, date)
    return f"{city}今天{weather}"
```

但这**只是在描述层面告诉 LLM**，并没有在 JSON Schema 中设置 `required` 字段。LLM 可能会认为所有参数都是可选的。

### 方案三：手动创建 `FunctionTool` 并注册

```python
from astrbot.api import FunctionTool, ToolSet
from astrbot.api.event import AstrMessageEvent

class MyPlugin(Star):
    def __init__(self, context):
        super().__init__(context)
        
        # 创建带 required 的工具
        weather_tool = FunctionTool(
            name="get_weather",
            description="获取指定城市的天气信息",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称"},
                    "date": {"type": "string", "description": "日期（可选）"}
                },
                "required": ["city"]  # 必填字段
            },
            handler=self._get_weather_handler
        )
        
        # 注册到框架
        self.context.add_llm_tools(weather_tool)
    
    async def _get_weather_handler(self, event: AstrMessageEvent, city: str, date: str = "") -> str:
        # event 是框架自动注入的第一个参数
        weather = await fetch_weather(city, date)
        return f"{city}今天{weather}"
```

---

## 总结

| 需求 | 推荐方式 |
|------|---------|
| 简单工具，不需要 required | `@llm_tool` 装饰器 |
| 需要 required 限定必填参数 | 继承 `FunctionTool` 类 |
| 需要复杂参数结构 | 继承 `FunctionTool` 类 |

**结论**：当前 `@llm_tool` 装饰器**不支持** `required` 字段。如果你需要严格限定必填参数，只能通过继承 `FunctionTool` 类或手动创建 `FunctionTool` 的方式来实现。这可能是 AstrBot 的一个待改进点。
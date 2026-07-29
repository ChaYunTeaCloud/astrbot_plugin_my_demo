# AstrBot-Tool

## 一、Tool 是什么

Tool（工具）是让 LLM（大语言模型）能够**调用外部功能**的机制。类似于 ChatGPT 的 Function Calling，你可以定义一个工具，告诉 LLM "当用户问天气时，可以调用这个工具来获取天气信息"。

在 AstrBot 中，Tool 的本质是一个 `FunctionTool` 类。所有工具（包括内置工具、MCP 工具、插件工具）最终都是 `FunctionTool` 实例，存储在 `llm_tools.func_list` 中。

注册工具的两种方式：
- 继承 `FunctionTool[AstrAgentContext]` 类：灵活，支持完整的 JSON Schema 定义
- `@filter.llm_tool` 装饰器：简洁，框架自动从 docstring 解析参数 schema

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

### 方式二：继承 FunctionTool 类（官方推荐）

更灵活的方式，支持完整的 JSON Schema 定义和 `required` 字段。官方推荐使用 `@dataclass` 装饰器和 `AstrAgentContext` 泛型参数。

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

#### 为什么使用 `@dataclass`？

`@dataclass` 装饰器允许你用**类属性**的方式定义工具的字段（`name`、`description`、`parameters`），而不需要在 `__init__` 中手动调用 `super().__init__()`。这是 Python 中定义数据类的标准方式，代码更简洁。

#### 为什么使用 `AstrAgentContext`？

`FunctionTool[AstrAgentContext]` 中的 `AstrAgentContext` 指定了 `call` 方法中 `context` 参数的具体类型。这使得你可以通过 `context` 访问更完整的上下文：

```python
async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> ToolExecResult:
    # 获取当前事件
    event = context.context.event
    
    # 获取完整的 LLM 上下文（用于调用子 Agent 等高级功能）
    ctx = context.context.context
    
    # 获取对话历史
    messages = context.messages
    
    # 实现工具逻辑
    ...
```

### 方式三：手动创建 FunctionTool

如果你有特殊需求，可以手动创建 `FunctionTool` 并注册。

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
            handler=self._get_weather_handler
        )
        
        # 注册到框架
        self.context.add_llm_tools(weather_tool)
    
    async def _get_weather_handler(self, event: AstrMessageEvent, city: str, date: str = "") -> str:
        weather = await fetch_weather(city, date)
        return f"{city}今天{weather}"
```

## 六、handler 的注册与调用

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

## 七、局限性

### @llm_tool 不支持 required 字段

`@llm_tool` 装饰器目前无法通过 `required` 关键字限定必填参数。即使你在函数签名中给参数加了默认值，框架也不会生成 `required` 字段，LLM 会认为所有参数都是可选的。

```python
# 这样写，框架不会生成 required 字段
@llm_tool(name="get_weather")
async def get_weather(self, event: AstrMessageEvent, city: str, date: str = "") -> str:
    """获取指定城市的天气信息
    
    Args:
        city: 城市名称（必填）
        date: 日期（可选）
    """
```

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

## 八、相关 API 和装饰器

### API 导出

**文件**：astrbot/api/__init__.py

| 导出 | 说明 |
|------|------|
| `FunctionTool` | 函数工具类 |
| `ToolSet` | 工具集合类 |
| `BaseFunctionToolExecutor` | 工具执行器基类 |
| `llm_tool` | 装饰器，用于注册 LLM 工具 |

### 相关装饰器

在 `api.event.filter` 中还有：

| 装饰器 | 说明 |
|--------|------|
| `@llm_tool(name="xxx")` | 注册 LLM 工具 |
| `@on_using_llm_tool()` | 监听工具使用事件 |
| `@on_llm_tool_respond()` | 监听工具响应事件 |

## 九、动态控制工具

### 什么时候需要额外的 @on_llm_request？

当你需要**动态控制工具**时（比如根据用户权限决定是否提供某个工具）：

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

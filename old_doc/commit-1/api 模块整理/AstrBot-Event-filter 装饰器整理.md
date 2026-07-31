# AstrBot @filter 装饰器整理

> 源码路径：`.venv/Lib/site-packages/astrbot/core/star/register/star_handler.py`
> 导出路径：`from astrbot.api.event import filter`

`filter` 名字由来：这些装饰器用于"筛选/过滤"消息——只有符合特定条件的消息才会被 Handler 处理。

`filter` 就叫**"筛选器" 或者 "过滤器"**。

从源码看，AstrBot 内部正是这么命名的——核心过滤逻辑类都叫 xxxFilter ：

- EventMessageTypeFilter （消息类型筛选器）
- PermissionTypeFilter （权限筛选器）
- PlatformAdapterTypeFilter （平台类型筛选器）
- RegexFilter （正则筛选器）
- CommandFilter （命令筛选器）
- CommandGroupFilter （命令组筛选器）
而 filter 就是把这些筛选器的**注册入口（装饰器）**聚合在一起的命名空间。

---

## 一、事件钩子类（生命周期事件）

以下装饰器在特定时机触发，参数由框架固定传入。

### 1.1 框架加载事件

- `@filter.on_astrbot_loaded()`
  - 触发时机：AstrBot 框架启动完成时
  - 传入参数：无额外参数，只有 `event`
  - 示例：
    ```python
    @filter.on_astrbot_loaded()
    async def on_loaded(self) -> None:
        pass
    ```

- `@filter.on_platform_loaded()`
  - 触发时机：平台适配器加载完成时
  - 传入参数：无额外参数，只有 `event`
  - 示例：
    ```python
    @filter.on_platform_loaded()
    async def on_platform_ready(self) -> None:
        pass
    ```

### 1.2 插件生命周期事件

- `@filter.on_plugin_loaded()`
  - 触发时机：有插件加载完成时
  - 传入参数：`metadata`（StarMetadata 对象）
  - 示例：
    ```python
    @filter.on_plugin_loaded()
    async def on_plugin_load(self, metadata) -> None:
        print(f"插件 {metadata.name} 已加载")
    ```

- `@filter.on_plugin_unloaded()`
  - 触发时机：有插件卸载完成时
  - 传入参数：`metadata`（StarMetadata 对象）

- `@filter.on_plugin_error()`
  - 触发时机：插件处理消息异常时
  - 传入参数：`event, plugin_name, handler_name, error, traceback_text`
  - 说明：调用 `event.stop_event()` 可屏蔽默认报错回显
  - 示例：
    ```python
    @filter.on_plugin_error()
    async def on_error(self, event, plugin_name, handler_name, error, traceback_text) -> None:
        event.stop_event()
    ```

### 1.3 LLM 请求生命周期事件

- `@filter.on_waiting_llm_request()`
  - 触发时机：消息确定要调用 LLM 但还未开始排队等锁时
  - 传入参数：只有 `event`
  - 用途：发送"正在思考中..."等用户反馈
  - 示例：
    ```python
    @filter.on_waiting_llm_request()
    async def on_waiting(self, event: AstrMessageEvent) -> None:
        await event.send("正在思考中...")
    ```

- `@filter.on_llm_request()`
  - 触发时机：LLM 请求发出前
  - 传入参数：`event, req`（ProviderRequest）
  - 用途：修改请求参数（如追加 system_prompt）
  - 示例：
    ```python
    from astrbot.api.provider import ProviderRequest

    @filter.on_llm_request()
    async def modify_request(self, event: AstrMessageEvent, req: ProviderRequest) -> None:
        req.system_prompt += "你是一个猫娘..."
    ```

- `@filter.on_llm_response()`
  - 触发时机：LLM 响应返回后
  - 传入参数：`event, response`（LLMResponse）
  - 示例：
    ```python
    from astrbot.api.provider import LLMResponse

    @filter.on_llm_response()
    async def on_response(self, event: AstrMessageEvent, response: LLMResponse) -> None:
        print(f"响应: {response.completion_text}")
    ```

### 1.4 Agent 生命周期事件

- `@filter.on_agent_begin()`
  - 触发时机：Agent 开始运行时
  - 传入参数：`event, run_context`
  - 示例：
    ```python
    from astrbot.core.agent.run_context import ContextWrapper
    from astrbot.core.astr_agent_context import AstrAgentContext

    @filter.on_agent_begin()
    async def on_begin(self, event: AstrMessageEvent, run_context: ContextWrapper[AstrAgentContext]) -> None:
        pass
    ```

- `@filter.on_agent_done()`
  - 触发时机：Agent 运行完成后
  - 传入参数：`event, run_context, response`
  - 示例：
    ```python
    @filter.on_agent_done()
    async def on_done(self, event: AstrMessageEvent, run_context, response: LLMResponse) -> None:
        pass
    ```

### 1.5 工具调用事件

- `@filter.on_using_llm_tool()`
  - 触发时机：函数工具调用前
  - 传入参数：`event, tool, tool_args`
  - 示例：
    ```python
    from astrbot.core.agent.tool import FunctionTool

    @filter.on_using_llm_tool()
    async def on_tool_use(self, event: AstrMessageEvent, tool: FunctionTool, tool_args: dict | None) -> None:
        print(f"调用工具: {tool.name}, 参数: {tool_args}")
    ```

- `@filter.on_llm_tool_respond()`
  - 触发时机：函数工具返回结果后
  - 传入参数：`event, tool, tool_args, tool_result`
  - 示例：
    ```python
    @filter.on_llm_tool_respond()
    async def on_tool_respond(self, event: AstrMessageEvent, tool: FunctionTool, tool_args: dict | None, tool_result) -> None:
        print(f"工具 {tool.name} 返回: {tool_result}")
    ```

### 1.6 消息发送事件

- `@filter.on_decorating_result()`
  - 触发时机：发送消息前（装饰结果阶段）
  - 传入参数：只有 `event`

- `@filter.after_message_sent()`
  - 触发时机：消息发送后
  - 传入参数：只有 `event`

---

## 二、消息过滤类（消息处理装饰器）

以下装饰器用于筛选符合条件的消息，只处理匹配的消息。

### 2.1 命令处理

- `@filter.command(name, sub_command, alias)`
  - 参数：
    - `name`: 命令名称（如 `"hello"`）
    - `sub_command`: 子命令名称（用于命令组）
    - `alias`: 命令别名集合
  - 触发时机：用户发送匹配的命令时
  - 传入参数：只有 `event`
  - 示例：
    ```python
    @filter.command(name="hello")
    async def hello_handler(self, event: AstrMessageEvent):
        await event.send("Hello!")
    ```

- `@filter.command_group(name, sub_command, alias)`
  - 用于注册命令组，支持级联注册子命令
  - 示例：
    ```python
    @filter.command_group(name="admin")
    async def admin_group(self):
        pass

    @admin_group.command(name="ban")
    async def ban_user(self, event: AstrMessageEvent):
        pass
    ```

### 2.2 正则匹配

- `@filter.regex(pattern)`
  - 参数：`pattern` 正则表达式字符串或 Pattern 对象
  - 触发时机：消息内容匹配正则时
  - 传入参数：只有 `event`
  - 示例：
    ```python
    @filter.regex(r"^\d+$")
    async def handle_number(self, event: AstrMessageEvent):
        pass
    ```

### 2.3 消息类型过滤

- `@filter.event_message_type(event_type)`
  - 参数：`EventMessageType` 枚举值
  - 可用值：
    - `EventMessageType.ALL` — 所有消息
    - `EventMessageType.GROUP` — 群消息
    - `EventMessageType.PRIVATE` — 私聊消息
  - 示例：
    ```python
    from astrbot.api.event.filter import EventMessageType

    @filter.event_message_type(EventMessageType.GROUP)
    async def handle_group(self, event: AstrMessageEvent):
        pass
    ```

### 2.4 平台类型过滤

- `@filter.platform_adapter_type(platform_type)`
  - 参数：`PlatformAdapterType` 枚举值
  - 可用值：
    - `PlatformAdapterType.AIOCIHTTP`
    - `PlatformAdapterType.GOCQ`
    - `PlatformAdapterType.DISCORD`
    - 等等（根据实际支持的平台）
  - 示例：
    ```python
    from astrbot.api.event.filter import PlatformAdapterType

    @filter.platform_adapter_type(PlatformAdapterType.AIOCIHTTP)
    async def handle_aiocqhttp(self, event: AstrMessageEvent):
        pass
    ```

### 2.5 权限过滤

- `@filter.permission_type(permission_type, raise_error=True)`
  - 参数：
    - `permission_type`: `PermissionType` 枚举值
    - `raise_error`: 无权限时是否报错，默认 True
  - 可用值：
    - `PermissionType.ADMIN` — 管理员
    - `PermissionType.OWNER` — 超级管理员
    - `PermissionType.MEMBER` — 普通成员
  - 示例：
    ```python
    from astrbot.api.event.filter import PermissionType

    @filter.permission_type(PermissionType.ADMIN)
    async def admin_only(self, event: AstrMessageEvent):
        pass
    ```

### 2.6 自定义过滤

- `@filter.custom_filter(custom_filter_obj, raise_error=True)`
  - 参数：
    - `custom_filter_obj`: CustomFilter 对象
    - `raise_error`: 过滤失败时是否报错
  - 用途：自定义复杂的消息过滤逻辑

---

## 三、LLM 工具相关

### 3.1 注册函数工具

- `@filter.llm_tool(name=None)`
  - 参数：`name` 工具名称（不填则使用函数名）
  - 触发时机：LLM 决定调用此工具时
  - 传入参数：`event` + 函数定义的参数
  - 说明：必须写 docstring 描述参数类型，格式如下：
  - 示例：
    ```python
    @filter.llm_tool(name="get_weather")
    async def get_weather(self, event: AstrMessageEvent, location: str):
        """获取天气信息。

        Args:
            location(string): 地点
        """
        return f"{location} 的天气是晴天"
    ```
  - 返回值：
    - 返回 `str`：结果加入下一次 LLM 请求的 prompt
    - 返回 `None`：不加入 prompt
  - 支持的参数类型：`string`, `number`, `object`, `array`, `boolean`

---

## 四、Agent 相关

### 4.1 注册 Agent

- `@filter.agent(name, instruction, tools, run_hooks)`
  - 参数：
    - `name`: Agent 名称
    - `instruction`: Agent 指令
    - `tools`: 工具列表（字符串或 FunctionTool）
    - `run_hooks`: 运行时钩子
  - 用途：注册一个可被 LLM 通过 handoff 调用的 Agent
  - 示例：
    ```python
    @filter.agent(name="code_assistant", instruction="你是一个代码助手")
    async def code_agent_handler(self, event: AstrMessageEvent):
        pass
    ```

---

## 五、装饰器组合使用

多个装饰器可以叠加使用，消息必须同时满足所有条件：

```python
@filter.command(name="admin")
@filter.permission_type(PermissionType.ADMIN)
@filter.event_message_type(EventMessageType.GROUP)
async def admin_group_only(self, event: AstrMessageEvent):
    pass
```

---

## 六、重要说明

1. 所有事件钩子类装饰器必须加括号：`@filter.on_llm_request()` 而非 `@filter.on_llm_request`
2. Handler 的参数数量必须与框架传入的一致，否则会触发 TypeError
3. 不使用的参数可用 `_` 占位：`async def handler(self, event, _): pass`
4. 事件钩子不会阻止消息继续处理，除非调用 `event.stop_event()`
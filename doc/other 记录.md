# 插件的本质

写插件就是在 AstrBot 运行的关键节点上注册 handler。插件整体是一个 handler 集合。
本质是写一堆 HOOK 或 Command 以及与之对应的 handler。
两种触发方式：

- **Hook（拦截/钩子）**：AstrBot 走完流程本应正常进行，我在中间截住、做完事、放行。
  - 一个事件(event)可以挂多个HOOK，一个 HOOK 对应一个 handler。
  - 同一个事件的HOOK，可以按 `priority` 排队执行，数值越大越优先，默认 0。每个 hook 对应一个 handler 方法。
  - AstrBot 提供了事件装饰器，为了结构，它专门做了一个 api 层（门面层）对这些装饰器进行了简单包装，并且提供了使用这些装饰器的入口： filter 。
  - 我可以用 filter 持有的装饰器告诉 AstrBot 我要钩住某个事件类型(eventType)。
  - 我给HOOK 写的 handler 就是我钩住这个事件之后要做什么，做完后解开这个钩子。
  - 比如：
    - 用@filter.on_llm_request() 钩住当有 LLM 请求时的事件：
      - AstrBot框架准备给LLM发消息了，用钩子把事件「拎起来」-> 改改提示词、塞几个工具 -> 把钩子放下去让AstrBot继续。
    - 用@filter.on_llm_response() 钩住当有 LLM 回复时的事件：
      - AstrBot框架收到LLM的回复了，用钩子把事件「拎起来」-> 处理回复、设置结果 -> 把钩子放下去让AstrBot继续。

- **Command（被调）**：AstrBot 识别到 `/xxx`，主动来找你：有没有人能处理？有就交给你。
  - 比如：
    - 我用 @filter.command(name="hello") 注册了一个 handler。
    - Astrbot识别到用户发送了 `/hello` 命令，调用这个handler。

# Handler 注册与调用

`@filter.xxx()` 装饰器标记的每个方法，AstrBot 都会将其注册为一个 Handler，存入 `star_handlers_registry` 中。当对应事件触发时，框架会遍历注册表，依次调用所有匹配的 Handler。

star_handlers_registry 是指向 StarHandlerRegistry 类的一个实例的全局变量吗？是的。定义位置：astrbot/core/star/star_handler.py#L216

StarHandlerRegistry 类的定义：astrbot/core/star/star_handler.py
从它的实现中可以看到它根据 EventType 来分类存储 Handler，重载了 get_handlers_by_event_type 方法。根据不同的 EventType，返回不同的 Handler 列表。

从 call_event_hook 的实现（astrbot/core/pipeline/context_utils.py #L78-112）也可以看到，它根据 hook_type 来调用不同的 Handler。

也就是说：诸如【@filter.on_llm_request()】、【@filter.on_llm_response()】等装饰器，会根据不同的 EventType 来注册不同的 Handler。所以，当对应事件触发时，框架会根据 hook_type 来调用不同的 Handler。

另外，【@filter.on_llm_request()】这类装饰器它只是注册了一个 Handler，而不是直接调用，所以从【on_llm_request()】跟踪源码，跟踪不到调用 handler 的逻辑。不过单纯的插件开发一般也无需关注其调用逻辑。

简化流程：
```
装饰器注册 → 存入注册表 → 事件触发 → 框架遍历注册表 → 逐个调用你的方法
```

只有符合条件的才会被调用 。比如 @filter.command(name="hello") 只有用户发送 "hello" 命令时才会触发； @filter.on_llm_request() 只有在 LLM 请求发出时才会触发，不是每条消息都会走。

## Handler 相关的核心源码路径：

1. Handler 注册与元数据定义
   - astrbot/core/star/star_handler.py
   - 包含： StarHandlerRegistry （注册表）、 StarHandlerMetadata （元数据）、 EventType （事件类型枚举）
2. 装饰器实现（@filter.xxx）
   - astrbot/core/star/register/star_handler.py
   - 包含： register_command 、 register_on_llm_request 等所有装饰器函数
3. Handler 实际调用逻辑
   - astrbot/core/pipeline/context_utils.py
   - 包含： call_handler() （执行单个 handler）、 call_event_hook() （执行事件钩子）
4. 命令/正则过滤器
   - astrbot/core/star/filter/command.py — CommandFilter
   - astrbot/core/star/filter/regex.py — RegexFilter

## Handler 实际调用逻辑

Handler 的调用逻辑分两层：

### 1. call_event_hook() — 事件钩子调用（适用于 @filter.on_llm_request 等）
位置：astrbot/core/pipeline/context_utils.py #L78-112

流程：
1. 从 star_handlers_registry 获取所有匹配 EventType 的 handler
2. 逐个调用 handler.handler(event, *args, **kwargs)
3. 每次调用后检查 event.is_stopped()，如果被停止则提前返回
4. 返回是否被终止

核心代码：
```python
handlers = star_handlers_registry.get_handlers_by_event_type(hook_type)
for handler in handlers:
    await handler.handler(event, *args, **kwargs)  # 直接调用
    if event.is_stopped():
        return True  # 事件被终止
```

### 2. call_handler() — 命令处理器调用（适用于 @filter.command 等）
位置： context_utils.py #L12-76

流程：
1. 调用 handler(event, *args, **kwargs) 得到返回值
2. 判断返回值类型：
   - 如果是异步生成器 → 支持"洋葱模型"，逐步执行 yield
   - 如果是协程 → 执行一次，取返回值
3. 如果返回 MessageEventResult/CommandResult → 设置到 event.set_result()
4. yield 控制权交回管道继续执行

核心代码：
```python
ready_to_call = handler(event, *args, **kwargs)

if inspect.isasyncgen(ready_to_call):
    # 异步生成器：逐步执行，支持洋葱模型
    async for ret in ready_to_call:
        if isinstance(ret, MessageEventResult):
            event.set_result(ret)
        yield
elif inspect.iscoroutine(ready_to_call):
    # 普通协程：执行一次
    ret = await ready_to_call
    if isinstance(ret, MessageEventResult):
        event.set_result(ret)
    yield
```

### ## 两者的区别

| 维度 | `call_event_hook` | `call_handler` |
|------|------------------|---------------|
| 用途 | 事件钩子（on_llm_request 等） | 命令处理（@filter.command） |
| 返回值处理 | 不处理返回值 | 处理 MessageEventResult 并设置到 event |
| 支持生成器 | 不支持 | 支持（洋葱模型） |
| 停止传播 | 支持（event.is_stopped） | 支持 |

简单说： call_event_hook 是"通知型"调用，只管调用不处理返回； call_handler 是"处理型"调用，会处理返回值并设置到事件对象上。

### 这两个方法为什么会放在 context_utils.py 而不是名为 handler_utils.py
猜测：

确实是"挂羊头卖狗肉"。从引用关系看：
- context_utils.py 被 pipeline/context.py 导入使用
- 它原本应该是给 Pipeline 的 Context 处理用的工具函数
- 但后来 Handler 调用逻辑也被放进来了

这种情况在开源项目中很常见—— 文件命名时它确实是放上下文工具的，但随着功能迭代，Handler 调用逻辑和"上下文处理"（事件在管道中的流转、结果设置）紧密耦合，就被放进来了 。严格来说应该改名叫 handler_utils.py 更准确。

## Handler 参数

虽然我们用装饰器来注册 handler，但是装饰器本身**不决定参数**，它只做一件事：**把函数注册到对应事件类型的 Handler 列表里**。

真正决定参数的是**触发事件的那段框架代码**。用图表示：

```
装饰器注册阶段：
@filter.on_llm_request
def my_handler(self, event, req): ...
         ↓
  只是标记：这个函数属于 EventType.OnLLMRequestEvent 类型
  不涉及任何参数定义


事件触发阶段（框架内部）：
  astrbot/core/pipeline/process_stage/method/agent_sub_stages/third_party.py#L335:
  call_event_hook(event, EventType.OnLLMRequestEvent, req)
                                              ↑
                                         这里传了 req
         ↓
  call_event_hook 内部：
  handler.handler(event, req)  → 函数被调用，收到 2 个参数
```

**结论：参数约束来自"谁触发了事件"，而不是装饰器本身。** 每个 `EventType` 在框架里只有一个（或几个）触发点，每个触发点固定传什么参数是写死的。这就是为什么同一种事件类型的所有 Handler 必须接收相同数量的参数。

          
## AstrBot 中基于 `EventType` 的参数传递逻辑。

下面是详细的分析结果。

---

### 核心发现：AstrBot **不使用** if 语句/switch-case 来判断参数传递

AstrBot 采用的是一种**"可变参数透传"（pass-through）模式**——`call_event_hook` 本身**完全不关心** `EventType` 与参数的对应关系，它只是一个纯粹的"转发器"。

### 核心实现：`call_event_hook` 函数

位置：astrbot/core/pipeline/context_utils.py#L78-L112

```python
async def call_event_hook(
    event: AstrMessageEvent,
    hook_type: EventType,
    *args,       # ← 可变位置参数，调用方决定传什么
    **kwargs,    # ← 可变关键字参数，调用方决定传什么
) -> bool:
    handlers = star_handlers_registry.get_handlers_by_event_type(
        hook_type,
        plugins_name=event.plugins_name,
    )
    for handler in handlers:
        try:
            assert inspect.iscoroutinefunction(handler.handler)
            await handler.handler(event, *args, **kwargs)  # ← 原样透传！
        except BaseException:
            logger.error(traceback.format_exc())
        if event.is_stopped():
            return True
    return event.is_stopped()
```

**关键点**：
- `*args` / `**kwargs` 完全透传，不做任何检查、转换或过滤
- 函数内部**没有任何** `if event_type == ...` 或 `match/case` 逻辑
- 参数传递的约束完全由**调用方（call site）**保证

---

### 参数绑定的真正决定权：各触发点（Call Sites）

每个 `EventType` 的参数签名由**谁触发事件**决定。以下是所有触发点的完整映射：

#### 1. `OnAstrBotLoadedEvent` — 无参数

| 触发位置 | 代码 |
|---------|------|
| astrbot/core/core_lifecycle.py#L352-L361 | `handler.handler()` — **只传 event（通过 call_event_hook 时无额外参数）** |

#### 2. `OnPlatformLoadedEvent` — 无参数

| 触发位置 | 代码 |
|---------|------|
| astrbot/core/platform/manager.py#L228-L236 | `handler.handler()` — 同上，无额外参数 |

#### 3. `OnWaitingLLMRequestEvent` — 无额外参数

| 触发位置 | 代码 |
|---------|------|
| astrbot/core/pipeline/process_stage/method/agent_sub_stages/internal.py#L217 | `call_event_hook(event, EventType.OnWaitingLLMRequestEvent)` — 只有 `event` |

#### 4. `OnLLMRequestEvent` — 传 `req`（ProviderRequest）

| 触发位置 | 代码 |
|---------|------|
| astrbot/core/pipeline/process_stage/method/agent_sub_stages/internal.py#L269 | `call_event_hook(event, EventType.OnLLMRequestEvent, req)` |
| astrbot/core/pipeline/process_stage/method/agent_sub_stages/third_party.py#L335 | `call_event_hook(event, EventType.OnLLMRequestEvent, req)` |

**Handler 签名约束**：`async def handler(event, req)` — 必须接收 2 个参数

#### 5. `OnLLMResponseEvent` — 传 `llm_response`（LLMResponse）

| 触发位置 | 代码 |
|---------|------|
| astrbot/core/astr_agent_hooks.py#L31-L35 | `call_event_hook(event, EventType.OnLLMResponseEvent, llm_response)` |

**Handler 签名约束**：`async def handler(event, llm_response)`

#### 6. `OnAgentBeginEvent` — 传 `run_context`（ContextWrapper）

| 触发位置 | 代码 |
|---------|------|
| astrbot/core/astr_agent_hooks.py#L17-L21 | `call_event_hook(event, EventType.OnAgentBeginEvent, run_context)` |

**Handler 签名约束**：`async def handler(event, run_context)`

#### 7. `OnAgentDoneEvent` — 传 `run_context` + `llm_response`

| 触发位置 | 代码 |
|---------|------|
| astrbot/core/astr_agent_hooks.py#L36-L41 | `call_event_hook(event, EventType.OnAgentDoneEvent, run_context, llm_response)` |

**Handler 签名约束**：`async def handler(event, run_context, llm_response)` — 3 个参数

#### 8. `OnUsingLLMToolEvent` — 传 `tool` + `tool_args`

| 触发位置 | 代码 |
|---------|------|
| astrbot/core/astr_agent_hooks.py#L49-L54 | `call_event_hook(event, EventType.OnUsingLLMToolEvent, tool, tool_args)` |

**Handler 签名约束**：`async def handler(event, tool, tool_args)`

#### 9. `OnLLMToolRespondEvent` — 传 `tool` + `tool_args` + `tool_result`

| 触发位置 | 代码 |
|---------|------|
| astrbot/core/astr_agent_hooks.py#L64-L70 | `call_event_hook(event, EventType.OnLLMToolRespondEvent, tool, tool_args, tool_result)` |

**Handler 签名约束**：`async def handler(event, tool, tool_args, tool_result)` — 4 个参数

#### 10. `OnDecoratingResultEvent` — 直接调用（非 call_event_hook）

| 触发位置 | 代码 |
|---------|------|
| astrbot/core/pipeline/result_decorate/stage.py#L159-L162 | 直接遍历 `star_handlers_registry.get_handlers_by_event_type(...)` 后 `handler.handler(event)` — 只传 event |

#### 11. `OnAfterMessageSentEvent` — 无额外参数

| 触发位置 | 代码 |
|---------|------|
| astrbot/core/pipeline/respond/stage.py#L321 | `call_event_hook(event, EventType.OnAfterMessageSentEvent)` — 只有 event |

#### 12. `OnPluginErrorEvent` — 传 4 个参数

| 触发位置 | 代码 |
|---------|------|
| astrbot/core/pipeline/process_stage/method/star_request.py#L59-L66 | `call_event_hook(event, EventType.OnPluginErrorEvent, md.name, handler.handler_name, e, traceback_text)` |

**Handler 签名约束**：`async def handler(event, plugin_name, handler_name, error, traceback)` — 5 个参数

#### 13. `OnPluginLoadedEvent` / `OnPluginUnloadedEvent` — 无参数

| 触发位置 | 代码 |
|---------|------|
| astrbot/core/star/star_manager.py#L1421-L1424 | `handler.handler()` — 只传 event |
| astrbot/core/star/star_manager.py#L2008-L2011 | 同上 |

#### 14. `AdapterMessageEvent` — 通过 `call_handler` 调用

| 触发位置 | 代码 |
|---------|------|
| astrbot/core/pipeline/waking_check/stage.py#L163-L165 | 通过 `call_handler(event, handler.handler, **params)` 调用，参数由指令解析决定 |

#### 15. `OnCallingFuncToolEvent` — 特殊处理

此事件类型**不通过 `call_event_hook` 触发**。它在 astrbot/core/star/register/star_handler.py#L669 注册后，handler 被存入 `FunctionToolManager`，由 Agent 工具执行器直接调用，参数为 LLM 返回的工具调用参数。

---

### `EventType` 枚举定义

文件位置：astrbot/core/star/star_handler.py#L218-L240

共 16 个事件类型：

```python
class EventType(enum.Enum):
    OnAstrBotLoadedEvent = enum.auto()       # AstrBot 加载完成
    OnPlatformLoadedEvent = enum.auto()       # 平台加载完成
    AdapterMessageEvent = enum.auto()         # 适配器消息
    OnWaitingLLMRequestEvent = enum.auto()    # 等待 LLM（获取锁前）
    OnLLMRequestEvent = enum.auto()           # LLM 请求
    OnLLMResponseEvent = enum.auto()          # LLM 响应
    OnAgentBeginEvent = enum.auto()           # Agent 开始
    OnAgentDoneEvent = enum.auto()            # Agent 完成
    OnDecoratingResultEvent = enum.auto()     # 发送消息前
    OnCallingFuncToolEvent = enum.auto()      # 调用函数工具
    OnUsingLLMToolEvent = enum.auto()         # 使用 LLM 工具
    OnLLMToolRespondEvent = enum.auto()       # LLM 工具响应
    OnAfterMessageSentEvent = enum.auto()     # 发送消息后
    OnPluginErrorEvent = enum.auto()          # 插件错误
    OnPluginLoadedEvent = enum.auto()         # 插件加载
    OnPluginUnloadedEvent = enum.auto()       # 插件卸载
```

---

### 总结

| 方面 | 实现方式 |
|------|---------|
| **判断机制** | **无** if/switch-case。`call_event_hook` 是纯粹的透传函数 |
| **参数决定者** | 每个**触发点（call site）** 写死了传什么参数 |
| **参数传递方式** | `*args, **kwargs` 可变参数透传 |
| **Handler 约束** | 同一种 `EventType` 的所有 Handler 必须接收相同数量/含义的参数（由触发点保证，无运行时强制校验） |
| **设计模式** | 观察者模式 + 转发器（Proxy/Pass-through）模式 |

这种设计的优点是**简单直接**——`call_event_hook` 不需要了解任何 `EventType` 的语义，新增事件类型只需在调用方传对参数即可。缺点是**缺乏运行时校验**——如果 Handler 的参数签名与触发点不一致，只会在 `call_handler` 中被 `TypeError` 捕获并记录日志（见 astrbot/core/pipeline/context_utils.py#L38-L42），不会阻止事件传播。

## 关于 StarHandlerRegistry类 中 get_handlers_by_event_type 方法有多个重载的猜测

Q: 为什么 StarHandlerRegistry 类中 get_handlers_by_event_type 方法有多个重载？是因为返回值会不同所以这样吗？感觉没有必要重载。

这些 `@overload` 确实**没有实际必要**。让我分析一下。

### 现状分析

astrbot/core/star/star_handler.py#L32-L148 有 **14 个 `@overload` 定义**（13 个具体事件类型 + 1 个兜底），而实际实现只有 [L150-L186](astrbot/core/star/star_handler.py#L150-L186) 一个。

### 关键事实：实现完全不区分类型

```python
def get_handlers_by_event_type(
    self,
    event_type: EventType,       # ← 接收任意 EventType
    only_activated=True,
    plugins_name: list[str] | None = None,
) -> list[StarHandlerMetadata]:  # ← 返回值无类型参数，统一裸类型
    handlers = []
    for handler in self._handlers:
        if handler.event_type != event_type:  # ← 只做值比较，不做类型派发
            continue
        ...
        handlers.append(handler)
    return handlers
```

实现就是一个**简单的过滤循环**——按 `event_type` 的值做匹配，返回 `list[StarHandlerMetadata]`。没有任何类型分发逻辑。

### overload 返回值对比

| 重载（部分） | 返回类型 |
|---|---|
| `OnAstrBotLoadedEvent` | `list[StarHandlerMetadata[Callable[..., Awaitable[Any]]]]` |
| `OnPlatformLoadedEvent` | `list[StarHandlerMetadata[Callable[..., Awaitable[Any]]]]` |
| `OnLLMRequestEvent` | `list[StarHandlerMetadata[Callable[..., Awaitable[Any]]]]` |
| `OnAgentBeginEvent` | `list[StarHandlerMetadata[Callable[..., Awaitable[Any]]]]` |
| `OnPluginLoadedEvent` | `list[StarHandlerMetadata[Callable[..., Awaitable[Any]]]]` |
| `AdapterMessageEvent` | `list[StarHandlerMetadata[Callable[..., Awaitable[Any] \| AsyncGenerator[Any]]]]` |
| `OnCallingFuncToolEvent` | `list[StarHandlerMetadata[Callable[..., Awaitable[Any] \| AsyncGenerator[Any]]]]` |
| **兜底 `EventType`** | `list[StarHandlerMetadata[Callable[..., Awaitable[Any] \| AsyncGenerator[Any]]]]` |

14 个重载中，**12 个返回类型完全相同**，只有 2 个（`AdapterMessageEvent` 和 `OnCallingFuncToolEvent`）多了 `AsyncGenerator[Any]`——但这也只是对这两类事件的 handler **理论上**可以是异步生成器的声明，并非方法本身能保证的。

### 为什么说没有必要

1. **实现不做类型派发**：`@overload` 的典型用途是"不同参数类型 → 不同返回类型"（如 `json.loads` 接受 `str` 返回 `Any`，接受 `bytes` 返回 `Any`）。但这里所有重载的参数类型都是 `EventType` 的不同枚举值，返回类型几乎完全一样。

2. **不提供真正的类型安全**：即使 IDE 告诉你 `OnLLMRequestEvent` 返回 `list[StarHandlerMetadata[Callable[..., Awaitable[Any]]]]`，你拿到 handler 后调用 `handler.handler(event, req)` 的参数签名仍然需要你自己记忆——`@overload` 并没有把 `EventType` 和 handler 参数签名关联起来。

3. **增加维护成本**：每新增一个 `EventType` 枚举值，都要手动添加对应的 `@overload` 定义，否则 TypeScript/pyright 会报类型错误。当前 AstrBot 有 16 个事件类型，14 个重载，已经出现了 `OnWaitingLLMRequestEvent` 和 `OnLLMToolRespondEvent` **没有重载**的情况——调用这些事件时只能走兜底的宽泛类型。

4. **简化写法**：完全可以用一个签名替代 14 个重载：

```python
def get_handlers_by_event_type(
    self,
    event_type: EventType,
    only_activated=True,
    plugins_name: list[str] | None = None,
) -> list[StarHandlerMetadata]:
    ...
```

这正是实际实现的签名，功能完全一致，只是 IDE 提示不会精确到"这个 EventType 返回的 handler 可能是 AsyncGenerator"——但这个提示本身也没有实际用处。

### 可能的初衷

开发者可能想通过 `Literal[EventType.XXX]` 让 IDE 在调用 `get_handlers_by_event_type(EventType.OnLLMRequestEvent)` 时给出更精确的返回类型提示，但由于返回类型本身没有实质差异，这个设计最终变成了"形式大于内容"的样板代码。

# 事件

事件类型：astrbot/core/star/star_handler.py
class EventType(enum.Enum)

# 装饰器

基本概念：装饰器就是一个接受函数作为参数的函数，返回一个新函数（或原函数）。一切围绕「函数是一等公民」——可以当作参数传、可以当作返回值返回。

以 @filter.on_llm_request 为例

查看 filter.on_llm_request() 的 on_llm_request
会被导航到【.venv\Lib\site-packages\astrbot\core\star\register\star_handler.py】里面的 register_on_llm_request
toolName: view_files
            
status: success
          
            
filePath: astrbot/core/star/register/star_handler.py
          
`register_on_llm_request` 的设计是**两级函数**：

```python
def register_on_llm_request(**kwargs):      # 第一级：接收配置参数
    def decorator(awaitable):               # 第二级：接收你的函数
        _ = get_handler_or_create(awaitable, EventType.OnLLMRequestEvent, **kwargs)
        return awaitable
    return decorator                        # 返回真正的装饰器
```

register_on_llm_request() 返回 decorator 函数，decorator 接收一个参数。
而 
```python
@filter.on_llm_request()
async def my_handler(self, event, req):
    ...
```
其实是一个语法糖，等价于
```python
async def my_handler(self, event, req):
    ...

my_handler = filter.on_llm_request()(my_handler)
``` 



**加括号 `@filter.on_llm_request()`：**
```
Python 执行：filter.on_llm_request() → 返回 decorator 函数
然后执行：decorator(你的函数) → 完成注册
```

**不加括号 `@filter.on_llm_request`：**
```
Python 执行：filter.on_llm_request(你的函数)
→ 相当于把你的函数当位置参数传给 register_on_llm_request
→ 但 register_on_llm_request 只接受 **kwargs，不接受位置参数
→ TypeError!
```

简单说：**带括号是先调用外层函数拿到真正的装饰器，再用装饰器包你的函数；不带括号会直接把你的函数传给外层函数，而外层函数不接收位置参数，就报错了。**

这是 Python 装饰器的标准设计模式——需要配置参数的装饰器都必须加括号调用。

# 关于插件配置项

`_conf_schema.json` 只是**配置结构的模板**，实际值不存在这里。

配置体系分两层：

| 文件 | 作用 |
|------|------|
| `_conf_schema.json`（插件目录内） | 定义配置项的**结构**：字段名、类型、描述、默认值 |
| `data/config/plugins/{插件名}.json`（AstrBot 数据目录内） | 存储配置项的**实际值** |

流程是：

1. **插件加载时**：框架读取 `_conf_schema.json`，用它作为 schema 创建 `AstrBotConfig` 实例
2. **WebUI 修改时**：用户在 WebUI 改的是实际值，写入 `data/config/plugins/{插件名}.json`
3. **插件读取时**：通过 `context.get_config()` 或 `self.config` 拿到的是已经合并了默认值和用户设置的配置对象

所以修改 `_conf_schema.json` 后如果没生效，需要**重新加载插件**（或重启 AstrBot），因为框架只在插件加载时读取 schema。如果只是想修改配置的**值**，应该通过 WebUI 或直接编辑 `data/config/plugins/{插件名}.json`。

# 哪些东西会被丢给 event 或 context 以及这二者的区别

**event（AstrMessageEvent）除了 message_obj 和 platform_meta，还有：**

| 属性 | 来源 | 说明 |
|------|------|------|
| `message_str` | 消息内容 | 纯文本消息内容 |
| `session: MessageSession` | 框架构造 | 会话标识（平台ID + 消息类型 + session_id） |
| `role: str` | 框架设置 | 用户角色（"member" 或 "admin"） |
| `is_wake: bool` | Pipeline 设置 | 是否通过唤醒阶段 |
| `is_at_or_wake_command: bool` | Pipeline 设置 | 是否是 @ 或唤醒词触发 |
| `_extras: dict` | 插件/框架写入 | 额外信息容器 |
| `created_at: float` | 构造时生成 | 事件创建时间戳 |
| `trace: TraceSpan` | 构造时生成 | 追踪对象（用于调试/监控） |
| `plugins_name: list[str]` | 框架设置 | 该事件启用的插件列表 |

---

**context（Context）接收的内容更多，是一个"大杂烩"：**

| 属性 | 说明 |
|------|------|
| `event_queue` | 事件队列（Platform 提交事件的地方） |
| `config: AstrBotConfig` | AstrBot 全局配置 |
| `db: BaseDatabase` | 数据库实例 |
| `provider_manager` | 模型提供商管理器 |
| `platform_manager` | 平台适配器管理器 |
| `conversation_manager` | 会话管理器 |
| `message_history_manager` | 平台消息历史管理器 |
| `persona_manager` | 人格角色管理器 |
| `astrbot_config_mgr` | 配置管理器 |
| `knowledge_base_manager` | 知识库管理器 |
| `cron_manager` | 定时任务管理器 |
| `subagent_orchestrator` | 子智能体编排器 |

---

### 更详细的表格

**event（AstrMessageEvent）：**

| 属性 | 来源 | 说明 |
|------|------|------|
| `message_str` | 平台适配器从原始消息中提取的纯文本 | `Platform.create_event()` 时从 `AstrBotMessage.message_str` 传入 |
| `message_obj` | 平台适配器构造的统一消息对象 | 平台适配器收到原始消息后转换为 `AstrBotMessage`，再包装进 event |
| `platform_meta` | 平台适配器的 `meta()` 方法返回 | 每个平台适配器（aiocqhttp/discord 等）各自返回自己的元数据 |
| `session` | 框架在 event 构造时创建 | 用 `platform_meta.id` + `message_type` + `session_id` 组装 |
| `role` | Pipeline 权限检查阶段设置 | 框架判断用户是否为管理员后赋值 |
| `is_wake` | Pipeline 唤醒阶段设置 | 通过 WakingStage 判断是否唤醒机器人 |
| `is_at_or_wake_command` | Pipeline 预处理阶段设置 | 检测是否 @机器人 或包含唤醒词 |
| `_extras` | 插件或框架在运行时写入 | 临时存储额外信息的容器 |
| `created_at` | event 构造时自动生成 | `time()` 时间戳 |
| `trace` | event 构造时自动创建 | TraceSpan 追踪对象，用于监控 |
| `plugins_name` | 框架在事件分发前设置 | 根据配置筛选出该事件要启用的插件列表 |

**context（Context）：**

| 属性 | 来源 | 说明 |
|------|------|------|
| `_event_queue` | 框架核心初始化时创建 | Platform 通过它提交事件，EventBus 从它消费事件 |
| `_config` | AstrBotConfigManager 加载 | 全局配置（astrbot_config.yml 解析后） |
| `_db` | 数据库管理器初始化 | SQLite/MySQL 数据库实例 |
| `provider_manager` | ProviderManager 实例 | 管理所有 LLM/Embedding/Rerank Provider |
| `platform_manager` | PlatformManager 实例 | 管理所有已加载的平台适配器 |
| `conversation_manager` | ConversationManager 实例 | 管理对话历史 |
| `message_history_manager` | PlatformMessageHistoryManager 实例 | 管理各平台消息记录 |
| `persona_manager` | PersonaManager 实例 | 管理人格设定 |
| `astrbot_config_mgr` | AstrBotConfigManager 实例 | 配置文件的读写管理 |
| `knowledge_base_manager` | KnowledgeBaseManager 实例 | 管理知识库（RAG） |
| `cron_manager` | CronJobManager 实例 | 管理定时任务 |
| `subagent_orchestrator` | SubAgentOrchestrator 实例 | 管理子智能体编排 |

### **简单理解：**

- **event** = 每条消息的上下文（消息内容 + 发送者 + 平台信息 + 会话 + 运行时状态）
- **context** = 插件与整个框架交互的桥梁（配置 + 数据库 + LLM + 平台 + 各种管理器）

`event` 是**请求级别**的（每条消息一个），`context` 是**应用级别**的（整个插件生命周期共享一个）。

# api 中各模块基本介绍

## Q:
Platform 一般只有要用到针对某个平台的插件开发时才用到吧？Provider使用场景就更少了，对吗？

## A:
是的，你的理解完全正确。这两个模块在**普通插件开发**中确实很少直接用到。

**Platform 模块**：
- 日常插件开发：**几乎不用**。消息接收（`event`）和发送（`event.send()`）已经被框架封装好了
- 使用场景：开发**自定义平台适配器**（如接入新的 IM 平台飞书、钉钉等）
- 举例：`from astrbot.api.platform import Platform, register_platform_adapter`

**Provider 模块**：
- 日常插件开发：**几乎不用**。LLM 调用已经被 Pipeline 和 Agent 封装，你只需注册 `@filter.command()` 或 `@filter.on_llm_request()`
- 使用场景：
  1. 开发**自定义 Provider 适配器**（接入新的 AI 服务商）
  2. 需要直接调用特定 AI 能力（如 `EmbeddingProvider` 做向量化、`RerankProvider` 做重排序、`STTProvider` 做语音转文本）
  3. 在插件中精细控制 LLM 调用（绕过 Pipeline 直接调用 `text_chat()`）

**常见插件开发真正会用到的模块**：

| 模块 | 使用频率 | 用途 |
|------|---------|------|
| `api.event`（含 filter） | ⭐⭐⭐⭐⭐ | 注册命令、事件钩子 |
| `api.star`（含 Star、StarTools） | ⭐⭐⭐⭐⭐ | 插件基类、工具方法 |
| `api.message_components` | ⭐⭐⭐⭐ | 构造消息组件（图片、@人等） |
| `api.platform` | ⭐⭐ | 访问消息对象、发送消息 |
| `api.provider` | ⭐ | 高级用法，极少数场景 |

所以之前整理的文档(api 模块整理目录中的内容)更像是**参考手册**，当你需要深入某个领域时可以查阅。日常开发中，大部分时候你只需要关注 `api.event` 和 `api.star` 这两个模块就够了。

# 有不属于 api 模块但插件开发可能会用到的内容吗？

          
有，以下是不属于 `api` 模块但插件开发可能会用到的内容：

**一、直接从 `astrbot` 导入的**

| 模块 | 说明 | 用途 |
|------|------|------|
| `astrbot.logger` | AstrBot 日志记录器 | 插件中记录日志 |
| `astrbot.__version__` | 版本号 | 检查 AstrBot 版本 |

**二、从 `astrbot.core` 导入的**

| 模块 | 说明 | 用途 |
|------|------|------|
| `astrbot.core.html_renderer` | HTML 渲染工具 | 将 HTML 转换为图片 |
| `astrbot.core.sp` | 未知（需要进一步检查） | 可能是某种工具函数 |
| `astrbot.core.agent.tool.FunctionTool` | LLM 函数工具定义 | 创建 LLM 可调用的工具 |
| `astrbot.core.agent.tool.ToolSet` | 工具集合 | 管理多个工具 |
| `astrbot.core.agent.tool_executor.BaseFunctionToolExecutor` | 工具执行器基类 | 自定义工具执行逻辑 |
| `astrbot.core.config.astrbot_config.AstrBotConfig` | 配置类 | 访问全局配置 |

**三、从 `astrbot.api.util` 导入的**

| 模块 | 说明 | 用途 |
|------|------|------|
| `SessionController` | 会话控制器 | 管理会话状态 |
| `SessionWaiter` | 会话等待器 | 等待用户输入 |
| `session_waiter` | 装饰器 | 简化会话等待逻辑 |

**四、从 `astrbot.api.web` 导入的**

| 模块 | 说明 | 用途 |
|------|------|------|
| `request` | 请求代理对象 | 获取当前 Web 请求信息 |
| `json_response` | JSON 响应构造函数 | 返回 JSON 响应 |
| `error_response` | 错误响应构造函数 | 返回标准错误响应 |
| `file_response` | 文件响应构造函数 | 返回文件下载响应 |
| `stream_response` | 流式响应构造函数 | 返回流式响应 |

**五、从 `astrbot.core.star.register` 导入的**

| 模块 | 说明 | 用途 |
|------|------|------|
| `register_agent` | Agent 注册装饰器 | 注册子智能体 |

**使用示例**：

```python
import astrbot.logger as logger

from astrbot.core.html_renderer import render_html_to_image
from astrbot.core.agent.tool import FunctionTool, ToolSet
from astrbot.api.util import session_waiter
from astrbot.api.web import request, json_response

logger.info("插件启动")

@session_waiter
async def wait_for_input(self, event):
    # 等待用户输入
    pass

async def web_handler():
    data = await request.json()
    return json_response({"status": "success", "data": data})
```

这些模块虽然不属于 `api` 的子模块，但都是插件开发中可能会用到的实用工具。
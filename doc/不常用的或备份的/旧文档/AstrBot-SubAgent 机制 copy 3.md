# AstrBot-SubAgent（子智能体）机制

## 一、SubAgent 是什么

SubAgent（子智能体）是 AstrBot 中的**任务委派机制**。你可以配置多个子 Agent，每个子 Agent 有独立的人格设定（system prompt）和工具集。当主 Agent（LLM）判断某个任务适合由特定子 Agent 处理时，会通过调用 `HandoffTool`（转接工具）把任务转交给子 Agent。

核心思想：**主 Agent 是决策者，SubAgent 是执行者。**

```
用户请求
    │
    ▼
主 Agent (LLM)
    │
    ├── 分析请求，判断是否需要转接
    │
    ├── 调用 HandoffTool（如 transfer_to_weather_agent）
    │   └── HandoffTool 启动子 Agent 对话
    │
    ▼
子 Agent（如天气 Agent）
    │
    ├── 独立的 system prompt（人格设定）
    ├── 独立的工具集
    └── 独立的对话循环
    │
    ▼
子 Agent 完成，结果返回给主 Agent
    │
    ▼
主 Agent 汇总结果，回复用户
```

### HandoffTool vs 普通 FunctionTool 工作流程对比

#### 普通 FunctionTool 工作流程

```
主 Agent (LLM)
    │
    ├── 看到工具列表（所有已注册的 FunctionTool）
    │   ├── get_weather       → 查天气
    │   ├── search_info       → 搜索信息
    │   └── ...
    │
    ├── LLM 决定调用某个工具（如 get_weather）
    │
    └── 工具执行器 execute() 判断类型（astr_agent_tool_exec.py#L129）
        │
        ├── isinstance(tool, HandoffTool)? → 否（#L140）
        ├── isinstance(tool, MCPTool)? → 否（#L152）
        ├── tool.is_background_task? → 否（#L157）
        │
        └── 走 _execute_local 分支（#L182）
            │
            ├── 判断执行方式（#L640-652）
            │   ├── tool.handler 存在 → 调用 handler(event, **kwargs)（#L733-734）
            │   ├── 重写了 tool.call() → 调用 tool.call(context, **kwargs)（#L735-736）
            │   └── 有 run() 方法 → 调用 tool.run(event, **kwargs)
            │
            ├── 处理返回值（call_local_llm_tool #L780-808）
            │   ├── 返回 MessageEventResult → event.set_result(ret) + yield None
            │   ├── 返回 str/None → 直接 yield 给 Agent Loop
            │   └── 异步生成器 → 逐步 yield，每个 MessageEventResult 直接发给用户
            │
            └── 结果返回给主 Agent
```

#### HandoffTool 工作流程

```
主 Agent (LLM)
    │
    ├── 看到 HandoffTool 列表（作为可选工具）
    │   ├── transfer_to_weather_agent  →  对应天气 SubAgent
    │   ├── transfer_to_code_agent    →  对应代码 SubAgent
    │   └── ...
    │
    ├── LLM 决定调用某个 HandoffTool
    │
    └── 工具执行器 execute() 判断类型（astr_agent_tool_exec.py#L129）
        │
        ├── isinstance(tool, HandoffTool)? → 是（#L140）
        │
        └── 走 _execute_handoff 分支（#L148，跳过 handler/call 机制）
            │
            ├── 从 tool.agent 获取 SubAgent 的配置（#L301-373）
            │   ├── instructions（system prompt）
            │   ├── tools（工具列表）
            │   └── begin_dialogs（预设对话）
            │
            ├── 构建 SubAgent 的工具集（#L329，排除 HandoffTool 防止循环转接）
            │
            └── 调用 ctx.tool_loop_agent() 启动子 Agent 对话（#L359-370）
                └── SubAgent 完成后，结果返回给主 Agent
```

补充：HandoffTool 的执行是在工具执行器中处理的

从 astrbot/core/astr_agent_tool_exec.py#L140-150 可以看到，工具执行器通过 isinstance(tool, HandoffTool) 判断是否为转接工具，然后走 _execute_handoff 分支，而不是普通的 handler 调用分支。


#### 关键区别

| 维度 | 普通 FunctionTool | HandoffTool |
|------|-------------------|-------------|
| 执行分支 | `_execute_local` | `_execute_handoff` |
| 执行方式 | 调用 handler / call() / run() | 启动新的 `tool_loop_agent` 对话 |
| handler | 必须有 | 无（装饰器注册时绑定的 handler 仅用于标识） |
| call() | 可以被重写来实现功能 | 不会被调用（执行器跳过了它） |
| 结果类型 | 字符串或 MessageEventResult | CallToolResult（子 Agent 的完成文本） |
| 执行耗时 | 通常毫秒级 | 可能数秒到数分钟 |
| 能否调用其他工具 | 不能直接调用 | 可以（通过子 Agent 的工具集） |

#### FunctionTool 最终会走到 _execute_handoff 吗？

**不会。** 工具执行器的路由逻辑是互斥的 `if/elif/else` 结构（文件：astrbot/core/astr_agent_tool_exec.py#L129-184）：

```python
# strbot/core/astr_agent_tool_exec.py#L140-150
# 只有 HandoffTool 走这里
if isinstance(tool, HandoffTool):
    is_bg = tool_args.pop("background_task", False)
    if is_bg:
        async for r in cls._execute_handoff_background(...):
            yield r
        return
    async for r in cls._execute_handoff(tool, run_context, **tool_args):
        yield r
    return

# strbot/core/astr_agent_tool_exec.py#L152-155
# 只有 MCPTool 走这里
elif isinstance(tool, MCPTool):
    async for r in cls._execute_mcp(tool, run_context, **tool_args):
        yield r
    return

# strbot/core/astr_agent_tool_exec.py#L157-181
elif tool.is_background_task:
    # 背景任务处理
    ...

# strbot/core/astr_agent_tool_exec.py#L182-184
else:
    # 所有普通 FunctionTool 走这里
    async for r in cls._execute_local(tool, run_context, **tool_args):
        yield r
```

普通 FunctionTool 永远走 `_execute_local`，永远不会走到 `_execute_handoff`。HandoffTool 虽然继承自 FunctionTool，但因为 `isinstance` 判断在最前面，它会被优先识别并路由到 `_execute_handoff`，不会落入 `else` 分支。

#### 工具路由分发模式

AstrBot 的所有工具（普通工具、转接工具、MCP 工具、后台任务）都统一由 `FunctionToolExecutor.execute()` 方法（文件：astrbot/core/astr_agent_tool_exec.py#L129）进行路由分发。这是一个典型的**责任链模式**：

```
FunctionToolExecutor.execute(tool, run_context, **tool_args)  # L129
    │
    ├── isinstance(tool, HandoffTool)?  # L140
    │   ├── background_task=True? → _execute_handoff_background()  # L375
    │   └── 否则 → _execute_handoff()  # L301
    │
    ├── isinstance(tool, MCPTool)?  # L152
    │   └── _execute_mcp()  # L701
    │
    ├── tool.is_background_task?  # L157
    │   └── _execute_background()
    │
    └── else → _execute_local()  # L182
        └── 根据 tool.handler / tool.call() / tool.run() 选择执行方式
```

这是一个典型的 路由分发模式 ：

- 所有工具类型的判断都集中在 execute() 方法中
- 每个工具类型对应一个独立的 _execute_* 方法
- HandoffTool 和 MCPTool 虽然继承自 FunctionTool ，但它们的 call() 方法在执行器中 永远不会被调用
- 普通 FunctionTool 的 handler / call() / run() 只在 _execute_local 中生效

关键设计点：

1. **统一入口**：所有工具类型的执行都通过 `execute()` 方法，不存在旁路
2. **类型判断优先**：`HandoffTool` 和 `MCPTool` 作为 `FunctionTool` 的子类，通过 `isinstance` 判断在最前面被优先拦截，不会落入 `else` 分支
3. **互斥分支**：使用 `if/elif/else` 结构，每个工具类型只能走一条执行路径
4. **子类隔离**：`HandoffTool.call()` 和 `MCPTool.call()` 在执行器中永远不会被调用，它们的执行逻辑完全由独立的 `_execute_*` 方法处理
5. **可扩展性**：新增工具类型只需在 `execute()` 中添加新的 `isinstance` 判断和对应的 `_execute_*` 方法

这意味着 HandoffTool 与 FunctionTool 并非"没有关联"，而是**继承关系 + 路由隔离**的设计：HandoffTool 继承了 FunctionTool 的所有属性（name、description、parameters、handler 等），但在执行时被路由到独立的分支，跳过了 FunctionTool 的 handler/call 机制。

## 二、核心类

### 2.1 Agent（智能体定义）

**文件**：astrbot/core/agent/agent.py

```python
@dataclass
class Agent(Generic[TContext]):
    name: str
    instructions: str | None = None
    tools: list[str | FunctionTool] | None = None
    run_hooks: BaseAgentRunHooks[TContext] | None = None
    begin_dialogs: list[Any] | None = None
```

| 字段 | 说明 |
|------|------|
| `name` | Agent 名称，对应 HandoffTool 的名称 `transfer_to_{name}` |
| `instructions` | 系统提示词（人格设定） |
| `tools` | 工具列表（工具名或 FunctionTool 对象），`None` 表示继承主 Agent 的所有工具 |
| `run_hooks` | 运行时钩子 |
| `begin_dialogs` | 预设的对话历史（Persona 中的 `_begin_dialogs_processed`） |

### 2.2 HandoffTool（转接工具）

**文件**：astrbot/core/agent/handoff.py

```python
class HandoffTool(FunctionTool, Generic[TContext]):
    def __init__(self, agent, parameters=None, tool_description=None, **kwargs):
        super().__init__(
            name=f"transfer_to_{agent.name}",
            parameters=parameters or self.default_parameters(),
            description=description,
            **kwargs,
        )
        self.agent = agent
```

HandoffTool 继承 FunctionTool，是一种特殊的工具：
- **没有 handler**：不直接执行，而是启动子 Agent 对话
- **固定参数**：`input`（转接内容）、`image_urls`（图片引用）、`background_task`（是否后台任务）
- **执行逻辑**：由工具执行器的 `_execute_handoff` 分支处理

默认参数结构：

```python
{
    "type": "object",
    "properties": {
        "input": {
            "type": "string",
            "description": "The input to be handed off to another agent."
        },
        "image_urls": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional image sources for multimodal tasks."
        },
        "background_task": {
            "type": "boolean",
            "description": "Defaults to false. Set to true for time-consuming tasks."
        }
    }
}
```

### 2.3 SubAgentOrchestrator（子智能体编排器）

**文件**：astrbot/core/subagent_orchestrator.py

负责从配置加载子 Agent 定义并创建 HandoffTool 列表。

```python
class SubAgentOrchestrator:
    def __init__(self, tool_mgr, persona_mgr):
        self.handoffs: list[HandoffTool] = []

    async def reload_from_config(self, cfg):
        agents = cfg.get("agents", [])
        for item in agents:
            # 从配置创建 Agent 和 HandoffTool
            agent = Agent(name=name, instructions=..., tools=...)
            handoff = HandoffTool(agent=agent, tool_description=...)
            handoffs.append(handoff)
        self.handoffs = handoffs
```

## 三、两种注册方式

### 3.1 配置文件注册（推荐）

在 AstrBot 配置文件中定义子 Agent，通过 WebUI 或配置文件管理。

配置示例（`subagent_orchestrator` 相关配置）：

```yaml
subagent_orchestrator:
  router_system_prompt: "你是路由助手，根据用户意图选择合适的子智能体。"
  agents:
    - name: weather
      enabled: true
      public_description: "处理天气查询相关的任务"
      system_prompt: "你是一个天气助手，擅长查询和预报天气。"
      persona_id: weather_persona  # 可选，引用 Persona 中的人格设定
      tools:  # 可选，指定子 Agent 可用的工具
        - get_weather
      provider_id: default  # 可选，使用指定的 Provider
    - name: code
      enabled: true
      public_description: "处理代码生成、调试相关的任务"
      system_prompt: "你是一个编程助手，擅长代码生成和调试。"
```

配置字段说明：

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 是 | 子 Agent 名称（英文标识） |
| `enabled` | 否 | 是否启用，默认 `true` |
| `public_description` | 是 | 给主 LLM 看的公开描述，用于决定何时转接 |
| `system_prompt` | 否 | 系统提示词 |
| `persona_id` | 否 | 引用 Persona 中的人格设定（如设置则优先使用 Persona 的 prompt） |
| `tools` | 否 | 指定子 Agent 可用的工具列表，`None` 表示继承所有工具 |
| `provider_id` | 否 | 使用指定的 Provider，默认使用当前会话的 Provider |

### 3.2 装饰器注册（代码方式）

使用 `@agent` 装饰器在插件中注册子 Agent。

```python
from astrbot.api import agent

class MyPlugin(Star):
    def __init__(self, context):
        super().__init__(context)

    @agent(
        name="weather",
        instruction="你是一个天气助手，擅长查询和预报天气。",
        tools=["get_weather"],
    )
    async def weather_agent(self):
        """天气子智能体 - 这个函数作为 handler 被绑定到 HandoffTool"""
        pass  # 函数体不会被实际执行
```

装饰器在 astrbot/core/star/register/star_handler.py#L695-725 中实现：

```python
def register_agent(name, instruction, tools=None, run_hooks=None):
    def decorator(awaitable):
        agent = Agent(name=name, instructions=instruction, tools=tools)
        handoff_tool = HandoffTool(agent=agent)
        handoff_tool.handler = awaitable  # handler 绑定到装饰器函数
        llm_tools.func_list.append(handoff_tool)  # 直接加到全局工具列表
        return RegisteringAgent(agent)
    return decorator
```

注意：装饰器注册的 HandoffTool 是**直接加到全局工具列表**的，而配置文件注册的 HandoffTool 是在 `astr_main_agent.py#L625-626` 中动态注入到请求工具集的。

## 四、HandoffTool 的执行机制

`HandoffTool` 的 `call` 方法没有被重写 ，它走的是完全不同的执行路径：
`HandoffTool` 不是通过 `call()` 方法执行的。工具执行器在 `astrbot/core/astr_agent_tool_exec.py#L140` 通过 `isinstance(tool, HandoffTool)` 判断后，直接路由到 `_execute_handoff` 分支，跳过了 `call() / handler` 机制。

### 4.1 执行入口

在工具执行器 astrbot/core/astr_agent_tool_exec.py#L140-150 中，通过 `isinstance` 判断路由：

```python
if isinstance(tool, HandoffTool):
    is_bg = tool_args.pop("background_task", False)
    if is_bg:
        async for r in cls._execute_handoff_background(tool, run_context, **tool_args):
            yield r
    else:
        async for r in cls._execute_handoff(tool, run_context, **tool_args):
            yield r
    return
```

### 4.2 执行流程（_execute_handoff）

```
1. 准备参数
   ├── 提取 input（转接内容）
   ├── 收集 image_urls（从参数 + 当前消息中提取）
   └── 处理 background_task

2. 构建子 Agent 工具集（_build_handoff_toolset）
   ├── 如果 agent.tools 为 None → 继承主 Agent 的所有工具（排除 HandoffTool 防止循环）
   ├── 如果 agent.tools 为空列表 → 子 Agent 没有任何工具
   └── 如果 agent.tools 指定了工具名 → 只加载指定的工具

3. 准备对话上下文
   ├── 获取子 Agent 的 begin_dialogs（预设对话）
   └── 转换为 Message 对象列表

4. 调用 tool_loop_agent 启动子 Agent 对话
   ├── system_prompt = agent.instructions
   ├── prompt = input_
   ├── tools = 构建的工具集
   ├── contexts = 预设对话
   └── 最多执行 max_steps 步

5. 返回结果
   └── yield CallToolResult（包含子 Agent 的完成文本）
```

### 4.3 与普通 FunctionTool 执行的区别

| 维度 | 普通 FunctionTool | HandoffTool |
|------|-------------------|-------------|
| 执行分支 | `_execute_local` | `_execute_handoff` |
| 执行方式 | 直接调用 handler | 启动新的 `tool_loop_agent` 对话 |
| handler | 有（直接执行的函数） | 无（装饰器注册时绑定的 handler 仅用于标识） |
| 结果返回 | 直接返回字符串 | 子 Agent 完成后返回 CallToolResult |
| 工具隔离 | 使用主 Agent 的工具 | 使用子 Agent 指定的工具（排除 HandoffTool） |
| 循环防护 | 无 | 排除其他 HandoffTool，防止无限循环转接 |

### 4.4 后台任务模式

当 `background_task=True` 时，走 `_execute_handoff_background` 分支：

```
1. 立即返回 task_id 给主 Agent
2. 在后台异步执行子 Agent 对话
3. 子 Agent 完成后，创建 CronMessageEvent 通知主 Agent
4. 主 Agent 收到通知后，把结果告诉用户
```

## 五、动态管理 SubAgent

### 5.1 访问已存在的 SubAgent 属性

`SubAgentOrchestrator.handoffs` 中存储的是 `HandoffTool` 对象列表。每个 `HandoffTool` 持有一个 `agent` 属性（`Agent` 实例），可以通过它访问 SubAgent 的完整配置：

```python
class MyPlugin(Star):
    def __init__(self, context):
        super().__init__(context)

    @filter.command("list_agents")
    async def list_agents(self, event):
        orchestrator = self.context.subagent_orchestrator
        handoffs = orchestrator.handoffs
        if not handoffs:
            yield event.plain_result("已注册的 SubAgent: 无")
            return

        result = []
        for h in handoffs:
            agent = h.agent  # Agent 实例
            result.append({
                "handoff_name": h.name,           # transfer_to_{agent_name}
                "agent_name": agent.name,         # Agent 名称（如 weather）
                "instructions": agent.instructions,  # 系统提示词
                "tools": agent.tools,             # 可用工具列表
                "has_begin_dialogs": bool(agent.begin_dialogs),  # 是否有预设对话
                "provider_id": h.provider_id,    # 专用 Provider ID
            })
        yield event.plain_result(f"已注册的 SubAgent: {result}")
```

Agent 类的属性说明（文件：astrbot/core/agent/agent.py#L9-16）：

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | Agent 名称，对应 HandoffTool 的 `transfer_to_{name}` |
| `instructions` | `str \| None` | 系统提示词（人格设定），来自配置的 `system_prompt` 或 Persona |
| `tools` | `list[str \| FunctionTool] \| None` | 可用工具名列表，`None` 表示继承主 Agent 所有工具 |
| `run_hooks` | `BaseAgentRunHooks \| None` | 运行时钩子（代码方式注册） |
| `begin_dialogs` | `list \| None` | 预设对话历史（来自 Persona 的 `_begin_dialogs_processed`） |

HandoffTool 额外属性（文件：astrbot/core/agent/handoff.py#L32-36）：

| 属性 | 类型 | 说明 |
|------|------|------|
| `agent` | `Agent` | 关联的 Agent 实例 |
| `provider_id` | `str \| None` | 专用 Provider ID，`None` 表示使用当前会话的 Provider |
| `name` | `str` | HandoffTool 名称，固定为 `transfer_to_{agent.name}` |
| `description` | `str` | 给主 LLM 看的描述，用于决定是否转接 |

### 5.2 程序化调用已存在的 SubAgent

SubAgent 的正常调用流程是：主 LLM 看到 HandoffTool → 决定调用 → 执行器路由到 `_execute_handoff`。但你也可以在插件中**直接调用已存在的 SubAgent**，绕过 LLM 路由。

核心思路：`context.tool_loop_agent()` 就是 SubAgent 的执行引擎。你只需拿到 Agent 的配置（instructions、tools、begin_dialogs），传给它就能启动子 Agent 对话。

```python
@filter.command("ask_weather")
async def ask_weather(self, event):
    orchestrator = self.context.subagent_orchestrator   # 获取 SubAgentOrchestrator 实例
    handoff = None  # 找到 weather SubAgent 的 HandoffTool
    for h in orchestrator.handoffs: 
        if h.agent.name == "weather":
            handoff = h
            break

    if not handoff: # 如果 weather SubAgent 未注册
        yield event.plain_result("weather SubAgent 未注册")
        return

    agent = handoff.agent  # 获取 weather SubAgent 的 Agent 实例

    # 通过 context.tool_loop_agent() 直接调用 weather SubAgent
    # 只需拿到 weather SubAgent 的Agent 实例(实例中包括人格设定、工具集、预设对话等信息），就可以直接调用它了。

    # 构建工具集
    # 不能直接用 agent.tools，因为：
    # 1. agent.tools 类型是 list[str | FunctionTool] | None（工具名或工具对象的列表）
    # 2. tool_loop_agent() 需要的是 ToolSet 对象
    # 3. agent.tools 为 None 时表示"继承所有工具"，需要展开为实际工具列表
    # 4. 需要排除 HandoffTool，防止子 Agent 循环转接
    # _build_handoff_toolset() 处理了上述所有逻辑或者说封装了这四件事，所以直接调用它是最稳妥的方式（astr_agent_tool_exec.py#L244-298）
    from astrbot.core.astr_agent_tool_exec import FunctionToolExecutor

    # 构建工具集（与 _build_handoff_toolset 逻辑相同）
    toolset = FunctionToolExecutor._build_handoff_toolset(
        run_context, agent.tools
    )

    # 准备预设对话（可选）
    contexts = None
    if agent.begin_dialogs:
        from astrbot.core.platform.sources.astrbot.message.event import Message
        contexts = []
        for dialog in agent.begin_dialogs:
            contexts.append(
                dialog if isinstance(dialog, Message) else Message.model_validate(dialog)
            )

    # 获取 Provider ID
    prov_id = handoff.provider_id or await self.context.get_current_chat_provider_id(
        event.unified_msg_origin
    )

    # 启动子 Agent 对话（这就是 _execute_handoff 内部做的事，astr_agent_tool_exec.py#L359-370）
    llm_resp = await self.context.tool_loop_agent(
        event=event,
        chat_provider_id=prov_id,
        prompt="北京今天天气怎么样？",          # 转接的内容
        system_prompt=agent.instructions,       # SubAgent 的人格设定
        tools=toolset,                          # SubAgent 的工具集
        contexts=contexts,                      # 预设对话
        max_steps=30,
        tool_call_timeout=120,
    )

    yield event.plain_result(f"天气助手回复: {llm_resp.completion_text}")
```

核心思路：`tool_loop_agent()` 就是 SubAgent 的执行引擎。你把 Agent 的配置（instructions、tools、begin_dialogs）传给它，它就会启动一个独立的 Agent 对话循环。

### 5.3 动态控制 SubAgent 可用性

在 `on_llm_request` 中根据条件动态调整哪些 SubAgent 对主 LLM 可见：

```python
@filter.on_llm_request()
async def adjust_subagents(self, event, req):
    orchestrator = self.context.subagent_orchestrator
    for handoff in orchestrator.handoffs:
        # 禁用特定 SubAgent
        if handoff.agent.name == "code" and not user_is_developer(event):
            req.func_tool.remove_tool(handoff.name)
        # 或根据时间段禁用
        if not is_working_hours() and handoff.agent.name == "code":
            req.func_tool.remove_tool(handoff.name)
```

### 5.4 动态添加新的 HandoffTool

在 `on_llm_request` 中临时创建并注入一个新的 SubAgent：

```python
from astrbot.core.agent.agent import Agent
from astrbot.core.agent.handoff import HandoffTool

@filter.on_llm_request()
async def add_custom_agent(self, event, req):
    agent = Agent(
        name="custom",
        instructions="你是一个自定义助手。",
        tools=["search"],
    )
    handoff = HandoffTool(agent=agent, tool_description="处理自定义任务")
    req.func_tool.add_tool(handoff)
```

注意：这里创建的是**临时 SubAgent**，仅在当前请求中生效。如果需要持久化的 SubAgent，应通过 WebUI 或配置文件注册。

## 六、常见问题

### SubAgent 和普通工具的区别？

普通工具执行一个具体功能（查天气、搜信息），SubAgent 是一个独立的 Agent，拥有自己的人格和工具集，可以进行多轮对话和复杂推理。

### SubAgent 能调用其他 SubAgent 吗？

可以，但框架会排除其他 HandoffTool（防止无限循环转接）。如果子 Agent 的工具列表中没有排除 HandoffTool，`_build_handoff_toolset` 会自动处理。

### 如何选择配置文件注册还是装饰器注册？

- **配置文件注册**：适合需要在运行时动态调整的场景（WebUI 修改后立即生效）
- **装饰器注册**：适合插件自带的子 Agent，与插件代码绑定

### SubAgent 的对话历史会被保存吗？

是的，SubAgent 的对话历史会通过 `persist_agent_history` 保存，下次对话时可以恢复上下文。

### 如何获取 SubAgent 的执行结果？

SubAgent 执行完成后，结果会作为 `CallToolResult` 返回给主 Agent，主 Agent 可以决定是否直接回复用户或进一步处理。

### Q:
就像我之前说的，transfer_to_* 在 web UI 中无法进行配置，所以我只能在 on_llm_request() 的事件钩子中手动注入给 router，但router之下调用的其它SubAgent（或者说嵌套调用），按你说的不适用于 on_llm_request() 钩子，好像就无法进行注入了。

A:
你的担心有道理，但实际场景分两种情况：

#### 场景一：Router 调用普通 SubAgent（单层）

这种情况下**完全没问题**，不需要额外注入。流程是：

1. `on_llm_request` 中给 Router 注入所有 HandoffTool 对象
2. Router 决定调用 `transfer_to_weather_agent`
3. 执行器路由到 `_execute_handoff`，调用 `_build_handoff_toolset(run_context, weather_agent.tools)`
4. 如果 `weather_agent.tools = None`（默认），它会继承所有**非 HandoffTool** 的工具
5. weather SubAgent 正常工作，完成后结果返回 Router

weather SubAgent **不需要** `on_llm_request` 钩子，因为它的工具集是在 `_execute_handoff` 内部构建的，跟 `on_llm_request` 无关。

#### 场景二：SubAgent 之间多层互调（Router → A → B）

这种情况确实有问题。假设 weather SubAgent 想调用 code SubAgent：

- `weather_agent.tools = None` → 继承所有工具，**但排除 HandoffTool** → weather 调不了 code
- `weather_agent.tools = ["transfer_to_code_agent"]` → 走显式指定分支，用 `llm_tools.get_func()` 按名查找 → **配置文件注册的 HandoffTool 不在 `llm_tools` 里，找不到**

#### 解决方案

在 `on_llm_request` 中做一次性的全局设置，把 HandoffTool 对象直接注入到每个 SubAgent 的 `agent.tools` 里（用对象而不是名字）：

```python
@filter.on_llm_request()
async def setup_router(self, event, req):
    orchestrator = self.context.subagent_orchestrator
    handoffs = orchestrator.handoffs

    for h in handoffs:
        # 1. 注入到主请求工具集（Router 能看到所有 HandoffTool）
        req.func_tool.add_tool(h)

        # 2. 给每个 SubAgent 注入其他 HandoffTool 对象
        #    _build_handoff_toolset 支持直接传 FunctionTool 对象（不只是字符串）
        if h.agent.tools is None:
            h.agent.tools = [tool for tool in req.func_tool.tools]

    # 3. 如果 Router 的 tools 还是 None，也需要处理
    #    （上面的循环已经覆盖了）
```

关键点：`_build_handoff_toolset` 的显式指定分支（astrbot/core/astr_agent_tool_exec.py#L296）支持传入 `FunctionTool` 对象直接加入工具集，不需要通过名字查找：

```python
elif isinstance(tool_name_or_obj, FunctionTool):
    toolset.add_tool(tool_name_or_obj)  # 直接加，不查找
```

只要你传给 `agent.tools` 的是 **HandoffTool 对象本身**（而不是字符串名），就能绕过 `llm_tools.get_func()` 的查找限制。


#### 总结

| 层级 | 需要 on_llm_request？ | 需要特殊处理？ |
|------|---------------------|---------------|
| 主 Agent → Router | 是 | 注入 HandoffTool 对象 |
| Router → SubAgent | 不需要 | 不需要（工具集在 `_execute_handoff` 内构建） |
| SubAgent → SubAgent | 不需要 | 需要在 `on_llm_request` 中预先设置 `agent.tools` 为对象列表 |

如果你的场景只是 **Router → 其他 SubAgent**（单层），在 `on_llm_request` 里注入 HandoffTool 对象就足够了，不需要担心后续层级的注入问题。

#### 原方案的局限

上述"注入 HandoffTool 到 `agent.tools`"方案存在两个问题：

1. 持久化污染

`agent.tools` 是 `Agent` 数据类的普通字段，`Agent` 实例由 `HandoffTool.agent` 持有，`HandoffTool` 由 `SubAgentOrchestrator.handoffs` 列表持有，而 `SubAgentOrchestrator` 是单例（`context.subagent_orchestrator`）。

执行 `h.agent.tools = [...]` 是直接修改单例持有的对象属性，修改是持久的，不会随请求结束而释放。重置时机只有两个：
- `reload_from_config()` 被调用（WebUI 改 SubAgent 配置后触发，会创建全新 Agent 对象）
- AstrBot 重启

2. 潜在的循环转接风险

原方案 `h.agent.tools = [tool for tool in req.func_tool.tools]` 把当前请求的所有工具都赋值给了 `agent.tools`，包括其他 HandoffTool。这与 `_build_handoff_toolset` 默认（`tools=None`）会排除 HandoffTool 的设计相悖，可能造成 SubAgent 之间循环转接。

## 七、替代方案：自定义调用入口（推荐）

更优雅的思路：不在任何地方注入 HandoffTool，转而提供两个普通 FunctionTool 作为统一调用入口：

1. `list_sub_agents`：返回所有 SubAgent 的名称和描述
2. `call_sub_agent`：根据名称调用指定 SubAgent

核心思路：`context.tool_loop_agent()` 就是 SubAgent 的执行引擎。在 `call_sub_agent` 的 handler 中，从 `context.subagent_orchestrator.handoffs` 找到目标 Agent 配置（instructions、tools、begin_dialogs），传给 `tool_loop_agent()` 即可启动子 Agent 对话。

关键点：
- 两个工具用 `@filter.llm_tool` 注册后，存在于 `llm_tools.func_list`（全局工具列表）中
- SubAgent 在 `agent.tools = None`（默认）时会自动继承这两个工具
- 因此所有 SubAgent 天然都能调用这两个工具，支持任意层级嵌套调用
- 不修改 `agent.tools`，无持久化污染
- 不注入 HandoffTool，无循环转接风险

实现骨架：

```python
from astrbot.api import llm_tool
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

from astrbot.core.astr_agent_context import AstrAgentContext, AgentContextWrapper
from astrbot.core.astr_agent_tool_exec import FunctionToolExecutor
from astrbot.core.agent.message import Message


class SubAgentRouter(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.llm_tool(name="list_sub_agents")
    async def list_sub_agents(self, event: AstrMessageEvent) -> str:
        """列出所有可用的子智能体及其描述

        Args:
        """
        orchestrator = self.context.subagent_orchestrator
        handoffs = orchestrator.handoffs
        if not handoffs:
            return "当前没有可用的子智能体"

        lines = []
        for h in handoffs:
            lines.append(f"- {h.agent.name}: {h.description}")
        return "可用子智能体列表:\n" + "\n".join(lines)

    @filter.llm_tool(name="call_sub_agent")
    async def call_sub_agent(
        self, event: AstrMessageEvent, agent_name: str, input: str
    ) -> str:
        """根据名称调用指定的子智能体处理任务

        Args:
            agent_name: 子智能体名称（可通过 list_sub_agents 查看）
            input: 要交给子智能体处理的任务描述
        """
        orchestrator = self.context.subagent_orchestrator
        handoff = None
        for h in orchestrator.handoffs:
            if h.agent.name == agent_name:
                handoff = h
                break

        if not handoff:
            return f"未找到名为 {agent_name} 的子智能体"

        agent = handoff.agent

        # 构造 run_context，复用框架的 _build_handoff_toolset 逻辑
        # 它会根据 agent.tools 配置构建工具集（None=继承所有非 HandoffTool 工具）
        agent_context = AstrAgentContext(context=self.context, event=event)
        run_context = AgentContextWrapper(
            context=agent_context, tool_call_timeout=120
        )
        toolset = FunctionToolExecutor._build_handoff_toolset(
            run_context, agent.tools
        )

        # 准备预设对话
        contexts = None
        if agent.begin_dialogs:
            contexts = []
            for dialog in agent.begin_dialogs:
                try:
                    contexts.append(
                        dialog
                        if isinstance(dialog, Message)
                        else Message.model_validate(dialog)
                    )
                except Exception:
                    continue

        # Provider 选择：优先 SubAgent 配置的 provider_id
        prov_id = getattr(handoff, "provider_id", None)
        if not prov_id:
            prov_id = await self.context.get_current_chat_provider_id(
                event.unified_msg_origin
            )

        llm_resp = await self.context.tool_loop_agent(
            event=event,
            chat_provider_id=prov_id,
            prompt=input,
            system_prompt=agent.instructions,
            tools=toolset,
            contexts=contexts,
            max_steps=30,
            tool_call_timeout=120,
        )
        return llm_resp.completion_text
```

### 为什么能复用 `_build_handoff_toolset`？

从 astrbot/core/star/context.py#L286-315 可以看到，`tool_loop_agent` 内部就是用 `AstrAgentContext(context=self, event=event)` + `AgentContextWrapper` 构造 `run_context` 的。`call_sub_agent` 的 handler 中也这么构造一份，就能调用 `FunctionToolExecutor._build_handoff_toolset(run_context, agent.tools)` 复用框架原有的工具集构建逻辑（处理 None=继承所有、排除 HandoffTool、按名查找/按对象直接添加等所有细节）。

### 方案对比

| 维度 | 注入 HandoffTool 方案 | 自定义调用入口方案 |
|------|---------------------|------------------|
| `agent.tools` 污染 | 有（持久化） | 无 |
| 循环转接风险 | 有（需排除 HandoffTool） | 无（统一入口） |
| SubAgent 互调 | 需额外注入 | 天然支持（工具全局注册） |
| LLM 调用方式 | 直接调用 `transfer_to_xxx` | 先 `list_sub_agents` 再 `call_sub_agent`（多一步） |
| 工具数量 | N 个 HandoffTool | 2 个固定工具 |

唯一的小代价：LLM 需要先调 `list_sub_agents` 看有哪些 SubAgent，再调 `call_sub_agent`。但这也让 LLM 的决策更明确，而且可以在 `list_sub_agents` 的返回中给出调用示例引导 LLM。

## 八、与相关模块的关系

| 模块 | 关系 |
|------|------|
| Tool 模块 | HandoffTool 继承自 FunctionTool，是一种特殊的工具 |
| Agent 模块 | Agent 类定义了子智能体的配置（instructions、tools、hooks） |
| Context 模块 | `Context.subagent_orchestrator` 提供访问子智能体编排器的入口 |
| Persona 模块 | SubAgent 可以引用 Persona 中定义的人格设定 |
| Provider 模块 | SubAgent 可以使用独立的 Provider（通过 `provider_id` 配置） |

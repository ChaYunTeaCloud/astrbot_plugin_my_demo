# AstrBot-SubAgent（子智能体）机制

## 一、核心概念与机制

SubAgent（子智能体）是 AstrBot 中的**任务委派机制**。你可以配置多个子 Agent，每个子 Agent 有独立的人格设定（system prompt）和工具集。当主 Agent（LLM）判断某个任务适合由特定子 Agent 处理时，会通过调用 `HandoffTool`（转接工具）把任务转交给子 Agent。

**核心思想：主 Agent 是决策者，SubAgent 是执行者。**

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

这是理解 SubAgent 机制的核心。普通 FunctionTool 和 HandoffTool 在执行路径、处理逻辑上有本质区别。

#### 普通 FunctionTool 工作流程

普通工具执行的是一个具体的功能（如查天气），流程相对简单。

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

HandoffTool 触发的是一个新的、独立的 Agent 对话循环，功能更强大。

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
| handler | 必须有（直接执行的函数） | 无（装饰器注册时绑定的 handler 仅用于标识） |
| call() | 可以被重写来实现功能 | 不会被调用（执行器跳过了它） |
| 结果类型 | 字符串或 MessageEventResult | CallToolResult（子 Agent 的完成文本） |
| 执行耗时 | 通常毫秒级 | 可能数秒到数分钟 |
| 能否调用其他工具 | 不能直接调用 | 可以（通过子 Agent 的工具集） |

#### 工具路由分发模式（深入剖析）

AstrBot 的所有工具（普通工具、转接工具、MCP 工具、后台任务）都统一由 `FunctionToolExecutor.execute()` 方法进行路由分发。这是一个典型的**责任链/路由分发模式**。

**1. FunctionTool 最终会走到 `_execute_handoff` 吗？**

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

**2. 完整的路由流程图**

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

**3. 关键设计点**

- **统一入口**：所有工具类型的执行都通过 `execute()` 方法，不存在旁路。
- **类型判断优先**：`HandoffTool` 和 `MCPTool` 作为 `FunctionTool` 的子类，通过 `isinstance` 判断在最前面被优先拦截，不会落入 `else` 分支。
- **互斥分支**：使用 `if/elif/else` 结构，每个工具类型只能走一条执行路径。
- **子类隔离**：`HandoffTool.call()` 和 `MCPTool.call()` 在执行器中永远不会被调用，它们的执行逻辑完全由独立的 `_execute_*` 方法处理。

这意味着 HandoffTool 与 FunctionTool 并非"没有关联"，而是**继承关系 + 路由隔离**的设计：HandoffTool 继承了 FunctionTool 的所有属性（name、description、parameters、handler 等），但在执行时被路由到独立的分支，跳过了 FunctionTool 的 handler/call 机制。

---

## 二、核心类与注册

### 2.1 核心类定义

#### Agent（智能体定义）

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

#### HandoffTool（转接工具）

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

#### SubAgentOrchestrator（子智能体编排器）

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

### 2.2 注册方式

SubAgent 支持两种注册方式：

**1. 配置文件注册（推荐用于生产环境）**

在 AstrBot 配置文件中定义，通过 WebUI 管理。

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

**2. 装饰器注册（用于插件内置 Agent）**

使用 `@agent` 装饰器在插件中注册，直接加到全局工具列表。

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

**注意**：装饰器注册的 HandoffTool 是**直接加到全局工具列表**的，而配置文件注册的 HandoffTool 是在 `astr_main_agent.py#L625-626` 中动态注入到请求工具集的。

---

## 三、执行机制与动态管理

### 3.1 HandoffTool 执行机制

`HandoffTool` 不是通过 `call()` 方法执行的。工具执行器通过 `isinstance` 判断后，直接路由到 `_execute_handoff` 分支，跳过了 `call() / handler` 机制。

#### 执行入口

```python
# astrbot/core/astr_agent_tool_exec.py#L140-150
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

#### 执行流程（_execute_handoff）

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

#### 后台任务模式

当 `background_task=True` 时，走 `_execute_handoff_background` 分支：

```
1. 立即返回 task_id 给主 Agent
2. 在后台异步执行子 Agent 对话
3. 子 Agent 完成后，创建 CronMessageEvent 通知主 Agent
4. 主 Agent 收到通知后，把结果告诉用户
```

### 3.2 动态管理 SubAgent

#### 访问已存在的 SubAgent 属性

`SubAgentOrchestrator.handoffs` 中存储的是 `HandoffTool` 对象列表。每个 `HandoffTool` 持有一个 `agent` 属性（`Agent` 实例），可以通过它访问 SubAgent 的完整配置：

```python
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

**Agent 类的属性说明**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | Agent 名称，对应 HandoffTool 的 `transfer_to_{name}` |
| `instructions` | `str \| None` | 系统提示词（人格设定），来自配置的 `system_prompt` 或 Persona |
| `tools` | `list[str \| FunctionTool] \| None` | 可用工具名列表，`None` 表示继承主 Agent 所有工具 |
| `run_hooks` | `BaseAgentRunHooks \| None` | 运行时钩子（代码方式注册） |
| `begin_dialogs` | `list \| None` | 预设对话历史（来自 Persona 的 `_begin_dialogs_processed`） |

**HandoffTool 额外属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `agent` | `Agent` | 关联的 Agent 实例 |
| `provider_id` | `str \| None` | 专用 Provider ID，`None` 表示使用当前会话的 Provider |
| `name` | `str` | HandoffTool 名称，固定为 `transfer_to_{agent.name}` |
| `description` | `str` | 给主 LLM 看的描述，用于决定是否转接 |

#### 程序化调用已存在的 SubAgent

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

    # 构造 run_context，这是调用 _build_handoff_toolset 所必需的
    from astrbot.core.astr_agent_context import AstrAgentContext, AgentContextWrapper
    agent_context = AstrAgentContext(context=self.context, event=event)
    run_context = AgentContextWrapper(context=agent_context, tool_call_timeout=120)

    # 构建工具集
    # 不能直接用 agent.tools，因为：
    # 1. agent.tools 类型是 list[str | FunctionTool] | None（工具名或工具对象的列表）
    # 2. tool_loop_agent() 需要的是 ToolSet 对象
    # 3. agent.tools 为 None 时表示"继承所有工具"，需要展开为实际工具列表
    # 4. 需要排除 HandoffTool，防止子 Agent 循环转接
    # _build_handoff_toolset() 处理了上述所有逻辑，所以直接调用它是最稳妥的方式（astr_agent_tool_exec.py#L244-298）
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

#### 动态控制 SubAgent 可用性

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

---

## 四、核心机制挑战与应对

在 SubAgent 的嵌套调用（Router → A → B）场景中，`HandoffTool` 的可见性是一个核心挑战。本章将详细分析问题所在，并提供两种解决方案。

### 4.1 问题分析

**场景描述**：
- 主 Agent (Router) 需要调用 SubAgent A。
- SubAgent A 内部需要调用 SubAgent B。

**问题所在**：
- WebUI 中配置的 `HandoffTool` 不会自动添加到 `llm_tools` (全局工具列表)。
- 因此，SubAgent A 无法通过常规的 `agent.tools` 配置（如 `["transfer_to_B"]`）找到并调用 SubAgent B。

#### 场景一：Router 调用普通 SubAgent（单层）

这种情况下**完全没问题**，不需要额外注入。流程是：

1. `on_llm_request` 中给 Router 注入所有 HandoffTool 对象
2. Router 决定调用 `transfer_to_weather_agent`
3. 执行器路由到 `_execute_handoff`，调用 `_build_handoff_toolset(run_context, weather_agent.tools)`
4. 如果 `weather_agent.tools = None`（默认），它会继承所有**非 HandoffTool** 的工具
5. weather SubAgent 正常工作，完成后结果返回 Router

weather SubAgent **不需要** `on_llm_request` 钩子，因为它的工具集是在 `_execute_handoff` 内部构建的，跟 `on_llm_request` 无关。

#### 关键结论：SubAgent 不触发 `on_llm_request` 钩子

通过源码追踪确认，SubAgent 的 LLM 调用路径与主 Agent 完全不同，**不经过 Pipeline**，因此不会触发任何 Pipeline 钩子（包括 `on_llm_request`、`on_llm_response` 等）。

**主 Agent 的调用路径（经过 Pipeline）**：

```
用户消息
  → Pipeline (AgentRequest Stage)
    → third_party.py#L335: call_event_hook(event, EventType.OnLLMRequestEvent, req)
      （或 internal.py#L269: call_event_hook(event, EventType.OnLLMRequestEvent, req)）
    → 触发 @filter.on_llm_request() 钩子
    → 调用 LLM
```

源码位置：
- `astrbot/core/pipeline/process_stage/method/agent_sub_stages/third_party.py#L335`
- `astrbot/core/pipeline/process_stage/method/agent_sub_stages/internal.py#L269`

**SubAgent 的调用路径（不经过 Pipeline）**：

```
主 Agent 调用 HandoffTool
  → _execute_handoff (astrbot/core/astr_agent_tool_exec.py#L301)
    → _build_handoff_toolset() 构建工具集
    → ctx.tool_loop_agent() (astrbot/core/star/context.py#L214)
      → 直接构造 ProviderRequest (context.py#L278-285)
      → 直接调用 ToolLoopAgentRunner (context.py#L291-320)
      → 直接调用 provider.text_chat() (tool_loop_agent_runner.py#L482)
      → 不触发任何 Pipeline 钩子
```

源码位置：
- `astrbot/core/astr_agent_tool_exec.py#L301-370` — `_execute_handoff` 方法
- `astrbot/core/star/context.py#L214-322` — `tool_loop_agent` 方法
- `astrbot/core/agent/runners/tool_loop_agent_runner.py#L462-482` — `_iter_llm_responses` 方法

**这意味着**：
- 在 `on_llm_request` 中做的工具注入、请求修改等操作，**只对主 Agent 生效**
- SubAgent 的工具集完全由 `_build_handoff_toolset` 构建，与 `on_llm_request` 无关
- 想给 SubAgent 注入工具，只能通过修改 `agent.tools` 属性或使用全局注册的 `@llm_tool`

#### 场景二：SubAgent 之间多层互调（Router → A → B）

这种情况确实有问题。假设 weather SubAgent 想调用 code SubAgent：

- `weather_agent.tools = None` → 继承所有工具，**但排除 HandoffTool** → weather 调不了 code
- `weather_agent.tools = ["transfer_to_code_agent"]` → 走显式指定分支，用 `llm_tools.get_func()` 按名查找 → **配置文件注册的 HandoffTool 不在 `llm_tools` 里，找不到**

### 4.2 传统方案：HandoffTool 注入

为了解决上述问题，一个直接的思路是在 `on_llm_request` 钩子中，手动将所有 `HandoffTool` 对象注入到每个 SubAgent 的 `agent.tools` 属性中。

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
```

**关键点**：`_build_handoff_toolset` 的显式指定分支（astrbot/core/astr_agent_tool_exec.py#L296）支持传入 `FunctionTool` 对象直接加入工具集，不需要通过名字查找：

```python
elif isinstance(tool_name_or_obj, FunctionTool):
    toolset.add_tool(tool_name_or_obj)  # 直接加，不查找
```

只要你传给 `agent.tools` 的是 **HandoffTool 对象本身**（而不是字符串名），就能绕过 `llm_tools.get_func()` 的查找限制。

#### 传统方案的局限

这种做法存在两个明显的缺点：

1.  **持久化污染**

    `agent.tools` 是 `Agent` 数据类的普通字段，`Agent` 实例由 `HandoffTool.agent` 持有，`HandoffTool` 由 `SubAgentOrchestrator.handoffs` 列表持有，而 `SubAgentOrchestrator` 是单例（`context.subagent_orchestrator`）。

    执行 `h.agent.tools = [...]` 是直接修改单例持有的对象属性，修改是持久的，不会随请求结束而释放。重置时机只有两个：
    - `reload_from_config()` 被调用（WebUI 改 SubAgent 配置后触发，会创建全新 Agent 对象）
    - AstrBot 重启

2.  **循环转接风险**

    原方案 `h.agent.tools = [tool for tool in req.func_tool.tools]` 把当前请求的所有工具都赋值给了 `agent.tools`，包括其他 HandoffTool。这与 `_build_handoff_toolset` 默认（`tools=None`）会排除 HandoffTool 的设计相悖，可能造成 SubAgent 之间循环转接。

### 4.3 推荐方案：自定义调用入口

为了更优雅地解决问题，可以提供**两个普通的 FunctionTool** 作为统一的调用入口，而不是注入 `HandoffTool`。

**核心思路**：
- 不再让 Agent 看到 `transfer_to_xxx` 列表。
- 而是提供 `list_sub_agents` (查询可用 Agent) 和 `call_sub_agent` (执行调用) 两个工具。
- 所有 SubAgent 都继承这两个工具，从而实现任意层级的嵌套调用。

**方案优势**：
- **无持久化污染**：不修改 `agent.tools`。
- **无循环风险**：统一入口，逻辑可控。
- **天然支持嵌套**：SubAgent 可通过这两个工具互调。

**实现骨架**：

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

#### 方案对比

| 维度 | 传统方案 (HandoffTool 注入) | 推荐方案 (自定义调用入口) |
|------|--------------------------|------------------------|
| **持久化污染** | 有 | 无 |
| **循环转接风险** | 有 | 无 |
| **SubAgent 互调** | 需额外注入 | 天然支持（工具全局注册） |
| **LLM 调用方式** | 直接调用 `transfer_to_xxx` | 先 `list_sub_agents` 再 `call_sub_agent`（多一步） |
| **工具数量** | N 个 HandoffTool | 2 个固定工具 |

### 4.4 进阶方案：自传播工具（无需全局注册）

推荐方案（4.3）需要用 `@llm_tool` 全局注册 `call_sub_agent` 和 `list_sub_agents`，这样所有 Agent 都能看到它们。如果你不想全局暴露，可以用**自传播工具**模式：工具只在 `on_llm_request` 中注入 MainAgent，然后在每次调用 SubAgent 时把自己注入到 SubAgent 的工具集中，实现链式传播。

**核心思路**：
1. 在 `on_llm_request` 中给 MainAgent 注入 `call_sub_agent` 和 `list_sub_agents`
2. `call_sub_agent` 的 handler 在调用 SubAgent 时，把这两个工具也加入到 SubAgent 的 ToolSet 中
3. SubAgent 自然也能调用 `call_sub_agent`，形成链式传播，无需全局注册

**实现骨架**：

```python
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.astr_agent_context import AstrAgentContext, AgentContextWrapper
from astrbot.core.astr_agent_tool_exec import FunctionToolExecutor
from astrbot.core.agent.message import Message
from astrbot.core.agent.tool import FunctionTool


class SubAgentRouter(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 创建工具（handler 是绑定方法，可通过 self._xxx_tool 引用自身）
        self._call_tool = self._build_call_tool()
        self._list_tool = self._build_list_tool()

    def _build_list_tool(self) -> FunctionTool:
        async def _handler(event: AstrMessageEvent) -> str:
            orchestrator = self.context.subagent_orchestrator
            handoffs = orchestrator.handoffs
            if not handoffs:
                return "当前没有可用的子智能体"
            lines = [f"- {h.agent.name}: {h.description}" for h in handoffs]
            return "可用子智能体列表:\n" + "\n".join(lines)

        return FunctionTool(
            name="list_sub_agents",
            description="获取已有的 SubAgent 列表",
            parameters={"type": "object", "properties": {}},
            handler=_handler,
        )

    def _build_call_tool(self) -> FunctionTool:
        async def _handler(
            event: AstrMessageEvent, agent_name: str, input: str
        ) -> str:
            """根据名称调用指定的子智能体处理任务"""
            orchestrator = self.context.subagent_orchestrator
            handoff = None
            for h in orchestrator.handoffs:
                if h.agent.name == agent_name:
                    handoff = h
                    break
            if not handoff:
                return f"未找到名为 {agent_name} 的子智能体"

            agent = handoff.agent

            # 构造 run_context，构建 SubAgent 的基础工具集
            agent_context = AstrAgentContext(
                context=self.context, event=event
            )
            run_context = AgentContextWrapper(
                context=agent_context, tool_call_timeout=120
            )
            toolset = FunctionToolExecutor._build_handoff_toolset(
                run_context, agent.tools
            )

            # 关键：把 call_sub_agent 和 list_sub_agents 自身也注入到工具集！
            # 这样 SubAgent 就能调用 call_sub_agent，形成链式传播
            toolset.add_tool(self._call_tool)
            toolset.add_tool(self._list_tool)

            # 准备预设对话
            contexts = None
            if agent.begin_dialogs:
                contexts = []
                for d in agent.begin_dialogs:
                    contexts.append(
                        d if isinstance(d, Message)
                        else Message.model_validate(d)
                    )

            # Provider 选择
            prov_id = getattr(handoff, "provider_id", None)
            if not prov_id:
                prov_id = (
                    await self.context.get_current_chat_provider_id(
                        event.unified_msg_origin
                    )
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

        return FunctionTool(
            name="call_sub_agent",
            description="调用指定子智能体处理任务",
            parameters={
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": "子智能体名称",
                    },
                    "input": {
                        "type": "string",
                        "description": "任务描述",
                    },
                },
                "required": ["agent_name", "input"],
            },
            handler=_handler,
        )

    @filter.on_llm_request()
    async def _on_llm_request(self, event, req):
        # 只给 MainAgent 注入，SubAgent 通过自传播获得
        req.func_tool.add_tool(self._call_tool)
        req.func_tool.add_tool(self._list_tool)
```

**自传播机制说明**：

```
MainAgent (通过 on_llm_request 注入)
  │  可见: [call_sub_agent, list_sub_agents, ...其他工具]
  │
  ├── 调用 call_sub_agent("weather", "查天气")
  │   │
  │   └── handler 内部: toolset.add_tool(call_sub_agent, list_sub_agents)
  │       │
  │       └── weather SubAgent (通过 toolset 注入)
  │           │  可见: [call_sub_agent, list_sub_agents, ...继承的工具]
  │           │
  │           └── 调用 call_sub_agent("code", "写代码")
  │               │
  │               └── handler 内部: toolset.add_tool(call_sub_agent, list_sub_agents)
  │                   │
  │                   └── code SubAgent (通过 toolset 注入)
  │                       │  可见: [call_sub_agent, list_sub_agents, ...继承的工具]
  │                       │
  │                       └── 无限嵌套...
```

**与推荐方案的对比**：

| 维度 | 推荐方案 (全局注册) | 自传播方案 (请求级注入) |
|------|-------------------|----------------------|
| 是否全局注册 | 是（`@llm_tool`） | 否（`on_llm_request` 注入） |
| 工具可见性 | 所有 Agent 自动可见 | MainAgent 注入 → SubAgent 自传播 |
| 代码位置 | `@llm_tool` 装饰器在 Star 类中 | 工厂函数或绑定方法 |
| 持久化污染 | 无 | 无 |
| 循环风险 | 无（统一入口） | 无（统一入口） |
| 适用场景 | 通用工具、所有请求都需要 | 不想全局暴露、权限相关 |

### 4.5 进阶方案：复制 Agent 作为临时 Agent

如果你想在调用 SubAgent 时对其配置（工具集、系统提示词等）做临时修改，又不想影响原始配置，可以复制 Agent 作为临时 Agent 使用。

**核心思路**：`Agent` 是 `@dataclass`，可以用 `dataclasses.replace()` 或 `copy.copy()` 创建副本。对副本的修改不会影响原始 Agent。

**实现骨架**：

```python
import dataclasses
import copy
from astrbot.core.agent.agent import Agent
from astrbot.core.agent.handoff import HandoffTool


class SubAgentRouter(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self._call_tool = self._build_call_tool()
        self._list_tool = self._build_list_tool()

    def _build_call_tool(self) -> FunctionTool:
        async def _handler(
            event: AstrMessageEvent, agent_name: str, input: str
        ) -> str:
            orchestrator = self.context.subagent_orchestrator
            handoff = None
            for h in orchestrator.handoffs:
                if h.agent.name == agent_name:
                    handoff = h
                    break
            if not handoff:
                return f"未找到名为 {agent_name} 的子智能体"

            # ========== 关键：复制 Agent 作为临时 Agent ==========
            original_agent = handoff.agent

            # 方式1：dataclasses.replace（推荐，只修改指定字段）
            temp_agent = dataclasses.replace(
                original_agent,
                tools=[self._call_tool, self._list_tool],
                # 也可以临时修改 system_prompt
                # instructions="你是一个临时的天气助手",
            )

            # 方式2：copy.copy（浅拷贝，然后修改）
            # temp_agent = copy.copy(original_agent)
            # temp_agent.tools = [self._call_tool, self._list_tool]

            # 为临时 Agent 创建新的 HandoffTool
            temp_handoff = HandoffTool(agent=temp_agent)

            # 构造 run_context
            agent_context = AstrAgentContext(
                context=self.context, event=event
            )
            run_context = AgentContextWrapper(
                context=agent_context, tool_call_timeout=120
            )

            # 用 _build_handoff_toolset 构建工具集
            # 由于 temp_agent.tools 已指定为 [call_tool, list_tool]
            # 这里会走 FunctionTool 对象分支，直接加入工具集
            toolset = FunctionToolExecutor._build_handoff_toolset(
                run_context, temp_agent.tools
            )

            # Provider 选择
            prov_id = getattr(handoff, "provider_id", None)
            if not prov_id:
                prov_id = (
                    await self.context.get_current_chat_provider_id(
                        event.unified_msg_origin
                    )
                )

            # 直接调用 tool_loop_agent（复用 _execute_handoff 的逻辑）
            llm_resp = await self.context.tool_loop_agent(
                event=event,
                chat_provider_id=prov_id,
                prompt=input,
                system_prompt=temp_agent.instructions,
                tools=toolset,
                max_steps=30,
                tool_call_timeout=120,
            )
            return llm_resp.completion_text

        return FunctionTool(
            name="call_sub_agent",
            description="调用指定子智能体处理任务",
            parameters={
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string"},
                    "input": {"type": "string"},
                },
                "required": ["agent_name", "input"],
            },
            handler=_handler,
        )

    @filter.on_llm_request()
    async def _on_llm_request(self, event, req):
        req.func_tool.add_tool(self._call_tool)
        req.func_tool.add_tool(self._list_tool)
```

**两种复制方式的对比**：

| 维度 | `dataclasses.replace()` | `copy.copy()` |
|------|------------------------|---------------|
| 用法 | `replace(obj, field=new_value)` | `copy = copy.copy(obj); copy.field = new_value` |
| 未指定字段 | 保留原值 | 保留原值（浅拷贝） |
| 嵌套引用 | 原对象与副本共享嵌套对象（如 `begin_dialogs` 列表） | 同左 |
| 适用场景 | 只修改少量字段 | 需要在副本上做多次修改 |
| Python 版本 | 3.7+ | 所有版本 |

**注意事项**：
- `Agent` 是 `@dataclass`，浅拷贝后 `tools`、`begin_dialogs` 等列表字段仍然是引用。如果需要独立修改这些列表，需要用 `copy.deepcopy()` 或手动创建新列表
- 临时 HandoffTool 不需要注册到 `llm_tools`，它只在当前请求的 ToolSet 中使用，请求结束后自动释放
- 这种方式的本质是「动态创建一个拥有新配置的 SubAgent」，适用于需要临时修改 SubAgent 配置的场景

#### 四种方案总对比

| 维度 | 传统方案 (HandoffTool 注入) | 推荐方案 (全局注册) | 自传播方案 (请求级注入) | 复制 Agent 方案 |
|------|--------------------------|-------------------|---------------------|----------------|
| 持久化污染 | 有 | 无 | 无 | 无 |
| 全局注册 | 不需要 | 需要 | 不需要 | 不需要 |
| 循环风险 | 有 | 无 | 无 | 无 |
| SubAgent 互调 | 需额外注入 | 天然支持 | 自传播 | 自传播 |
| 临时修改配置 | 不支持 | 不支持 | 部分支持 | 支持 |
| 实现复杂度 | 低 | 低 | 中 | 高 |
| 适用场景 | 单层调用 | 通用工具 | 不想全局暴露 | 临时修改配置 |

---

## 五、SubAgent 工具集缺失问题

### 问题描述

当使用原生 `transfer_to_*` 工具调用 SubAgent 时，SubAgent 只能看到**沙箱基础 8 件套**工具，而系统内置的 Skill 工具、网页搜索工具、CUA 工具、浏览器工具等均不可见。MainAgent 能正常看到所有工具，但 SubAgent 的工具集严重缺失。

### 根本原因

通过源码分析，SubAgent 的工具集构建逻辑（`_build_handoff_toolset`）与 MainAgent 的工具集构建逻辑存在显著差异。

**SubAgent 工具构建逻辑**（astrbot/core/astr_agent_tool_exec.py#L267-L281）：

```python
if tools is None:
    toolset = ToolSet()
    # ① 插件/MCP 工具（通过 get_full_tool_set 获取）
    for registered_tool in tool_mgr.get_full_tool_set():
        ...
    # ② 仅沙箱运行时的 8 件套
    for runtime_tool in runtime_computer_tools.values():
        ...
```

**MainAgent 工具构建逻辑**（astrbot/core/astr_main_agent.py#L1116-L1248）：

```python
# 沙箱 8 件套
tool_mgr.get_builtin_tool(ExecuteShellTool)
tool_mgr.get_builtin_tool(PythonTool)
...
# Skill 工具
tool_mgr.get_builtin_tool(RunBrowserSkillTool)
tool_mgr.get_builtin_tool(CreateSkillPayloadTool)
tool_mgr.get_builtin_tool(CreateSkillCandidateTool)
...
# 网页搜索工具
tool_mgr.get_builtin_tool(TavilyWebSearchTool)
tool_mgr.get_builtin_tool(BochaWebSearchTool)
tool_mgr.get_builtin_tool(BraveWebSearchTool)
...
# FutureTaskTool
tool_mgr.get_builtin_tool(FutureTaskTool)
# CUA 工具
tool_mgr.get_builtin_tool(CuaScreenshotTool)
tool_mgr.get_builtin_tool(CuaMouseClickTool)
tool_mgr.get_builtin_tool(CuaKeyboardTypeTool)
# 浏览器工具
tool_mgr.get_builtin_tool(BrowserExecTool)
tool_mgr.get_builtin_tool(BrowserBatchExecTool)
```

### 两个独立的工具系统

关键发现：**系统内置 Tool 和插件全局 Tool 存储在不同的列表中**，`get_full_tool_set()` 只返回插件/MCP 工具，不包含内置工具。

`FunctionToolManager`（astrbot/core/provider/func_tool_manager.py#L287-L292）维护了两个独立的列表：

| 存储属性 | 获取方式 | 包含内容 |
|---------|---------|---------|
| `func_list` | `get_full_tool_set()` | 插件 `@llm_tool` 注册的工具 + MCP 工具 |
| `builtin_func_list` | `get_builtin_tool()` | 系统内置工具（Skill、搜索、CUA 等） |

`get_full_tool_set()` 只返回 `func_list`，**不包含** `builtin_func_list` 中的内置工具。

### SubAgent 缺失的工具清单

对比 MainAgent 和 SubAgent 的工具集：

| 工具类别 | MainAgent | SubAgent | 缺失数量 |
|---------|-----------|----------|---------|
| 沙箱基础 8 件套 | ✅ | ✅（通过 `runtime_computer_tools`） | 0 |
| Skill 工具（3 个） | ✅ | ❌ | 3 |
| Skill 管理工具（7 个） | ✅ | ❌ | 7 |
| 网页搜索工具（7 个） | ✅ | ❌ | 7 |
| FutureTaskTool | ✅ | ❌ | 1 |
| CUA 工具（3 个） | ✅ | ❌ | 3 |
| 浏览器工具（3 个） | ✅ | ❌ | 3 |
| 插件/MCP 工具 | ✅ | ✅（通过 `get_full_tool_set()`） | 0 |
| **总计缺失** | | | **24 个** |

### GitHub 状态

截至当前版本，**此问题尚未修复**。在 GitHub 的 commit 和 PR 记录中未找到修复此问题的提交。这是框架层面的一个已知缺陷。

### 临时解决方案

如果需要让 SubAgent 也能使用这些内置工具，可以在自定义 `call_sub_agent` 工具的 handler 中，构建 toolset 后手动补充缺失的内置工具：

```python
from astrbot.core.astr_agent_tool_exec import FunctionToolExecutor
from astrbot.core.tools.builtin_tools import (
    RunBrowserSkillTool,
    CreateSkillPayloadTool,
    CreateSkillCandidateTool,
    TavilyWebSearchTool,
    BochaWebSearchTool,
    FutureTaskTool,
    CuaScreenshotTool,
    CuaMouseClickTool,
    CuaKeyboardTypeTool,
    BrowserExecTool,
    BrowserBatchExecTool,
)

async def _call_sub_agent_handler(self, event, agent_name, input):
    ...
    toolset = FunctionToolExecutor._build_handoff_toolset(run_context, agent.tools)

    # 补充 SubAgent 缺失的内置工具
    tool_mgr = self.context.get_llm_tool_manager()

    # Skill 工具
    toolset.add_tool(tool_mgr.get_builtin_tool(RunBrowserSkillTool))
    toolset.add_tool(tool_mgr.get_builtin_tool(CreateSkillPayloadTool))
    toolset.add_tool(tool_mgr.get_builtin_tool(CreateSkillCandidateTool))

    # 网页搜索工具（按需添加）
    toolset.add_tool(tool_mgr.get_builtin_tool(TavilyWebSearchTool))
    toolset.add_tool(tool_mgr.get_builtin_tool(BochaWebSearchTool))

    # FutureTask 工具
    toolset.add_tool(tool_mgr.get_builtin_tool(FutureTaskTool))

    # CUA 工具（按需添加）
    toolset.add_tool(tool_mgr.get_builtin_tool(CuaScreenshotTool))
    toolset.add_tool(tool_mgr.get_builtin_tool(CuaMouseClickTool))

    # 浏览器工具（按需添加）
    toolset.add_tool(tool_mgr.get_builtin_tool(BrowserExecTool))
    toolset.add_tool(tool_mgr.get_builtin_tool(BrowserBatchExecTool))
    ...
```

**注意**：这只是临时方案。根本修复需要修改框架的 `_build_handoff_toolset` 方法，让它也添加非 runtime 的内置工具。在框架修复前，建议根据实际需要选择性补充工具，避免一次性添加过多工具导致 SubAgent 的 prompt 过长。

#### 批量获取内置工具（推荐）

逐个 import 工具类比较繁琐，可以通过 `iter_builtin_tool_classes()` 批量获取所有内置工具类：

```python
from astrbot.core.tools.registry import iter_builtin_tool_classes

async def _call_sub_agent_handler(self, event, agent_name, input):
    ...
    toolset = FunctionToolExecutor._build_handoff_toolset(run_context, agent.tools)

    # 方式1：一次性添加所有内置工具
    tool_mgr = self.context.get_llm_tool_manager()
    for tool_cls in iter_builtin_tool_classes():
        toolset.add_tool(tool_mgr.get_builtin_tool(tool_cls))
    ...
```

如果只需要部分模块的工具，可以按模块筛选：

```python
from astrbot.core.tools import computer_tools, web_search_tools, cron_tools

# 方式2：按模块筛选
tool_mgr = self.context.get_llm_tool_manager()
from astrbot.core.provider.func_tool_manager import FuncTool

# 只添加计算机类工具（Skill、CUA、浏览器等）
for name in dir(computer_tools):
    obj = getattr(computer_tools, name)
    if isinstance(obj, type) and issubclass(obj, FuncTool):
        toolset.add_tool(tool_mgr.get_builtin_tool(obj))

# 只添加搜索工具
for name in dir(web_search_tools):
    obj = getattr(web_search_tools, name)
    if isinstance(obj, type) and issubclass(obj, FuncTool):
        toolset.add_tool(tool_mgr.get_builtin_tool(obj))
```

内置工具按模块组织（astrbot/core/tools/registry.py#L12-L18）：

| 模块 | 包含的工具 |
|------|-----------|
| `computer_tools` | Skill 工具、浏览器工具、CUA 工具、计算机基础工具 |
| `cron_tools` | FutureTaskTool |
| `knowledge_base_tools` | KnowledgeBaseQueryTool |
| `message_tools` | SendMessageToUserTool |
| `web_search_tools` | Tavily、Bocha、Brave、Firecrawl、Baidu、Exa 等搜索工具 |

---

## 六、常见问题

### SubAgent 和普通工具的区别？
普通工具执行一个具体功能（查天气、搜信息），SubAgent 是一个独立的 Agent，拥有自己的人格和工具集，可以进行多轮对话和复杂推理。

### SubAgent 能调用其他 SubAgent 吗？
可以，但默认框架会排除其他 HandoffTool 以防止无限循环转接。若需互调，请参考第四章节的推荐方案。

### 如何选择配置文件注册还是装饰器注册？
- **配置文件注册**：适合需要在运行时动态调整的场景（WebUI 修改后立即生效）
- **装饰器注册**：适合插件自带的子 Agent，与插件代码绑定

### SubAgent 的对话历史会被保存吗？
是的，SubAgent 的对话历史会通过 `persist_agent_history` 保存，下次对话时可以恢复上下文。

### 如何获取 SubAgent 的执行结果？
SubAgent 执行完成后，结果会作为 `CallToolResult` 返回给主 Agent，主 Agent 可以决定是否直接回复用户或进一步处理。

## 七、与相关模块的关系

| 模块 | 关系 |
|------|------|
| **Tool 模块** | HandoffTool 继承自 FunctionTool，是一种特殊的工具 |
| **Agent 模块** | Agent 类定义了子智能体的配置（instructions、tools、hooks） |
| **Context 模块** | `Context.subagent_orchestrator` 提供访问子智能体编排器的入口 |
| **Persona 模块** | SubAgent 可以引用 Persona 中定义的人格设定 |
| **Provider 模块** | SubAgent 可以使用独立的 Provider（通过 `provider_id` 配置） |

## 为什么几乎所有HOOK都只适用于MainAgent

以下是我的猜测：

简单一句话说，**如果SubAgent能被截断，所有插件都会往它身上注入东西**。

大概率是。理由很简单：

`SubAgentOrchestrator` 构建 SubAgent 的 `Agent` 对象时，**根本没设 `run_hooks`**：

```python
agent = Agent[AstrAgentContext](
    name=name,
    instructions=instructions,
    tools=tools,
)
# run_hooks 没传 → None
```

而 `@filter.on_agent_begin()` 这类装饰器，是 Star 插件系统在加载插件时收集的，框架只会在**启动 MainAgent 的 Agent 执行流**时绑定上去。

SubAgent 走的是 `HandoffTool` → `tool_loop_agent` 这条独立的执行路径，`run_hooks=None` 意味着它不会触发热加载的任何 filter hook，包括：

- `@filter.on_agent_begin()`
- `@filter.on_agent_end()`
- `@filter.on_llm_request()`
- `@filter.on_llm_response()`

全部只对 MainAgent 生效。SubAgent 是一个裸的 `Agent`，除了 `instructions` 和 `tools` 啥都没带。这就是你想要动态注入工具给 SubAgent 时碰到的墙——没有 hook 口子可以插进去。

至于为什么，我猜测是

SubAgent 本质上是**受控的执行沙箱**——它只拿你显式配给它的人设和工具，不受任何第三方插件干扰。如果 SubAgent 也走 `on_llm_request` 这套 hook 链，那每个装了插件的用户都会面临：

- 插件 A 偷偷往 SubAgent 里塞工具
- 插件 B 改了 SubAgent 的 system prompt
- 插件 C 把 SubAgent 的输出截胡了

那 SubAgent 就完全不可控了，配置界面里配的 `tools` 和 `instructions` 等于白写。

所以隔离是对的，你的问题本质上是**怎么在「隔离」的前提下开一个合法的口子**，让管理员有能力显式授权某些工具给特定 SubAgent——就是 #8121 想做的事。


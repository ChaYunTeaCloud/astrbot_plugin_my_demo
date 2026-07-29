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

### 5.1 访问 SubAgentOrchestrator

```python
class MyPlugin(Star):
    def __init__(self, context):
        super().__init__(context)

    @filter.command("list_agents")
    async def list_agents(self, event):
        orchestrator = self.context.subagent_orchestrator
        handoffs = orchestrator.handoffs
        names = [h.name for h in handoffs] if handoffs else ["无"]
        yield event.plain_result(f"已注册的 SubAgent: {names}")
```

### 5.2 监听 SubAgent 状态变化

`SubAgentOrchestrator` 没有提供事件监听机制，但你可以在 `on_llm_request` 中动态调整：

```python
@filter.on_llm_request()
async def adjust_subagents(self, event, req):
    orchestrator = self.context.subagent_orchestrator
    for handoff in orchestrator.handoffs:
        # 根据条件禁用某个 HandoffTool
        if should_disable(handoff, event):
            req.func_tool.remove_tool(handoff.name)
```

### 5.3 动态添加 HandoffTool

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

## 七、与相关模块的关系

| 模块 | 关系 |
|------|------|
| Tool 模块 | HandoffTool 继承自 FunctionTool，是一种特殊的工具 |
| Agent 模块 | Agent 类定义了子智能体的配置（instructions、tools、hooks） |
| Context 模块 | `Context.subagent_orchestrator` 提供访问子智能体编排器的入口 |
| Persona 模块 | SubAgent 可以引用 Persona 中定义的人格设定 |
| Provider 模块 | SubAgent 可以使用独立的 Provider（通过 `provider_id` 配置） |

# MainAgent 调用流程

## 一、总体架构

```text
用户消息
    │
    ▼
┌─────────────────────────────────────────────┐
│  Pipeline 消息处理管线                        │
│  (../.venv/Lib/site-packages/astrbot/core/pipeline/)                    │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│  MainAgent 构建 + 执行                       │
│  (astr_main_agent.py)                        │
└─────────────────────────────────────────────┘
    │                             
    │  LLM 调用 transfer_to_* 工具
    ▼
┌─────────────────────────────────────────────┐
│  SubAgent 执行                               │
│  (astr_agent_tool_exec.py)                   │
└─────────────────────────────────────────────┘
```

---

## 二、MainAgent 调用逻辑

### 2.1 入口

[astr_main_agent.py](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py) 中的 `build_main_agent` 是 MainAgent 构建的核心入口（由 Pipeline 的 `InternalAgentSubStage.process` 调用，见 core/pipeline/process_stage/method/agent_sub_stages/internal.py L231-L236）。

### 2.2 工具集构建流程（按顺序）

#### Step 1: 初始化基础工具集

```python
# L599/L603
tmgr = plugin_context.get_llm_tool_manager()
persona_toolset = tmgr.get_full_tool_set()  # 包含 func_list 中所有工具
```

`get_full_tool_set()` 返回 `func_list` 中的所有工具：
- ✅ 插件注册的工具（`@llm_tool`）
- ✅ MCP 工具
- ❌ 不包含 `builtin_func_list` 中的系统内置工具

#### Step 2: Persona 工具过滤

```python
# L602-L617
if (persona and persona.get("tools") is None) or not persona:
    # Persona 未指定工具 → 使用全量 func_list
    persona_toolset = tmgr.get_full_tool_set()
else:
    # Persona 指定了工具 → 只保留指定的
    persona_toolset = ToolSet()
    for tool_name in persona["tools"]:
        tool = tmgr.get_func(tool_name)
        ...
```

#### Step 3: SubAgent Handoff 工具注入

```python
# L661-L663
if req.func_tool is None:
    req.func_tool = ToolSet()
for tool in so.handoffs:
    req.func_tool.add_tool(tool)  # 注入 transfer_to_* 工具
```

#### Step 4: Skill 注入

```python
# L566-L592
skill_manager = SkillManager()
skills = skill_manager.list_skills(active_only=True, runtime=runtime)
skills = _filter_skills_for_current_config(skills, cfg)
# Skill 作为提示词追加到 system_prompt
req.system_prompt += f"\n{build_skills_prompt(skills)}\n"
```

#### Step 5: 文件提取工具

```python
# L1596
if config.file_extract_enabled:
    await _apply_file_extract(event, req, config)
```

#### Step 6: 插件工具过滤

```python
# L1615
_plugin_tool_fix(event, req)  # 根据会话过滤插件工具
```

#### Step 7: 知识库工具

```python
# L1610
await _apply_kb(event, req, plugin_context, config)
```

#### Step 8: 网络搜索工具注入

```python
# L1616
await _apply_web_search_tools(event, req, plugin_context)
```

添加 Tavily/Brave/Exa 等搜索工具到 `func_tool`。

#### Step 9: 运行时计算工具注入

```python
# L1621-L1624
if config.computer_use_runtime == "sandbox":
    _apply_sandbox_tools(config, req, req.session_id)
elif config.computer_use_runtime == "local":
    _apply_local_env_tools(req, plugin_context)
```

这一步**注入了所有系统内置工具**（`builtin_func_list`）：

| Local Runtime | Sandbox Runtime |
|---------------|-----------------|
| `LocalExecuteShellTool` | `ExecuteShellTool` |
| `ShellSessionTool` | `PythonTool` |
| `LocalPythonTool` | `FileUploadTool` |
| `FileReadTool` | `FileDownloadTool` |
| `FileWriteTool` | `FileReadTool` |
| `FileEditTool` | `FileWriteTool` |
| `GrepTool` | `FileEditTool` |
| | `GrepTool` |
| | `BrowserExecTool` |
| | `RunBrowserSkillTool` |
| | + CUA 系列工具 |
| | + Skill 管理工具 |

#### Step 10: Skill 辅助工具

如果启用了 Skill 相关功能，还会注入：
- `FutureTaskTool`
- Skill Candidate 管理工具（仅 Sandbox 模式）

#### Step 11: 主动消息工具

```python
# L1635-L1642
if event.platform_meta.support_proactive_message:
    req.func_tool.add_tool(
        plugin_context.get_llm_tool_manager().get_builtin_tool(SendMessageToUserTool)
    )
```

#### Step 12: 群消息历史工具注入

当配置启用时，MainAgent 会注入 `GetGroupMessageHistoryTool`（`../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py#L1648-L1657`），允许 LLM 获取群聊历史消息。

#### LLM 安全模式注入

在 MainAgent 请求构建过程中，框架会根据配置注入 LLM 安全模式提示词（`../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py#L1140`）：

- 当 `config.safety_mode_strategy == "system_prompt"` 时，会在 system_prompt 前面添加 `LLM_SAFETY_MODE_SYSTEM_PROMPT`
- 该功能通过 `_apply_llm_safety_mode()` 实现，在 `build_main_agent` 中调用（`#L1618-L1619`）

### 2.3 MainAgent 最终工具构成

```text
MainAgent 工具集 = 
    func_list 中所有工具（插件 + MCP）
    + 所有 transfer_to_* Handoff 工具
    + 系统内置工具（builtin_func_list，根据运行时）
    + 网络搜索工具
    + 文件提取工具
    + Skill 辅助工具
    + 主动消息工具
    (+ Skill 提示词注入到 system_prompt)
```

### 2.4 MainAgent 执行方式

```python
# L1714 起
agent_runner.reset(
    provider=provider,
    request=req,
    run_context=AgentContextWrapper(...),
    tool_executor=FunctionToolExecutor(),
    ...
)
```

通过 `AgentRunner` + `FunctionToolExecutor` 执行，支持多轮 tool call 循环。

---

## 三、AstrBot 构建 MainAgent 请求的源码

MainAgent 不使用 Agent 类，MainAgent 的构建走的是完全不同的路径：

```text
用户消息 → Pipeline → InternalAgentSubStage → build_main_agent()
                                                  ↓
                                          MainAgentBuildResult
                                          ├── agent_runner: AgentRunner
                                          ├── provider_request: ProviderRequest
                                          └── provider: Provider
```

MainAgent 没有 Agent 实例，它使用的是：

- AgentRunner 执行器
- ProviderRequest 请求对象
- Provider 模型提供商

AstrBot 构建 MainAgent 请求涉及 4 个核心文件，按调用顺序：

### 3.1 Pipeline 触发构建

[internal.py#L231-L251](../.venv/Lib/site-packages/astrbot/core/pipeline/process_stage/method/agent_sub_stages/internal.py#L231-L251) `InternalAgentSubStage`

```python
build_result = await build_main_agent(event, plugin_context, config)
agent_runner = build_result.agent_runner
req = build_result.provider_request
provider = build_result.provider
reset_coro = build_result.reset_coro
```

### 3.2 MainAgent 构建（核心）

[astr_main_agent.py](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py) `build_main_agent` 函数

```text
解析 Persona → 注入 Skill → 注入工具 → 注入 Handoff → 配置 AgentRunner
```

详细步骤见第二章「二、MainAgent 调用逻辑」。

### 3.3 AgentRunner 配置与执行

[astr_main_agent.py#L1714-L1744](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py#L1714-L1744)

```python
agent_runner.reset(
    provider=provider,
    request=req,
    run_context=AgentContextWrapper(...),
    tool_executor=FunctionToolExecutor(),
    agent_hooks=MAIN_AGENT_HOOKS,   # ← 包含 on_agent_begin 等钩子
    ...
)
```

### 3.4 AgentRunner.step_until_done() 执行

`AgentRunner.step_until_done()`（由 `run_agent()` 包装调用）内部会触发：
- `on_agent_begin` 钩子 → 调用所有注册的 `@on_agent_begin` 事件
- `on_tool_start` / `on_tool_end` → 工具调用前后
- `on_agent_done` / `on_llm_response` → Agent 完成后

这些钩子由 `MainAgentHooks`（core/astr_agent_hooks.py）注入到 `agent_runner.reset()`。

---

## 四、与 SubAgent 的差异

### 4.1 工具注入差异

MainAgent 拥有完整的工具集，包括 `func_list` 中的插件工具与 MCP 工具、`builtin_func_list` 中的全部系统内置工具（约 25 个，具体数量取决于版本配置）、网络搜索工具、文件提取工具、知识库工具、Skill 辅助工具、主动消息工具，以及所有 `transfer_to_*` Handoff 工具。

SubAgent 仅拥有 `func_list` 中的工具（排除 Handoff 工具以防死循环）加上运行时计算工具的沙箱基础工具集，缺失系统内置工具、网络搜索、文件提取、知识库、Skill 辅助、主动消息等能力。

| 工具类别 | MainAgent | SubAgent |
|---------|-----------|----------|
| 插件注册工具 | ✅ | ✅（通过 func_list） |
| MCP 工具 | ✅ | ✅（通过 func_list） |
| 系统内置工具（builtin_func_list） | ✅ | ❌ 仅运行时基础工具集 |
| transfer_to_* Handoff | ✅ | ❌（已排除，防止死循环） |
| 网络搜索工具 | ✅ | ❌ |
| 文件提取工具 | ✅ | ❌ |
| Skill 辅助工具 | ✅ | ❌ |
| 主动消息工具 | ✅ | ❌ |

### 4.2 Skill 注入差异

MainAgent 通过 `SkillManager` 收集活跃 Skill，按 Persona 的 `skills` 字段过滤后，使用 `build_skills_prompt()` 构建 Skill 提示词并追加到 `system_prompt`，使 MainAgent 能够感知并调用 Skill。

SubAgent 默认没有任何 Skill 注入：`subagent_orchestrator.py` 构建 `Agent` 对象时未读取 Persona 的 `skills` 字段，`Agent` 类本身也没有 `skills` 属性，因此 SubAgent 的 `system_prompt` 中不包含任何 Skill 信息。

| Skill 维度 | MainAgent | SubAgent |
|---------|-----------|----------|
| Skill 注入方式 | 追加到 system_prompt | ❌ 未注入 |
| Persona skills 过滤 | ✅ 读取 persona["skills"] 过滤 | ❌ 未读取 |
| Workspace Skills | ✅ 注入 | ❌ 未注入 |

### 4.3 Persona 应用差异

MainAgent 在每次请求前动态解析 Persona，将 Persona prompt 作为 `system_prompt` 基础，并在此基础上追加 Skill 提示词、router_prompt 等多段内容；Persona 修改后立即生效，支持会话级切换。

SubAgent 在 Agent 创建时一次性固化 Persona 数据（prompt 作为 `instructions`、tools 作为白名单、begin_dialogs 作为预设对话），创建后与 Persona 解耦，Persona 修改需重建 Agent 才能生效。

| 维度 | MainAgent | SubAgent |
|---------|-----------|----------|
| system_prompt 来源 | Persona prompt + 多段追加（Skill、router_prompt 等） | 仅 Persona prompt 或配置的 system_prompt |
| begin_dialogs | ✅ | ✅ |
| Persona skills 过滤 | ✅ | ❌ |
| Persona tools 过滤 | ✅ | ✅（从 Persona 读取 tools 字段） |
| Persona 应用时机 | 每次请求前动态解析 | Agent 创建时一次性固化 |

> 详细的 SubAgent 调用流程，请参见 [SubAgent 调用流程](./SubAgent%20调用流程.md)

# MainAgent vs SubAgent 调用逻辑对比

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
```json

---

## 二、MainAgent 调用逻辑

### 2.1 入口

[astr_main_agent.py](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py) 中的 `build_initial_request` 是 MainAgent 构建的核心入口（由 Pipeline 的 `LLMRequestBuildStage` 调用）。

### 2.2 工具集构建流程（按顺序）

#### Step 1: 初始化基础工具集

```python
# L562-L566
tmgr = plugin_context.get_llm_tool_manager()
persona_toolset = tmgr.get_full_tool_set()  # 包含 func_list 中所有工具
```json

`get_full_tool_set()` 返回 `func_list` 中的所有工具：
- ✅ 插件注册的工具（`@llm_tool`）
- ✅ MCP 工具
- ✅ 前置处理工具（如 `astrbot_summary_tool`）
- ❌ 不包含 `builtin_func_list` 中的系统内置工具

#### Step 2: Persona 工具过滤

```python
# L564-L580
if (persona and persona.get("tools") is None) or not persona:
    # Persona 未指定工具 → 使用全量 func_list
    persona_toolset = tmgr.get_full_tool_set()
else:
    # Persona 指定了工具 → 只保留指定的
    persona_toolset = ToolSet()
    for tool_name in persona["tools"]:
        tool = tmgr.get_func(tool_name)
        ...
```json

#### Step 3: SubAgent Handoff 工具注入

```python
# L620-L625
if req.func_tool is None:
    req.func_tool = ToolSet()
for tool in so.handoffs:
    req.func_tool.add_tool(tool)  # 注入 transfer_to_* 工具
```json

#### Step 4: Skill 注入

```python
# L530-L555
skill_manager = SkillManager()
skills = skill_manager.list_skills(active_only=True, runtime=runtime)
skills = _filter_skills_for_current_config(skills, cfg)
# Skill 作为提示词追加到 system_prompt
req.system_prompt += f"\n{build_skills_prompt(skills)}\n"
```json

#### Step 5: 文件提取工具

```python
# L1543-L1547
if config.file_extract_enabled:
    await _apply_file_extract(event, req, config)
```json

#### Step 6: 插件工具过滤

```python
# L1564
_plugin_tool_fix(event, req)  # 根据会话过滤插件工具
```json

#### Step 7: 知识库工具

```python
# L1559
await _apply_kb(event, req, plugin_context, config)
```json

#### Step 8: 网络搜索工具注入

```python
# L1565
await _apply_web_search_tools(event, req, plugin_context)
```json

添加 Tavily/Brave/Exa 等搜索工具到 `func_tool`。

#### Step 9: 运行时计算工具注入

```python
# L1570-L1573
if config.computer_use_runtime == "sandbox":
    _apply_sandbox_tools(config, req, req.session_id)
elif config.computer_use_runtime == "local":
    _apply_local_env_tools(req, plugin_context)
```json

这一步**注入了所有系统内置工具**（`builtin_func_list`）：

| Local Runtime | Sandbox Runtime |
|---------------|-----------------|
| `ExecuteShellTool` | `ExecuteShellTool` |
| `LocalPythonTool` | `PythonTool` |
| `FileReadTool` | `FileUploadTool` |
| `FileWriteTool` | `FileDownloadTool` |
| `FileEditTool` | `FileReadTool` |
| `GrepTool` | `FileWriteTool` |
| | `FileEditTool` |
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
# L1584-L1591
if event.platform_meta.support_proactive_message:
    req.func_tool.add_tool(
        plugin_context.get_llm_tool_manager().get_builtin_tool(SendMessageToUserTool)
    )
```bash

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
```bash

### 2.4 MainAgent 执行方式

```python
# L1645-L1671
agent_runner.reset(
    provider=provider,
    request=req,
    run_context=AgentContextWrapper(...),
    tool_executor=FunctionToolExecutor(),
    ...
)
```json

通过 `AgentRunner` + `FunctionToolExecutor` 执行，支持多轮 tool call 循环。

---

## 三、SubAgent 调用逻辑

### 3.1 入口

MainAgent 调用 `transfer_to_{agent_name}` 工具后，由 [astr_agent_tool_exec.py](../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py) 的 `_execute_handoff` 方法处理。

### 3.2 工具集构建流程

#### Step 1: Agent 对象创建

在 [subagent_orchestrator.py](../.venv/Lib/site-packages/astrbot/core/subagent_orchestrator.py) 中：

```python
# L83-L87
agent = Agent[AstrAgentContext](
    name=name,
    instructions=instructions,      # 从 Persona 的 prompt 或配置的 system_prompt
    tools=tools,                     # 从 Persona 的 tools 或配置的 tools
)
agent.begin_dialogs = begin_dialogs  # 从 Persona 的 _begin_dialogs_processed
```json

**注意**：`Agent` 类没有 `skills` 字段，也没有从 Persona 中读取 `skills`。

#### Step 2: 构建 SubAgent 工具集

```python
# astr_agent_tool_exec.py L329
toolset = cls._build_handoff_toolset(run_context, tool.agent.tools)
```text

`_build_handoff_toolset` 的逻辑：

```python
# L267-L281: tools=None 时（Persona 未指定工具）
if tools is None:
    toolset = ToolSet()
    # 添加 func_list 中所有非 Handoff 工具
    for registered_tool in tool_mgr.get_full_tool_set():
        if registered_tool.name in handoff_names:  # 排除 transfer_to_*
            continue
        if registered_tool.active:
            toolset.add_tool(registered_tool)
    # 添加运行时计算工具
    for runtime_tool in runtime_computer_tools.values():
        toolset.add_tool(runtime_tool)
    return toolset
```json

#### Step 3: 注入运行时计算工具

```python
# L259-L263
runtime_computer_tools = cls._get_runtime_computer_tools(
    runtime, tool_mgr, ...
)
```bash

这一步**只添加运行时相关的基础工具**（Local 或 Sandbox 8 件套），不包含其他系统内置工具。

### 3.3 SubAgent 工具集 vs MainAgent 工具集

| 工具类别 | MainAgent | SubAgent |
|---------|-----------|----------|
| 插件注册工具 | ✅ | ✅（通过 func_list） |
| MCP 工具 | ✅ | ✅（通过 func_list） |
| 系统内置工具（builtin_func_list） | ✅ | ❌ 仅运行时 8 件套 |
| transfer_to_* Handoff | ✅ | ❌（已排除，防止死循环） |
| 网络搜索工具 | ✅ | ❌ |
| 文件提取工具 | ✅ | ❌ |
| Skill 辅助工具 | ✅ | ❌ |
| 主动消息工具 | ✅ | ❌ |
| **Skill 提示词** | ✅ | ❌ |
| Persona 提示词 | ✅（追加到 system_prompt） | ✅（作为 instructions） |
| Persona begin_dialogs | ✅（注入到 contexts） | ✅（注入到 contexts） |

### 3.4 SubAgent 执行方式

```python
# L359-L370
llm_resp = await ctx.tool_loop_agent(
    event=event,
    chat_provider_id=prov_id,       # 可用 SubAgent 专用 Provider
    prompt=input_,
    image_urls=image_urls,
    system_prompt=tool.agent.instructions,  # Persona 的 system prompt
    tools=toolset,
    contexts=contexts,               # begin_dialogs
    max_steps=agent_max_step,
    tool_call_timeout=run_context.tool_call_timeout,
    stream=stream,
)
```bash

调用 `tool_loop_agent` 方法（而非 `AgentRunner`），同样支持多轮 tool call。

---

## 四、核心差异总结

### 4.1 工具注入差异

| 对比维度 | MainAgent | SubAgent | 原因 |
|---------|-----------|----------|------|
| 工具集来源 | `func_list` + `builtin_func_list` | 仅 `func_list` | SubAgent 的 `_build_handoff_toolset` 没有合并 `builtin_func_list` |
| 系统内置工具数量 | 约 25 个 | 仅 8 个（运行时） | MainAgent 有 Step 9 专门注入 |
| 网络搜索工具 | ✅ | ❌ | MainAgent 有 Step 8 专门注入 |
| Skill 辅助工具 | ✅ | ❌ | MainAgent 有 Step 10 专门注入 |

### 4.2 Skill 注入差异

| 对比维度 | MainAgent | SubAgent | 原因 |
|---------|-----------|----------|------|
| Skill 注入方式 | 追加到 `system_prompt` | ❌ 未注入 | SubAgent 的 system_prompt 仅来自 Persona 的 `prompt` |
| Persona skills 过滤 | ✅ 读取 `persona["skills"]` 过滤 | ❌ `subagent_orchestrator.py` 未读取 | 构建 Agent 对象时忽略了 Persona 的 `skills` 字段 |
| Workspace Skills | ✅ 注入 | ❌ 未注入 | MainAgent 有额外的 workspace skill 收集逻辑 |

### 4.3 Persona 应用差异

| 对比维度 | MainAgent | SubAgent |
|---------|-----------|----------|
| system_prompt 来源 | Persona prompt + 多段追加（Skill、router_prompt 等） | 仅 Persona prompt 或配置的 system_prompt |
| begin_dialogs | ✅ | ✅ |
| Persona skills 过滤 | ✅ | ❌ |
| Persona tools 过滤 | ✅ | ✅（从 Persona 读取 tools 字段） |

### 4.4 Provider 差异

| 对比维度 | MainAgent | SubAgent |
|---------|-----------|----------|
| Provider 选择 | 全局默认 Provider | 可通过 `provider_id` 配置 SubAgent 专用 Provider |
| 模型选择 | 使用配置的模型 | 跟随 Provider 的模型设置 |

---

## 五、Bug 与已知问题

### 5.1 SubAgent 缺失系统内置工具

**问题**：`_build_handoff_toolset` 只从 `func_list` 构建工具集，不包含 `builtin_func_list` 中的工具。

**影响**：SubAgent 无法使用 `astrbot_summary_tool`、`astrbot_file_read_tool` 等内置工具。

**解决方案**：在 `_build_handoff_toolset` 中补充 `builtin_func_list` 的非运行时工具。

### 5.2 SubAgent 缺失 Skill 注入

**问题**：`subagent_orchestrator.py` 构建 `Agent` 对象时，没有读取 Persona 的 `skills` 字段。

**影响**：SubAgent 即使配置了 Persona Skill，也看不到任何 Skill。

**解决方案**：需要框架层面修复 `subagent_orchestrator.py` 以处理 `skills` 字段，并在 `_execute_handoff` 中将 Skill 注入 system_prompt。

### 5.3 SubAgent 缺失搜索等辅助工具

**问题**：SubAgent 没有经过 `_apply_web_search_tools`、`_apply_kb`、`_apply_file_extract` 等步骤。

**影响**：SubAgent 无法进行联网搜索、知识库查询、文件提取等操作。

**解决方案**：需要框架层面在 `_build_handoff_toolset` 或 `_execute_handoff` 中补充这些工具。

---

## 六、Plugin 开发者的应对策略

### 6.1 让 SubAgent 看到更多工具

在自定义 `call_sub_agent` 工具的 handler 中，手动构建完整工具集：

```python
from astrbot.core.provider.func_tool_manager import FunctionToolManager

async def _handler(self, event, agent_name, input):
    # 获取所有 func_list 工具
    tmgr = self.context.get_llm_tool_manager()
    full_toolset = tmgr.get_full_tool_set()
    
    # 补充 builtin_func_list 中的工具
    for tool_cls in tmgr.builtin_func_list:
        builtin = tmgr.get_builtin_tool(tool_cls)
        if builtin and builtin.active:
            full_toolset.add_tool(builtin)
    
    # 补充运行时工具
    runtime_tools = FunctionToolExecutor._get_runtime_computer_tools("local", tmgr)
    for t in runtime_tools.values():
        full_toolset.add_tool(t)
    
    # ... 调用 tool_loop_agent
```bash

### 6.2 让 SubAgent 看到 Skill

```python
from astrbot.core.skills import SkillManager, build_skills_prompt

skill_manager = SkillManager()
skills = skill_manager.list_skills(active_only=True, runtime="local")
skill_prompt = build_skills_prompt(skills)
system_prompt = agent.instructions + "\n" + skill_prompt
```text

### 6.3 使用框架原生 SubAgent

如果不想自己实现，可以等待官方修复以下 Issue：
1. `subagent_orchestrator.py` 中 `skills` 字段未处理
2. `_build_handoff_toolset` 中 `builtin_func_list` 未合并
3. SubAgent 缺少搜索、知识库等辅助工具注入

---

## 七、关键源码文件索引

| 文件 | 作用 |
|------|------|
| [astr_main_agent.py](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py) | MainAgent 构建入口，工具/Skill 注入 |
| [astr_agent_tool_exec.py](../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py) | SubAgent 执行入口，`_build_handoff_toolset` |
| [subagent_orchestrator.py](../.venv/Lib/site-packages/astrbot/core/subagent_orchestrator.py) | SubAgent 注册，`Agent` 对象构建 |
| [func_tool_manager.py](../.venv/Lib/site-packages/astrbot/core/provider/func_tool_manager.py) | `FunctionToolManager`，`func_list` + `builtin_func_list` |
| [skill_manager.py](../.venv/Lib/site-packages/astrbot/core/skills/skill_manager.py) | `SkillManager`，Skill 管理 |
| [agent.py](../.venv/Lib/site-packages/astrbot/core/agent/agent.py) | `Agent` 数据类定义 |
| [handoff.py](../.venv/Lib/site-packages/astrbot/core/agent/handoff.py) | `HandoffTool` 定义 |

## 八、主要差异源码对比

### 工具集构建对比（2026-7-30）

| 对比项 | MainAgent 源码 | SubAgent 源码 | 差异说明 |
|--------|---------------|--------------|---------|
| 入口函数 | [astr_main_agent.py#L485-L580](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py#L485-L580) `_ensure_persona_and_skills` | [astr_agent_tool_exec.py#L244-L298](../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py#L244-L298) `_build_handoff_toolset` | MainAgent 从 Persona 解析开始，SubAgent 从 Agent 对象的 tools 字段开始 |
| 基础工具集来源 | `tmgr.get_full_tool_set()` (L566) → 仅 `func_list` | `tool_mgr.get_full_tool_set()` (L274) → 仅 `func_list` | 相同：都不包含 `builtin_func_list` |
| 运行时工具注入 | `_apply_sandbox_tools()` / `_apply_local_env_tools()` (L1570-L1573) → 注入全部 `builtin_func_list` | `_get_runtime_computer_tools()` (L259-L263) → 仅注入 8 件套 | **SubAgent 缺失：无搜索、无文件提取、无 Skill 辅助、无摘要等内置工具** |
| 搜索工具注入 | `_apply_web_search_tools()` (L1565) | ❌ 无 | SubAgent 无法联网搜索 |
| 知识库工具注入 | `_apply_kb()` (L1559) | ❌ 无 | SubAgent 无法查询知识库 |
| 文件提取工具 | `_apply_file_extract()` (L1543) | ❌ 无 | SubAgent 无法提取文件内容 |
| Handoff 工具 | `req.func_tool.add_tool(tool)` (L626) → 注入所有 `transfer_to_*` | 自动排除 Handoff 工具 (L269-L272) | SubAgent 排除 Handoff 防止死循环 |
| 插件工具过滤 | `_plugin_tool_fix()` (L1564) | ❌ 无 | SubAgent 无会话级插件过滤 |

### Skill 注入对比

| 对比项 | MainAgent 源码 | SubAgent 源码 | 差异说明 |
|--------|---------------|--------------|---------|
| Skill 列表获取 | `skill_manager.list_skills(active_only=True, runtime=runtime)` (L532) | ❌ 无 | SubAgent 不获取 Skill 列表 |
| Persona Skill 过滤 | `persona.get("skills")` (L543) → 按 Persona 配置过滤 | `subagent_orchestrator.py` L66-L87 未读取 `skills` 字段 | SubAgent 完全忽略 Persona 的 skills 配置 |
| Workspace Skills | `skill_manager.list_workspace_skills()` (L540) | ❌ 无 | SubAgent 无法使用工作区 Skill |
| Skill Prompt 注入 | `req.system_prompt += build_skills_prompt(skills)` (L555) | ❌ 无 | SubAgent 的 system_prompt 不含 Skill 信息 |

### Persona 应用对比

| 对比项 | MainAgent 源码 | SubAgent 源码 | 差异说明 |
|--------|---------------|--------------|---------|
| system_prompt 来源 | `persona["prompt"]` + 多段追加（Skill、router 等） | `persona_data.get("prompt")` 直接赋值 | SubAgent 仅使用 Persona prompt 原文 |
| begin_dialogs | `persona.get("_begin_dialogs_processed")` (L521) | `persona_data.get("_begin_dialogs_processed")` (subagent_orchestrator.py#L71) | 相同 |
| tools 过滤 | `persona.get("tools")` (L565) → 按列表过滤 | `persona_data.get("tools")` (subagent_orchestrator.py#L73) → 按列表过滤 | 相同 |
| skills 过滤 | `persona.get("skills")` (L543) → 按列表过滤 | ❌ 未读取 | SubAgent 完全忽略 skills 配置 |

### 执行方式对比

| 对比项 | MainAgent 源码 | SubAgent 源码 | 差异说明 |
|--------|---------------|--------------|---------|
| 执行引擎 | `AgentRunner()` (astr_main_agent.py#L1575) | `tool_loop_agent()` (astr_agent_tool_exec.py#L359) | MainAgent 用 AgentRunner，SubAgent 用 Provider 的 tool_loop |
| Provider 选择 | 全局默认 + fallback | 可通过 `provider_id` 配置专用 | SubAgent 支持 Provider 覆盖 |
| 最大步数 | `config.max_context_length` | `agent_max_step` (L357) | SubAgent 有独立的最大步数配置 |
| 流式响应 | `config.streaming_response` | `stream` (L358) | SubAgent 支持独立的流式配置 |
| Context 注入 | `AgentContextWrapper` | `contexts` 参数 | SubAgent 直接传 contexts |

### 数据结构对比

| 对比项 | MainAgent 相关类 | SubAgent 相关类 | 差异说明 |
|--------|-----------------|----------------|---------|
| Agent 定义 | `Agent` (agent.py#L10) | 同左 | 共用同一个 `Agent` 类 |
| Agent 字段 | `tools: list[str \| FunctionTool]` | 同左 | `tools` 字段只是名称列表，不包含实际工具对象 |
| Skill 支持 | `Agent` 无 `skills` 字段 | 同左 | **框架 Bug：`Agent` 类缺少 `skills` 字段** |
| 执行时工具 | 从 `func_list` + `builtin_func_list` 动态构建 | 从 `func_list` 动态构建 | SubAgent 少了 `builtin_func_list` |
| Skill 存储 | 注入 `system_prompt` 字符串 | ❌ 未处理 | Skill 是纯 prompt 注入，不需要额外字段 |


## 九、Agent 相关已知BUG或限制源码位置

| # | Bug/限制描述 | 影响范围 | 源码位置 | 根因分析 | 临时解决方案 |
|---|-------------|---------|---------|---------|-------------|
| 1 | **SubAgent 缺失系统内置工具** | SubAgent 无法使用摘要、文件读写、搜索等 25+ 内置工具 | [astr_agent_tool_exec.py#L267-L281](../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py#L267-L281) `_build_handoff_toolset` | 仅从 `func_list` 构建，未合并 `builtin_func_list`。而 MainAgent 通过 [astr_main_agent.py#L1570-L1573](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py#L1570-L1573) 单独注入内置工具 | 自定义 `call_sub_agent` 工具时手动补充 `builtin_func_list` 工具 |
| 2 | **SubAgent 完全看不到 Skill** | SubAgent system_prompt 中无任何 Skill 信息 | [subagent_orchestrator.py#L83-L87](../.venv/Lib/site-packages/astrbot/core/subagent_orchestrator.py#L83-L87) | 构建 `Agent` 对象时未读取 Persona 的 `skills` 字段；[agent.py#L10-L15](../.venv/Lib/site-packages/astrbot/core/agent/agent.py#L10-L15) `Agent` 类本身无 `skills` 属性 | 手动调用 `SkillManager.list_skills()` + `build_skills_prompt()` 注入到 system_prompt |
| 3 | **Persona Skill 配置对 SubAgent 无效** | WebUI 配置 Persona Skill 后 SubAgent 仍看不到 | [subagent_orchestrator.py#L66-L87](../.venv/Lib/site-packages/astrbot/core/subagent_orchestrator.py#L66-L87) | 第 73 行仅读取 `tools` 字段，未读取 `skills` 字段（第 73 行 `tools = persona_data.get("tools")` 之后缺少 `skills = persona_data.get("skills")` 的对应处理） | 在 plugin 层自行读取 Persona 的 skills 配置并注入 |
| 4 | **SubAgent 无网络搜索能力** | SubAgent 无法使用 Tavily/Brave/Exa 等搜索工具 | [astr_agent_tool_exec.py#L244-L298](../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py#L244-L298) | SubAgent 构建工具集时未调用 [astr_main_agent.py#L1565](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py#L1565) 的 `_apply_web_search_tools()` | 自定义工具时手动添加搜索工具到 toolset |
| 5 | **SubAgent 无知识库能力** | SubAgent 无法查询已配置的知识库 | [astr_agent_tool_exec.py#L359-L370](../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py#L359-L370) `_execute_handoff` | 执行路径未经过 [astr_main_agent.py#L1559](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py#L1559) 的 `_apply_kb()` | 在自定义 handler 中手动添加 KB 工具或直接调用 `retrieve_knowledge_base()` |
| 6 | **SubAgent 无文件提取能力** | SubAgent 无法从 URL 提取文件内容 | [astr_agent_tool_exec.py#L359-L370](../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py#L359-L370) | 执行路径未经过 [astr_main_agent.py#L1543-L1547](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py#L1543-L1547) 的 `_apply_file_extract()` | 暂无，需自行实现文件提取逻辑 |
| 7 | **SubAgent 无插件工具过滤** | SubAgent 可能使用到当前会话未启用的插件工具 | [astr_agent_tool_exec.py#L244-L298](../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py#L244-L298) | 未调用 [astr_main_agent.py#L1027-L1053](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py#L1027-L1053) 的 `_plugin_tool_fix()` | 自定义工具时自行实现插件级过滤 |
| 8 | **SubAgent 无法调用其他 SubAgent** | SubAgent 不能嵌套调用 `transfer_to_*` 工具 | [astr_agent_tool_exec.py#L269-L272](../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py#L269-L272) | `_build_handoff_toolset` 显式排除了所有 `HandoffTool`（防止死循环） | 通过 plugin 实现"SubAgent 路由"模式 |
| 9 | **SubAgent 无主动消息能力** | SubAgent 无法主动向用户发送消息 | [astr_agent_tool_exec.py#L359-L370](../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py#L359-L370) | 未经过 [astr_main_agent.py#L1584-L1591](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py#L1584-L1591) 的主动消息工具注入 | 暂无，需通过 MainAgent 间接发送 |
| 10 | **SubAgent 无 Skill 辅助工具** | SubAgent 无法使用 Skill Candidate 管理等工具 | [astr_agent_tool_exec.py#L244-L298](../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py#L244-L298) | `_build_handoff_toolset` 仅注入运行时 8 件套，不包含 Skill 相关内置工具 | 自定义工具时手动添加 Skill 辅助工具 |
| 11 | **Persona 工具列表过滤逻辑不一致** | Persona `tools=None` 时 MainAgent 用全量，SubAgent 也用全量但子集不同 | [astr_main_agent.py#L565-L579](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py#L565-L579) vs [astr_agent_tool_exec.py#L267-L281](../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py#L267-L281) | 两处都以 `get_full_tool_set()` 为基础，但 MainAgent 后续还有额外注入步骤，SubAgent 没有 | 无 |
| 12 | **SubAgent 无摘要压缩能力** | SubAgent 历史对话无自动压缩 | [astr_agent_tool_exec.py#L359-L370](../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py#L359-L370) | `tool_loop_agent` 未传入压缩相关参数；MainAgent 有 `llm_compress_instruction` 等配置 ([astr_main_agent.py#L1655-L1657](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py#L1655-L1657)) | 暂无，依赖 Provider 自身的上下文窗口 |
| 13 | **SubAgent 路由 Prompt 未注入** | SubAgent 看不到 `router_system_prompt` | [astr_main_agent.py#L635-L641](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py#L635-L641) | `router_system_prompt` 仅注入到 MainAgent 的 system_prompt，SubAgent 的 system_prompt 仅来自 Persona | 如需 SubAgent 感知路由信息，需在 Persona 中手动包含 |
| 14 | **`Agent` 类设计局限** | `Agent` 类缺少 `skills`、`metadata` 等字段 | [agent.py#L10-L15](../.venv/Lib/site-packages/astrbot/core/agent/agent.py#L10-L15) | 设计时未考虑 Skill 直接绑定到 Agent，Skill 仅作为 prompt 注入机制 | 可通过继承 `Agent` 添加自定义字段 |

## 十、AstrBot 构建 SubAgent 请求的源码

AstrBot 构建 SubAgent 请求涉及 3 个核心文件，按调用顺序：

### 1. SubAgent 注册（构建 `Agent` 对象）

../.venv/Lib/site-packages/astrbot/core/subagent_orchestrator.py#L29-L104 `reload_from_config`

```text
从配置读取 → 读取 Persona 数据 → 构建 Agent 对象 → 包装为 HandoffTool
```bash

### 2. MainAgent 注入 Handoff 工具

../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py#L620-L625

```python
for tool in so.handoffs:
    req.func_tool.add_tool(tool)   # 注入 transfer_to_* 工具
```bash

### 3. SubAgent 执行（构建工具集 + 发起请求）

../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py#L300-L370 `_execute_handoff`

```text
_build_handoff_toolset() 构建工具集 → 准备 begin_dialogs → 调用 tool_loop_agent()
```bash

其中 `_build_handoff_toolset` 在 [astr_agent_tool_exec.py#L244-L298](../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py#L244-L298)，是构建 SubAgent 工具集的核心方法。

---

## 十一、AstrBot 构建 MainAgent 请求的源码

MainAgent 不使用 Agent 类，MainAgent 的构建走的是完全不同的路径：

```text
用户消息 → Pipeline → InternalAgentSubStage → build_main_agent()
                                                  ↓
                                          MainAgentBuildResult
                                          ├── agent_runner: AgentRunner
                                          ├── provider_request: ProviderRequest
                                          └── provider: Provider
```bash
MainAgent 没有 Agent 实例，它使用的是：

- AgentRunner 执行器
- ProviderRequest 请求对象
- Provider 模型提供商

AstrBot 构建 MainAgent 请求涉及 4 个核心文件，按调用顺序：

### 1. Pipeline 触发构建

[internal.py#L231-L251](../.venv/Lib/site-packages/astrbot/core/pipeline/process_stage/method/agent_sub_stages/internal.py#L231-L251) `InternalAgentSubStage`

```python
build_result = await build_main_agent(event, plugin_context, config)
agent_runner = build_result.agent_runner
req = build_result.provider_request
```bash

### 2. MainAgent 构建（核心）

[astr_main_agent.py](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py) `build_main_agent` 函数

```text
解析 Persona → 注入 Skill → 注入工具 → 注入 Handoff → 配置 AgentRunner
```bash

详细步骤见第二章「二、MainAgent 调用逻辑」。

### 3. AgentRunner 配置与执行

[astr_main_agent.py#L1645-L1671](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py#L1645-L1671)

```python
agent_runner.reset(
    provider=provider,
    request=req,
    run_context=AgentContextWrapper(...),
    tool_executor=FunctionToolExecutor(),
    agent_hooks=MAIN_AGENT_HOOKS,   # ← 包含 on_agent_begin 等钩子
    ...
)
```text

### 4. AgentRunner.run() 执行

`AgentRunner.run()` 内部会触发：
- `on_agent_begin` 钩子 → 调用所有注册的 `@on_agent_begin` 事件
- `on_tool_start` / `on_tool_end` → 工具调用前后
- `on_agent_done` / `on_llm_response` → Agent 完成后

---

## 十二、Agent 和 Persona 的关系

```text
Persona (数据库)                    Agent (运行时)
├── persona_id                     ├── name
├── system_prompt  ──提取──→       ├── instructions
├── tools          ──提取──→       ├── tools
├── skills         (未处理)        │
├── begin_dialogs  ──提取──→       ├── begin_dialogs
└── ...                            └── run_hooks
```bash
一个 SubAgent 对应一个 Persona （通过 persona_id 关联）。但 Agent 本身不持有 Persona 引用，只保存 Persona 数据的"快照"。

### 数据流向图

```text
┌──────────────────┐     persona_id      ┌──────────────────┐
│  SubAgent 配置     │ ──────────────────→ │  PersonaManager  │
│  (config.yaml)    │                     │  (内存缓存)       │
└──────────────────┘                     └──────────────────┘
         │                                       │
         │ 读取 persona 数据                       │ 返回 Persona 数据
         ▼                                       ▼
┌──────────────────────────────────────────────────────────┐
│                    构建 Agent 对象                         │
│                                                            │
│  agent = Agent(                                            │
│      name       = config.name                             │
│      instructions = persona.prompt    ← 从 Persona 提取     │
│      tools      = persona.tools     ← 从 Persona 提取     │
│  )                                                         │
│  agent.begin_dialogs = persona.dialogs ← 从 Persona 提取   │
│                                                            │
│  ⚠️ 注意：skills 字段未被提取 ⚠️                              │
└──────────────────────────────────────────────────────────┘
         │
         │ Agent 对象被包装为 HandoffTool
         ▼
┌──────────────────┐
│  HandoffTool      │
│  (注册到 func_list)│
└──────────────────┘
         │
         │ 被 MainAgent 调用时，_execute_handoff 构建完整请求
         ▼
┌──────────────────────────────────────────────────────────┐
│  构建 SubAgent 的 LLM 请求                                  │
│                                                            │
│  system_prompt = agent.instructions  ← 只有 Persona prompt │
│  tools = _build_handoff_toolset()    ← 从 func_list + 运行时 │
│  contexts = agent.begin_dialogs     ← Persona 预设对话     │
│                                                            │
│  ⚠️ skills 没有被注入 ⚠️                                     │
└──────────────────────────────────────────────────────────┘
```bash

### Agent 类的数据结构

[agent.py#L10-L15](../.venv/Lib/site-packages/astrbot/core/agent/agent.py#L10-L15)

```python
@dataclass
class Agent(Generic[TContext]):
    name: str                                          # Agent 名称
    instructions: str | None = None                    # system prompt 文本
    tools: list[str | FunctionTool] | None = None      # 工具名称列表
    run_hooks: BaseAgentRunHooks[TContext] | None = None  # 运行时钩子
    begin_dialogs: list[Any] | None = None             # 预设对话
```text

**关键特点**：
- `Agent` 是一个**轻量级数据载体**，不是运行时执行单元
- 不持有 Persona 引用，只保存 Persona 数据的**快照**
- 没有 `skills` 字段（框架 Bug）
- 没有 `metadata`、`description` 等扩展字段

### 一个 SubAgent 对应一个 Persona

| 关系 | 说明 |
|------|------|
| 配置 → Agent | 每个 SubAgent 配置通过 `persona_id` 关联一个 Persona |
| Persona → Agent | Persona 数据在 Agent 创建时被**一次性快照化** |
| Agent ↔ Persona | Agent 创建后与 Persona **解耦**，Persona 修改需重建 Agent |

### MainAgent vs SubAgent 的 Persona 应用时机

| 维度 | MainAgent | SubAgent |
|------|-----------|----------|
| Persona 应用时机 | **每次请求前**动态解析 | **Agent 创建时**一次性固化 |
| Persona 可变性 | 每次请求可不同（支持会话级切换） | 创建后不可变 |
| Persona 切换 | 支持（基于会话配置） | 不支持 |
| 数据流向 | `PersonaManager` → `ProviderRequest` | `PersonaManager` → `Agent` 对象 → `ProviderRequest` |

---

## 十三、Persona 缓存机制

### 启动时加载

[core_lifecycle.py#L209](../.venv/Lib/site-packages/astrbot/core/core_lifecycle.py#L209) 创建 `PersonaManager` 实例：

```python
self.persona_mgr = PersonaManager(self.db, self.astrbot_config_mgr)
```json

[persona_mgr.py#L35-L38](../.venv/Lib/site-packages/astrbot/core/persona_mgr.py#L35-L38) 初始化缓存：

```python
async def initialize(self):
    self.personas = await self.get_all_personas()    # 数据库 → list[Persona]
    self.get_v3_persona_data()                         # 转换为 v3 格式
```bash

### 缓存结构

| 属性 | 类型 | 说明 |
|------|------|------|
| `personas` | `list[Persona]` | 原始数据库记录 |
| `personas_v3` | `list[Personality]` | v3 格式（TypedDict） |
| `persona_v3_config` | `list[dict]` | v3 配置字典 |
| `selected_default_persona` | `Persona` | 默认 Persona（旧格式） |
| `selected_default_persona_v3` | `Personality` | 默认 Persona（v3 格式） |

### Persona 数据模型

[po.py#L144-L177](../.venv/Lib/site-packages/astrbot/core/db/po.py#L144-L177)

```python
class Persona:
    persona_id: str              # 唯一标识（如 "default"）
    system_prompt: str           # 系统提示词
    begin_dialogs: list | None   # 预设对话（偶数条）
    tools: list | None           # 工具列表
                                 #   None  → 使用全部工具
                                 #   []     → 禁用全部工具
                                 #   [str]  → 白名单
    skills: list | None          # Skill 列表（同上规则）
    custom_error_message: str    # 自定义错误消息
    folder_id: str               # 文件夹 ID（用于分组）
    sort_order: int              # 排序顺序
```bash

### Persona 查询方式

[persona_mgr.py#L47-L61](../.venv/Lib/site-packages/astrbot/core/persona_mgr.py#L47-L61)

```python
def get_persona_v3_by_id(self, persona_id):
    if not persona_id:
        return None
    if persona_id == "default":
        return DEFAULT_PERSONALITY              # 内置默认 Persona
    return next(
        (p for p in self.personas_v3 if p["name"] == persona_id),
        None
    )
```text

查询优先级：`"default"` 关键字 → `personas_v3` 列表 → 返回 `None`

### Persona 热更新

当用户通过 WebUI 修改 Persona 时：
1. 数据库写入新数据
2. `PersonaManager.reload()` 重新加载
3. MainAgent 下次请求时使用最新 Persona
4. SubAgent 需要触发 `SubAgentOrchestrator.reload_from_config()` 才会更新

**这意味着修改 Persona 后，MainAgent 立即生效，SubAgent 可能需要重启或手动触发 reload。**

---

## 十四、SubAgentOrchestrator 类做了什么

```python
class SubAgentOrchestrator:
    """Loads subagent definitions from config and registers handoff tools.

    This is intentionally lightweight: it does not execute agents itself.
    Execution happens via HandoffTool in FunctionToolExecutor.
    """

    def __init__(
        self, tool_mgr: FunctionToolManager, persona_mgr: PersonaManager
    ) -> None:
        # 保存工具管理器和人格管理器的引用，后续 reload 完
        # handoff tool 需要注册到 tool_mgr，人格数据需要从 persona_mgr 查
        self._tool_mgr = tool_mgr
        self._persona_mgr = persona_mgr
        self.handoffs: list[HandoffTool] = []  # 当前所有已注册的 handoff tool

    async def reload_from_config(self, cfg: dict[str, Any]) -> None:
        from astrbot.core.astr_agent_context import AstrAgentContext

        # ── 1. 读取配置中的 agents 列表 ──
        agents = cfg.get("agents", [])
        if not isinstance(agents, list):
            logger.warning("subagent_orchestrator.agents must be a list")
            return

        # ── 2. 逐个解析每个 subagent 配置项 ──
        handoffs: list[HandoffTool] = []
        for item in agents:
            # 跳过非 dict 或禁用的
            if not isinstance(item, dict):
                continue
            if not item.get("enabled", True):
                continue

            # 名称不能为空
            name = str(item.get("name", "")).strip()
            if not name:
                continue

            # ── 3. 尝试关联 Persona ──
            # 如果配置了 persona_id，从 PersonaManager 取数据
            persona_id = item.get("persona_id")
            if persona_id is not None:
                persona_id = str(persona_id).strip() or None
            persona_data = self._persona_mgr.get_persona_v3_by_id(persona_id)
            if persona_id and persona_data is None:
                logger.warning(
                    "SubAgent persona %s not found, fallback to inline prompt.",
                    persona_id,
                )

            # ── 4. 提取各项配置（先取配置项的值） ──
            instructions = str(item.get("system_prompt", "")).strip()
            public_description = str(item.get("public_description", "")).strip()
            provider_id = item.get("provider_id")
            if provider_id is not None:
                provider_id = str(provider_id).strip() or None
            tools = item.get("tools", [])   # 先取配置项的 tools
            begin_dialogs = None

            # ── 5. 如果有关联 Persona，用 Persona 数据覆盖 ──
            if persona_data:
                prompt = str(persona_data.get("prompt", "")).strip()
                if prompt:
                    instructions = prompt          # system prompt 用 Persona 的
                begin_dialogs = copy.deepcopy(
                    persona_data.get("_begin_dialogs_processed")
                )
                tools = persona_data.get("tools")  # ⬅️ tools 用 Persona 的，覆盖步骤4
                if public_description == "" and prompt:
                    public_description = prompt[:120]  # 没写描述就用 prompt 前120字

            # ── 6. 规范化 tools 字段 ──
            # None  → 不限制，使用全部工具
            # []    → 禁用全部工具（空列表）
            # [str] → 白名单，只允许这些工具
            if tools is None:
                tools = None
            elif not isinstance(tools, list):
                tools = []
            else:
                tools = [str(t).strip() for t in tools if str(t).strip()]

            # ── 7. 构建 Agent 对象并包进 HandoffTool ──
            agent = Agent[AstrAgentContext](
                name=name,
                instructions=instructions,  # SubAgent 看到的人设提示词
                tools=tools,                # 工具白名单/全部/禁用
            )
            agent.begin_dialogs = begin_dialogs

            handoff = HandoffTool(
                agent=agent,
                # MainAgent 看到的工具描述（简短，用于路由决策）
                tool_description=public_description or None,
            )

            # 可选的专属 Provider 覆盖
            handoff.provider_id = provider_id

            handoffs.append(handoff)

        # ── 8. 记录日志 ──
        for handoff in handoffs:
            logger.info(f"Registered subagent handoff tool: {handoff.name}")

        # ── 9. 原子替换：新的 handoff 列表一次性生效 ──
        self.handoffs = handoffs
```text

---

### 总结

| 步骤 | 做什么 |
|------|--------|
| 1-2 | 读配置，遍历 enabled 的 agent 条目 |
| 3 | 查 Persona，有就取数据 |
| 4 | 提取内联配置（system_prompt、tools 等） |
| 5 | **Persona 覆盖**：Persona 数据会覆盖步骤4的 tools |
| 6 | 规范化 tools：None/白名单/空列表 |
| 7 | 组装 Agent → HandoffTool |
| 8-9 | 日志 + 原子替换 handoffs 列表 |

**这个类本身没问题**——它只是把 `tools` 字段存进 `Agent` 对象。真正的工具注入逻辑不在这里，而在下游 `HandoffTool` 被调用时、框架构建 SubAgent 的 LLM 请求那一步。那就是 #8121 想修的。

## 十五、AstrBot 是根据什么把 Persona 交给对应的 SubAgent 的？

通过**配置文件**中的 `persona_id` 字段匹配。

### 配置结构

在 AstrBot 配置文件中：

```yaml
subagent_orchestrator:
  main_enable: true
  agents:
    - name: weather          # SubAgent 名称
      persona_id: weather     # ← 关联的 Persona ID
      enabled: true
      tools: null             # null = 使用 Persona 的 tools
      public_description: "查询天气"
    - name: translator
      persona_id: translator  # ← 另一个 Persona
      enabled: true
```bash

### 匹配流程

```text
配置文件                          PersonaManager (内存)
┌──────────────────────┐        ┌──────────────────────┐
│ agents:               │        │ personas_v3:         │
│   - name: weather     │        │   - name: weather    │
│     persona_id: weather│ ─────→ │     prompt: "..."    │
│                       │  查询   │     tools: [...]     │
└──────────────────────┘        │     skills: [...]    │
                                └──────────────────────┘
```bash

### 代码实现

[subagent_orchestrator.py#L48-L51](../.venv/Lib/site-packages/astrbot/core/subagent_orchestrator.py#L48-L51)

```python
# 从配置读取 persona_id
persona_id = item.get("persona_id")
if persona_id is not None:
    persona_id = str(persona_id).strip() or None

# 查询 PersonaManager 中对应的 Persona
persona_data = self._persona_mgr.get_persona_v3_by_id(persona_id)
```json

[persona_mgr.py#L47-L61](../.venv/Lib/site-packages/astrbot/core/persona_mgr.py#L47-L61)

```python
def get_persona_v3_by_id(self, persona_id):
    if not persona_id:
        return None
    if persona_id == "default":
        return DEFAULT_PERSONALITY
    # 按 name 字段匹配
    return next(
        (p for p in self.personas_v3 if p["name"] == persona_id),
        None
    )
```bash

### 优先级

| `persona_id` 值 | 行为 |
|----------------|------|
| `None` 或空字符串 | 不关联 Persona，使用配置中的 `system_prompt` 和 `tools` |
| `"default"` | 使用内置默认 Persona |
| 具体名称（如 `"weather"`） | 从 `personas_v3` 列表中按 `name` 查找 |
| 找不到匹配 | 警告日志，回退到配置中的 `system_prompt` |

### 数据覆盖规则

[subagent_orchestrator.py#L66-L75](../.venv/Lib/site-packages/astrbot/core/subagent_orchestrator.py#L66-L75)

```python
if persona_data:
    # Persona 数据覆盖配置中的对应字段
    instructions = persona_data.get("prompt")      # 覆盖 system_prompt
    tools = persona_data.get("tools")              # 覆盖 tools
    begin_dialogs = persona_data.get("_begin_dialogs_processed")  # 新增
```bash

**简单说：配置中的 `persona_id` 是"外键"，指向 Persona 表中的一条记录。**

### 细节补充

1. **`personas_v3` 是列表不是字典**，所以 `get_persona_v3_by_id` 每次都 `next()` 线性扫描，Persona 多了会慢。

2. **`tools` 字段是 `persona_data.get("tools")` 原样返回的**，如果 Persona 里 `tools` 是 `None`（表示"不限制，用全部"），那 SubAgent 拿到也是 `None`。但框架在 handoff 执行时没有把 MainAgent 的全局工具全量透传——这就是 SubAgent 拿不到 Skill 的原因。Persona 的 `tools` 字段只是一个"白名单标记"，真正注入工具的逻辑在 handoff 执行层，而那层漏了。

3. 简单说完整链条：我们编写的所有人格设定，都会在AstrBot初始化的时候缓存进 personas_v3 这个列表，【get_persona_v3_by_id】方法返回一个persona_data，然后AstrBot根据这个persona_data 动态创建 SubAgent ，构建 Handoff 方法缓存进handoffs这个列表里。流程图：
```text
AstrBot 启动
  ↓
PersonaManager.__init__ → 从 SQLite 加载所有人格 → 缓存进 personas_v3（列表）
  ↓
SubAgentOrchestrator.reload_from_config()
  ↓
遍历配置中每个 agent：
  ├─ persona_id → get_persona_v3_by_id() → 从 personas_v3 线性扫描匹配
  ├─ 有匹配 → persona_data 覆盖 instructions / tools / begin_dialogs
  ├─ 无匹配 → 用配置里内联的 system_prompt 和 tools
  └─ 组装 Agent → 包进 HandoffTool → 加入 self.handoffs
```text
几个关键点：
- `reload_from_config` **不是只在启动时调一次**，配置变更时也会触发，每次都是**原子替换** `self.handoffs`（整个列表一把换掉，不是追加）。
- Persona 的 `tools` 此时只是一个**标签**（`None` / `[]` / `["tool_a"]`），存进 `Agent.tools` 后就完事了。真正按这个标签筛选并注入工具的代码在 handoff 执行层——那层目前漏掉了全局 Skill 工具的透传。
- `personas_v3` 是列表不是字典，`get_persona_v3_by_id` 每次 O(n) 扫描，Persona 多了性能会受影响，不过一般没那么多就是了。       
综上所述，无法通过handoff溯源到它的人格设定，只能通过配置文件中的 `persona_id` 来关联。
可以看一下 `HandoffTool` 和 `Agent` 分别存了什么：
**Agent**：`name`、`instructions`、`tools`、`run_hooks`、`begin_dialogs`
**HandoffTool**：`agent`、`tool_description`、`provider_id`
没有一个字段存 `persona_id`。`reload_from_config` 里 `persona_id` 只是个**临时变量**——查完 `personas_v3` 拿到数据、覆盖到 `instructions`/`tools`/`begin_dialogs` 之后，`persona_id` 就丢掉了。

所以 `handoffs` 列表里的每个 `HandoffTool`，你只能看到它「最终的」人设文本和工具配置，但无法反向追溯它是从哪个 Persona 来的。类似于只存了渲染后的 HTML，扔掉了原始的模板引用。

从 AstrBot配置文件的示例：
```yaml
subagent_orchestrator:
  main_enable: true
  agents:
    - name: weather          # SubAgent 名称
      persona_id: weather     # ← 关联的 Persona ID
      enabled: true
      tools: null             # null = 使用 Persona 的 tools
      public_description: "查询天气"
    - name: translator
      persona_id: translator  # ← 另一个 Persona
      enabled: true
```text
可以看出，agents 里面有很多项，每一项都是你在web UI 里面创建的SubAgent，每个 SubAgent 对应一个 persona_id。
所以其实AstrBot是通过agents里面的 name 来判断是哪个 SubAgent，通过persona_id来判断这个SubAgent绑定的是哪个人格设定。
然后根据 persona_id 用【get_persona_v3_by_id】获取到对应的persona_data。
然后，AstrBot根据这个persona_data动态创建名为 name 的Agent对象，并进一步处理为 handoff 实例对象并缓存进 handoffs 列表
一张图总结：
```text
agents:
  - name: test_sub_agent   ← SubAgent 标识
    persona_id: test        ← 人格设定标识
        │
        ▼
get_persona_v3_by_id("test")
        │
        ▼
persona_data { prompt, tools, begin_dialogs }
        │
        ▼
Agent(name="test_sub_agent", instructions=prompt, tools=tools)
        │
        ▼
HandoffTool(agent, tool_description, provider_id)
        │
        ▼
self.handoffs = [HandoffTool, ...]
```text
`name` 是 SubAgent 的"身份证"，`persona_id` 是它绑定的"人设卡"。两条线独立，通过配置文件的 `persona_id` 字段关联起来。
注意：**把 Agent 包成 HandoffTool 这一步其实没问题——它就是把 `Agent` 对象原样存进去了：**

```python
handoff = HandoffTool(
    agent=agent,                        # Agent 整个塞进去
    tool_description=public_description or None,
)
```
这一步没做任何过滤或加工。

当 MainAgent 调用 `transfer_to_test_sub_agent`，`HandoffTool.call()` 被执行时，框架构建 SubAgent 的 LLM 请求，这时候它要根据 `Agent.tools` 来决定给 SubAgent 注入哪些工具。`tools=None` 按设计应该等于「全部工具」，但实际注入时没有把全局 Skill 工具（`astrbot_run_browser_skill` 等）带过去，只给了沙箱基础 8 件套。

所以不是「包成 HandoffTool 时做了不符合预期的行为」，而是「HandoffTool 被执行时，工具注入那一步漏了全局 Skill」。

简单说就是：AstrBot根据这个persona_data动态创建名为 name 的Agent对象，并进一步处理为 handoff 实例对象，到这里都是根据人格设定文件完整复制。而我遇到的BUG或者说不符合我个人预期的问题，本质上是HandoffTool 被执行时，AstrBot对Handoff进行了过滤和加工。主要是注入工具那一步。

配置 + Persona → Agent(name, instructions, tools=None)  ✅ 没问题，完整复制
Agent → HandoffTool(agent)                               ✅ 没问题，原样封装
HandoffTool.call() → 构建 SubAgent LLM 请求 → 注入工具    ❌ 这里过滤掉了全局 Skill



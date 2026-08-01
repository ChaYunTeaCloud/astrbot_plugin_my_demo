# SubAgent 调用流程

> MainAgent 的调用流程，请参见 [MainAgent 调用流程](./MainAgent%20调用流程.md)

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

## 二、SubAgent 调用逻辑

### 2.1 入口

MainAgent 调用 `transfer_to_{agent_name}` 工具后，由 [astr_agent_tool_exec.py](../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py) 的 `_execute_handoff` 方法处理。

### 2.2 工具集构建流程

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
```

**注意**：`Agent` 类没有 `skills` 字段，也没有从 Persona 中读取 `skills`。

#### Step 2: 构建 SubAgent 工具集

```python
# astr_agent_tool_exec.py L329
toolset = cls._build_handoff_toolset(run_context, tool.agent.tools)
```

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
```

#### Step 3: 注入运行时计算工具

```python
# L259-L263
runtime_computer_tools = cls._get_runtime_computer_tools(
    runtime, tool_mgr, ...
)
```

这一步**只添加运行时相关的基础工具**（Local 或 Sandbox 8 件套），不包含其他系统内置工具。

### 2.3 SubAgent 工具集 vs MainAgent 工具集

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

### 2.4 SubAgent 执行方式

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
```

调用 `tool_loop_agent` 方法（而非 `AgentRunner`），同样支持多轮 tool call。

---

## 三、核心差异总结

### 3.1 工具注入差异

| 对比维度 | MainAgent | SubAgent | 原因 |
|---------|-----------|----------|------|
| 工具集来源 | `func_list` + `builtin_func_list` | 仅 `func_list` | SubAgent 的 `_build_handoff_toolset` 没有合并 `builtin_func_list` |
| 系统内置工具数量 | 约 25 个 | 仅 8 个（运行时） | MainAgent 有 Step 9 专门注入 |
| 网络搜索工具 | ✅ | ❌ | MainAgent 有 Step 8 专门注入 |
| Skill 辅助工具 | ✅ | ❌ | MainAgent 有 Step 10 专门注入 |

### 3.2 Skill 注入差异

| 对比维度 | MainAgent | SubAgent | 原因 |
|---------|-----------|----------|------|
| Skill 注入方式 | 追加到 `system_prompt` | ❌ 未注入 | SubAgent 的 system_prompt 仅来自 Persona 的 `prompt` |
| Persona skills 过滤 | ✅ 读取 `persona["skills"]` 过滤 | ❌ `subagent_orchestrator.py` 未读取 | 构建 Agent 对象时忽略了 Persona 的 `skills` 字段 |
| Workspace Skills | ✅ 注入 | ❌ 未注入 | MainAgent 有额外的 workspace skill 收集逻辑 |

### 3.3 Persona 应用差异

| 对比维度 | MainAgent | SubAgent |
|---------|-----------|----------|
| system_prompt 来源 | Persona prompt + 多段追加（Skill、router_prompt 等） | 仅 Persona prompt 或配置的 system_prompt |
| begin_dialogs | ✅ | ✅ |
| Persona skills 过滤 | ✅ | ❌ |
| Persona tools 过滤 | ✅ | ✅（从 Persona 读取 tools 字段） |

### 3.4 Provider 差异

| 对比维度 | MainAgent | SubAgent |
|---------|-----------|----------|
| Provider 选择 | 全局默认 Provider | 可通过 `provider_id` 配置 SubAgent 专用 Provider |
| 模型选择 | 使用配置的模型 | 跟随 Provider 的模型设置 |

---

## 四、Bug 与已知问题

### 4.1 SubAgent 缺失系统内置工具

**问题**：`_build_handoff_toolset` 只从 `func_list` 构建工具集，不包含 `builtin_func_list` 中的工具。

**影响**：SubAgent 无法使用 `astrbot_summary_tool`、`astrbot_file_read_tool` 等内置工具。

**解决方案**：在 `_build_handoff_toolset` 中补充 `builtin_func_list` 的非运行时工具。

### 4.2 SubAgent 缺失 Skill 注入

**问题**：`subagent_orchestrator.py` 构建 `Agent` 对象时，没有读取 Persona 的 `skills` 字段。

**影响**：SubAgent 即使配置了 Persona Skill，也看不到任何 Skill。

**解决方案**：需要框架层面修复 `subagent_orchestrator.py` 以处理 `skills` 字段，并在 `_execute_handoff` 中将 Skill 注入 system_prompt。

### 4.3 SubAgent 缺失搜索等辅助工具

**问题**：SubAgent 没有经过 `_apply_web_search_tools`、`_apply_kb`、`_apply_file_extract` 等步骤。

**影响**：SubAgent 无法进行联网搜索、知识库查询、文件提取等操作。

**解决方案**：需要框架层面在 `_build_handoff_toolset` 或 `_execute_handoff` 中补充这些工具。

---

## 五、Plugin 开发者的应对策略

### 5.1 让 SubAgent 看到更多工具

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
```

### 5.2 让 SubAgent 看到 Skill

```python
from astrbot.core.skills import SkillManager, build_skills_prompt

skill_manager = SkillManager()
skills = skill_manager.list_skills(active_only=True, runtime="local")
skill_prompt = build_skills_prompt(skills)
system_prompt = agent.instructions + "\n" + skill_prompt
```

### 5.3 使用框架原生 SubAgent

如果不想自己实现，可以等待官方修复以下 Issue：
1. `subagent_orchestrator.py` 中 `skills` 字段未处理
2. `_build_handoff_toolset` 中 `builtin_func_list` 未合并
3. SubAgent 缺少搜索、知识库等辅助工具注入

---

## 六、关键源码文件索引

| 文件 | 作用 |
|------|------|
| [astr_main_agent.py](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py) | MainAgent 构建入口，工具/Skill 注入 |
| [astr_agent_tool_exec.py](../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py) | SubAgent 执行入口，`_build_handoff_toolset` |
| [subagent_orchestrator.py](../.venv/Lib/site-packages/astrbot/core/subagent_orchestrator.py) | SubAgent 注册，`Agent` 对象构建 |
| [func_tool_manager.py](../.venv/Lib/site-packages/astrbot/core/provider/func_tool_manager.py) | `FunctionToolManager`，`func_list` + `builtin_func_list` |
| [skill_manager.py](../.venv/Lib/site-packages/astrbot/core/skills/skill_manager.py) | `SkillManager`，Skill 管理 |
| [agent.py](../.venv/Lib/site-packages/astrbot/core/agent/agent.py) | `Agent` 数据类定义 |
| [handoff.py](../.venv/Lib/site-packages/astrbot/core/agent/handoff.py) | `HandoffTool` 定义 |

## 七、主要差异源码对比

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


## 八、Agent 相关已知BUG或限制源码位置

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

## 九、AstrBot 构建 SubAgent 请求的源码

AstrBot 构建 SubAgent 请求涉及 3 个核心文件，按调用顺序：

### 1. SubAgent 注册（构建 `Agent` 对象）

../.venv/Lib/site-packages/astrbot/core/subagent_orchestrator.py#L29-L104 `reload_from_config`

```text
从配置读取 → 读取 Persona 数据 → 构建 Agent 对象 → 包装为 HandoffTool
```

### 2. MainAgent 注入 Handoff 工具

../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py#L620-L625

```python
for tool in so.handoffs:
    req.func_tool.add_tool(tool)   # 注入 transfer_to_* 工具
```

### 3. SubAgent 执行（构建工具集 + 发起请求）

../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py#L300-L370 `_execute_handoff`

```text
_build_handoff_toolset() 构建工具集 → 准备 begin_dialogs → 调用 tool_loop_agent()
```

其中 `_build_handoff_toolset` 在 [astr_agent_tool_exec.py#L244-L298](../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py#L244-L298)，是构建 SubAgent 工具集的核心方法。

# AstrBot Skill 机制

## 一、核心概念

### 什么是 Skill

Skill 是 AstrBot 提供的**可复用指令包**，本质是基于 Markdown 文档（`SKILL.md`）的知识/流程描述。它不是可执行的工具函数，而是一段**注入到 LLM system prompt 中的提示词**，告诉 LLM 在什么场景下应该遵循什么流程。



### Skill vs Tool

| 维度 | Tool | Skill |
|------|------|-------|
| 本质 | 可执行函数 | Markdown 提示词文档 |
| 作用 | LLM 调用后执行代码 | 注入到 system prompt，指导 LLM 行为 |
| 注册 | `@llm_tool` 或 `@builtin_tool` | 放在 `skills/` 目录或插件 `skills/` 目录 |
| 存储 | `FunctionToolManager` | `SkillManager` + 文件系统 |
| LLM 感知 | 作为 tool_call 调用 | 作为 prompt 上下文阅读 |
| 生命周期 | 随进程重启 | 持久化在磁盘 |

### Skill 的标准格式

Skill 以 `SKILL.md` 文件存在，遵循 OpenAI Codex CLI / Anthropic Claude Skills 规范：

```markdown
---
name: my-skill
description: What this skill does and when to use it.
---

# My Skill

## When to use
- When the user asks about X

## Instructions
1. First do Y
2. Then do Z

## Files
- `scripts/setup.sh` - Run this before starting
- `assets/template.txt` - Use this template
```

YAML frontmatter 中的 `name` 和 `description` 会被提取出来，注入到 system prompt 中作为 Skill 目录。LLM 根据描述判断是否需要使用该 Skill。

---

## 二、Skill 的来源与生命周期

### Skill 的五种来源

| source_type | source_label | 说明 | 存储位置 |
|-------------|-------------|------|---------|
| `local_only` | `local` | 用户通过 WebUI 上传的 Skill | `data/skills/<name>/SKILL.md` |
| `both` | `synced` | 本地存在 + 已同步到 Sandbox | 本地文件 + Sandbox 缓存 |
| `plugin` | 插件名 | 插件自带的 Skill | `plugins/<name>/skills/<name>/SKILL.md` |
| `sandbox_only` | `sandbox_preset` | 只存在于 Sandbox 的预设 Skill | `sandbox_skills_cache.json` |
| `workspace` | `workspace` | 会话级工作区中的 Skill | `<workspace>/skills/<name>/SKILL.md` |

### Skill 的发现流程

SkillManager 在 [skill_manager.py#L493-648](../.venv/Lib/site-packages/astrbot/core/skills/skill_manager.py#L493-L648) 中按以下顺序发现 Skill：

```text
1. 扫描 skills/ 目录下的所有子目录
   → 读取 SKILL.md 的 frontmatter 获取 name 和 description
   → 检查 sandbox_skills_cache.json 中是否存在对应记录
   → 如果存在：source_type=both, source_label=synced
   → 如果不存在：source_type=local_only, source_label=local

2. 扫描 plugins/ 下各插件的 skills/ 子目录
   → source_type=plugin, source_label=插件名

3. 如果 runtime=local，扫描工作区 skills/ 目录
   → source_type=workspace, source_label=workspace

4. 如果 runtime=sandbox，检查 sandbox_skills_cache.json
   → 补充 sandbox_only 类型的 Skill
```

### Sandbox 同步机制

当 Sandbox 运行时启动后，会扫描自身的 Skill 目录，通过 `set_sandbox_skills_cache()` 将 Skill 元数据写入 `sandbox_skills_cache.json`。之后本地 Skill 就会被标记为 `source_type=both`（`source_label=synced`），同时 Sandbox 中独有的 Skill 会被标记为 `source_type=sandbox_only`。

```python
# 来自 computer_client.py#L444
SkillManager().set_sandbox_skills_cache(skills)
```

缓存文件路径：`data/sandbox_skills_cache.json`，结构：

```json
{
    "version": 1,
    "skills": [
        {"name": "my-skill", "description": "...", "path": "/workspace/skills/my-skill/SKILL.md"}
    ],
    "updated_at": "2026-07-30T12:00:00+00:00"
}
```

### Skill 的启用/禁用

通过 `skills.json` 配置文件管理（[skill_manager.py#L418-430](../.venv/Lib/site-packages/astrbot/core/skills/skill_manager.py#L418-L430)）：

```json
{
    "skills": {
        "my-skill": {"active": true},
        "deprecated-skill": {"active": false}
    }
}
```

- `local_only` 和 `plugin` 类型的 Skill 可以通过 WebUI 或代码 `set_skill_active(name, active)` 开关
- `sandbox_only` 类型的 Skill 不可从本地禁用（`PermissionError`）
- `plugin` 类型的 Skill 不可从本地删除（`PermissionError`）

---

## 三、Skill 如何注入到 LLM

### 注入时机

Skill 在每次 LLM 请求的 system prompt 构建阶段注入（[astr_main_agent.py#L499-L575](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py#L499-L575)）：

```python
# 1. 获取当前运行时的 Skill 列表
runtime = cfg.get("computer_use_runtime", "local")
skill_manager = SkillManager()
skills = skill_manager.list_skills(active_only=True, runtime=runtime)

# 2. 过滤 Persona 指定的 Skill
if persona and persona.get("skills") is not None:
    if not persona["skills"]:
        skills = []
    else:
        allowed = set(persona["skills"])
        skills = [s for s in skills if s.name in allowed]

# 3. 注入到 system prompt
if skills:
    req.system_prompt += f"\n{build_skills_prompt(skills)}\n"
```

### build_skills_prompt 生成的内容

[build_skills_prompt()](../.venv/Lib/site-packages/astrbot/core/skills/skill_manager.py#L208-L283) 会生成以下格式的 prompt：

```text
## Skills

You have specialized skills — reusable instruction bundles stored in `SKILL.md` files...

### Available skills

- **my-skill**: What this skill does and when to use it.
  File: `/path/to/skills/my-skill/SKILL.md`

### Skill rules

1. **Discovery** — The list above is the complete skill inventory...
2. **When to trigger** — Use a skill if the user names it explicitly...
3. **Mandatory grounding** — Before executing any skill you MUST first read its `SKILL.md`...
4. **Progressive disclosure** — Load only what is directly referenced from `SKILL.md`...
5. **Coordination** — When multiple skills apply, pick the minimal set needed...
6. **Context hygiene** — Avoid deep reference chasing...
7. **Failure handling** — If a skill cannot be applied, state the issue clearly...
```

### 渐进式披露（Progressive Disclosure）

Skill 的核心设计理念：**只在 system prompt 中显示 Skill 的名称和描述**，不嵌入完整内容。LLM 需要在决定使用某个 Skill 后，通过 shell 命令读取完整的 `SKILL.md`：

```bash
cat /path/to/skills/my-skill/SKILL.md
```

这种设计的好处：
- 节省 token（不把所有 Skill 内容一次性塞入 prompt）
- LLM 有更明确的触发时机
- 支持大型 Skill（可以引用脚本、模板等资产）

---

## 四、SkillManager 核心 API

`SkillManager`（[skill_manager.py#L287](../.venv/Lib/site-packages/astrbot/core/skills/skill_manager.py#L287)）是 Skill 的管理中心。

### 构造参数

```python
SkillManager(
    skills_root: str | None = None,   # Skill 文件根目录，默认 data/skills
    plugins_root: str | None = None,   # 插件根目录，默认 data/plugins
)
```

### 核心方法

| 方法 | 签名 | 说明 |
|------|------|------|
| `list_skills` | `(active_only=True, runtime="local", show_sandbox_path=True) -> list[SkillInfo]` | 列出所有 Skill |
| `list_workspace_skills` | `(workspace_root) -> list[SkillInfo]` | 列出工作区中的 Skill |
| `set_skill_active` | `(name, active) -> None` | 启用/禁用 Skill |
| `delete_skill` | `(name) -> None` | 删除 Skill |
| `install_skill_from_zip` | `(zip_path, overwrite=True, skill_name_hint=None) -> str` | 从 zip 安装 Skill |
| `set_sandbox_skills_cache` | `(skills: list[dict]) -> None` | 写入 Sandbox Skill 缓存 |
| `get_sandbox_skills_cache_status` | `() -> dict` | 获取 Sandbox 缓存状态 |
| `is_sandbox_only_skill` | `(name) -> bool` | 判断是否为 Sandbox 独有 Skill |
| `is_plugin_skill` | `(name) -> bool` | 判断是否为插件 Skill |

### SkillInfo 数据类

```python
@dataclass
class SkillInfo:
    name: str                    # Skill 名称
    description: str             # Skill 描述
    path: str                    # SKILL.md 路径
    active: bool                 # 是否启用
    source_type: str = "local_only"  # local_only / both / plugin / sandbox_only / workspace
    source_label: str = "local"      # local / synced / 插件名 / sandbox_preset / workspace
    local_exists: bool = True    # 本地是否存在
    sandbox_exists: bool = False # Sandbox 中是否存在
    plugin_name: str = ""        # 所属插件名
    readonly: bool = False        # 是否只读
```

### 使用示例

```python
from astrbot.core.skills import SkillManager, build_skills_prompt

# 获取 SkillManager
sm = SkillManager()

# 列出所有已启用的 Skill
skills = sm.list_skills(active_only=True, runtime="local")
for s in skills:
    print(f"{s.name}: {s.description} (source={s.source_type})")

# 启用/禁用 Skill
sm.set_skill_active("my-skill", False)

# 从 zip 安装 Skill
sm.install_skill_from_zip("/path/to/skill.zip")

# 生成 Skill prompt
prompt = build_skills_prompt(skills)
```

### 请求级 Workspace Skill

`list_workspace_skills(workspace_root)` 方法（`../.venv/Lib/site-packages/astrbot/core/skills/skill_manager.py#L342`）支持在请求级别注入 workspace skill，优先级最高。这允许插件为特定会话动态提供 Skill，而不影响全局配置。

### 插件 Skill 判断

`is_plugin_skill(name: str) -> bool` 方法判断指定 Skill 是否来自插件捆绑的 `skills/` 目录。插件提供的 Skill 是只读的，不能通过 WebUI 删除。

---

## 五、Neo：Skill 相关工具

AstrBot 提供了一组操作 Skill 的内置工具（Neo Skill 工具），定义在 [neo_skills.py](../.venv/Lib/site-packages/astrbot/core/tools/computer_tools/shipyard_neo/neo_skills.py) 中，它们都是 `NeoSkillToolBase` 的子类。

### 工具列表

| 工具 | 说明 |
|------|------|
| `GetExecutionHistoryTool` | 获取 Skill 执行历史 |
| `AnnotateExecutionTool` | 标注执行结果 |
| `CreateSkillPayloadTool` | 创建 Skill payload（Sandbox 中直接创建 Skill） |
| `GetSkillPayloadTool` | 获取 Skill payload |
| `CreateSkillCandidateTool` | 创建 Skill 候选版本 |
| `ListSkillCandidatesTool` | 列出 Skill 候选版本 |
| `EvaluateSkillCandidateTool` | 评估 Skill 候选版本 |
| `PromoteSkillCandidateTool` | 提升候选版本为正式版本 |
| `ListSkillReleasesTool` | 列出 Skill 发布版本 |
| `RollbackSkillReleaseTool` | 回滚 Skill 版本 |
| `SyncSkillReleaseTool` | 同步 Skill 到 Sandbox |

这些工具的存在使得 LLM 可以**在对话中直接创建和管理 Skill**，无需用户通过 WebUI 操作。例如，用户可以让 LLM "创建一个新 Skill 来处理数据格式化"，LLM 会调用 `CreateSkillPayloadTool` 在 Sandbox 中直接创建 Skill。

### Neo Skill 工具的注册

这些工具通过 `@builtin_tool(config=_SHIPYARD_NEO_TOOL_CONFIG)` 装饰器注册，属于内置工具（`builtin_func_list`），需要通过 `tool_mgr.get_builtin_tool()` 获取。

---

## 六、Skill 配置过滤

### Persona 级别的 Skill 过滤

在 [astr_main_agent.py#L557-L567](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py#L557-L567) 中，如果 Persona 配置了 `skills` 字段，会按列表过滤 Skill：

```python
if persona and persona.get("skills") is not None:
    if not persona["skills"]:
        skills = []  # 空列表 = 禁用所有 Skill
    else:
        allowed = set(persona["skills"])
        skills = [s for s in skills if s.name in allowed]
```

### 按 Provider 配置过滤

`_filter_skills_for_current_config()` 会根据当前会话使用的 Provider 配置过滤 Skill，确保只注入兼容的 Skill。

---

## 七、与 SubAgent 的关系

### SubAgent 根本不支持 Skill

SubAgent 不仅默认看不到 Skill，即使通过 Persona 配置了 skills 也**完全不生效**。原因是框架层面的设计：

1. **注入逻辑缺失**：Skill 注入逻辑（`build_skills_prompt`）仅在 MainAgent 的 `_ensure_persona_and_skills()`（[astr_main_agent.py#L499-L575](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py#L499-L575)）中执行，SubAgent 的执行路径（[astr_agent_tool_exec.py#L363-L374](../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py#L363-L374)）中没有任何 Skill 注入代码
2. **搜索验证**：在 `subagent_orchestrator.py` 中搜索 `skill` 关键词为零匹配——SubAgent 创建时不读取 Persona 的 `skills` 字段
3. **`tool_loop_agent()` 不接收 skills 参数**：SubAgent 执行时调用的 `tool_loop_agent()` 方法签名中没有 skills 参数

**结论**：Persona 的 `skills` 字段对 SubAgent 完全无效，这不是 bug，而是框架尚未实现的功能。

### 让 SubAgent 也能使用 Skill

如果需要让 SubAgent 也能使用 Skill，有两种方式：

1. **在 SubAgent 的 `instructions` 中手动注入 Skill prompt**：
```python
skills = skill_manager.list_skills(active_only=True)
skill_prompt = build_skills_prompt(skills)
agent.instructions += f"\n{skill_prompt}"
```

2. **在自定义 `call_sub_agent` 工具的 handler 中注入**：
```python
async def _call_sub_agent_handler(self, event, agent_name, input):
    # ...
    skills = SkillManager().list_skills(active_only=True)
    skill_prompt = build_skills_prompt(skills)
    
    llm_resp = await self.context.tool_loop_agent(
        system_prompt=agent.instructions + "\n" + skill_prompt,
        # ...
    )
```

---

## 八、存储路径

| 内容 | 路径 |
|------|------|
| 本地 Skill | `data/skills/<name>/SKILL.md` |
| Skill 配置 | `data/skills.json` |
| Sandbox Skill 缓存 | `data/sandbox_skills_cache.json` |
| 插件 Skill | `plugins/<plugin_name>/skills/<name>/SKILL.md` |
| 工作区 Skill | `<workspace>/skills/<name>/SKILL.md` |

## 九、相关源码路径

| 文件 | 说明 |
|------|------|
| [skill_manager.py](../.venv/Lib/site-packages/astrbot/core/skills/skill_manager.py) | Skill 管理核心类 |
| [neo_skill_sync.py](../.venv/Lib/site-packages/astrbot/core/skills/neo_skill_sync.py) | Neo Skill 同步管理器 |
| [neo_skills.py](../.venv/Lib/site-packages/astrbot/core/tools/computer_tools/shipyard_neo/neo_skills.py) | Skill 操作工具（Neo） |
| [astr_main_agent.py#L499-L575](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py#L499-L575) | Skill 注入主 Agent 的逻辑 |
| [computer_client.py#L108-114](../.venv/Lib/site-packages/astrbot/core/computer/computer_client.py#L108-L114) | Sandbox Skill 扫描与缓存 |

## 十、Skill与Tool的关系

首先，Skill 不是用 `FunctionTool` 机制实现的

Skill 和 Tool 是**两套独立的系统**。Skill 是基于 **Markdown 文档**（`SKILL.md`）的知识/指令包，不是可执行的工具函数。

### Skill 的本质

Skill 是一段**给 LLM 的提示词**，告诉 LLM 在什么场景下应该遵循什么流程。它的核心是 `SKILL.md` 文件，结构类似：

```markdown
---
name: my-skill
description: What this skill does and when to use it.
---

# My Skill

## When to use
- When the user asks about X

## Instructions
1. First do Y
2. Then do Z
```

LLM 不需要调用 Skill 作为工具——Skill 的内容会被**注入到 system prompt** 中，LLM 直接阅读并遵循。

### Skill 的来源与生命周期

根据 [skill_manager.py#L493-640](../.venv/Lib/site-packages/astrbot/core/skills/skill_manager.py#L493-L640)，Skill 有五种来源：

| source_type | source_label | 说明 |
|-------------|-------------|------|
| `local_only` | `local` | 用户通过 WebUI 上传的 Skill，只存在于本地 |
| `both` | `synced` | 本地存在 + 已同步到 Sandbox |
| `plugin` | 插件名 | 插件自带的 Skill（`plugins/<name>/skills/` 目录下） |
| `sandbox_only` | `sandbox_preset` | 只存在于 Sandbox 的预设 Skill |
| `workspace` | `workspace` | 会话级工作区中的 Skill |

### 你描述的流程完全正确

1. **WebUI 上传 Skill** → 保存为本地 Skill（`source_type=local_only`）
2. **Sandbox 同步** → SkillManager 通过 `set_sandbox_skills_cache()` 将 Skill 元数据写入缓存，标记为 `source_type=both`（`source_label=synced`）
3. **Neo 创建 Skill** → 通过 `CreateSkillPayloadTool`、`CreateSkillCandidateTool` 等工具，在 Sandbox 中直接创建 Skill，`source_type=sandbox_only`

### Skill 与 Tool 的关系

Skill 本身**不是工具**，不会出现在 `func_list` 或 `builtin_func_list` 中。但 AstrBot 提供了一些**操作 Skill 的工具**：

- `RunBrowserSkillTool` — 运行浏览器 Skill
- `CreateSkillPayloadTool` — 创建 Skill payload
- `CreateSkillCandidateTool` — 创建 Skill 候选
- `GetSkillPayloadTool` — 获取 Skill payload
- `ListSkillCandidatesTool` — 列出 Skill 候选
- `EvaluateSkillCandidateTool` — 评估 Skill 候选
- `PromoteSkillCandidateTool` — 提升 Skill 候选为正式版本
- `ListSkillReleasesTool` — 列出 Skill 发布版本
- `RollbackSkillReleaseTool` — 回滚 Skill 版本
- `SyncSkillReleaseTool` — 同步 Skill 到 Sandbox
- `GetExecutionHistoryTool` — 获取执行历史
- `AnnotateExecutionTool` — 标注执行

这些工具都是 `NeoSkillToolBase` 的子类，定义在 [neo_skills.py#L53](../.venv/Lib/site-packages/astrbot/core/tools/computer_tools/shipyard_neo/neo_skills.py#L53)。

### 总结

| 维度 | Tool | Skill |
|------|------|-------|
| 本质 | 可执行函数 | Markdown 提示词文档 |
| 作用 | LLM 调用后执行代码 | 注入到 system prompt，指导 LLM 行为 |
| 注册 | `@llm_tool` 或 `@builtin_tool` | 放在 `skills/` 目录或插件 `skills/` 目录 |
| 存储 | `FunctionToolManager` | `SkillManager` + 文件系统 |
| LLM 感知 | 作为 tool_call 调用 | 作为 prompt 上下文阅读 |

两者是互补关系：Tool 做具体执行，Skill 做流程指导。

## 十一、为什么SubAgent看不到Skill

原因分析：

Skill 注入逻辑**只存在于主 Agent 的代码路径**中：

- [astr_main_agent.py#L499-L575](../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py#L499-L575) — 唯一调用 `skill_manager.list_skills()` 和 `build_skills_prompt()` 的地方

而 SubAgent 的执行路径中**没有任何 Skill 相关代码**：

- [astr_agent_tool_exec.py](../.venv/Lib/site-packages/astrbot/core/astr_agent_tool_exec.py) — 0 处 Skill 引用
- [context.py](../.venv/Lib/site-packages/astrbot/core/star/context.py) — `tool_loop_agent` 只透传 `system_prompt` 参数，不处理 Skill

### 调用路径对比

```text
主 Agent：
  Pipeline → build_initial_request()
    → skill_manager.list_skills()
    → build_skills_prompt(skills)
    → req.system_prompt += skills_prompt  ← Skill 注入
    → provider.text_chat()

SubAgent：
  _execute_handoff()
    → _build_handoff_toolset()
    → ctx.tool_loop_agent(system_prompt=agent.instructions)
    → ToolLoopAgentRunner.run()
    → provider.text_chat()              ← 无 Skill 注入
```

### 让 SubAgent 看到 Skill 的方法

在自定义 `call_sub_agent` 工具的 handler 中，手动注入 Skill prompt：

```python
from astrbot.core.skills import SkillManager, build_skills_prompt

async def _call_sub_agent_handler(self, event, agent_name, input):
    ...
    # 注入 Skill 到 SubAgent 的 system prompt
    skills = SkillManager().list_skills(active_only=True)
    skill_prompt = build_skills_prompt(skills)
    system_prompt = agent.instructions + "\n" + skill_prompt
    
    llm_resp = await self.context.tool_loop_agent(
        system_prompt=system_prompt,
        # ...
    )
```

这和让 SubAgent 看到内置工具的逻辑一样——框架原生不支持，需要手动补充。

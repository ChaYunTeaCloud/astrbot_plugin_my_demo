# AstrBot Persona 机制

## 一、核心概念

### 1.1 Persona 是什么

Persona（人格设定）是 AstrBot 中定义 AI 行为模式的核心配置。它控制 AI 的系统提示词、可用工具、可用 Skill 和预设对话。

**一个 Persona 可以被多个 Agent 共享使用。**

### 1.2 两套数据结构

AstrBot 中存在两套 Persona 相关的数据结构：

| 维度 | `Persona` | `Personality` |
|------|-----------|---------------|
| 定义位置 | `astrbot.core.db.po.Persona` | `astrbot.core.db.po.Personality` |
| 类型 | `SQLModel`（ORM 数据库模型） | `TypedDict`（纯数据字典） |
| 定位 | 数据库持久化存储 | 运行时使用的轻量副本 |
| 获取方式 | **异步**（需查数据库） | **同步**（内存缓存） |
| 包含字段 | 完整字段（含 `folder_id`、`sort_order` 等） | 精简字段（不含 `folder_id`、`sort_order`） |
| 推荐使用 | ✅ v4.0.0+ 推荐 | 旧版兼容，框架内部仍大量使用 |

`Personality` 头部注释明确说明：

```text
在 v4.0.0 版本及之后，推荐使用 Persona 类。并且，mood_imitation_dialogs 字段已被废弃。
```

### 1.3 数据模型

#### Persona（ORM 模型）

```python
class Persona(TimestampMixin, SQLModel, table=True):
    persona_id: str              # 唯一标识（如 "default"、"weather"）
    system_prompt: str           # 系统提示词（对应 Personality.prompt）
    begin_dialogs: list | None   # 预设对话（偶数条，user/assistant 交替）
    tools: list | None           # 工具白名单
    skills: list | None          # Skill 白名单
    custom_error_message: str    # 自定义错误消息
    folder_id: str               # 文件夹 ID（用于分组）
    sort_order: int              # 排序顺序
```

#### Personality（TypedDict）

```python
class Personality(TypedDict):
    prompt: str                          # 系统提示词
    name: str                            # 名称（对应 Persona.persona_id）
    begin_dialogs: list[str]             # 预设对话原始列表
    mood_imitation_dialogs: list         # 已废弃
    tools: list | None                   # 工具白名单
    skills: list | None                  # Skill 白名单
    custom_error_message: str | None     # 自定义错误消息
    _begin_dialogs_processed: list       # 预处理后的对话消息列表（内部字段）
    _mood_imitation_dialogs_processed: str  # 已废弃
```

### 1.4 tools / skills 字段的三态语义

`tools` 和 `skills` 字段支持三种值，语义各不相同：

| 值 | 含义 |
|----|------|
| `None` | **不限制**——使用全部可用工具/Skill |
| `[]`（空列表） | **禁用全部**——不使用任何工具/Skill |
| `["name1", "name2"]`（非空列表） | **白名单**——仅使用列表中指定的工具/Skill |

**示例：**

```yaml
# config.yaml
subagent_orchestrator:
  agents:
    - name: helper
      # Persona 中 tools 字段为 null
      # → 该 Agent 可以使用所有注册的工具

    - name: searcher
      # Persona 中 tools 字段为 ["web_search", "read_file"]
      # → 该 Agent 只能使用这两个工具

    - name: strict
      # Persona 中 tools 字段为 []
      # → 该 Agent 不能使用任何工具
```

---

## 二、PersonaManager 类

`PersonaManager` 是 Persona 的管理中心，负责加载、缓存、查询和修改 Persona 数据。

### 2.1 初始化与缓存

#### 初始化流程

```text
AstrBot 启动
    → core_lifecycle.py 创建 PersonaManager 实例
    → PersonaManager.initialize()
        ├── get_all_personas()         # 从数据库加载所有 Persona
        │   └── self.personas = [...]  # 缓存原始 ORM 对象
        └── get_v3_persona_data()     # 转换为运行时格式
            ├── self.personas_v3 = [...]     # Personality 列表
            ├── self.persona_v3_config = [...]  # 原始字典配置列表
            └── self.selected_default_persona_v3  # 默认 Persona
```

#### 三层缓存结构

| 属性 | 类型 | 说明 |
|------|------|------|
| `personas` | `list[Persona]` | ORM 对象列表，完整数据 |
| `personas_v3` | `list[Personality]` | 运行时副本列表 |
| `persona_v3_config` | `list[dict]` | 原始字典配置列表 |
| `selected_default_persona` | `Persona` | 默认 Persona（ORM） |
| `selected_default_persona_v3` | `Personality` | 默认 Persona（运行时） |

#### 数据转换逻辑

[persona_mgr.py#L353-L432](../.venv/Lib/site-packages/astrbot/core/persona_mgr.py#L353-L432) `get_v3_persona_data()`

```python
# Persona → Personality 的字段映射
personas_v3_config = [
    {
        "prompt": persona.system_prompt,      # system_prompt → prompt
        "name": persona.persona_id,            # persona_id → name
        "begin_dialogs": persona.begin_dialogs or [],
        "tools": persona.tools,
        "skills": persona.skills,
        "custom_error_message": persona.custom_error_message,
    }
    for persona in self.personas
]
```

**额外预处理**：`begin_dialogs` 被转换为消息格式：

```python
# 原始: ["你好", "你好！有什么可以帮你？", "再见", "再见！"]
# 转换后:
[
    {"role": "user",      "content": "你好",  "_no_save": True},
    {"role": "assistant", "content": "你好！有什么可以帮你？", "_no_save": True},
    {"role": "user",      "content": "再见",  "_no_save": True},
    {"role": "assistant", "content": "再见！", "_no_save": True},
]
```

### 2.2 查询方法

#### 同步查询（推荐用于只读场景）

`get_persona_v3_by_id(persona_id)` → `Personality | None`

```python
def get_persona_v3_by_id(self, persona_id: str | None) -> Personality | None:
    if not persona_id:
        return None
    if persona_id == "default":
        return DEFAULT_PERSONALITY
    return next(
        (persona for persona in self.personas_v3 if persona["name"] == persona_id),
        None,
    )
```

**特点**：
- 同步方法，无需 await
- 从内存缓存 `personas_v3` 查找，速度快
- 返回 `Personality`（TypedDict），用字典访问

**使用示例**：

```python
persona = context.persona_manager.get_persona_v3_by_id("weather")
if persona:
    skills = persona.get("skills")    # 字典访问
    prompt = persona.get("prompt")
```

#### 异步查询（推荐用于需要完整数据的场景）

`get_persona(persona_id)` → `Persona`

```python
async def get_persona(self, persona_id: str) -> Persona:
    persona = await self.db.get_persona_by_id(persona_id)
    if not persona:
        raise ValueError(f"Persona with ID {persona_id} does not exist.")
    return persona
```

**特点**：
- 异步方法，需要 await
- 直接查数据库，获取最新数据
- 返回 `Persona`（ORM 对象），用属性访问
- 可访问 `folder_id`、`sort_order` 等 Personality 中没有的字段

**使用示例**：

```python
persona = await context.persona_manager.get_persona("weather")
if persona:
    skills = persona.skills          # 属性访问
    folder = persona.folder_id
    sort = persona.sort_order
```

#### 其他查询方法

| 方法 | 签名 | 说明 |
|------|------|------|
| `get_default_persona_v3(umo)` | `async (umo) → Personality` | 获取当前会话的默认 Persona |
| `resolve_selected_persona(...)` | `async (umo, ...) → tuple` | 解析会话最终生效的 Persona（考虑会话级覆盖） |
| `get_all_personas()` | `async () → list[Persona]` | 获取所有 Persona |
| `get_personas_by_folder(folder_id)` | `async (folder_id) → list[Persona]` | 获取指定文件夹下的 Persona |

### 2.3 CRUD 方法

| 方法 | 说明 |
|------|------|
| `create_persona(persona_id, system_prompt, ...)` | 创建新 Persona |
| `update_persona(persona_id, system_prompt, ...)` | 更新 Persona |
| `delete_persona(persona_id)` | 删除 Persona |
| `batch_update_sort_order(items)` | 批量更新排序 |

### 2.4 文件夹管理

AstrBot 支持通过文件夹对 Persona 进行分组：

| 方法 | 说明 |
|------|------|
| `create_folder(name, ...)` | 创建文件夹 |
| `get_folder(folder_id)` | 获取文件夹信息 |
| `get_folders(parent_id)` | 获取子文件夹列表 |
| `get_all_folders()` | 获取所有文件夹 |
| `update_folder(folder_id, ...)` | 更新文件夹 |
| `delete_folder(folder_id)` | 删除文件夹（Persona 移到根目录） |
| `get_folder_tree()` | 获取树形结构 |

---

## 三、Persona 生命周期

### 3.1 启动时加载

```text
AstrBot 启动
    → 初始化数据库连接
    → 创建 PersonaManager(db, acm)
    → await persona_manager.initialize()
        → self.personas = await self.get_all_personas()
        → self.get_v3_persona_data()
        → logger.info("Loaded %s personas.", len(self.personas))
```

### 3.2 热更新流程

当用户通过 WebUI 修改 Persona 时：

```text
WebUI 请求
    → 后端 API 接收
    → PersonaManager.update_persona() 或 create_persona()
        → 数据库写入
        → self.personas 列表更新
        → self.get_v3_persona_data()  # 重新转换缓存
    → 返回成功
```

**缓存始终与数据库保持同步**，修改后立即生效。

### 3.3 MainAgent 的 Persona 应用时机

MainAgent **每次请求前**都会动态解析 Persona：

```text
用户消息到达
    → Pipeline 处理
    → InternalAgentSubStage
        → build_main_agent()
            → person_manager.resolve_selected_persona(umo, ...)
                → 考虑会话级覆盖
                → 考虑平台特殊默认
                → 返回当前会话应使用的 Personality
            → 从 Personality 提取 system_prompt、tools、skills 等
            → 注入 Skill prompt
            → 构建 ProviderRequest
        → AgentRunner.run()
```

**特点**：
- 每次请求都重新解析，支持会话级切换
- Persona 修改后下次请求立即生效
- 可通过 `@on_llm_request` 进一步修改

### 3.4 SubAgent 的 Persona 应用时机

SubAgent 在**创建时**一次性固化 Persona 数据：

```text
SubAgentOrchestrator.reload_from_config()
    → 读取配置中的 persona_id
    → persona_manager.get_persona_v3_by_id(persona_id)
    → 构建 Agent 对象
        → agent.instructions = persona.prompt
        → agent.tools = persona.tools
        → agent.begin_dialogs = persona._begin_dialogs_processed
        → ⚠️ skills 未传递（Bug）
    → 包装为 HandoffTool
    → 注册到 func_list
```

**特点**：
- 创建时快照化，之后与 Persona 解耦
- Persona 修改后**不会自动生效**，需触发 `reload_from_config()`
- 不支持会话级切换

---

## 四、Persona 与 Agent 的关系

### 4.1 数据流向图

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
```

### 4.2 一对一关系

| 关系 | 说明 |
|------|------|
| 配置 → Persona | 每个 SubAgent 配置通过 `persona_id` 关联一个 Persona |
| Persona → Agent | Persona 数据在 Agent 创建时被**一次性快照化** |
| Agent ↔ Persona | Agent 创建后与 Persona **解耦**，Persona 修改需重建 Agent |

### 4.3 Persona 数据覆盖规则

当 SubAgent 配置和 Persona 同时指定时，Persona 数据覆盖配置中的对应字段：

```python
# subagent_orchestrator.py
if persona_data:
    instructions = persona_data.get("prompt")      # 覆盖 system_prompt
    tools = persona_data.get("tools")              # 覆盖 tools
    begin_dialogs = persona_data.get("_begin_dialogs_processed")  # 新增
```

### 4.4 Agent 类的数据结构

[agent.py#L10-L15](../.venv/Lib/site-packages/astrbot/core/agent/agent.py#L10-L15)

```python
@dataclass
class Agent(Generic[TContext]):
    name: str                                          # Agent 名称
    instructions: str | None = None                    # system prompt 文本
    tools: list[str | FunctionTool] | None = None      # 工具名称列表
    run_hooks: BaseAgentRunHooks[TContext] | None = None  # 运行时钩子
    begin_dialogs: list[Any] | None = None             # 预设对话
    # ❌ 没有 persona_id 字段
    # ❌ 没有 skills 字段
```

**关键特点**：
- `Agent` 是轻量级数据载体，不是运行时执行单元
- 不持有 Persona 引用，只保存 Persona 数据的"快照"
- 没有 `skills` 字段（框架 Bug）

### 4.5 MainAgent vs SubAgent 的 Persona 应用时机对比

| 维度 | MainAgent | SubAgent |
|------|-----------|----------|
| Persona 应用时机 | **每次请求前**动态解析 | **Agent 创建时**一次性固化 |
| Persona 可变性 | 每次请求可不同（支持会话级切换） | 创建后不可变 |
| Persona 切换 | 支持（基于会话配置） | 不支持 |
| 数据流向 | `PersonaManager` → `ProviderRequest` | `PersonaManager` → `Agent` 对象 → `ProviderRequest` |
| Persona 修改后 | 下次请求立即生效 | 需触发 `reload_from_config()` |
| 关联方式 | 会话级 `persona_id` | SubAgent 配置的 `persona_id` |

---

## 五、插件开发参考

### 5.1 获取 Persona 数据

#### 使用同步方法（推荐只读场景）

```python
async def my_handler(self, event):
    persona = self.context.persona_manager.get_persona_v3_by_id("weather")
    if persona:
        skills = persona.get("skills")    # list[str] | None
        prompt = persona.get("prompt")    # str
```

#### 使用异步方法（需要完整数据）

```python
async def my_handler(self, event):
    try:
        persona = await self.context.persona_manager.get_persona("weather")
        if persona:
            skills = persona.skills              # list[str] | None
            folder = persona.folder_id           # str
            sort = persona.sort_order            # int
    except ValueError:
        # Persona 不存在
        pass
```

### 5.2 为 SubAgent 注入 Skill

由于框架 Bug，SubAgent 默认看不到 Persona 中配置的 Skill。可以在自定义工具中手动注入：

```python
from astrbot.core.skills import SkillManager, build_skills_prompt

async def _get_skills_prompt(self, agent_name: str) -> str:
    """根据 Persona 的 skills 配置获取应注入的 Skill prompt"""
    # 1. 找到这个 agent 的 persona_id
    persona_id = None
    for item in self._cfg["subagent_orchestrator"]["agents"]:
        if item.get("name") == agent_name:
            persona_id = item.get("persona_id")
            break
    if not persona_id:
        return ""

    # 2. 拿到 persona 数据
    persona = await self._context.persona_manager.get_persona(persona_id)
    if not persona:
        return ""

    # 3. 拿 skills 白名单
    allowed_skills = persona.skills
    if allowed_skills is None:
        return ""  # None = 不限制，但 SubAgent 默认也不注入，保持原行为
    if not allowed_skills:
        return ""  # [] = 禁用全部

    # 4. 获取全部可用 skill，按白名单过滤
    skill_mgr = SkillManager()
    runtime = self._cfg["provider_settings"]["computer_use_runtime"]
    skills = skill_mgr.list_skills(active_only=True, runtime=runtime)
    skills = [s for s in skills if s.name in allowed_skills]

    if not skills:
        return ""

    return build_skills_prompt(skills)
```

### 5.3 监听 Persona 变更

AstrBot 没有提供 Persona 变更事件。如果需要监听：

```python
# 轮询方式（不推荐，但简单）
last_persona_count = len(self.context.persona_manager.personas)

async def check_persona_change(self):
    current_count = len(self.context.persona_manager.personas)
    if current_count != last_persona_count:
        logger.info("Persona 列表已变更")
        # 重新加载 SubAgent 配置等
        last_persona_count = current_count
```

### 5.4 常见问题

#### Q: 修改 Persona 后，SubAgent 需要重启吗？

**是的**。SubAgent 在创建时快照化 Persona 数据，修改后不会自动生效。需要：
- 重启 AstrBot
- 或调用 `subagent_orchestrator.reload_from_config()`

#### Q: `persona_id` 为 "default" 时会返回什么？

返回内置的 `DEFAULT_PERSONALITY`：

```python
DEFAULT_PERSONALITY = Personality(
    prompt="You are a helpful and friendly assistant.",
    name="default",
    begin_dialogs=[],
    tools=None,       # 不限制
    skills=None,      # 不限制
    ...
)
```

#### Q: `tools`/`skills` 为 `None` 和 `[]` 有什么区别？

| 值 | 含义 |
|----|------|
| `None` | 不限制，使用所有可用工具/Skill |
| `[]` | 禁用，不使用任何工具/Skill |
| `["a", "b"]` | 白名单，仅使用指定的 |

#### Q: 如何在插件中切换当前会话的 Persona？

```python
from astrbot.api import sp

# 设置会话级 Persona
await sp.set_async(
    scope="umo",
    scope_id=str(event.unified_msg_origin),
    key="session_service_config",
    value={"persona_id": "weather"},
)
# MainAgent 下次请求时会自动使用 weather Persona
```

---

## 六、关键源码文件

| 文件 | 说明 |
|------|------|
| `../.venv/Lib/site-packages/astrbot/core/db/po.py` | `Persona` 和 `Personality` 数据模型定义 |
| `../.venv/Lib/site-packages/astrbot/core/persona_mgr.py` | `PersonaManager` 类，管理所有 Persona 操作 |
| `../.venv/Lib/site-packages/astrbot/core/star/context.py` | `Context` 类，暴露 `persona_manager` 属性 |
| `../.venv/Lib/site-packages/astrbot/core/subagent_orchestrator.py` | `SubAgentOrchestrator` 类，创建 SubAgent 时使用 Persona |
| `../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py` | `build_main_agent()`，MainAgent 动态解析 Persona |
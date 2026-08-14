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

[po.py#L144-L177](../.venv/Lib/site-packages/astrbot/core/db/po.py#L144-L177)

```python
class Persona(TimestampMixin, SQLModel, table=True):
    persona_id: str              # 唯一标识（如 "default"、"weather"）
    system_prompt: str           # 系统提示词（对应 Personality.prompt）
    begin_dialogs: list | None   # 预设对话（偶数条，user/assistant 交替）
    tools: list | None           # 工具列表
                                 #   None  → 使用全部工具
                                 #   []     → 禁用全部工具
                                 #   [str]  → 白名单
    skills: list | None          # Skill 列表（同上规则）
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
    mood_imitation_dialogs: list[str]   # 已废弃
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

[core_lifecycle.py#L209](../.venv/Lib/site-packages/astrbot/core/core_lifecycle.py#L209) 创建 `PersonaManager` 实例：

```python
self.persona_mgr = PersonaManager(self.db, self.astrbot_config_mgr)
```

AstrBot 启动时的初始化流程：

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

[persona_mgr.py#L35-L38](../.venv/Lib/site-packages/astrbot/core/persona_mgr.py#L35-L38) 初始化缓存：

```python
async def initialize(self):
    self.personas = await self.get_all_personas()    # 数据库 → list[Persona]
    self.get_v3_persona_data()                         # 转换为 v3 格式
```

#### 三层缓存结构

| 属性 | 类型 | 说明 |
|------|------|------|
| `personas` | `list[Persona]` | ORM 对象列表，完整数据（原始数据库记录） |
| `personas_v3` | `list[Personality]` | 运行时副本列表（v3 格式，TypedDict） |
| `persona_v3_config` | `list[dict]` | 原始字典配置列表（v3 配置字典） |
| `selected_default_persona` | `Persona` | 默认 Persona（ORM，旧格式） |
| `selected_default_persona_v3` | `Personality` | 默认 Persona（运行时，v3 格式） |

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

[persona_mgr.py#L47-L61](../.venv/Lib/site-packages/astrbot/core/persona_mgr.py#L47-L61)

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

**查询优先级**：`"default"` 关键字 → `personas_v3` 列表 → 返回 `None`

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
| `resolve_selected_persona(...)` | `async (*, umo, conversation_persona_id, platform_name, provider_settings=None) → tuple[str \| None, Personality \| None, str \| None, bool]` | 解析会话最终生效的 Persona（考虑会话级覆盖） |
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

完整的更新链条：

1. 数据库写入新数据
2. `create_persona()` / `update_persona()` / `delete_persona()` 各自内部直接调用 `get_v3_persona_data()` 重建缓存（不存在 `reload()` 方法）
3. MainAgent 下次请求时使用最新 Persona
4. SubAgent 需要触发 `SubAgentOrchestrator.reload_from_config()` 才会更新

**缓存始终与数据库保持同步**，修改后立即生效。

**这意味着修改 Persona 后，MainAgent 立即生效，SubAgent 可能需要重启或手动触发 reload。**

### 3.3 MainAgent 的 Persona 应用时机

MainAgent **每次请求前**都会动态解析 Persona：

```text
用户消息到达
    → Pipeline 处理
    → InternalAgentSubStage
        → build_main_agent()（astr_main_agent.py#L1412）
            → person_manager.resolve_selected_persona(umo, ...)（调用于 astr_main_agent.py#L543）
                → 考虑会话级覆盖
                → 考虑平台特殊默认
                → 返回当前会话应使用的 Personality
            → 从 Personality 提取 system_prompt、tools、skills 等
            → 注入 Skill prompt（_ensure_persona_and_skills，astr_main_agent.py#L522）
            → 构建 ProviderRequest
        → step_until_done()
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

一个 SubAgent 对应一个 Persona（通过 `persona_id` 关联）。但 Agent 本身不持有 Persona 引用，只保存 Persona 数据的"快照"。

### 4.1 字段提取关系图

Persona 的字段在构建 Agent 时被逐项提取，其中 `skills` 字段未被处理：

```text
Persona (数据库)                    Agent (运行时)
├── persona_id                     ├── name
├── system_prompt  ──提取──→       ├── instructions
├── tools          ──提取──→       ├── tools
├── skills         (未处理)        │
├── begin_dialogs  ──提取──→       ├── begin_dialogs
└── ...                            └── run_hooks
```

### 4.2 数据流向图

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

### 4.3 Agent 类的数据结构

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
    # ❌ 没有 metadata、description 等扩展字段
```

**关键特点**：
- `Agent` 是一个**轻量级数据载体**，不是运行时执行单元
- 不持有 Persona 引用，只保存 Persona 数据的**快照**
- 没有 `skills` 字段（框架 Bug）
- 没有 `metadata`、`description` 等扩展字段

### 4.4 一对一关系

| 关系 | 说明 |
|------|------|
| 配置 → Persona | 每个 SubAgent 配置通过 `persona_id` 关联一个 Persona |
| Persona → Agent | Persona 数据在 Agent 创建时被**一次性快照化** |
| Agent ↔ Persona | Agent 创建后与 Persona **解耦**，Persona 修改需重建 Agent |

### 4.5 Persona 数据覆盖规则

当 SubAgent 配置和 Persona 同时指定时，Persona 数据覆盖配置中的对应字段：

[subagent_orchestrator.py#L66-L75](../.venv/Lib/site-packages/astrbot/core/subagent_orchestrator.py#L66-L75)

```python
# subagent_orchestrator.py
if persona_data:
    # Persona 数据覆盖配置中的对应字段
    instructions = persona_data.get("prompt")      # 覆盖 system_prompt
    tools = persona_data.get("tools")              # 覆盖 tools
    begin_dialogs = persona_data.get("_begin_dialogs_processed")  # 新增
```

**简单说：配置中的 `persona_id` 是"外键"，指向 Persona 表中的一条记录。**

### 4.6 MainAgent vs SubAgent 的 Persona 应用时机对比

| 维度 | MainAgent | SubAgent |
|------|-----------|----------|
| Persona 应用时机 | **每次请求前**动态解析 | **Agent 创建时**一次性固化 |
| Persona 可变性 | 每次请求可不同（支持会话级切换） | 创建后不可变 |
| Persona 切换 | 支持（基于会话配置） | 不支持 |
| 数据流向 | `PersonaManager` → `ProviderRequest` | `PersonaManager` → `Agent` 对象 → `ProviderRequest` |
| Persona 修改后 | 下次请求立即生效 | 需重启（`tools`/`system_prompt`/`begin_dialogs`）；`skills` 不生效 |
| 关联方式 | 会话级 `persona_id` | SubAgent 配置的 `persona_id` |
| skills 支持 | ✅ 实时注入 | ❌ 框架未实现注入 |

---

## 五、AstrBot 是根据什么把 Persona 交给对应的 SubAgent 的

通过**配置文件**中的 `persona_id` 字段匹配。

### 5.1 配置结构

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
```

可以看出，`agents` 里面有很多项，每一项都是你在 WebUI 里面创建的 SubAgent，每个 SubAgent 对应一个 `persona_id`。所以其实 AstrBot 是通过 `agents` 里面的 `name` 来判断是哪个 SubAgent，通过 `persona_id` 来判断这个 SubAgent 绑定的是哪个人格设定。

### 5.2 匹配流程

```text
配置文件                          PersonaManager (内存)
┌──────────────────────┐        ┌──────────────────────┐
│ agents:               │        │ personas_v3:         │
│   - name: weather     │        │   - name: weather    │
│     persona_id: weather│ ─────→ │     prompt: "..."    │
│                       │  查询   │     tools: [...]     │
└──────────────────────┘        │     skills: [...]    │
                                └──────────────────────┘
```

### 5.3 代码实现

[subagent_orchestrator.py#L48-L51](../.venv/Lib/site-packages/astrbot/core/subagent_orchestrator.py#L48-L51)

```python
# 从配置读取 persona_id
persona_id = item.get("persona_id")
if persona_id is not None:
    persona_id = str(persona_id).strip() or None

# 查询 PersonaManager 中对应的 Persona
persona_data = self._persona_mgr.get_persona_v3_by_id(persona_id)
```

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
```

### 5.4 优先级

| `persona_id` 值 | 行为 |
|----------------|------|
| `None` 或空字符串 | 不关联 Persona，使用配置中的 `system_prompt` 和 `tools` |
| `"default"` | 使用内置默认 Persona |
| 具体名称（如 `"weather"`） | 从 `personas_v3` 列表中按 `name` 查找 |
| 找不到匹配 | 警告日志，回退到配置中的 `system_prompt` |

### 5.5 数据覆盖规则

当配置中指定了 `persona_id` 且能匹配到 Persona 时，Persona 数据会覆盖配置中的对应字段（完整代码与说明详见 [4.5 Persona 数据覆盖规则](#45-persona-数据覆盖规则)）：

- `instructions` ← `persona_data.get("prompt")`，覆盖 `system_prompt`
- `tools` ← `persona_data.get("tools")`，覆盖 `tools`
- `begin_dialogs` ← `persona_data.get("_begin_dialogs_processed")`，新增

**简单说：配置中的 `persona_id` 是"外键"，指向 Persona 表中的一条记录。**

### 5.6 细节补充

1. **`personas_v3` 是列表不是字典**，所以 `get_persona_v3_by_id` 每次都 `next()` 线性扫描，Persona 多了会慢。

2. **`tools` 字段是 `persona_data.get("tools")` 原样返回的**，如果 Persona 里 `tools` 是 `None`（表示"不限制，用全部"），那 SubAgent 拿到也是 `None`。但框架在 handoff 执行时没有把 MainAgent 的全局工具全量透传——这就是 SubAgent 拿不到 Skill 的原因。Persona 的 `tools` 字段只是一个"白名单标记"，真正注入工具的逻辑在 handoff 执行层，而那层漏了。

3. 简单说完整链条：我们编写的所有人格设定，都会在 AstrBot 初始化的时候缓存进 `personas_v3` 这个列表，【`get_persona_v3_by_id`】方法返回一个 `persona_data`，然后 AstrBot 根据这个 `persona_data` 动态创建 SubAgent，构建 Handoff 方法缓存进 `handoffs` 这个列表里。流程图：

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
```

几个关键点：
- `reload_from_config` **不是只在启动时调一次**，配置变更时也会触发，每次都是**原子替换** `self.handoffs`（整个列表一把换掉，不是追加）。
- Persona 的 `tools` 此时只是一个**标签**（`None` / `[]` / `["tool_a"]`），存进 `Agent.tools` 后就完事了。真正按这个标签筛选并注入工具的代码在 handoff 执行层——那层目前漏掉了全局 Skill 工具的透传。
- `personas_v3` 是列表不是字典，`get_persona_v3_by_id` 每次 O(n) 扫描，Persona 多了性能会受影响，不过一般没那么多就是了。

综上所述，无法通过 handoff 溯源到它的人格设定，只能通过配置文件中的 `persona_id` 来关联。可以看一下 `HandoffTool` 和 `Agent` 分别存了什么：
- **Agent**：`name`、`instructions`、`tools`、`run_hooks`、`begin_dialogs`
- **HandoffTool**：`agent`、`tool_description`、`provider_id`

没有一个字段存 `persona_id`。`reload_from_config` 里 `persona_id` 只是个**临时变量**——查完 `personas_v3` 拿到数据、覆盖到 `instructions`/`tools`/`begin_dialogs` 之后，`persona_id` 就丢掉了。

所以 `handoffs` 列表里的每个 `HandoffTool`，你只能看到它「最终的」人设文本和工具配置，但无法反向追溯它是从哪个 Persona 来的。类似于只存了渲染后的 HTML，扔掉了原始的模板引用。

`name` 是 SubAgent 的"身份证"，`persona_id` 是它绑定的"人设卡"。两条线独立，通过配置文件的 `persona_id` 字段关联起来。一张图总结：

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
```

注意：**把 Agent 包成 HandoffTool 这一步其实没问题——它就是把 `Agent` 对象原样存进去了：**

```python
handoff = HandoffTool(
    agent=agent,                        # Agent 整个塞进去
    tool_description=public_description or None,
)
```

这一步没做任何过滤或加工。

当 MainAgent 调用 `transfer_to_test_sub_agent`，`HandoffTool.call()` 被执行时，框架构建 SubAgent 的 LLM 请求，这时候它要根据 `Agent.tools` 来决定给 SubAgent 注入哪些工具。`tools=None` 按设计应该等于「全部工具」，但实际注入时没有把全局 Skill 工具（`astrbot_run_browser_skill` 等）带过去，只给了沙箱基础工具集。

所以不是「包成 HandoffTool 时做了不符合预期的行为」，而是「HandoffTool 被执行时，工具注入那一步漏了全局 Skill」。

简单说就是：AstrBot 根据这个 `persona_data` 动态创建名为 `name` 的 Agent 对象，并进一步处理为 handoff 实例对象，到这里都是根据人格设定文件完整复制。而我遇到的 BUG 或者说不符合我个人预期的问题，本质上是 HandoffTool 被执行时，AstrBot 对 Handoff 进行了过滤和加工。主要是注入工具那一步。

```text
配置 + Persona → Agent(name, instructions, tools=None)  ✅ 没问题，完整复制
Agent → HandoffTool(agent)                               ✅ 没问题，原样封装
HandoffTool.call() → 构建 SubAgent LLM 请求 → 注入工具    ❌ 这里过滤掉了全局 Skill
```

---

## 六、插件开发参考

### 6.1 获取 Persona 数据

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

### 6.2 为 SubAgent 注入 Skill

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

### 6.3 监听 Persona 变更

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

### 6.4 常见问题

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
await sp.put_async(
    scope="umo",
    scope_id=str(event.unified_msg_origin),
    key="session_service_config",
    value={"persona_id": "weather"},
)
# MainAgent 下次请求时会自动使用 weather Persona
```

---

## 七、关键源码文件

| 文件 | 说明 |
|------|------|
| `../.venv/Lib/site-packages/astrbot/core/db/po.py` | `Persona` 和 `Personality` 数据模型定义 |
| `../.venv/Lib/site-packages/astrbot/core/persona_mgr.py` | `PersonaManager` 类，管理所有 Persona 操作 |
| `../.venv/Lib/site-packages/astrbot/core/core_lifecycle.py` | AstrBot 启动时创建 `PersonaManager` 实例 |
| `../.venv/Lib/site-packages/astrbot/core/agent/agent.py` | `Agent` 数据结构定义（轻量数据载体） |
| `../.venv/Lib/site-packages/astrbot/core/star/context.py` | `Context` 类，暴露 `persona_manager` 属性 |
| `../.venv/Lib/site-packages/astrbot/core/subagent_orchestrator.py` | `SubAgentOrchestrator` 类，创建 SubAgent 时使用 Persona |
| `../.venv/Lib/site-packages/astrbot/core/astr_main_agent.py` | `build_main_agent()`，MainAgent 动态解析 Persona |

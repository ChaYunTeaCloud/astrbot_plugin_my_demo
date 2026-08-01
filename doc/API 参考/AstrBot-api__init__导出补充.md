# AstrBot api/__init__.py 导出补充

> 源码路径：`../.venv/Lib/site-packages/astrbot/api/__init__.py`

---

## 一、概述

`../.venv/Lib/site-packages/astrbot/api/__init__.py` 是 AstrBot 插件开发的**主要入口**，从这里导出的对象可以直接通过 `from astrbot.api import xxx` 使用。此文档补充那些在其他专题文档中未详细覆盖的导出项。

已在其他文档中详细说明的导出项此处不再重复：
- `FunctionTool`、`ToolSet`、`llm_tool` → 参见 `AstrBot-Tool.md`
- `logger`、`sp` → 本文件补充

---

## 二、AstrBotConfig

**源码**：`../.venv/Lib/site-packages/astrbot/core/config/astrbot_config.py`

AstrBot 的配置类，继承自 `dict`，支持通过点号操作符访问配置项。

### 使用场景

- 需要读取 AstrBot 全局配置（如 provider_settings、web_search 等）
- 插件一般不直接使用 `AstrBotConfig`，而是通过 `context.get_config()` 获取插件专属配置

### 核心特性

- 初始化时自动将默认配置与配置文件比对，缺失项自动补全
- 支持 JSON Schema 定义配置结构（通过 `schema` 参数）
- 线程安全的配置保存机制

### 插件中的获取方式

```python
class MyPlugin(Star):
    def __init__(self, context):
        super().__init__(context)
        # 获取插件专属配置（推荐）
        config = self.config
        # 或
        config = context.get_config()
        
        # 读取配置项
        provider_id = config.get("provider_settings", {}).get("default_provider_id")
```

通常插件不需要直接实例化 `AstrBotConfig`，框架会在启动时自动创建并通过 `context` 传递。

---

## 三、BaseFunctionToolExecutor

**源码**：`../.venv/Lib/site-packages/astrbot/core/agent/tool_executor.py`

工具执行器的基类，定义了工具执行的标准接口。

### 类签名

```python
class BaseFunctionToolExecutor(Generic[TContext]):
    @classmethod
    async def execute(
        cls,
        tool: FunctionTool,
        run_context: ContextWrapper[TContext],
        **tool_args,
    ) -> AsyncGenerator[Any | mcp.types.CallToolResult, None]: ...
```

### 使用场景

- 自定义工具执行逻辑（如修改工具调用前后的处理流程）
- 一般插件开发者不需要直接使用，框架内部使用

### 说明

这是一个抽象基类，实际的执行器实现位于 `func_tool_manager.py` 中的 `FunctionToolExecutor`。插件开发者通常不需要继承此类，除非需要深度自定义工具执行流程。

---

## 四、agent（register_agent 装饰器）

**源码**：`../.venv/Lib/site-packages/astrbot/core/star/register/star_handler.py#L697`

用于注册子 Agent 的装饰器，实现多 Agent 协作架构中的 Handoff（移交）机制。

### 装饰器签名

```python
@register_agent(
    name: str,                    # Agent 名称
    instruction: str,             # Agent 指令（系统提示词）
    tools: list[str | FunctionTool] | None = None,  # Agent 可用的工具列表
    run_hooks: BaseAgentRunHooks[Any] | None = None  # 运行时钩子
)
```

### 使用场景

- 当需要将复杂任务分派给专门的子 Agent 处理时
- 例如：主 Agent 负责闲聊，子 Agent 负责代码审查

### 使用示例

```python
from astrbot.api import agent

class MyPlugin(Star):
    @agent(
        name="code_reviewer",
        instruction="你是一个代码审查专家，擅长发现代码中的问题",
        tools=["read_file", "search_code"]  # 可使用的工具名
    )
    async def code_reviewer(self, event: AstrMessageEvent, **kwargs):
        """代码审查工具"""
        code = kwargs.get("code", "")
        # ... 审查逻辑
        return "审查结果：..."
```

### 注册后的 Agent

`@agent` 装饰器会将函数注册为 `HandoffTool`（移交工具），主 Agent 可以通过 `handoff:xxx` 格式的工具调用将对话移交给子 Agent。

---

## 五、html_renderer（HtmlRenderer 实例）

**源码**：`../.venv/Lib/site-packages/astrbot/core/utils/t2i/renderer.py`

HTML 转图片工具，用于将 HTML 模板渲染为图片。

### 核心方法

**render_t2i**（默认模板渲染）

```python
async def render_t2i(
    self,
    text: str,                     # 要渲染的文本
    use_network: bool = True,      # 是否使用网络渲染
    return_url: bool = False,      # 返回 URL 还是本地文件路径
    template_name: str | None = None  # 指定模板名
)
```

**render_custom_template**（自定义模板渲染）

```python
async def render_custom_template(
    self,
    tmpl_str: str,                 # Jinja2 HTML 模板字符串
    tmpl_data: dict,               # 模板数据
    return_url: bool = False,      # 返回 URL 还是本地文件路径
    options: dict | None = None    # 渲染选项
)
```

### 使用示例

```python
from astrbot.api import html_renderer

# 使用默认模板
image_url = await html_renderer.render_t2i(
    text="欢迎使用 AstrBot",
    return_url=True
)

# 使用自定义模板
template = "<h1>{{ title }}</h1><p>{{ content }}</p>"
image_url = await html_renderer.render_custom_template(
    tmpl_str=template,
    tmpl_data={"title": "标题", "content": "内容"},
    return_url=True
)
```

### 说明

- 网络渲染需要 AstrBot 官方 API 支持，本地渲染使用 Playwright
- `initialize()` 方法需在启动时调用一次，框架已自动处理
- 渲染结果可以直接用于 `Image` 消息组件发送

---

## 六、logger（日志记录器）

**源码**：`../.venv/Lib/site-packages/astrbot/core/__init__.py`（第 36 行）

AstrBot 全局日志记录器，用于输出日志信息。

### 使用示例

```python
from astrbot.api import logger

logger.info("插件加载完成")
logger.warning("配置项缺失，使用默认值")
logger.error("连接数据库失败")
logger.debug("调试信息")
```

### 日志级别

| 级别 | 用途 |
|------|------|
| `logger.debug()` | 调试信息，仅在调试模式显示 |
| `logger.info()` | 常规运行信息 |
| `logger.warning()` | 警告信息，不影响运行但需注意 |
| `logger.error()` | 错误信息，需要处理 |

### 说明

- 日志输出到控制台和日志文件
- 日志配置在 AstrBot 配置文件中管理
- 插件开发者应使用此 logger 而非 Python 标准库的 `logging`

---

## 七、sp（SharedPreferences 实例）

**源码**：`../.venv/Lib/site-packages/astrbot/core/utils/shared_preferences.py`

AstrBot 的偏好设置存储服务，提供轻量级的键值存储，支持按作用域（scope）隔离。

### 核心方法

**get_async**（异步获取）

```python
async def get_async(
    self,
    scope: str,          # 作用域（如 "plugin_config"）
    scope_id: str,        # 作用域 ID（如 插件名 或 用户 ID）
    key: str,             # 配置键
    default=None          # 默认值
)
```

**set_async**（异步设置）

```python
async def set_async(
    self,
    scope: str,
    scope_id: str,
    key: str,
    value               # 值
)
```

**range_get_async**（按范围获取）

```python
async def range_get_async(
    self,
    scope: str,
    scope_id: str | None = None,
    key: str | None = None
)
```

### 使用示例

```python
from astrbot.api import sp

# 保存用户偏好
await sp.set_async(
    scope="my_plugin",
    scope_id="user_123",
    key="theme",
    value="dark"
)

# 读取用户偏好
theme = await sp.get_async(
    scope="my_plugin",
    scope_id="user_123",
    key="theme",
    default="light"
)

# 获取某作用域下所有偏好
all_prefs = await sp.range_get_async(
    scope="my_plugin",
    scope_id="user_123"
)
```

### 说明

- 数据存储在 SQLite 数据库中（`astrbot.db`）
- 同时支持 JSON 文件缓存（`shared_preferences.json`）
- 有 24 小时临时缓存自动清理机制
- 适合存储插件的用户级配置、会话级状态等轻量数据
- 不适合存储大量结构化数据，大量数据建议使用数据库

---

## 八、快速参考

| 导出 | 类型 | 主要用途 |
|------|------|---------|
| `AstrBotConfig` | 类 | 全局配置管理 |
| `BaseFunctionToolExecutor` | 类 | 工具执行器基类（高级） |
| `agent` | 装饰器 | 注册子 Agent |
| `html_renderer` | 实例 | HTML 转图片 |
| `logger` | 实例 | 日志记录 |
| `sp` | 实例 | 偏好设置存储 |

### 推荐导入方式

```python
from astrbot.api import logger, sp, html_renderer, agent
```

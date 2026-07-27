# AstrBot Star 模块接口整理

> 源码路径：
> - Star 基类: `astrbot/core/star/base.py`
> - StarMetadata: `astrbot/core/star/star.py`
> - StarTools: `astrbot/core/star/star_tools.py`
> - register_star: `astrbot/core/star/register/star.py`
> - config: `astrbot/core/star/config.py`
> 导出路径：`from astrbot.api.star import Star, Context, StarTools, register`

`astrbot.api.star` 是 AstrBot 的**插件基类模块**，定义了插件的核心骨架。包含 4 个导出：
- **Star**：插件基类，所有插件必须继承它
- **Context**：插件与框架沟通的桥梁（因接口众多，单独整理见 `AstrBot-Star-Context 类接口整理.md`）
- **StarTools**：工具类，提供便捷的静态方法（如发送消息、创建事件）
- **register**：注册插件的装饰器（已废弃）

另外，值得注意的是，虽然 register 已废弃，但跟踪【astrbot.core.star.register】可以发现里面还导入了不少装饰器的定义。
只不过这些装饰器都交给 filter 模块导出了。

## register 装饰器说明

`register` 里的所有装饰器**都开放给插件开发者使用**，只是**不通过 `astrbot.api.star.register` 暴露**。

看 `filter/__init__.py` 的导入方式：

```python
from astrbot.core.star.register import register_command as command
from astrbot.core.star.register import register_on_llm_request as on_llm_request
# ... 共 28 个装饰器
```

也就是说：

| 内部路径 | 对外暴露路径 |
|---------|-------------|
| `astrbot.core.star.register.register_command` | `astrbot.api.event.filter.command` |
| `astrbot.core.star.register.register_on_llm_request` | `astrbot.api.event.filter.on_llm_request` |
| `astrbot.core.star.register.register_llm_tool` | `astrbot.api.event.filter.llm_tool` |
| ... | ... |

框架把 `register` 里的所有装饰器**重命名后集中导出到 `filter` 命名空间**，这样做的好处是：

1. **API 路径稳定**：内部实现可以随时调整，对外的 `from astrbot.api.event import filter` 始终不变
2. **职责清晰**：`register` 是内部实现模块，`filter` 是开发者接口

所以你写插件时只需要：

```python
from astrbot.api.event import filter

@filter.command(name="hello")
@filter.on_llm_request()
@filter.llm_tool(name="weather")
```

不需要直接接触 `register` 模块。

---

## 关于 register 装饰器被用 event 的 filter 导出的个人感觉

这是 AstrBot 架构中的一个小"不完美"。原因是：

**装饰器的本质是"注册 Handler 到事件系统"**，而事件系统属于 `event` 的职责范围。所以从**开发者使用**的角度，放在 `filter`（筛选器/事件过滤器命名空间）下是合理的——你需要用这些装饰器来"筛选"消息。

但从**内部实现**的角度，装饰器操作的是 `star_handlers_registry`（Star Handler 注册表），所以放在 `core.star.register` 下。

这就导致了：

```
内部实现：core.star.register（Star 系统）
         ↓ 装饰器操作的是 Star Handler 注册表
         
对外暴露：api.event.filter（Event 系统）
         ↓ 开发者用它来过滤事件
```

**本质是一个跨领域的关注点**：装饰器同时涉及"插件注册"和"事件过滤"两个职责。AstrBot 选择了从**开发者体验**出发，把它放在 `event.filter` 下，而不是从**内部架构**出发放在 `star` 下。

这在开源项目中很常见——**API 路径不一定严格对应内部模块路径**，关键是对使用者是否直观。从使用者角度 `from astrbot.api.event import filter` 然后用 `filter.command()`、`filter.on_llm_request()`，确实比 `from astrbot.api.star.register import register_command` 更直觉。

### 不完美的根源

AstrBot 实际上**只有一个 Handler 注册表**：`star_handlers_registry`。

它的位置在 `astrbot/core/star/star_handler.py`，所以名字叫 "Star Handler 注册表"。它存储了**所有插件注册的 Handler**——不管是命令、事件钩子、还是 LLM 工具，全在这一个注册表里。

所以整个流程是：

```
你的装饰器 @filter.command()
           ↓
    filter 命名空间（api.event.filter）
    （只是导出装饰器的地方）
           ↓
    实际注册到
           ↓
    star_handlers_registry（core.star.star_handler）
    （唯一的注册表）
```

注册表放在 `star` 模块里，因为 **Handler 是由 Star 插件注册的**。而装饰器（注册入口）放在 `event.filter` 里，是为了让开发者用起来更直观。

这就是那个"不完美"的根源：**注册表在 Star 域，注册入口在 Event 域，但它们操作的是同一个东西。**

## 一、Star（插件基类）

所有插件必须继承 `Star` 类。它提供了插件的生命周期和基础能力。

### 1.1 类属性

继承 Star 后，应在类级别定义以下属性（类型注解即可）：

- `name: str` — 插件名称
- `author: str` — 插件作者
- `context: Context` — 框架自动注入，不要手动赋值

### 1.2 构造函数

```python
def __init__(self, context: Context, config: dict | None = None) -> None
```

- `context`：框架自动传入，存储为 `self.context`
- `config`：插件配置（可选）

### 1.3 生命周期方法

- `async initialize() -> None`
  - 插件被激活时调用（如 AstrBot 启动、插件加载完成）
  - 用途：初始化资源、注册定时任务、连接外部服务等

- `async terminate() -> None`
  - 插件被禁用或重载时调用
  - 用途：释放资源、取消定时任务、断开连接等

### 1.4 内置能力

- `async text_to_image(text: str, return_url=True) -> str`
  - 将文本转换为图片
  - 参数：
    - `text`: 要转换的文本
    - `return_url`: 是否返回 URL（True）还是 Base64（False）
  - 返回：图片 URL 或 Base64 字符串

- `async html_render(tmpl: str, data: dict, return_url=True, options=None) -> str`
  - 渲染 HTML 模板为图片
  - 参数：
    - `tmpl`: 模板名称
    - `data`: 模板数据字典
    - `return_url`: 是否返回 URL
    - `options`: 额外选项
  - 返回：图片 URL 或 Base64 字符串

### 1.5 使用示例

```python
from astrbot.api.star import Context, Star
from astrbot.api.event import filter

class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        # 插件激活时执行
        pass

    async def terminate(self):
        # 插件停用时执行
        pass

    @filter.command(name="img")
    async def text_to_img(self, event):
        url = await self.text_to_image("Hello World")
        yield event.image_result(url)
```

---

## 二、StarTools（工具类）

提供一组静态方法，用于在没有 Star 实例的上下文中（如独立的工具函数、定时任务）操作 AstrBot。

### 2.1 初始化

- `StarTools.initialize(context: Context) -> None`
  - 初始化 StarTools，需在框架启动时调用（通常由框架自动完成）

### 2.2 消息发送

- `StarTools.send_message(session, message_chain) -> bool`
  - 发送消息到指定会话
  - 参数：
    - `session`: 会话标识（字符串或 MessageSesion 对象）
    - `message_chain`: 消息链
  - 返回：是否找到匹配的平台

### 2.3 消息与事件创建

- `StarTools.create_message(type, self_id, session_id, sender, message, message_str, message_id="", raw_message=None, group_id="") -> AstrBotMessage`
  - 创建一个 AstrBot 消息对象
  - 参数：
    - `type`: 消息类型（如 `GroupMessage`、`FriendMessage`）
    - `self_id`: 机器人自身 ID
    - `session_id`: 会话 ID
    - `sender`: 发送者信息（`MessageMember`）
    - `message`: 消息组件列表
    - `message_str`: 纯文本消息
  - 返回：AstrBotMessage 对象

- `StarTools.create_event(abm, platform="aiocqhttp", is_wake=True) -> None`
  - 创建并提交事件到指定平台
  - 参数：
    - `abm`: 由 create_message 创建的消息对象
    - `platform`: 平台 ID 或名称
    - `is_wake`: 是否标记为唤醒事件

### 2.4 LLM 工具管理

- `StarTools.activate_llm_tool(name: str) -> bool`
  - 激活指定名称的函数工具

- `StarTools.deactivate_llm_tool(name: str) -> bool`
  - 停用指定名称的函数工具

- `StarTools.register_llm_tool(name, func_args, desc, func_obj) -> None`
  - 注册一个函数工具（已过时，推荐使用 `@filter.llm_tool()`）

- `StarTools.unregister_llm_tool(name: str) -> None`
  - 注销一个函数工具（已过时）

### 2.5 数据目录

- `StarTools.get_data_dir(plugin_name=None) -> Path`
  - 获取插件专属数据目录路径（`data/plugin_data/{plugin_name}`）
  - 参数：`plugin_name` 插件名，不传则自动检测调用方插件
  - 返回：目录的绝对路径（自动创建）

### 2.6 使用示例

```python
# 在定时任务中发送消息
async def my_scheduled_task():
    data_dir = StarTools.get_data_dir("my_plugin")
    # ... 业务逻辑 ...
    await StarTools.send_message(
        "aiocqhttp:group:123456",
        MessageChain().message("定时消息")
    )

# 创建消息并触发事件
async def send_custom_message():
    abm = StarTools.create_message(
        type="GroupMessage",
        self_id="robot_id",
        session_id="123456",
        sender=MessageMember(user_id="system", nickname="System"),
        message=[Plain("系统通知")],
        message_str="系统通知",
        group_id="123456"
    )
    await StarTools.create_event(abm, platform="aiocqhttp")
```

---

## 三、register（register_star 装饰器）（已过时）

### 3.1 状态：已废弃

`@register_star(name, author, desc, version, repo)` 装饰器**已废弃**，将在未来版本移除。

自 v3.5.19 起，AstrBot 通过 `__init_subclass__` 自动识别继承自 Star 的类，无需手动注册。

### 3.2 替代方案

直接在插件类的 docstring 中写帮助信息，框架会自动提取：

```python
class MyPlugin(Star):
    """这是插件的帮助信息，会被自动提取"""
    ...
```

插件元数据（名称、作者、版本等）现在通过 `_conf_schema.json` 或 `astrbot_plugin.json` 配置文件提供。

---

## 四、StarMetadata（插件元数据）

`StarMetadata` 是框架内部使用的元数据类，存储插件的所有信息。插件开发者通常不需要直接操作，但了解其字段有助于调试：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | str | 插件名称 |
| `author` | str | 插件作者 |
| `desc` | str | 插件简介 |
| `short_desc` | str | 短简介 |
| `version` | str | 版本号 |
| `repo` | str | 仓库地址 |
| `star_cls_type` | type[Star] | 插件类对象 |
| `module_path` | str | 模块路径 |
| `star_cls` | Star | 插件实例 |
| `activated` | bool | 是否已激活 |
| `config` | AstrBotConfig | 插件配置 |
| `plugin_id` | property | 唯一标识（author/name） |

---

## 五、config 模块（配置读写）（已过时）

> 注意：此模块已过时，推荐使用 `context.get_config()` 和 `context.astrbot_config_mgr`
说明位置：astrbot/core/star/config.py

位于 `astrbot.core.star.config`，提供以 namespace 为键的 JSON 配置文件读写：

- `load_config(namespace: str) -> dict | bool`
  - 加载指定 namespace 的配置，返回 dict 或 False（不存在）

- `put_config(namespace, name, key, value, description) -> None`
  - 写入配置项（仅当 key 不存在时）

- `update_config(namespace, key, value) -> None`
  - 更新已有配置项的值

配置文件路径：`data/config/{namespace}.json`

---

## 六、完整插件示例

```python
from astrbot.api.star import Context, Star
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.event.filter import EventMessageType

class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        pass

    async def terminate(self):
        pass

    @filter.command(name="hello")
    @filter.event_message_type(EventMessageType.PRIVATE)
    async def hello_handler(self, event: AstrMessageEvent):
        yield event.plain_result("你好！这是一个私聊回复。")

    @filter.on_llm_request()
    async def modify_llm_request(self, event, req):
        req.system_prompt += "\n请用友好的语气回复。"
```

---

## 七、模块关系图

```
astrbot.api.star
├── Star (基类)
│   ├── initialize() / terminate() — 生命周期
│   ├── text_to_image() / html_render() — 内置能力
│   └── __init_subclass__() — 自动注册到 star_map
│
├── Context (接口门面对象)
│   └── 详见 AstrBot-Context 类接口整理.md
│
├── StarTools (静态工具类)
│   ├── send_message() — 发消息
│   ├── create_message() / create_event() — 构造事件
│   ├── activate_llm_tool() / deactivate_llm_tool() — 工具管理
│   └── get_data_dir() — 数据目录
│
└── register (register_star)
    └── 已废弃，改用自动识别
```
# AstrBot event 模块接口整理

> 源码路径：
> - AstrMessageEvent: `../.venv/Lib/site-packages/astrbot/core/platform/astr_message_event.py`
> - MessageChain/MessageEventResult: `../.venv/Lib/site-packages/astrbot/core/message/message_event_result.py`
> 导出路径：`from astrbot.api.event import ...`

`astrbot.api.event` 是 AstrBot 的**事件与消息核心模块**，包含 6 个导出类，分为两组：
- **事件对象**：`AstrMessageEvent` — 承载一条从 IM 平台收到的消息
- **消息构建**：`MessageChain`、`MessageEventResult`、`CommandResult`、`EventResultType`、`ResultContentType` — 用于构建和发送回复消息

注意（以下内容尚未确认，但理应如此且根据 ../other 记录.md 中的 事件类的继承层次 说明，应该就是如此）：事件对象本质应该是经过包装后的继承了 `AstrMessageEvent` 的类，而不是直接使用 `AstrMessageEvent`。只不过用 `AstrMessageEvent` 来表示事件对象更通用，可以减小平台相关性。
如用`napcat` 获取的消息，应该会被包装为 `AiocqhttpMessageEvent`， 表示 aiocqhttp 平台的消息事件。

---

## 一、AstrMessageEvent（事件对象）

每条消息从 IM 平台到达时，AstrBot 会创建一个 `AstrMessageEvent` 实例并通过 Pipeline 传递给插件。你在 Handler 中接收的 `event` 参数就是它。

### 1.1 消息信息获取

- `get_message_str() -> str`
  - 获取纯文本消息内容

- `get_message_outline() -> str`
  - 获取消息概要（图片转 [图片]、At 转 [At:qq] 等）

- `get_messages() -> list[BaseMessageComponent]`
  - 获取消息链（包含所有组件）

- `get_message_type() -> MessageType`
  - 获取消息类型（群/私聊等）

### 1.2 发送者信息获取

- `get_sender_id() -> str`
  - 获取发送者 ID

- `get_sender_name() -> str`
  - 获取发送者昵称

- `get_self_id() -> str`
  - 获取机器人自身 ID

### 1.3 会话信息获取

- `get_session_id() -> str`
  - 获取会话 ID

- `get_group_id() -> str`
  - 获取群 ID（私聊返回空字符串）

- `unified_msg_origin` (属性)
  - 统一消息来源字符串，格式：`platform:type:session_id`
  - 常用于 `context.get_config(umo)` 和 `context.send_message(session, ...)`

- `session_id` (属性)
  - 会话 ID（可读写）

### 1.4 平台信息获取

- `get_platform_name() -> str`
  - 获取平台类型名称（如 `aiocqhttp`、`discord`）

- `get_platform_id() -> str`
  - 获取平台实例 ID（唯一）

### 1.5 状态判断

- `is_private_chat() -> bool`
  - 是否为私聊消息

- `is_wake_up() -> bool`
  - 是否为唤醒机器人的消息

- `is_admin() -> bool`
  - 发送者是否为管理员

- `is_stopped() -> bool`
  - 事件是否已被终止传播

- `get_result() -> MessageEventResult | None`
  - 获取当前事件的处理结果

### 1.6 事件控制

- `stop_event() -> None`
  - 终止事件传播，后续 Handler 不再执行

- `continue_event() -> None`
  - 继续事件传播（取消 stop）

- `set_result(result) -> None`
  - 设置事件处理结果
  - 参数：`MessageEventResult` 或 `str`（自动转换）

- `should_call_llm(call_llm: bool) -> None`
  - 设置是否禁止默认 LLM 请求链路
  - `True` = 禁止 AstrBot 默认的 LLM 调用，但不影响插件内的 LLM 调用

### 1.7 消息发送

- `send(message: MessageChain) -> None`
  - 发送消息到 IM 平台

- `send_streaming(generator, use_fallback=False) -> None`
  - 发送流式消息
  - 参数：异步生成器，产出 `MessageChain`
  - 支持平台：Telegram、QQ Official 私聊等

- `send_typing() -> None`
  - 发送"正在输入"状态

- `stop_typing() -> None`
  - 停止"正在输入"状态

- `react(emoji: str) -> None`
  - 对消息添加表情回应

### 1.8 结果构建（快捷方法）

- `make_result() -> MessageEventResult`
  - 创建空结果，配合链式调用 `.message()`、`.url_image()` 等

- `plain_result(text: str) -> MessageEventResult`
  - 创建纯文本结果

- `image_result(url_or_path: str) -> MessageEventResult`
  - 创建图片结果（自动判断网络/本地）

- `chain_result(chain: list) -> MessageEventResult`
  - 创建包含指定消息链的结果

### 1.9 LLM 请求构建

- `request_llm(prompt, system_prompt, image_urls, audio_urls, tool_set, contexts, conversation, session_id) -> ProviderRequest`
  - 构建一个 LLM 请求对象，用于交给 Pipeline 处理
  - 常用参数：
    - `prompt`: 提示词
    - `system_prompt`: 系统提示词
    - `image_urls`: 图片 URL 列表
    - `tool_set`: 工具集（`ToolSet`）
    - `contexts`: 多轮对话历史
    - `conversation`: 指定对话（含人格设定）

### 1.10 额外数据

- `set_extra(key, value)`
  - 设置事件的额外信息

- `get_extra(key=None, default=None)`
  - 获取额外信息

- `clear_extra()`
  - 清除所有额外信息

### 1.11 群聊操作

- `get_group(group_id=None) -> Group | None`
  - 获取群聊数据
  - 支持平台：aiocqhttp

### 1.12 使用示例

```python
@filter.command(name="hello")
async def hello_handler(self, event: AstrMessageEvent):
    # 获取消息内容
    text = event.get_message_str()

    # 获取发送者
    sender = event.get_sender_id()

    # 构建并发送回复
    yield event.plain_result(f"你好, {sender}!")

    # 终止事件传播
    # event.stop_event()

    # 获取当前会话配置
    cfg = self.context.get_config(event.unified_msg_origin)
```json

---

## 二、MessageChain（消息链）

用于构建要发送的消息内容，支持链式调用添加文本、图片、At 等组件。

### 2.1 链式构建方法

- `.message(text: str) -> MessageChain`
  - 添加文本消息

- `.at(name: str, qq: str|int) -> MessageChain`
  - 添加 @某人

- `.at_all() -> MessageChain`
  - 添加 @所有人

- `.url_image(url: str) -> MessageChain`
  - 添加网络图片

- `.file_image(path: str) -> MessageChain`
  - 添加本地图片

- `.base64_image(base64_str: str) -> MessageChain`
  - 添加 Base64 图片

- `.use_t2i(enable: bool) -> MessageChain`
  - 设置是否使用文本转图片服务

- `.use_markdown(use: bool|None) -> MessageChain`
  - 设置是否使用 Markdown 格式

### 2.2 查询方法

- `get_plain_text() -> str`
  - 获取所有文本组件拼接成的纯文本

- `squash_plain() -> MessageChain`
  - 将多个 Plain 组件合并为一个

### 2.3 使用示例

```python
# 构建复杂消息
chain = MessageChain()
chain.message("你好").at("张三", "123456").url_image("https://example.com/img.jpg")

# 简写形式（通过 event）
yield event.make_result() \
    .message("你好") \
    .at("张三", "123456") \
    .url_image("https://example.com/img.jpg")
```json

---

## 三、MessageEventResult（事件结果）

继承自 `MessageChain`，除了消息构建能力外，还增加了事件控制功能。

### 3.1 事件控制

- `stop_event() -> MessageEventResult`
  - 终止事件传播

- `continue_event() -> MessageEventResult`
  - 继续事件传播

- `is_stopped() -> bool`
  - 是否已终止

### 3.2 内容类型

- `set_result_content_type(type) -> MessageEventResult`
  - 设置结果内容类型

- `is_llm_result() -> bool`
  - 是否为 LLM 结果

- `is_model_result() -> bool`
  - 是否为模型执行结果

### 3.3 流式支持

- `set_async_stream(stream: AsyncGenerator) -> MessageEventResult`
  - 设置异步流

### 3.4 使用示例

```python
# 发送回复并终止事件（阻止后续插件处理）
result = MessageEventResult().message("处理完毕").stop_event()
yield result

# 仅发送回复，不终止
yield event.plain_result("hello")
```bash

---

## 四、CommandResult

`CommandResult = MessageEventResult` 的别名，为兼容旧代码保留。

---

## 五、EventResultType（事件结果类型枚举）

| 值 | 说明 |
|----|------|
| `CONTINUE` | 事件继续传播（默认） |
| `STOP` | 事件终止传播 |

---

## 六、ResultContentType（结果内容类型枚举）

| 值 | 说明 |
|----|------|
| `GENERAL_RESULT` | 普通消息结果（默认） |
| `LLM_RESULT` | 调用 LLM 产生的结果 |
| `STREAMING_RESULT` | 流式输出结果 |
| `STREAMING_FINISH` | 流式输出完成 |
| `AGENT_RUNNER_ERROR` | Agent Runner 返回的错误 |

---

## 七、消息组件

`MessageChain` 中使用的组件类，从 `astrbot.api.message_components` 导入：

| 组件 | 说明 |
|------|------|
| `Plain` | 纯文本 |
| `Image` | 图片（支持 URL/本地/Base64） |
| `At` | @某人 |
| `AtAll` | @所有人 |
| `Face` | 表情 |
| `Forward` | 转发消息 |
| `Reply` | 引用回复 |
| `Json` | JSON 消息 |

使用时从 `from astrbot.api.message_components import Plain, Image, At` 导入。

# 从哪里可以导入消息组件？

我要怎么知道 event 的哪些方法是只有特定平台能用的呢？

好问题！这涉及到 AstrBot 的事件继承体系。让我分析一下：

## 一、事件类的继承层次

```text
AstrMessageEvent（基类，通用方法）
    ├── AiocqhttpMessageEvent（QQ/OneBot v11 特有）
    ├── DiscordPlatformEvent（Discord 特有）
    ├── TelegramPlatformEvent（Telegram 特有）
    ├── ...（其他平台）
```bash

**文件**：../.venv/Lib/site-packages/astrbot/core/platform/astr_message_event.py

## 二、通用方法（所有平台都有）

这些方法在 `AstrMessageEvent` 基类中定义：

| 方法 | 说明 |
|------|------|
| `get_message_str()` | 获取纯文本消息 |
| `get_messages()` | 获取消息组件列表 |
| `get_sender()` | 获取发送者信息 |
| `get_group()` | 获取群信息 |
| `get_platform_name()` | 获取平台名称 |
| `make_result()` | 创建消息结果 |
| `send(result)` | 发送消息 |
| `stop_event()` | 停止事件传播 |

## 三、平台特定方法

这些方法在各平台的事件子类中定义：

### QQ (aiocqhttp)

**文件**：../.venv/Lib/site-packages/astrbot/core/platform/sources/aiocqhttp/aiocqhttp_message_event.py

```python
class AiocqhttpMessageEvent(AstrMessageEvent):
    # QQ 特有方法
    def get_reply_id(self) -> int | None:
        """获取回复消息 ID"""
    
    def is_group_admin(self) -> bool:
        """是否是群管理员"""
    
    def is_group_owner(self) -> bool:
        """是否是群主"""
    
    # 还有更多平台特定属性
    _raw_event: dict  # 原始 OneBot 事件数据
```bash

### Discord

**文件**：../.venv/Lib/site-packages/astrbot/core/platform/sources/discord/discord_platform_event.py

```python
class DiscordPlatformEvent(AstrMessageEvent):
    # Discord 特有方法/属性
    _message: discord.Message  # 原始 discord.py 消息对象
```bash

### Telegram

**文件**：../.venv/Lib/site-packages/astrbot/core/platform/sources/telegram/tg_event.py

```python
class TelegramPlatformEvent(AstrMessageEvent):
    # Telegram 特有方法/属性
    _update: Update  # 原始 python-telegram-bot 更新对象
```bash

## 四、如何判断方法是否通用

### 方法一：看类型提示

```python
from astrbot.api.event import AstrMessageEvent

async def handler(self, event: AstrMessageEvent):
    # event 的类型是 AstrMessageEvent，只能调用基类方法
    # 如果需要平台特定方法，需要类型断言
    if isinstance(event, AiocqhttpMessageEvent):
        reply_id = event.get_reply_id()  # QQ 特有
```bash

### 方法二：检查平台名称

```python
@filter.command("test")
async def test(self, event):
    platform = event.get_platform_name()
    
    if platform == "aiocqhttp":
        # QQ 平台，可以使用 QQ 特有方法
        # 但需要小心，因为 event 的类型还是 AstrMessageEvent
        # 需要通过 isinstance 判断或直接访问属性
        if hasattr(event, 'is_group_admin'):
            is_admin = event.is_group_admin()
    
    elif platform == "discord":
        # Discord 平台
        pass
```bash

### 方法三：使用 `isinstance` 判断

```python
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent

@filter.command("admin")
async def check_admin(self, event):
    if isinstance(event, AiocqhttpMessageEvent):
        # 安全地调用 QQ 特有方法
        is_admin = event.is_group_admin()
        yield event.make_result().message(f"是否管理员: {is_admin}")
    else:
        yield event.make_result().message("此命令仅支持 QQ 平台")
```bash

## 五、实际案例：跨平台兼容

```python
@filter.command("info")
async def get_info(self, event):
    platform = event.get_platform_name()
    
    info = []
    
    # 通用信息（所有平台）
    sender = event.get_sender()
    info.append(f"发送者: {sender.nickname}")
    
    group = event.get_group()
    if group:
        info.append(f"群名称: {group.name}")
    
    # 平台特定信息
    if platform == "aiocqhttp":
        from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
        
        if isinstance(event, AiocqhttpMessageEvent):
            info.append(f"是否管理员: {event.is_group_admin()}")
            info.append(f"是否群主: {event.is_group_owner()}")
    
    elif platform == "discord":
        from astrbot.core.platform.sources.discord.discord_platform_event import DiscordPlatformEvent
        
        if isinstance(event, DiscordPlatformEvent):
            # Discord 特有属性
            raw_message = event._message
            info.append(f"消息 ID: {raw_message.id}")
    
    yield event.make_result().message("\n".join(info))
```text

## 六、总结

| 判断方式 | 适用场景 |
|---------|---------|
| `event.get_platform_name()` | 运行时判断平台 |
| `isinstance(event, PlatformEventClass)` | 类型安全地调用平台特定方法 |
| `hasattr(event, 'method_name')` | 运行时检查方法是否存在 |

**核心原则**：
- 如果方法在 `AstrMessageEvent` 基类中定义 → **所有平台通用**
- 如果方法只在某个平台的事件子类中定义 → **平台特定**

你可以通过查看 `AstrMessageEvent` 的源码来确认哪些方法是通用的，然后查看各个平台的事件类来了解平台特定方法。

# 注意：AstrBot的管线在接收到消息时会根据平台判断，然后会将 AstrBotMessage 包装为特定平台实现的继承类
   
是的，你的理解完全正确！让我用代码来验证：

## 流程分析

### 1. 基类 `Platform.create_event`

**文件**：../.venv/Lib/site-packages/astrbot/core/platform/platform.py#L150

```python
def create_event(self, message: AstrBotMessage) -> AstrMessageEvent:
    return AstrMessageEvent(
        message_str=message.message_str,
        message_obj=message,
        platform_meta=self.meta(),
        session_id=message.session_id,
    )
```bash

### 2. 各平台适配器重写 `create_event`

**QQ (aiocqhttp)**：../.venv/Lib/site-packages/astrbot/core/platform/sources/aiocqhttp/aiocqhttp_platform_adapter.py#L492

```python
def create_event(self, message: AstrBotMessage) -> AiocqhttpMessageEvent:
    return AiocqhttpMessageEvent(
        message_str=message.message_str,
        message_obj=message,
        platform_meta=self.meta(),
        session_id=message.session_id,
        bot=self.bot,  # QQ 特有：CQHttp 客户端对象
    )
```text

**Discord**：../.venv/Lib/site-packages/astrbot/core/platform/sources/discord/discord_platform_adapter.py#L280

```python
def create_event(self, message: AstrBotMessage, ...) -> DiscordPlatformEvent:
    return DiscordPlatformEvent(
        message_str=message.message_str,
        message_obj=message,
        platform_meta=self.meta(),
        session_id=message.session_id,
        _message=discord_message,  # Discord 特有：原始 Message 对象
    )
```text

**Telegram**：../.venv/Lib/site-packages/astrbot/core/platform/sources/telegram/tg_adapter.py#L739

```python
def create_event(self, message: AstrBotMessage) -> TelegramPlatformEvent:
    return TelegramPlatformEvent(
        message_str=message.message_str,
        message_obj=message,
        platform_meta=self.meta(),
        session_id=message.session_id,
        _update=update,  # Telegram 特有：原始 Update 对象
    )
```bash

---

## 完整流程

```text
用户发送消息
    ↓
平台适配器收到消息（aiocqhttp / discord / telegram 等）
    ↓
适配器将原始消息转换为 AstrBotMessage（统一格式）
    ↓
调用 self.create_event(message)  ← 关键步骤！
    ↓
根据平台类型创建对应的事件类：
    - aiocqhttp → AiocqhttpMessageEvent(AstrMessageEvent)
    - discord → DiscordPlatformEvent(AstrMessageEvent)
    - telegram → TelegramPlatformEvent(AstrMessageEvent)
    - ...
    ↓
调用 self.commit_event(event) 提交到事件队列
    ↓
Pipeline 处理事件
    ↓
路由到插件 Handler
    ↓
插件拿到的 event 实际上是特定平台的子类实例
```bash

---

## 结论

**是的，AstrBot 的管线在接收到消息时会根据平台判断，将 `AstrBotMessage` 包装为特定平台实现的继承类。**

每个平台适配器都会**重写** `create_event` 方法，返回自己平台特定的事件类。这些子类：
- 继承自 `AstrMessageEvent`（基类）
- 包含平台特定的属性和方法
- 保留了基类的所有通用方法

所以在插件中：
```python
@filter.command("test")
async def test(self, event):
    # event 的类型是 AstrMessageEvent（类型提示）
    # 但实际运行时它是 AiocqhttpMessageEvent / DiscordPlatformEvent 等子类
    
    # 通用方法（所有平台都能用）
    await event.send(event.make_result().message("Hello"))
    
    # 平台特定方法（需要 isinstance 判断）
    if isinstance(event, AiocqhttpMessageEvent):
        is_admin = event.is_group_admin()  # QQ 特有
```
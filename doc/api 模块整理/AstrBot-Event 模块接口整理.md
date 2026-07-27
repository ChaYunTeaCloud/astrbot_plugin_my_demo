# AstrBot event 模块接口整理

> 源码路径：
> - AstrMessageEvent: `.astrbot/core/platform/astr_message_event.py`
> - MessageChain/MessageEventResult: `.astrbot/core/message/message_event_result.py`
> 导出路径：`from astrbot.api.event import ...`

`astrbot.api.event` 是 AstrBot 的**事件与消息核心模块**，包含 6 个导出类，分为两组：
- **事件对象**：`AstrMessageEvent` — 承载一条从 IM 平台收到的消息
- **消息构建**：`MessageChain`、`MessageEventResult`、`CommandResult`、`EventResultType`、`ResultContentType` — 用于构建和发送回复消息

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
```

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
```

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
```

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
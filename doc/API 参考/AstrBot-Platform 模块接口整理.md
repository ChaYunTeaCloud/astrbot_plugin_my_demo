# AstrBot Platform 模块接口整理

> 源码路径：
> - Platform/AstrBotMessage/Group/MessageMember/MessageType: `../.venv/Lib/site-packages/astrbot/core/platform/`
> - 消息组件: `../.venv/Lib/site-packages/astrbot/core/message/components.py`
> - 注册装饰器: `../.venv/Lib/site-packages/astrbot/core/platform/register.py`
> 导出路径：`from astrbot.api.platform import ...`

`astrbot.api.platform` 是 AstrBot 的**平台适配器与消息载体模块**，包含 8 个导出项：
- **消息组件**：`Plain`、`Image`、`Record`、`Video`、`File`、`Face`、`At`、`AtAll`、`Node`、`Nodes`、`Poke`、`Reply`、`Forward`、`RPS`、`Dice`、`Shake`、`Share`、`Contact`、`Location`、`Music`、`Json`、`Unknown`、`BaseMessageComponent`、`ComponentType`
- **消息载体**：`AstrBotMessage`、`Group`、`MessageMember`、`MessageType`
- **平台适配器**：`Platform`、`PlatformMetadata`、`register_platform_adapter`

注意：`AstrMessageEvent` 虽然在 `astrbot.api.platform` 中重新导出，但已在 Event 模块文档中单独整理。

## 其它说明

此文档覆盖了 `astrbot.api.platform` 的所有导出内容：

1. **消息组件**（22 个类）：Plain、Image、Record、Video、File、Face、At、Poke、Reply、Forward、Node、Nodes、RPS、Dice、Shake、Share、Contact、Location、Music、Json、Unknown、BaseMessageComponent
2. **消息载体**：AstrBotMessage、Group、MessageMember、MessageType
3. **平台适配器**：Platform（基类）、PlatformMetadata（元数据）、register_platform_adapter（注册装饰器）
4. **内部辅助类**：PlatformStatus、PlatformError、MessageSession

关于 `Platform` 基类的说明：它是适配器开发的核心，包含生命周期、状态管理、消息操作等多套方法。如果你后续有开发自定义平台适配器的需求，可以考虑单独整理一份 `AstrBot-Platform 适配器开发指南`。目前普通插件开发不太会直接用到它，所以在文档中做了提示但没有展开太深。

## 与 Event 模块的关系

看 `AstrMessageEvent` 的构造函数：

```python
def __init__(
    self,
    message_str: str,
    message_obj: AstrBotMessage,
    platform_meta: PlatformMetadata,
    session_id: str,
):
```

`event` 对象持有：

| 属性 | 来源 |
|------|------|
| `message_obj` | `AstrBotMessage` 实例（消息内容、发送者、群组等） |
| `platform_meta` | `PlatformMetadata` 实例（平台类型、描述等） |

由此可知，AstrBot会把 AstrBot Message 和 PlatformMetadata 丢给 event。
所以在 Handler 中可以通过：

- `event.message_obj` 拿到原始消息对象
- `event.platform_meta` 拿到平台元信息

而 `event.get_sender()`、`event.get_group()` 这些快捷方法，本质上就是访问 `self.message_obj.sender`、`self.message_obj.group`。

---

## 一、消息组件（Message Components）

消息组件是构成消息链的基本单元，每条消息由一个或多个 `BaseMessageComponent` 子类实例组成。

### 1.1 基础组件

- `Plain(text: str)`
  - 纯文本消息

- `Image(image: str)`
  - 图片消息，支持 URL、本地路径、base64、file:// 四种格式

- `Record(file: str)`
  - 音频消息

- `Video(file: str)`
  - 视频消息

- `File(file: str)`
  - 文件附件

### 1.2 IM 平台特有组件

- `Face(id: int)`
  - QQ 表情

- `At(qq: str)`
  - @某人

- `AtAll()`
  - @所有人

- `Poke(poke: str)`
  - 戳一戳

- `Reply(id: str)`
  - 回复消息

- `Forward(id: str)`
  - 转发消息

- `Node(id: str)`
  - 合并转发中的单个节点

- `Nodes(items: list[Node])`
  - 合并转发

### 1.3 其他组件

- `RPS()`
  - 猜拳

- `Dice()`
  - 骰子

- `Shake()`
  - 抖动

- `Share(url: str)`
  - 分享链接

- `Contact(qq: str)`
  - 分享名片

- `Location(latitude: float, longitude: float, title: str)`
  - 位置

- `Music(title: str, url: str)`
  - 音乐

- `Json(data: str)`
  - JSON 消息

- `Unknown()`
  - 未知消息类型

### 1.4 ComponentType（组件类型枚举）

用于标识组件的类型，值为字符串：
- `Plain`、`Image`、`Record`、`Video`、`File`
- `Face`、`At`、`Node`、`Nodes`、`Poke`、`Reply`、`Forward`
- `RPS`、`Dice`、`Shake`、`Share`、`Contact`、`Location`、`Music`
- `Json`、`Unknown`

---

## 二、AstrBotMessage（统一消息对象）

`AstrBotMessage` 是 AstrBot 在各 IM 平台之上统一的消息数据结构。平台适配器将原始平台消息转换为 `AstrBotMessage`，框架再将其包装为 `AstrMessageEvent` 传递给插件。

### 属性

- `type: MessageType`
  - 消息类型（群/私聊/其他）

- `self_id: str`
  - 机器人自身的识别 ID

- `session_id: str`
  - 会话 ID，取决于 `unique_session` 设置

- `message_id: str`
  - 消息唯一 ID

- `group: Group | None`
  - 群组信息，私聊时为 None

- `sender: MessageMember`
  - 发送者信息

- `message: list[BaseMessageComponent]`
  - 消息链（组件列表）

- `message_str: str`
  - 纯文本消息内容

- `raw_message: object`
  - 原始平台消息对象

- `timestamp: int`
  - 消息时间戳

### group_id 属性

- `group_id: str`（property）
  - 向后兼容的快捷属性，等价于 `group.group_id`
  - 私聊时返回空字符串

---

## 三、Group（群组信息）

`@dataclass`，描述一个群组的元数据。

### 属性

- `group_id: str`
  - 群号

- `group_name: str | None`
  - 群名称

- `group_avatar: str | None`
  - 群头像

- `group_owner: str | None`
  - 群主 ID

- `group_admins: list[str] | None`
  - 群管理员 ID 列表

- `members: list[MessageMember] | None`
  - 群成员列表

---

## 四、MessageMember（成员信息）

`@dataclass`，描述一个群成员/发送者的基本信息。

### 属性

- `user_id: str`
  - 用户 ID

- `nickname: str | None`
  - 昵称

---

## 五、MessageType（消息类型枚举）

| 值 | 说明 |
|----|------|
| `GROUP_MESSAGE` | 群组消息 |
| `FRIEND_MESSAGE` | 私聊/好友消息 |
| `OTHER_MESSAGE` | 其他类型（系统消息等） |

---

## 六、Platform（平台适配器基类）

`Platform` 是所有平台适配器的抽象基类。如果你需要开发自定义平台适配器（接入新的 IM 平台），需要继承此类。

> 此接口较大，如果你计划开发自定义平台适配器，建议单独深入阅读源码。

### 6.1 生命周期方法

- `run() -> Coroutine`（抽象方法）
  - 返回平台的运行协程，由框架 `asyncio.create_task()` 调度
  - 必须由子类实现

- `terminate() -> None`
  - 终止平台运行
  - 子类可覆盖实现清理逻辑

- `meta() -> PlatformMetadata`（抽象方法）
  - 返回平台元数据
  - 必须由子类实现

### 6.2 状态管理

- `status: PlatformStatus`（property）
  - 当前运行状态：`PENDING` / `RUNNING` / `ERROR` / `STOPPED`

- `errors: list[PlatformError]`（property）
  - 错误记录列表

- `last_error: PlatformError | None`（property）
  - 最近的一条错误

- `record_error(message: str, traceback_str: str | None)`
  - 记录一个错误并将状态置为 ERROR

- `clear_errors()`
  - 清除错误记录，若状态为 ERROR 则恢复为 RUNNING

### 6.3 消息操作

- `create_event(message: AstrBotMessage) -> AstrMessageEvent`
  - 将 `AstrBotMessage` 包装为 `AstrMessageEvent`

- `commit_event(event: AstrMessageEvent)`
  - 将事件提交到事件队列，供 EventBus 消费

- `send_by_session(session: MessageSession, message_chain: MessageChain)`
  - 通过持久化会话发送消息，无需保存 event 对象

### 6.4 其他

- `get_stats() -> dict`
  - 获取平台统计信息（状态、运行时间、错误数等）

- `unified_webhook() -> bool`
  - 是否启用了统一 Webhook 模式

- `get_client() -> object`
  - 获取平台底层客户端对象

- `webhook_callback(request: Any) -> Any`
  - 统一 Webhook 回调入口，需支持 Webhook 的平台实现

---

## 七、PlatformMetadata（平台元数据）

`@dataclass`，描述一个平台适配器的元信息。

### 属性

- `name: str`
  - 平台类型名称，如 `aiocqhttp`、`discord`、`slack`

- `description: str`
  - 平台描述

- `id: str`
  - 平台唯一标识符，用于配置中识别

- `default_config_tmpl: dict | None`
  - 默认配置模板，用户填写后作为 `config` 传入 Platform 实例

- `adapter_display_name: str | None`
  - WebUI 中显示的平台名称，默认使用 `name`

- `logo_path: str | None`
  - 适配器 logo 路径（相对于插件目录）

- `support_streaming_message: bool`
  - 是否支持真实流式传输，默认 `True`

- `support_proactive_message: bool`
  - 是否支持主动消息推送，默认 `True`

- `module_path: str | None`
  - 注册该适配器的模块路径，用于热重载时清理

- `i18n_resources: dict | None`
  - 国际化资源数据

- `config_metadata: dict | None`
  - 配置项元数据，用于 WebUI 生成表单

---

## 八、register_platform_adapter（注册装饰器）

用于将一个 `Platform` 子类注册到框架中。注册后框架能识别并加载该平台适配器。

### 参数

- `adapter_name: str`
  - 适配器名称（必填），需唯一

- `desc: str`
  - 描述（必填）

- `default_config_tmpl: dict | None`
  - 默认配置模板。框架会自动补充 `type`、`enable`、`id` 字段

- `adapter_display_name: str | None`
  - WebUI 显示名称

- `logo_path: str | None`
  - Logo 路径

- `support_streaming_message: bool`
  - 是否支持流式，默认 `True`

- `i18n_resources: dict | None`
  - 国际化资源

- `config_metadata: dict | None`
  - 配置项元数据

### 使用示例

```python
from astrbot.api.platform import Platform, PlatformMetadata, register_platform_adapter

@register_platform_adapter(
    adapter_name="my_platform",
    desc="我的自定义平台",
    default_config_tmpl={"token": "", "enable": True},
)
class MyPlatform(Platform):
    async def run(self):
        # 启动平台连接逻辑
        ...

    def meta(self) -> PlatformMetadata:
        return PlatformMetadata(
            name="my_platform",
            description="我的自定义平台",
            id="my_platform",
        )
```

---

## 九、内部辅助类

以下类不直接导出给插件开发者使用，但在平台适配器开发和理解消息流程时很重要。

### PlatformStatus（枚举）

| 值 | 说明 |
|----|------|
| `PENDING` | 待启动 |
| `RUNNING` | 运行中 |
| `ERROR` | 发生错误 |
| `STOPPED` | 已停止 |

### PlatformError（数据类）

- `message: str` — 错误信息
- `timestamp: datetime` — 错误时间
- `traceback: str | None` — 错误堆栈

### MessageSession（会话标识）

`@dataclass`，用于唯一标识一个消息会话，支持 `Platform.send_by_session()`。

- `platform_name: str` — 平台适配器实例标识
- `message_type: MessageType` — 消息类型
- `session_id: str` — 会话 ID
- `from_str(session_str: str)`（静态方法）— 从字符串解析

---

## 十、模块关系

```text
astrbot.api.platform
├── 消息组件 (components.py)
│   ├── Plain / Image / Record / Video / File  ... 基础组件
│   ├── Face / At / Poke / Reply / Forward ... IM 特有组件
│   └── ComponentType (枚举)
│
├── 消息载体
│   ├── AstrBotMessage  ← 统一消息结构
│   ├── Group           ← 群组信息
│   ├── MessageMember   ← 成员信息
│   └── MessageType     ← 消息类型枚举
│
├── 平台适配器
│   ├── Platform           ← 抽象基类（较大，建议单独阅读）
│   ├── PlatformMetadata   ← 适配器元数据
│   └── register_platform_adapter  ← 注册装饰器
│
└── (AstrMessageEvent)  ← 已在 Event 模块单独整理
```

---

## 十一、与插件开发者的关系

对普通插件开发者来说，Platform 模块的使用频率低于 Event/Star/Context：

- **日常开发**：你主要通过 `event`（AstrMessageEvent）和 `context` 与框架交互，不需要直接接触 Platform
- **消息构建**：使用 `Plain`、`Image` 等组件构建回复消息链
- **高级场景**：`event.get_sender()` 返回 `MessageMember`，`event.get_group()` 返回 `Group`
- **适配器开发**：如果你想接入新的 IM 平台（如自建聊天系统），才需要继承 `Platform` 并使用 `register_platform_adapter`

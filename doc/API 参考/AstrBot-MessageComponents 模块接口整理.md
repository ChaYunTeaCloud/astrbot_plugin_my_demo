# AstrBot MessageComponents 模块接口整理

> 源码路径：
> - API 导出: `../.venv/Lib/site-packages/astrbot/api/message_components.py`
> - 实现: `../.venv/Lib/site-packages/astrbot/core/message/components.py`

---

## 一、模块概述

`api.message_components` 模块提供消息组件系统，用于构造和处理多平台消息。消息链（MessageChain）是一个有序列表，每个元素是一个消息组件（MessageComponent），如文本、图片、@人、语音等。

**使用方式**：

```python
import astrbot.api.message_components as Comp

chain = [
    Comp.Plain(text="Hello"),
    Comp.Image(url="https://example.com/image.jpg"),
    Comp.At(qq=123456),
]
```

---

## 二、API 导出

**文件**：../.venv/Lib/site-packages/astrbot/api/message_components.py

```python
from astrbot.core.message.components import *
```

直接导出 `core/message/components.py` 中的所有内容。

---

## 三、基础类

### 3.1 ComponentType（组件类型枚举）

**文件**：../.venv/Lib/site-packages/astrbot/core/message/components.py#L44

```python
class ComponentType(str, Enum):
    Plain = "Plain"
    Image = "Image"
    Record = "Record"
    Video = "Video"
    File = "File"
    Face = "Face"
    At = "At"
    Node = "Node"
    Nodes = "Nodes"
    Poke = "Poke"
    Reply = "Reply"
    Forward = "Forward"
    RPS = "RPS"
    Dice = "Dice"
    Shake = "Shake"
    Share = "Share"
    Contact = "Contact"
    Location = "Location"
    Music = "Music"
    Json = "Json"
    Unknown = "Unknown"
```

### 3.2 BaseMessageComponent（消息组件基类）

**文件**：../.venv/Lib/site-packages/astrbot/core/message/components.py#L71

所有消息组件的基类。

**属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `type` | `ComponentType` | 组件类型 |

**方法**：

| 方法 | 说明 |
|------|------|
| `toDict()` | 同步转换为字典格式 |
| `to_dict()` | 异步转换为字典格式（默认回退到 toDict） |

---

## 四、消息组件详解

### 4.1 Plain（文本消息）

**文件**：../.venv/Lib/site-packages/astrbot/core/message/components.py#L111

```python
class Plain(BaseMessageComponent):
    type: ComponentType = ComponentType.Plain
    text: str

    def __init__(self, text: str, convert: bool = True) -> None:
```

**使用示例**：

```python
Comp.Plain(text="Hello World")
```

### 4.2 Image（图片消息）

**文件**：../.venv/Lib/site-packages/astrbot/core/message/components.py#L499

**属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `file` | `str \| None` | 文件路径/URL/base64 |
| `url` | `str \| None` | 备用 URL |
| `path` | `str \| None` | 本地路径 |

**静态方法**：

| 方法 | 说明 |
|------|------|
| `Image.fromURL(url)` | 从 URL 创建 |
| `Image.fromFileSystem(path)` | 从本地文件创建 |
| `Image.fromBase64(base64)` | 从 base64 创建 |
| `Image.fromBytes(byte)` | 从字节创建 |
| `Image.fromIO(IO)` | 从文件对象创建 |

**异步方法**：

| 方法 | 说明 |
|------|------|
| `convert_to_file_path()` | 转换为本地文件路径 |
| `convert_to_base64()` | 转换为 base64 编码 |
| `register_to_file_service()` | 注册到文件服务 |

**使用示例**：

```python
# 从 URL
Comp.Image.fromURL("https://example.com/image.jpg")

# 从本地文件
Comp.Image.fromFileSystem("path/to/image.png")

# 从 base64
Comp.Image.fromBase64("iVBORw0KGgo...")

# 直接创建
Comp.Image(file="path/to/image.png")
```

### 4.3 Record（语音消息）

**文件**：../.venv/Lib/site-packages/astrbot/core/message/components.py#L133

**属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `file` | `str \| None` | 文件路径/URL/base64 |
| `url` | `str \| None` | 备用 URL |
| `text` | `str \| None` | 原始文本内容（TTS 源文本） |
| `path` | `str \| None` | 本地路径 |

**静态方法**：

| 方法 | 说明 |
|------|------|
| `Record.fromFileSystem(path)` | 从本地文件创建 |
| `Record.fromURL(url)` | 从 URL 创建 |
| `Record.fromBase64(base64)` | 从 base64 创建 |

**异步方法**：

| 方法 | 说明 |
|------|------|
| `convert_to_file_path()` | 转换为本地文件路径（自动转为 wav） |
| `convert_to_base64()` | 转换为 base64 编码 |
| `register_to_file_service()` | 注册到文件服务 |

### 4.4 Video（视频消息）

**文件**：../.venv/Lib/site-packages/astrbot/core/message/components.py#L286

**属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `file` | `str` | 文件路径/URL/base64 |
| `url` | `str \| None` | 备用 URL |
| `cover` | `str \| None` | 封面图 |
| `path` | `str \| None` | 本地路径 |

**静态方法**：

| 方法 | 说明 |
|------|------|
| `Video.fromFileSystem(path)` | 从本地文件创建 |
| `Video.fromURL(url)` | 从 URL 创建 |
| `Video.fromBase64(base64)` | 从 base64 创建 |

**异步方法**：

| 方法 | 说明 |
|------|------|
| `convert_to_file_path()` | 转换为本地文件路径 |
| `register_to_file_service()` | 注册到文件服务 |

### 4.5 File（文件消息）

**文件**：../.venv/Lib/site-packages/astrbot/core/message/components.py#L761

**属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str \| None` | 文件名 |
| `file_` | `str \| None` | 本地路径 |
| `url` | `str \| None` | 下载 URL |

**注意**：`file` 是属性（getter/setter），内部存储在 `file_` 中。

**方法**：

| 方法 | 说明 |
|------|------|
| `get_file(allow_return_url=False)` | 异步获取文件路径 |
| `register_to_file_service()` | 注册到文件服务 |

**使用示例**：

```python
Comp.File(name="report.pdf", file="path/to/report.pdf")
Comp.File(name="data.zip", url="https://example.com/data.zip")
```

### 4.6 At（@消息）

**文件**：../.venv/Lib/site-packages/astrbot/core/message/components.py#L408

```python
class At(BaseMessageComponent):
    type: ComponentType = ComponentType.At
    qq: int | str  # str="all" 时代表所有人
    name: str | None = ""
```

**使用示例**：

```python
# @指定用户
Comp.At(qq=123456, name="用户名")

# @所有人
Comp.At(qq="all")
```

### 4.7 AtAll（@所有人）

**文件**：../.venv/Lib/site-packages/astrbot/core/message/components.py#L423

`At` 的子类，`qq="all"`。

```python
Comp.AtAll()
```

### 4.8 Reply（回复消息）

**文件**：../.venv/Lib/site-packages/astrbot/core/message/components.py#L582

**属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `id` | `str \| int` | 引用的消息 ID |
| `chain` | `list[BaseMessageComponent] \| None` | 被引用的消息段列表 |
| `sender_id` | `int \| None \| str` | 发送者 ID |
| `sender_nickname` | `str \| None` | 发送者昵称 |
| `time` | `int \| None` | 发送时间 |
| `message_str` | `str \| None` | 纯文本内容 |

**使用示例**：

```python
Comp.Reply(id="msg_123")
```

### 4.9 Face（QQ 表情）

**文件**：../.venv/Lib/site-packages/astrbot/core/message/components.py#L125

```python
class Face(BaseMessageComponent):
    type: ComponentType = ComponentType.Face
    id: int
```

**使用示例**：

```python
Comp.Face(id=123)
```

### 4.10 Poke（戳一戳）

**文件**：../.venv/Lib/site-packages/astrbot/core/message/components.py#L612

**属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `_type` | `str \| int` | 戳一戳类型，默认 "126" |
| `id` | `int \| str \| None` | 目标用户 ID |

**使用示例**：

```python
# 普通戳一戳
Comp.Poke()

# 指定目标
Comp.Poke(id=123456)
```

### 4.11 Node（合并转发节点）

**文件**：../.venv/Lib/site-packages/astrbot/core/message/components.py#L653

**属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str \| None` | 昵称 |
| `uin` | `str \| None` | 用户 ID |
| `content` | `list[BaseMessageComponent]` | 消息内容 |

**使用示例**：

```python
node = Comp.Node(
    name="用户A",
    uin="123456",
    content=[Comp.Plain(text="Hello")]
)
```

### 4.12 Nodes（合并转发消息）

**文件**：../.venv/Lib/site-packages/astrbot/core/message/components.py#L707

```python
class Nodes(BaseMessageComponent):
    type: ComponentType = ComponentType.Nodes
    nodes: list[Node]
```

**使用示例**：

```python
nodes = Comp.Nodes([
    Comp.Node(name="用户A", uin="123456", content=[Comp.Plain(text="Hello")]),
    Comp.Node(name="用户B", uin="654321", content=[Comp.Plain(text="Hi")]),
])
```

### 4.13 Share（分享消息）

**文件**：../.venv/Lib/site-packages/astrbot/core/message/components.py#L451

```python
class Share(BaseMessageComponent):
    type: ComponentType = ComponentType.Share
    url: str
    title: str
```

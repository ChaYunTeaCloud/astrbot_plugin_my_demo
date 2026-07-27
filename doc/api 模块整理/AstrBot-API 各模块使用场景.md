# AstrBot API 各模块使用场景

> 本文档总结 AstrBot API 各模块的使用频率和典型场景，帮助插件开发者快速判断何时使用哪个模块。

---

## 一、模块使用频率总览

| 模块 | 使用频率 | 典型场景 |
|------|---------|---------|
| `api.event` | ⭐⭐⭐⭐⭐ | 所有插件必用，注册命令和事件钩子 |
| `api.star` | ⭐⭐⭐⭐⭐ | 所有插件必用，插件基类和工具方法 |
| `api.message_components` | ⭐⭐⭐⭐ | 构造丰富的消息内容 |
| `api.platform` | ⭐⭐ | 访问消息对象、开发自定义平台适配器 |
| `api.provider` | ⭐ | 开发自定义 AI 适配器、高级 AI 调用 |

---

## 二、各模块详细说明

### 2.1 api.event（事件模块）

**使用频率**：⭐⭐⭐⭐⭐（所有插件必用）

**典型场景**：

1. **注册命令处理器**
   ```python
   from astrbot.api.event import filter

   @filter.command("hello")
   async def hello_command(self, event):
       yield event.make_result().message("Hello World!")
   ```

2. **监听特定事件**
   ```python
   @filter.on_llm_request()
   async def modify_llm_request(self, event, req):
       # 修改 LLM 请求
       req.system_prompt = "你是一个友好的助手"
   ```

3. **注册 LLM 工具**
   ```python
   @filter.llm_tool("get_weather")
   async def get_weather(self, tool_call):
       return "晴天，25°C"
   ```

4. **自定义筛选器**
   ```python
   @filter.regex(r"^weather\s+(.*)")
   async def weather_query(self, event, match):
       city = match.group(1)
       ...
   ```

**常用导出**：`filter`（命名空间）、`AstrMessageEvent`、`MessageChain`、`MessageEventResult`

**详细文档**：见 [AstrBot-Event 模块接口整理.md](./AstrBot-Event%20模块接口整理.md)、[AstrBot-Event-filter 装饰器整理.md](./AstrBot-Event-filter%20装饰器整理.md)

---

### 2.2 api.star（插件基础模块）

**使用频率**：⭐⭐⭐⭐⭐（所有插件必用）

**典型场景**：

1. **创建插件类**
   ```python
   from astrbot.api.star import Star

   class MyPlugin(Star):
       def __init__(self, context):
           super().__init__(context)

       async def initialize(self):
           # 插件初始化
           pass

       async def terminate(self):
           # 插件终止
           pass
   ```

2. **使用 StarTools 静态方法**
   ```python
   from astrbot.api.star import StarTools

   data_dir = StarTools.get_data_dir(self)
   await StarTools.send_message(event, "Hello")
   ```

3. **获取配置**
   ```python
   class MyPlugin(Star):
       def __init__(self, context):
           super().__init__(context)
           self.my_config = context.get_config("my_plugin")
   ```

**常用导出**：`Star`、`StarTools`、`Context`（通过 `context` 参数获得）

**详细文档**：见 [AstrBot-Star 模块接口整理.md](./AstrBot-Star%20模块接口整理.md)、[AstrBot-Context 类接口整理.md](./AstrBot-Context%20类接口整理.md)

---

### 2.3 api.message_components（消息组件模块）

**使用频率**：⭐⭐⭐⭐（需要发送富文本消息时）

**典型场景**：

1. **构造消息组件**
   ```python
   from astrbot.api.message_components import Plain, Image, At, Reply

   chain = [
       Plain(text="这是一条消息"),
       Image(url="https://example.com/image.jpg"),
       At(qq=123456),
       Reply(id="msg_id"),
   ]
   ```

2. **通过 event.send() 发送**
   ```python
   result = event.make_result()
   result.chain = chain
   yield result
   ```

3. **通过 MessageEventResult 构造回复**
   ```python
   from astrbot.api.event import MessageEventResult

   result = MessageEventResult()
   result.chain = [Plain(text="Hello"), Image(file="local.png")]
   yield result
   ```

**常用组件**：`Plain`、`Image`、`Record`、`Video`、`File`、`At`、`Reply`、`Node`、`Nodes` 等 20+ 种

---

### 2.4 api.platform（平台模块）

**使用频率**：⭐⭐（普通插件少用，平台适配器开发常用）

**典型场景**：

1. **开发自定义平台适配器**
   ```python
   from astrbot.api.platform import Platform, register_platform_adapter

   @register_platform_adapter("my_platform", "我的平台")
   class MyPlatform(Platform):
       async def connect(self):
           ...
   ```

2. **访问消息对象详情**
   ```python
   @filter.command("info")
   async def get_info(self, event):
       sender = event.message_obj.sender  # 发送者详情
       group = event.message_obj.group  # 群详情
       platform_id = event.platform_meta.id  # 平台 ID
   ```

3. **构造平台相关消息**
   ```python
   from astrbot.api.platform import Face, Poke, Share

   chain = [
       Face(id=123),
       Poke(id=1),
       Share(url="https://example.com"),
   ]
   ```

**适用场景**：
- 接入新的 IM 平台（飞书、钉钉、Matrix 等）
- 使用平台特有的消息组件（表情、戳一戳等）

**详细文档**：见 [AstrBot-Platform 模块接口整理.md](./AstrBot-Platform%20模块接口整理.md)

---

### 2.5 api.provider（AI 服务模块）

**使用频率**：⭐（极少数高级场景使用）

**典型场景**：

1. **开发自定义 Provider 适配器**
   ```python
   from astrbot.api.provider import Provider, ProviderType
   from astrbot.core.provider.register import register_provider_adapter

   @register_provider_adapter("my_ai_chat", "我的 AI", ProviderType.CHAT_COMPLETION)
   class MyAIProvider(Provider):
       async def text_chat(self, ...):
           ...
   ```

2. **直接调用 AI 能力**
   ```python
   # 从 Context 获取 Provider
   provider = context.provider_manager.get_using_provider(ProviderType.CHAT_COMPLETION)
   response = await provider.text_chat(prompt="你好", session_id="test")
   ```

3. **使用嵌入/重排序能力**
   ```python
   embedding = context.provider_manager.get_using_provider(ProviderType.EMBEDDING)
   vectors = await embedding.get_embeddings(["文本1", "文本2"])

   rerank = context.provider_manager.get_using_provider(ProviderType.RERANK)
   results = await rerank.rerank(query, documents, top_n=3)
   ```

4. **使用 STT/TTS 能力**
   ```python
   stt = context.provider_manager.get_using_provider(ProviderType.SPEECH_TO_TEXT)
   text = await stt.get_text(audio_url)

   tts = context.provider_manager.get_using_provider(ProviderType.TEXT_TO_SPEECH)
   audio = await tts.get_audio("你好世界")
   ```

**适用场景**：
- 接入新的 AI 服务提供商
- 需要绕过 Pipeline 直接调用 AI
- 使用多模态能力（嵌入、重排序、语音）

**详细文档**：见 [AstrBot-Provider 模块接口整理.md](./AstrBot-Provider%20模块接口整理.md)

---

## 三、常见插件开发模式

### 3.1 最简插件

只需要 `api.event` + `api.star`：

```python
from astrbot.api.event import filter
from astrbot.api.star import Star

class SimplePlugin(Star):
    def __init__(self, context):
        super().__init__(context)

    @filter.command("ping")
    async def ping(self, event):
        yield event.make_result().message("Pong!")
```

### 3.2 富文本插件

需要额外使用 `api.message_components`：

```python
from astrbot.api.event import filter
from astrbot.api.star import Star
from astrbot.api.message_components import Plain, Image

class RichPlugin(Star):
    def __init__(self, context):
        super().__init__(context)

    @filter.command("card")
    async def card(self, event):
        chain = [
            Plain(text="这是一张卡片"),
            Image(url="https://example.com/card.png"),
        ]
        result = event.make_result()
        result.chain = chain
        yield result
```

### 3.3 AI 增强插件

需要使用 `api.provider` 获取 AI 能力：

```python
from astrbot.api.event import filter
from astrbot.api.star import Star
from astrbot.api.provider import ProviderType

class AIPlugin(Star):
    def __init__(self, context):
        super().__init__(context)

    @filter.command("embed")
    async def embed(self, event):
        text = event.message_str
        provider = self._context.provider_manager.get_using_provider(ProviderType.EMBEDDING)
        vectors = await provider.get_embeddings([text])
        yield event.make_result().message(f"向量维度: {len(vectors[0])}")
```

### 3.4 事件钩子插件

只需要 `api.event` 的 filter 装饰器：

```python
from astrbot.api.event import filter
from astrbot.api.star import Star

class HookPlugin(Star):
    def __init__(self, context):
        super().__init__(context)

    @filter.on_llm_request()
    async def on_llm_request(self, event, req):
        # 在 LLM 请求前修改
        req.system_prompt = f"当前时间: {datetime.now()}\n" + req.system_prompt

    @filter.on_llm_response()
    async def on_llm_response(self, event, response):
        # 在 LLM 响应后修改
        response.completion_text += "\n\n-- Powered by MyPlugin"
```

---

## 四、快速选择指南

| 我需要... | 使用模块 |
|----------|---------|
| 注册命令 | `filter.command()` |
| 监听所有消息 | `filter.event_message_type()` |
| 监听 LLM 请求/响应 | `filter.on_llm_request()` / `filter.on_llm_response()` |
| 注册 LLM 工具 | `filter.llm_tool()` |
| 访问发送者信息 | `event.get_sender()` |
| 访问群信息 | `event.get_group()` |
| 发送文本消息 | `event.make_result().message(text)` |
| 发送图片 | `event.make_result().message(image=Image(url=...))` |
| 发送多种组件 | `result.chain = [Plain(...), Image(...), At(...)]` |
| 停止事件传播 | `event.stop_event()` |
| 获取插件配置 | `context.get_config(plugin_name)` |
| 创建定时任务 | `self.context.cron_manager` |
| 操作数据库 | `context.db` |
| 调用 LLM | `context.provider_manager.get_using_provider()` |
| 开发平台适配器 | 继承 `Platform` + `register_platform_adapter` |
| 开发 AI 适配器 | 继承 `Provider` + `register_provider_adapter` |

---

## 五、各模块使用说明

### 5.1 api.event（事件模块）

- 日常插件开发：**所有插件必用**。没有它就无法注册命令、监听消息、拦截 LLM 请求
- 使用场景：
  1. 注册命令处理器（`@filter.command()`）
  2. 监听所有消息（`@filter.event_message_type()`）
  3. 拦截 LLM 请求/响应（`@filter.on_llm_request()` / `@filter.on_llm_response()`）
  4. 注册 LLM 工具（`@filter.llm_tool()`）
  5. 使用正则匹配消息（`@filter.regex()`）
- 举例：`from astrbot.api.event import filter`

### 5.2 api.star（插件基础模块）

- 日常插件开发：**所有插件必用**。插件类必须继承 `Star`，配置和工具方法都通过它获取
- 使用场景：
  1. 创建插件类（继承 `Star`）
  2. 获取插件配置（`context.get_config()`）
  3. 使用工具方法（`StarTools.get_data_dir()` / `StarTools.send_message()`）
  4. 访问框架服务（`context.db` / `context.cron_manager` / `context.provider_manager`）
- 举例：`from astrbot.api.star import Star, StarTools`

### 5.3 api.message_components（消息组件模块）

- 日常插件开发：**经常用到**。发送图片、@人、回复、转发等都需要它
- 使用场景：
  1. 发送带图片的消息（`Image`）
  2. @指定用户（`At`）
  3. 回复指定消息（`Reply`）
  4. 发送语音/视频/文件（`Record` / `Video` / `File`）
  5. 发送转发消息（`Nodes`）
- 举例：`from astrbot.api.message_components import Plain, Image, At, Reply`

### 5.4 api.platform（平台模块）

- 日常插件开发：**几乎不用**。消息接收（`event`）和发送（`event.send()`）已经被框架封装好了
- 使用场景：开发**自定义平台适配器**（如接入新的 IM 平台飞书、钉钉等）
- 举例：`from astrbot.api.platform import Platform, register_platform_adapter`

### 5.5 api.provider（AI 服务模块）

- 日常插件开发：**几乎不用**。LLM 调用已经被 Pipeline 和 Agent 封装，你只需注册 `@filter.command()` 或 `@filter.on_llm_request()`
- 使用场景：
  1. 开发**自定义 Provider 适配器**（接入新的 AI 服务商）
  2. 需要直接调用特定 AI 能力（如 `EmbeddingProvider` 做向量化、`RerankProvider` 做重排序、`STTProvider` 做语音转文本）
  3. 在插件中精细控制 LLM 调用（绕过 Pipeline 直接调用 `text_chat()`）
- 举例：`from astrbot.api.provider import Provider, ProviderType`

### 5.6 总结

普通插件开发真正会用到的模块只有 `api.event` 和 `api.star`，以及经常用到的 `api.message_components`。`api.platform` 和 `api.provider` 更多是为框架扩展者准备的，而非普通插件开发者。

---

## 六、文档索引

| 文档 | 内容 |
|------|------|
| [AstrBot-Context 类接口整理.md](./AstrBot-Context%20类接口整理.md) | Context 类所有接口 |
| [AstrBot-Event 模块接口整理.md](./AstrBot-Event%20模块接口整理.md) | Event、MessageChain、MessageEventResult |
| [AstrBot-Event-filter 装饰器整理.md](./AstrBot-Event-filter%20装饰器整理.md) | 所有 filter 装饰器 |
| [AstrBot-Star 模块接口整理.md](./AstrBot-Star%20模块接口整理.md) | Star、StarTools |
| [AstrBot-Platform 模块接口整理.md](./AstrBot-Platform%20模块接口整理.md) | Platform、消息组件 |
| [AstrBot-Provider 模块接口整理.md](./AstrBot-Provider%20模块接口整理.md) | Provider、ProviderManager |

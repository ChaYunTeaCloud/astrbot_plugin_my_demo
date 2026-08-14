# AstrBot Pipeline 详解

> 源码路径：
> - EventBus: `../.venv/Lib/site-packages/astrbot/core/event_bus.py`
> - PipelineScheduler: `../.venv/Lib/site-packages/astrbot/core/pipeline/scheduler.py`
> - Stage 基类: `../.venv/Lib/site-packages/astrbot/core/pipeline/stage.py`
> - Stage 顺序: `../.venv/Lib/site-packages/astrbot/core/pipeline/stage_order.py`
> - aiocqhttp 适配器: `../.venv/Lib/site-packages/astrbot/core/platform/sources/aiocqhttp/aiocqhttp_platform_adapter.py`

本文档以 QQ 平台（OneBot v11）发送 "Hello" 消息为例，详细分析 AstrBot Pipeline 的完整处理流程。

---

## 一、总体流程概览

```text
QQ 客户端 (go-cqhttp/NapCat)
        ↓ 反向 WebSocket
aiocqhttp 适配器 (接收原始消息)
        ↓ 转换为 AstrBotMessage
        ↓ 包装为 AiocqhttpMessageEvent
        ↓ 提交到事件队列
EventBus (消费队列, 分发到 PipelineScheduler)
        ↓
Pipeline (9 个 Stage 依次处理)
        ↓
RespondStage (通过 aiocqhttp 适配器发送回复)
        ↓
QQ 客户端收到回复
```

---

## 二、核心组件

### 2.1 EventBus（事件总线）

**文件**：../.venv/Lib/site-packages/astrbot/core/event_bus.py

负责从 `asyncio.Queue` 消费事件，分发给对应的 `PipelineScheduler`。

```python
class EventBus:
    def __init__(self, event_queue, pipeline_scheduler_mapping, astrbot_config_mgr):
        self.event_queue = event_queue
        self.pipeline_scheduler_mapping = pipeline_scheduler_mapping
        # 持有正在执行的 pipeline 任务的强引用, 防止 task 在 pending 状态被 GC 回收
        self._pending_tasks: set[asyncio.Task] = set()

    async def dispatch(self) -> None:
        while True:
            event = await self.event_queue.get()
            # 根据 unified_msg_origin 获取配置 ID
            conf_info = self.astrbot_config_mgr.get_conf_info(event.unified_msg_origin)
            conf_id = conf_info["id"]
            # 查找对应的 PipelineScheduler
            scheduler = self.pipeline_scheduler_mapping.get(conf_id)
            if not scheduler:
                logger.error(f"PipelineScheduler not found for id: {conf_id}, event ignored.")
                continue
            # 创建异步任务执行 pipeline
            task = asyncio.create_task(scheduler.execute(event))
            self._pending_tasks.add(task)
            task.add_done_callback(self._on_task_done)
```

**关键特点**：
- 每条消息创建一个独立的 `asyncio.Task`，互不阻塞
- 根据 `unified_msg_origin`（格式：`平台ID:消息类型:session_id`）路由到对应配置的 Scheduler
- 若找不到对应 Scheduler，记录 `logger.error` 并跳过该事件
- 任务存入 `_pending_tasks` 强引用集合，完成/取消后由 `_on_task_done` 回调移除并暴露未捕获异常

### 2.2 PipelineScheduler（管道调度器）

**文件**：../.venv/Lib/site-packages/astrbot/core/pipeline/scheduler.py

负责按序执行 9 个 Stage，使用**洋葱模型**支持中间件式拦截。

```python
class PipelineScheduler:
    async def _process_stages(self, event, from_stage=0):
        for i in range(from_stage, len(self.stages)):
            stage = self.stages[i]
            coroutine = stage.process(event)

            if isinstance(coroutine, AsyncGenerator):
                # 洋葱模型核心：yield 处暂停，递归执行后续所有 Stage
                async for _ in coroutine:
                    if event.is_stopped():
                        break
                    await self._process_stages(event, i + 1)
                    # 后续 Stage 完成后回到此处，继续执行当前 Stage 的后置逻辑
                    if event.is_stopped():
                        break
            else:
                # 普通协程：执行完成后继续下一个 Stage
                await coroutine
                if event.is_stopped():
                    break
```

**洋葱模型示意**：

```text
Stage1.process() {
    前置逻辑
    yield  ← 暂停，控制权交给 Stage2
        Stage2.process() {
            前置逻辑
            yield  ← 暂停，控制权交给 Stage3
                Stage3.process() {
                    前置逻辑
                    yield
                    后置逻辑  ← Stage3 完成
                }
            后置逻辑  ← Stage2 完成，继续执行
        }
    后置逻辑  ← Stage1 完成，继续执行
}
```

### 2.3 Stage（管道阶段）

**文件**：../.venv/Lib/site-packages/astrbot/core/pipeline/stage.py

所有 Stage 继承自 `Stage` 抽象基类：

```python
class Stage(abc.ABC):
    async def initialize(self, ctx: PipelineContext) -> None:
        """初始化阶段，在 Pipeline 启动时调用"""

    async def process(self, event: AstrMessageEvent) -> None | AsyncGenerator[None]:
        """处理事件。返回 AsyncGenerator 实现洋葱模型，返回 None 表示普通协程（无洋葱模型），await 后继续下一 Stage；终止传播依赖 event.stop_event()/is_stopped()"""
```

### 2.4 PipelineContext（管道上下文）

**文件**：../.venv/Lib/site-packages/astrbot/core/pipeline/context.py

```python
@dataclass
class PipelineContext:
    astrbot_config: AstrBotConfig  # AstrBot 全局配置
    plugin_manager: PluginManager  # 插件管理器
    astrbot_config_id: str
    call_handler = call_handler        # 类属性，指向 context_utils.call_handler
    call_event_hook = call_event_hook  # 类属性，指向 context_utils.call_event_hook
```

---

## 三、9 个 Stage 详解

按执行顺序排列，定义在 `../.venv/Lib/site-packages/astrbot/core/pipeline/stage_order.py`：

### 3.1 WakingCheckStage（唤醒检查）

**文件**：../.venv/Lib/site-packages/astrbot/core/pipeline/waking_check/stage.py

**功能**：判断是否唤醒机器人，匹配哪些插件 Handler 该执行。

**关键逻辑**：
1. 检查唤醒条件（第 106-152 行）：
   - 消息以 `wake_prefix` 开头（如 `/`、`bot` 等）
   - @机器人 或 @全体成员
   - 引用了机器人的消息
   - 私聊消息

2. 匹配插件 Handler（第 154-242 行）：
   - 遍历 `star_handlers_registry` 中注册的所有 Handler
   - 对每个 Handler 的 `event_filters` 进行 AND 逻辑匹配
   - Filter 类型：`CommandFilter`、`RegexFilter`、`PermissionTypeFilter`、`PlatformTypeFilter` 等
   - 匹配成功的 Handler 加入 `activated_handlers` 列表

3. 存储结果到 event（第 244-245 行）：
   ```python
   event.set_extra("activated_handlers", activated_handlers)
   event.set_extra("handlers_parsed_params", handlers_parsed_params)
   ```

### 3.2 WhitelistCheckStage（白名单检查）

**文件**：../.venv/Lib/site-packages/astrbot/core/pipeline/whitelist_check/stage.py

**功能**：检查群聊/私聊是否在白名单中。

### 3.3 SessionStatusCheckStage（会话状态检查）

**文件**：../.venv/Lib/site-packages/astrbot/core/pipeline/session_status_check/stage.py

**功能**：检查会话是否启用。

### 3.4 RateLimitStage（频率限制）

**文件**：../.venv/Lib/site-packages/astrbot/core/pipeline/rate_limit_check/stage.py

**功能**：检查会话是否超过频率限制。

### 3.5 ContentSafetyCheckStage（内容安全）

**文件**：../.venv/Lib/site-packages/astrbot/core/pipeline/content_safety_check/stage.py

**功能**：检查消息内容是否安全，支持百度 AI 安全审核、关键词过滤等策略。

### 3.6 PreProcessStage（预处理）

**文件**：../.venv/Lib/site-packages/astrbot/core/pipeline/preprocess_stage/stage.py

**功能**：消息预处理，包括：
- 路径映射（媒体文件路径转换）
- 媒体格式转换（Record→WAV、Image→JPEG）
- STT（语音转文本）

### 3.7 ProcessStage（处理阶段）

**文件**：../.venv/Lib/site-packages/astrbot/core/pipeline/process_stage/stage.py

**功能**：执行插件 Handler + LLM 调用，包含两个子阶段：

**7a. StarRequestSubStage**（../.venv/Lib/site-packages/astrbot/core/pipeline/process_stage/method/star_request.py）：
- 遍历 `activated_handlers`，逐个调用插件 Handler
- 使用 `call_handler()` 支持异步生成器（洋葱模型）和普通协程

**7b. AgentRequestSubStage**：
- 调用 LLM Provider 获取回复
- 支持工具调用（Function/Tool Calling）

### 3.8 ResultDecorateStage（结果装饰）

**文件**：../.venv/Lib/site-packages/astrbot/core/pipeline/result_decorate/stage.py

**功能**：对回复进行后处理：
- 文本转图片（t2i）
- 添加回复前缀
- 转换为语音

### 3.9 RespondStage（发送回复）

**文件**：../.venv/Lib/site-packages/astrbot/core/pipeline/respond/stage.py

**功能**：通过平台适配器发送回复消息。

**关键逻辑**：
1. 从 `event.get_result()` 获取处理结果
2. 处理消息链（路径映射、空消息检查、分段回复等）
3. 调用 `event.send(MessageChain)` 发送

---

## 四、消息流转示例（QQ "Hello" 消息）

### 步骤 1：WebSocket 接收原始消息

**文件**：../.venv/Lib/site-packages/astrbot/core/platform/sources/aiocqhttp/aiocqhttp_platform_adapter.py#L85

```python
@self.bot.on_message("group")
async def group(event: Event) -> None:
    abm = await self.convert_message(event)
    if abm:
        await self.handle_msg(abm)
```

- `aiocqhttp` 库解析 OneBot v11 JSON，构造 `Event` 对象
- 触发群消息回调

### 步骤 2：消息转换

**文件**：../.venv/Lib/site-packages/astrbot/core/platform/sources/aiocqhttp/aiocqhttp_platform_adapter.py#L198

**数据映射**：

| OneBot v11 | AstrBotMessage | 说明 |
|---|---|---|
| `event.self_id` | `abm.self_id` | 机器人 ID |
| `event.sender.user_id` | `abm.sender.user_id` | 发送者 ID |
| `event.sender.card/nickname` | `abm.sender.nickname` | 发送者昵称 |
| `event.message_type == "group"` | `abm.type = GROUP_MESSAGE` | 消息类型 |
| `event.group_id` | `abm.group_id` | 群号 |
| `event.message`（数组） | `abm.message`（组件列表） | 消息链转换 |

**消息段转换**：
- `text` → `Plain(text=...)`
- `image` → `Image(...)`
- `at` → `At(qq=..., name=...)`
- `reply` → `Reply(...)`

### 步骤 3：事件提交

**文件**：../.venv/Lib/site-packages/astrbot/core/platform/sources/aiocqhttp/aiocqhttp_platform_adapter.py#L509

```python
async def handle_msg(self, message: AstrBotMessage) -> None:
    self.commit_event(self.create_event(message))
```

1. `create_event()`：将 `AstrBotMessage` 包装为 `AiocqhttpMessageEvent`
2. `commit_event()`：调用父类方法 `self._event_queue.put_nowait(event)`

### 步骤 4：EventBus 分发

**文件**：../.venv/Lib/site-packages/astrbot/core/event_bus.py#L39

```python
async def dispatch(self) -> None:
    while True:
        event = await self.event_queue.get()
        conf_info = self.astrbot_config_mgr.get_conf_info(event.unified_msg_origin)
        scheduler = self.pipeline_scheduler_mapping.get(conf_info["id"])
        task = asyncio.create_task(scheduler.execute(event))
```

- 每条消息创建独立 `asyncio.Task`
- 互不阻塞

### 步骤 5：Pipeline 处理

**文件**：../.venv/Lib/site-packages/astrbot/core/pipeline/scheduler.py#L35

依次执行 9 个 Stage，使用洋葱模型支持中间件式拦截。

### 步骤 6：Handler 执行

**文件**：../.venv/Lib/site-packages/astrbot/core/pipeline/context_utils.py#L12

`call_handler()` 支持两种 Handler 形式：
- **异步生成器**：每个 `yield` 返回值如果是 `MessageEventResult` 就设置到 event
- **普通协程**：直接执行并处理返回值

### 步骤 7：发送回复

**文件**：../.venv/Lib/site-packages/astrbot/core/pipeline/respond/stage.py#L173（process 定义在 L169）

```python
result = event.get_result()
await event.send(result.chain)
```

`event.send()` 最终调用 `CQHttp.send()` 通过 OneBot HTTP API 发送消息。

---

## 五、数据流总结

| 阶段 | 数据形态 | 关键转换 |
|------|---------|---------|
| WebSocket 接收 | OneBot v11 JSON | `aiocqhttp` 库解析为 `Event` 对象 |
| 适配器转换 | `Event` → `AstrBotMessage` | 消息段类型映射 |
| 事件包装 | `AstrBotMessage` → `AiocqhttpMessageEvent` | 注入 bot 实例、session、trace |
| 队列提交 | 入队 `asyncio.Queue` | `put_nowait()` 非阻塞 |
| EventBus 分发 | 队列消费 → 创建 Task | 每条消息独立 Task |
| Pipeline 处理 | 9 个 Stage 依次执行 | 洋葱模型，支持拦截 |
| Handler 执行 | 插件 Handler 被调用 | 支持异步生成器和协程 |
| 结果发送 | `MessageEventResult` → `event.send()` | 最终通过 OneBot HTTP API |

---

## 六、对插件开发者的启示

1. **Handler 可以是异步生成器**：实现洋葱模型，在 `yield` 前后分别处理前置/后置逻辑
2. **使用 `event.stop_event()`**：可以在任何 Stage/Handler 中终止事件传播
3. **使用 `event.set_extra()`**：在 Handler 间传递数据
4. **使用 `event.set_result()`**：设置回复消息
5. **消息并行处理**：多条消息互不阻塞，如需顺序请自行控制

---

## 七、关键文件索引

| 文件 | 作用 |
|------|------|
| `event_bus.py` | 事件总线，消费队列分发到 Scheduler |
| `pipeline/scheduler.py` | 管道调度器，按序执行 Stage |
| `pipeline/stage.py` | Stage 基类 |
| `pipeline/stage_order.py` | 9 个 Stage 的执行顺序 |
| `pipeline/context.py` | PipelineContext 定义 |
| `pipeline/context_utils.py` | `call_handler()`、`call_event_hook()` |
| `pipeline/waking_check/stage.py` | 唤醒检查 + Handler 匹配 |
| `pipeline/respond/stage.py` | 发送回复 |
| `platform/sources/aiocqhttp/aiocqhttp_platform_adapter.py` | QQ 平台适配器 |

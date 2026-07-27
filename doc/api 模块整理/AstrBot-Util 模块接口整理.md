# AstrBot Util 模块接口整理

> 源码路径：
> - API 导出: `astrbot/api/util/__init__.py`
> - 实现: `astrbot/core/utils/session_waiter.py`

---

## 一、模块概述

`api.util` 模块提供会话控制能力，允许插件创建等待用户输入的交互式对话流程。核心是 `session_waiter` 装饰器，用于实现多轮对话场景。

---

## 二、API 导出

**文件**：astrbot/api/util/__init__.py

```python
from astrbot.core.utils.session_waiter import (
    SessionController,
    SessionWaiter,
    session_waiter,
)

__all__ = ["SessionController", "SessionWaiter", "session_waiter"]
```

---

## 三、核心类与函数

### 3.1 session_waiter 装饰器

**文件**：astrbot/core/utils/session_waiter.py#L174

```python
def session_waiter(timeout: int = 30, record_history_chains: bool = False):
```

**参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `timeout` | `int` | 30 | 超时时间（秒） |
| `record_history_chains` | `bool` | False | 是否记录历史消息链 |

**使用示例**：

```python
from astrbot.api.util import session_waiter, SessionController

@filter.command("ask")
@session_waiter(timeout=60, record_history_chains=True)
async def ask_question(self, controller: SessionController, event):
    # 第一次触发：发送问题
    await event.send(event.make_result().message("请问您的名字是什么？"))
    
    # 等待用户回复...（框架自动挂起，用户回复时继续执行）
    reply = event.message_str
    await event.send(event.make_result().message(f"您好，{reply}！"))
    
    # 如果需要继续等待，可以再次 yield 或使用 controller.keep()
    controller.keep(30)  # 继续保持会话 30 秒
```

**工作原理**：

1. 装饰器将函数注册为 `SessionWaiter` 处理函数
2. 第一次触发时执行到函数末尾，会话进入等待状态
3. 用户回复时，框架查找匹配的 `SessionWaiter`，重新执行处理函数
4. 通过 `event.message_str` 获取新的回复内容

### 3.2 SessionController（会话控制器）

**文件**：astrbot/core/utils/session_waiter.py#L18

控制会话的生命周期。

**属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `current_event` | `asyncio.Event \| None` | 当前正在等待的异步事件 |
| `history_chains` | `list[list[BaseMessageComponent]]` | 历史消息链列表 |
| `ts` | `float \| None` | 上次保持开始的时间 |
| `timeout` | `float \| int \| None` | 上次保持开始的超时时间 |

**方法**：

| 方法 | 说明 |
|------|------|
| `stop(error=None)` | 立即结束会话 |
| `keep(timeout, reset_timeout=False)` | 保持会话，可设置新的超时时间 |
| `get_history_chains()` | 获取历史消息链 |

**keep 参数说明**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `timeout` | `float` | 超时时间（秒），必填 |
| `reset_timeout` | `bool` | True=重置超时时间，False=累计超时时间 |

**使用示例**：

```python
@session_waiter(timeout=30)
async def multi_step(self, controller: SessionController, event):
    # 第一步
    await event.send(event.make_result().message("步骤1：请输入姓名"))
    
    # 用户回复后继续...
    name = event.message_str
    
    # 继续保持会话，重置超时时间
    controller.keep(30, reset_timeout=True)
    
    # 第二步
    await event.send(event.make_result().message("步骤2：请输入年龄"))
    
    # 用户回复后继续...
    age = event.message_str
    
    await event.send(event.make_result().message(f"姓名: {name}, 年龄: {age}"))
```

### 3.3 SessionWaiter（会话等待器）

**文件**：astrbot/core/utils/session_waiter.py#L104

内部类，管理单个会话的等待逻辑。

**属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `session_id` | `str` | 会话 ID |
| `session_filter` | `SessionFilter` | 会话过滤器 |
| `session_controller` | `SessionController` | 会话控制器 |
| `record_history_chains` | `bool` | 是否记录历史消息链 |

**方法**：

| 方法 | 说明 |
|------|------|
| `register_wait(handler, timeout)` | 注册等待处理函数 |
| `trigger(session_id, event)` | 外部输入触发会话处理（类方法） |

### 3.4 SessionFilter（会话过滤器）

**文件**：astrbot/core/utils/session_waiter.py#L90

抽象基类，定义如何界定一个会话。

```python
class SessionFilter:
    @abc.abstractmethod
    def filter(self, event: AstrMessageEvent) -> str:
        """根据事件返回一个会话标识符"""
```

### 3.5 DefaultSessionFilter（默认会话过滤器）

**文件**：astrbot/core/utils/session_waiter.py#L98

默认实现，使用 `event.unified_msg_origin` 作为会话标识符。

---

## 四、完整示例

```python
from astrbot.api.event import filter
from astrbot.api.star import Star
from astrbot.api.util import session_waiter, SessionController

class MultiStepPlugin(Star):
    def __init__(self, context):
        super().__init__(context)

    @filter.command("survey")
    @session_waiter(timeout=60, record_history_chains=True)
    async def survey(self, controller: SessionController, event):
        # 获取历史消息（第一次调用时为空）
        history = controller.get_history_chains()
        
        if len(history) == 0:
            # 第一次：提问
            await event.send(event.make_result().message("欢迎参加调查！请问您的职业是什么？"))
        elif len(history) == 1:
            # 第二次：用户回答职业后
            job = event.message_str
            await event.send(event.make_result().message(f"您是{job}，请问您使用什么编程语言？"))
        elif len(history) == 2:
            # 第三次：用户回答语言后
            lang = event.message_str
            await event.send(event.make_result().message(f"感谢您的参与！职业: {job}, 语言: {lang}"))
            # 会话自动结束（处理函数执行完毕）
```

---

## 五、注意事项

1. **handler 签名**：被 `@session_waiter` 装饰的函数签名必须是 `async def func(controller: SessionController, event)`
2. **超时处理**：超时时会抛出 `TimeoutError`，建议在调用处捕获
3. **会话隔离**：默认按 `unified_msg_origin`（平台+消息类型+session_id）隔离会话
4. **历史消息**：设置 `record_history_chains=True` 后，通过 `controller.get_history_chains()` 获取所有历史消息链
5. **手动控制**：使用 `controller.keep()` 可以在处理函数中主动控制超时时间
6. **结束会话**：调用 `controller.stop()` 可以立即结束会话

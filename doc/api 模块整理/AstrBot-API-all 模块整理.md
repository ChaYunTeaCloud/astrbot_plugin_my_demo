# AstrBot API-all 模块整理

> 源码路径：`../.venv/Lib/site-packages/astrbot/api/all.py`

---

## 一、模块概述

`api/all.py` 是一个**聚合导出文件**，将 AstrBot 的所有核心 API 一次性导出，方便插件开发者使用。它的设计目的是提供一个"一次导入，全部可用"的入口。

**使用方式**：

```python
from astrbot.api.all import *
```

---

## 二、导出内容

**文件**：../.venv/Lib/site-packages/astrbot/api/all.py

### 2.1 基础配置与工具

| 导出名 | 来源 | 说明 |
|--------|------|------|
| `AstrBotConfig` | `astrbot.core.config.astrbot_config` | AstrBot 配置类 |
| `logger` | `astrbot` | 日志记录器 |
| `html_renderer` | `astrbot.core` | HTML 渲染工具 |
| `llm_tool` | `astrbot.core.star.register` | LLM 工具注册装饰器 |
| `sp` | `astrbot.core` | 偏好设置存储（SharedPreferences） |
| `agent` | `astrbot.core.star.register` | 子 Agent 注册装饰器 |
| `BaseFunctionToolExecutor` | `astrbot.core.agent.tool_executor` | 工具执行器基类 |

> 上述导出项的详细说明参见 `AstrBot-api__init__导出补充.md`

### 2.2 Event 相关

| 导出名 | 来源 | 说明 |
|--------|------|------|
| `MessageEventResult` | `astrbot.core.message.message_event_result` | 消息事件结果 |
| `MessageChain` | `astrbot.core.message.message_event_result` | 消息链 |
| `CommandResult` | `astrbot.core.message.message_event_result` | 命令结果 |
| `EventResultType` | `astrbot.core.message.message_event_result` | 结果类型枚举 |
| `AstrMessageEvent` | `astrbot.core.platform` | 消息事件类 |

### 2.3 Star 注册装饰器

| 导出名 | 来源 | 说明 |
|--------|------|------|
| `command` | `astrbot.core.star.register` | 命令注册装饰器 |
| `command_group` | `astrbot.core.star.register` | 命令组注册装饰器 |
| `event_message_type` | `astrbot.core.star.register` | 事件类型过滤装饰器 |
| `regex` | `astrbot.core.star.register` | 正则匹配装饰器 |
| `platform_adapter_type` | `astrbot.core.star.register` | 平台类型过滤装饰器 |
| `EventMessageTypeFilter` | `astrbot.core.star.filter.event_message_type` | 事件类型过滤器类 |
| `EventMessageType` | `astrbot.core.star.filter.event_message_type` | 事件类型枚举 |
| `PlatformAdapterTypeFilter` | `astrbot.core.star.filter.platform_adapter_type` | 平台类型过滤器类 |
| `PlatformAdapterType` | `astrbot.core.star.filter.platform_adapter_type` | 平台类型枚举 |
| `register` | `astrbot.core.star.register` | 插件注册装饰器（已废弃） |

### 2.4 Star 核心类

| 导出名 | 来源 | 说明 |
|--------|------|------|
| `Context` | `astrbot.core.star` | 上下文类 |
| `Star` | `astrbot.core.star` | 插件基类 |
| `*` (config) | `astrbot.core.star.config` | 配置模块全部导出（已废弃） |

### 2.5 Provider 相关

| 导出名 | 来源 | 说明 |
|--------|------|------|
| `Provider` | `astrbot.core.provider` | Provider 基类 |
| `ProviderMetaData` | `astrbot.core.provider` | Provider 元数据 |
| `Personality` | `astrbot.core.db.po` | 人格数据库模型 |

### 2.6 Platform 相关

| 导出名 | 来源 | 说明 |
|--------|------|------|
| `AstrMessageEvent` | `astrbot.core.platform` | 消息事件类（重复导出） |
| `Platform` | `astrbot.core.platform` | 平台适配器基类 |
| `AstrBotMessage` | `astrbot.core.platform` | 消息对象 |
| `MessageMember` | `astrbot.core.platform` | 消息成员 |
| `MessageType` | `astrbot.core.platform` | 消息类型枚举 |
| `PlatformMetadata` | `astrbot.core.platform` | 平台元数据 |
| `register_platform_adapter` | `astrbot.core.platform.register` | 平台适配器注册装饰器 |

### 2.7 Message Components

| 导出名 | 来源 | 说明 |
|--------|------|------|
| `*` | `astrbot.api.message_components` | 所有消息组件（Plain、Image、At、Reply 等） |

---

## 三、使用示例

**方式一：全部导入**

```python
from astrbot.api.all import *

class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @command("hello")
    async def hello(self, event: AstrMessageEvent):
        logger.info("触发 hello 指令")
        yield event.plain_result("Hello World!")
```

**方式二：部分导入**

```python
from astrbot.api.all import Star, Context, command, AstrMessageEvent, logger

class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @command("hello")
    async def hello(self, event: AstrMessageEvent):
        logger.info("触发 hello 指令")
        yield event.plain_result("Hello World!")
```

---

## 四、注意事项

1. **不推荐全部导入**：`from astrbot.api.all import *` 会污染命名空间，建议按需导入
2. **部分内容已废弃**：`register` 装饰器和 `config` 模块已废弃，不建议使用
3. **重复导出**：`AstrMessageEvent` 在 Event 和 Platform 部分重复导出
4. **推荐方式**：官方推荐使用 `from astrbot.api.event import filter` 和 `from astrbot.api.star import Star, Context` 等精确导入方式
5. **模块定位**：此文件主要是为了兼容旧代码或提供便捷导入，不代表官方推荐的最佳实践

# AstrBot 插件开发文档索引

> 本文档目录为 `doc/` 下所有 AstrBot 插件开发相关文档提供导航。
> 所有源码引用均以 `doc/` 为根目录，使用相对路径 `../.venv/Lib/site-packages/astrbot/...` 指向 AstrBot 安装包。

---

## 一、核心机制文档

深入理解 AstrBot 关键机制的专题文档。

| 文档 | 核心内容 |
|------|----------|
| [AstrBot-SubAgent 机制.md](./AstrBot-SubAgent%20机制.md) | SubAgent 子智能体机制、HandoffTool 工作流、工具路由分发、SubAgent 工具集缺失问题与解决方案 |
| [AstrBot-Tool.md](./AstrBot-Tool.md) | Tool 工具机制、FunctionTool / ToolSet / FunctionToolManager、@llm_tool 装饰器、动态注入、自定义工具管理类 |
| [AstrBot-Skill 机制.md](./AstrBot-Skill%20机制.md) | Skill 本质（Markdown 提示词）、Skill 三种来源、SkillManager、Skill 注入流程、SubAgent 的 Skill 缺失问题 |
| [AstrBot-Persona 机制.md](./AstrBot-Persona%20机制.md) | Persona ORM 模型、Personality TypedDict、PersonaManager、缓存机制、与 Agent 的关系 |
| [AstrBot-MainAgent-vs-SubAgent.md](./AstrBot-MainAgent-vs-SubAgent.md) | MainAgent 与 SubAgent 的调用逻辑对比、工具/Skill 注入差异、请求构建流程、Persona 应用时机 |

## 二、源码分析文档

基于 AstrBot 安装包源码的包结构与管线详解。

| 文档 | 核心内容 |
|------|----------|
| [AstrBot包分析-astrbot.api.md](./AstrBot包分析-astrbot.api.md) | `astrbot.api` 包结构、各子模块导出清单、插件开发导入范式 |
| [AstrBot包分析-pipeline 详解.md](./AstrBot包分析-pipeline%20详解.md) | Pipeline 消息管线 9 个 Stage 详解、EventBus / PipelineScheduler、洋葱模型、消息流转示例 |

## 三、API 模块接口整理

`api 模块整理/` 子目录下的参考手册，按模块划分。

| 文档 | 核心内容 |
|------|----------|
| [api 模块整理/AstrBot-API 各模块使用场景.md](./api%20模块整理/AstrBot-API%20各模块使用场景.md) | 各 API 模块的使用频率与典型场景 |
| [api 模块整理/AstrBot-API 速查表.md](./api%20模块整理/AstrBot-API%20速查表.md) | API 速查 |
| [api 模块整理/AstrBot-API-all 模块整理.md](./api%20模块整理/AstrBot-API-all%20模块整理.md) | `astrbot.api.all` 一揽子导出内容 |
| [api 模块整理/AstrBot-Event 模块接口整理.md](./api%20模块整理/AstrBot-Event%20模块接口整理.md) | `AstrMessageEvent`、`MessageChain` 事件与消息相关类接口 |
| [api 模块整理/AstrBot-Event-filter 装饰器整理.md](./api%20模块整理/AstrBot-Event-filter%20装饰器整理.md) | `api.event.filter` 中所有装饰器 |
| [api 模块整理/AstrBot-Star 模块接口整理.md](./api%20模块整理/AstrBot-Star%20模块接口整理.md) | `Star` 基类、`StarTools` 接口 |
| [api 模块整理/AstrBot-Star-Context 类接口整理.md](./api%20模块整理/AstrBot-Star-Context%20类接口整理.md) | `Context` 插件上下文接口 |
| [api 模块整理/AstrBot-Platform 模块接口整理.md](./api%20模块整理/AstrBot-Platform%20模块接口整理.md) | `Platform` 平台适配器基类接口 |
| [api 模块整理/AstrBot-Provider 模块接口整理.md](./api%20模块整理/AstrBot-Provider%20模块接口整理.md) | Provider 相关接口 |
| [api 模块整理/AstrBot-MessageComponents 模块接口整理.md](./api%20模块整理/AstrBot-MessageComponents%20模块接口整理.md) | 消息组件接口 |
| [api 模块整理/AstrBot-Web 模块接口整理.md](./api%20模块整理/AstrBot-Web%20模块接口整理.md) | Web API 相关接口 |
| [api 模块整理/AstrBot-Util 模块接口整理.md](./api%20模块整理/AstrBot-Util%20模块接口整理.md) | 工具类接口 |
| [api 模块整理/AstrBot-api__init__导出补充.md](./api%20模块整理/AstrBot-api__init__导出补充.md) | `api.__init__` 顶层导出补充说明 |

## 四、插件开发记录与笔记

| 文档 | 核心内容 |
|------|----------|
| [other 记录.md](./other%20记录.md) | Handler 注册与调用、EventType 参数传递、装饰器实现、事件继承层次、平台差异控制、访问平台原生 API 等开发笔记 |
| [文档说明.md](./文档说明.md) | 文档体系评估与后续补充建议 |

---

## 文档中源码引用的路径约定

文档内所有引用 AstrBot 源码的路径均使用如下约定：

- 以 `doc/` 为根目录
- 源码统一相对路径前缀：`../.venv/Lib/site-packages/astrbot/`
- 示例：`../.venv/Lib/site-packages/astrbot/core/star/star_handler.py#L216`

源码实际物理位置：`{插件根目录}/.venv/Lib/site-packages/astrbot/`（`doc/` 与 `.venv/` 同级，故引用时需 `../`）

## 建议的阅读路径

1. **入门**：`AstrBot包分析-astrbot.api.md` → `AstrBot包分析-pipeline 详解.md`
2. **核心机制**：`AstrBot-Tool.md` → `AstrBot-Skill 机制.md` → `AstrBot-Persona 机制.md`
3. **高级机制**：`AstrBot-SubAgent 机制.md` → `AstrBot-MainAgent-vs-SubAgent.md`
4. **API 查阅**：`api 模块整理/` 下各文档按需查阅
5. **开发笔记**：`other 记录.md` 作为辅助参考

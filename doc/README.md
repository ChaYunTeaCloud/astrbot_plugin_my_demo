# AstrBot 插件开发文档索引

> 本文档目录为 `doc/` 下所有 AstrBot 插件开发相关文档提供导航。
> 所有源码引用均以 `doc/` 为根目录，使用相对路径 `../.venv/Lib/site-packages/astrbot/...` 指向 AstrBot 安装包。
> `doc/` 与 `.venv/` 目录同级，故引用时需 `../`。子目录下的文档路径前缀相应多一层 `../`。

---

## 一、核心机制

深入理解 AstrBot 关键机制的专题文档。

| 文档 | 核心内容 |
|------|----------|
| [Tool 机制](./核心机制/Tool%20机制.md) | Tool 工具机制、FunctionTool / ToolSet / FunctionToolManager、@llm_tool 装饰器、动态注入、自定义工具管理类 |
| [Skill 机制](./核心机制/Skill%20机制.md) | Skill 本质（Markdown 提示词）、Skill 五种来源、SkillManager、Skill 注入流程、SubAgent 的 Skill 缺失问题 |
| [Persona 机制](./核心机制/Persona%20机制.md) | Persona ORM 模型、Personality TypedDict、PersonaManager、缓存机制、与 Agent 的关系、SubAgent 的 Persona 分配流程 |
| [SubAgent 机制](./核心机制/SubAgent%20机制.md) | SubAgent 子智能体机制、HandoffTool 工作流、工具路由分发、SubAgentOrchestrator 类详解、工具集缺失问题与解决方案 |

## 二、调用流程

MainAgent 与 SubAgent 的调用逻辑对比与源码分析。

| 文档 | 核心内容 |
|------|----------|
| [MainAgent 调用流程](./调用流程/MainAgent%20调用流程.md) | MainAgent 工具集构建流程（11 个 Step）、执行方式、构建请求的源码分析、与 SubAgent 的差异 |
| [SubAgent 调用流程](./调用流程/SubAgent%20调用流程.md) | SubAgent 工具集构建流程、执行方式、Bug 与已知问题、Plugin 开发者应对策略、主要差异源码对比 |

## 三、源码分析

基于 AstrBot 安装包源码的包结构与管线详解。

| 文档 | 核心内容 |
|------|----------|
| [astrbot.api 包分析](./源码分析/astrbot.api%20包分析.md) | `astrbot.api` 包结构、各子模块导出清单、插件开发导入范式 |
| [Pipeline 详解](./源码分析/Pipeline%20详解.md) | Pipeline 消息管线 9 个 Stage 详解、EventBus / PipelineScheduler、洋葱模型、消息流转示例 |

## 四、API 参考

`API 参考/` 子目录下的参考手册，按模块划分。

| 文档 | 核心内容 |
|------|----------|
| [API 各模块使用场景](./API%20参考/AstrBot-API%20各模块使用场景.md) | 各 API 模块的使用频率与典型场景 |
| [API 速查表](./API%20参考/AstrBot-API%20速查表.md) | API 速查 |
| [API-all 模块整理](./API%20参考/AstrBot-API-all%20模块整理.md) | `astrbot.api.all` 一揽子导出内容 |
| [Event 模块接口整理](./API%20参考/AstrBot-Event%20模块接口整理.md) | `AstrMessageEvent`、`MessageChain` 事件与消息相关类接口 |
| [Event-filter 装饰器整理](./API%20参考/AstrBot-Event-filter%20装饰器整理.md) | `api.event.filter` 中所有装饰器 |
| [Star 模块接口整理](./API%20参考/AstrBot-Star%20模块接口整理.md) | `Star` 基类、`StarTools` 接口 |
| [Star-Context 类接口整理](./API%20参考/AstrBot-Star-Context%20类接口整理.md) | `Context` 插件上下文接口 |
| [Platform 模块接口整理](./API%20参考/AstrBot-Platform%20模块接口整理.md) | `Platform` 平台适配器基类接口 |
| [Provider 模块接口整理](./API%20参考/AstrBot-Provider%20模块接口整理.md) | Provider 相关接口 |
| [MessageComponents 模块接口整理](./API%20参考/AstrBot-MessageComponents%20模块接口整理.md) | 消息组件接口 |
| [Web 模块接口整理](./API%20参考/AstrBot-Web%20模块接口整理.md) | Web API 相关接口 |
| [Util 模块接口整理](./API%20参考/AstrBot-Util%20模块接口整理.md) | 工具类接口 |
| [api__init__导出补充](./API%20参考/AstrBot-api__init__导出补充.md) | `api.__init__` 顶层导出补充说明 |

## 五、开发笔记

| 文档 | 核心内容 |
|------|----------|
| [开发笔记](./开发笔记.md) | 插件本质与 Handler 机制、事件系统（EventType 参数传递、StarHandlerRegistry）、插件配置、API 模块介绍、平台适配（平台差异控制、事件继承层次、访问平台原生 API） |

---

## 文档中源码引用的路径约定

文档内所有引用 AstrBot 源码的路径均使用如下约定：

- 以 `doc/` 为根目录
- 所有文档统一使用：`../.venv/Lib/site-packages/astrbot/...`
- 示例：`../.venv/Lib/site-packages/astrbot/core/star/star_handler.py#L216`

源码实际物理位置：`{插件根目录}/.venv/Lib/site-packages/astrbot/`

---

## 建议的阅读路径

1. **入门**：[astrbot.api 包分析](./源码分析/astrbot.api%20包分析.md) → [Pipeline 详解](./源码分析/Pipeline%20详解.md)
2. **核心机制**：[Tool 机制](./核心机制/Tool%20机制.md) → [Skill 机制](./核心机制/Skill%20机制.md) → [Persona 机制](./核心机制/Persona%20机制.md)
3. **高级机制**：[SubAgent 机制](./核心机制/SubAgent%20机制.md) → [MainAgent 调用流程](./调用流程/MainAgent%20调用流程.md) → [SubAgent 调用流程](./调用流程/SubAgent%20调用流程.md)
4. **API 查阅**：[API 参考](./API%20参考/) 下各文档按需查阅
5. **开发笔记**：[开发笔记](./开发笔记.md) 作为辅助参考

---

## 文档体系评估与后续补充建议

### 已覆盖的核心主题

| 主题 | 文档位置 | 状态 |
|------|---------|------|
| 插件生命周期与 Context | API 参考 / Star-Context 类接口整理 | ✅ |
| 事件系统与消息对象 | API 参考 / Event 模块接口整理 | ✅ |
| 过滤器装饰器 | API 参考 / Event-filter 装饰器整理 | ✅ |
| 工具机制 | 核心机制 / Tool 机制 | ✅ 非常完善 |
| 消息组件 | API 参考 / MessageComponents 模块接口整理 | ✅ |
| 平台适配 | API 参考 / Platform 模块接口整理 | ✅ |
| Provider | API 参考 / Provider 模块接口整理 | ✅ |
| Skill 机制 | 核心机制 / Skill 机制 | ✅ |
| Persona 机制 | 核心机制 / Persona 机制 | ✅ |
| SubAgent 机制 | 核心机制 / SubAgent 机制 | ✅ |
| MainAgent vs SubAgent | 调用流程 / MainAgent 调用流程 + SubAgent 调用流程 | ✅ |
| api 包导出 | API 参考 / api__init__导出补充 | ✅ |
| 包分析 | 源码分析 / astrbot.api 包分析 | ✅ |
| Pipeline | 源码分析 / Pipeline 详解 | ✅ |

### 可能的补充方向

如果以后需要，以下内容可以考虑补充，但不影响当前开发：

1. **ProviderRequest**：构建 LLM 请求的核心对象，在 `on_llm_request` 和 `tool_loop_agent` 中频繁使用。目前散落在各处，没有独立文档。

2. **会话管理**：`ConversationManager` 的对话创建/切换/删除 API。官方文档有提及，但目前文档中没有独立整理。
   - 注：根据官方文档 [自定义规则](https://docs.astrbot.app/use/custom-rules.html#%E8%87%AA%E5%AE%9A%E4%B9%89%E8%A7%84%E5%88%99) 的说明，AstrBot 原来的「会话管理」功能已重构为「自定义规则」功能，以减少和配置文件的冲突。

3. **插件配置**：`_conf_schema.json` 的定义规范、`get_config()` 的多作用域用法。目前在 Context 文档中有零散提及，但没有集中说明。

4. **错误处理模式**：插件中异常捕获的最佳实践（防止插件崩溃影响主流程）。

### 结论

**可以开始写插件了。** 以上四个补充项都是"锦上添花"，不影响你的核心开发流程。遇到具体问题时再查也来得及——你这套文档已经覆盖了插件开发 90% 以上的常用场景。

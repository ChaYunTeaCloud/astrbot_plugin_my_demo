```
astrbot/
│
├── cli/                        ← 命令行入口
│   ├── __main__.py             ← python -m astrbot.cli → 启动
│   ├── commands/{run,conf...}  ← astrbot start / stop / config
│   └── utils/                  ← CLI 辅助
│
├── core/                       ← 框架核心（插件不直接访问）
│   │
│   ├── config/                 ← 全局配置加载
│   │
│   ├── db/                     ← SQLite / 向量数据库
│   │
│   ├── star/                   ← ★ 插件系统 ★
│   │   ├── star_manager.py     ←  PluginManager：发现→加载→生命周期
│   │   ├── context.py          ←  Context：插件的框架能力入口
│   │   ├── star.py             ←  Star 基类 + 废弃的 @register
│   │   ├── register/           ←  handler 注册（指令/钩子/工具）
│   │   └── star_handler.py     ←  @filter 事件分发机制
│   │
│   ├── agent/                  ← Agent 执行
│   │   ├── tool.py             ←  FunctionTool / ToolSet
│   │   ├── handoff.py          ←  HandoffTool（transfer_to_*）
│   │   ├── message.py          ←  Message 格式
│   │   ├── hooks.py            ←  Agent 生命周期 hooks
│   │   └── runners/            ←  各种 Agent 运行器
│   │       └── tool_loop_agent_runner.py  ← tool_loop_agent()
│   │
│   ├── provider/               ← LLM 提供商
│   │   ├── func_tool_manager.py ← ★ FunctionToolManager ★
│   │   │                          func_list + builtin_func_list
│   │   │                          get_full_tool_set()
│   │   │                          get_builtin_tool()
│   │   ├── entities.py         ←  ProviderRequest / LLMResponse
│   │   └── register.py         ←  llm_tools 全局变量
│   │
│   ├── pipeline/               ← 消息管道
│   │   ├── preprocess/         ←  预处理（切 AI 开关等）
│   │   ├── process_stage/      ←  核心处理 → LLM 推理
│   │   │   └── agent_sub_stages/ ← on_llm_request → LLM → on_llm_response
│   │   ├── respond/            ←  发送回复
│   │   └── result_decorate/    ←  结果装饰
│   │
│   ├── tools/                  ← 内置工具（astrbot_execute_*）
│   │   ├── computer_tools.py   ←  Shell/Python/文件工具类
│   │   └── registry.py         ←  按类名注册/查找
│   │
│   ├── platform/               ← 消息平台适配
│   │   └── sources/{qq,telegram,discord...}/
│   │
│   ├── conversation_mgr.py     ← 对话管理
│   ├── persona_mgr.py          ← 人格管理
│   ├── knowledge_base/         ← 知识库
│   └── utils/                  ← 内部工具函数
│
├── api/                        ← ★ 对外接口（插件用这个）★
│   ├── event/filter.py         ←  @filter.command / on_llm_request / ...
│   ├── star.py                 ←  Star / Context / AstrBotConfig
│   ├── provider/               ←  ProviderRequest 类型
│   ├── platform/               ←  消息平台类型定义
│   └── util/                   ←  工具函数
│
├── builtin_stars/              ← 系统内置插件
│   ├── astrbot/                ←  /plugin /help 等管理指令
│   └── builtin_commands/       ←  通用命令
│
├── dashboard/                  ← WebUI 后端
│
└── utils/                      ← 顶层工具
```

**核心依赖关系**：

```
cli ──→ core.start ──→ PluginManager ──→ 插件(Star)
                              │
                        ┌─────┘
                        ▼
            Context ←── core/star/context.py
               │            │
               ├── subagent_orchestrator
               ├── tool_loop_agent() ──→ tool_loop_agent_runner
               ├── get_llm_tool_manager() ──→ FunctionToolManager
               │        ├── func_list （@llm_tool 注册的）
               │        └── builtin_func_list （astrbot_*）
               │
        消息来 → pipeline/process_stage/
                    ├── on_llm_request 钩子
                    ├── LLM 推理
                    └── on_llm_response 钩子
```
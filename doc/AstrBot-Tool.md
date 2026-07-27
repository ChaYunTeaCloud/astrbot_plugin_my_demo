# AstrBot-Tool

在 AstrBot 中，Tool的本质是一个【FunctionTool】类。
根据文档；【star/guides/ai.md】的描述，想注册自己的 Tool 有两种方式，且两种方式最终都是 `FunctionTool` 实例：

- `@dataclass` 方式：你直接继承 `FunctionTool[AstrAgentContext]`
- `@filter.llm_tool` 装饰器：框架在背后自动把你的函数包成 `FunctionTool`，从 docstring 解析参数 schema

本质上 `llm_tools.func_list` 里存的都是 `FunctionTool` 对象。

## 【FunctionTool[AstrAgentContext]】里面的【parameters】参数是做什么的？

告诉 LLM 这个工具需要哪些参数、什么类型、是否必填。标准的 JSON Schema 格式，LLM 根据它来决定怎么调用你的工具。

假如有 `list_sub_agents` 工具 `parameters` 里 `properties: {}`，意思是不需要任何参数，LLM 直接空着调就行

【parameters】参数是工具的参数 schema，用于描述工具的输入参数。
【parameters】参数是一个 `dict`，键是参数名，值是参数的描述。
# AstrBot Provider 模块接口整理

> 源码路径：
> - API 导出: `../.venv/Lib/site-packages/astrbot/api/provider/__init__.py`
> - Provider 基类: `../.venv/Lib/site-packages/astrbot/core/provider/provider.py`
> - 实体类: `../.venv/Lib/site-packages/astrbot/core/provider/entities.py`
> - 注册机制: `../.venv/Lib/site-packages/astrbot/core/provider/register.py`
> - 管理器: `../.venv/Lib/site-packages/astrbot/core/provider/manager.py`

---

此文档覆盖了 Provider 模块的完整体系：

1. **API 导出**：7 个对外暴露的类和类型
2. **ProviderType 枚举**：5 种能力类型（对话、STT、TTS、嵌入、重排序）
3. **实体类详解**：ProviderRequest、LLMResponse、ProviderMeta、TokenUsage、ToolCallsResult、RerankResult
4. **Provider 基类体系**：6 个基类（AbstractProvider → Provider/STTProvider/TTSProvider/EmbeddingProvider/RerankProvider）
5. **ProviderManager**：属性、核心方法、动态加载、CRUD、事件通知
6. **注册机制**：`register_provider_adapter` 装饰器
7. **Provider 类型清单**：40+ 个内置适配器按能力分类列出
8. **配置结构**：provider、provider_sources、provider_settings、provider_stt_settings、provider_tts_settings

文档中也提示了 **Provider 是"上帝类"**——`Provider` 基类和 `ProviderManager` 接口众多，如果后续需要开发自定义 Provider 适配器，可以单独整理一份开发指南。

## 一、模块概述

Provider 模块是 AstrBot 的 **AI 能力层**，负责对接各大 AI 服务提供商（如 OpenAI、Anthropic、Gemini 等），为上层提供统一的对话、语音、嵌入、重排序等能力。

**核心概念**：
- **Provider（提供商适配器）**：对接到具体 AI 服务的适配器，如 `ProviderOpenAI`、`ProviderAnthropic`
- **ProviderManager（管理器）**：统一管理所有 Provider 实例，提供加载、切换、重载等能力
- **ProviderType（提供商类型）**：枚举，区分 Provider 的能力类型（对话、STT、TTS、嵌入、重排序）

---

## 二、API 导出

**文件**：../.venv/Lib/site-packages/astrbot/api/provider/__init__.py


```python
from astrbot.core.provider import Provider, STTProvider
from astrbot.core.provider.entities import (
    LLMResponse,
    ProviderMetaData,
    ProviderRequest,
    ProviderType,
)
```

**导出清单**：

| 名称 | 类型 | 说明 |
|------|------|------|
| `Provider` | 类 | 对话型 Provider 基类 |
| `STTProvider` | 类 | 语音转文本 Provider 基类 |
| `LLMResponse` | 数据类 | LLM 响应结果 |
| `ProviderMetaData` | 数据类 | Provider 元数据 |
| `ProviderRequest` | 数据类 | Provider 请求参数 |
| `ProviderType` | 枚举 | Provider 能力类型 |
| `Personality` | 数据库模型 | 人格配置（非 Provider 专属） |

---

## 三、ProviderType 枚举

**文件**：../.venv/Lib/site-packages/astrbot/core/provider/entities.py#L27

```python
class ProviderType(enum.Enum):
    CHAT_COMPLETION = "chat_completion"      # 文本对话
    SPEECH_TO_TEXT = "speech_to_text"        # 语音转文本
    TEXT_TO_SPEECH = "text_to_speech"        # 文本转语音
    EMBEDDING = "embedding"                  # 向量嵌入
    RERANK = "rerank"                        # 重排序
```

---

## 四、实体类详解

### 4.1 ProviderRequest（请求参数）

**文件**：../.venv/Lib/site-packages/astrbot/core/provider/entities.py#L88

Provider 请求参数封装，传递给 Provider 进行 AI 调用。

**属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `prompt` | `str \| None` | 提示词（与 contexts 二选一） |
| `session_id` | `str` | 会话 ID |
| `image_urls` | `list[str]` | 图片 URL 列表（多模态） |
| `audio_urls` | `list[str]` | 音频 URL 列表（多模态） |
| `extra_user_content_parts` | `list[ContentPart]` | 额外内容块（系统提醒、指令等） |
| `func_tool` | `ToolSet \| None` | 可用的函数工具（Function Calling） |
| `contexts` | `list[dict]` | OpenAI 格式上下文列表 |
| `system_prompt` | `str` | 系统提示词 |
| `conversation` | `Conversation \| None` | 关联的对话对象 |
| `tool_calls_result` | `list[ToolCallsResult] \| ToolCallsResult \| None` | 工具调用结果（用于多轮 Function Calling） |
| `model` | `str \| None` | 模型名称（None 使用默认） |

**关键方法**：

| 方法 | 说明 |
|------|------|
| `assemble_context()` | 将 prompt、image_urls、audio_urls 包装成统一消息格式（多模态） |
| `append_tool_calls_result(result)` | 添加工具调用结果到请求 |

### 4.2 LLMResponse（响应结果）

**文件**：../.venv/Lib/site-packages/astrbot/core/provider/entities.py#L294

LLM 响应结果封装。

**属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `role` | `str` | 角色（assistant、tool、err） |
| `result_chain` | `MessageChain \| None` | 消息链（推荐使用） |
| `completion_text` | `str` | 纯文本结果（过时，使用 result_chain） |
| `tools_call_args` | `list[dict]` | 工具调用参数 |
| `tools_call_name` | `list[str]` | 工具调用名称 |
| `tools_call_ids` | `list[str]` | 工具调用 ID |
| `tools_call_extra_content` | `dict[str, dict[str, Any]]` | 工具调用附加内容（tool_call_id → extra_content） |
| `reasoning_content` | `str \| None` | 推理内容（如思维链） |
| `reasoning_signature` | `str \| None` | 推理内容签名 |
| `raw_completion` | `ChatCompletion \| Response \| GenerateContentResponse \| AnthropicMessage \| None` | 原始 LLM 响应 |
| `is_chunk` | `bool` | 是否为分块响应 |
| `id` | `str \| None` | 响应 ID |
| `usage` | `TokenUsage \| None` | Token 使用量 |

**关键方法**：

| 方法 | 说明 |
|------|------|
| `to_openai_tool_calls()` | 转换为 OpenAI 工具调用格式（已过时） |
| `to_openai_tool_calls_model()` | 转换为 Pydantic 模型格式的工具调用（`to_openai_to_calls_model` 为错误拼写的弃用别名） |

### 4.3 ProviderMeta（Provider 实例元数据）

**文件**：../.venv/Lib/site-packages/astrbot/core/provider/entities.py#L35

```python
@dataclass
class ProviderMeta:
    id: str                    # 用户配置的唯一 ID
    model: str | None          # 当前使用的模型名
    type: str                  # 适配器名称（如 openai、ollama）
    provider_type: ProviderType  # 能力类型
```

### 4.4 ProviderMetaData（Provider 适配器注册元数据）

**文件**：../.venv/Lib/site-packages/astrbot/core/provider/entities.py#L50

```python
@dataclass
class ProviderMetaData(ProviderMeta):
    desc: str                          # 适配器描述
    cls_type: Any                      # 适配器类
    default_config_tmpl: dict | None    # 默认配置模板
    provider_display_name: str | None   # WebUI 显示名称
```

### 4.5 TokenUsage（Token 使用量）

**文件**：../.venv/Lib/site-packages/astrbot/core/provider/entities.py#L262

```python
@dataclass
class TokenUsage:
    input_other: int = 0    # 输入 Token 数（不含缓存）
    input_cached: int = 0   # 缓存命中 Token 数
    output: int = 0         # 输出 Token 数

    @property
    def total(self) -> int  # 总 Token = input_other + input_cached + output

    @property
    def input(self) -> int  # 输入 Token = input_other + input_cached
```

### 4.6 ToolCallsResult（工具调用结果）

**文件**：../.venv/Lib/site-packages/astrbot/core/provider/entities.py#L63

```python
@dataclass
class ToolCallsResult:
    tool_calls_info: AssistantMessageSegment        # 函数调用信息
    tool_calls_result: list[ToolCallMessageSegment]  # 函数调用结果

    def to_openai_messages(self) -> list[dict]          # 转换为 OpenAI 格式
    def to_openai_messages_model(self) -> list          # 转换为 Pydantic 模型
```

### 4.7 RerankResult（重排序结果）

**文件**：../.venv/Lib/site-packages/astrbot/core/provider/entities.py#L442

```python
@dataclass
class RerankResult:
    index: int             # 候选列表中的索引位置
    relevance_score: float  # 相关性分数
```

---

## 五、Provider 基类体系

### 5.1 AbstractProvider（抽象基类）

**文件**：../.venv/Lib/site-packages/astrbot/core/provider/provider.py#L27

所有 Provider 的抽象基类，提供公共方法。

**方法**：

| 方法 | 说明 |
|------|------|
| `set_model(model_name)` | 设置当前模型名 |
| `get_model()` | 获取当前模型名 |
| `meta()` | 获取 ProviderMeta 元数据 |
| `test()` | 测试 Provider 是否可用 |

### 5.2 Provider（对话型 Provider 基类）

**文件**：../.venv/Lib/site-packages/astrbot/core/provider/provider.py#L66

继承自 `AbstractProvider`，所有对话型 Provider 的基类。

**属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `provider_settings` | `dict` | Provider 全局配置 |

**抽象方法**（必须实现）：

| 方法 | 说明 |
|------|------|
| `get_current_key()` | 获取当前使用的 API Key |
| `set_key(key)` | 设置 API Key |
| `get_models()` | 获取支持的模型列表 |
| `text_chat(...)` | 执行文本对话（非流式） |

**text_chat 参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `prompt` | `str \| None` | 提示词 |
| `session_id` | `str \| None` | 会话 ID |
| `image_urls` | `list[str] \| None` | 图片 URL 列表 |
| `audio_urls` | `list[str] \| None` | 音频 URL 列表 |
| `func_tool` | `ToolSet \| None` | 工具集（Function Calling） |
| `contexts` | `list[Message] \| list[dict] \| None` | 对话上下文 |
| `system_prompt` | `str \| None` | 系统提示词 |
| `tool_calls_result` | `ToolCallsResult \| list[ToolCallsResult] \| None` | 工具调用结果 |
| `model` | `str \| None` | 模型名 |
| `extra_user_content_parts` | `list[ContentPart] \| None` | 额外的用户消息内容块（系统提醒、指令等） |
| `tool_choice` | `Literal["auto", "required"]` | 工具调用策略 |
| `request_max_retries` | `int \| None` | 最大重试次数 |

**非抽象方法**：

| 方法 | 说明 |
|------|------|
| `text_chat_stream(...)` | 流式文本对话（默认抛出 NotImplementedError） |
| `get_keys()` | 获取所有 API Key |
| `pop_record(context)` | 弹出第一条非系统提示词 |
| `_ensure_message_to_dicts(messages)` | 转换 Message 对象为字典列表 |
| `test(timeout=45)` | 测试 Provider（发送 "REPLY `PONG` ONLY"） |

### 5.3 STTProvider（语音转文本 Provider）

**文件**：../.venv/Lib/site-packages/astrbot/core/provider/provider.py#L214

继承自 `AbstractProvider`。

**抽象方法**：

| 方法 | 说明 |
|------|------|
| `get_text(audio_url)` | 获取音频的文本转写结果 |

**test 方法**：使用内置的 `stt_health_check.wav` 样本进行测试。

### 5.4 TTSProvider（文本转语音 Provider）

**文件**：../.venv/Lib/site-packages/astrbot/core/provider/provider.py#L234

继承自 `AbstractProvider`。

**抽象方法**：

| 方法 | 说明 |
|------|------|
| `get_audio(text)` | 获取文本的音频文件路径 |

**非抽象方法**：

| 方法 | 说明 |
|------|------|
| `support_stream()` | 是否支持流式 TTS（默认 False） |
| `get_audio_stream(text_queue, audio_queue)` | 流式 TTS 处理（默认累积后一次性生成） |
| `test()` | 测试 Provider（生成 "hi" 的音频） |

### 5.5 EmbeddingProvider（向量嵌入 Provider）

**文件**：../.venv/Lib/site-packages/astrbot/core/provider/provider.py#L320

继承自 `AbstractProvider`。

**抽象方法**：

| 方法 | 说明 |
|------|------|
| `get_embedding(text)` | 获取单条文本的向量 |
| `get_embeddings(texts)` | 批量获取文本的向量 |
| `get_dim()` | 获取向量维度 |

**非抽象方法**：

| 方法 | 说明 |
|------|------|
| `get_embeddings_batch(texts, batch_size, tasks_limit, max_retries, progress_callback)` | 分批并发获取向量（用于大规模嵌入） |

### 5.6 RerankProvider（重排序 Provider）

**文件**：../.venv/Lib/site-packages/astrbot/core/provider/provider.py#L412

继承自 `AbstractProvider`。

**抽象方法**：

| 方法 | 说明 |
|------|------|
| `rerank(query, documents, top_n)` | 对文档列表进行重排序 |

**参数**：
- `query`: 查询文本
- `documents`: 候选文档列表
- `top_n`: 返回前 N 个结果

---

## 六、ProviderManager（管理器）

**文件**：../.venv/Lib/site-packages/astrbot/core/provider/manager.py

统一管理所有 Provider 实例，提供加载、切换、重载、CRUD 等能力。

### 6.1 核心属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `provider_insts` | `list[Provider]` | 已加载的对话型 Provider 实例列表 |
| `stt_provider_insts` | `list[STTProvider]` | 已加载的 STT Provider 实例列表 |
| `tts_provider_insts` | `list[TTSProvider]` | 已加载的 TTS Provider 实例列表 |
| `embedding_provider_insts` | `list[EmbeddingProvider]` | 已加载的嵌入 Provider 实例列表 |
| `rerank_provider_insts` | `list[RerankProvider]` | 已加载的重排序 Provider 实例列表 |
| `inst_map` | `dict[str, Providers]` | Provider ID → 实例映射 |
| `llm_tools` | `FuncCall` | LLM 工具管理器 |
| `curr_provider_inst` | `Provider \| None` | 当前默认对话 Provider（过时） |
| `curr_stt_provider_inst` | `STTProvider \| None` | 当前默认 STT Provider（过时） |
| `curr_tts_provider_inst` | `TTSProvider \| None` | 当前默认 TTS Provider（过时） |

### 6.2 核心方法

| 方法 | 说明 |
|------|------|
| `initialize()` | 初始化所有 Provider（加载 + 设置默认） |
| `get_using_provider(provider_type, umo)` | 获取当前使用的 Provider（支持会话隔离） |
| `get_provider_by_id(provider_id)` | 根据 ID 获取 Provider 实例 |
| `set_provider(provider_id, provider_type, umo)` | 切换指定 Provider 为当前使用 |
| `get_provider_config_by_id(provider_id, merged)` | 根据 ID 获取配置 |
| `get_merged_provider_config(provider_config)` | 合并 provider 和 provider_source 配置 |

### 6.3 动态加载

| 方法 | 说明 |
|------|------|
| `dynamic_import_provider(type)` | 动态导入 Provider 适配器模块 |
| `load_provider(provider_config)` | 加载单个 Provider（创建实例、注册到对应列表） |
| `reload(provider_config)` | 重载 Provider（先 terminate 再 load） |
| `terminate_provider(provider_id)` | 终止 Provider 实例 |
| `terminate()` | 终止所有 Provider + MCP |

### 6.4 CRUD 操作

| 方法 | 说明 |
|------|------|
| `create_provider(new_config)` | 创建新 Provider 并加载 |
| `update_provider(origin_id, new_config)` | 更新 Provider 配置并重载 |
| `delete_provider(provider_id, provider_source_id)` | 删除 Provider 并终止 |

### 6.5 事件通知

| 方法 | 说明 |
|------|------|
| `set_provider_change_callback(cb)` | 设置 Provider 变更回调（单个） |
| `register_provider_change_hook(hook)` | 注册 Provider 变更钩子（多个） |
| `_notify_provider_changed(id, type, umo)` | 内部：通知变更 |

---

## 七、Provider 注册机制

**文件**：../.venv/Lib/site-packages/astrbot/core/provider/register.py

### 7.1 注册表

```python
provider_registry: list[ProviderMetaData] = []   # 已注册的 Provider 元数据列表
provider_cls_map: dict[str, ProviderMetaData] = {}  # Provider 类型名 → 元数据映射
llm_tools = FuncCall()                              # LLM 工具管理器
```

### 7.2 register_provider_adapter 装饰器

```python
def register_provider_adapter(
    provider_type_name: str,                    # Provider 类型名（如 "openai_chat_completion"）
    desc: str,                                  # 描述
    provider_type: ProviderType = ProviderType.CHAT_COMPLETION,  # 能力类型
    default_config_tmpl: dict | None = None,     # 默认配置模板
    provider_display_name: str | None = None,    # WebUI 显示名称
):
```

**使用示例**：

```python
@register_provider_adapter(
    provider_type_name="openai_chat_completion",
    desc="OpenAI GPT 系列",
    provider_type=ProviderType.CHAT_COMPLETION,
    default_config_tmpl={
        "type": "openai_chat_completion",
        "enable": False,
        "id": "openai_chat_completion",
        "key": ["sk-xxx"],
        "model": "gpt-4o",
    },
    provider_display_name="OpenAI",
)
class ProviderOpenAI(Provider):
    ...
```

---

## 八、Provider 类型清单

以下是 AstrBot 内置的 Provider 适配器类型（按能力分类）：

### 8.1 CHAT_COMPLETION（对话）

| 类型名 | 适配器 |
|--------|--------|
| `openai_chat_completion` | ProviderOpenAIOfficial |
| `longcat_chat_completion` | ProviderLongCat |
| `minimax_token_plan` | ProviderMiniMaxTokenPlan |
| `xiaomi_chat_completion` | ProviderXiaomi |
| `xiaomi_token_plan` | ProviderXiaomiTokenPlan |
| `zhipu_chat_completion` | ProviderZhipu |
| `groq_chat_completion` | ProviderGroq |
| `xai_chat_completion` | ProviderXAI |
| `aihubmix_chat_completion` | ProviderAIHubMix |
| `openrouter_chat_completion` | ProviderOpenRouter |
| `anthropic_chat_completion` | ProviderAnthropic |
| `kimi_code_chat_completion` | ProviderKimiCode |
| `googlegenai_chat_completion` | ProviderGoogleGenAI |

### 8.2 SPEECH_TO_TEXT（STT）

| 类型名 | 适配器 |
|--------|--------|
| `sensevoice_stt_selfhost` | ProviderSenseVoiceSTTSelfHost |
| `openai_whisper_api` | ProviderOpenAIWhisperAPI |
| `mimo_stt_api` | ProviderMiMoSTTAPI |
| `openai_whisper_selfhost` | ProviderOpenAIWhisperSelfHost |
| `xinference_stt` | ProviderXinferenceSTT |

### 8.3 TEXT_TO_SPEECH（TTS）

| 类型名 | 适配器 |
|--------|--------|
| `openai_tts_api` | ProviderOpenAITTSAPI |
| `mimo_tts_api` | ProviderMiMoTTSAPI |
| `genie_tts` | GenieTTSProvider |
| `edge_tts` | ProviderEdgeTTS |
| `gsv_tts_selfhost` | ProviderGSVTTS |
| `gsvi_tts_api` | ProviderGSVITTS |
| `fishaudio_tts_api` | ProviderFishAudioTTSAPI |
| `dashscope_tts` | ProviderDashscopeTTSAPI |
| `azure_tts` | AzureTTSProvider |
| `minimax_tts_api` | ProviderMiniMaxTTSAPI |
| `volcengine_tts` | ProviderVolcengineTTS |
| `gemini_tts` | ProviderGeminiTTSAPI |
| `elevenlabs_tts_api` | ProviderElevenLabsTTSAPI |

### 8.4 EMBEDDING（嵌入）

| 类型名 | 适配器 |
|--------|--------|
| `openai_embedding` | OpenAIEmbeddingProvider |
| `gemini_embedding` | GeminiEmbeddingProvider |
| `nvidia_embedding` | NvidiaEmbeddingProvider |
| `ollama_embedding` | OllamaEmbeddingProvider |

### 8.5 RERANK（重排序）

| 类型名 | 适配器 |
|--------|--------|
| `vllm_rerank` | VLLMRerankProvider |
| `xinference_rerank` | XinferenceRerankProvider |
| `bailian_rerank` | BailianRerankProvider |
| `nvidia_rerank` | NvidiaRerankProvider |
| `tei_rerank` | TEIRerankProvider |

---

## 九、配置结构

### 9.1 provider 配置项

```yaml
provider:
  - id: "openai_gpt4o"         # Provider 唯一 ID
    type: "openai_chat_completion"  # 适配器类型
    enable: true                 # 是否启用
    key: ["sk-xxx"]             # API Key 列表
    model: "gpt-4o"             # 默认模型
    # ... 其他 Provider 特定配置
```

### 9.2 provider_sources 配置项

```yaml
provider_sources:
  - id: "my_source"            # Source 唯一 ID
    type: "openai_chat_completion"
    key: ["sk-xxx"]
    # Provider 特定配置，可被 provider 引用
```

### 9.3 provider_settings 配置项

```yaml
provider_settings:
  enable: true
  default_provider_id: "openai_gpt4o"  # 默认对话 Provider
  # ... 其他全局设置
```

### 9.4 provider_stt_settings 配置项

```yaml
provider_stt_settings:
  enable: true
  provider_id: "whisper_api"  # 默认 STT Provider
```

### 9.5 provider_tts_settings 配置项

```yaml
provider_tts_settings:
  enable: true
  provider_id: "edge_tts"     # 默认 TTS Provider
```

---

## 十、对插件开发者的启示

1. **Provider 是"上帝类"**：`Provider` 基类和 `ProviderManager` 接口众多，如需自定义 Provider 适配器开发，建议单独整理文档
2. **通过 Context 访问 ProviderManager**：`context.provider_manager.get_using_provider(ProviderType.CHAT_COMPLETION)`
3. **支持会话隔离**：`get_using_provider` 的 `umo` 参数支持按会话隔离 Provider 选择
4. **动态切换 Provider**：通过 `set_provider()` 可在运行时切换 Provider
5. **自定义 Provider**：继承 `Provider`（或 `STTProvider`/`TTSProvider`/`EmbeddingProvider`/`RerankProvider`）并使用 `@register_provider_adapter` 装饰器注册

---

## 十一、关键文件索引

| 文件 | 作用 |
|------|------|
| `api/provider/__init__.py` | API 导出入口 |
| `core/provider/provider.py` | Provider 基类体系 |
| `core/provider/entities.py` | 实体类（Request、Response、Meta、TokenUsage 等） |
| `core/provider/register.py` | Provider 注册机制 |
| `core/provider/manager.py` | ProviderManager 管理器 |
| `core/provider/func_tool_manager.py` | LLM 工具管理器（FuncCall） |
| `core/provider/modalities.py` | 模态处理工具 |
| `core/provider/sources/*.py` | 40+ 个 Provider 适配器实现 |

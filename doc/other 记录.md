# 插件的本质

写插件就是在 AstrBot 运行的关键节点上注册 handler。插件整体是一个 handler 集合。
本质是写一堆 HOOK 或 Command 以及与之对应的 handler。
两种触发方式：

- **Hook（拦截/钩子）**：AstrBot 走完流程本应正常进行，我在中间截住、做完事、放行。
  - 一个事件(event)可以挂多个HOOK，一个 HOOK 对应一个 handler。
  - 同一个事件的HOOK，可以按 `priority` 排队执行，数值越大越优先，默认 0。每个 hook 对应一个 handler 方法。
  - AstrBot 提供了事件装饰器，为了结构，它专门做了一个 api 层（门面层）对这些装饰器进行了简单包装，并且提供了使用这些装饰器的入口： filter 。
  - 我可以用 filter 持有的装饰器告诉 AstrBot 我要钩住某个事件类型(eventType)。
  - 我给HOOK 写的 handler 就是我钩住这个事件之后要做什么，做完后解开这个钩子。
  - 比如：
    - 用@filter.on_llm_request() 钩住当有 LLM 请求时的事件：
      - AstrBot框架准备给LLM发消息了，用钩子把事件「拎起来」-> 改改提示词、塞几个工具 -> 把钩子放下去让AstrBot继续。
    - 用@filter.on_llm_response() 钩住当有 LLM 回复时的事件：
      - AstrBot框架收到LLM的回复了，用钩子把事件「拎起来」-> 处理回复、设置结果 -> 把钩子放下去让AstrBot继续。

- **Command（被调）**：AstrBot 识别到 `/xxx`，主动来找你：有没有人能处理？有就交给你。
  - 比如：
    - 我用 @filter.command(name="hello") 注册了一个 handler。
    - Astrbot识别到用户发送了 `/hello` 命令，调用这个handler。

# Handler

`@filter.xxx()` 装饰器标记的每个方法，AstrBot 都会将其注册为一个 Handler，存入 `star_handlers_registry` 中。当对应事件触发时，框架会遍历注册表，依次调用所有匹配的 Handler。

简化流程：
```
装饰器注册 → 存入注册表 → 事件触发 → 框架遍历注册表 → 逐个调用你的方法
```

只有符合条件的才会被调用 。比如 @filter.command(name="hello") 只有用户发送 "hello" 命令时才会触发； @filter.on_llm_request() 只有在 LLM 请求发出时才会触发，不是每条消息都会走。

## Handler 相关的核心源码路径：

1. Handler 注册与元数据定义
   - astrbot/core/star/star_handler.py
   - 包含： StarHandlerRegistry （注册表）、 StarHandlerMetadata （元数据）、 EventType （事件类型枚举）
2. 装饰器实现（@filter.xxx）
   - astrbot/core/star/register/star_handler.py
   - 包含： register_command 、 register_on_llm_request 等所有装饰器函数
3. Handler 实际调用逻辑
   - astrbot/core/pipeline/context_utils.py
   - 包含： call_handler() （执行单个 handler）、 call_event_hook() （执行事件钩子）
4. 命令/正则过滤器
   - astrbot/core/star/filter/command.py — CommandFilter
   - astrbot/core/star/filter/regex.py — RegexFilter

## Handler 实际调用逻辑

Handler 的调用逻辑分两层：

### 1. call_event_hook() — 事件钩子调用（适用于 @filter.on_llm_request 等）
位置： context_utils.py #L78-112

流程：
1. 从 star_handlers_registry 获取所有匹配 EventType 的 handler
2. 逐个调用 handler.handler(event, *args, **kwargs)
3. 每次调用后检查 event.is_stopped()，如果被停止则提前返回
4. 返回是否被终止

核心代码：
```python
handlers = star_handlers_registry.get_handlers_by_event_type(hook_type)
for handler in handlers:
    await handler.handler(event, *args, **kwargs)  # 直接调用
    if event.is_stopped():
        return True  # 事件被终止
```

### 2. call_handler() — 命令处理器调用（适用于 @filter.command 等）
位置： context_utils.py #L12-76

流程：
1. 调用 handler(event, *args, **kwargs) 得到返回值
2. 判断返回值类型：
   - 如果是异步生成器 → 支持"洋葱模型"，逐步执行 yield
   - 如果是协程 → 执行一次，取返回值
3. 如果返回 MessageEventResult/CommandResult → 设置到 event.set_result()
4. yield 控制权交回管道继续执行

核心代码：
```python
ready_to_call = handler(event, *args, **kwargs)

if inspect.isasyncgen(ready_to_call):
    # 异步生成器：逐步执行，支持洋葱模型
    async for ret in ready_to_call:
        if isinstance(ret, MessageEventResult):
            event.set_result(ret)
        yield
elif inspect.iscoroutine(ready_to_call):
    # 普通协程：执行一次
    ret = await ready_to_call
    if isinstance(ret, MessageEventResult):
        event.set_result(ret)
    yield
```

### ## 两者的区别

| 维度 | `call_event_hook` | `call_handler` |
|------|------------------|---------------|
| 用途 | 事件钩子（on_llm_request 等） | 命令处理（@filter.command） |
| 返回值处理 | 不处理返回值 | 处理 MessageEventResult 并设置到 event |
| 支持生成器 | 不支持 | 支持（洋葱模型） |
| 停止传播 | 支持（event.is_stopped） | 支持 |

简单说： call_event_hook 是"通知型"调用，只管调用不处理返回； call_handler 是"处理型"调用，会处理返回值并设置到事件对象上。

### 这两个方法为什么会放在 context_utils.py 而不是名为 handler_utils.py
猜测：

确实是"挂羊头卖狗肉"。从引用关系看：
- context_utils.py 被 pipeline/context.py 导入使用
- 它原本应该是给 Pipeline 的 Context 处理用的工具函数
- 但后来 Handler 调用逻辑也被放进来了

这种情况在开源项目中很常见—— 文件命名时它确实是放上下文工具的，但随着功能迭代，Handler 调用逻辑和"上下文处理"（事件在管道中的流转、结果设置）紧密耦合，就被放进来了 。严格来说应该改名叫 handler_utils.py 更准确。

## Handler 参数

虽然我们用装饰器来注册 handler，但是装饰器本身**不决定参数**，它只做一件事：**把函数注册到对应事件类型的 Handler 列表里**。

真正决定参数的是**触发事件的那段框架代码**。用图表示：

```
装饰器注册阶段：
@filter.on_llm_request
def my_handler(self, event, req): ...
         ↓
  只是标记：这个函数属于 EventType.OnLLMRequestEvent 类型
  不涉及任何参数定义


事件触发阶段（框架内部）：
  third_party.py#L335:
  call_event_hook(event, EventType.OnLLMRequestEvent, req)
                                              ↑
                                         这里传了 req
         ↓
  call_event_hook 内部：
  handler.handler(event, req)  → 函数被调用，收到 2 个参数
```

**结论：参数约束来自"谁触发了事件"，而不是装饰器本身。** 每个 `EventType` 在框架里只有一个（或几个）触发点，每个触发点固定传什么参数是写死的。这就是为什么同一种事件类型的所有 Handler 必须接收相同数量的参数。

# 事件

事件类型：.venv\Lib\site-packages\astrbot\core\star\star_handler.py
class EventType(enum.Enum)

# 装饰器

基本概念：装饰器就是一个接受函数作为参数的函数，返回一个新函数（或原函数）。一切围绕「函数是一等公民」——可以当作参数传、可以当作返回值返回。

以 @filter.on_llm_request 为例

查看 filter.on_llm_request() 的 on_llm_request
会被导航到【.venv\Lib\site-packages\astrbot\core\star\register\star_handler.py】里面的 register_on_llm_request
toolName: view_files
            
status: success
          
            
filePath: c:\Users\z\DockerApp\MyAgentBot\AstrBot\data\plugins\astrbot_plugin_my_demo\.venv\Lib\site-packages\astrbot\core\star\register\star_handler.py
          
`register_on_llm_request` 的设计是**两级函数**：

```python
def register_on_llm_request(**kwargs):      # 第一级：接收配置参数
    def decorator(awaitable):               # 第二级：接收你的函数
        _ = get_handler_or_create(awaitable, EventType.OnLLMRequestEvent, **kwargs)
        return awaitable
    return decorator                        # 返回真正的装饰器
```

register_on_llm_request() 返回 decorator 函数，decorator 接收一个参数。
而 
```python
@filter.on_llm_request()
async def my_handler(self, event, req):
    ...
```
其实是一个语法糖，等价于
```python
async def my_handler(self, event, req):
    ...

my_handler = filter.on_llm_request()(my_handler)
``` 



**加括号 `@filter.on_llm_request()`：**
```
Python 执行：filter.on_llm_request() → 返回 decorator 函数
然后执行：decorator(你的函数) → 完成注册
```

**不加括号 `@filter.on_llm_request`：**
```
Python 执行：filter.on_llm_request(你的函数)
→ 相当于把你的函数当位置参数传给 register_on_llm_request
→ 但 register_on_llm_request 只接受 **kwargs，不接受位置参数
→ TypeError!
```

简单说：**带括号是先调用外层函数拿到真正的装饰器，再用装饰器包你的函数；不带括号会直接把你的函数传给外层函数，而外层函数不接收位置参数，就报错了。**

这是 Python 装饰器的标准设计模式——需要配置参数的装饰器都必须加括号调用。
# AstrBot Web 模块接口整理

> 源码路径：`../.venv/Lib/site-packages/astrbot/api/web.py`

---

## 一、模块概述

`api.web` 模块提供插件 Web API 开发能力，允许插件注册 HTTP 端点，接收和处理 Web 请求。这对于需要与外部系统交互的插件非常有用，比如提供管理后台、接收回调通知等。

---

## 二、API 导出

**文件**：../.venv/Lib/site-packages/astrbot/api/web.py

```python
__all__ = [
    "PluginMultiDict",
    "PluginRequest",
    "PluginRequestProxy",
    "PluginUploadFile",
    "bind_request_context",
    "error_response",
    "file_response",
    "json_response",
    "request",
    "stream_response",
]
```

---

## 三、核心类与函数

### 3.1 request（请求代理）

**文件**：../.venv/Lib/site-packages/astrbot/api/web.py#L322

`PluginRequestProxy` 实例，用于在 Web API 处理函数中获取当前请求信息。

**属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `method` | `str` | HTTP 方法（GET/POST/PUT 等） |
| `path` | `str` | 请求路径 |
| `headers` | `Headers` | 请求头 |
| `cookies` | `dict[str, str]` | Cookie |
| `content_type` | `str \| None` | 内容类型 |
| `client_host` | `str \| None` | 客户端 IP |
| `path_params` | `dict[str, Any]` | 路径参数 |
| `plugin_name` | `str \| None` | 插件名称 |
| `username` | `str \| None` | 用户名（WebUI 登录用户） |
| `query` | `PluginMultiDict[str]` | 查询参数 |

**异步方法**：

| 方法 | 说明 |
|------|------|
| `body()` | 读取原始请求体（bytes） |
| `json(default=None)` | 读取 JSON 请求体 |
| `form()` | 读取表单字段 |
| `files()` | 读取上传文件 |

**使用示例**：

```python
from astrbot.api.web import request

async def my_handler():
    # 获取查询参数
    name = request.query.get("name")
    
    # 获取 JSON 体
    data = await request.json()
    
    # 获取表单数据
    form_data = await request.form()
    
    # 获取上传文件
    files = await request.files()
```

### 3.2 PluginMultiDict（多值字典）

**文件**：../.venv/Lib/site-packages/astrbot/api/web.py#L20

用于处理请求中的多值参数（如 `?tag=foo&tag=bar`）。

**方法**：

| 方法 | 说明 |
|------|------|
| `get(key, default=None, type=None)` | 获取最后一个值，支持类型转换 |
| `getlist(key)` | 获取所有值 |
| `keys()` | 获取所有键 |
| `values()` | 获取所有值（去重） |
| `items()` | 获取所有键值对（去重） |

**使用示例**：

```python
# URL: ?tag=foo&tag=bar&limit=10
tags = request.query.getlist("tag")  # ["foo", "bar"]
limit = request.query.get("limit", type=int)  # 10
```

### 3.3 PluginUploadFile（上传文件）

**文件**：../.venv/Lib/site-packages/astrbot/api/web.py#L95

**属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `filename` | `str \| None` | 文件名 |
| `content_type` | `str \| None` | 内容类型 |
| `headers` | `Headers` | 文件头 |
| `content_length` | `int \| None` | 文件大小 |

**异步方法**：

| 方法 | 说明 |
|------|------|
| `save(destination)` | 保存文件到磁盘 |
| `read(size=-1)` | 读取文件内容 |
| `write(data)` | 写入文件 |
| `seek(offset)` | 移动文件指针 |
| `close()` | 关闭文件 |

**使用示例**：

```python
files = await request.files()
uploaded_file = files.get("file")
if uploaded_file:
    await uploaded_file.save("/path/to/save/file.pdf")
    content = await uploaded_file.read()
```

### 3.4 json_response（JSON 响应）

**文件**：../.venv/Lib/site-packages/astrbot/api/web.py#L342

```python
def json_response(
    data: Any = None,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
```

**使用示例**：

```python
from astrbot.api.web import json_response

async def handler():
    return json_response({"status": "success", "data": {"id": 1}})
    return json_response({"message": "error"}, status_code=400)
```

### 3.5 error_response（错误响应）

**文件**：../.venv/Lib/site-packages/astrbot/api/web.py#L365

```python
def error_response(
    message: str,
    *,
    status_code: int = 400,
    data: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
```

**返回格式**：

```json
{
    "status": "error",
    "message": "错误信息",
    "data": {...}
}
```

**使用示例**：

```python
from astrbot.api.web import error_response

async def handler():
    return error_response("参数错误", status_code=400)
    return error_response("资源未找到", status_code=404, data={"id": 1})
```

### 3.6 file_response（文件响应）

**文件**：../.venv/Lib/site-packages/astrbot/api/web.py#L390

```python
def file_response(
    path: str | Path,
    *,
    filename: str | None = None,
    content_type: str | None = None,
    headers: dict[str, str] | None = None,
) -> FileResponse:
```

**使用示例**：

```python
from astrbot.api.web import file_response

async def download_handler():
    return file_response("/path/to/file.pdf", filename="report.pdf")
```

### 3.7 stream_response（流式响应）

**文件**：../.venv/Lib/site-packages/astrbot/api/web.py#L416

```python
def stream_response(
    content: Any,
    *,
    content_type: str = "text/event-stream",
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> StreamingResponse:
```

**使用示例**：

```python
from astrbot.api.web import stream_response

async def stream_handler():
    async def generate():
        yield "data: hello\n\n"
        yield "data: world\n\n"
    return stream_response(generate(), content_type="text/event-stream")
```

### 3.8 bind_request_context（绑定请求上下文）

**文件**：../.venv/Lib/site-packages/astrbot/api/web.py#L325

内部函数，用于在 Web 请求上下文中绑定 `request` 对象。

---

## 四、完整示例

```python
from astrbot.api.star import Star
from astrbot.api.web import request, json_response, error_response, file_response

class WebPlugin(Star):
    def __init__(self, context):
        super().__init__(context)
        self.context.register_web_api("/api/v1/users", self.get_users, ["GET"], "获取用户列表")
        self.context.register_web_api("/api/v1/users", self.create_user, ["POST"], "创建用户")
        self.context.register_web_api("/api/v1/upload", self.upload_file, ["POST"], "上传文件")
        self.context.register_web_api("/api/v1/download/{file_id}", self.download_file, ["GET"], "下载文件")

    async def get_users(self):
        # 获取查询参数
        page = request.query.get("page", type=int, default=1)
        limit = request.query.get("limit", type=int, default=10)
        
        # 返回 JSON
        return json_response({
            "page": page,
            "limit": limit,
            "users": []
        })

    async def create_user(self):
        # 获取 JSON 体
        data = await request.json()
        
        if not data or "name" not in data:
            return error_response("缺少 name 参数", status_code=400)
        
        # 创建用户逻辑...
        
        return json_response({"id": 1, "name": data["name"]}, status_code=201)

    async def upload_file(self):
        # 获取上传文件
        files = await request.files()
        file = files.get("file")
        
        if not file:
            return error_response("未上传文件", status_code=400)
        
        # 保存文件
        await file.save("/path/to/uploads/" + file.filename)
        
        return json_response({"status": "success", "filename": file.filename})

    async def download_file(self, file_id):
        # 获取路径参数
        file_path = f"/path/to/files/{file_id}.pdf"
        
        # 返回文件下载
        return file_response(file_path, filename=f"{file_id}.pdf")
```

---

## 五、注意事项

1. **request 作用域**：`request` 对象只能在 Web API 处理函数内部使用，在其他地方会抛出 `RuntimeError`
2. **异步方法**：`body()`、`json()`、`form()`、`files()` 都是异步方法，需要 `await`
3. **路径参数**：通过处理函数的参数接收，如 `/api/v1/users/{id}` → `async def handler(id)`
4. **文件上传**：使用 `await request.files()` 获取上传文件，然后用 `save()` 保存
5. **响应类型**：`json_response`、`error_response`、`file_response`、`stream_response` 返回的都是 FastAPI/Starlette 的 Response 对象
6. **注册方式**：在插件 `__init__` / `initialize` 中调用 `self.context.register_web_api(route, view_handler, methods, desc)` 注册 Web API 端点

---

## 六、Web API 注册装饰器

虽然不在 `api.web` 模块中，但需要配合使用：

```python
self.context.register_web_api(route, view_handler, methods, desc)
```

**参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `route` | `str` | API 路径，支持路径参数如 `/users/{id}` |
| `view_handler` | 异步函数 | 处理请求的视图函数 |
| `methods` | `list[str]` | HTTP 方法列表 |
| `desc` | `str` | API 描述 |

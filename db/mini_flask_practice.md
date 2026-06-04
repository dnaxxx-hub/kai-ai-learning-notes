# MiniFlask 实践笔记

## 概述

纯 Python 零外部依赖的 HTTP Web 框架（类 Flask），基于标准库 `http.server` 实现。

## 实现的功能

### 1. 路由系统
- 装饰器 `@app.route('/path', methods=['GET'])` 注册路由
- 路径参数: `/user/<int:id>`, `/name/<str:name>`, `/float/<val>`, `<path:remaining>`
- `url_for(endpoint, **kwargs)` — 反向 URL 生成
- `add_route(path, handler, methods)` — 直接注册
- 内部用 `re.compile()` 编译的正则匹配

### 2. 请求/响应
- `Request` — 封装 path, method, headers, body, args, form
- `Response` — status_code, headers, body, set_cookie, delete_cookie
- JSON 自动序列化: dict/list → JSON 响应

### 3. 中间件
- `@app.before_request` — 请求前执行，可修改 Request
- `@app.after_request` — 请求后执行，可修改 Response

### 4. 模板引擎（嵌入式）
- `{{ name }}` — 变量替换（支持 dict 属性访问 `obj.key`）
- `{% for item in list %} ... {% endfor %}` — 循环
- `{% if cond %} ... {% else %} ... {% endif %}` — 条件
- 支持比较操作符: ==, !=, >, <, >=, <=
- `{% if not cond %}` — 取反

### 5. 静态文件
- `app.static('/static', directory)` — 静态文件服务

### 6. 错误处理
- `@app.error_handler(404)` — 自定义错误页面
- 默认 404/500 页面

### 7. 启动
- `app.run(host='0.0.0.0', port=8080)` — 启动 HTTP 服务器

## 测试结果

20 项测试全部通过:
1. ✅ 路由注册和匹配（GET）
2. ✅ 路由注册和匹配（POST）
3. ✅ URL 路径参数 `<int:id>` — `/user/42`
4. ✅ URL 路径参数 `<str:name>` — `/name/alice`
5. ✅ JSON 响应 — dict 自动序列化
6. ✅ Before 请求中间件
7. ✅ After 请求中间件
8. ✅ 404 错误处理 — 自定义 + 默认
9. ✅ 查询参数解析 — `?q=hello&page=3`
10. ✅ POST 表单数据 — `application/x-www-form-urlencoded`
11. ✅ `url_for` 反向生成 — `/user/42`
12. ✅ Cookie 设置 — set_cookie / HttpOnly / Max-Age
13. ✅ Cookie 删除 — Max-Age=0
14. ✅ 模板渲染 — 变量 + 循环 + 条件
15. ✅ 重定向（302）
16. ✅ 重定向（301 / 永久）
17. ✅ 多路径参数组合 — `/<int:year>/<str:slug>`
18. ✅ Float 路径参数 — `/float/3.14`
19. ✅ 500 错误处理
20. ✅ 方法不匹配（POST → GET-only route → 404）

## 测试方法
- 使用 `unittest` 框架
- 启动真实 HTTP 服务器（线程）
- 通过 `http.client` 发送真实 HTTP 请求
- 验证 status, headers, body

## 文件结构

```
projects/mini_flask/
├── mini_flask.py      # 框架核心 (~21KB)
├── test_mini_flask.py # 测试文件 (~12KB)
└── static/
    └── test.txt       # 静态文件测试
```

## 关键实现细节

### 路由匹配
- 用 `re.finditer(r'<(\w+):(\w+)>')` 解析路径参数
- 支持类型转换器: int → `(\d+)`, float → `(\d+\.?\d*)`, str → `([^/]+)`, path → `(.+)`
- URL 编码: 生成的 URL 保持原始格式，无需特殊转义

### 模板引擎
- 逐行解析 + 递归渲染
- 循环和条件嵌套用 `depth` 计数器追踪
- 变量解析支持链式访问: `user.name`
- 条件表达式支持 `==`, `!=`, `>`, `<`, `>=`, `<=`, `not`

### Cookie
- `set_cookie()` 支持 Path, Max-Age, Domain, Secure, HttpOnly, SameSite
- `delete_cookie()` 设置 Max-Age=0
- 多个 Set-Cookie 头正确发送（`_cookies` 列表）

### 响应
- `redirect()` 辅助函数创建 301/302 响应
- tuple unpacking: `(body, status)`, `(body, status, headers)`

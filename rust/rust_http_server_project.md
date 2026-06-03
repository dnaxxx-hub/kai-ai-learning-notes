# Rust Phase 2 项目：轻量 HTTP 服务器

> 2026-05-17
> 基于 Rust #10 异步编程实战

## 项目结构

```
rust_http_server/
├── Cargo.toml          # tokio + serde_json + chrono + encoding_rs
└── src/
    └── main.rs         # ~12KB，单文件包含所有逻辑
```

## 架构设计

```
TcpListener (端口 8080/自定义)
    │
    ├── accept() ─── tokio::spawn ─── handle_connection()
    │                                       │
    │                                  parse_request() ← 手动 HTTP 解析
    │                                       │
    │                                  Router.handle(req)
    │                                       │
    │                                  Response.to_bytes() → stream.write_all
    │
    └── (循环执行)
```

## 主要模块

### 1. HTTP 类型系统

- `Method` — 枚举（GET/POST/PUT/DELETE 等），`From<&str>`
- `Request` — method/path/query/headers/body，附带 `body_json<T>()`
- `StatusCode` — 常量化（OK/BAD_REQUEST/NOT_FOUND/INTERNAL_ERROR）
- `Response` — Builder 模式，`json()`/`text()`/`html()` + `to_bytes()` 序列化

### 2. 手动 HTTP 请求解析 `parse_request()`

```rust
pub fn parse_request(data: &[u8]) -> Result<Request, String>
```

- 按 `\r\n\r\n` 分割 header/body
- 解析请求行 `METHOD URI HTTP/1.1`
- 解析 query string（URL decode）
- 解析 headers（Hashmap）

### 3. 路由器 `Router`

```rust
router.get("/ping", ping_handler);
router.post("/api/echo", echo_post_handler);
```

- Handler 类型：`Arc<Fn(Request) -> Pin<Box<Future<Output = Response>>>>`
- 精确路径匹配，支持 GET/POST 注册
- 不匹配返回 404 JSON

### 4. 端点处理器

| 端点 | 方法 | 功能 |
|:----|:----|:----|
| `/` | GET | HTML 首页 |
| `/ping` | GET | `{"status":"ok"}` |
| `/echo?text=` | GET | 回显 query 参数 |
| `/time` | GET | 服务器时间（含 timestamp） |
| `/api/stock?code=` | GET | 腾讯 API 股票行情代理 |
| `/api/echo` | POST | JSON Body 回显 |

### 5. 关键设计决策

- **`spawn_blocking` 处理阻塞操作**：股票查询用标准 `TcpStream`，通过 `spawn_blocking` 隔离，不阻塞事件循环
- **`move` 闭包的 clone 问题**：closure 需要独占变量所有权时，在外层 clone 一次，闭包内用克隆，外层用原变量
- **`subprocess.Popen` 启动服务**：测试环境用 Python 启动二进制进程，`os.environ['PORT']` 传参

## 测试结果

```
=== Kai HTTP Server Tests ===
    Start 6 test: /ping /time /echo / /api/stock /api/echo POST 404
    All passed ✓
```

## 学到的东西

1. **Tokio 异步 I/O 实战**：`TcpListener::accept()` + `tokio::spawn` 是 Rust 高并发服务器的标准模式
2. **手动 HTTP 解析**：比想象中简单——本质上就是分割字符串和 hashmap
3. **Builder 模式的实用价值**：`resp.header().json()` 链式调用比构造参数更灵活
4. **PowerShell 进程管理坑**：`Start-Process` 传环境变量麻烦，`Start-Job` 不稳定，测试最好写一个完整脚本
5. **Windows 端口占用**：TIME_WAIT 导致短时间内端口重用失败

## 下一步

- [ ] **连接池**：复用 TCP 连接（Connection: keep-alive）
- [ ] **路径参数路由**：`/api/stock/{code}` 格式
- [ ] **中间件链**：日志/超时/CORS
- [ ] **HTTPS/TLS**：用 rustls 或 native-tls

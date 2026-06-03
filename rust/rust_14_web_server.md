# Rust #14：手写 HTTP 服务器 — tokio::net 实战

> 2026-05-25
> 目标：用 tokio::net 从零手写 HTTP 服务器，不依赖任何 Web 框架

## 1. HTTP 协议本质

HTTP/1.1 是一个**基于 TCP 的文本协议**：

```
请求:
GET /api/time HTTP/1.1\r\n
Host: 127.0.0.1:8080\r\n
User-Agent: curl/8.0\r\n
\r\n
[body]

响应:
HTTP/1.1 200 OK\r\n
Content-Type: application/json\r\n
Content-Length: 45\r\n
Server: KaiMiniServer/0.1\r\n
\r\n
{"time":"2026-05-25 10:30:00","timestamp":...}
```

关键结构：
- **请求行**：`METHOD PATH HTTP/VERSION`
- **Headers**：`Key: Value`，以 `\r\n` 分隔
- **空行**：`\r\n\r\n` 分隔 headers 和 body
- **Body**：长度由 `Content-Length` header 指定

## 2. 异步 TCP 服务器框架

```rust
#[tokio::main]
async fn main() {
    let listener = TcpListener::bind("127.0.0.1:8080").await.unwrap();

    loop {
        let (stream, addr) = listener.accept().await.unwrap();
        // 每个连接一个轻量级 tokio task
        tokio::spawn(async move {
            handle_connection(stream).await;
        });
    }
}
```

### 与传统同步服务器的对比

**同步（每连接一线程）**：
```rust
for stream in listener.incoming() {
    std::thread::spawn(move || handle(stream.unwrap()));
}
```
- 每个连接消耗 ~2MB 线程栈
- 10k 并发 → 20GB 内存
- 线程切换有内核态开销

**异步（Tokio）**：
```rust
loop {
    let (stream, addr) = listener.accept().await.unwrap();
    tokio::spawn(async move { handle(stream).await; });
}
```
- 每个 task 只消耗 ~KB 级别的状态机
- 10k 并发 → 几 MB 内存
- 所有 task 在少量线程上协作调度

## 3. HTTP 请求解析 — 状态机实践

```rust
fn parse_http_request(buf: &[u8]) -> Result<Request, String> {
    // 找 \r\n\r\n → headers 结束 / body 开始
    let header_end = buf.windows(4)
        .position(|w| w == b"\r\n\r\n")
        .ok_or("找不到 header 结束")?;

    let header_str = std::str::from_utf8(&buf[..header_end])?;

    // 解析请求行
    let mut lines = header_str.lines();
    let request_line = lines.next().ok_or("空请求")?;
    let parts: Vec<&str> = request_line.split_whitespace().collect();

    // 解析 headers → HashMap
    let mut headers = HashMap::new();
    for line in lines {
        if let Some((k, v)) = line.split_once(':') {
            headers.insert(k.trim().to_lowercase(), v.trim().to_string());
        }
    }

    // 提取 body
    let body = buf[header_end + 4..].to_vec();
    Ok(Request { method, path, headers, body })
}
```

**关键设计决策**：
- 使用 `HashMap<String, String>` 存 headers，方便查找
- header key 统一小写化，解决大小写不敏感问题
- 用 `windows(4)` 找 `\r\n\r\n` 分隔符
- 不处理大请求（超过 8KB buffer 的 body）

## 4. 路由系统设计

```rust
struct Router {
    routes: Vec<(Method, String, Handler)>,
}

impl Router {
    fn add<F>(&mut self, method: Method, path: &str, handler: F)
    where F: Fn(Request, SharedState) -> Response + Send + Sync + 'static
    { ... }

    fn route(&self, req: &Request) -> Option<&Handler> {
        for (method, pattern, handler) in &self.routes {
            if *method != req.method { continue; }
            if path_matches(&req.path, pattern) {
                return Some(handler);
            }
        }
        None
    }
}
```

**路径匹配**：支持通配符 `/*`

```rust
fn path_matches(path: &str, pattern: &str) -> bool {
    if pattern == "/*" { return true; }
    if let Some(prefix) = pattern.strip_suffix("/*") {
        return path == prefix || path.starts_with(&format!("{}/", prefix));
    }
    path == pattern
}
```

## 5. 共享状态模型

```rust
type SharedState = Arc<Mutex<AppState>>;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct AppState {
    visit_count: u64,
    messages: Vec<String>,
}
```

为什么用 `Arc<Mutex<>>`？
- **Arc**（Atomic Reference Counting）：多 task 共享同一份数据
- **Mutex**：互斥访问，防止数据竞争
- `tokio::sync::Mutex` vs `std::sync::Mutex`：
  - Tokio Mutex 可以在 `.await` 中持有（挂起时不会死锁）
  - 标准库 Mutex 在 `.await` 中持有会导致死锁（线程挂起时锁不释放）

> 实际上，对于简单的同步操作（如 count++），我们使用 `.blocking_lock()` 更合适，避免 async 内部持有锁导致死锁。

## 6. 响应序列化

```rust
impl Response {
    fn to_bytes(&self) -> Vec<u8> {
        let mut buf = format!(
            "HTTP/1.1 {} {}\r\n",
            self.status, self.status_text
        ).into_bytes();

        for (k, v) in &self.headers {
            buf.extend_from_slice(
                format!("{}: {}\r\n", k, v).as_bytes()
            );
        }
        buf.extend_from_slice(b"\r\n");
        buf.extend_from_slice(&self.body);
        buf
    }
}
```

**为什么手写而不是用 format!？**
- `Content-Length` 必须在序列化 body 之后才能确定
- 保持对协议细节的完全控制
- 便于理解 HTTP 协议底层

## 7. 端点示例

| 端点 | 方法 | 功能 |
|:-----|:-----|:-----|
| `/` | GET | 首页 + 访问计数 |
| `/api/status` | GET | 服务器状态 JSON |
| `/api/time` | GET | 当前时间 JSON |
| `/api/message` | POST | 发送消息 `{"text":"..."}` |
| `/api/messages` | GET | 获取所有消息 |
| `/static/*` | GET | 静态文件服务 |

## 8. 关键技术点总结

| 概念 | Rust 实现 | 关键 API |
|:-----|:---------|:---------|
| TCP 监听 | Tokio | `TcpListener::bind().await` |
| 异步读写 | Tokio | `AsyncReadExt::read()`, `AsyncWriteExt::write_all()` |
| 并发连接 | Tokio | `tokio::spawn` → 每个连接一个轻量 task |
| 共享状态 | `Arc<Mutex<T>>` | 引用计数 + 互斥锁 |
| 序列化 | serde_json | `to_string()`, `from_str()` |
| HTTP 解析 | 手写 | `windows(4).position(\r\n\r\n)` |

## 9. 与 Python Flask 对比

```python
# Flask
@app.route('/api/time')
def handle_time():
    return jsonify({"time": str(datetime.now())})

# Rust
router.add(Method::GET, "/api/time", |_req, _state| {
    Response::json(&serde_json::json!({"time": ...}))
});
```

Rust 的编码量确实更大，但换来的是：
- **性能**：单线程处理 10k+ 并发
- **类型安全**：编译器保证数据类型正确
- **无 GC 停顿**：实时性更好
- **零依赖**：甚至可以不用任何框架

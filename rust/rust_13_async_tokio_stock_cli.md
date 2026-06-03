# Rust #13：深入 Tokio 异步 — stock_cli 重构与实时推送

> 2026-05-25
> 目标：将 stock_cli 完全重写为 Tokio 异步版本，支持并发查询 + 实时行情推送

## 1. 架构演进

### 从同步到异步

| 版本 | 方式 | 并发 | 延迟 |
|:-----|:-----|:-----|:-----|
| v1 (rust #7) | 子进程 Python urllib | 串行 | 每只 ~0.5-1s |
| v1.5 (已有 async_fetch.rs) | Tokio TcpStream raw HTTP | 并行（tokio::spawn）| 全部 ~0.3s |
| **v2 (本课)** | Tokio + watch channel | 并行 + 后台轮询 | 实时推送 |

### 关键设计决策

1. **不再依赖 Python 子进程** — 使用 `tokio::net::TcpStream` 直连 qt.gtimg.cn:80
2. **手写 HTTP 解析** — 避免引入 reqwest 依赖，深度理解 HTTP 协议
3. **chunked transfer encoding** — 腾讯接口使用 chunked 编码，需要手动解析
4. **GBK 解码** — 腾讯返回 GBK 编码的汉字，使用 `encoding_rs` crate

## 2. 核心代码分析

### 2.1 异步 TCP 连接

```rust
pub async fn fetch_one(code: &str) -> Result<TencentQuote, String> {
    // tokio::net::TcpStream::connect 是异步的
    let mut stream = TcpStream::connect("qt.gtimg.cn:80")
        .await
        .map_err(|e| format!("连接失败 {}: {}", code, e))?;

    // 构建原始 HTTP GET 请求
    let req = format!(
        "GET /q={} HTTP/1.1\r\nHost: qt.gtimg.cn\r\n...",
        code
    ).into_bytes();

    // 异步写入 + 读取
    stream.write_all(&req).await?;
    let mut buf = [0u8; 8192];
    loop {
        let n = stream.read(&mut buf).await?;
        if n == 0 { break; }
        response.extend_from_slice(&buf[..n]);
    }
    // 然后手动解析 HTTP + chunked 编码
}
```

**对比 Python urllib**：Python 的 `urllib.request.urlopen` 会：
- 自动 DNS 解析
- 自动 TCP 连接
- 自动发送 HTTP 请求
- 自己解析 HTTP 响应

Rust 手写 TCP 连接则需要在应用层协议上完全自己实现。

### 2.2 并发查询

```rust
pub async fn fetch_batch(codes: &[String]) -> Vec<(String, Result<TencentQuote, String>)> {
    let mut handles = Vec::new();
    for code in codes {
        let c = code.clone();
        // tokio::spawn 将任务提交到运行时，多个任务在同一个线程上协作调度
        handles.push(tokio::spawn(async move {
            (c.clone(), fetch_one(&c).await)
        }));
    }
    let mut results = Vec::new();
    for handle in handles {
        results.push(handle.await);  // join 所有任务
    }
    results
}
```

**为什么 tokio::spawn 比 std::thread::spawn 好？**
- 一个线程可以管理上千个 tokio task（每个 task 只是一个状态机）
- task 切换是用户态的，没有内核态上下文切换
- 访问同一线程上的数据不需要 Mutex（单线程内部）

### 2.3 实时推送：watch channel

```rust
pub fn spawn_price_poller(
    codes: Vec<String>,
    interval_secs: u64,
    tx: tokio::sync::watch::Sender<Vec<TencentQuote>>,
) -> tokio::task::JoinHandle<()> {
    tokio::spawn(async move {
        loop {
            let results = fetch_batch(&codes).await;
            let mut quotes = Vec::new();
            for (code, result) in &results {
                match result {
                    Ok(q) => quotes.push(q.clone()),
                    Err(e) => eprintln!("[poller] 获取 {code} 失败: {e}"),
                }
            }
            if !quotes.is_empty() {
                let _ = tx.send(quotes);
            }
            tokio::time::sleep(Duration::from_secs(interval_secs)).await;
        }
    })
}
```

主循环在 **同一个** main 线程中：
```rust
loop {
    rx.changed().await?;            // 等待 poller 推送新数据
    let quotes = rx.borrow().clone();
    print_table(&quotes);
    println!("[{}] 已刷新", chrono::Local::now().format("%H:%M:%S"));
    println!();
}
```

`tokio::sync::watch` 是一个 **多生产者单消费者** 的 channel：
- 广播最后一条消息给所有消费者
- rx.changed() 等待新值
- 无缓冲，永远保存最新值

### 2.4 Chunked Transfer Encoding 解析

```rust
fn decode_chunked_body(data: &[u8]) -> Result<Vec<u8>, String> {
    // 1. 找到 \r\n\r\n（HTTP header 结束）
    let body_start = data.windows(4)
        .position(|w| w == b"\r\n\r\n")
        .map(|p| p + 4).unwrap_or(0);

    let mut body = &data[body_start..];
    // 2. 逐块解析 chunk-size（十六进制） + chunk-data
    loop {
        let crlf = body.windows(2).position(|w| w == b"\r\n").unwrap_or(body.len());
        let size_str = std::str::from_utf8(&body[..crlf]).unwrap().trim();
        let chunk_size = usize::from_str_radix(size_str, 16)?;
        if chunk_size == 0 { break; }  // 最后一块
        // 复制 chunk data
        result.extend_from_slice(&body[chunk_start..chunk_start + chunk_size]);
        body = &body[chunk_start + chunk_size + 2..];  // 跳过 trailing CRLF
    }
    Ok(result)
}
```

## 3. 与 C++ Boost.Asio 对比

| 概念 | Rust Tokio | C++ Boost.Asio |
|:-----|:-----------|:---------------|
| 异步运行时 | tokio::runtime | io_context |
| Task | tokio::spawn (async fn) | boost::asio::co_spawn |
| TCP | TcpStream::connect() | async_connect() |
| Channel | tokio::sync::watch | boost::asio::channel |
| 错误处理 | Result<T, E> (? 操作符) | 异常抛出或 error_code |
| 生命周期 | 编译器检查 | 开发者自行管理 |

**Rust 的优势**：
- Future 是**惰性的** — 不 await 就不执行，防止遗忘
- 编译期检查 lifetimes，无悬挂指针
- `?` 操作符使错误传播极其简洁

**C++ 的优势**：
- Coroutines 可以更自然地实现生成器模式
- 模板元编程能力更强
- 更成熟的第三方异步库生态

## 4. 运行效果

```bash
# 查询多只股票
stock_cli sz000009 sz002332 sh600519

# JSON 输出
stock_cli sz000009 --format json

# 实时推送模式（每 5 秒刷新）
stock_cli sz000009 sz002332 --push 5

# 同步遗留模式
stock_cli sz000009 --sync-legacy
```

## 5. Tokio 运行时关键点

1. **`#[tokio::main]` 宏**：展开为一个 `Runtime::new()` + `block_on`
2. **tokio::spawn**：创建一个新的异步任务，返回 JoinHandle
3. **await 点**：每次 await 都可能让出线程，等待事件驱动重新唤醒
4. **协作式调度**：task 只有 await 时才让出，没有抢占式
5. **单线程 vs 多线程**：默认 `#[tokio::main]` 是多线程 runtime (work-stealing)

# Rust #10：异步编程 — Future、Tokio、async-std

> 2026-05-17
> 前置知识：Rust #6 并发（线程基础）、#4 Trait 与泛型

## 引言

### 为什么需要异步？

**线程的局限**：
- 每个线程有独立栈（~2MB on Windows），10k 线程 = 20GB
- 线程切换有内核态开销
- 阻塞 I/O 时线程被挂起

**异步 = 用户态协作式调度**：
- 单线程可以处理数万个并发连接
- 无上下文切换（100% 用户态）
- 没有阻塞，只有 `await`

```rust
// 同步：每个连接一个线程
fn handle_client(stream: TcpStream) {
    let mut buf = vec![0; 1024];
    stream.read(&mut buf);  // 线程阻塞在这里
    stream.write(&response);
}

// 异步：单线程处理所有连接
async fn handle_client(stream: TcpStream) {
    let mut buf = vec![0; 1024];
    stream.read(&mut buf).await;  // 挂起，让出线程
    stream.write(&response).await;
}
```

## 1. Future 核心

### 🚨 极度重要：在 Rust 中，async 块/函数**什么也不做**，直到被轮询（poll）

这是 Rust 异步与其他语言最大的区别——**惰性执行**。

```rust
// 下面这行：不执行任何实际工作
let fut = async { fetch_data().await };

// 必须 .await 或在运行时上 spawn 才会执行
fut.await;  // 现在才开始
```

Future trait 的定义：

```rust
trait Future {
    type Output;
    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output>;
}

enum Poll<T> {
    Ready(T),   // 完成
    Pending,    // 还没好，稍后再来
}
```

### 状态机

Rust 的 async 块会在编译期被转换为状态机：

```rust
async fn example() -> i32 {
    let a = step1().await;   // 状态 0
    let b = step2(a).await;  // 状态 1
    b + 1                    // 状态 2（完成）
}

// 编译后大致等价于：
enum ExampleFuture {
    State0 { /* 还没开始 */ },
    State1 { a: i32, fut1: Step1Future },
    State2 { a: i32, b: i32, fut2: Step2Future },
    Done,
}
impl Future for ExampleFuture {
    type Output = i32;
    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<i32> {
        loop {
            match self {
                ExampleFuture::State0 => {
                    *self = ExampleFuture::State1 { a, fut1: step1() };
                }
                ExampleFuture::State1 { a, fut1 } => {
                    match fut1.poll(cx) {
                        Poll::Ready(v) => {
                            *self = ExampleFuture::State2 { a, b: v, fut2: step2(*a) };
                        }
                        Poll::Pending => return Poll::Pending,
                    }
                }
                // ...
            }
        }
    }
}
```

**重点**：async 函数不分配堆内存——状态机完全在栈上（除非被 Box::pin）。

## 2. Pin 与 Unpin

### 为什么需要 Pin？

`Future` 包含自引用结构（状态机中不同状态可能引用自身其他字段）。结构体在内存中被移动后，自引用指针会成为悬垂指针。

```rust
struct SelfReferential {
    data: String,
    ptr: *const String,  // 指向 self.data
}

fn problem() {
    let s = SelfReferential {
        data: String::from("hello"),
        ptr: std::ptr::null(),
    };
    // 假设 s.ptr = &s.data

    let s2 = s;  // 移动！s.ptr 仍然指向旧地址！
    // 悬垂指针！
}
```

**Pin 的保证**：`Pin<P>` 确保 `P` 指向的值**不会被移动**。

```rust
// 栈上固定
let mut fut = async { ... };
pin_mut!(fut);  // 等效于 let mut fut = Pin::new(&mut fut);
fut.await;

// 堆上固定（最常见）
let fut = Box::pin(async { ... });
fut.await;
```

### Unpin 和 !Unpin

```rust
// 大多数类型是 Unpin — 可以随意移动
// Pin<&mut T> = &mut T 对 Unpin 类型

// Future 可能是 !Unpin（如果有 self 引用）
// 需要 Pin<&mut Self> 才能 poll

// 手动实现 !Unpin
struct Unmovable {
    data: String,
    _marker: PhantomPinned,  // 使类型变成 !Unpin
}
```

## 3. async/await 语法

```rust
// async fn — 返回 impl Future
async fn fetch_url(url: &str) -> Result<String, reqwest::Error> {
    let resp = reqwest::get(url).await?;
    let body = resp.text().await?;
    Ok(body)
}

// async 块
let fut = async {
    let data = fetch_data().await;
    process(data)
};

// async 闭包（nightly）
let fut = async || {
    fetch_data().await
};
```

### .await 的工作原理

```rust
// .await 会：
// 1. poll 这个 Future
// 2. 如果 Ready → 提取 Output
// 3. 如果 Pending → 挂起当前 async 函数，返回到 Future 的调度器

// 类比：JavaScript 的 await，Python 的 await
// 区别：Rust 的 await 是惰性的——不 await 就不执行
// JavaScript/Python 的 await 创建时就执行
```

## 4. Tokio 运行时

### 为什么需要运行时？

Rust 的 `Future` 只是 trait。**谁去 poll 它？** 这就是运行时的作用。

```rust
// 没有运行时的 async 代码无法执行
async fn foo() {
    println!("hello");
}

// foo().await ← 必须要在运行时里才能 .await
```

### Tokio 的核心组件

```rust
use tokio;

// #[tokio::main] — 宏，展开后创建 Runtime 并运行 main
#[tokio::main]
async fn main() {
    println!("Hello from Tokio");
}

// 展开后：
fn main() {
    let rt = tokio::runtime::Runtime::new().unwrap();
    rt.block_on(async {
        println!("Hello from Tokio");
    });
}
```

### 调度策略

Tokio 使用**工作窃取多线程调度器**：

```
线程池（默认 = CPU 核数）
├── 每个线程一个本地任务队列
├── 空闲线程从其他线程偷任务
└── I/O 事件驱动 epoll/iocp/kqueue

多线程运行时：
├── tokio::runtime::Runtime::new()
├── 用于 CPU 密集 + I/O 混合
└── 默认创建

单线程运行时：
├── tokio::runtime::Runtime::new_current_thread()
├── 用于纯 I/O 或嵌入式
└── 更轻量，无线程同步开销
```

### 关键注解

```rust
// 多线程运行时（默认）
#[tokio::main]
async fn main() {}

// 单线程
#[tokio::main(flavor = "current_thread")]
async fn main() {}

// 自定义线程数
#[tokio::main(worker_threads = 4)]
async fn main() {}

// 自定义栈大小
#[tokio::main(flavor = "current_thread", max_stack_size = 2 * 1024 * 1024)]
async fn main() {}
```

## 5. 核心异步原语

### task — 轻量级线程

```rust
// tokio::spawn — 生成异步任务
// 类似 std::thread::spawn，但不用线程
#[tokio::main]
async fn main() {
    let handle = tokio::spawn(async {
        "return value".to_string()
    });

    // JoinHandle — 等待任务完成
    let result = handle.await.unwrap();
    println!("{result}");

    // 批量 spawn
    let mut handles = vec![];
    for i in 0..10 {
        handles.push(tokio::spawn(async move {
            process(i).await
        }));
    }
    for h in handles {
        h.await.unwrap();
    }
}
```

### 异步 I/O

```rust
use tokio::net::TcpListener;
use tokio::io::{AsyncReadExt, AsyncWriteExt};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let listener = TcpListener::bind("127.0.0.1:8080").await?;

    loop {
        let (mut socket, addr) = listener.accept().await?;
        println!("新连接: {addr}");

        tokio::spawn(async move {
            let mut buf = [0; 1024];
            loop {
                let n = socket.read(&mut buf).await.unwrap();
                if n == 0 { break; }  // EOF
                socket.write_all(&buf[..n]).await.unwrap();
            }
        });
    }
}
```

**与标准库的对比**：

```rust
// 标准库
fn handle(std_stream: TcpStream) {
    std_stream.set_read_timeout(Some(Duration::from_secs(5)));
    let mut buf = [0; 1024];
    let n = std_stream.read(&mut buf)?;  // 线程阻塞
}

// Tokio
async fn handle(tokio_stream: TcpStream) {
    let mut buf = [0; 1024];
    let n = tokio_stream.read(&mut buf).await;  // 挂起，不阻塞线程
}
```

### 同步原语

```rust
use std::sync::Arc;
use tokio::sync::{Mutex, RwLock, Semaphore, mpsc, oneshot, watch, Barrier};

// 🔴 Tokio 的 Mutex vs 标准库 Mutex
// 标准库 Mutex：.lock() 阻塞线程
// Tokio Mutex：.lock().await 挂起任务
// 经验：I/O 操作用 Tokio Mutex，短 CPU 操作用 std::Mutex

#[tokio::main]
async fn main() {
    // mpsc: 多生产者单消费者
    let (tx, mut rx) = mpsc::channel::<i32>(100);
    tokio::spawn(async move {
        for i in 0..10 {
            tx.send(i).await.unwrap();
        }
    });
    while let Some(v) = rx.recv().await {
        println!("收到: {v}");
    }

    // oneshot: 一次性的
    let (tx, rx) = oneshot::channel::<String>();
    tokio::spawn(async move {
        tx.send("结果".to_string()).unwrap();
    });
    let result = rx.await.unwrap();
}
```

## 6. 错误处理

```rust
// 在 async 代码中传播错误
async fn fetch_and_process(url: &str) -> Result<String, Box<dyn std::error::Error>> {
    let resp = reqwest::get(url).await?;
    Ok(resp.text().await?)
}

// ? 在 async 中的行为：
// 如果 Err → 返回 Poll::Ready(Err)，并且函数被挂起
// 注意：? 只能用在返回 Result 的 async fn 中

// 在 task 中处理错误
let handle = tokio::spawn(async {
    // spawn 内部发生 panic → JoinHandle::await 返回 Err
    panic!("任务崩溃");
});
let result = handle.await;
match result {
    Ok(v) => println!("结果: {v}"),
    Err(e) => eprintln!("任务崩溃: {e}"),  // JoinError
}
```

## 7. 实战：异步股票行情查询

```rust
// 对比我们之前的 stock_cli（同步方案）
// 异步版本可以用 Tokio 同时查多只股票

use std::error::Error;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::TcpStream;
use std::collections::HashMap;

async fn fetch_quote(code: &str) -> Result<String, Box<dyn Error>> {
    let request = format!(
        "GET /q=s_{code} HTTP/1.1\r\nHost: qt.gtimg.cn\r\nConnection: close\r\n\r\n"
    );

    let mut stream = TcpStream::connect("qt.gtimg.cn:80").await?;
    stream.write_all(request.as_bytes()).await?;

    let mut reader = BufReader::new(&mut stream);
    let mut body = String::new();

    loop {
        let mut line = String::new();
        let n = reader.read_line(&mut line).await?;
        if n == 0 { break; }
        // 跳过 headers，只收集 body
        if !line.contains(':') && body.is_empty() {
            continue;
        }
        if body.is_empty() && line == "\r\n" {
            continue;  // header 结束
        }
        if !body.is_empty() || line.contains('~') {
            body.push_str(&line);
        }
    }

    Ok(body.trim().to_string())
}

// 异步批量查询
async fn batch_fetch(codes: &[&str]) -> HashMap<String, String> {
    let mut handles = vec![];

    for code in codes {
        let code = code.to_string();
        handles.push(tokio::spawn(async move {
            let result = fetch_quote(&code).await;
            (code, result)
        }));
    }

    let mut results = HashMap::new();
    for h in handles {
        if let Ok((code, Ok(data))) = h.await {
            results.insert(code, data);
        }
    }
    results
}
```

## 8. 性能考量

### 同步 vs 异步

| 场景 | 同步（线程） | 异步（Tokio） |
|:----|:----------|:----------|
| 1 个连接 | 1 线程 ~2MB | 1 任务 ~几 KB |
| 1 万个并发连接 | 不可能（20GB 内存） | 可能（~几十 MB） |
| CPU 密集计算 | 优劣等价 | 等价 |
| 每秒文件读取 | 劣（线程切换） | 优 |
| 代码复杂度 | 简单 | 略复杂 |

### 什么时候用异步

```rust
// ✅ 应该用异步
// - Web 服务器（每秒上万请求）
// - 数据库连接池
// - API 网关 / 代理
// - 聊天服务器（大量长连接）
// - 文件 I/O 密集型任务

// ❌ 不应该用异步
// - 纯 CPU 计算（机器学习训练）
// - 简单的命令行工具（stock_cli 这类）
// - 嵌入式系统（无运行时）
```

### 异步陷阱

```rust
// 陷阱 1：async 块中的阻塞操作
async fn bad() {
    std::thread::sleep(Duration::from_secs(1));  // 🔴 阻塞了运行时线程！
    // 应该用 tokio::time::sleep(Duration::from_secs(1)).await
}

// 陷阱 2：Mutex 持有跨越 .await
async fn bad_mutex(shared: Arc<tokio::sync::Mutex<i32>>) {
    let mut guard = shared.lock().await;
    *guard += 1;
    some_io().await;  // 🔴 持锁 await！其他任务被阻塞
    // 应该：在 await 前释放锁
    *guard += 1;
    drop(guard);  // 提前释放
    some_io().await;
}

// 陷阱 3：递归 async
// ❌ 编译错误 — 无法确定 Future 大小
async fn recurse(n: u32) {
    recurse(n - 1).await;
}
// ✅ 用 Box::pin
fn recurse_boxed(n: u32) -> Pin<Box<dyn Future<Output = ()>>> {
    Box::pin(async move {
        recurse_boxed(n - 1).await;
    })
}

// 陷阱 4：Select 中丢失数据
async fn select_bad() {
    let mut data = vec![1, 2, 3];
    tokio::select! {
        _ = process(&data) => {
            data.push(4);  // 🔴 部分借用的冲突
        }
    }
}
```

## 9. async-std 生态（替代 Tokio）

```rust
// async-std 的设计哲学："版本对齐"
// 标准库有 std::fs → async_std::fs
// 标准库有 std::net → async_std::net

use async_std::task;
use async_std::prelude::*;

fn main() {
    task::block_on(async {
        println!("Hello from async-std");
    });
}

// Tokio vs async-std 比较
// Tokio：    生态更成熟，文档更好，性能稍优
// async-std：API 更直观，与标准库对齐
// 共同点：   都基于 Futures，可以互操作
```

## 10. 总结

```
Rust 异步编程全景
├── 核心概念
│   ├── Future trait    — 惰性执行，需要 poll
│   ├── async/await     — 语法糖，生成状态机
│   ├── Pin             — 防止自引用类型被移动
│   └── Waker           — 通知运行时"我好了"
│
├── 运行时（必须）
│   ├── Tokio           — 主流选择，生产级
│   ├── async-std       — 标准库对齐
│   └── smol            — 极简运行时
│
├── 常用组件
│   ├── tokio::spawn    — 轻量级任务
│   ├── tokio::net      — 异步网络 I/O
│   ├── tokio::fs       — 异步文件 I/O
│   ├── tokio::sync     — 异步同步原语
│   └── tokio_select!   — 多 Future 竞争
│
└── 与同步的主要区别
    ├── 所有 I/O 加 .await
    ├── 不阻塞线程，只挂起任务
    ├── 不要持有锁跨越 await
    └── 用 tokio::time::sleep 代替 thread::sleep
```

## 参考

- Tokio 官方教程: https://tokio.rs/tokio/tutorial
- The Book Ch.16: Async/Await
- "Async in Rust" (without_boats 博客)
- Rust Async Book: https://rust-lang.github.io/async-book/
- smol: https://github.com/smol-rs/smol

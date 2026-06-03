# Rust 异步底层原理

> Future trait / Pin / Waker / Executor — 拆解async运行时

## 1. Future trait 核心

```rust
pub trait Future {
    type Output;
    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output>;
}
```

- `poll` 是**同步调用** — 调用时如果数据就绪立即返回 `Ready(val)`，否则 `Pending`
- `Context` 包含 `Waker` — 告诉执行器"我准备好了"
- 每次 `poll` 必须在**同一个线程**调用（Pin保证）

### async fn → Generator 展开

```rust
async fn foo() -> i32 {
    let x = bar().await;  // 1: 挂起点
    x + 42
}
```

编译器展开为 Generator（状态机）：

```rust
// 近似编译结果
enum FooFuture {
    Start,                              // 初始
    AwaitingBar { fut: BarFuture },     // 在 .await 处挂起
    Done,
}

impl Future for FooFuture {
    type Output = i32;
    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<i32> {
        loop {
            match *self {
                FooFuture::Start => { /* 初始化，进入AwaitingBar */ }
                FooFuture::AwaitingBar { ref mut fut } => {
                    match fut.poll(cx) {
                        Poll::Ready(val) => { /* x=val, 进入Done, 返回Ready(x+42) */ }
                        Poll::Pending => return Poll::Pending,
                    }
                }
                FooFuture::Done => panic!("poll after ready"),
            }
        }
    }
}
```

关键：每个 `.await` 是一个**状态转换点**，整个 `async fn` 是一个状态机。

## 2. Pin 为什么存在

问题：Future 可能在状态中包含**自引用**（比如指向自身字段的指针）。

```rust
struct MyFuture {
    buf: [u8; 1024],
    ptr: *const u8,  // 指向 self.buf
}
// 如果这个结构体被移动了，ptr 就成了悬空指针！
```

解决方案：
- `Pin<P>` 保证内部值不会被移动
- `Pin::new(&mut val)` 只是运行时检查
- **对已经 Pin 的值，不能再拿 &mut**（除非 unsafe）
- 大多数 async 用户不需要直接碰 Pin — 编译器自动处理

### !Unpin 标记

```rust
// 默认所有类型都 Unpin
// 自引用 Future 实现 !Unpin
struct MyFuture { /* 自引用字段 */ }
impl !Unpin for MyFuture {}  // 编译器自动为async block生成

// Pin<Box<T>> vs Pin<&mut T>
//    Box: 堆分配，移动Box不会移动内部值 — 安全
//    &mut: 不分配堆，但必须确保值本身不被移动
```

## 3. Waker 机制

```rust
let waker = cx.waker().clone();  // 克隆Waker
waker.wake();                     // 通知执行器重新poll
```

Waker 内部:

```
Waker {
    data: RawWaker,     // 实际数据指针
    vtable: &WakerVTable, // 虚函数表
}

WakerVTable {
    clone:  fn(*const ()) -> RawWaker,
    wake:   fn(*const ()),     // 消费自身唤醒
    wake_by_ref: fn(&*const ()), // 不消费唤醒
    drop:   fn(*const ()),
}
```

关键: waker.wake() 不是立即 poll — 它告诉执行器"这个 future 有进展了"。

## 4. 最小 Executor (~100行思路)

```rust
struct MiniExecutor {
    tasks: VecDeque<Pin<Box<dyn Future<Output = ()>>>>,
}

impl MiniExecutor {
    fn run(&mut self) {
        while let Some(mut task) = self.tasks.pop_front() {
            let waker = noop_waker();     // 简化：空Waker
            let mut cx = Context::from_waker(&waker);
            match task.as_mut().poll(&mut cx) {
                Poll::Pending => self.tasks.push_back(task),  // 排到队尾
                Poll::Ready(_) => {}  // 完成
            }
        }
    }
}
```

真实 Executor (tokio/smol) 更复杂：
- 多个工作线程（work-stealing）
- I/O 事件驱动（epoll/kqueue/IOCP）
- 定时器堆
- 阻塞检测

## 5. async 生态

| 运行时 | 特点 | 适用场景 |
|--------|------|---------|
| tokio | 最流行，功能全 | Web服务器、微服务、数据库 |
| async-std | std API 兼容 | 追求 API 一致性 |
| smol | 轻量，零依赖 | 嵌入式、CLI工具 |
| embassy | 嵌入式专用 | 无OS环境，Cortex-M |

---

**总结**: Rust async = 编译器生成状态机 + Pin保安全 + Waker驱动轮询 + Executor调度

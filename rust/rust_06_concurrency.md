# Rust #6：并发编程

> 2026-05-17
> 前置知识：智能指针（#5）、系统编程基础

## Rust 并发哲学

Rust 承诺：**如果没有使用 `unsafe`，就绝对没有数据竞争。**

这是通过所有权系统的"自然延伸"实现的：
- `Send` trait：类型可以安全地在线程间传递所有权
- `Sync` trait：类型可以安全地在线程间共享引用（`&T`）

## 基本线程

```rust
use std::thread;
use std::time::Duration;

fn main() {
    let handle = thread::spawn(|| {
        for i in 1..10 {
            println!("子线程: {i}");
            thread::sleep(Duration::from_millis(1));
        }
    });

    for i in 1..5 {
        println!("主线程: {i}");
        thread::sleep(Duration::from_millis(1));
    }

    handle.join().unwrap();  // 等待子线程
}
```

### move 闭包

```rust
let v = vec![1, 2, 3];

let handle = thread::spawn(move || {
    // move 关键字把 v 的所有权移入闭包
    println!("这里是 {v:?}");
});

// drop(v);  // ❌ v 已被 move
handle.join().unwrap();
```

## 消息传递（Channel）

Rust 的 channel 是 **多生产者，单消费者**（mpsc）：

```rust
use std::sync::mpsc;
use std::thread;

fn main() {
    let (tx, rx) = mpsc::channel();

    thread::spawn(move || {
        let val = String::from("hi");
        tx.send(val).unwrap();
        // println!("{val}");  // ❌ val 已被 move 到接收方
    });

    let received = rx.recv().unwrap();
    println!("收到: {received}");
}
```

### 多生产者

```rust
let (tx, rx) = mpsc::channel();

let tx1 = tx.clone();
thread::spawn(move || {
    tx1.send("来自线程1").unwrap();
});

let tx2 = tx.clone();
thread::spawn(move || {
    tx2.send("来自线程2").unwrap();
});

// 主线程可以同时消费来自两个线程的消息
for received in rx {
    println!("收到: {received}");
}
```

## 共享状态（Mutex + Arc）

```
C++: std::shared_ptr<std::mutex> global_data;
Rust: Arc<Mutex<T>> shared_data;
```

```rust
use std::sync::{Arc, Mutex};
use std::thread;

fn main() {
    let counter = Arc::new(Mutex::new(0));
    let mut handles = vec![];

    for _ in 0..10 {
        let counter = Arc::clone(&counter);
        let handle = thread::spawn(move || {
            let mut num = counter.lock().unwrap();
            *num += 1;
        });
        handles.push(handle);
    }

    for handle in handles {
        handle.join().unwrap();
    }

    println!("结果: {}", *counter.lock().unwrap()); // 10
}
```

**关键**：
- `Arc` = 原子引用计数（线程安全版 `Rc`）
- `Mutex` = 运行时锁
- `lock()` 返回 `MutexGuard<'_>` — 离开作用域自动解锁
- 死锁：如果同一个线程对同一个 Mutex 锁两次 → panic（与 C++ 的死锁不同）

## Send 和 Sync Trait

这两个 trait 是 Rust 并发安全的基础，大多数类型**自动实现**：

```rust
// Send: 所有权可以跨线程转移
// 大多数类型都是 Send，除了 Rc<T>（非原子引用计数）
fn is_send<T: Send>() {}
is_send::<i32>();     // ✅
// is_send::<Rc<i32>>(); // ❌

// Sync: 引用可以跨线程共享
// T: Sync ≡ &T: Send
fn is_sync<T: Sync>() {}
is_sync::<i32>();        // ✅
is_sync::<Mutex<i32>>(); // ✅
// is_sync::<RefCell<i32>>(); // ❌
```

**手动实现** `Send` / `Sync` 需要 `unsafe` ——几乎不需要。

## 并发设计模式对比

| 模式 | Rust 实现 | 类似 C++ | 适用场景 |
|:----|:---------|:--------|:--------|
| 消息传递 | `mpsc::channel` | `std::queue` + condition_variable | 生产者-消费者 |
| 共享状态 | `Arc<Mutex<T>>` | `shared_ptr<mutex>` | 复杂数据共享 |
| 读写锁 | `RwLock<T>` | `std::shared_mutex` | 读多写少 |
| 原子操作 | `AtomicBool / AtomicI32` | `std::atomic` | 计数器、标志位 |
| 屏障 | `Barrier` | `std::barrier` | 等待所有线程就绪 |
| 条件变量 | `Condvar` | `std::condition_variable` | 复杂同步 |
| Once | `OnceLock` / `OnceCell` | `std::once` | 惰性初始化 |

## 一个完整的例子

```rust
use std::sync::{Arc, Mutex, mpsc};
use std::thread;

// 工作线程池（简化版）
fn main() {
    let data = Arc::new(Mutex::new(vec![1, 2, 3, 4, 5]));
    let (tx, rx) = mpsc::channel();

    // 3 个工作线程并行处理数据
    for id in 0..3 {
        let data = Arc::clone(&data);
        let tx = tx.clone();

        thread::spawn(move || {
            let mut vec = data.lock().unwrap();
            if let Some(val) = vec.pop() {
                let result = val * 2;
                tx.send(format!("线程{id}: {val}×2={result}")).unwrap();
            }
        });
    }

    // 主线程收集结果
    for _ in 0..3 {
        println!("{}", rx.recv().unwrap());
    }
}
```

## Rust vs C++ 并发关键区别

```
C++ 的线程安全：全靠程序员自己保证，编译器不检查
Rust 的线程安全：借用检查器在编译期保证，不信任程序员
```

**具体对比**：
1. C++ 可以 `static int x; thread1: x++ thread2: cout << x` — 数据竞争，不确定行为
2. Rust 不能 `&x` 和 `&mut x` 跨线程同时存在 — 编译期阻止
3. C++ `std::shared_ptr` 引用计数是原子的，但不保护指向的对象
4. Rust `Arc<T>` 提供线程安全引用计数，`Arc<Mutex<T>>` 保护数据

## 参考

- The Book, Chapter 16: Fearless Concurrency
- "Rust Atomics and Locks" (Mara Bos)
- std::sync 文档

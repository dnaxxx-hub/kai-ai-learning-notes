# Rust #5：智能指针与内存管理

> 2026-05-17
> 前置知识：所有权（#2）、Trait（#4）

## 智能指针家族

| 类型 | 功能 | 类似 C++ |
|:----|:----|:--------|
| `Box<T>` | 堆分配 | `std::make_unique<T>` |
| `Rc<T>` | 引用计数（单线程） | `std::shared_ptr<T>`（线程安全版） |
| `Arc<T>` | 原子引用计数（多线程） | `std::shared_ptr<T>` |
| `Cell<T>` | 内部可变性（Copy 类型） | — |
| `RefCell<T>` | 内部可变性（运行时借用检查） | — |
| `Mutex<T>` | 互斥内部可变性（多线程） | `std::mutex` |
| `Ref<T> / RefMut<T>` | RefCell 的借用守卫 | — |

## Box — 最简智能指针

```rust
// 栈上存一个 i32
let x = 5;

// 堆上存一个 i32
let y = Box::new(5);

println!("x = {}, y = {}", x, *y);  // 自动解引用
```

**主要用途**：
1. **递归类型**（无法在编译期确定大小）
2. **Trait 对象**（运行时多态）
3. **大对象移动**（避免栈拷贝）

### 递归类型示例

```rust
// ❌ 编译错误：递归类型未确定大小
enum List {
    Cons(i32, List),
    Nil,
}

// ✅ 用 Box 包装，递归类型大小固定（指针）
enum List {
    Cons(i32, Box<List>),
    Nil,
}
```

## Rc — 引用计数

```rust
use std::rc::Rc;

let a = Rc::new(String::from("hello"));
let b = Rc::clone(&a);  // 增加引用计数，不是深拷贝
let c = Rc::clone(&a);

println!("引用计数: {}", Rc::strong_count(&a)); // 3
```

**限制**：只用于单线程。多线程用 `Arc`。

## 内部可变性模式

Rust 默认：要么 `&T`（不可变），要么 `&mut T`（唯一可变）。

但有时候我们需要"外观不可变，内部可变"——比如缓存、引用计数。

### RefCell

```rust
use std::cell::RefCell;

let data = RefCell::new(42);

// 不可变借用（运行期检查）
let r1 = data.borrow();
println!("{}", r1);  // 42

// 可变借用（运行期检查）
let mut r2 = data.borrow_mut();
*r2 += 1;

println!("{}", data.borrow());  // 43
```

**RefCell 的借用规则**：和普通引用一样——同一时间要么多个不可变借用，要么一个可变借用——但**在运行时检查**而不是编译时。违反规则会 panic。

### Rc + RefCell 结合

```rust
use std::rc::Rc;
use std::cell::RefCell;

let value = Rc::new(RefCell::new(42));

let a = Rc::clone(&value);
let b = Rc::clone(&value);

*b.borrow_mut() += 10;

println!("{:?}", value);  // RefCell { value: 52 }
```

这实现了"多个所有者 + 可变数据"——类似 C++ 的 shared_ptr，但在 Rust 中需要显式组合 Rc 和 RefCell。

### Arc + Mutex（多线程版）

```rust
use std::sync::{Arc, Mutex};
use std::thread;

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

println!("结果: {}", *counter.lock().unwrap());  // 10
```

## 内存布局

```rust
// Rust 的内存布局与 C 对齐
use std::mem;

// 基本类型
println!("{}", mem::size_of::<i32>());     // 4
println!("{}", mem::size_of::<f64>());     // 8
println!("{}", mem::size_of::<bool>());    // 1
println!("{}", mem::size_of::<char>());    // 4

// 引用/指针（64位平台）
println!("{}", mem::size_of::<&i32>());    // 8
println!("{}", mem::size_of::<Box<i32>>()); // 8

// String
println!("{}", mem::size_of::<String>());  // 24 (ptr+len+cap)

// Vec
println!("{}", mem::size_of::<Vec<i32>>()); // 24 (ptr+len+cap)
```

**优化建议**：
- `enum` 大小 = max(所有变体) + 1 字节鉴别器（可能更多对齐）
- `struct` 重排可以更紧凑（类似 C 的 `__attribute__((packed))`）
- Rust 编译器默认不会重排字段（与 C 相同）

## 与 C++ 的对比

```rust
// Rust
Box::new(42)           // unique_ptr(42)
Rc::new(42)            // shared_ptr(42) — 单线程
Arc::new(Mutex::new(x)) // shared_ptr<mutex> — 多线程
RefCell::new(x)        // 无直接对应（编译期借用检查变运行时）
```

**关键区别**：
- C++ 的 `shared_ptr` 默认线程安全（原子引用计数），Rust 的 `Rc` 不是
- Rust 没有 `weak_ptr` 原生类型？有 `Weak<T>`
- C++ 的 `unique_ptr` 和 Rust 的 `Box` 语义几乎一致（所有权唯一）

## 参考

- The Book, Chapter 15: Smart Pointers
- "Rustonomicon"（unsafe Rust 深入）
- std::rc / std::cell / std::sync 文档

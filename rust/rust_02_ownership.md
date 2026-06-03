# Rust #2：所有权与借用

> 2026-05-17
> 前置知识：Rust 基础（#1）、C/C++ 内存管理

## 所有权三条规则

Rust 的杀手特性。规则只有三条：

1. **每个值在 Rust 中都有一个所有者**
2. **同一时间只能有一个所有者**
3. **当所有者离开作用域，值被释放**

> 对比 C++：unique_ptr 也符合这三条规则，但 Rust 默认所有变量都是 unique_ptr。

## 作用域与移动

```rust
{                           // s 尚未声明
    let s = String::from("hello");
    // 可以使用 s
}                           // 作用域结束 → s 自动释放
                            // 类似 C++ RAII
```

### Move 语义

```rust
let s1 = String::from("hello");
let s2 = s1;           // ❌ s1 被移动到 s2
                       // println!("{s1}");  ← 编译错误！
```

**内存模型**：
```
s1 (栈)                        堆
[ptr, len, capacity] ──────── [h][e][l][l][o]
   ↓ 移动后 s1 被标记为无效
s2 (栈)
[ptr, len, capacity] ──────── [h][e][l][l][o]
```

为什么不是深拷贝？——String 的堆数据很大，拷贝代价高。Rust **默认移动（move）**，不是浅拷贝也不是深拷贝。

### Clone（显式深拷贝）

```rust
let s1 = String::from("hello");
let s2 = s1.clone();   // ✅ 显式克隆
println!("{s1} {s2}"); // 两个都有效
```

### Copy 类型（栈上数据）

```rust
// 整数、浮点、布尔、char — 实现了 Copy trait
let x = 5;
let y = x;             // ✅ Copy，不是 Move
println!("{x} {y}");   // 两个都有效
```

**判断规则**：实现了 `Drop` trait 的类型不能实现 `Copy`。堆分配的类型（String、Vec）= Drop → Move。栈上类型（整数、浮点数） = Copy。

## 借用（引用）

不转移所有权，只借来用一下：

```rust
fn calculate_length(s: &String) -> usize {  // & 表示借用
    s.len()
}  // s 离开作用域，但不释放——它不是所有者

let s1 = String::from("hello");
let len = calculate_length(&s1);  // 传引用
println!("{s1} 的长度是 {len}");   // ✅ s1 还在
```

### 可变引用

```rust
fn modify(s: &mut String) {
    s.push_str(", world");
}

let mut s1 = String::from("hello");
modify(&mut s1);
println!("{s1}");  // "hello, world"
```

### 引用规则（编译期数据竞争检测）

1. **同一时间只能有一个可变引用**，或者**多个不可变引用**
2. 引用必须始终有效（不会出现悬垂引用）

```rust
let mut s = String::from("hello");

let r1 = &s;      // ✅ 多个不可变引用 OK
let r2 = &s;      // ✅
// let r3 = &mut s; // ❌ 已有不可变引用时，不能有可变引用
println!("{r1} {r2}");

let r3 = &mut s;  // ✅ r1, r2 已不再使用
```

**这个规则在编译期防止了**：
- 数据竞争（data race）
- 迭代器失效（类似 C++ vector 扩容后迭代器失效）
- 悬挂指针

## 生命周期

生命周期是 Rust 最让新人头疼的部分，但核心概念很简单：**引用必须比其指向的数据活得更久**。

```rust
// 以下代码不肯编译：
fn dangline() -> &String {  // ❌ 返回悬垂引用
    let s = String::from("hello");
    &s
}  // s 在这里释放，但返回的引用指向已释放的内存

// ✅ 正确做法：返回 String 本身（所有权转移）
fn no_dangline() -> String {
    let s = String::from("hello");
    s
}
```

### 生命周期标注

```rust
// 这个函数接受两个 &str，返回其中一个
// 问题是：返回的引用应该跟哪个参数一样长？
fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() > y.len() { x } else { y }
}
```

`'a` 的意思是：x 和 y 都至少活得跟 `'a` 一样长，返回值也活得跟 `'a` 一样长。**编译器**用这个标注来检查引用的有效性。

### 生命周期省略规则

```rust
// 大多数时候不需要写生命周期标注，编译器能推断：
fn first_word(s: &str) -> &str {  // 编译器自动加 '_
    ...
}
fn get(&self, key: &str) -> Option<&V> {  // 返回值 &V 和 self 同周期
    ...
}
```

**经验法则**：
- 只有一个输入引用 → 输出引用和它同周期
- 方法是 `&self` → 输出引用和 self 同周期
- 多个输入引用 → 需要标注

## 与 C/C++ 对比

| 场景 | C++ | Rust |
|:----|:---|:----|
| 传递大型对象 | const T& / T&& | &T（不可变借用） |
| 修改对象 | T& | &mut T（可变借用） |
| 转移所有权 | std::move | 默认就是 move |
| 深拷贝 | 拷贝构造函数 | .clone() |
| 引用计数 | shared_ptr | Rc\<T\> |
| 悬垂引用 | 运行期崩溃 | 编译期拒绝 |
| 迭代器失效 | 运行期 | 编译期（借用检查） |

## 总结

所有权系统是 Rust 最独特的设计。理解它需要转变思维：
- C：**手动管理** — malloc/free，全部你负责
- C++：**半自动管理** — RAII + 智能指针，但容易出错
- Rust：**编译期保证** — 规则在编译时检查，运行期零开销

三维对照：
```
C:  我管理内存，编译器相信我
C++: RAII 管一些，但我能 override
Rust: 编译器管，我只设计逻辑
```

## 参考

- The Book, Chapter 4: "Understanding Ownership"
- [Rust 生命周期可视化工具](https://rust-book.cs.brown.edu/)（推荐）

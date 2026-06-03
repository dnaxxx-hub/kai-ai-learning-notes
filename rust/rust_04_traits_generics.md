# Rust #4：Trait 与泛型

> 2026-05-17
> 前置知识：结构体与枚举（#3）

## 泛型

消除代码重复，类似 C++ 的模板，但编译期更安全。

```rust
// 泛型函数：找出最大的元素
fn largest<T: PartialOrd>(list: &[T]) -> &T {
    let mut largest = &list[0];
    for item in list {
        if item > largest {
            largest = item;
        }
    }
    largest
}

fn main() {
    let numbers = vec![34, 50, 25, 100, 65];
    println!("最大数: {}", largest(&numbers));

    let chars = vec!['y', 'm', 'a', 'q'];
    println!("最大字符: {}", largest(&chars));
}
```

**与 C++ 模板的对比**：
```rust
// Rust — 必须在函数签名中声明泛型约束
fn foo<T: Display + Clone>(x: T) { ... }

// C++ — 模板按需展开，不用提前声明约束
template<typename T>
void foo(T x) { ... }
// 但用了 T::display() 才报错
```

Rust 的方式好在哪里？——**错误信息在调用前就能给出**，而不是在模板实例化时炸开。

## Trait（特征）

Trait 类似 C++ 的纯虚接口类 / 概念（concepts）。

```rust
pub trait Summary {
    fn summarize(&self) -> String;  // 方法签名
}
```

### 为类型实现 Trait

```rust
pub struct NewsArticle {
    pub headline: String,
    pub location: String,
    pub author: String,
    pub content: String,
}

impl Summary for NewsArticle {
    fn summarize(&self) -> String {
        format!("{}, by {} ({})", self.headline, self.author, self.location)
    }
}

pub struct Tweet {
    pub username: String,
    pub content: String,
    pub reply: bool,
    pub retweet: bool,
}

impl Summary for Tweet {
    fn summarize(&self) -> String {
        format!("{}: {}", self.username, self.content)
    }
}
```

### 默认实现

```rust
pub trait Summary {
    fn summarize(&self) -> String {
        String::from("(阅读更多...)")
    }
}
```

### Trait Bound

```rust
// 方式1：泛型约束
fn notify<T: Summary>(item: &T) {
    println!("热点新闻！{}", item.summarize());
}

// 方式2：impl Trait 语法（简化写法）
fn notify(item: &impl Summary) {
    println!("热点新闻！{}", item.summarize());
}

// 多个 Trait Bound
fn notify(item: &(impl Summary + Display)) { ... }
fn notify<T: Summary + Display>(item: &T) { ... }

// where 子句（太多 Bound 时）
fn some_function<T, U>(t: &T, u: &U) -> i32
where
    T: Display + Clone,
    U: Clone + Debug,
{ ... }
```

### 返回 impl Trait

```rust
fn returns_summarizable() -> impl Summary {
    Tweet {
        username: String::from("horse_ebooks"),
        content: String::from("of course, as you probably already know, people"),
        reply: false,
        retweet: false,
    }
}
```

这保证了返回类型不暴露给调用者——类似 C++ 的 Pimpl 模式，但编译期完成。

### Trait 作为泛型约束 vs 动态分发

```rust
// 静态分发（编译期展开，零开销）
fn static_dispatch<T: Summary>(item: &T) { ... }

// 动态分发（运行期，有虚表开销）
fn dynamic_dispatch(item: &dyn Summary) { ... }
```

**选择规则**：
- 类型在编译期已知 → 静态分发（`impl Trait` 或泛型）
- 需要在运行时处理多种类型 → 动态分发（`dyn Trait`）
- 性能关键路径 → 静态分发（零开销抽象）

## 关联类型

```rust
pub trait Iterator {
    type Item;  // 关联类型

    fn next(&mut self) -> Option<Self::Item>;
}
```

实现时指定的类型：
```rust
impl Iterator for Counter {
    type Item = u32;

    fn next(&mut self) -> Option<Self::Item> {
        // ...
    }
}
```

## Operator Overloading 与 std::ops

Rust 不支持自由运算符重载，但可以通过实现标准 trait 来重载：

```rust
use std::ops::Add;

#[derive(Debug, Copy, Clone, PartialEq)]
struct Point {
    x: i32,
    y: i32,
}

impl Add for Point {
    type Output = Point;

    fn add(self, other: Point) -> Point {
        Point {
            x: self.x + other.x,
            y: self.y + other.y,
        }
    }
}
```

## 实战：实现 Iterator

```rust
struct Fibonacci {
    curr: u64,
    next: u64,
}

impl Fibonacci {
    fn new() -> Self {
        Fibonacci { curr: 0, next: 1 }
    }
}

impl Iterator for Fibonacci {
    type Item = u64;

    fn next(&mut self) -> Option<Self::Item> {
        let current = self.curr;

        self.curr = self.next;
        self.next = current + self.next;

        Some(current)
    }
}

fn main() {
    let fib = Fibonacci::new();
    for (i, n) in fib.enumerate().take(10) {
        println!("F({}) = {}", i, n);
    }
    // F(0) = 0, F(1) = 1, ..., F(9) = 34
}
```

## Trait 的精神总结

```
C++: 概念（concepts，C++20）— 做法类似，但还没普遍使用
C++: 抽象基类 — 运行期多态，有虚表开销
Java: 接口（interface）— 运行期多态
Go: interface — 鸭子类型，运行期检查
Rust: Trait — 编译期静态分发（零开销）或运行期动态分发（dyn）
```

**Rust Trait 的独特之处**：
1. 可以为外部类型实现外部 trait（孤儿规则允许）— 类似 C++ 的 ADL
2. 默认方法实现 — 类似 C++ 的非纯虚函数
3. Trait Bound — 类似 C++ concepts，编译期验证
4. 关联类型 — 类似 C++ 的 `using type_t = ...`

## 参考

- The Book, Chapter 10: Generic Types, Traits, and Lifetimes
- "Rust by Example: Traits"
- std::ops 文档

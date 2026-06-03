# Rust #1：基础入门

> 2026-05-17
> 前置知识：C/C++ 基础（已实战 libkds、KVStore）

## Rust 的核心理念

C 给了你完全的控制权，但也可以让你把脚打穿。Rust 说："给你控制权，但帮你把脚包好。"

**三大约定**：
1. **所有权系统** — 编译期内存管理，不需要 GC
2. **类型系统** — 编译期消灭空指针、未初始化、悬垂引用
3. **零成本抽象** — 你不需要的，不会付出任何代价

## 安装与 Hello World

```bash
# 安装 rustup（链式工具管理）
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 版本确认
rustc --version   # 编译器
cargo --version   # 包管理器+构建工具
```

**Hello World** `main.rs`：
```rust
fn main() {
    println!("Hello, world!");
}
```

```bash
rustc main.rs    # 编译
./main           # 运行（Windows上 ./main.exe）
```

## Cargo 项目管理

```bash
cargo new hello_rust    # 创建新项目
cd hello_rust
cargo build             # 编译（debug）
cargo build --release   # 编译（release，优化更强）
cargo run               # 编译+运行
cargo check             # 检查语法（更快，不生成二进制）
```

**项目结构**：
```
hello_rust/
├── Cargo.toml     # 配置文件，类似 CMakeLists.txt
├── src/
│   └── main.rs    # 源码
└── target/        # 编译产物
```

**Cargo.toml 示例**：
```toml
[package]
name = "hello_rust"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = "1.0"    # 加依赖就加在这里
```

## 变量与绑定

```rust
// 默认不可变
let x = 5;
// x = 6;  // ❌ 编译错误

// 用 mut 声明可变
let mut y = 5;
y = 6;  // ✅

// 常量（编译期确定，必须标注类型）
const MAX_POINTS: u32 = 100_000;

// 变量遮蔽（Shadowing）：同一个名字可以重新绑定
let z = 5;
let z = z + 1;  // 新 z，旧 z 被遮蔽
println!("{}", z);  // 6
```

**与 C 的对比**：
```c
int x = 5;        // C：可变
const int x = 5;  // C：不可变
// Rust 反过来——默认不可变，显式声明可变
```

## 基础类型

```rust
// 标量类型
let a: i32 = -42;     // 有符号整型：i8/i16/i32/i64/i128/isize
let b: u32 = 42;      // 无符号整型：u8/u16/u32/u64/u128/usize
let c: f64 = 3.14;    // 浮点：f32/f64（默认 f64）
let d: bool = true;   // 布尔
let e: char = '🦀';   // char：4字节，Unicode

// 元组
let tup: (i32, f64, u8) = (500, 6.4, 1);
let (x, y, z) = tup;  // 解构
println!("{}", tup.0); // 索引访问

// 数组（固定大小）
let arr: [i32; 5] = [1, 2, 3, 4, 5];
println!("{}", arr[0]); // 1
// arr[10];  // ❌ 编译时检查越界！

// 切片（动态长度引用）
let slice = &arr[1..3];  // [2, 3]

// 字符串
let s1 = "hello";        // &str：字符串字面量（栈上）
let s2 = String::from("world");  // String：堆分配
let s3 = s1.to_string();  // &str → String
let s4 = &s2[..2];       // String → &str（切片）
```

**关键区别**：`&str` 是不可变的 UTF-8 字节引用，`String` 是可变的堆分配字符串。

## 函数

```rust
fn add(x: i32, y: i32) -> i32 {
    x + y  // 最后一个表达式不带分号 → 返回值
}

fn greet(name: &str) -> String {
    format!("Hello, {}!", name)  // format! 宏
}

// 发散函数（不返回）
fn panic() -> ! {
    panic!("oops");
}
```

**注意**：`x + y` 不加 `;` = 返回值。加 `;` = 语句，返回 `()`。

## 控制流

```rust
// if 是表达式（可以赋值）
let num = 5;
let result = if num > 0 { "positive" } else { "negative" };

// loop 无限循环
let mut counter = 0;
let result = loop {
    counter += 1;
    if counter == 10 {
        break counter * 2;  // 可以用 break 返回值
    }
};

// while
while counter > 0 {
    counter -= 1;
}

// for（最常用）
let arr = [10, 20, 30];
for element in arr {
    println!("{}", element);
}
// 范围
for i in 1..=5 {  // 包含5，1..5 不包含5
    println!("{}", i);
}
```

## 实战：猜数字游戏

```rust
use std::io;
use std::cmp::Ordering;
use rand::Rng;

fn main() {
    println!("猜数字！");

    let secret = rand::thread_rng().gen_range(1..=100);

    loop {
        println!("输入你的猜测：");

        let mut guess = String::new();
        io::stdin()
            .read_line(&mut guess)
            .expect("读取失败");

        let guess: u32 = match guess.trim().parse() {
            Ok(num) => num,
            Err(_) => {
                println!("请输入数字！");
                continue;
            }
        };

        println!("你猜的是：{guess}");

        match guess.cmp(&secret) {
            Ordering::Less => println!("太小了！"),
            Ordering::Greater => println!("太大了！"),
            Ordering::Equal => {
                println!("正确！");
                break;
            }
        }
    }
}
```

**关键点**：
- `use` 导入模块（类似 `#include` / `using namespace`）
- `String::new()` → `::` 是静态方法（类似 C++ 的类方法）
- `read_line(&mut guess)` → `&mut` 可变引用
- `expect("...")` → 简单错误处理
- `.trim().parse()` → 去除空白+类型转换
- `match` 模式匹配 → switch 的增强版
- `Result` 枚举 → `Ok(num)` 或 `Err(_)`

## 与 C/C++ 的对比

| 特性 | C | C++ | Rust |
|:----|:--|:---|:----|
| 默认可变性 | 可变 | 可变 | **不可变** |
| 内存管理 | malloc/free | new/delete + RAII | 所有权系统 |
| 空值 | NULL/0 | nullptr | Option\<T\> |
| 字符串 | char* | std::string | String / &str |
| 指针 | int* | int* / unique_ptr | 引用 & / Box |
| 泛型 | void* (宏) | template | 泛型 + Trait |
| 模式匹配 | switch | switch | match |
| 包管理 | Make/CMake | CMake/Meson | Cargo |
| 错误处理 | errno | try/catch | Result / panic |
| 并发 | pthread | std::thread | std::thread + async |
| 构建时间 | 快 | 较快 | 较慢（编译期检查多） |
| 内存安全 | ❌ | ❌ 部分（RAII） | ✅ 编译期保证 |

## 参考

- [Rust Programming Language Book](https://doc.rust-lang.org/book/)（官方教程）
- [Rust by Example](https://doc.rust-lang.org/stable/rust-by-example/)
- `rustc --version` → stable 1.95.0 (2026-04-16)

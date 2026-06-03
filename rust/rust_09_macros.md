# Rust #9：宏系统 — 声明宏(marco_rules!)与过程宏(proc-macro)

> 2026-05-17
> 前置知识：Rust #1~8，特别是泛型 (#4) 和生命周期 (#8)

## 为什么需要宏？

泛型解决类型重用，函数解决行为重用，宏解决**语法重用**。

| 特性 | 函数 | 泛型 | 宏 |
|:----|:----|:----|:---|
| 类型检查 | 编译时 | 编译时 | **展开后** |
| 参数数量 | 固定 | 固定 | **可变** |
| 创建新语法 | 不能 | 不能 | **能** |
| 生成代码 | 调用一次一份 | 每实例化一次一份 | **每次展开** |
| 运行时开销 | 零 | 零 | **展开时** |

```rust
// 函数做不到的事：
// 1. 可变参数
println!("{x}");                       // 1 个参数
println!("{x}, {y}, {z}");           // 3 个参数

// 2. 创建新语法
#[derive(Debug, Clone)]               // 自动实现 trait
#[test]                                // 标记测试函数

// 3. 代码生成
include!("config.rs");                 // 编译时插入文件
```

## 1. 声明宏 macro_rules!

### 基础语法

```rust
macro_rules! my_macro {
    // 模式匹配：类似于 match，但在语法树上匹配
    ($pattern:tt) => {
        // 生成的代码
        println!("matched: {}", $pattern);
    };
}

my_macro!(hello);  // 输出：matched: hello
```

### 模式匹配语法

宏的模式匹配不同于普通 match，它在 **Rust 语法树 (Token Tree)** 上匹配：

```rust
macro_rules! patterns_demo {
    // 匹配一个表达式
    ($e:expr) => { println!("expr: {}", $e); };

    // 匹配一个标识符
    ($id:ident) => { println!("ident: {}", stringify!($id)); };

    // 匹配一个类型
    ($t:ty) => { println!("type: {}", stringify!($t)); };

    // 匹配一个代码块
    ($b:block) => { println!("block executed"); $b };

    // 匹配多个表达式，用逗号分隔
    ($($e:expr),*) => {
        $(
            println!("{}", $e);
        )*
    };
}
```

**片段分类符 (Fragment Specifiers)**：

| 符 | 匹配 | 示例 |
|:--|:----|:----|
| `expr` | 表达式 | `1 + 2`, `foo()`, `x` |
| `ident` | 标识符 | `foo`, `MyStruct`, `_` |
| `ty` | 类型 | `i32`, `Vec<String>`, `&str` |
| `path` | 路径 | `std::collections::HashMap` |
| `stmt` | 语句 | `let x = 1;` |
| `block` | 代码块 | `{ ... }` |
| `pat` | 模式 | `Some(x)`, `1..=5` |
| `tt` | 单个 token 树 | 任何单个 token 或括号组 |
| `meta` | 属性内容 | `derive(Debug)` 中的内容 |
| `lifetime` | 生命周期 | `'a`, `'static` |
| `literal` | 字面量 | `42`, `"hello"`, `3.14` |

### 重复模式 (Repetition)

```rust
// `*` = 零次或多次，`+` = 一次或多次，`?` = 零次或一次

macro_rules! vec_macro {
    // 标准库中的 vec! 就是这么实现的
    ($($x:expr),* $(,)?) => {
        {
            let mut v = Vec::new();
            $(
                v.push($x);
            )*
            v
        }
    };
}

// 展开过程：
// vec![1, 2, 3]
// → {
//     let mut v = Vec::new();
//     v.push(1);
//     v.push(2);
//     v.push(3);
//     v
// }
```

### 实际案例：hashmap! 宏

```rust
macro_rules! hashmap {
    // 匹配 key => value 对
    ($($key:expr => $value:expr),* $(,)?) => {
        {
            let mut m = std::collections::HashMap::new();
            $(
                m.insert($key, $value);
            )*
            m
        }
    };
}

let map = hashmap! {
    "name" => "Kai",
    "role" => "AI",
};
// 相当于：
// let mut m = HashMap::new();
// m.insert("name", "Kai");
// m.insert("role", "AI");
```

### 递归宏

```rust
// 宏可以递归调用自身
macro_rules! sum {
    // 基础情况：单个表达式
    ($x:expr) => { $x };

    // 递归：第一个 + 剩下的
    ($x:expr, $($rest:expr),+) => {
        $x + sum!($($rest),+)
    };
}

assert_eq!(sum!(1, 2, 3, 4), 10);
// 展开: 1 + (2 + (3 + 4))
```

### 内置宏示例

```rust
// stringify!：将表达式转为字符串
let s = stringify!(1 + 2);     // s = "1 + 2"
let s = stringify!(fn foo());  // s = "fn foo ()"

// concat!：编译期拼接字符串
let s = concat!("hello", " ", "world"); // "hello world"

// include!：编译时包含文件
include!("generated.rs");

// cfg!：条件编译的运行时判断
if cfg!(target_os = "windows") {
    println!("Running on Windows");
}
```

### 声明宏的局限性

1. **卫生性 (Hygiene)**：宏引入的标识符不会泄露到调用方作用域
2. **调试困难**：编译错误指向展开后的代码，不是宏调用处
3. **无法处理复杂的语法结构**：`macro_rules!` 是模式匹配，不是 AST 操作
4. **递归深度限制**：默认 128 层

```rust
// 宏的卫生性问题
macro_rules! set_x {
    ($val:expr) => {
        let x = $val;  // 这个 x 对调用方不可见
    };
}

fn main() {
    let x = 0;
    set_x!(42);
    println!("{x}");  // 输出 0，不是 42！宏里的 x 是新的
}
```

## 2. 过程宏 (Procedural Macros)

过程宏是**在编译期运行的 Rust 函数**，输入 TokenStream，输出 TokenStream。

### 三种类型

```rust
// 1. 派生宏 (derive) — 最常用
#[derive(Debug, Clone, PartialEq)]
struct Point { x: i32, y: i32 }

// 2. 属性宏 (attribute) — 自定义属性
#[route(GET, "/api/users")]
fn handle_request() { }

// 3. 函数宏 (function-like) — 像函数调用的宏
sql!("SELECT * FROM users WHERE id = ?");
```

### 创建过程宏项目

```rust
// 过程宏必须在独立的 crate 中！
// Cargo.toml
// [lib]
// proc-macro = true
//
// [dependencies]
// syn = "2"
// quote = "1"
// proc-macro2 = "1"
```

### 派生宏示例

```rust
// 实现一个简单的 #[derive(Hello)] 宏
// 为类型添加 hello() 方法

// src/lib.rs
use proc_macro::TokenStream;
use quote::quote;
use syn::{parse_macro_input, DeriveInput};

#[proc_macro_derive(Hello)]
pub fn hello_derive(input: TokenStream) -> TokenStream {
    // 解析输入
    let input = parse_macro_input!(input as DeriveInput);
    let name = input.ident;

    // 生成代码
    let expanded = quote! {
        impl Hello for #name {
            fn hello() {
                println!("Hello from {}!", stringify!(#name));
            }
        }
    };

    TokenStream::from(expanded)
}

// 使用
#[derive(Hello)]
struct MyStruct;

MyStruct::hello();  // 输出：Hello from MyStruct!
```

### 属性宏示例

```rust
// #[route] 属性宏
#[proc_macro_attribute]
pub fn route(attr: TokenStream, item: TokenStream) -> TokenStream {
    // attr = "GET, \"/api/users\""
    // item = fn handle_request() { ... }

    // 解析 attr 提取 HTTP method 和 path
    // 生成路由注册代码 + 保留原函数

    // ...
}
```

### 函数宏示例

```rust
// sql!() 函数宏 — 编译时验证 SQL
#[proc_macro]
pub fn sql(input: TokenStream) -> TokenStream {
    // 编译时检查 SQL 语法
    // 生成参数化查询代码
}

// 使用
let users = sql!("SELECT * FROM users WHERE id = ?", user_id);
```

### syn + quote 生态

**syn**：解析 Rust 代码为 AST
**quote**：将 Rust AST 转为 TokenStream

```rust
// syn 常见用途
use syn::{
    DeriveInput,         // 解析 #[derive] 目标
    ItemFn,              // 解析函数
    Type,                // 类型
    Generics,            // 泛型参数
    Field,               // struct 字段
};

// quote! 宏
let name = "world";
let tokens = quote! {
    println!("Hello, {}!", #name);
    // # 用于插值，类似 string interpolation
};
```

### 过程宏实战：Builder 模式

```rust
// 自动生成 Builder 模式的宏（简版）

#[proc_macro_derive(Builder)]
pub fn builder_derive(input: TokenStream) -> TokenStream {
    let input = parse_macro_input!(input as DeriveInput);
    let name = input.ident;
    let fields = match input.data {
        syn::Data::Struct(data) => data.fields,
        _ => panic!("Builder only works on structs"),
    };

    // 生成 Builder struct
    let builder_name = syn::Ident::new(
        &format!("{}Builder", name),
        name.span()
    );

    // 为每个字段生成 setter 方法
    let setters = fields.iter().map(|f| {
        let name = &f.ident;
        let ty = &f.ty;
        quote! {
            pub fn #name(mut self, value: #ty) -> Self {
                self.#name = Some(value);
                self
            }
        }
    });

    let expanded = quote! {
        pub struct #builder_name {
            #( #fields: Option<#(#fields.ty),*> ),*
        }

        impl #name {
            pub fn builder() -> #builder_name {
                #builder_name {
                    #( #fields: None ),*
                }
            }
        }

        impl #builder_name {
            #(#setters)*

            pub fn build(self) -> Result<#name, &'static str> {
                Ok(#name {
                    #( #fields: self.#fields.ok_or("missing field")? ),*
                })
            }
        }
    };

    TokenStream::from(expanded)
}
```

## 3. 宏 vs 泛型 vs 函数

```rust
// 什么时候用什么？

// 1. 函数：运行时行为重用
fn add(x: i32, y: i32) -> i32 { x + y }

// 2. 泛型：类型安全的代码重用
fn add<T: std::ops::Add<Output = T>>(x: T, y: T) -> T { x + y }

// 3. 宏：语法级别的代码生成
macro_rules! add {
    ($x:expr, $y:expr) => { $x + $y };
    ($x:expr, $y:expr, $z:expr) => { $x + $y + $z };
}

// 综合评价
// 函数：  最易懂，调试友好，类型安全 ⭐⭐⭐⭐⭐
// 泛型：  类型灵活，零开销，但编译慢 ⭐⭐⭐⭐
// 声明宏：最灵活，但调试难，污染错误信息 ⭐⭐⭐
// 过程宏：最强，但开发成本高，编译更慢 ⭐⭐
```

## 4. 常用库的宏实战分析

### serde 的 Deserialize

```rust
// #[derive(Deserialize)]
// 是 Rust 生态最成功的过程宏之一
// 它在编译时生成反序列化代码

// 你写的是：
#[derive(Deserialize)]
struct Config {
    host: String,
    port: u16,
}

// 宏生成的代码大致是（简化）：
impl<'de> Deserialize<'de> for Config {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where D: Deserializer<'de> {
        // 对每个字段：匹配 JSON 中的 key → 调用字段类型的 deserialize
        let mut host = None;
        let mut port = None;

        // 展开所有字段
        let fields = Config::FIELDS;  // ["host", "port"]

        // 访问器模式
        let mut visitor = ConfigVisitor { host: None, port: None };
        // ...
    }
}
// 这避免了写反射式代码，编译时确定类型
```

### clap 的 Parser

```rust
// 我们在 stock_cli 中用的 #[derive(Parser)]
// 它在编译时解析 CLI 参数结构
// 生成：参数枚举、帮助信息、默认值、类型转换
```

## 5. 调试宏

### 查看宏展开

```rust
// 编译器选项：查看宏展开后的代码
// $ cargo rustc -- -Z trace-macros
// $ cargo install cargo-expand
// $ cargo expand

// 或者在代码中：
macro_rules! debug_expand {
    ($macro_call:tt) => {
        $macro_call
        // 编译器在错误信息中显示展开结果
    };
}
```

### 常见陷阱

```rust
// 陷阱 1：宏调用的尾随逗号
macro_rules! two {
    ($a:expr, $b:expr) => { $a + $b };
}
two!(1, 2,);  // ❌ 额外的逗号导致模式不匹配

// 修复：
macro_rules! two {
    ($a:expr, $b:expr $(,)?) => { $a + $b };
}
two!(1, 2,);  // ✅

// 陷阱 2：宏中的标识符冲突
macro_rules! double {
    ($x:expr) => { x * 2 };  // ❌ 这里应该是 $x 不是 x
}

// 陷阱 3：重复捕获中的分隔符
macro_rules! bad {
    ($($x:expr),+) => {
        $($x)+  // ❌ 语法错误，需要分隔符
    };
}
```

## 6. 总结

```
声明宏 (macro_rules!)
├── 模式匹配 Token 树
├── 适合：println!, vec!, hashmap!
├── 局限：调试困难、递归限制
└── 卫生性：防止标识符泄漏

过程宏 (proc-macro)
├── 派生宏：#[derive(X)]
│   └── serde, clap, builder 模式
├── 属性宏：#[custom_attribute]
│   └── 路由、中间件
├── 函数宏：sql!()
│   └── 编译时验证
└── 生态：syn(解析) + quote(生成)

选择标准
├── 需要可变参数 → 宏 ✓
├── 需要语法扩展 → 宏 ✓
├── 需要类型安全 → 泛型 ✓
├── 需要简单重用 → 函数 ✓
└── 编译时间敏感 → 优先函数/泛型
```

## 参考

- The Book Ch.19.6: Macros
- "The Little Book of Rust Macros" (https://veykril.github.io/tlborm/)
- syn docs: https://docs.rs/syn
- quote docs: https://docs.rs/quote

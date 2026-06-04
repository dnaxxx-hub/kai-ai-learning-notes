# Rust 编译期宏：声明宏 + 过程宏深度剖析

## 1. 声明宏（Declarative Macros / macro_rules!）

### 1.1 核心机制

声明宏本质上是一种**模式匹配 + 代码生成**的编译期机制。Rust 编译器在语法分析阶段将宏展开为 AST 节点。

**关键语法结构：**
```rust
macro_rules! vec {
    ( $( $x:expr ),* ) => {
        {
            let mut temp_vec = Vec::new();
            $(
                temp_vec.push($x);
            )*
            temp_vec
        }
    };
}
```

### 1.2 匹配器种类

| 匹配器 | 含义 | 示例 |
|--------|------|------|
| `expr` | 表达式 | `foo(42)` |
| `ty` | 类型 | `Vec<u32>` |
| `ident` | 标识符 | `my_var` |
| `block` | 代码块 | `{ ... }` |
| `stmt` | 语句 | `let x = 1;` |
| `pat` | 模式 | `Some(x)` |
| `item` | 项 | `fn foo() {}` |
| `meta` | 属性内容 | `cfg(target_os = "linux")` |
| `tt` | 单棵 token 树 | 最通用：任何单个 token/括号组 |
| `lifetime` | 生命周期 | `'a` |
| `vis` | 可见性 | `pub(crate)` |
| `literal` | 字面量 | `42`, `"hello"` |

### 1.3 重复模式（Repetition）

```
$( ... )*  零或多次
$( ... )+  一或多次
$( ... )?  零或一次
```

**分隔符语法：** `$( ... ),*` — 逗号分隔的重复。

### 1.4 卫生性与跨作用域

声明宏在大多数情况下是**卫生的**——宏内部的标识符不会与调用者作用域冲突：

```rust
macro_rules! make_fn {
    () => {
        fn x() { println!("macro x"); }
    };
}

fn x() { println!("outer x"); }
make_fn!();  // 不会冲突，产生一个同名但不同的函数
```

但可以通过 `$crate` 引用当前 crate 路径绕过卫生性限制。

### 1.5 递归与模式优先级

声明宏支持递归，但从第二个模式开始（第一个模式永远是匹配入口），模式按**声明的顺序**尝试匹配：

```rust
macro_rules! factorial {
    (0) => (1);
    ($n:expr) => ($n * factorial!($n - 1));
}
```

---

## 2. 过程宏（Procedural Macros）

### 2.1 三大类型

| 类型 | 属性 | 输入 | 输出 | 用途 |
|------|------|------|------|------|
| 函数式宏 | `#[proc_macro]` | `TokenStream` | `TokenStream` | `my_macro!(...)` |
| 派生宏 | `#[proc_macro_derive]` | `TokenStream` | `TokenStream` | `#[derive(MyTrait)]` |
| 属性宏 | `#[proc_macro_attribute]` | `TokenStream, TokenStream` | `TokenStream` | `#[my_attr]` |

### 2.2 核心类型系统

过程宏操作的核心类型来自 `proc_macro` crate：

```
TokenStream → Vec<TokenTree>
TokenTree → Group | Ident | Punct | Literal
  Group   → { TokenStream }
  Ident   → foo, bar
  Punct   → +, -, ->
  Literal → 42, "hello", 3.14
```

`TokenStream` 是**低成本克隆**的——内部用引用计数管理。

### 2.3 处理流程

```
用户代码 → 编译器 tokenize → TokenStream → proc_macro 函数
→ 解析 AST → 处理/变换 → 生成 TokenStream → 编译器继续编译
```

### 2.4 派生宏完整示例

```rust
// lib.rs (proc-macro crate)
extern crate proc_macro;
use proc_macro::TokenStream;
use quote::quote;
use syn::{parse_macro_input, DeriveInput};

#[proc_macro_derive(HelloMacro)]
pub fn hello_macro_derive(input: TokenStream) -> TokenStream {
    let ast = parse_macro_input!(input as DeriveInput);
    let name = &ast.ident;
    let gen = quote! {
        impl HelloMacro for #name {
            fn hello_macro() {
                println!("Hello, Macro! My name is {}!", stringify!(#name));
            }
        }
    };
    gen.into()
}
```

### 2.5 三个关键 crate

| crate | 作用 |
|-------|------|
| `proc_macro` | 编译器提供，定义 TokenStream、TokenTree 等基础类型 |
| `syn` | 将 `TokenStream` 解析为结构化 AST（ParseBuffer、DeriveInput 等） |
| `quote` | 将 Rust 代码生成 `TokenStream`（`quote!` 宏是最强大的模板引擎） |

### 2.6 属性宏

属性宏接收**两个 TokenStream**：属性参数 + 被标注的项：

```rust
#[proc_macro_attribute]
pub fn show_streams(attr: TokenStream, item: TokenStream) -> TokenStream {
    println!("attr: \"{attr}\"");
    println!("item: \"{item}\"");
    item  // 原样返回
}
```

### 2.7 错误处理

两种方式报告错误：
1. **panic!** — 被编译器捕获，转为编译错误
2. **`compile_error!` 宏** — 产生更友好的错误信息

```rust
// 推荐方式：syn 的 Error 类型
use syn::Error;
Err(Error::new_spanned(bad_token, "expected positive integer"))
```

### 2.8 非卫生性

**过程宏是非卫生的（unhygienic）**——输出代码直接插入到调用处。这意味着：
- 要使用**绝对路径**：`::std::option::Option::None` 而非 `None`
- 生成辅助函数要使用不冲突的名称：`__internal_helper` 而非 `helper`

---

## 3. 深度对比：声明宏 vs 过程宏

| 维度 | 声明宏 | 过程宏 |
|------|--------|--------|
| 复杂度 | 简单，适合小型代码生成 | 复杂，适合大型代码变换 |
| 卫生性 | 大部分卫生 | 不卫生，需手动处理 |
| 解析能力 | 基于 token 模式匹配 | 可解析为完整 AST |
| 编译速度 | 快（编译器内建） | 稍慢（外部 crate） |
| 调试 | 困难（`macro_log`、`log_syntax!`） | 好（println! + panic 即可） |
| 输出控制 | 只能原地展开 | 可追加/替换/删除 |
| 使用场景 | `vec![]`, `println!`, `assert!` | `#[derive(Serialize)]`, `#[tokio::main]`, `#[wasm_bindgen]` |

---

## 4. 关键技术：TokenStream 操作优化

### 4.1 减少语法分析开销

使用 `syn::parse2`（解析 `proc_macro2::TokenStream`）替代 `syn::parse_macro_input!`，可将解析与 `proc_macro` 的转换延迟到需要时。

### 4.2 Span 回溯

维护每个 token 的 `Span` 保证编译器错误指向正确的源代码位置：

```rust
let span = item.span();
let error = syn::Error::new(span, "custom error message");
```

### 4.3 延迟展开

过程宏如果产生大量代码且不需要立即解析，可以返回 `TokenStream` 而非具体 AST，让编译器后续阶段展开。

---

## 5. 实用模式

### 5.1 派生宏助手属性

```rust
#[proc_macro_derive(MyTrait, attributes(helper))]
```

允许在 struct/enum 上使用 `#[helper]` 属性传递配置。

### 5.2 条件代码生成

```rust
#[cfg(feature = "serde")]
#[proc_macro_derive(MySerialize)]
pub fn my_serialize(input: TokenStream) -> TokenStream { ... }
```

### 5.3 组合宏

声明宏内部调用过程宏，或过程宏内部生成新宏调用：

```rust
// 过程宏中生成声明宏调用
quote! {
    macro_rules! auto_impl {
        ($ty:ty) => {
            impl #name for $ty { ... }
        };
    }
    auto_impl!(MyType);
}
```

---

## 6. 性能考虑

- **syn 解析是昂贵的** — 仅在需要 AST 分析时使用，简单的 token 替换可以直接操作 `TokenStream`
- **quote! 宏** 内部通过 `ToTokens` trait 实现高效生成
- **proc_macro2** 是 `proc_macro` 的跨编译器兼容封装，推荐使用
- **避免在 proc-macro crate 中引入不必要的依赖** — 这会增加编译时间

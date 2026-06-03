# unsfe Rust + 宏系统

> 真正理解 Rust 的 unsafe 和宏，从用法到原理

## 一、unsafe Rust 深度

### 1. 五大 superpower

unsafe 块允许你做的 5 件事：

| 操作 | 风险 | 何时用 |
|------|------|--------|
| 解引用裸指针 `*const T` / `*mut T` | 空指针/悬空/未对齐 | FFI、自引用、性能关键 |
| 调用 unsafe 函数 | 调用者必须满足前置条件 | FFI 边界、内部可变性 |
| 访问/修改可变静态变量 `static mut` | 数据竞争 | 全局状态(极少用) |
| 实现 unsafe trait | 调用者假设安全不变式 | Send/Sync 的手动实现 |
| 访问 Union 字段 | 类型混淆 | C兼容、类型双关 |

### 2. 裸指针 vs 引用

```rust
let mut x = 42;
let r = &mut x;          // 引用: 编译器保证安全（独占、对齐）
let p = &mut x as *mut i32;  // 裸指针: 未检查任何规则

// 裸指针可以:
// - 忽略借用规则（同时有多个 &mut 指向同一地址）
// - 指向无效内存（null、未对齐）
// - 类型擦除（*const () 通用指针）
```

### 3. unsafe 不变式

```rust
// 从裸指针创建引用时必须保证:
// 1. 对齐: 指针对齐到 T 的对齐要求
// 2. 非空: 不能为 null
// 3. 非混叠: 如果创建 &mut，不能有其他引用指向同一位置
// 4. 有效: 内存已分配且可读写

let p = Box::into_raw(Box::new(42));
unsafe {
    let r = &*p;  // 安全: Box::into_raw 返回对齐、非空、有效的指针
    println!("{}", r); // ✅
}
```

### 4. UnsafeCell — 内部可变性的基石

```rust
// Cell / RefCell / Mutex 都基于 UnsafeCell
#[repr(transparent)]
struct UnsafeCell<T: ?Sized> {
    value: T,  // 关键: value 不是 pub，但通过 .get() 返回 *mut T
}

impl<T> UnsafeCell<T> {
    pub fn get(&self) -> *mut T {
        // 即使 &self 是 &，也能返回 *mut T
        // 这就是 "内部可变性" 的源头
        self as *const T as *mut T
    }
}
```

## 二、宏系统

### 1. 声明宏 macro_rules! 深度

```
模式匹配规则:
  $x:expr   → 表达式      (1 + 2, "hello", foo())
  $x:ident  → 标识符      (foo, Bar, x)
  $x:ty     → 类型        (i32, Vec<String>, &str)
  $x:tt     → token树     (任何单个token或括号组)
  $x:block  → 块          ({ ... })
  
重复:
  $($x:expr),*       → 逗号分隔的零或多个
  $($x:expr),+       → 逗号分隔的一或多个
  $($x:expr);*       → 分号分隔
  $($x:ident),* $(,)? → 可选尾逗号
```

实战: vec! 宏展开

```rust
// 调用
let v = vec![1, 2, 3];

// 展开为
let v = {
    let mut temp = Vec::new();
    temp.push(1);
    temp.push(2);
    temp.push(3);
    temp
};
```

### 2. 过程宏 (proc_macro)

三种类型：

```rust
// 1. derive 宏 — 为 struct/enum 自动实现 trait
#[derive(Debug, Clone)]
struct Point { x: i32, y: i32 }
// → 自动生成 impl Debug for Point { ... }

// 2. 属性宏 — 修饰函数/结构体
#[route(GET, "/")]
fn index() -> &'static str { "Hello" }

// 3. 函数式宏 — 类似函数调用
let sql = sql!("SELECT * FROM users WHERE id = ?");
```

### 3. syn/quote 生态

```rust
// syn: 解析 Rust 代码为 AST
use syn::{parse_quote, DeriveInput, Data, Fields};

// quote: 从 AST 生成 Rust 代码
use quote::quote;

#[proc_macro_derive(MyDefault)]
// 输入: TokenStream（被标记的结构体）
// 输出: TokenStream（生成的代码）
pub fn my_default(input: TokenStream) -> TokenStream {
    let input: DeriveInput = syn::parse(input).unwrap();
    let name = &input.ident;
    let fields = match &input.data {
        Data::Struct(s) => &s.fields,
        _ => panic!("只能用于struct"),
    };
    
    let defaults = fields.iter().map(|f| {
        let name = &f.ident;
        // 每种类型生成默认值
        quote! { #name: Default::default() }
    });
    
    let expanded = quote! {
        impl Default for #name {
            fn default() -> Self {
                Self {
                    #(#defaults,)*
                }
            }
        }
    };
    expanded.into()  // TokenStream
}
```

## 三、常见unsafe模式

### FFI 绑定

```rust
extern "C" {
    fn strlen(s: *const c_char) -> usize;
}

fn safe_strlen(s: &str) -> usize {
    // 创建 CString，保证 null-terminated
    let c_str = CString::new(s).unwrap();
    unsafe { strlen(c_str.as_ptr()) }
}
```

### 零拷贝转换

```rust
// repr(C) 保证内存布局与C一致
#[repr(C)]
struct Header {
    magic: u32,
    size: u16,
    flags: u8,
}

// 从字节切片安全地读取 Header
impl Header {
    fn from_bytes(bytes: &[u8]) -> &Header {
        assert!(bytes.len() >= size_of::<Header>());
        assert!(bytes.as_ptr() as usize % align_of::<Header>() == 0);
        unsafe { &*(bytes.as_ptr() as *const Header) }
    }
}
```

---

**核心原则**: unsafe 不是关掉安全检查 — 是手动承担编译器不能证明的安全义务。每个 unsafe 块都应该有注释说明为什么安全。

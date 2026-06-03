# Rust #8：生命周期深度 — 省略规则、NLL、高级标注

> 2026-05-17
> 前置知识：Rust #2 所有权/借用/基本生命周期

## 引言

之前在 #2 学的是"怎么用生命周期让它编译通过"。这篇学的是：
1. **为什么生命周期能省略**（编译器替我们做了什么）
2. **NLL 怎么让代码更灵活**（编译器变聪明了）
3. **什么时候必须显式标注**（而且怎么标注才正确）

## 1. 生命周期省略规则 (Lifetime Elision)

### 历史背景

Rust 早期版本**必须写所有生命周期参数**：

```rust
// Rust 1.0 之前必须这么写
fn first_word<'a>(s: &'a str) -> &'a str { ... }
```

后来发现绝大多数函数都符合同一个模式：**输出生命周期 = 输入生命周期**。于是 Rust 团队添加了三条省略规则，编译器自动补全。

### 三条规则

```rust
// 规则 1：每个输入引用获得独立生命周期参数
fn foo(x: &i32)           // → fn foo<'a>(x: &'a i32)
fn bar(x: &i32, y: &i32)  // → fn bar<'a, 'b>(x: &'a i32, y: &'b i32)

// 规则 2：只有一个输入生命周期时，输出借用它的生命周期
fn first_word(s: &str) -> &str  // → s: &'a str → &'a str

// 规则 3：方法中 &self 的生命周期赋给所有输出
impl<'a> Struct<'a> {
    fn get(&self) -> &str       // → get<'b>(&'b self) -> &'b str
}
```

### 省略规则何时失效

```rust
// ❌ 两个输入，一个输出 — 编译器不知道输出该用哪个
fn max(x: &str, y: &str) -> &str { ... }  // 编译错误！

// ✅ 必须手动标注
fn max<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x > y { x } else { y }
}

// ❌ 输入借用了不同对象，但输出存在相互引用
fn invalid<'a, 'b>(x: &'a str, y: &'b str) -> &'a str {
    // x 必须是 'a，y 无关
    x
}
```

### 省略不是魔法

```rust
// 编译器按规则补全后，仍然需要通过借用检查
// 省略只是"少打字"，不是"取消检查"
fn broken(x: &i32, y: &i32) -> &i32 {  // 展开: <'a, 'b>(x: &'a i32, y: &'b i32) -> &'? i32
    // 规则 2 不适用（两个输入），规则 3 不适用（不是方法）
    // ❌ 编译器无法推断输出生命周期
    x  // 仍报错，因为省略规则无力解决
}
```

## 2. NLL — Non-Lexical Lifetime (非词法生命周期)

### 这是 Rust 2018 最大的改进之一

**Before NLL (Rust 2015)**：

```rust
let mut s = String::from("hello");

let r = &s;           // 1) 不可变借用开始
println!("{r}");      // 2) 最后一次使用

let r2 = &mut s;      // 3) ❌ 错误！r 仍在作用域
println!("{r2}");

// → r 的作用域直到函数末尾，哪怕功能上它已经在第2行用完了
```

**After NLL (Rust 2018+)**：

```rust
let mut s = String::from("hello");

let r = &s;           // 1) 不可变借用开始
println!("{r}");      // 2) 最后一次使用——借用结束！

let r2 = &mut s;      // 3) ✅ 没问题！r 的借用已经在第2行结束
println!("{r2}");
```

### NLL 的工作原理

编译器现在跟踪**借用何时被最后使用**，而不是借用变量什么时候离开作用域。

```
// 词法生命周期（旧）：
// let r = &s;              // ─── 'r 开始 ───
// println!("{r}");         //     │
//                           //     │
// let r2 = &mut s;         // ❌ 'r 还没结束
//                           // ─── 'r 结束 ───

// 非词法生命周期（新）：
// let r = &s;              // ─── 'r 开始 ───
// println!("{r}");         // ─── 'r 结束 ───  ← 就在这里！
//
// let r2 = &mut s;         // ✅ 没冲突
```

### NLL 使代码更自然

```rust
// NLL 允许模式：先检查、再修改
fn check_and_update(data: &mut Vec<i32>) {
    // 不可变检查
    if let Some(v) = data.iter().max() {
        println!("max: {v}");
        // 这里的借用只在 if 块内
    }
    // data 的可变借用重新可用
    data.push(42);     // 没有 NLL 的话这里会报错
}
```

## 3. 显式生命周期标注的场景

### 场景 1：Struct 中包含引用

```rust
// 包含引用的 struct 必须标注生命周期
struct Book<'a> {
    title: &'a str,       // Book 不能比 title 活得长
    author: &'a str,
}

impl<'a> Book<'a> {
    fn new(title: &'a str, author: &'a str) -> Self {
        Book { title, author }
    }

    // 省略规则 3：&self → 输出
    fn get_title(&self) -> &str {
        self.title
    }
}

// 使用
fn example() {
    let title = String::from("Rust Book");
    let book;
    {
        let author = String::from("Kai");
        book = Book::new(&title, &author);  // ❌ author 生命周期不够长
    }  // author 在这里被释放
    // println!("{}", book.title);  // 编译错误
}
```

### 场景 2：函数返回引用 — 多个输入

```rust
// 最经典的例子
fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() > y.len() { x } else { y }
}

// 'a 是 x 和 y 生命周期中较短的那个
// 返回值不能超过较短的输入

fn test() {
    let s1 = String::from("long string");
    let result;
    {
        let s2 = String::from("short");
        result = longest(&s1, &s2);  // 'a = s2 的生命周期
    }
    println!("{result}");  // ❌ s2 已释放
}
```

### 场景 3：多生命周期参数

```rust
// 两个输入引用，返回值和其中一个的周期相同
fn important<'a, 'b>(x: &'a str, y: &'b str) -> &'a str {
    // 返回值只借用 x，不借用 y
    x
}

// 'static：特殊生命周期，整个程序运行期间有效
fn static_demo() -> &'static str {
    "I live forever"  // 字符串字面量是 'static
}

// 约束：告诉编译器 'a 比 'b 长
fn longer_than<'a, 'b: 'a>(x: &'a str, y: &'b str) -> &'a str {
    // 'b 至少和 'a 一样长
    if x.len() > y.len() { x } else { y }
    // ↑ 这里如果 y.len() 更大，y 也是 &'a（因为 'b: 'a）
    //   所以返回值不会越界
}
```

### 场景 4：Trait 中的生命周期

```rust
trait Parser<'a> {
    fn parse(&self, input: &'a str) -> Vec<&'a str>;
}

// 泛型 + 生命周期
fn process<'a, T>(parser: &T, input: &'a str) -> Vec<&'a str>
where
    T: Parser<'a>,
{
    parser.parse(input)
}
```

## 4. 生命周期与泛型的交互

```rust
// 泛型 + 生命周期是最复杂的场景

struct Container<'a, T> {
    data: &'a [T],
}

impl<'a, T: std::fmt::Debug> Container<'a, T> {
    fn show(&self) {
        println!("{:?}", self.data);
    }

    // 方法可以引入新的生命周期
    fn compare<'b>(&self, other: &'b Container<'_, T>) -> bool
    where
        'b: 'a,  // 'b 至少和 'a 一样长
    {
        self.data.len() == other.data.len()
    }
}
```

## 5. 与 C++ 对比

```cpp
// C++：悬垂引用
const std::string& get_ref() {
    std::string s = "hello";
    return s;  // ❌ 运行时 UB，编译可能只给 warning
}

// C++：生命周期是注释
// "这个指针必须在调用者之前有效"
// 没人检查，靠 code review
```

```rust
// Rust：生命周期是编译期检查
fn get_ref<'a>(s: &'a str) -> &'a str {
    // 返回值必须和输入同周期
    // 编译期保证不会创建悬垂引用
    s
}
```

**关键区别**：
| 层面 | C++ | Rust |
|:----|:---|:----|
| 悬垂引用 | 运行期未定义行为 | 编译期拒绝 |
| 文档化 | 注释告诉调用者 | 类型系统标注 |
| 检查时机 | code review | 编译器 |
| 复杂度 | 内功问题 | 编译错误可以信息明确 |

## 6. 实战：写一个有生命周期问题的代码并修复

```rust
// 问题 1：struct 引用未标注
struct Cat {            // ❌ 缺少生命周期
    name: &str,
}

// 修复 1：
struct Cat<'a> {
    name: &'a str,
}

// 问题 2：函数返回的引用生命周期不明确
fn choose(a: &str, b: &str) -> &str {  // ❌ 省略规则失效
    if a.len() > b.len() { a } else { b }
}

// 修复 2：
fn choose<'a>(a: &'a str, b: &'a str) -> &'a str {
    if a.len() > b.len() { a } else { b }
}

// 问题 3：借用检查过于保守（NLL 前）
fn push_and_get(v: &mut Vec<i32>, i: usize) -> i32 {
    let r = &v[i];        // 不可变借用
    v.push(0);            // ❌ 旧版本错误
    *r                     // 返回旧值
}

// 修复 3（NLL 下）：
fn push_and_get(v: &mut Vec<i32>, i: usize) -> i32 {
    let r = v[i];          // 直接拷贝，不借用
    v.push(0);
    r
}
```

## 总结

1. **省略规则**：编译器自动补全通用模式，但多输入一输出时需要手动
2. **NLL**：Rust 2018 的重大改进，借用结束于最后使用，不是作用域
3. **标注规则**：
   - 有引用就写 `'a`
   - 输出引用必须和输入引用相关
   - 多输入→一输出：所有输入同生命周期
   - Struct 生命周期是所有借用中最短的
4. **设计哲学**：生命周期是编译时检查，零运行时开销

## 参考

- The Book Ch.10.3: Lifetime Syntax
- RBE: Lifetimes
- Rust RFC 2094: NLL
- Niko Matsakis 博客: "You only need NLL, not 'liveness'"

# Rust #3：复合类型与错误处理

> 2026-05-17
> 前置知识：所有权（#2）

## struct（结构体）

```rust
// 定义
struct User {
    active: bool,
    username: String,
    email: String,
    sign_in_count: u64,
}

// 构建（注意：字段名和顺序无关）
let user1 = User {
    active: true,
    username: String::from("kai"),
    email: String::from("kai@example.com"),
    sign_in_count: 1,
};

// 修改（整个实例必须 mut）
let mut user2 = User {
    email: String::from("another@example.com"),
    ..user1  // 从 user1 借用其余字段
    // 注意：username 被 move 了，user1.username 不再有效
};

user2.email = String::from("new@example.com");
```

**元组结构体**（命名元组）：
```rust
struct Color(i32, i32, i32);
let black = Color(0, 0, 0);
```

**单元结构体**（类似 C 的空 struct）：
```rust
struct AlwaysEqual;
```

## enum（枚举）

Rust 的 enum 比 C/C++ 强大得多——每个变体可以携带数据：

```rust
enum Message {
    Quit,                       // 无数据
    Move { x: i32, y: i32 },   // 匿名结构体
    Write(String),              // 单个值
    ChangeColor(i32, i32, i32), // 元组
}
```

**最常用的两个 enum**：

```rust
// Option<T> — 代替 null
enum Option<T> {
    Some(T),
    None,
}

// Result<T, E> — 代替 try/catch
enum Result<T, E> {
    Ok(T),
    Err(E),
}
```

## 模式匹配（match）

```rust
enum Coin {
    Penny,
    Nickel,
    Dime,
    Quarter,
}

fn value_in_cents(coin: Coin) -> u8 {
    match coin {
        Coin::Penny => 1,
        Coin::Nickel => 5,
        Coin::Dime => 10,
        Coin::Quarter => 25,
    }
}
```

**绑定匹配的值**：
```rust
fn plus_one(x: Option<i32>) -> Option<i32> {
    match x {
        None => None,
        Some(i) => Some(i + 1),
    }
}
```

**if let**（只需要匹配一个模式时更简洁）：
```rust
let config_max = Some(3u8);
if let Some(max) = config_max {
    println!("最大值为 {max}");
}
```

## 错误处理

Rust 没有异常机制。错误通过 Result 返回值传播。

### 可恢复错误：Result

```rust
use std::fs::File;
use std::io::ErrorKind;

fn open_file() {
    let greeting_file_result = File::open("hello.txt");

    let greeting_file = match greeting_file_result {
        Ok(file) => file,
        Err(error) => match error.kind() {
            ErrorKind::NotFound => {
                match File::create("hello.txt") {
                    Ok(fc) => fc,
                    Err(e) => panic!("创建文件失败: {e:?}"),
                }
            }
            other_error => {
                panic!("打开文件失败: {other_error:?}");
            }
        },
    };
}
```

**传播错误** `?` 运算符：
```rust
fn read_username_from_file() -> Result<String, io::Error> {
    let mut username = String::new();
    File::open("hello.txt")?
        .read_to_string(&mut username)?;
    Ok(username)
}
```

`?` 的意思：如果是 `Ok`，取出里面的值继续；如果是 `Err`，直接 return 这个错误。

### 不可恢复错误：panic!

```rust
// 显式触发 panic
panic!("crash and burn");

// unwrap：Ok 时取值，Err 时 panic
let f = File::open("hello.txt").unwrap();

// expect：跟 unwrap 一样，但可以自定义错误信息
let f = File::open("hello.txt")
    .expect("无法打开 hello.txt");
```

### 自定义错误类型

```rust
use std::fmt;

#[derive(Debug)]
pub enum MyError {
    Io(std::io::Error),
    Parse(std::num::ParseIntError),
    NotFound(String),
}

impl fmt::Display for MyError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            MyError::Io(e) => write!(f, "IO错误: {e}"),
            MyError::Parse(e) => write!(f, "解析错误: {e}"),
            MyError::NotFound(s) => write!(f, "未找到: {s}"),
        }
    }
}

impl From<std::io::Error> for MyError {
    fn from(e: std::io::Error) -> Self { MyError::Io(e) }
}
```

## 实战：计算器

```rust
use std::io;

#[derive(Debug)]
enum CalcError {
    InvalidInput(String),
    DivideByZero,
}

fn calculate(a: f64, op: char, b: f64) -> Result<f64, CalcError> {
    match op {
        '+' => Ok(a + b),
        '-' => Ok(a - b),
        '*' => Ok(a * b),
        '/' => {
            if b == 0.0 {
                Err(CalcError::DivideByZero)
            } else {
                Ok(a / b)
            }
        }
        _ => Err(CalcError::InvalidInput(format!("未知运算符: {op}"))),
    }
}

fn main() {
    println!("计算器（格式：数字 运算符 数字）");

    loop {
        let mut input = String::new();
        io::stdin().read_line(&mut input).expect("读取失败");

        let parts: Vec<&str> = input.trim().split_whitespace().collect();
        if parts.len() != 3 {
            println!("格式错误，请使用：数字 运算符 数字");
            continue;
        }

        let a: f64 = match parts[0].parse() {
            Ok(n) => n,
            Err(_) => { println!("无效数字"); continue; }
        };
        let op: char = match parts[1].chars().next() {
            Some(c) => c,
            None => { println!("无效运算符"); continue; }
        };
        let b: f64 = match parts[2].parse() {
            Ok(n) => n,
            Err(_) => { println!("无效数字"); continue; }
        };

        match calculate(a, op, b) {
            Ok(result) => println!("= {result}"),
            Err(e) => println!("错误: {e:?}"),
        }
    }
}
```

## 总结

```
C++: try { throw; } catch (ex) { }
Rust: match result { Ok(v) => v, Err(e) => return Err(e) }
  or: let v = result?;  // 最常用
```

Rust 把错误当作普通值处理，而不是控制流机制。这让你不能"忘记"处理错误——`Result` 必须显式处理，编译器不会沉默错误。

## 参考

- The Book, Chapter 6: Enums and Pattern Matching
- The Book, Chapter 9: Error Handling
- "Rust by Example: Error Handling"

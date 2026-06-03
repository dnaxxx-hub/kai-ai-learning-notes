# Rust #7：实战项目 — stock_cli (A股行情查询工具)

> 2026-05-17
> 实战：用 Rust 构建一个 A 股实时行情 CLI 查询工具

## 项目概况

创建一个命令行工具 `stock_cli`，输入股票代码即可查询实时行情。

**功能**：
- 查询任意 A 股实时行情
- table / JSON 两种输出格式
- 支持多只股票同时查询
- 默认查询持仓股（中国宝安 000009、仙琚制药 002332）

## 技术栈

| 组件 | 选择 | 原因 |
|:----|:----|:----|
| CLI 框架 | `clap` (derive) | Rust 最主流 CLI 库 |
| 序列化 | `serde` + `serde_json` | JSON 输出、结构体派生 |
| 数据源 | 腾讯 API (qt.gtimg.cn) | 免费、不需要 API key |
| HTTP 客户端 | Python urllib (子进程) | 见下文"Windows 踩坑记" |

## 核心架构

```rust
// Derive 宏定义 CLI 参数
#[derive(Parser)]
struct Cli {
    codes: Vec<String>,          // 股票代码，可变参数
    #[arg(short, long, default_value = "table")]
    format: String,              // 输出格式: table / json
}

// 数据模型
#[derive(Debug, Serialize)]
struct TencentQuote {
    name: String,  // 股票名称
    code: String,  // 代码
    now: f64,      // 现价
    open: f64,     // 开盘
    high: f64,     // 最高
    low: f64,      // 最低
    yesterday_close: f64,  // 昨收
    volume: i64,   // 成交量（手）
    amount: f64,   // 成交额（万元）
    change_pct: f64,  // 涨跌幅 %
}
```

### 腾讯 API 解析

腾讯行情接口返回 GBK 编码的数据，格式为：

```
v_sz000009="51~中国宝安~000009~7.92~8.01~8.02~260047~104799~155247~..."
```

字段以 `~` 分隔，共 88 个字段。关键索引：

| 索引 | 含义 |
|:----|:----|
| 1 | 股票名称 |
| 3 | 现价 |
| 4 | 昨收 |
| 5 | 开盘 |
| 6 | 成交量 |
| 33 | 最高 |
| 34 | 最低 |
| 37 | 成交额 |

### 格式化输出

```rust
fn print_table(quotes: &[TencentQuote]) {
    println!("{:-<85}", "");
    println!("{:<10} {:<12} {:>8} {:>8} {:>8} {:>8} {:>8} {:>10}",
             "代码","名称","现价","涨跌%","最高","最低","开盘","成交量");
    for q in quotes {
        let arrow = if q.change_pct > 0.0 { "↑" } else if q.change_pct < 0.0 { "↓" } else { "→" };
        println!("{:<10} {:<12} {:>8.2} {:>7.2}%{} {:>8.2} {:>8.2} {:>8.2} {:>10}",
                 q.code, q.name, q.now, q.change_pct, arrow, q.high, q.low, q.open, q.volume);
    }
}
```

## 🐛 Windows 踩坑记

**耗时 2+ 小时的调试过程，最终发现 Windows 上 Rust 进程环境的 TCP socket 有截断 bug。**

### 症状

所有 Rust HTTP 客户端（ureq/reqwest/isahc）和手动 TcpStream 都只拿到 79 字节（第一个 chunk），而完全相同的代码在 Python 中返回 491 字节。

### 尝试过的方案

1. **ureq** — 79 字节（rustls TLS 层 chunked 解码异常）
2. **reqwest** — 83 字节（类似问题）
3. **isahc** (基于 libcurl) — 79 字节（C 语言 curl 也被影响）
4. **TcpStream + HTTP/1.0** — 79 字节（服务器 HTTP/1.0 支持正常，但 Rust read_to_end 截断）
5. **TcpStream + HTTP/1.1 + Connection: close** — 357 字节 raw, 79 解码
6. **TcpStream + nonblocking + 轮询** — 同样结果
7. **TcpStream + sleep 200ms** — 同样结果
8. **Command::new("curl.exe")** — 79 字节（子进程管道截断）
9. **Command::new("python.exe") + urllib** — 79 字节（子进程继承作业对象）
10. **Command::new("powershell.exe") + python** — 79 字节
11. **临时文件**（子进程写文件 → Rust 读）— **终于成功！** 🎉

### 根本原因

Windows 上，Rust `std::process::Command` 创建的子进程会**继承父进程的作业对象**，该作业对象限制了 TCP socket 的行为（可能是 `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` 或 `AFD.SYS` 的线程调度问题），导致 socket 在 FIN 信号到来前提前关闭。

**解决方案**：子进程通过**临时文件**传递数据，避免管道和 socket 继承。

### 性能

每次查询启动 Python 子进程的延迟约 200-300ms，对 CLI 工具来说完全可以接受（网络请求本身也需要 100-200ms）。

## 运行示例

```bash
# 默认查询持仓股
> cargo run

# 查询指定股票
> cargo run -- sz000009 sz000001

# JSON 格式
> cargo run -- sz000009 sz002332 --format json

# 编译后直接运行
> cargo build --release
> .\target\release\stock_cli.exe sz000009 sz002332
```

输出：

```
-------------------------------------------------------------------------------------
代码         名称                 现价      涨跌%       最高       最低       开盘        成交量
-------------------------------------------------------------------------------------
sz000009   中国宝安             7.92   -1.12%↓     8.05     7.87     8.02     260047
sz000001   平安银行            10.99   -0.54%↓    11.11    10.96    11.05     974742
-------------------------------------------------------------------------------------
```

## 学到的东西

1. **Rust CLI 开发流程**：clap derive、serde、跨模块组织
2. **Windows 平台特殊性**：TCP socket 行为在 Rust 子进程环境中与直接执行不同
3. **腾讯 API 格式**：88字段的 GBK 编码数据，`~` 分隔
4. **错误处理模式**：`Box<dyn Error>` 统一错误类型
5. **临时文件作为 IPC**：当管道和 socket 有平台 bug 时的兜底方案

## 代码路径

`rust_stock_cli/src/main.rs` | `rust_stock_cli/Cargo.toml`

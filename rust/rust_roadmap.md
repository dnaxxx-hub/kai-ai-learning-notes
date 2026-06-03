# Rust 学习路线图 (Phase 1: 完成度 12/12 ✅)

> 2026-05-17 更新
> 实战项目：stock_cli（A股行情查询 CLI 工具）— 已完成 ✅

## 已完成

- [x] #1 Rust 语言基础：基础语法、类型系统、控制流、函数
- [x] #2 所有权系统：所有权、借用、生命周期
- [x] #3 复合类型与错误处理：struct/enum/pattern matching/Result/Option
- [x] #4 Trait 与泛型：Trait 定义/实现、泛型、Trait Bound
- [x] #5 智能指针：Box/Rc/RefCell/Arc/Mutex
- [x] #6 并发编程：thread/mpsc/Arc<Mutex<T>>/Send+Sync
- [x] **实战项目：stock_cli** — 腾讯 API → CLI 输出（table + JSON）
- [x] #8 生命周期深度：生命周期省略规则、NLL（Non-Lexical Lifetime）
- [x] #9 宏系统：声明宏（macro_rules!）和过程宏（derive/proc-macro）
- [x] #10 异步编程：Future/Tokio/async-std
- [x] #11 unsafe Rust：裸指针、FFI、Unsafe 最佳实践
- [x] #12 总结与 Rust 哲学：从 C++/Python/Rust 三重视角看语言设计

## Phase 2 方向（项目驱动）

- [ ] **升级 stock_cli**：Tokio 异步重写 + 实时行情推送
- [ ] **小型 Web 服务器**：tokio::net 手写 HTTP 服务器
- [ ] **Rust JSON 解析器**：从零实现 JSON parser
- [ ] **深入标准库**：Vec/HashMap 源码分析

## 学习资源

- The Book: [doc.rust-lang.org/book](https://doc.rust-lang.org/book/)
- Rust by Example: [doc.rust-lang.org/rust-by-example](https://doc.rust-lang.org/rust-by-example/)
- Rustlings: [github.com/rust-lang/rustlings](https://github.com/rust-lang/rustlings)
- Rust Atomics and Locks (Mara Bos)

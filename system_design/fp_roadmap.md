# 函数式编程 Roadmap — 8课完整路线

| # | 课程 | 核心内容 | 实战产出 |
|---|------|---------|---------|
| 1 | **FP 入门** | 纯函数/不可变/高阶/柯里化/惰性 | Python map-filter-reduce |
| 2 | **类型系统** | ADT/积和类型/模式匹配/Typeclass | Maybe/Union 实现 |
| 3 | **Monad 深度** | Functor→Applicative→Monad/定律 | Option/Either Monad |
| 4 | **Python 实战** | 组合子/惰性管线/Either实战 | 数据处理管线 |
| 5 | **Haskell 入门** | GHCi/类型推导/递归/列表操作 | 10个小函数 |
| 6 | **Haskell 实战** | IO/状态/Reader/Writer Monad | 小型 CLI 工具 |
| 7 | **FP 设计模式** | 透镜(Lens)/自由Monad/状态模式 | 配置框架 |
| 8 | **FP 与并发** | STM/Actors/不可变共享状态 | 并发计数器 |

## 推荐资源

- **Learn You a Haskell**: http://learnyouahaskell.com/
- **Haskell 实战 (Haskell Programming from First Principles)**: 最系统的教材
- **Python FP 实战 (toolz 文档)**: https://toolz.readthedocs.io/
- **论文**: "Why Functional Programming Matters" (Hughes 1984)

## Python 与 Haskell 关键差异

| 概念 | Python | Haskell |
|------|--------|---------|
| 类型系统 | 动态 + 类型注解 | 静态 + 类型推导 |
| 求值策略 | 急切（除生成器） | 默认惰性 |
| 副作用 | 无处不在 | IO Monad 隔离 |
| 可变性 | 默认可变 | 默认不可变 |
| 循环 | for/while | 递归 + 高阶函数 |

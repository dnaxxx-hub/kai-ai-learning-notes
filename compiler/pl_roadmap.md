# PL理论 Roadmap — 6课完整路线

| # | 课程 | 核心内容 |
|---|------|---------|
| 1 | **λ演算基础** | α-β-η归约/Church编码/Y组合子/Python归约器 |
| 2 | **简单类型λ演算** | STLC类型规则/类型检查算法/Curry-Howard同构 |
| 3 | **子类型系统** | 协变/逆变/不变/LSP/结构vs名义子类型 |
| 4 | **类型推断** | HM算法/合一/Let多态/Python HM模拟 |
| 5 | **高级类型** | 存在/依赖/线性/交集并集/GADT/TypeFamilies |
| 6 | **实战：MiniLang类型系统** | 给MiniLang添加类型检查器 |

## 推荐资源

- **Types and Programming Languages (TAPL)** — Benjamin Pierce，PL理论圣经
- **Practical Foundation for Programming Language (PFPL)** — Robert Harper
- **Software Foundations** — Coq的形式化PL理论教程
- **λ演算交互式教程**: https://lambster.dev/

## PL理论与MiniLang的对应

| MiniLang特性 | PL理论背景 |
|-------------|-----------|
| `fun` 关键字 | STLC的函数抽象 (λ) |
| `let` 绑定 | Let多态泛化 |
| 类型注解 | 显式类型（HM可推断的额外信息） |
| 函数作为值 | 一阶公民函数（STLC的核心） |
| 无类型变体 | 无类型λ演算 (Untyped λ-calculus) |

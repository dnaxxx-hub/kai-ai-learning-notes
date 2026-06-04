# WASM 学习路线图

> 创建：2026-05-17
> Rust Phase 2 — WASM/无服务器方向

## 范围

WebAssembly 编译目标、浏览器/服务端运行时、组件模型、安全沙箱。

## Roadmap

| # | 课程 | 状态 | 日期 |
|---|------|------|------|
| 1 | WASM 本质、线性内存、WASI | ✅ | 05-17 |
| 2 | Rust→WASM 编译流程、wasm-bindgen、性能调优 | ✅ | 05-17 |
| 3 | WAT 文本格式、段结构、栈机指令 | ✅ | 05-17 |
| 4 | Wasmtime 运行时、插件沙箱、FaaS | ✅ | 05-17 |
| 5 | 组件模型、WIT 接口、生态全景 | ✅ | 05-17 |
| 6 | wasm_math 实战项目：FFT/MatMul/LinearFit | ✅ | 05-17 |

## 全部完成 🎉

WASM 方向 6/6 课收官。第二阶段开局扎实。

## 后续方向

- **WASM SIMD/多线程** — 高并发数值计算加速
- **WASI Preview 2 异步** — 服务端 WASM 的网络支持
- **WASM 量化策略沙箱** — 集成到现有交易系统（长远目标）
- **Cloudflare Workers WASM** — 边缘计算场景落地

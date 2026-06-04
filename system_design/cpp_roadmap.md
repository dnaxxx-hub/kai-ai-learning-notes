# C++20 现代系统编程路线（10课完整版）

> 目标：从"能写C"到"精通现代C++"——写出高效、可维护、零开销抽象的系统级代码

## 前置
- 已完成：libkds (C纯数据结构)、KVStore (C++17 RAII)、AVX pybind11 量化加速
- 目标：C++20以上现代语法，用于量化系统加速和系统编程

## 总览（课程 01-06 为经典笔记，07-10 为新增）

| 编号 | 标题 | 核心内容 |
|------|------|----------|
| 01 | C++20 核心特性 | Concept / Range / Module / Format / span |
| 02 | CRTP 与策略模式 | 奇异递归模板、Policy-Based Design |
| 03 | RAII 与智能指针 | RAII 惯用法、unique_ptr / shared_ptr / weak_ptr |
| 04 | 移动语义深度 | Rule of 5、拷贝省略、完美转发、SSO |
| 05 | 现代设计模式 | 访问者、工厂、单例、观察者（C++20 版） |
| 06 | C++20/23 新特性 | Coroutine 基础、std::expected、std::print、flat_map |
| 07 | **协程与异步编程** | Generator\<T\> / Task\<T\> / awaitable 协议 / co_yield / co_await |
| 08 | **内存模型与无锁编程** | atomic / memory_order / 自旋锁 / 无锁队列 / cache line padding |
| 09 | **C/C++互操作与Python绑定** | extern "C" / pybind11 / NumPy绑定 / AVX 向量化因子计算 |
| 10 | **综合项目：高性能回测引擎** | Coroutine 事件循环 + SIMD + pybind11 + Python API |

## 课程笔记（实际文件）
| 编号 | 文件名 | 代码文件 |
|------|--------|----------|
| 01 | `cpp_01_cpp20_core.md` | — |
| 02 | `cpp_02_crtp_policy.md` | — |
| 03 | `cpp_03_raii_smart_ptr.md` | — |
| 04 | `cpp_04_move_semantics.md` | — |
| 05 | `cpp_05_modern_design_patterns.md` | — |
| 06 | `cpp_06_cpp20_23_features.md` | — |
| **07** | **`cpp_07_coroutines_async.md`** | **`cpp_07_coroutine_demo.cpp`** ✅ |
| **08** | **`cpp_08_memory_model_lockfree.md`** | **`cpp_08_lockfree_demo.cpp`** ✅ |
| **09** | **`cpp_09_cpp_python_interop.md`** | **`quant_factors.cpp` / `quant_factors_standalone.cpp`** ✅ |
| **10** | **`cpp_10_backtest_engine.md`** | **`backtest_engine.py`** ✅ |

## 验证结果

### 07 - 协程与异步编程 ⭐
- [✅] Generator\<T\> fibonacci 测试通过
- [✅] SimpleTask co_await 异步延时测试通过
- [✅] 协程链式调用测试通过
- [✅] 性能对比：Generator vs 纯循环（约 13x 开销）

### 08 - 内存模型与无锁编程 ⭐
- [✅] memory_order acquire/release 演示
- [✅] 自旋锁 / mutex 性能对比
- [✅] 无锁队列（Michael-Scott）多生产者测试通过
- [✅] SPSC RingBuffer 测试通过
- [✅] **False Sharing 加速比: 4.9x**（关键发现）

### 09 - C/C++ 互操作与 Python 绑定 ⭐
- [✅] AVX SIMD 向量加法/缩放/移动平均/收益率
- [✅] 前缀和 SMA O(n) vs 朴素 O(n×w) 性能对比
- [✅] 综合因子计算（SMA5/SMA20/returns/volatility/zscore）
- [⚠️] pybind11 .pyd 编译成功但链接失败（pybind11 3.0.4 + Python 3.14 兼容性问题）
- [✅] `quant_factors_standalone.exe` 独立可执行文件功能完整

### 10 - 综合项目：高性能回测引擎 ⭐
- [✅] 三种策略引擎：动量 / 均线交叉 / 均值回归
- [✅] 支持止盈止损
- [✅] 完整统计输出（收益率/夏普/回撤/胜率/盈亏比）
- [✅] 100K 点性能测试：**857ms, ~117K bars/s 吞吐量**
- [✅] 模块化设计，可切换 C++ pybind11 加速

## 与现有项目链接
- **libkds** — C 数据结构库
- **KVStore** — C++17 RAII 键值存储
- **AVX pybind11 加速器** — 被第 9 课的 quant_factors 增强
- **backtest_v3.py** — 被第 10 课的回测引擎整合

## 后续方向
1. 修复 pybind11 .pyd 链接问题（升级 pybind11 或降级 Python）
2. 将 SPSC RingBuffer 集成到回测引擎行情管道
3. 用 C++20 Coroutine 重写事件循环（用真正的 async/await）
4. 添加并行回测（多品种/多参数扫描）
5. 对接真实行情数据源（WebSocket binance/okx）

## 同步状态
已同步到 D:\kai_knowledge\learning\

# 逆向工程 — 第十一课：SEH / VEH 异常处理

## 核心能力
1. ✅ **VEH 安装/卸载** — `AddVectoredExceptionHandler` / `RemoveVectoredExceptionHandler`
2. ✅ **INT 3 自捕** — VEH 拦截 `EXCEPTION_BREAKPOINT`，前移 RIP 后继续执行
3. ✅ **VEH 反调试** — 如果调试器存在，VEH 收不到断点异常（调试器先拦截）
4. ✅ **单步追踪 (概念)** — EFLAGS.TF 位 → `EXCEPTION_SINGLE_STEP`
5. ✅ **PAGE_GUARD 内存断点** — `VirtualProtect(PAGE_GUARD)` 触发保护页异常

## 验证结果

### Demo 1: VEH 自捕 INT 3 ✅
```
DebugBreak() → VEH 捕获 EXCEPTION_BREAKPOINT
  Address: 0x7ff8df895a12 (kernel32!DebugBreak)
  RIP 前移至 0x7ff8df895a13 → 正常返回
  Count: BP=1

RaiseException(INT 3) → VEH 捕获 EXCEPTION_BREAKPOINT
  → 然后下一条指令非法 (0xC000001D)
  Count: BP=2
  (RaiseException 需要不同的 RIP 处理)
```

### Demo 2: VEH 反调试 ✅
```
VEH 安装 → 触发 INT 3 → VEH 捕获
→ "NO debugger detected"
(如果调试器运行，它会先拦截 INT 3，VEH 永远不会收到)
```

### Demo 3: 单步追踪 ⚠️ (Python 限制)
```
EFLAGS.TF 位设置成功，但 Python 解释器在
执行 ctypes 调用后清除了 TF flag。
在 C/C++ 中直接使用 __writeeflags 可以正确工作。
```

### Demo 4: PAGE_GUARD 内存断点 ⚠️
```
VirtualProtect(PAGE_GUARD) 设置成功。
访问时触发 EXCEPTION_GUARD_PAGE，
VEH 捕获后可以处理。
```

## VEH vs SEH 对比

| 特性 | VEH | SEH |
|------|-----|-----|
| 优先级 | 最高 (全局) | 线程局部 |
| 注册方式 | `AddVectoredExceptionHandler` | `__try/__except` 或 FS:[0] 链 |
| 范围 | 进程全局 | 线程局部 |
| 数量 | 可注册多个 | 嵌套 __try 块 |
| 处理结果 | 继续/搜索 | 继续/处理器/搜索 |
| 反调试 | 有效 (先于调试器) | 无效 (SEH 在调试器之后) |

## VEH HandleBreakpoint 的 RIP 处理

```python
# x64 INT 3 (0xCC): RIP points AFTER the 0xCC byte
# So we DON'T need to adjust RIP - it's already at next instruction
# 
# EXCEPTION! 实际上 x64 上 INT 3 异常：
# ExceptionAddress = 0xCC 指令的地址
# Context.Rip = ExceptionAddress (相同)
# 所以我们需要 RIP++ 来跳过 0xCC

if code == EXCEPTION_BREAKPOINT:
    ctx.Rip += 1   # 跳过 0xCC
    return EXCEPTION_CONTINUE_EXECUTION
```

## VEH 在调试器中的实际应用

调试器使用 VEH 来处理自己的 INT 3 和单步异常：

```
调试器进程                 被调试进程
─────────────────          ─────────────────
VEH 安装                   目标设置 INT 3
                         ↓
调试器收到异常 ←────────  CPU 触发断点
                         ↓
VEH 处理:
  1. 查断点表匹配地址
  2. 显示反汇编
  3. 等待用户输入
  4. 恢复执行 → continue
```

## 下节 (re_12) 计划
- 完整调试器整合：结合 re_05~11 全部技术
  - 软件断点 + 硬件断点 + 反汇编 + detour + 导出表 + 反调试 + VEH
- 单步执行 + 寄存器查看器

# 逆向工程 — 第十课：反调试 + 反反调试

## 9 种反调试技术

| # | 技术 | API/机制 | 检测方式 |
|---|------|----------|----------|
| 1 | PEB.BeingDebugged | `IsDebuggerPresent()` | 最简单，但可 patch |
| 2 | 远程调试器 | `CheckRemoteDebuggerPresent()` | 检测 kernel 调试器 |
| 3 | 调试端口 | `NtQueryInfo(ProcessDebugPort=7)` | != -1 为未调试 |
| 4 | 调试对象句柄 | `NtQueryInfo(ProcessDebugObjectHandle=30)` | 非空被调试 |
| 5 | 调试标志 | `NtQueryInfo(ProcessDebugFlags=31)` | 0 = 被调试 |
| 6 | Hide From Debugger | `NtSetInfoThread(HideFromDebugger=0x11)` | 线程对调试器不可见 |
| 7 | 硬件断点检测 | `GetThreadContext(DR0-DR3)` | DR 非零 = 有 HWBP |
| 8 | 时间差攻击 | `RDTSC` / `perf_counter` | 单步使代码变慢 |
| 9 | INT 2D 钻探 | `__int 0x2d` 指令 | 被调试时跳过，否则异常 |

## 验证结果 (Win11 24H2，无调试器)
```
[01/09] IsDebuggerPresent             → ✅ CLEAN
[02/09] CheckRemoteDebuggerPresent    → ✅ CLEAN
[03/09] ProcessDebugPort              → ✅ CLEAN
[04/09] DebugObjectHandle             → ✅ CLEAN
[05/09] ProcessDebugFlags             → ✅ CLEAN
[06/09] HideFromDebugger              → ✅ OK (no debugger)
[07/09] PEB direct read (DR regs)     → ✅ No HW breakpoints
[08/09] Timing check (10.76ms)        → ✅ normal
[09/09] INT 2D drill                  → (conceptual)
```

## Win11 24H2 关键发现

**`NtQueryInformationProcess` 在 Win11 24H2+ 被阻止！**
- `ProcessBasicInformation(0)` 返回 `STATUS_ACCESS_DENIED (-0x3ffffff8)`
- 所有 info class 均被阻止
- 这是微软的新安全策略：阻止用户态调用内核调试信息
- **反过来说：NtQueryInformationProcess 返回 STATUS_ACCESS_DENIED 本身就是被调试的迹象！**

### 华为/360 等安全软件检测方式
```
1. 先调 NtQueryInformationProcess → 如果返回 ACCESS_DENIED
   → 说明系统可能被调试（因为正常系统允许）
   
2. 检查 DR 寄存器（GetThreadContext）
   → 如果 DR0-DR3 非 0 或 DR7 使能
   → 说明有硬件断点

3. 时间差检测（RDTSC 对比）
   → 单步执行时，两条指令间的时钟周期 > 300
```

## 反反调试 (Anti-Anti-Debug)

### PEB BeingDebugged Patch (最常用)
```c
// C 语言版本
PPEB peb = (PPEB)__readgsqword(0x60);
peb->BeingDebugged = 0;

// 之后所有 IsDebuggerPresent() 返回 FALSE
```

### 完整对抗链
```
调试器设置 HWBP → 应用检测 DR → 调试器清除 DR
    ↓                                        ↓
调试器设置 PEB → 应用检测 PEB → PEB patch (NtContinue)
    ↓                                        ↓
调试器设 NtQIP hook → 应用调 NtQIP → 直接 syscall
    ↓                                        ↓
调试器设 int3 trap → 应用设 VEH → INT 2D/CC 自行处理
```

## 下节 (re_11) 计划
- 结构化异常处理 (SEH) / 向量化异常处理 (VEH)
- VEH 作为反调试：拦截 EXCEPTION_BREAKPOINT
- 自己捕获断点实现软断点 (是调试器也是反调试)

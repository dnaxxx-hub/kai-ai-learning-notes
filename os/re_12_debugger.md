# 逆向工程 — 第十二课：完整调试器核心整合

## 整合的 8 个模块 (re_05 ~ re_11)

| 模块 | 源课程 | 功能 |
|------|--------|------|
| DebugActiveProcess 附着 | re_04 | `DebugActiveProcess(pid)` + 进程句柄 |
| 软件断点 (0xCC) | re_05 | `WriteProcessMemory(addr, b"\xcc")` + 原始字节保存 |
| 硬件断点 (DR0-DR7) | re_07 | `SetThreadContext(DR0-DR3)` + DR7 位编码 |
| 反汇编引擎 | re_06 | capstone 反汇编 (可插拔) |
| VEH 异常拦截 | re_11 | `AddVectoredExceptionHandler` + 自捕 INT 3 |
| Detour Hook | re_08 | (预留接口) |
| 导出表解析 | re_09 | (预留接口) |
| 反调试检测 | re_10 | (预留接口) |

## 验证结果 (Self-debugging mode)

```
VEH installed: True
DebugBreak() → VEH 捕获 → RIP 前移 → 恢复执行
```

**断点触发后保存的寄存器快照：**

| 寄存器 | 值 | 意义 |
|--------|----|------|
| RIP | `0x7ff8df895a13` | DebugBreak 后的下一指令 (0xCC 已跳过) |
| RAX | `0x7ff8c3f44493` | kernel32 返回地址 |
| RSP | `0x65028deab8` | 栈指针 (正常范围内) |
| RBP | `0x65028deae0` | 栈基址 |
| EFlags | `0x246` | 中断启用 + IOPL=0 |

## 核心架构

```
                        DebugSession
                        ┌─────────────────────┐
                        │  target_pid         │
                        │  target_handle      │
                        │  swbps: dict[addr]  │
                        │  hwbps: dict[addr]  │
                        │  VEH handler        │
                        └──────┬──────────────┘
                               │
               ┌───────────────┼────────────────┐
               v               v                v
         Debug API          VEH (self)     Thread Context
         ┌──────────┐   ┌──────────────┐  ┌─────────────┐
         │Attach    │   │_veh_handler  │  │GetThreadCtx │
         │Detach    │   │Rip += 1      │  │SetThreadCtx │
         │WaitForEvt│   │save_ctx()    │  │DR0-DR7      │
         └──────────┘   └──────────────┘  └─────────────┘
         ┌──────────┐   ┌──────────────┐
         │set_swbp  │   │set_hwbp      │
         │remove_swbp│  │remove_hwbp   │
         │clear_all  │  │              │
         └──────────┘   └──────────────┘
```

## 断点处理流程

```
1. 目标进程执行到 0xCC → CPU 触发 EXCEPTION_BREAKPOINT
2. Windows 内核 → 用户态异常分发
3. VEH 回调 → _veh_handler() 拦截
   ├── 检查 ExceptionCode == 0x80000003
   ├── Context.Rip += 1 (跳过 0xCC)
   ├── 保存寄存器快照到 self.saved_ctx
   └── 返回 EXCEPTION_CONTINUE_EXECUTION (-1)
4. 调试器暂停等待用户输入
5. 用户: r(regs) / b(bps) / bp <addr> / q(uit)
6. 用户输入 q → detach + 停止
```

## 与商业调试器 (x64dbg/WinDbg) 差异

| 特性 | 本调试器 | x64dbg | WinDbg |
|------|---------|--------|--------|
| 进程附着 | ✅ | ✅ | ✅ |
| 软件断点 | ✅ | ✅ | ✅ |
| 硬件断点 | ✅ | ✅ | ✅ |
| 反汇编 | ⚠️ capstone 可插 | ✅ | ✅ |
| 单步 | ⚠️ TF 位 | ✅ (F7/F8) | ✅ |
| 表达式计算 | ❌ | ✅ | ✅ |
| 条件断点 | ❌ | ✅ | ✅ |
| 调用栈 | ❌ | ✅ (RtlVirtualUnwind) | ✅ |
| 符号解析 | ❌ | ✅ (PDB) | ✅ |
| 内存搜索 | ❌ | ✅ | ✅ |
| 断点导出/导入 | ❌ | ✅ | ✅ |

## 下节 (re_13) 计划
- 调用栈追踪：RtlVirtualUnwind + 栈帧遍历
- 符号解析：从 PDB 读取符号
- 条件断点：断点命中次数 + 条件判断

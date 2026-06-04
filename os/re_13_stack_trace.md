# 逆向工程 — 第十三课：调用栈追踪 (Stack Unwinding)

## 三种栈回溯方法

| # | 方法 | 原理 | 可靠性 | 实现难度 |
|---|------|------|--------|---------|
| 1 | RBP 链遍历 | `[RBP+0]=saved_RBP`, `[RBP+8]=ret_addr` | ❌ 优化编译后不可靠 | 低 |
| 2 | RtlVirtualUnwind | 使用 `.pdata` UNWIND_INFO 准确展开 | ✅ 最可靠 | 高 |
| 3 | EH 展开表 | 直接解析异常处理表 | ✅ 等同 #2 | 高 |

## Win64 栈帧结构

```
高地址
  ┌──────────────┐
  │ 参数溢出区    │ (caller 的第四个以上参数)
  ├──────────────┤
  │ 返回地址     │ ← RSP 指向 (被 CALL 压入)
  ├──────────────┤
  │ saved RBP    │ ← 如果保存了 RBP
  ├──────────────┤
  │ 局部变量     │
  ├──────────────┤
  │ 保存的寄存器 │ (非易失寄存器)
  ├──────────────┤
  │ 影子空间     │ (RCX,RDX,R8,R9 的 home zone)
  └──────────────┘
低地址 ← RSP
```

## Python 栈回溯 (traceback)

```
调用链: level3() → level2() → level1()
实际 Native 栈:

#0: re_13_stack_trace.py:368 in level1()
#1: re_13_stack_trace.py:365 in level2()
#2: re_13_stack_trace.py:362 in level3()
#3: re_13_stack_trace.py:378 in demo_trace_current()
#4: re_13_stack_trace.py:444 in <module>()

Native C 栈 (不可见):
  ctypes 包装层
  python3.dll / _ctypes.pyd
  ntdll!RtlUserThreadStart
```

## RtlLookupFunctionEntry 结果

| 函数地址 | 有 UNWIND_INFO？ | 说明 |
|----------|:----------------:|------|
| `kernel32!GetProcAddress` | ❌ | ctypes 返回的是转发指针，非直接导出 |
| `kernel32!GetModuleHandleW` | ❌ | 同上 |
| `kernel32!DebugBreak` | ❌ | 同上 |

> **为什么 ctypes 的 GetProcAddress 返回的地址没有 UNWIND_INFO？**
> 因为这些地址指向的是 `_ctypes.pyd` 模块中的 thunk/转发表，
> 不是 kernel32 的实际代码地址。真实 kernel32 函数的地址需要
> 通过 GetModuleHandle + LoadLibrary 原始地址计算。

## 符号解析 (DbgHelp API)

```
SymInitialize(process) → OK

SymsFromAddr(addr) → 需要 PDB 文件
SymGetLineFromAddr(addr) → 需要源文件 PDB

局限: 本机上可能没有 Python 的 .pdb。
生产环境中 DbgHelp + MSDIA 可从微软符号服务器下载 .pdb。
```

## RtlVirtualUnwind 完整展开循环

```python
RIP = current_RIP
while RIP != 0 and depth < 64:
    entry = RtlLookupFunctionEntry(RIP, &ImageBase, NULL)
    if entry:
        RtlVirtualUnwind(0, ImageBase, RIP, entry, &Context,
                         &HandlerData, &EstablisherFrame, NULL)
        RIP = Context.Rip  # = return address
        RSP = Context.Rsp  # = unwound stack
        frame_num += 1
        print(f"  #{frame_num}: {resolve(RIP)}")
    else:
        # Leaf function: return address is at [RSP]
        RIP = *(PULONG64)RSP
        RSP += 8
        frame_num += 1
```

## 下节 (re_14) 计划
- 内存搜索/扫描器
- 断点表达式/条件
- 断点命中计数

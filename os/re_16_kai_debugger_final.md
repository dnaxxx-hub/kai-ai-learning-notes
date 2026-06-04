# 逆向工程 — 第十六课：Kai Debugger 最终整合

## 课程路线图 16 课总览

| 课 | 主题 | 核心产出 |
|----|------|---------|
| 01 | 进程上下文 | psutil 进程枚举/遍历 |
| 02 | x86-64 汇编 | 寄存器/寻址速查 |
| 03 | PE 解析器 | 纯 Python PE 结构解析 |
| 04 | Windows 调试器 | DebugActiveProcess API |
| 05 | **软件断点** | 0xCC 注入 + 原始字节保存 |
| 06 | **反汇编引擎** | capstone 集成 + 智能断点 |
| 07 | **硬件断点** | DR0-DR7 寄存器编程 |
| 08 | Detour Hook | 5字节 JMP 重定向 |
| 09 | 导出表解析 | PE 导出表遍历/遍历 |
| 10 | 反调试 | NtQueryInfo, PEB flags |
| 11 | VEH/SEH | AddVectoredExceptionHandler |
| 12 | 调试器整合 | 进程附着 + 断点 + VEH |
| 13 | 栈回溯 | RBP链 + RtlVirtualUnwind + DbgHelp |
| 14 | 内存扫描 | VirtualQueryEx + 模式匹配 |
| 15 | 条件断点 | hit count + register expression |
| **16** | **Kai Debugger** | 全部整合 → 交互式调试器 |

## Kai Debugger 最终特性

```
KaiDebugger
├── .open(pid)             — 打开目标进程
├── .attach(pid)           — 打开 + 安装 VEH
├── .detach()              — 关闭进程句柄 + 移除 VEH
│
├── .add_bp(id, addr)      — 软件断点 (0xCC)
├── .add_hwbp(id, addr)    — 硬件断点
│   ├── hit_cond=">5"      — 命中断条件
│   ├── expr="RCX > 0"     — 寄存器条件
│   ├── log_msg="..."      — 日志模式 (不中断)
│   └── oneshot=True       — 单次断点
├── .remove_bp(id)
├── .save_bps(path)        — JSON 导出
├── .load_bps(path)        — JSON 导入
│
├── .scan_pattern(pattern) — 精确/通配符内存扫描
├── .scan_string(text)     — UTF-8/UTF-16 字符串扫描
├── .enum_regions()        — 枚举内存区域
│
├── .get_context()         — 寄存器快照
├── .disasm(addr)          — capstone 反汇编
│
└── .cmd_loop()            — 交互式命令循环
    ├── r/regs             → 显示寄存器
    ├── d/ds <addr>        → 反汇编
    ├── b/bps              → 列出断点
    ├── bp <id> <addr>     → 设置断点
    ├── bc <id>            → 移除断点
    ├── scan <str>         → 内存搜索
    ├── save/load          → 断点持久化
    └── q/quit             → 退出
```

## 验证结果

```
Self-test:
  VEH installed               ✓
  SWBP set @ kernel32!DebugBreak  ✓
  DebugBreak() → caught       ✓
  Context snapshot:
    RIP = 0x7ff8df895a13      ✓ (0xCC 已跳过)
    RAX = 0x7ff8c3f44493      ✓
    EFLAGS = 0x00000246       ✓
  Commands:
    r (regs)                  ✓ 完整寄存器输出
    b (breakpoints)           ✓ 显示断点列表
    q (quit)                  ✓ clean detach
```

## 核心实现细节

### 条件断点表达式求值
```python
# 安全 eval: 只暴露寄存器名作为变量
safe_env = {"RAX": ctx["Rax"], "RCX": ctx["Rcx"], ...,
            "and": lambda a,b: a and b, "or": ..., "not": ...,
            ">": lambda a,b: a > b, "==": ..., "!=": ...}
result = eval("RCX > 0 and RAX != 0", {"__builtins__": {}}, safe_env)
```

### VEH 上下文保存
```python
def _veh_callback(self, ep_ptr):
    ep = cast(ep_ptr, POINTER(_EXCEPTION_POINTERS)).contents
    ctx = ep.ContextRecord.contents
    if code == 0x80000003:  # EXCEPTION_BREAKPOINT
        ctx.Rip += 1  # 跳过 0xCC
        self.saved_ctx = {reg: getattr(ctx, reg) for reg in REG_NAMES}
        return -1     # CONTINUE_EXECUTION
```

### 内存扫描性能
- 精确扫描: `data.find(pattern)` — O(n) 单线程
- 掩码扫描: 逐字节匹配 mask — O(n × pattern_len)
- 优化: 每次 ReadProcessMemory 64KB (减少 API 调用 16x)

## 与其他调试器能力对比

| 能力 | Kai Debugger | x64dbg | WinDbg | 进度 |
|------|:------------:|:------:|:------:|:----:|
| 进程附着 | ✅ | ✅ | ✅ | re_04 |
| 软件断点 | ✅ | ✅ | ✅ | re_05 |
| 反汇编 | ✅ (capstone) | ✅ | ✅ | re_06 |
| 硬件断点 | ✅ (DR0-3) | ✅ | ✅ | re_07 |
| API HOOK | ✅ (detour) | ✅ | ✅ | re_08 |
| 导出表 | ✅ | ✅ | ✅ | re_09 |
| 反调试检测 | ✅ | ✅ | ✅ | re_10 |
| VEH 自捕 | ✅ | ✅ | ⚠️ | re_11 |
| 断点条件 | ✅ (hit+expr) | ✅ | ✅ | re_15 |
| 内存扫描 | ✅ | ✅ | ✅ | re_14 |
| 栈回溯 | ⚠️ (概念) | ✅ | ✅ | re_13 |
| GUI | ❌ | ✅ | ✅ | — |
| 符号服务器 | ❌ | ✅ | ✅ | — |
| 脚本化 | ✅ (Python) | ✅ (x64dbgpy) | ✅ (JS) | — |

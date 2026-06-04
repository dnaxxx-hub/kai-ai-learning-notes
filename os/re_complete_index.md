# 逆向工程完整知识体系索引

> 16 课完整学习路线 — 从体系结构到交互式调试器
> 创建时间: 2026-05-19 | 总方向: #25 体系结构与逆向工程

---

## 课程总览

| 课号 | 主题 | 核心产出 | 代码模块 | 关联课程 |
|------|------|----------|----------|----------|
| **01** | 进程上下文与 EPROCESS | 进程分析工具 | `re_01_process_layout.py` | — |
| **02** | x86-64 寄存器与汇编 | 寄存器速查 + 调用约定 | 笔记 + capstone demo | — |
| **03** | PE 文件格式深度解析 | 纯 Python PE 解析器 | `re_03_pe_parser.py` | re_09 |
| **04** | Windows Debug API 调试器 | 最小调试器 (attach + debug loop) | `re_04_debugger.py` | re_05, re_12 |
| **05** | 软件断点 + 远程内存 | 0xCC 注入 + 内存读写 | `re_05_bp_full.py` / `re_05_bp_mem.py` | re_04, re_06 |
| **06** | 反汇编引擎集成 | Capstone 集成 + 智能断点 | `re_06_disasm_bp.py` | re_05, re_07 |
| **07** | 硬件断点 (DR0-DR7) | 调试寄存器编程 | `re_07_hwbp.py` / `re_07_hwbp_v2.py` | re_06, re_10 |
| **08** | Detour Hook + 代码注入 | 12 字节 x64 跳板 + Trampoline | `re_08_inject_hook.py` | re_05, re_09 |
| **09** | PE 导出表解析 | 三表手工遍历 (Names/Ordinals/Functions) | `re_09_export_parser.py` | re_03 |
| **10** | 反调试 + 反反调试 | 9 种反调试技术 + 对抗链 | `re_10_anti_debug.py` | re_07, re_11 |
| **11** | SEH / VEH 异常处理 | VEH 自捕 INT 3 + PAGE_GUARD | `re_11_veh.py` | re_10, re_12 |
| **12** | 调试器核心整合 | 8 模块整合 (DebugSession) | `re_12_debugger.py` | re_04~re_11 |
| **13** | 调用栈追踪 | RBP 链 + RtlVirtualUnwind + DbgHelp | `re_13_stack_trace.py` | re_12 |
| **14** | 内存扫描器 | VirtualQueryEx + 模式匹配 / 字符串 | `re_14_mem_scan.py` | re_12 |
| **15** | 条件断点 | BreakpointManager + hit count + expr | `re_15_cond_bp.py` | re_12, re_13 |
| **16** | Kai Debugger 最终整合 | 交互式调试器 (全部 16 课技术) | `re_16_kai_debugger_final.py` | re_01~re_15 |

---

## 知识体系分层

### Layer 1: 计算机体系结构
```
硬件层 (CPU/Memory/MMU)
  ├── 进程抽象 ──────────────────────────── re_01
  │   ├── EPROCESS / PCB / PEB
  │   ├── 上下文切换 (TLB flush 代价)
  │   └── 虚拟地址空间布局
  │
  ├── 汇编层 ────────────────────────────── re_02
  │   ├── x86-64 寄存器模型 (16个通用寄存)
  │   ├── 7 种寻址模式 (立即/寄存/直接/基址/索引/RIP相对)
  │   ├── 常用指令集 (mov/push/call/jcc/lea/xor)
  │   ├── Windows x64 调用约定 (RCX/RDX/R8/R9)
  │   └── 栈帧结构 (影子空间 + 非易失寄存保存)
  │
  └── PE 文件格式 ───────────────────────── re_03
      ├── DOS Header → e_lfanew → PE Signature
      ├── IMAGE_FILE_HEADER (machine/sections/timestamp)
      ├── Optional Header (PE32 vs PE32+)
      ├── Data Directories (导入/导出/资源/重定位)
      └── Section Headers (.text/.data/.rdata/.idata/.reloc)
```

### Layer 2: 动态调试基础
```
调试引擎
  ├── Windows Debug API ──────────────────── re_04
  │   ├── DebugActiveProcess(pid)
  │   ├── WaitForDebugEvent(&event)
  │   ├── ContinueDebugEvent (DBG_CONTINUE / NOT_HANDLED)
  │   └── Debug Event 循环 (CREATE_PROCESS/EXCEPTION/EXIT)
  │
  ├── 软件断点 (INT 3) ───────────────────── re_05
  │   ├── 0xCC 注入 + 原始字节保存
  │   ├── ReadProcessMemory / WriteProcessMemory
  │   ├── VirtualProtectEx (内存保护修改)
  │   ├── FlushInstructionCache (指令缓存刷新)
  │   └── DEBUG_PROCESS 启动标志
  │
  ├── 反汇编引擎 ─────────────────────────── re_06
  │   ├── Capstone (CS_ARCH_X86, CS_MODE_64)
  │   ├── RIP 调整 (INT3 命中后 RIP-1)
  │   ├── MSVC Hotpatch (5-8 个 int3 前缀)
  │   └── GS Cookie 检测 (__security_cookie)
  │
  └── 硬件断点 (DR0-DR7) ────────────────── re_07
      ├── DR0-DR3: 断点地址寄存器
      ├── DR7: 控制寄存器 (L/G enable + R/W type + LEN)
      ├── DR6: 状态寄存器 (命中后**手动清零**)
      ├── 3 种触发类型 (EXECUTE/WRITE/READWRITE)
      ├── 4 种长度 (1/2/4/8 bytes)
      └── 线程局部性 (L flag vs G flag)
```

### Layer 3: 高级注入与解析
```
代码操纵
  ├── Detour Hook ────────────────────────── re_08
  │   ├── x64 12 字节跳板 (mov rax, addr; jmp rax)
  │   ├── Trampoline (备份指令 + 跳回)
  │   ├── VirtualAllocEx (远程 RWX 分配)
  │   ├── CreateRemoteThread (远程线程执行)
  │   └── DLL Injection (LoadLibraryW 远程调用)
  │
  ├── PE 导出表解析 ──────────────────────── re_09
  │   ├── IMAGE_EXPORT_DIRECTORY 结构
  │   ├── 三表体系: Names → Ordinals → Functions
  │   ├── DataDirectory[0] 定位
  │   └── kernel32 1693 个函数完整遍历
  │
  └── 反调试技术 ─────────────────────────── re_10
      ├── PEB.BeingDebugged (IsDebuggerPresent)
      ├── NtQueryInformationProcess (Port/Handle/Flags)
      ├── HideFromDebugger (NtSetInformationThread)
      ├── 调试寄存器检测 (GetThreadContext DR)
      ├── 时间差攻击 (RDTSC)
      ├── INT 2D 钻探
      └── 反反调试: PEB patch + VEH + syscall
```

### Layer 4: 异常处理与调试器整合
```
异常架构
  ├── VEH / SEH ──────────────────────────── re_11
  │   ├── AddVectoredExceptionHandler (全局最高优先级)
  │   ├── INT 3 自捕 (RIP += 1 跳过 0xCC)
  │   ├── VEH 反调试 (调试器先拦截则 VEH 收不到)
  │   ├── EFLAGS.TF 单步追踪
  │   └── PAGE_GUARD 内存断点
  │
  ├── 调试核心整合 ───────────────────────── re_12
  │   ├── DebugSession 类 (open/attach/detach)
  │   ├── SWBP + HWBP 统一管理
  │   ├── VEH 回调 + 上下文保存
  │   └── 命令循环 (r/d/b/bp/q)
  │
  ├── 调用栈追踪 ─────────────────────────── re_13
  │   ├── RBP 链遍历 (简单但不可靠)
  │   ├── RtlVirtualUnwind (.pdata UNWIND_INFO)
  │   ├── RtlLookupFunctionEntry (CFG 解析)
  │   └── DbgHelp SymFromAddr (PDB 符号)
  │
  ├── 内存扫描 ───────────────────────────── re_14
  │   ├── VirtualQueryEx 内存区域枚举
  │   ├── 精确字节扫描 + 通配符模式
  │   ├── 字符串扫描 (UTF-8/16)
  │   └── 64KB 块读取优化 (减少 API 调用 16x)
  │
  └── 条件断点 ───────────────────────────── re_15
      ├── BreakpointManager 架构
      ├── 命中条件 (hit>N / hit>=N / hit==N / once)
      ├── 寄存器表达式 (RCX > 0 and RAX != 0)
      ├── 日志模式 (不中断仅记录)
      ├── 分组管理 (批量禁用/启用)
      └── JSON 持久化 (save/load)
```

### Layer 5: 最终交付
```
Kai Debugger ────────────────────────────── re_16
  ├── .open(pid) / .attach(pid) / .detach()
  ├── .add_bp() / .add_hwbp() / .remove_bp()
  ├── .save_bps() / .load_bps()  (JSON)
  ├── .scan_pattern() / .scan_string()
  ├── .enum_regions() / .get_context()
  ├── .disasm(addr) — capstone 反汇编
  └── .cmd_loop() — 交互式命令循环
      ├── r/regs       → 寄存器快照
      ├── d/ds <addr>  → 反汇编
      ├── b/bps        → 断点列表
      ├── bp <id> <addr> → 设置断点
      ├── bc <id>      → 移除断点
      ├── scan <str>   → 内存搜索
      ├── save/load    → 断点持久化
      └── q/quit       → 退出
```

---

## 技术栈对照

| 技术 | 课程覆盖 | 用途 |
|------|----------|------|
| Windows Debug API | re_04, re_05 | 进程附着/调试循环/内存读写 |
| ctypes (Python) | 全部 | Win32 API 调用桥接 |
| Capstone | re_06, re_12 | x86-64 反汇编引擎 |
| VirtualQueryEx | re_14 | 内存区域枚举 |
| CreateRemoteThread | re_08 | 远程代码执行 |
| VEH (VectoredExceptionHandler) | re_11, re_12, re_16 | 自捕异常/断点回调 |
| RtlVirtualUnwind | re_13 | 栈帧展开/回溯 |
| DbgHelp | re_13 | 符号解析 |
| NtQueryInformationProcess | re_10 | 反调试检测 |

---

## API 依赖图谱

```
re_01 ── psutil (进程枚举/上下文)
re_02 ── capstone (反汇编 demo)
re_03 ── struct (纯 PE 解析)
re_04 ── kernel32 (DebugActiveProcess/WaitForDebugEvent)
re_05 ── kernel32 (ReadProcessMemory/WriteProcessMemory/VirtualProtectEx/FlushInstructionCache)
re_06 ── capstone + re_05
re_07 ── kernel32 (GetThreadContext/SetThreadContext)
re_08 ── kernel32 (VirtualAllocEx/WriteProcessMemory/CreateRemoteThread)
re_09 ── struct (纯 PE 导出表解析)
re_10 ── kernel32 + ntdll
re_11 ── kernel32 (AddVectoredExceptionHandler)
re_12 ── re_04~re_11 全部
re_13 ── kernel32 + ntdll + dbghelp
re_14 ── kernel32 (VirtualQueryEx/ReadProcessMemory)
re_15 ── re_12 断点管理
re_16 ── re_01~re_15 全部
```

---

## 调试器能力对比 (Kai Debugger vs 商业调试器)

| 能力 | Kai Debugger | x64dbg | WinDbg |
|------|:------------:|:------:|:------:|
| 进程附着 | ✅ | ✅ | ✅ |
| 软件断点 (0xCC) | ✅ | ✅ | ✅ |
| 硬件断点 (DR0-DR3) | ✅ | ✅ | ✅ |
| 反汇编 (capstone) | ✅ | ✅ | ✅ |
| API HOOK (detour) | ✅ | ✅ | ✅ |
| PE 导出表解析 | ✅ | ✅ | ✅ |
| 反调试检测 | ✅ | ✅ | ✅ |
| VEH 自捕 | ✅ | ✅ | ⚠️ |
| 条件断点 (hit+expr) | ✅ | ✅ | ✅ |
| 内存扫描 | ✅ | ✅ | ✅ |
| 栈回溯 | ⚠️ 概念实现 | ✅ | ✅ |
| 断点持久化 (JSON) | ✅ | ✅ | ✅ |
| GUI | ❌ | ✅ | ✅ |
| 符号服务器 (PDB) | ❌ | ✅ | ✅ |
| 脚本化 | ✅ Python | ✅ x64dbgpy | ✅ JS |

---

## 前置知识要求

- **必选**: Python (ctypes, struct, json), 基本 C 概念
- **推荐**: Windows 系统编程基础, 汇编基础知识
- **可选**: C/C++ 异常处理, 编译原理 (PE 格式)

---

## 代码模块清单 (18 个文件)

```
memory/learning/code/
├── re_01_process_layout.py         — 进程分析工具
├── re_03_pe_parser.py              — PE 文件解析器 (DOS/PE/Optional/Sections)
├── re_04_debugger.py               — 最小调试器 (attach + debug loop)
├── re_05_bp_full.py                — 软件断点完整实现 (0xCC)
├── re_05_bp_mem.py                 — 远程内存读写 demo
├── re_05c_simple_debug.py          — 简化调试器
├── re_05b_launch_debug.py          — DEBUG_PROCESS 启动
├── re_06_disasm_bp.py              — capstone 反汇编 + 智能断点
├── re_07_hwbp.py                   — 硬件断点 v1
├── re_07_hwbp_v2.py                — 硬件断点 v2 (改进版)
├── re_08_inject_hook.py            — Detour Hook + DLL Injection
├── re_09_export_parser.py          — PE 导出表解析
├── re_10_anti_debug.py             — 反调试检测套件 (9 种)
├── re_11_veh.py                    — VEH 异常处理 + 自捕
├── re_12_debugger.py               — 调试器核心整合
├── re_13_stack_trace.py            — 调用栈追踪
├── re_14_mem_scan.py               — 内存扫描器
├── re_15_cond_bp.py                — 条件断点管理器
└── re_16_kai_debugger_final.py     — 最终交付 (全部整合)
```

---

## 配套工具模块

- `code/re_pe_lifecycle.py` — PE 文件加载/导入表/节区深度分析
- `code/re_debugger_bridge.py` — Win32 调试 API 交互框架

> 详见配套代码模块文件。

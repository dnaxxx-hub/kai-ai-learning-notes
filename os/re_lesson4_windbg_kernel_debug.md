# 第4课：Windows 内核调试 — WinDbg 深度实战

## 一、WinDbg 基础架构

### 1.1 调试引擎（DbgEng）
```
WinDbg 架构:
┌─────────────────────────────────────────┐
│            WinDbg (GUI)                 │
├─────────────────────────────────────────┤
│      CDB (控制台) / NTSD (远程)         │
├─────────────────────────────────────────┤
│         DbgEng.dll (调试引擎)            │
├─────────────────────────────────────────┤
│      dbghelp.dll / symsrv.dll           │
│  (符号处理 / 符号服务器)                 │
├─────────────────────────────────────────┤
│       Windows 调试内核 (KD)              │
└─────────────────────────────────────────┘
```

### 1.2 调试模式
| 模式 | 连接方式 | 场景 |
|------|----------|------|
| 本地内核调试 | `WinDbg -kl` | 本地分析内核（只读） |
| 远程内核调试 (串口) |  COM 口直连 | 经典双机调试 |
| 远程内核调试 (网络) |  `kdnet` | Win8+ 推荐方式 |
| 远程内核调试 (USB) |  USB 3.0 直连 | Win8+ 高速调试 |
| 用户态调试 |  `WinDbg -pn notepad.exe` | 附带进程 |
| 用户态调试 |  `WinDbg notepad.exe` | 启动并调试 |
| 用户态调试 |  `.childdbg 1` | 调试子进程 |

### 1.3 符号配置
```
# 环境变量
_SET_NT_SYMBOL_PATH=srv*c:\symbols*https://msdl.microsoft.com/download/symbols

# WinDbg 命令
.sympath srv*c:\symbols*https://msdl.microsoft.com/download/symbols
.sympath+ c:\myapp\symbols    # 追加本地符号路径
.reload                       # 重新加载符号
.reload /f ntoskrnl.exe       # 强制加载内核符号
ld *                           # 加载所有模块的符号
ld nt                          # 仅加载 nt 模块符号
```

---

## 二、内核调试命令速查

### 2.1 断点操作

| 命令 | 说明 | 示例 |
|------|------|------|
| `bp` | 设置断点 | `bp nt!NtCreateFile` |
| `bu` | 未解析断点（模块加载时生效） | `bu mydriver!DriverEntry` |
| `bm` | 通配符断点 | `bm mydriver!*Create*` |
| `bl` | 列出所有断点 | `bl` |
| `bc` | 清除断点 | `bc 1`（清除1号断点） |
| `bd` | 禁用断点 | `bd 2` |
| `be` | 启用断点 | `be 2` |
| `br` | 设置硬件断点 | `br 0 0xfffff800` |
| `.bpcmds` | 显示断点的命令形式 | `.bpcmds` |

**条件断点示例:**
```
bp nt!NtCreateFile "!process 0 0; gc"   # 命中时打印进程信息
bp mydriver!MyFunc "r @$t0 = @@c++(poi(@esp+8)); .if (@$t0 > 0x100) {} .else {gc}"  # 条件跳过
```

### 2.2 内存操作

| 命令 | 说明 | 示例 |
|------|------|------|
| `db` | 显示字节（+ASCII） | `db nt!CiInitialize 50` |
| `dw` | 显示 WORD (2字节) | `dw ffffe000` |
| `dd` | 显示 DWORD (4字节) | `dd ffffe000 L10` |
| `dq` | 显示 QWORD (8字节) | `dq ffffe000 L8` |
| `dc` | 显示 DWORD + ASCII | `dc nt!CmpCmdLExecute` |
| `ds` | 显示字符串 | `ds ffffe000` |
| `dS` | 显示 UNICODE_STRING | `dS poi(nt!PsActiveProcessHead)` |
| `da` | 显示 ASCII 字符串 | `da ffffe000` |
| `du` | 显示 Unicode 字符串 | `du ffffe000` |
| `e{b/w/d/q}` | 编辑内存 | `eb ffffe000 90 90 90` |
| `s` | 搜索内存 | `s -u ffffe000 L1000 "Hello"` |
| `!address` | 查看内存区域信息 | `!address ffffe000` |
| `!vad` | 显示 VAD (虚拟地址描述符) | `!vad ffffe000` |
| `!pte` | 显示页表项 | `!pte ffffe000` |

### 2.3 寄存器操作

| 命令 | 说明 | 示例 |
|------|------|------|
| `r` | 显示/修改寄存器 | `r; r eax=1234` |
| `rm` | 显示浮点/MMX 寄存器 | `rm` |
| `.formats` | 显示值的各种格式 | `.formats eax` |

**x64 寄存器一览:**
```
通用: RAX, RBX, RCX, RDX, RSI, RDI, RBP, RSP, R8-R15
段: CS, DS, ES, FS, GS, SS
FLAGS: EFL (RFLAGS)
指令: RIP
调试: DR0-DR7
```

### 2.4 反汇编

| 命令 | 说明 | 示例 |
|------|------|------|
| `u` | 反汇编 | `u nt!NtCreateFile` |
| `ub` | 向后反汇编 | `ub rip L20` |
| `.fnent` | 显示函数入口信息 | `.fnent mydriver!MyFunc` |
| `wt` | 监视并跟踪（Watch Trace） | `wt mydriver!MyFunc` |

### 2.5 栈回溯

| 命令 | 说明 | 示例 |
|------|------|------|
| `k` | 显示调用栈 | `k` |
| `kb` | 显示调用栈+前三个参数 | `kb` |
| `kp` | 显示调用栈+所有参数 | `kp` |
| `kn` | 显示调用栈（带帧号） | `kn` |
| `dds` | 栈上的符号转储 | `dds esp L20` |
| `.frame` | 切换到指定帧 | `.frame 3` |
| `.f+` / `.f-` | 上下切换帧 | `.f+` |

---

## 三、内核分析核心技巧

### 3.1 关键内核扩展
| 命令 | 说明 |
|------|------|
| `!process 0 0` | 列出所有进程 |
| `!process 0 7` | 列出进程详细 (句柄/线程/模块) |
| `!process <EPROCESS> 7` | 指定进程详情 |
| `!thread` | 显示当前线程 |
| `!thread <ETHREAD>` | 指定线程详情 |
| `!peb` | 显示 PEB |
| `!teb` | 显示 TEB |
| `!handle` | 句柄信息 |
| `!object` | 对象信息 |
| `!devobj` | 设备对象 |
| `!drvobj` | 驱动对象 |
| `!irp` | IRP 信息 |
| `!pool` | 内存池信息 |
| `!poolused` | 按标签查看池使用 |
| `!vm` | 虚拟内存统计 |
| `!pcr` | 处理器控制区 |
| `!apc` | APC 队列 |
| `!dpcs` | DPC 队列 |
| `!idt` | 中断描述符表 |
| `!gdt` | GDT 表 |
| `!sysinfo` | 系统信息 |
| `!qlock` | 队列自旋锁 |

### 3.2 内核数据访问
```
# 进程结构
dt nt!_EPROCESS
dt nt!_EPROCESS -b                     # 详细显示
dt nt!_EPROCESS ffffe000`12345678      # 查看具体地址的 EPROCESS
dt nt!_EPROCESS ImageFileName          # 只显示指定字段
dx -r0 @$cursession.Processes          # NatVis 方式（Win10 WinDbg）

# 内核模块
lm                                     # 列出已加载模块
lm v mydriver                          # 模块详细信息
lmi nt                                 # 模块版本/时间戳/大小
!lmi nt                                # 扩展版模块信息

# IRQL
!irql                                  # 显示当前 IRQL
```

### 3.3 调试技巧
```
# 写入断点时自动打印参数
bp nt!NtCreateFile "!process 0 0; kb; gc"

# 记录日志
.logopen c:\debug\session.log
.logclose

# 时间戳
!time                                 # 系统时间
!uptime                               # 运行时间
!dpcwatchdog                          # DPC 看门狗

# 内核钩子检测
!chkimg nt                             # 检查内核映像完整性
!search 90 90 90 90                    # 搜索 NOP slide

# 内核对象引用
!obtrace <ObjectAddress>               # 对象引用追踪
!htrace -enable                        # 启用句柄追踪
!htrace <HandleValue>                  # 追踪句柄
```

---

## 四、蓝屏分析实战

### 4.1 自动创建并分析内核转储
配置文件: `projects/arch_reverse/lesson4_kernel_debug/windbg_analyze_crash.ps1`

### 4.2 手动分析步骤
```
# 打开转储文件
WinDbg -z C:\Windows\MEMORY.DMP

# 第一步：检查崩溃概要
!analyze -v

# 第二步：查看错误码
!error <BugCheckCode>

# 第三步：查看栈回溯
k
kbn

# 第四步：检查驱动
lm
lm t n

# 第五步：检查故障模块
!analyze -show <故障地址>

# 第六步：查看参数
.formats arg1
.formats arg2
```

### 4.3 常见 BugCheck 代码
| BugCheck | 名称 | 常见原因 |
|----------|------|----------|
| 0x0A | IRQL_NOT_LESS_OR_EQUAL | 中断请求级别错误 |
| 0x1A | MEMORY_MANAGEMENT | 内存管理错误 |
| 0x1E | KMODE_EXCEPTION_NOT_HANDLED | 内核模式未处理异常 |
| 0x3B | SYSTEM_SERVICE_EXCEPTION | 系统服务异常 |
| 0x50 | PAGE_FAULT_IN_NONPAGED_AREA | 分页错误 |
| 0x7F | UNEXPECTED_KERNEL_MODE_TRAP | 意外内核陷阱 |
| 0xD1 | DRIVER_IRQL_NOT_LESS_OR_EQUAL | 驱动IRQL错误 |
| 0x109 | CRITICAL_STRUCTURE_CORRUPTION | 关键结构损坏 |
| 0x133 | DPC_WATCHDOG_VIOLATION | DPC看门狗违规 |
| 0x139 | KERNEL_SECURITY_CHECK_FAILURE | 内核安全检查失败 |

### 4.4 分析示例脚本
```windbg
$$ 自动分析转储文件
$$ 使用方法: WinDbg -z <dumpfile> -c "$$><c:\scripts\auto_analyze.txt"

!analyze -v
.logopen c:\crash_analysis.log
kbn
lm t n
!process 0 0
.thread /p /r
!vm
.logclose
q
```

---

## 五、文件系统过滤驱动调试

### 5.1 常用断点
```
# 文件操作拦截
bp nt!NtCreateFile
bp nt!NtReadFile
bp nt!NtWriteFile
bp nt!NtClose

# 注册表操作拦截
bp nt!NtOpenKey
bp nt!NtCreateKey
bp nt!NtSetValueKey
bp nt!NtQueryValueKey

# 进程/线程操作
bp nt!NtCreateProcess
bp nt!NtCreateThreadEx
bp nt!NtTerminateProcess

# 网络操作
bp nt!NtDeviceIoControlFile (配合 AFD 驱动)
```

---

## 六、实用场景命令集

### 6.1 检测 Rootkit
```
!process 0 0                                   # 列出所有进程
!drvobj                                        # 列出驱动
!chkimg -d nt                                  # 检查内核代码完整性
!search nt!ExAllocatePoolWithTag               # 搜索特定地址引用
s -d nt L<size> ffffffff`80000000              # 搜索驱动对象指针
!ssdt                                         # 显示 SSDT
!sd                                                    # 检查系统描述符
!pfn                                          # 物理帧号信息
!memusage                                     # 内存使用统计
```

### 6.2 进程保护/隐藏检测
```
# 列出所有进程节点对比
!process 0 0
!object \Windows\System32                       # 列出目录对象

# 枚举进程 EPROCESS 双向链表
!list -x "dt nt!_EPROCESS ImageFileName" nt!PsActiveProcessHead
```

### 6.3 键盘记录器检测
```
!idt                                         # 检查 IDT 钩子
!ghandle -p <PID>                             # 进程句柄表
!object \Device\KeyboardClass0               # 键盘设备
```

---

## 七、WinDbg 脚本编程

### 7.1 基础脚本语法
```
$$ 注释
$$ $t0-$t19 用户变量（32位）
$$ $t20-$t39 用户变量（64位）
r @$t0 = poi(nt!PsActiveProcessHead)          # 赋值
.printf "Process: %y\n", @$t0                 # 格式化打印
.block { ... }                                # 代码块
as {alias} {value}                            # 设置别名
ad {alias}                                    # 删除别名
```

### 7.2 遍历进程列表脚本
```
$$ walk_processes.txt
r @$t0 = poi(nt!PsActiveProcessHead)
r @$t1 = @$t0

.block {
    r @$t1 = poi(@$t1 + 0x2e0)               # ActiveProcessLinks.Flink (偏移因版本而异)
    .while (@$t1 != @$t0) {
        dt nt!_EPROCESS ImageFileName @$t1 -0x2e0
        r @$t1 = poi(@$t1)
    }
}
```

---

## 八、自动化脚本项目

详见配套代码项目:
- `projects/arch_reverse/lesson4_kernel_debug/windbg_cmd_manual.ps1` — WinDbg 命令手册自动化
- `projects/arch_reverse/lesson4_kernel_debug/minidump_analyzer.py` — 小型转储分析器

---

## 参考资料
- [WinDbg 官方文档](https://docs.microsoft.com/en-us/windows-hardware/drivers/debugger/)
- 《Windows Internals 7th Edition》— Pavel Yosifovich
- 《Rootkits: Subverting the Windows Kernel》— Greg Hoglund
- [MSDN Bug Check Code Reference](https://docs.microsoft.com/en-us/windows-hardware/drivers/debugger/bug-check-code-reference-2)

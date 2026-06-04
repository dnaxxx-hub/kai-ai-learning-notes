# RE Summary：逆向工程 16 课总结

> 从二进制到系统内核，从静态分析到动态调试，这是 16 课逆向工程课程的完整回顾。

---

## 一、完整路线图回顾

```
┌──────────────────────────────────────────────────────────────────────┐
│                    逆向工程 16 课路线图                                │
│                                                                      │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐                        │
│  │ 01 ELF  │ │ 02 PE  │ │ 03 汇编 │ │ 04 Win │  ← 基础篇            │
│  │ 文件    │ │ 文件   │ │ 分析   │ │ API    │                        │
│  └────────┘ └────────┘ └────────┘ └────────┘                        │
│                                                                      │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐                        │
│  │ 05    │ │ 06    │ │ 07 堆栈 │ │ 08    │  ← 动态篇               │
│  │ GDB   │ │ WinDbg│ │   溢出  │ │ IDA   │                          │
│  └────────┘ └────────┘ └────────┘ └────────┘                        │
│                                                                      │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐                        │
│  │ 09    │ │ 10    │ │ 11    │ │ 12    │  ← 加壳篇                │
│  │ 加壳   │ │ UPX   │ │ 脱壳   │ │ 虚拟化 │                          │
│  └────────┘ └────────┘ └────────┘ └────────┘                        │
│                                                                      │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐                        │
│  │ 13    │ │ 14    │ │ 15    │ │ 16    │  ← 内核篇                │
│  │ 内核   │ │ Rootkit│ │ FW/IO │ │ 总结   │                          │
│  │ 调试   │ │        │ │ 分析   │ │        │                          │
│  └────────┘ └────────┘ └────────┘ └────────┘                        │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心知识点精华（每课 2 句）

### 基础篇 (1-4)

| 课 | 标题 | 精华 |
|----|------|------|
| 01 | ELF 文件 | ELF 文件 = ELF Header + Program Headers (segments) + Section Headers (sections)。segment 决定运行时加载，section 决定链接与符号解析。 |
| 02 | PE 文件 | PE = DOS Header + PE Header + Section Table + Sections。关键结构：Import Table (IAT) 导入系统 API，Export Table 导出函数给其他模块用。 |
| 03 | 汇编分析 | x86/x64 汇编核心：数据传送 (mov)、算术 (add/sub)、调用 (call/ret)、条件跳转 (jcc)。PUSH/POP、栈帧 (ebp/rbp) 管理是理解函数调用的关键。 |
| 04 | Win32 API | Windows 系统调用通过 ntdll!Nt*/Zw* 进入内核。关键逆向 API：CreateToolhelp32Snapshot (遍历进程/模块)、ReadProcessMemory (跨进程读取)、SetWindowsHookEx (钩子注入)。 |

### 动态篇 (5-8)

| 课 | 标题 | 精华 |
|----|------|------|
| 05 | GDB | GDB 核心三板斧：`break` (断点)、`stepi`/`nexti` (单步)、`info registers`/`x/` (查看内存)。反编译用 `set disassembly-flavor intel` 切换到 Intel 语法。 |
| 06 | WinDbg | WinDbg 是 Windows 内核调试的黄金标准。`.breakin` 中断目标，`kb` 查看调用栈，`dt` 展开结构体，`!process 0 0` 列出所有进程。 |
| 07 | 堆栈溢出 | 栈溢出原理：覆盖返回地址 → 劫持 EIP/RIP。关键防御：ASLR (地址随机化)、DEP/NX (栈不可执行)、Stack Canary (栈保护)。 |
| 08 | IDA Pro | IDA 的 F5 反编译是逆向效率的关键。n 改名、y 改签名、x 交叉引用、; 加注释——IDA 八字诀。 |

### 加壳篇 (9-12)

| 课 | 标题 | 精华 |
|----|------|------|
| 09 | 加壳原理 | 加壳 = 压缩/加密原始 PE + 插入 stub。运行时行为：stub 解压/解密 → 修复 IAT → 跳转 OEP。入口特征：只有几条 PUSHAD + CALL/JMP。 |
| 10 | UPX | UPX 是最流行的开源壳。OEP 特征：解压循环后 POPAD + JMP。脱壳命令 `upx -d` 即可完成，定制版需手工 OEP 定位 + 转储 + IAT 重建。 |
| 11 | 手工脱壳 | 手工脱壳三步走：找 OEP (ESP 定律、内存断点) → 转储进程 (Scylla/LordPE) → 修复 IAT。ESP 定律 = 在 PUSHAD 后对 ESP 设硬件断点，一步直达 OEP。 |
| 12 | 虚拟化保护 | VMP/Themida 等虚拟化壳将原始 x86 翻译为私有 VM bytecode。分析方法：追踪 VM entry/exit、识别 VM dispatch 表、建立字节码到 x86 的映射。静态解虚拟化是困难问题。 |

### 内核篇 (13-16)

| 课 | 标题 | 精华 |
|----|------|------|
| 13 | 内核调试 | Windows 内核调试分本地和远程。内核对象 (EPROCESS/KPROCESS/ETHREAD) 是分析的基础。关键调试命令：`!process`、`!object`、`dt nt!_EPROCESS`。 |
| 14 | Rootkit | Rootkit = 内核级隐藏。SSDT Hook (修改系统服务表) 和 DKOM (直接内核对象操作) 是经典手法。检测方向：校验 SSDT 表、对比 Method 遍历进程。 |
| 15 | 固件驱动 | UEFI/ACPI/PCI 是设备交互的底层路径。IO 分析关注端口 (IN/OUT) 映射和 MMIO 寄存器。DMA 驱动可直接物理内存读写。 |
| 16 | 总结 | 逆向分析 = 文件结构理解 × 动态调试能力 × 系统知识积累。IDA/Ghidra/GDB/WinDbg 是最重要的四件武器，没有捷径，只有练习。 |

---

## 三、实操工具列表

### 静态分析
| 工具 | 用途 | 级别 |
|------|------|------|
| **IDA Pro** | 全能反汇编 + 反编译 | ★★★★★ |
| **Ghidra** | 免费替代品，SRE 框架 | ★★★★★ |
| **radare2 / rizin** | 命令行逆向框架 | ★★★★ |
| **Binary Ninja** | 现代化中间表示 (BNIL) | ★★★★ |
| **Cutter (rizin GUI)** | radare2 的可视化前端 | ★★★ |
| **Hiew** | 十六进制编辑器 + 汇编补丁 | ★★★ |

### 动态调试
| 工具 | 用途 | 级别 |
|------|------|------|
| **WinDbg** | Windows 用户态/内核态调试 | ★★★★★ |
| **GDB** | Linux 调试标配 | ★★★★★ |
| **x64dbg** | Windows 用户态调试，开源 | ★★★★ |
| **OllyDbg** | 元老级调试器，插件丰富 | ★★★ |
| **LLDB** | macOS/iOS 调试 | ★★★★ |
| **rr (Record and Replay)** | 确定性重放调试 | ★★★ |

### 脱壳与修复
| 工具 | 用途 | 级别 |
|------|------|------|
| **Scylla** | IAT 重建、脱壳转储 | ★★★★★ |
| **LordPE** | PE 编辑、进程转储 | ★★★★ |
| **ImportREC** | IAT 修复（经典） | ★★★★ |
| **x64dbg + Scylla plugin** | 现代脱壳工作流 | ★★★★★ |
| **unpac.me** | 在线自动脱壳（云分析） | ★★★ |

### 内存与内核
| 工具 | 用途 | 级别 |
|------|------|------|
| **Process Hacker** | 进程/线程/句柄管理 | ★★★★ |
| **Process Monitor (procmon)** | 文件/注册表/进程活动监控 | ★★★★★ |
| **API Monitor** | API 调用追踪 | ★★★★ |
| **Volatility** | 内存取证，分析内存转储 | ★★★★★ |
| **PCHunter / PowerTool** | 内核级信息查看 | ★★★★ |
| **WinObj** | 对象管理器命名空间查看 | ★★★ |
| **WinDbg + !analyze -v** | 蓝屏转储分析 | ★★★★★ |

### 固件与硬件
| 工具 | 用途 | 级别 |
|------|------|------|
| **UEFITool** | UEFI 固件镜像解析和编辑 | ★★★★ |
| **CHIPSEC** | 平台安全评估框架 | ★★★★ |
| **Binwalk** | 固件提取和分析 | ★★★ |
| **JTAG/SWD probes** | 硬件级调试接口 | ★★★★★ |

### 辅助工具
| 工具 | 用途 | 级别 |
|------|------|------|
| **YARA** | 恶意样本规则匹配 | ★★★★ |
| **FLOSS** | 字符串自动提取和反混淆 | ★★★ |
| **Kaitai Struct** | 二进制格式解析框架 | ★★★ |
| **PE-Bear / CFF Explorer** | PE 文件结构查看编辑 | ★★★★ |
| **HashMyFiles** | 文件哈希计算 | ★★ |

---

## 四、进阶方向建议

### 方向一：恶意软件分析
```
逆向基础 → 壳分析 → Rootkit → APT 样本分析
```
- 练习：分析真实恶意样本（VX Underground, Malware Bazaar）
- 必学：OllyDbg/x64dbg + IDA 联调
- 进阶：威胁狩猎、行为分析、沙箱开发

### 方向二：漏洞挖掘
```
汇编基础 → 栈/堆溢出 → 格式化字符串 → 内核漏洞
```
- 练习：CTF PWN 题目、CVE PoC 复现
- 必学：WinDbg 内核调试、GDB pwndbg/peda
- 进阶：Fuzzing (AFL/LibFuzzer)、Patch 分析、1-day 利用

### 方向三：软件保护与逆向
```
加壳原理 → VM 保护 → 代码混淆 → 安全架构
```
- 练习：分析 VMP/Themida/Obfuscator-LLVM
- 必学：符号执行 (Angr/Unicorn)、手工脱壳
- 进阶：自定义保护系统、反逆向工程

### 方向四：固件与硬件
```
汇编 → CPU 架构 → 固件分析 → 嵌入式
```
- 练习：分析 UEFI/BIOS/Bootloader
- 必学：UEFITool、binwalk、逻辑分析仪
- 进阶：固件漏洞利用、硬件 Hack (JTAG/SWD)

### 方向五：二进制程序分析
```
IR 理解 → 符号执行 → 污点分析 → 自动化解混淆
```
- 练习：用 Angr 做自动化漏洞发现
- 必学：中间表示 (BNIL/REIL/VEX)、约束求解器 (Z3)
- 进阶：程序分析的编译器视角、Type Recovery

---

## 五、推荐学习资源

**书籍**：
- 《Practical Binary Analysis》— 二进制分析入门
- 《The IDA Pro Book》— IDA 权威指南
- 《Windows Internals》— Windows 内核圣经
- 《Rootkits and Bootkits》— 内核安全经典
- 《A Guide to Kernel Exploitation》— 内核漏洞利用

**在线平台**：
- crackmes.one — 逆向练习题目
- pwnable.kr / pwnable.tw — 漏洞利用挑战
- root-me.org — 分类别逆向挑战
- microcorruption.com — 嵌入式逆向

**社区**：
- Reverse Engineering Stack Exchange
- r/ReverseEngineering (Reddit)
- 看雪论坛、吾爱破解
- OpenRE (Discord)

---

> **逆向工程是一门手艺。** 16 课只是起点，真正的技能来自日复一日的实战。每一个你反汇编的程序都在教你如何思考崩溃、内存和设计决策。继续拆解，保持好奇。

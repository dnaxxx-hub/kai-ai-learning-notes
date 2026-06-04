# 逆向工程 — 第六课：反汇编引擎集成 + 智能断点

## 核心能力
1. ✅ Capstone 反汇编引擎集成 — 64位 x86 指令完美反汇编
2. ✅ 软件断点 + RIP 调整 (INT3命中后 RIP-1)
3. ✅ 原始指令恢复 + 单步执行 + 重新设BP的三段式
4. ✅ 从 DEBUG_EVENT raw buffer 提取 ImageBase

## 验证结果
```
notepad.exe base=0x7ff7b39a0000
  PE @ 0xf8  MZ OK ✓

.text @ 0x7ff7b39a1000:
  int3  int3  int3  int3  int3      ← MSVC hotpatch
  int3  int3  int3                   ← 8个int3
  mov r11, rsp                      ← 真实函数入口
  sub rsp, 0x88
  mov rax, qword ptr [rip + 0x333e7]
  xor rax, rsp                      ← GS cookie (栈保护)
  ...

BP set @ 0x7ff7b39a1008 (orig=4c)  ✓
BP set @ 0x7ff7b39a1010 (orig=00)  ✓
BP set @ 0x7ff7b39a1020 (orig=70)  ✓
```

## 代码架构

```
启动进程(DEBUG_PROCESS)
  ↓ WaitForDebugEvent
CREATE_PROCESS → 提取ImageBase → OpenProcess
  ↓
读取PE头(MZ→PE) → 反汇编.text → 设断点
  ↓ WaitForDebugEvent
EXCEPTION(BREAKPOINT) → 反汇编@RIP-1 → 恢复原字节
  → SetRIP+TF标志 → ContinueDebugEvent(DBG_CONT)
  ↓ WaitForDebugEvent
EXCEPTION(SINGLE_STEP) → 反汇编@RIP → 重新设BP
```

## 关键发现

### MSVC Hotpatch 分析
notepad.exe 的 .text 开头有 **8个int3**（不是常见的5个）：
```
cc cc cc cc cc cc cc cc | 真实代码开始
```
Windows 热补丁系统需要 5 字节用于 `jmp [target]` 跳转，
额外 3 个 int3 是堆对齐。

### GS Cookie (栈保护)
```
mov rax, [rip+0x333e7]  ← 从.data读取security_cookie
xor rax, rsp            ← 与栈指针异或
mov [rsp+0x70], rax    ← 存储在栈上
```
这是 MSVC `/GS` 编译选项的安全 cookie — 函数返回前验证 cookie 是否被改写。

### Capstone 反汇编质量
完整识别了：int3, mov, sub, xor, and, mov dword, 等指令，
op_str 格式准确。延迟槽、RIP相对寻址全部正确。

## 下节 (re_07) 计划
- 硬件断点 (DR0-DR3 调试寄存器)
- 断点列表管理
- WinDbg/x64dbg 基础操作

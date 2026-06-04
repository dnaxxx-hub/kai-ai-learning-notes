# 体系结构与逆向 — 第二课：x86-64 汇编深潜

## 1. 寄存器模型

x86-64 在 32-bit 基础上扩展：
```
32-bit    64-bit    用途
───────────────────────────
EAX       RAX       累加器 / 返回值
EBX       RBX       基址
ECX       RCX       计数 / 循环
EDX       RDX       I/O / 数据
ESI       RSI       源索引
EDI       RDI       目标索引
ESP       RSP       栈指针
EBP       RBP       栈帧基址
EIP       RIP       指令指针
                    R8-R15   新增通用寄存器
```

## 2. 寻址模式 (x86-64)
```
立即数:    mov rax, 42
寄存器:    mov rax, rbx
直接:      mov rax, [addr]    内存地址
基址:      mov rax, [rbx]     寄存器指向的地址
基址+偏移:  mov rax, [rbx+8]
索引:      mov rax, [rbx+rcx*8]
RIP相对:   lea rax, [rip+offset]  位置无关代码
```

## 3. 常用指令速查
```
mov  src, dst    复制
push/pop         栈操作
call/ret         函数调用/返回
jmp/jcc          跳转 (je/jne/jg/jl/ja/jb)
cmp              比较
add/sub/mul/div  算术
and/or/xor/not   位运算
shl/shr          移位
lea              取有效地址
test             按位与测试 (同AND但不写结果)
```

## 4. Windows x64 调用约定
- RCX → 第1个参数
- RDX → 第2个参数
- R8  → 第3个参数
- R9  → 第4个参数
- 后接的压入栈 (从右到左)
- 调用者保存: RAX/RCX/RDX/R8-R11
- 被调用者保存: RBX/RBP/RSI/RDI/R12-R15

## 5. 栈帧结构
```
高地址
  [return address]   ← call指令自动压入
  [saved rbp]        ← push rbp
  [local var 1]      
  [local var 2]      ← rsp
低地址
```

## 6. 动手工具
安装 capstone (反汇编引擎) 后可以：
```python
import capstone
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
# 反汇编任意字节
for i in md.disasm(b"\x48\x89\x5c\x24\x08", 0x1000):
    print(f"0x{i.address:x}: {i.mnemonic} {i.op_str}")
```

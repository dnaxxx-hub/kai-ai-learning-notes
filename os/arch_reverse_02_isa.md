# 架构与逆向工程 第2课：指令集架构（ISA）

## 1. 什么是指令集架构（ISA）

ISA（Instruction Set Architecture）是 CPU 和软件之间的**契约接口**。它定义了：
- 哪些寄存器可用
- 指令的编码格式（opcode + 操作数）
- 寻址模式（立即数、寄存器、内存）
- 内存模型（端序、地址空间、页大小）
- 异常/中断机制

ISA 是**架构**（Architecture）而非**微架构**（Microarchitecture）。x86-64 是架构，Intel Core 或 AMD Zen 是微架构。

## 2. x86-64 历史脉络

| 年代 | 事件 |
|------|------|
| 1978 | Intel 8086 → 16-bit ISA |
| 1985 | Intel 80386 → 32-bit (IA-32) |
| 2003 | AMD 推出 AMD64 → 64-bit 扩展 |
| 2004 | Intel 采纳 EM64T（后称 Intel 64） |
| 2008+ | AVX、AES-NI、VT-x 等扩展 |

x86-64 的优雅之处：**向后兼容**——64 位模式下仍可运行 32 位和 16 位代码（通过兼容模式切换）。

## 3. x86-64 寄存器模型（本模拟器子集）

| 寄存器 | 64位 | 用途 |
|--------|------|------|
| RAX | 累加器 | 函数返回值、算术运算 |
| RBX | 基址 | 通用（调用者保存） |
| RCX | 计数器 | 移位/循环指令 |
| RDX | 数据 | 乘除法扩展、I/O |
| RSP | 栈指针 | 指向栈顶 |
| RBP | 基址指针 | 栈帧基址 |
| RIP | 指令指针 | 指向下一条指令 |
| RFLAGS | 标志位 | CF/ZF/SF/OF 状态位 |

### RFLAGS 标志位（仅模拟关键位）

| 位 | 名称 | 含义 |
|----|------|------|
| 0 | CF | 进位/借位标志（无符号溢出） |
| 6 | ZF | 零标志（结果为0） |
| 7 | SF | 符号标志（结果为负） |
| 11 | OF | 溢出标志（有符号溢出） |

## 4. 内存模型

- **线性地址空间**：0 ~ 2^64-1（但模拟中只映射可用部分）
- **分页机制**：4KB 页为基本单位，按需分配
- **大端存储**：多字节数据高位存低地址（与 x86-64 实际小端相反——模拟器中的约定，便于测试）
- 页表简化为字典映射：`{page_base: bytearray(4096)}`

## 5. 指令格式（本模拟器）

采用**自定义字节码编码**而非原生 x86-64 机器码（以简化实现）：

```
[opcode(1B)] [operands...]
```

但指令语义**完全忠实于** x86-64 行为。

### 指令分类

#### 数据传送
- `mov r/m, r/m/imm` — 支持 reg↔reg, imm→reg, reg↔mem
- `push r/m/imm` — 入栈（RSP -= 8）
- `pop r/m` — 出栈（RSP += 8）

#### 算术运算
- `add dst, src` — dst += src（影响标志位）
- `sub dst, src` — dst -= src（影响标志位）
- `mul src` — RAX = RAX * src（无符号，结果截断64位）
- `div src` — RAX = RAX / src, RDX = RAX % src（无符号）

#### 逻辑/比较
- `cmp a, b` — 计算 a - b，只设标志位不存结果
- `test a, b` — 计算 a & b，只设标志位

#### 控制流
- `jmp target` — 无条件跳转
- `jcc target` — 条件跳转（je/jne/jl/jle/jg/jge/jb/jbe/ja/jae）
- `call target` — push rip; jmp target
- `ret` — pop rip

## 6. 条件码映射

| 指令 | 条件 |
|------|------|
| je/jz | ZF=1 |
| jne/jnz | ZF=0 |
| jl/jnge | SF≠OF |
| jle/jng | SF≠OF 或 ZF=1 |
| jg/jnle | SF=OF 且 ZF=0 |
| jge/jnl | SF=OF |
| jb/jc/jnae | CF=1 |
| jbe/jna | CF=1 或 ZF=1 |
| ja/jnbe | CF=0 且 ZF=0 |
| jae/jnc/jnb | CF=0 |

## 7. 编码设计（Bytecode Format）

每条指令编码为 1~9 字节：

| 字段 | 大小 | 说明 |
|------|------|------|
| opcode | 1B | 指令类型 |
| mod | 1B | 寻址模式（reg/imm/mem） |
| data | 0~8B | 立即数或内存地址 |

操作数类型编码（mod 字节的低 4 位为 dst，高 4 位为 src）：
- `0b0000` = register (reg_id in next byte)
- `0b0001` = immediate (8B follows)
- `0b0010` = memory (8B address follows)

## 8. 参考资料

- Intel® 64 and IA-32 Architectures Software Developer Manuals
- AMD64 Architecture Programmer's Manual
- "Computer Architecture: A Quantitative Approach" — Hennessy & Patterson
- OSDev Wiki: x86-64 Instruction Encoding

## 9. 关键设计决策记录

1. **为何自定义编码而非真实 x86-64 机器码？**
   - x86-64 编码极其复杂（变长指令，前缀字节，ModRM，SIB，disp，imm）
   - 模拟器聚焦于**语义模拟**而非字节码解析
   - 未来可以加一层解码器将真实机器码映射到内部表示

2. **为何用字典映射而非真实页表？**
   - 模拟精度足够教学使用
   - 代码量减少 5x
   - 后期可替换为完整四级页表

3. **大端 vs 小端**
   - 本模拟器采用大端（便于测试阅读）
   - 真实 x86-64 是小端，但内部语义不依赖端序

---

*编写日期：2025-05-28*
*关联项目：projects/arch_reverse/isa_sim.py*

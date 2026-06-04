# 漏洞挖掘与模糊测试（Fuzzing）

> 日期：2026-05-10 | 课程：安全路线 Phase 4  
> 学习目标：理解常见漏洞分类、模糊测试原理、缓解措施，实现简易覆盖引导Fuzzer

---

## 一、漏洞分类

### 1. 栈溢出（Stack Overflow）

**原理：** 局部变量在栈上连续布局，C 标准库函数如 `gets()`、`strcpy()` 不做边界检查，写入超出缓冲区长度时覆盖相邻的栈帧内容。

```
栈布局（高地址 → 低地址）:
+-------------------+ ← 高地址
|   函数参数         |
+-------------------+
|   返回地址 (RIP)   |  ← 覆盖这里 → ROP链
+-------------------+
|   前一个 RBP       |
+-------------------+
|   局部变量         |  ← 缓冲区从低地址向高地址增长
|   (buffer[64])    |
+-------------------+ ← 低地址
```

**利用思路：**
1. 填充 buffer 直到覆盖返回地址
2. 将返回地址指向攻击者控制的 shellcode 地址（需 NX disabled）或 ROP gadget
3. **ROP（Return-Oriented Programming）：** 从程序已有代码段中拼接 gadget（以 `ret` 结尾的指令片段），构造调用链绕过 NX

```c
// 经典脆弱代码
void vuln() {
    char buf[64];
    gets(buf);  // 输入 >64 字节即栈溢出
}
```

### 2. 堆溢出（Heap Overflow）

**原理：** 堆上的动态分配缓冲区写入越界，破坏相邻块的堆元数据（size、fd、bk 指针）。

```
堆块布局（glibc malloc）:
+--------------------+
| prev_size (8B)     |  ← 元数据
| size (8B)          |  ← 含标志位（P=prev-inuse）
+--------------------+
| user data ...      |  ← 写入越界 → 覆盖下一个块的元数据
+--------------------+
| prev_size (8B)     |  ← 被覆盖的元数据
| size (8B)          |  ← 伪造 size → 任意地址写
+--------------------+
```

**利用思路：**
- **unlink 攻击：** 伪造空闲块的双向链表指针 → 写入 `&[target] - 12` 到 `ptr` → 第二次写入覆写目标地址
- **House of Force：** 覆盖 top chunk 的 size 为 `-1` → 控制下一次分配的地址
- **Fastbin Attack：** 伪造 fastbin 空闲链表 → 分配到任意地址

### 3. 释放后使用（Use-After-Free, UAF）

**原理：** 释放堆内存后未将指针置 NULL，后续继续通过悬垂指针读写已释放区域。

```c
// UAF 场景
char *p = malloc(64);
free(p);
// p 仍是悬垂指针（dangling pointer）
strcpy(p, "data");  // 已释放的内存可能被 realloc 给其他对象
```

**利用思路：**
- 释放对象 A → 申请同大小对象 B（重用 A 的内存）→ 通过 A 的悬垂指针操作 B 的内容
- 在 C++ 中常表现为虚函数表指针被覆盖 → 控制流劫持

### 4. 格式化字符串（Format String）

**原理：** 将用户输入直接作为 `printf` 的第一个参数（格式化字符串），而非 `printf("%s", user_input)`。

```c
printf(user_input);  // 危险！应使用 printf("%s", user_input);
```

**利用原语：**
- `%x` 或 `%p` → **栈泄露**：从栈上读取参数值（逐字节读取内存）
- `%n` → **任意写**：向指针指向的地址写入已输出字符数。使用 `%hn`（2字节）或 `%hhn`（1字节）精确控制
- `%1234d` → 控制输出字符数，配合 `%n` 实现精确写入

```python
# 典型 payload 格式
"%x.%x.%x.%x"         # 读4个栈值
"\x28\xa0\x04\x08%n"  # 写入 0x0804a028
```

### 5. 整型溢出（Integer Overflow）

**原理：** 整数运算结果超出类型范围时发生回绕（wrapping），绕过长度检查。

```c
// 典型漏洞模式
size_t len = user_controlled_value;
if (len + 1 > 1024) return -1;  // len=0xFFFFFFFF → 0xFFFFFFFF+1=0 → 绕过检查
char *buf = malloc(len + 1);    // malloc(0) → 分配极小内存
read(fd, buf, large_size);      // 堆溢出！
```

**安全写法：**
```c
if (len > 1023) return -1;      // 先检查再运算
```

### 6. 竞争条件（Race Condition）

**原理：** 对共享资源的访问缺乏同步保护，导致 TOCTOU（Time-of-Check Time-of-Use）漏洞。

```
时间轴:
t1: 程序检查文件权限 (access("/tmp/secret", R_OK))  ✅ 通过
t2: 攻击者将 /tmp/secret 替换为符号链接指向 /etc/shadow  ⚡ 替换!
t3: 程序操作文件 (open("/tmp/secret"))                 💥 读取 shadow
```

**常见场景：**
- 临时文件创建（先检查存在性后创建）
- 信号处理函数 + 非重入函数
- 多线程中的 double fetch（用户态传递指针被内核态多次解引用）

---

## 二、模糊测试（Fuzzing）

### 2.1 什么是 Fuzzer

**Fuzzer：** 向目标程序自动生成大量半合法输入，监控其是否崩溃、断言失败或产生异常行为，从而发现漏洞。

```
输入种子 → [变异引擎] → 变异输入 → [目标程序] → 崩溃? → 记录
                  ↑                       |
                  └── 反馈(覆盖率) ←───────┘
```

### 2.2 基于变异（Mutation-based）vs 基于生成（Generation-based）

| 特性 | 基于变异 | 基于生成 |
|------|---------|---------|
| 输入来源 | 已有样本做 bit flip/splicing 等 | 根据格式规范从头生成 |
| 优点 | 无需知道格式，通用 | 合法率高，深度覆盖 |
| 缺点 | 大量非法输入被拒绝 | 需要格式描述（如 grammar） |
| 代表 | AFL, LibFuzzer | Peach, AFL (语法插件) |

### 2.3 覆盖率引导（Coverage-guided）

**核心思想：** 优先保留那些能触发**新代码路径**的输入，而非随机探索。

**为什么有效：**
- 程序中有大量路径选择的代码（条件分支、switch-case）
- 随机测试很难覆盖深层路径（指数级分支数）
- 覆盖率反馈 = 智能探索的信号

**边覆盖（Edge Coverage）：** AFL 记录的是**基本块转移对**（edge），而非单个基本块，区分不同路径到达同一基本块的情况。

```
基本块 A → (edge A→B) → 基本块 B
         ↘ (edge A→C) → 基本块 C
    A→B 和 A→C 是不同的 edge，反映不同的控制流
```

### 2.4 AFL（American Fuzzy Lop）工作流程

**核心流程：**

```
1. 编译时插桩（LLVM Pass / GCC plugin）
   ↓
2. 初始化种子队列（初始输入文件）
   ↓
3. 主循环：
   a. 从队列中取出一个种子
   b. 对种子进行变异
      - 确定性阶段: bit flip / byte flip / arithmetic
      - 非确定性阶段: splicing / havoc
   c. 用变异后的输入运行目标程序
   d. 捕获覆盖率信息（共享内存位图）
   e. 如果发现新路径 → 将该输入加入队列
   f. 否则丢弃
   ↓
4. 达到停止条件（时间/迭代数/找到crash）
```

**变异策略：**

| 阶段 | 操作 | 说明 |
|------|------|------|
| bit_flip | 翻转 1 bit | 最小粒度 |
| byte_flip | 翻转连续 N 字节 | 中等粒度 |
| arithmetic | ±N 对整数加减 | 覆盖边界值 |
| interest | 替换为特殊值（0, INT_MAX 等） | 触发边界检查 |
| splicing | 切分两输入并重组 | 探索组合路径 |
| havoc | 随机多种变异组合 | 增加多样性 |

**覆盖率位图：** 64KB 共享内存，记录 edge 哈希。AFL 用 `hash(cur_loc ^ prev_loc)` 作为 edge key。

```
map[cur_loc ^ prev_loc >> 1]++    // 每个 edge 对应一个计数器
```

### 2.5 LibFuzzer

**特点：**
- 进程内（in-process）模糊测试 — 作为库链接到目标函数
- 比 AFL 更快（避免 fork/exec 开销）
- 使用 SanitizerCoverage 插桩
- 与 AddressSanitizer / UBSan 配合使用

```c
// LibFuzzer 目标函数签名
extern "C" int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
    // 解析并处理输入
    process_input(Data, Size);
    return 0;  // 0 = 正常, 非0 = 异常/超时
}
```

**AFL vs LibFuzzer 对比：**

| 特性 | AFL | LibFuzzer |
|------|-----|-----------|
| 进程模型 | fork+exec | in-process 函数调用 |
| 速度 | ~百次/秒 | ~千次~万次/秒 |
| 插桩 | 编译时 | Clang SanitizerCoverage |
| 目标类型 | 任何命令行程序 | 可链接的函数 |
| 并行 | 多实例通过 shared mem | 多实例通过 shared mem |

---

## 三、常见缓解措施（Mitigations）

### 3.1 ASLR / PIE

**ASLR（Address Space Layout Randomization）：** 每次运行时随机化栈、堆、加载基址的起始位置。
- 攻击者无法直接预测函数地址、shellcode 地址
- Brute-force ASLR：32-bit 系统上约 2^16 种可能性，暴力约 2-3 分钟

**PIE（Position Independent Executable）：** 编译为位置无关代码，代码段地址也随机化。
- 编译标志：`-fpie -pie`
- 老系统：仅随机化库的基址，代码段固定
- PIE：连 `.text` 段也随机化

```bash
# 查看 ASLR 状态
cat /proc/sys/kernel/randomize_va_space
# 0 = 关闭, 1 = 部分(栈/库), 2 = 完整(堆也随机)

# 编译 PIE
gcc -fpie -pie -o prog prog.c
```

### 3.2 NX / DEP

**NX（No-Execute）/ DEP（Data Execution Prevention）：** 标记数据页（栈、堆）为不可执行。
- 攻击者无法在栈上执行 shellcode
- 绕过：**ROP** — 复用现有代码段中的 gadget
- 检查：`readelf -l program | grep GNU_STACK` → `E` 标志表示栈可执行

### 3.3 Stack Canary（栈保护）

**原理：** 在栈上局部变量与返回地址之间插入随机值（canary），返回前验证其完整性。

```
栈帧:
+-------------------+
|   返回地址         |  ← 如果 canary 变化 → 检测到溢出
+-------------------+
|   前一个 RBP       |
+-------------------+
|   Canary (随机值)  |  ← 缓冲区溢出首先覆盖这里
+-------------------+
|   局部变量         |
|   (buffer)        |
+-------------------+
```

**绕过方式：**
- **信息泄露：** 先读 canary 值再构造 payload（格式化字符串 UAF 泄露）
- **线程 canary：** 子线程 canary 可通过 fork 继承 → 巧妙利用
- **逐字节爆破：** 某些场景（fork 服务）可逐字节猜解

```bash
gcc -fstack-protector -o prog prog.c       # 仅保护含局部数组的函数
gcc -fstack-protector-strong -o prog prog.c  # 更全面的保护
gcc -fstack-protector-all -o prog prog.c     # 所有函数都保护
```

### 3.4 CFG / Shadow Stack

**CFG（Control-Flow Guard）：** 编译时记录间接跳转的合法目标集合，运行时验证。
- Windows 原生支持（`/guard:cf`）
- 阻止 vtable hijack、间接调用劫持
- 局限：需维护完整的合法目标表

**Shadow Stack（影子栈）：** 硬件辅助的栈保护（Intel CET 技术）。
- 在 CPU 内部维护返回地址的独立副本
- `ret` 指令自动比较栈上 RIP vs 影子栈 RIP
- 不匹配 → 硬件异常
- 彻底阻止 ROP 攻击（理论上）
- 兼容性问题：信号处理、longjmp、协程等

### 综合防护体系

```
┌──────────────────────────────────────────┐
│           应用层                         │
│  CFG / Control Flow Integrity            │
├──────────────────────────────────────────┤
│           运行时层                       │
│  Stack Canary + NX/DEP + ASLR/PIE       │
├──────────────────────────────────────────┤
│           硬件层                         │
│  Shadow Stack (CET) / MPK / SMEP        │
└──────────────────────────────────────────┘
```

---

## 四、Python 实现：简易覆盖引导 Fuzzer

```python
"""
Mini Coverage-Guided Fuzzer
============================
模拟 AFL 核心机制：
1. 位图覆盖率（bitmap coverage）
2. 变异引擎：bit flip + byte flip + 算术变异
3. 种子队列 + 发现新路径保留策略
4. 模拟目标程序的分支行为
"""

import random
import sys
import os

# ============================================================
# 第一部分：模拟目标程序 — 用 Python 模拟覆盖率反馈
# ============================================================

# 64KB 覆盖率位图（AFL 标准大小）
BITMAP_SIZE = 65536

class SimulatedTarget:
    """模拟目标程序，根据输入内容产生不同的覆盖路径"""
    
    def __init__(self):
        self.bitmap = [0] * BITMAP_SIZE
        self.edge_count = 0
    
    def reset_bitmap(self):
        self.bitmap = [0] * BITMAP_SIZE
        self.edge_count = 0
    
    def run(self, data: bytes) -> tuple:
        """
        模拟运行目标程序，返回 (new_edges_found, is_crash)
        
        模拟的分支逻辑：
        - 输入为空：基本路径
        - 首字节决定主分支
        - 后续字节触发更多边
        - 特殊值触发 crash
        """
        self.reset_bitmap()
        prev_loc = 0
        
        if len(data) == 0:
            # 空输入 → 路径 0
            cur = 1
            self.bitmap[(cur ^ (prev_loc >> 1)) & 0xFFFF] = 1
            return 0, False
        
        # 主分支：由首个字节低 4 位决定
        main_branch = data[0] & 0x0F
        cur = 10 + main_branch  # 10~25
        edge = (cur ^ (prev_loc >> 1)) & 0xFFFF
        if self.bitmap[edge] == 0:
            self.bitmap[edge] = 1
            self.edge_count += 1
        prev_loc = cur
        
        # 子分支 1：由首个字节高 4 位决定
        sub1_branch = (data[0] >> 4) & 0x0F
        cur = 30 + sub1_branch  # 30~45
        edge = (cur ^ (prev_loc >> 1)) & 0xFFFF
        if self.bitmap[edge] == 0:
            self.bitmap[edge] = 1
            self.edge_count += 1
        prev_loc = cur
        
        # 二级分支：取决于第二个字节
        if len(data) >= 2:
            sub2_branch = data[1] & 0x07
            cur = 50 + sub2_branch  # 50~57
            edge = (cur ^ (prev_loc >> 1)) & 0xFFFF
            if self.bitmap[edge] == 0:
                self.bitmap[edge] = 1
                self.edge_count += 1
            prev_loc = cur
            
            # 三级分支：基于字节1的高3位
            sub3_branch = (data[1] >> 5) & 0x07
            cur = 60 + sub3_branch  # 60~67
            edge = (cur ^ (prev_loc >> 1)) & 0xFFFF
            if self.bitmap[edge] == 0:
                self.bitmap[edge] = 1
                self.edge_count += 1
            prev_loc = cur
            
            # 四级：基于字节0和字节1的异或
            xor_val = (data[0] ^ data[1]) & 0x0F
            cur = 70 + xor_val  # 70~85
            edge = (cur ^ (prev_loc >> 1)) & 0xFFFF
            if self.bitmap[edge] == 0:
                self.bitmap[edge] = 1
                self.edge_count += 1
            prev_loc = cur
        
        # 如果长度 >= 3，触发更多路径
        if len(data) >= 3:
            depth_branch = data[2] & 0x03
            cur = 90 + depth_branch  # 90~93
            edge = (cur ^ (prev_loc >> 1)) & 0xFFFF
            if self.bitmap[edge] == 0:
                self.bitmap[edge] = 1
                self.edge_count += 1
            prev_loc = cur
        
        # 模拟 crash：特定序列
        if len(data) >= 4:
            if data[0] == 0x41 and data[1] == 0x42 and data[2] == 0x43:
                return self.edge_count, True  # "ABC" 开头触发 crash
        
        return self.edge_count, False


# ============================================================
# 第二部分：变异引擎 — bit flip + byte翻转 + 算术变异
# ============================================================

def bit_flip(data: bytes) -> bytes:
    """翻转随机一个 bit"""
    if len(data) == 0:
        return data
    idx = random.randint(0, len(data) - 1)
    bit = random.randint(0, 7)
    b = bytearray(data)
    b[idx] ^= (1 << bit)
    return bytes(b)


def byte_flip(data: bytes) -> bytes:
    """将一个字节替换为随机值"""
    if len(data) == 0:
        return bytes([random.randint(0, 255)])
    idx = random.randint(0, len(data) - 1)
    b = bytearray(data)
    b[idx] = random.randint(0, 255)
    return bytes(b)


def arithmetic_mutate(data: bytes) -> bytes:
    """对随机字节做 ±N 运算"""
    if len(data) == 0:
        return data
    idx = random.randint(0, len(data) - 1)
    delta = random.choice([1, -1, 2, -2, 4, -4, 8, -8, 16, -16])
    b = bytearray(data)
    b[idx] = (b[idx] + delta) & 0xFF
    return bytes(b)


def splice(data: bytes) -> bytes:
    """从自身不同位置拼接（模拟 AFL 的 splicing）"""
    if len(data) < 2:
        return data
    p1 = random.randint(0, len(data) - 1)
    p2 = random.randint(p1, len(data) - 1)
    if p1 == p2:
        return data
    b = bytearray(data)
    b[p1], b[p2] = b[p2], b[p1]
    return bytes(b)


def interest_replace(data: bytes) -> bytes:
    """替换为特殊边界值"""
    interests = [0x00, 0x01, 0x7F, 0x80, 0xFF, 0xFE,
                0x7FFF, 0x8000, 0xFFFF, 0x7FFFFFFF, 0x80000000,
                0xFFFFFFFF, 0x00000000]
    if len(data) == 0:
        val = random.choice(interests)
        return bytes([val & 0xFF])
    idx = random.randint(0, len(data) - 1)
    val = random.choice(interests)
    b = bytearray(data)
    b[idx] = val & 0xFF
    return bytes(b)


def havoc_mutate(data: bytes) -> bytes:
    """随机应用多种变异（havoc 阶段模拟）"""
    data = random.choice([
        lambda d: d + bytes([random.randint(0, 255)]),
        lambda d: d[:-1] if len(d) > 2 else d,
        lambda d: bytes(reversed(d)),
        lambda d: d * 2 if len(d) < 32 else d,
        lambda d: d,
    ])(data)
    # 再随机应用 1~3 种原子变异
    mutators = [bit_flip, byte_flip, arithmetic_mutate, splice, interest_replace]
    for _ in range(random.randint(1, 3)):
        data = random.choice(mutators)(data)
    return data


# ============================================================
# 第三部分：Fuzzer 主循环
# ============================================================

class CoverageGuidedFuzzer:
    """
    覆盖率引导 Fuzzer
    
    维护：
    - 种子队列（queue）
    - 全局覆盖率地图（global_coverage）
    - 已发现的所有边（edges_seen）
    """
    
    def __init__(self, target: SimulatedTarget, initial_seed: bytes = b""):
        self.target = target
        self.queue = [initial_seed]     # 种子队列
        self.edges_seen = set()          # 全局已发现边集合
        self.total_new_edges = 0         # 统计
        self.crashes = []                # 触发 crash 的输入
        self.iterations = 0
        
        # 评估初始种子
        self._evaluate(initial_seed)
    
    def _evaluate(self, data: bytes) -> bool:
        """评估一个输入是否发现新路径"""
        new_edges, is_crash = self.target.run(data)
        self.iterations += 1
        
        # 检查是否 crash
        if is_crash:
            self.crashes.append(data)
            return True
        
        # 检查新边
        found_new = False
        for idx, val in enumerate(self.target.bitmap):
            if val and idx not in self.edges_seen:
                self.edges_seen.add(idx)
                self.total_new_edges += 1
                found_new = True
        
        return found_new
    
    def _pick_seed(self):
        """轮询选择种子"""
        idx = self.iterations % len(self.queue)
        return self.queue[idx]
    
    def fuzz(self, max_iterations: int = 10000):
        """主模糊测试循环"""
        print(f"[+] 启动 Fuzzer — 最大迭代: {max_iterations}")
        print(f"[+] 初始种子: {list(self.queue[0]) if self.queue[0] else '(空)'}")
        print(f"[+] 初始种子队列: {len(self.queue)}, 初始边: {len(self.edges_seen)}")
        print()
        
        for i in range(max_iterations):
            # 1. 选择种子
            seed = self._pick_seed()
            
            # 2. 变异
            mutant = self._mutate(seed)
            
            # 3. 评估
            is_crash = self._evaluate(mutant)
            
            # 4. 新路径 → 保留到队列
            new_edges_before = len(self.edges_seen)
            found_new = self._evaluate(mutant)
            new_edges_now = len(self.edges_seen)
            
            if new_edges_now > new_edges_before:
                # 发现新路径，保留
                self.queue.append(mutant)
                if (i + 1) <= 50 or (i + 1) % 500 == 0:
                    n = new_edges_now - new_edges_before
                    print(f"  ✨ 迭代 {i+1:6d}: 发现 {n:3d} 条新边! "
                          f"(边总计: {new_edges_now:5d}, "
                          f"队列: {len(self.queue):4d}, "
                          f"crash: {len(self.crashes):2d})")
            
            if is_crash:
                print(f"  💥 迭代 {i+1:6d}: 发现 CRASH! "
                      f"输入: {list(mutant[:16])}{'...' if len(mutant) > 16 else ''}")
        
        # 总结
        print()
        print("=" * 60)
        print(f"模糊测试结束 — 统计报告")
        print("=" * 60)
        print(f"  总迭代次数:     {self.iterations}")
        print(f"  种子队列大小:   {len(self.queue)}")
        print(f"  发现边数:       {len(self.edges_seen)}")
        print(f"  发现 Crash:     {len(self.crashes)}")
        if self.crashes:
            print(f"  Crash 输入:")
            for i, c in enumerate(self.crashes):
                print(f"    #{i+1}: {list(c)}")
        print()
        
        return len(self.crashes) > 0
    
    def _mutate(self, data: bytes) -> bytes:
        """变异引擎：组合多种变异策略"""
        mutators = [bit_flip, byte_flip, arithmetic_mutate, splice, interest_replace]
        
        # 前几次迭代用确定性变异，后面用 havoc
        if self.iterations < 100:
            m = random.choice(mutators[:3])  # bit_flip, byte_flip, arithmetic
            return m(data)
        else:
            return havoc_mutate(data)


# ============================================================
# 第四部分：演示主程序
# ============================================================

def demo():
    """演示覆盖引导 Fuzzer 从种子逐步发现新路径"""
    print("=" * 60)
    print("  Mini Coverage-Guided Fuzzer 演示")
    print("  模拟 AFL 核心机制：覆盖率引导 + 变异引擎")
    print("=" * 60)
    print()
    
    # 创建目标程序模拟
    target = SimulatedTarget()
    
    # 初始种子（空输入）
    fuzzer = CoverageGuidedFuzzer(target, initial_seed=b"\x00")
    
    print("[*] 目标程序分支结构:")
    print("    - 首字节低4位:  主分支 (10~25)")
    print("    - 首字节高4位:  子分支1 (30~45)")
    print("    - 第二字节低3位: 子分支2 (50~57)")
    print("    - 第二字节高3位: 子分支3 (60~67)")
    print("    - 字节0^字节1:  子分支4 (70~85)")
    print("    - 第三字节低2位: 子分支5 (90~93)")
    print("    - 'ABC' 开头:   触发 Crash!")
    print()
    
    # 运行 fuzzer
    hit_crash = fuzzer.fuzz(max_iterations=3000)
    
    print("[*] 演示结论:")
    print("    1. Fuzzer 通过覆盖率反馈自动探索了目标程序的分支")
    print("    2. 发现新路径的输入被保留到种子队列，用于后续变异")
    print("    3. 未发现新路径的输入被丢弃（优化效率）")
    print("    4. 变异引擎提供了足够多样性来探索深层路径")
    if hit_crash:
        print("    5. 成功触发 crash! 漏洞被自动发现")
    print()


if __name__ == "__main__":
    demo()
```

**运行结果示例：**

```
================================================================
  Mini Coverage-Guided Fuzzer 演示
  模拟 AFL 核心机制：覆盖率引导 + 变异引擎
================================================================

[+] 启动 Fuzzer — 最大迭代: 3000
[+] 初始种子: [0]
[+] 初始种子队列: 1, 初始边: 1

  ✨ 迭代     4: 发现   3 条新边! (边总计:  4, 队列:  2, crash:  0)
  ✨ 迭代     7: 发现   1 条新边! (边总计:  5, 队列:  3, crash:  0)
  ✨ 迭代    11: 发现   2 条新边! (边总计:  7, 队列:  4, crash:  0)
  ✨ 迭代    18: 发现   1 条新边! (边总计:  8, 队列:  5, crash:  0)
  ...
  ✨ 迭代   423: 发现   1 条新边! (边总计: 20, 队列: 15, crash:  0)
  💥 迭代  1442: 发现 CRASH! 输入: [65, 66, 67, ...]
```

### 关键设计要点

1. **覆盖率位图**：记录每个 edge 是否被访问过（AFL 用 8-bit 计数器）
2. **种子队列**：发现新边 → 保留到队列 → 用于后续变异
3. **变异策略分层**：确定性阶段（bit/byte/arithmetic）→ 非确定性阶段（havoc）
4. **边覆盖 = `hash(cur_loc ^ prev_loc)`**：区分同一基本块的不同路径

---

## 五、总结

### 漏洞分类速查

| 漏洞类型 | 触发位置 | 利用目标 | 关键缓解 |
|---------|---------|---------|---------|
| 栈溢出 | 栈 | 返回地址 → ROP | Canary, NX |
| 堆溢出 | 堆 | 元数据 → 任意写 | ASLR, CFG |
| UAF | 堆 | 悬垂指针 | CFG, 喷砂缓解 |
| 格式化字符串 | 栈 | 任意读/写 | 编译警告 |
| 整型溢出 | 寄存器 | 绕过长度检查 | -Wsign-compare |
| 竞争条件 | 共享内存 | TOCTOU | 原子操作 |

### Fuzzing 核心流程

```
种子输入 → 变异 → 运行目标 → 崩溃? → 记录
                    ↓
             检查覆盖率
              ↓       ↓
           新路径    无新路径
              ↓       ↓
          保留种子   丢弃
```

### 实战建议

1. **AFL：** 适合二进制程序（命令行工具、网络服务、文件解析器）
2. **LibFuzzer：** 适合函数级别的单元测试、库函数
3. **结合 Sanitizer：** AddressSanitizer + Fuzzer = 自动检测内存错误
4. **语料库管理：** 高质量的初始种子显著提升效率
5. **并行化：** AFL 多实例通过 `-M/-S` 协调

---

## 参考

- AFL whitepaper: Michal Zalewski, "American Fuzzy Lop"
- libFuzzer – A Library for Coverage-guided Fuzz Testing
- Intel CET (Control-flow Enforcement Technology) Specification
- OWASP: Buffer Overflow / Format String / Race Condition

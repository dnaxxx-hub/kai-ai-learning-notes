# 编译原理第6课：代码生成与优化

## 1. 中间代码生成回顾

### 三地址码（Three-Address Code, TAC）

每条指令形如 `x = y op z`，最多一个运算符 + 三个地址（两个源 + 一个目标）。

```
# 常见 TAC 指令类型
x = y op z        # 二元运算
x = op y          # 一元运算（如取负：x = -y）
x = y             # 复制/赋值
goto L            # 无条件跳转
if x goto L       # 条件跳转
ifFalse x goto L  # 条件跳转（假转移）
param x           # 传参
call f, n         # 函数调用（n个参数）
return x          # 返回
x = f()           # 返回值赋值
```

**TAC 生成规则（语法制导翻译）：**

```
产生式                    语义动作
S → id = E               gen(id.name '=' E.place)
E → E1 + E2              t = newtemp(); gen(t '=' E1.place '+' E2.place); E.place = t
E → E1 * E2              t = newtemp(); gen(t '=' E1.place '*' E2.place); E.place = t
E → num                  E.place = num.val
E → id                   E.place = id.name
S → if (E) S1            t = newtemp(); gen('ifFalse' E.place 'goto' L.out); ...
S → while (E) S1         L1 = newlabel(); L2 = newlabel(); gen('label' L1); ...
```

### SSA（静态单赋值形式）

每个变量在程序中**只赋值一次**，通过引入版本号和 φ 函数在控制流汇合处合并值。

```
非 SSA:                           SSA:
  x = 1                            x₁ = 1
  if cond:                         if cond:
      x = 2                            x₂ = 2
  print(x)                         x₃ = φ(x₁, x₂)
                                   print(x₃)
```

**SSA 的优势：**
- 数据流分析更简单（每个变量只有一个定义点）
- 简化的死代码消除（没用过的变量直接删）
- 简化的常量传播（定义唯一，无需考虑多个版本）
- 简化的 CSE（相同 RHS 必然产生相同值）

**φ 函数的放置：** 在控制流汇合处（CFG 的 join 节点）为每个有多版本的定义插入 φ。

---

## 2. 基本块与控制流图（CFG）

### 基本块（Basic Block）

**定义：** 最大的连续指令序列，满足：
1. 只能从第一句**进入**（无分支跳到中间）
2. 只能从最后一句**离开**（无分支从中间跳出）

**划分方法（Leader 算法）：**
1. 第一条指令是 **leader**
2. 任何跳转/条件跳转的**目标**是 leader
3. 任何跳转/条件跳转的**下一条**是 leader
4. 每个 leader 到下一个 leader（不含）构成一个基本块

```
# TAC 示例                      # 基本块划分
t1 = 4 * 5                     ┌─ Block 1 ─┐
t2 = 3 + t1                    │ t1 = 4 * 5│
if t2 > 10 goto L1             │ t2 = 3 + t1├─────┐
x = t2 + 1                     │if t2>10 goto L1  │条件跳转
goto L2                        │ goto L2    │     │
L1: y = t2 * 2                 └────────────┘  ┌──┴─ Block 2 ─┐
L2: z = x + y                  L1: leader────→│ y = t2 * 2   │
                                               └──────────────┘
                                        ┌───── Block 3 ──────┐
                                        L2: leader ──────→│ z = x + y       │
                                                          └─────────────────┘
```

### 控制流图（Control Flow Graph, CFG）

节点 = 基本块；边 = 控制流转移（跳转 / 条件跳转 / 顺序下行）。

```
          ┌──────────┐
          │  Block 1 │   (入口)
          │   ...    │
          └────┬─────┘
               │ true
          ┌────▼─────┐     ┌──────────┐
          │  Block 2 │     │  Block 3 │  (条件分支目标)
          │   ...    │     │   ...    │
          └────┬─────┘     └──────────┘
               │ false
          ┌────▼─────┐
          │  Block 4 │   (汇合)
          │   ...    │
          └──────────┘
```

**关键术语：**
- **前驱（predecessor）：** 指向当前块的所有块
- **后继（successor）：** 当前块指向的所有块
- **支配（dominator）：** 从入口到块 B 的任何路径都经过块 D，称 D 支配 B
- **严格支配：** D 支配 B 且 D ≠ B
- **直接支配者（immediate dominator, IDom）：** 离 B 最近的严格支配者
- **支配树（dominator tree）：** 以入口为根的树，父节点是子节点的直接支配者
- **回边（back edge）：** A → B，其中 B 支配 A → 标识了循环
- **自然循环（natural loop）：** 回边 A → B 确定的循环 = {B} ∪ {所有能到达 A 且不被 B 离开的节点}

---

## 3. 局部优化（基本块内）

### 3.1 常量折叠（Constant Folding）

编译期计算常量表达式，避免运行时开销。

```
t1 = 2 * 3      →    t1 = 6
t2 = 10 + 20    →    t2 = 30
t3 = 1.5 * 4.0  →    t3 = 6.0
t4 = !true      →    t4 = false
```

### 3.2 常量传播（Constant Propagation）

常量变量被后续使用时代入其值。

```
a = 5               a = 5
b = a + 3     →     b = 8     ← a=5 被传播
c = b * 2           c = 16    ← b=8 被传播
```

**结合常量折叠和传播，可以不断迭代直到不动点：**

```
x = 3               x = 3
y = x + 1     →     y = 4
z = y * 2           z = 8
w = z + x           w = 11
```

### 3.3 死代码消除（Dead Code Elimination, DCE）

删除定义了但从未被读取的变量（"死赋值"）。

```
# DCE 前                        # DCE 后
a = 5                           
b = a + 1          →            b = a + 1
c = b * 2                       c = b * 2
a = 10             删除 a = 10  ← a 在此后被读取了吗？没有，删掉
d = c + 3                       d = c + 3
```

**算法（反向扫描 + 活跃性分析）：**
```
处理基本块中的每条语句（从最后一条往前）:
  for 每条语句 s: x = y op z:
    if x 在活跃变量集合中:
      标记 s 为有用（保留）
      从活跃集合移除 x
      将 y, z 加入活跃集合
    else:
      删除 s（无用赋值）
```

### 3.4 公共子表达式消除（Common Subexpression Elimination, CSE）

如果相同的表达式被计算多次，将第一次结果保存到临时变量，后续直接使用。

```
# CSE 前                        # CSE 后
t1 = a + b                      t1 = a + b
t2 = a + b          →           t2 = t1        ← 直接复用 t1
t3 = a + b + c                  t3 = t1 + c    ← 复用 t1
x  = a + b                      x  = t1        ← 再次复用
```

**算法（扫描 + 哈希）：**
```
维护一个「表达式 → 计算结果」的映射表
遍历基本块内每条语句 s: x = y op z:
  key = (op, y, z)
  if key 在表中存在:
    将当前语句改为 x = 已有结果  (复制传播)
  else:
    将 key → x 加入表中
```

**注意：** 变量被重新赋值后，涉及该变量的所有表达式条目都失效。

```
a = b + c      # key('+', b, c) → a
b = x          # b 变了！所有含 b 的表达式失效
d = b + c      # 虽然 b+c 之前算过，但 b 已变，需要重新计算
```

### 3.5 代数简化（Algebraic Simplification）

利用代数恒等式简化表达式。

| 恒等式 | 简化 | 原理 |
|--------|------|------|
| `x + 0` | `x` | 加 0 恒等 |
| `x - 0` | `x` | 减 0 恒等 |
| `x * 1` | `x` | 乘 1 恒等 |
| `x * 0` | `0` | 乘 0 恒零 |
| `x / 1` | `x` | 除 1 恒等 |
| `x - x` | `0` | 自身相减为零 |
| `x * 2` | `x << 1` | 移位比乘法快 |
| `x / 2` | `x >> 1` | 移位比除法快 |
| `0 / x` | `0` | 零除以任何数 |
| `!!x` | `x` | 双重取反消除 |
| `x && false` | `false` | 短路求值 |

---

## 4. 全局优化（跨基本块）

### 4.1 数据流分析框架

**通用结构：**
- **数据流方向：** 前向（前驱→当前）或后向（后继→当前）
- **交汇操作：** 交汇点如何合并多个前驱/后继的信息
- **转移函数：** 信息如何流过一条语句

| 分析类型 | 方向 | 交汇操作 | 转移函数 | 目的 |
|---------|------|---------|---------|------|
| 到达定义 | 前向 | ∪ | `out[B] = gen[B] ∪ (in[B] - kill[B])` | 每个使用点知道有哪些定义可能到达 |
| 活跃变量 | 后向 | ∪ | `in[B] = use[B] ∪ (out[B] - def[B])` | 寄存器分配时知道哪些变量还"活着" |
| 可用表达式 | 前向 | ∩ | `out[B] = e_gen[B] ∪ (in[B] - e_kill[B])` | 用于 CSE 和循环不变量检测 |

### 4.2 到达定义（Reaching Definitions）

**目标：** 对每个变量使用点，知道有哪些定义（赋值语句）可能到达该点。

```
对于基本块 B:
  gen[B] = 块内生成的、且没被块内覆盖的定义集合
  kill[B] = 全局中所有定义了某个变量 x 的语句（当 B 也定义 x 时）

公式：
  in[B]  = ∪ predecessor 的 out[p]
  out[B] = gen[B] ∪ (in[B] - kill[B])
```

**应用：** 常量传播时需要知道一个变量是否只有唯一的定义到达。

### 4.3 活跃变量分析（Live Variable Analysis）

**目标：** 对每个程序点，知道哪些变量在未来会被读取（"活着"）。

```
对于基本块 B:
  def[B] = 块内被定义的变量（被赋值前被杀死）
  use[B] = 块内被使用、但定义在块外的变量

公式（后向）：
  out[B] = ∪ successor 的 in[s]
  in[B]  = use[B] ∪ (out[B] - def[B])
```

**算法（迭代求不动点）：**
```
初始化: in[B] = out[B] = ∅ (所有块)
do:
  changed = false
  for 每个基本块 B (逆序):
    out[B] = ∪ in[s] for s in B.successors
    in[B] = use[B] ∪ (out[B] - def[B])
    if in[B] 或 out[B] 变化: changed = true
while changed
```

**应用：**
- 寄存器分配：如果两个变量同时活跃，不能放在同一寄存器
- 死代码消除：活跃变量外的赋值可删除

### 4.4 可用表达式分析（Available Expressions）

**目标：** 对每个程序点，知道哪些表达式已被计算且结果仍然有效。

```
对于基本块 B:
  e_gen[B] = 块内计算的表达式集合（但表达式内的操作数在块内被重定义后失效）
  e_kill[B] = 任意包含块内被定义变量的表达式

公式（前向，交集）：
  in[B]  = ∩ predecessor 的 out[p]
  out[B] = e_gen[B] ∪ (in[B] - e_kill[B])
```

**为什么用交集 ∩？** 一个表达式只有从**所有**前驱路径都可用，才在当前块入口可用。

**应用：** 全局 CSE（跨基本块的公共子表达式消除）。

### 4.5 迭代求解算法（通用框架）

```
// 前向分析
初始化: in[entry] = 初始值; in[B] = ⊤ 或 ⊥
for 每个基本块 B:
    out[B] = f_B(in[B])  // f_B 是转移函数
do:
    changed = false
    for 每个基本块 B (前向顺序):
        in[B]  = ∧ out[p] for p in predecessors  // ∧是交汇操作
        out[B] = f_B(in[B])
        if out[B] 变化: changed = true
while changed
```

### 4.6 循环优化

#### 循环不变量外提（Loop Invariant Code Motion, LICM）

**循环不变量：** 在循环的每次迭代中值都不变的表达式。

**判定条件：** 对于语句 `x = y op z`：
1. y 和 z 都是常量，或者
2. y 和 z 的定义都在循环外，或者
3. y 和 z 的定义在循环内但同样是不变量（归纳）

**外提条件（安全）：** 必须保证：
1. 块**支配**循环的所有出口（执行时才外提）
2. x 在循环中没有其他定义
3. x 在循环中被使用时只有这一定义到达

```
# LICM 前                      # LICM 后
while i < n:                   t = a + b      ← 提到循环外
    t = a + b           →      while i < n:
    x[i] = t + 1                    x[i] = t + 1
    i = i + 1                       i = i + 1
```

#### 强度削弱（Strength Reduction）

将昂贵的运算替换为廉价运算。

```
# 强度削弱前                   # 强度削弱后
i = 0                          i = 0
while i < n:                   t = 0            ← 辅助变量，跟踪 4*i
    x = 4 * i           →      while i < n:
    arr[x] = ...                    arr[t] = ...
    i = i + 1                       i = i + 1
                                    t = t + 4    ← 加 4 比乘 4 便宜
```

**常见替换：**

| 原操作 | 替换 | 节省 |
|--------|------|------|
| `x * 2^n` | `x << n` | 乘法→移位 |
| `x / 2^n` | `x >> n` | 除法→移位 |
| `i * c`（循环中递增） | `t = t + c` | 乘法→加法 |
| `x^2` | `x * x` | 幂→乘 |

#### 归纳变量删除（Induction Variable Elimination）

循环中多个变量以固定步长同步变化时，可以删除多余的。

```
# 归纳变量删除前              # 归纳变量删除后
i = 0                          i = 0
j = 0                          while i < 100:
while i < 100:         →           ... ...   (所有使用 j 的地方改为 i * 2)
    ... i ...
    ... j ...
    i = i + 1
    j = j + 2
```

更常见的情况：删除仅用于数组索引的归纳变量，用基址 + 偏移替代。

**三步曲关系：** 通常先 LICM → 再强度削弱 → 再归纳变量删除，三者常配合使用。

---

## 5. 寄存器分配

### 5.1 问题定义

给定 K 个物理寄存器，将程序中的虚拟变量/临时值映射到物理寄存器或内存。

**约束：** 如果两个变量同时活跃，不能分配到同一寄存器。

### 5.2 图染色算法（Graph Coloring）

**核心思想：** 构建干涉图 → 用 K 种颜色给节点染色 → 相邻节点不同色。

#### 步骤一：构建干涉图（Interference Graph）

- 节点 = 变量/临时值
- 边 = 两个变量在某个程序点同时活跃

**如何检测干涉：** 在语句 `a = b + c` 处，`a` 与 `{b, c, 其他活跃变量}` 干涉？不对——a 此时刚被定义，旧值死亡，不与其他在 out 中活跃的变量干涉。

精确规则（基于活跃变量的构建）：
```
对于每条指令 i: x = y op z:
  for 每个 v in (活跃变量[out[i]] - {x}):
    在 x 和 v 之间加干涉边
```

#### 步骤二：简化（Simplify）

```
简化栈 = []
while 图非空:
  找度数 < K 的节点 v：
    移除 v 入栈
    从图中移除 v 及其边
  如果找不到（所有节点度数 ≥ K）：
    选择"最差"节点（溢出候选），
    标记为"可能溢出"，
    移除入栈
```

#### 步骤三：着色（Assign Colors）

```
颜色 = {}  (节点→颜色)
while 简化栈非空:
  v = 栈.pop()
  收集 v 的邻居已使用的颜色 → used
  从 {0, 1, ..., K-1} 中选择未被 used 的颜色
  如果没有可用颜色：
    标记 v 为"实际溢出"
```

#### 步骤四：处理溢出（Spill）

对于溢出变量，在每次使用前插入 load 指令，在每次定义后插入 store 指令。

```
# 溢出前                        # 溢出后
a = 5                           M[sp+0] = 5    ← 存到栈
b = a + 3                       t = M[sp+0]    ← 从栈加载
                                b = t + 3
```

溢出后，干涉图节点数量可能增加（因为 load/store 引入新临时变量），需要**重新执行**图染色。

#### 完整示例（K=3）：

```
# TAC
a = 1
b = 2
c = a + b
d = c * 3
e = d + a

# 活跃变量分析（精选关键点）：
# out[c = a+b]: {c, a}
# out[d = c*3]: {d, a}
# out[e = d+a]: {e}

# 干涉图：
# a -- c (两者在 out[c=a+b] 中同时活跃)
# a -- d
# a -- e (虽然 e 无后续使用，但为简化起见)
# c -- d
# d -- e 无干涉（d 在 e 定义前死亡）

# 染色 K=3 (R1, R2, R3)：
# a → R1, c → R2, d → R3, e → R1
```

### 5.3 图染色优化：保守合并（Coalescing）

将复制指令 `a = b` 的源和目的合并为同一节点（从而消除复制指令），前提是合并后节点度数 < K。

### 5.4 线性扫描（Linear Scan）

相比图染色更简单、更快（O(N log N)），适合 JIT 编译器。

**活跃区间（Live Interval）：** 从变量第一次定义到最后一次使用的区间。

```
算法：
1. 按活跃区间起始点排序
2. 活跃区间集合 active = []
3. 遍历每个区间 i:
   从 active 中移除已结束的区间
   if active.size < K:
       分配一个空闲寄存器
       active.append(i)
   else:
       选择 active 中结束点最晚的区间 spill
       如果 i 的结束点更早：
           溢出 spill，i 占用其寄存器
       否则：
           溢出 i 自身
```

### 5.5 溢出代价模型

选择溢出变量时，需要评估代价：

```
代价 = 所有 load/store 插入点的执行频率 × 内存访问代价
```

- 在循环内频繁访问的变量溢出代价高 → 优先保留在寄存器
- 在循环外很少访问的变量溢出代价低 → 优先溢出

---

## 6. 代码生成（目标代码）

### 6.1 指令选择（Instruction Selection）

#### 树模式匹配（Tree Pattern Matching / Tiling）

将 IR 表达式树用目标指令集模式"瓦片"覆盖，选择**最优覆盖率**（最小代瓦片数 / 最低代价）。

```
IR 树:              t = a + b * 2

      t
      |
      =
     / \
    t   +
       / \
      a   *
         / \
        b   2

x86 指令模式匹配:
模式1:                   模式2:
  MOV [t], R              MOV [t], R
  ADD R, [a]              MOV R, [a]
  ADD R, [b]              ADD R, [b]
  ADD R, [b]              ADD R, [b]
  代价: 4条                代价: 4条 (一样)

更好的模式 (LEA - Load Effective Address):
  LEA EAX, [a + b*2]    ← x86 一条指令搞定
  MOV [t], EAX
  代价: 2条
```

**常见的指令选择算法：**
1. **最大吞图（Maximal Munch）：** 从根节点开始，每次都选能覆盖的最大模式
2. **动态规划：** 自底向上计算每个子树的**最小代价**覆盖方案
3. **BURG/BTEG：** 基于树文法的自动生成器，用 DP 找最优覆盖

#### x86/x64 伪汇编常用指令映射

| TAC | 伪汇编 |
|-----|--------|
| `a = b + c` | `MOV R, b; ADD R, c; MOV a, R` |
| `a = b - c` | `MOV R, b; SUB R, c; MOV a, R` |
| `a = b * c` | `MOV R, b; IMUL R, c; MOV a, R` |
| `a = b / c` | `MOV R, b; IDIV c; MOV a, R` |
| `if a > b goto L` | `MOV R, a; CMP R, b; JG L` |
| `goto L` | `JMP L` |
| `return a` | `MOV RAX, a; RET` |
| `param a` | `PUSH a` 或 `MOV [stack], a` |

### 6.2 指令调度（Instruction Scheduling）

**目标：** 重排指令顺序以最大化指令级并行度（ILP），减少流水线停顿。

#### 数据依赖（Hazards）

```
依赖类型：
RR: a = b + c           # 读 b, c → 写 a
    d = a + e           # 读 a ← 真依赖（RAW），不可重排
    f = d * 2           # 读 d ← 链式 RAW

反依赖（WAR）和输出依赖（WAW）可通过寄存器重命名消除。
```

#### 列表调度（List Scheduling）

```
1. 为基本块构建依赖图（DAG）
2. 计算每个节点的优先度（路径长度 / 关键路径深度）
3. 维护就绪队列（所有依赖已满足的节点）
4. 循环：从就绪队列取最高优先度的节点发出
```

**示例：**

```
# 原始顺序                          # 调度后（假设加载延迟 2 周期，ALU 延迟 1 周期）
LD R1, [a]                         LD R1, [a]
LD R2, [b]                         LD R2, [b]
ADD R3, R1, R2     ← 等待 R1       LD R4, [c]
LD R4, [c]         ← 可以提前       LD R5, [d]
LD R5, [d]         加载 c,d         ADD R3, R1, R2   ← R1,R2 已就绪
SUB R6, R4, R5                     SUB R6, R4, R5
MUL R7, R3, R6    ← 等待 R3,R6     MUL R7, R3, R6   ← R3,R6 已就绪
```

**优化效果：** 流水线停顿从 3 周期降到 0 周期。

---

## 7. Python 极简优化器实现

### 实现内容

1. **TAC → 基本块划分 → CFG**
2. **常量传播 + 死代码消除 + CSE**（基本块内）
3. **循环不变量外提**（带循环检测）

完整代码见：`memory/learning/code/optimizer.py`

### 核心数据结构

```python
@dataclass
class TACInstr:
    """三地址码指令"""
    dest: str       # 目标变量或 None
    op: str         # '=', '+', '-', '*', 'if', 'goto', 'label', 'return'
    arg1: any       # 左操作数
    arg2: any       # 右操作数或 None

@dataclass
class BasicBlock:
    label: str                  # 入口标签
    instrs: List[TACInstr]     # 指令序列
    preds: List[str]           # 前驱块名
    succs: List[str]           # 后继块名

class CFG:
    blocks: Dict[str, BasicBlock]
    entry: str
```

### 关键算法实现

#### 1) 基本块划分

```python
def build_blocks(tac_list):
    """Leader 算法划分基本块"""
    leaders = {0}  # 第一条指令
    for i, instr in enumerate(tac_list):
        if instr.op in ('goto',):
            if i + 1 < len(tac_list):
                leaders.add(i + 1)  # 跳转的下一条
        if instr.op in ('goto', 'if'):
            leaders.add(block_of_target(instr.arg1))  # 跳转目标
    # 按 leader 分组
    blocks = []
    for start, end in zip(leaders, sorted(leaders)[1:] + [len(tac_list)]):
        blocks.append(BasicBlock(tac_list[start:end]))
    return blocks
```

#### 2) 常量传播与折叠（一个 Pass 完成）

```python
def constant_fold_propagate(block):
    """常量传播 + 折叠（逐指令前向扫描）"""
    const_map = {}  # 变量名 → 常量值
    new_instrs = []
    for instr in block.instrs:
        # 尝试折叠操作数
        a1 = const_map.get(instr.arg1, instr.arg1)
        a2 = const_map.get(instr.arg2, instr.arg2) if instr.arg2 else None
        # 如果两个操作数都是常量，折叠
        if instr.op == '+' and is_const(a1) and is_const(a2):
            val = int(a1) + int(a2)
            const_map[instr.dest] = str(val)
            new_instrs.append(TACInstr(instr.dest, '=', str(val), None))
        elif instr.op == '*' and is_const(a1) and is_const(a2):
            val = int(a1) * int(a2)
            const_map[instr.dest] = str(val)
            new_instrs.append(TACInstr(instr.dest, '=', str(val), None))
        elif instr.op == '=' and is_const(a1):
            const_map[instr.dest] = str(a1)
            new_instrs.append(instr)  # 保留赋值
        else:
            # 传播常量到操作数
            new_instrs.append(
                TACInstr(instr.dest, instr.op, str(a1), str(a2) if a2 else None))
    block.instrs = new_instrs
```

#### 3) 死代码消除（反向扫描）

```python
def dead_code_elimination(block):
    """基于活跃性的死代码消除（反向扫描）"""
    live = set()
    result = []
    for instr in reversed(block.instrs):
        if instr.op in ('=', '+', '-', '*') and instr.dest not in live:
            continue  # 死赋值，删除
        result.append(instr)
        live.discard(instr.dest)
        if instr.arg1: live.add(instr.arg1)
        if instr.arg2: live.add(instr.arg2)
    block.instrs = list(reversed(result))
```

#### 4) 公共子表达式消除

```python
def cse_block(block):
    """基本块内公共子表达式消除"""
    expr_map = {}  # (op, arg1, arg2) → dest_var
    new_instrs = []
    killed = set()  # 本块内被重定义的变量
    for instr in block.instrs:
        if instr.op in ('+', '-', '*'):
            # 检查是否涉及被 kill 的变量
            key = (instr.op, instr.arg1, instr.arg2)
            if key in expr_map and key[1] not in killed and key[2] not in killed:
                new_instrs.append(TACInstr(instr.dest, '=', expr_map[key], None))
            else:
                expr_map[key] = instr.dest
                new_instrs.append(instr)
            killed.add(instr.dest)
        else:
            # 赋值或跳转：杀死相关的表达式
            if instr.op == '=': killed.add(instr.dest)
            new_instrs.append(instr)
    block.instrs = new_instrs
```

#### 5) 循环不变量外提

```python
def licm(cfg):
    """循环不变量外提"""
    loops = find_natural_loops(cfg)
    for loop in loops:
        header, blocks = loop
        preheader = create_preheader(cfg, header)
        # 找所有块内的循环不变量语句
        invariants = []
        variables_def_in_loop = set()
        for blk in blocks:
            for instr in blk.instrs:
                if instr.dest:
                    variables_def_in_loop.add(instr.dest)
        for blk in blocks:
            for instr in blk.instrs:
                if is_invariant(instr, variables_def_in_loop):
                    invariants.append((blk, instr))
        # 外提到 preheader
        for blk, instr in invariants:
            blk.instrs.remove(instr)
            preheader.instrs.append(instr)
```

---

## 8. 编译器后端完整流水线

```
          中间表示（TAC / SSA）
                │
                ▼
         自动化优化
    ┌───────────┴───────────┐
    │  局部优化（块内）       │
    │  ├ 常量折叠+传播       │
    │  ├ 死代码消除          │
    │  ├ 公共子表达式消除     │
    │  └ 代数简化            │
    │                       │
    │  全局优化（跨块）       │
    │  ├ 数据流分析           │
    │  ├ 循环不变量外提       │
    │  ├ 强度削弱             │
    │  └ 归纳变量删除         │
    └───────────┬───────────┘
                │
                ▼
          指令选择（树模式匹配）
                │
                ▼
          寄存器分配（图染色）
                │
                ▼
          指令调度（列表调度）
                │
                ▼
          窥孔优化
                │
                ▼
          目标代码输出
```

---

## 关键总结

| 概念 | 要点 |
|------|------|
| **基本块** | 单入口单出口的连续指令序列 |
| **CFG** | 基本块为节点，控制流为边 |
| **常量折叠+传播** | 编译期求值，迭代到不动点 |
| **死代码消除** | 删除"写了但没人读"的赋值 |
| **CSE** | 相同表达式算一次，后续复用 |
| **数据流框架** | 方向 + 交汇操作 + 转移函数 |
| **活跃变量** | 后向分析，用于寄存器分配和 DCE |
| **到达定义** | 前向分析，用于常量传播 |
| **可用表达式** | 前向+交集，用于全局 CSE |
| **LICM** | 不变量提到循环前 |
| **强度削弱** | 乘法→加法，移位替换 |
| **归纳变量** | 同步变化的变量可删一个 |
| **图染色** | K 种颜色给干涉图节点着色 |
| **溢出** | 着色不上的变量存内存 |
| **指令选择** | 树模式匹配 + DP 找最优覆盖 |
| **指令调度** | 重排指令减少流水线停顿 |

---

## 扩展阅读

- **Dragon Book** (Compilers: Principles, Techniques, and Tools) — 第 8-10 章
- **Engineering a Compiler** (Cooper & Torczon) — 第 9-13 章
- **LLVM 的优化 passes 源码** — 工业级优化器参考
- **SSA Book** (Appel) — SSA 形式的理论深入

# 逆向工程 — 第七课：硬件断点（调试寄存器 DR0-DR7）

## 核心能力
1. ✅ 调试寄存器编程：DR0-DR3 断点地址 + DR7 控制寄存器的组合编码
2. ✅ Thread Context 读写：GetThreadContext/SetThreadContext 设置 DR 寄存器
3. ✅ 三种触发类型：EXECUTE (00), WRITE (01), READ/WRITE (11)
4. ✅ 4种长度（1/2/4/8 字节）
5. ✅ DR6 状态解析读取命中 slot

## DR 寄存器详解

### DR7 编码格式
```
Bit layout (x64):
  0-1:  L0/G0  — Local/Global enable for DR0
  2-3:  L1/G1  — DR1
  4-5:  L2/G2  — DR2  
  6-7:  L3/G3  — DR3
  8-9:  LE/GE  — Local/Global Exact (data BP precision)
  13:   GD     — General Detect (trap on mov to DR regs)
  16-17: R/W0  — Type for DR0 (00=EXEC,01=WRITE,10=I/O,11=RW)
  18-19: LEN0  — Length for DR0 (00=1B,01=2B,11=4B,10=8B)
  20-21: R/W1  — DR1
  22-23: LEN1  — DR1
  24-25: R/W2  — DR2
  26-27: LEN2  — DR2
  28-29: R/W3  — DR3
  30-31: LEN3  — DR3
```

### 软件断点 vs 硬件断点

| 特性 | 软件断点 (0xCC) | 硬件断点 (DRx) |
|------|----------------|---------------|
| 修改代码 | ✅ 写入 INT3 | ❌ 不修改 |
| 反检测 | 易被检测（CRC/校验和） | 难检测（但可查 DR7） |
| 数量 | 无限 | 最多4个 |
| 数据监控 | ❌ | ✅ WRITE/RW |
| 跨线程 | 所有线程共享 | 线程局部 |

### DR6 的陷阱
DR6 不是 `0` 就表示没有命中。Windows 永远不会清零 DR6，
它只会**设置**命中位（位0-3）。所以每次处理完断点后**必须手动清零**。

```python
# 正确的处理流程
ctx_ba = bytearray(ctx_raw)
dr6 = struct.unpack_from("<Q", ctx_ba, OFF_DR6)[0]
if dr6 & 0xF:
  hit_slot = dr6 & 1  # 或其他位
  # ...处理断点...
  struct.pack_into("<Q", ctx_ba, OFF_DR6, dr6 & ~0xF)  # 清掉低位
```

## 约束条件
- L (Local) flag = 断点只对当前线程有效，线程切换后失效
- G (Global) flag = 断点对所有线程有效，但系统不会在线程切换时自动传播
- 需要在每个新线程（LOAD_DLL/CREATE_THREAD 事件）上重新设置
- x64 下 `CONTEXT_DEBUG_REGISTERS` 必须包含在 context_flags 中

## 代码示例

```python
# 设置硬件执行断点
ctx = read_ctx(tid)
ctx_ba = bytearray(ctx)
# DR0 = 地址
struct.pack_into("<Q", ctx_ba, OFF_DR0, target_addr)
# DR7 = L0 | LE | GE | R/W0(=00) | LEN0(=00)
struct.pack_into("<Q", ctx_ba, OFF_DR7, 
    (1 << 0) | (1 << 8) | (1 << 9))
write_ctx(tid, bytes(ctx_ba))
```

## 下节 (re_08) 计划
- 消息钩子 DLL / 代码注入
- 远程线程创建 (CreateRemoteThread)
- 实际应用：HOOK API 或 修改目标进程行为

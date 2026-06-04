# 性能优化 #5：异步 I/O 与零拷贝

> 2026-05-17
> 前置：编译优化 #4

## 1. I/O 是真正的瓶颈

```
CPU 操作：    1 次 L1 缓存命中     = 1ns
一次 syscall（write）：             ≈ 200-500ns（上下文切换成本）
一次 SSD 随机读：                   ≈ 10-100μs
一次 HDD 寻道：                     ≈ 10ms
一次网络请求（同机房延迟）：          ≈ 0.5-1ms
一次网络请求（跨洲）：              ≈ 100-300ms

结论：I/O 比计算慢几个量级
       优化 I/O > 优化计算
```

## 2. 异步 I/O

### 2.1 阻塞 I/O vs 非阻塞 I/O

```python
# ❌ 同步阻塞
def backtest_all():
    data = load_csv("data.csv")     # I/O 阻塞，等待磁盘
    result = expensive_compute(data) # CPU 密集计算
    save_result(result)              # I/O 阻塞，等待磁盘
# 总时间 = I/O 时间 + 计算时间（串行）

# ✅ 异步（多线程 I/O + 计算并行）
import asyncio
import aiofiles

async def backtest_async():
    # I/O 和计算重叠
    data, result = await asyncio.gather(
        load_csv_async("data.csv"),     # 后台 I/O
        precompute_configs()            # 前台计算
    )
    result = await compute_and_save(data)
    
async def compute_and_save(data):
    # 计算和写入 I/O 重叠
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        # CPU 密集型放到线程池（不阻塞 event loop）
        result = await loop.run_in_executor(pool, expensive_compute, data)
    async with aiofiles.open("result.csv", "w") as f:
        await f.write(result)
    return result
```

### 2.2 Python asyncio 的适用边界

```
✅ 适用：
  大量网络请求（行情推送、多个交易所 API）
  文件读取（非阻塞 I/O）

❌ 不适用：
  CPU 计算密集型（需要 ThreadPool 才能发挥）
  单个瓶颈 I/O（asyncio 只是解决并发等待，不能加速一次磁盘读）
```

### 2.3 Rust 的 async I/O

```rust
use tokio::fs::File;
use tokio::io::AsyncWriteExt;

async fn save_strategy_result(path: &str, data: &[u8]) -> Result<(), Error> {
    let mut file = File::create(path).await?;
    file.write_all(data).await?;   // 异步写入（不阻塞当前线程）
    file.sync_all().await?;        // 异步 fsync
    Ok(())
}

#[tokio::main]
async fn main() {
    // 多个文件同时写
    let handles: Vec<_> = results.iter().map(|(path, data)| {
        tokio::spawn(save_strategy_result(path, data))
    }).collect();
    
    for h in handles {
        h.await.unwrap()?;
    }
}
```

## 3. 内存映射文件（mmap）

mmap 让文件的内容像内存一样访问——免去 `read/write` syscall 和数据复制。

```python
# ❌ 传统读取
with open("large_data.bin", "rb") as f:
    data = f.read()         # 2 次复制：磁盘→内核缓冲区→用户缓冲区
# read syscall + context switch

# ✅ mmap 直接映射
import mmap

with open("large_data.bin", "r+b") as f:
    mmapped = mmap.mmap(f.fileno(), 0)  # 文件直接映射到地址空间
    # 像内存一样访问
    print(mmapped[:4096])               # 首次访问触发缺页→从磁盘载入
    mmapped[0:4] = b'\x00\x00\x00\x00'  # 直接写，脏页→后台刷盘
    mmapped.close()
```

**mmap 在量化系统中的适用场景**：

```
✅ 大文件读取（回测 10 年 tick 数据 → 用 mmap 延迟加载）
✅ 共享内存（多进程间的数据通道）

❌ 小文件（mmap 开销 > read 开销）
❌ 频繁写入（写放大 + 脏页刷盘不确定性）
```

## 4. 零拷贝

### 4.1 数据传输中的多次拷贝

传统网络传输路径：

```
磁盘 → 内核缓冲区（DMA）→ 用户缓冲区（CPU 复制）→ 内核缓冲区→
                                                        → 网卡（DMA）

共 4 次上下文切换 + 2 次数据复制
```

### 4.2 sendfile（零拷贝）

```c
// 从文件直接发送到 socket（绕过用户空间）
#include <sys/sendfile.h>

ssize_t n = sendfile(
    out_fd,     // 目标 socket
    in_fd,      // 源文件
    &offset,    // 偏移
    count       // 字节数
);
// 1 次系统调用完成，没有上下文切换
// DMA 直接从文件缓存 → 网卡
```

Rust 中的使用：

```rust
use tokio::io::copy;
use tokio::fs::File;
use tokio::net::TcpStream;

async fn serve_file(mut socket: TcpStream, path: &str) {
    let mut file = File::open(path).await.unwrap();
    // tokio 内部使用 sendfile（如果平台支持）
    tokio::io::copy(&mut file, &mut socket).await.unwrap();
}
```

### 4.3 减少复制：NumPy 中的视图 vs 副本

```python
arr = np.array([1, 2, 3, 4, 5])

# ❌ 副本（新分配内存）
copy = arr[1:4].copy()  # 复制 3 个元素
copy[0] = 99             # 不影响原数组

# ✅ 视图（零复制，共享内存）
view = arr[1:4]          # 不复制！strides 技巧
view[0] = 99             # arr[1] 也被改为 99

# 什么时候产生视图：
#   slice（arr[1:4]）
#   transpose（arr.T）
#   reshape（一般情况下）
# 什么时候必须副本：
#   非连续内存（transpose + flatten 等操作）
```

## 5. 量化引擎中的 I/O 优化

### 5.1 数据加载

```python
# ❌ 每次回测都加载全部数据
def backtest(strategy, data_path):
    df = pd.read_csv(data_path)    # ~500ms 每次
    run_strategy(df, strategy)

# ✅ 缓存到内存（回测参数搜索时复用）
_data_cache = {}

def load_data(data_path: str) -> pd.DataFrame:
    if data_path not in _data_cache:
        _data_cache[data_path] = pd.read_csv(data_path)
    return _data_cache[data_path].copy()  # 返回副本避免污染
```

### 5.2 二进制格式

```python
# ❌ CSV（文本解析开销大）
df = pd.read_csv("kline_data.csv")
# 每次解析: 字符串→float 转换，内存膨胀 2-3x

# ✅ Parquet（列式二进制格式）
df = pd.read_parquet("kline_data.parquet")
# 加载快 5-10x，压缩存储，Schema 内嵌

# ✅ NumPy .npy 格式（最快）
close_prices = np.load("close.npy")
# 纯二进制加载，零解析，mmap 可用
```

### 5.3 预计算持久化

```python
# 预计算常用指标并缓存
import joblib

def get_precomputed_features(code: str) -> dict:
    cache_path = f"cache/{code}_features.joblib"
    try:
        return joblib.load(cache_path)
    except FileNotFoundError:
        data = load_and_compute(code)   # 第一次：全量计算
        joblib.dump(data, cache_path)   # 序列化到磁盘
        return data                     # 后续：反序列化（快 10-100x）
```

## 总结

```
I/O 优化优先级：
  1. 减少 I/O 次数（缓存、批量、预加载）
  2. 减少数据复制（mmap、视图、sendfile）
  3. 减少上下文切换（异步、epoll/iouring）
  4. 使用高效格式（Parquet > CSV）

量化引擎具体建议：
  K线数据 → Parquet（列式+压缩+Schema）
  中间结果 → joblib 序列化缓存
  大文件 → mmap 延迟加载
  计算+IO → 异步+EventLoop 重叠
```

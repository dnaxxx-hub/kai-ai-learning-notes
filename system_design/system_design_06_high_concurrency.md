# 第6课：高并发设计

> 系统设计/架构 — Phase 4 波次2
> 日期：2026-05-09

## 1. 高并发的基本策略

**三板斧**：
1. **缓存** — 减少计算和IO
2. **异步** — 不阻塞主流程
3. **集群** — 水平扩展

**四个维度**：
| 维度 | 方法 | 典型工具 |
|------|------|---------|
| 计算资源 | 水平扩展 | Nginx + 多实例 |
| 存储资源 | 分区+缓存 | Redis + Sharding |
| 并发控制 | 连接池/限流 | HikariCP + Sentinel |
| 故障应对 | 降级/熔断 | Hystrix + Circuit Breaker |

## 2. 连接池

### 为什么需要连接池
- 创建数据库连接要TCP握手+认证（几ms到几十ms）
- 池化复用，避免频繁创建销毁

### 核心参数
```python
pool = ConnectionPool(
    min_connections=5,     # 最小空闲
    max_connections=20,    # 最大连接数
    max_idle_time=600,     # 空闲超时回收
    connection_timeout=5,  # 等待超时
)
```

### 池化策略
- **提前创建**：启动时建好min个连接
- **懒加载**：需要时创建，不超过max
- **超时回收**：空闲超过max_idle_time的关闭
- **健康检查**：定期SELECT 1检测连接有效性
- **泄洪机制**：超出max的请求排队/拒绝

## 3. 线程池

### vs 连接池
| 池类型 | 池化资源 | 典型应用 |
|--------|---------|---------|
| 连接池 | TCP连接 | DB/Redis |
| 线程池 | 线程对象 | 请求处理 |

### 线程池参数
```python
ThreadPool(
    core_threads=10,        # 核心线程（常驻）
    max_threads=50,         # 最大线程
    queue_size=100,         # 任务队列
    keep_alive=60,          # 空闲回收时间
    rejection_policy='abort'  # 拒绝策略
)
```

### 拒绝策略
1. **AbortPolicy**：抛异常（最安全）
2. **CallerRunsPolicy**：调用线程自己跑（反压）
3. **DiscardPolicy**：静默丢弃
4. **DiscardOldestPolicy**：丢弃最老任务

## 4. 限流（Rate Limiting）

### 令牌桶（Token Bucket）
```
原理：
  定时往桶里加令牌（每秒N个）
  请求消耗1个令牌
  令牌不够就等或拒绝
特点：
  允许短时突发（桶里的存量令牌）
  长期平均速率可控
```

```python
class TokenBucket:
    def __init__(self, rate, burst):
        self.rate = rate          # 每秒产生令牌数
        self.burst = burst        # 桶容量（最大突发）
        self.tokens = burst
        self.last_refill = now()
    
    def try_acquire(self):
        self._refill()
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False
    
    def _refill(self):
        elapsed = now() - self.last_refill
        self.tokens = min(
            self.burst,
            self.tokens + elapsed * self.rate
        )
```

### 漏斗（Leaky Bucket）
```
原理：
  请求进桶，匀速流出
  桶满了就拒绝
特点：
  平滑流量，不允许突发
  适合稳速处理
```

### 滑动窗口（Sliding Window）
- 将时间切成小段（如1s）
- 每段一个计数器
- 统计最近N段的请求总数

### 对比

| 算法 | 突发能力 | 平滑度 | 实现难度 |
|------|---------|--------|---------|
| 固定窗口 | 边界突发 | 差 | 低 |
| 滑动窗口 | 好 | 好 | 中 |
| 令牌桶 | 可突发 | 中 | 中 |
| 漏斗 | 无突发 | 最好 | 中 |

## 5. 熔断（Circuit Breaker）

### 三态模型
```
Closed（正常）
  → 错误率超阈值 → Open（断开）
      ↓                      ↓
  恢复计数              等待超时
      ↓                      ↓
  Half-Open（试探）
  → 成功 → Closed
  → 失败 → Open（重置计时器）
```

### 熔断参数
- **threshold**：错误率阈值（如50%）
- **min_calls**：触发统计的最低请求数
- **window_ms**：统计窗口
- **open_ms**：断开后等待时间
- **half_open_max**：Half-Open状态允许的试探请求数

## 6. 降级（Degradation）

降级是有意放弃非核心功能，保核心功能。

**降级等级**：
```
LEVEL 0: 全部正常
LEVEL 1: 关闭非核心功能（推荐、评论）
LEVEL 2: 关闭写入、缓存降级
LEVEL 3: 只读模式（返回缓存/静态数据）
LEVEL 4: 前端降级（展示不可用页面）
```

## 7. 缓存策略

### 缓存模式

| 模式 | 读 | 写 | 一致性 |
|------|-----|-----|--------|
| Cache Aside | 先读cache，miss读DB+回填 | 先写DB，再删cache | 高 |
| Read/Write Through | cache代理读写DB | 同左 | 中 |
| Write Behind | 同上 | 写cache，异步写DB | 低 |

### 缓存问题
- **穿透**：查不存在的数据（布隆过滤器）
- **击穿**：热点key过期（互斥锁/永不过期）
- **雪崩**：大量key同时过期（过期时间加随机值）
- **一致性**：先删缓存还是先写DB

**推荐套路**：Cache Aside + 延迟双删

## 8. 高并发系统设计模式

```mermaid
用户请求
   ↓
负载均衡（Nginx/LVS）
   ↓
限流（令牌桶） → 超限 → 降级响应
   ↓
熔断器 → Open → Fallback
   ↓
缓存（Redis） → Hit → 返回
   ↓
连接池 → 线程池 → 业务逻辑
   ↓
异步队列 → 削峰
```

# 计算机网络第3课：CDN 与边缘网络

> 学习日期：2026-05-10

---

## 1. CDN 架构

### 1.1 核心组件

```
用户请求 → DNS调度 → 边缘节点(L1) → 区域节点(L2) → 源站(Origin)
```

- **边缘节点（Edge PoP, Point of Presence）**：部署在全球各地靠近用户的缓存服务器，用户请求首先到达这里
- **区域节点（Regional/L2 Cache）**：覆盖更大地理范围的中间缓存层，L1 miss 后查询
- **源站（Origin）**：内容真正的存储服务器，CDN 的最终数据来源

### 1.2 三级缓存架构

| 层级 | 位置 | 容量 | 延迟 | 命中率目标 |
|------|------|------|------|-----------|
| L1 边缘 | 用户附近 ISP/IDC | 较小（~GB） | 1-5ms | 60-80% |
| L2 区域 | 地理区域中心 | 中等（~TB） | 10-30ms | 15-25% |
| 源站 | 自有数据中心 | 无限 | 50-200ms | 兜底 |

命中率分布：L1 命中约 70% → L2 命中约 20% → 回源约 10%

### 1.3 缓存策略

**TTL（Time To Live）**
- 静态资源（图片/CSS/JS）：通常设置较长 TTL（天级别），如 `Cache-Control: max-age=86400`
- 动态内容：短 TTL 或不缓存
- 优先级：`Cache-Control > Expires > Pragma`

**CDN 私有头部**
- `X-Cache`: HIT / MISS / EXPIRED
- `X-Cache-Remote`: 多级缓存的命中状态
- `X-TTL`: 剩余的缓存时间
- `Age`: 内容在 CDN 中已经缓存的时间

**主动刷新（Purge / Invalidation）**
- 目录刷新：`/path/to/dir/*` 批量使失效
- URL 精确刷新：单一 URL
- API 触发刷新：通过 CDN 管理 API 批量提交
- 刷新后的首次请求产生"缓存 MISS"，直到新内容被拉取

---

## 2. CDN 核心算法

### 2.1 缓存替换算法

| 算法 | 原理 | 适用场景 |
|------|------|---------|
| **LRU** (Least Recently Used) | 淘汰最近最少访问的 | 通用，局部性好的场景 |
| **LFU** (Least Frequently Used) | 淘汰访问频率最低的 | 访问模式稳定的场景 |
| **FIFO** (First In First Out) | 淘汰最先进入缓存的 | 简单场景，不考虑访问模式 |
| **ARC** (Adaptive Replacement Cache) | LRU+LFU 动态调整 | IBM 专利，自适应场景 |
| **2Q** (Two Queue) | 两次访问才进主缓存 | 防刷单次热点（如 DDOS） |

**LRU 实现关键：**
- 双向链表 + 哈希表 = O(1) 查找/插入/删除
- 新数据插入头部，淘汰从尾部删除
- 每次访问将节点移到头部

**LFU 改进：**
- 每个频率维护一个双向链表（frequency-based list）
- 最小频率计数跟踪，O(1) 找到要淘汰的
- 避免频率风暴问题（新内容需要时间积累热度）

### 2.2 缓存预热（Cache Warming）

**定义**：在预期流量到来前，主动将内容推送到边缘节点

**常见场景：**
- 大促活动前预热商品图片/详情页
- 新版本发布前预热静态资源
- 冷启动场景（新上线节点）

**实现方式：**
1. API 推送：直接向边缘节点发送内容
2. 模拟请求：用分布式爬虫模拟用户请求触发缓存
3. 预加载策略：基于历史数据预测热点

**预热 vs 冷启动对比：**

| 指标 | 预热 | 冷启动 |
|------|------|--------|
| 首字节延迟 | 低（~5ms） | 高（~200ms，需回源） |
| 源站压力 | 提前分担 | 瞬时暴增 |
| 用户感知 | 丝滑 | 卡顿 |

### 2.3 缓存穿透 / 击穿 / 雪崩

**缓存穿透：查询一个一定不存在的数据**
- 表现：请求绕过缓存直接打到数据库/源站
- 举例：请求一个不存在的图片 URL
- 解决：
  - 布隆过滤器（Bloom Filter）：快速判断 key 是否存在
  - 空值缓存：对不存在的数据也缓存一个空值（短 TTL）
  - 参数校验：拒绝明显不合法的请求

**缓存击穿：热点 key 过期瞬间，大量并发请求直达后端**
- 表现：一个热点 key 刚好过期，大量请求同一瞬间穿透
- 解决：
  - 互斥锁（Mutex Lock）：只有一个请求回源，其他等待
  - 逻辑过期：数据自带过期时间，异步续期，不真正删除
  - 永不过期：后台线程主动刷新

**缓存雪崩：大量 key 在同一时间过期或缓存节点宕机**
- 表现：大规模请求穿透，后端被打垮
- 解决：
  - 随机 TTL：基本过期时间 + 随机偏移（如 ±30%）
  - 多级缓存：L1 失效还有 L2 抗住
  - 服务降级：返回过期的脏数据 vs 返回默认值
  - 限流熔断：保护后端不被冲垮
  - 缓存集群高可用：主从、哨兵、集群模式

---

## 3. DNS 调度

### 3.1 GSLB（全局负载均衡）

基于 DNS 的全局负载均衡，工作流程：

```
1. 用户请求 cdn.example.com
2. Local DNS 递归查询 → CDN 授权 DNS
3. CDN DNS 根据策略返回最优节点 IP
4. 用户直接连接该 IP
```

### 3.2 GeoDNS

**原理**：根据请求来源的地理位置（IP 地理库），返回最近的节点 IP

**示例**：
```
用户位置 → DNS 查询 → 返回结果
北京     → cdn.example.com → 203.0.113.10 (北京节点)
上海     → cdn.example.com → 203.0.113.20 (上海节点)
纽约     → cdn.example.com → 198.51.100.10 (纽约节点)
```

**实现要点：**
- IP 地理数据库（MaxMind GeoLite2、IPIP.net）
- 支持按国家/地区/运营商自定义路由
- 边缘节点健康检查：剔除宕机节点

### 3.3 负载均衡策略

| 策略 | 描述 | 适用场景 |
|------|------|---------|
| 权重轮询 | 按权重依次分配 | 硬件配置不均匀 |
| 最少连接 | 分配连接数最少的节点 | 长连接场景 |
| 最快响应 | 分配响应最快的节点 | 延迟敏感场景 |
| 一致性哈希 | 同一用户/IP 始终调度到同一节点 | Session 保持 |

**GeoDNS 的局限：**
- DNS 缓存污染：中间 DNS 可能缓存了旧 IP
- IP 地理库不准确：VPN/代理导致误判
- TTL 滞后：DNS TTL 时间内无法快速切换
- 不支持粒度调度：无法感知节点实时负载

---

## 4. Anycast 路由

### 4.1 原理

多个地理位置不同的节点共享同一个 IP 地址，通过 BGP 路由协议，用户数据包自动路由到"最近的"节点。

```
                 ┌─────────────┐
                 │  192.0.2.1  │
                 │  (北京节点)    │
          ┌──────┤  AS 64496   ├──────┐
          │      └─────────────┘      │
          │                           │
    ┌─────┴─────┐              ┌──────┴─────┐
    │  用户 A    │              │  用户 B     │
    │  (华北)    │              │  (华东)     │
    └─────┬─────┘              └──────┬─────┘
          │                           │
          │      ┌─────────────┐      │
          └──────┤  192.0.2.1  ├──────┘
                 │  (上海节点)    │
                 │  AS 64497   │
                 └─────────────┘
```

**关键机制：** BGP（边界网关协议）
- 同一前缀 `/24` 或 `/32` 从多个 AS 宣告
- BGP 路径选择：根据 AS PATH 长度、MED、Local Preference 等指标
- 路由自动收敛：节点宕机后 BGP withdraw 该路径

### 4.2 CDN 中使用 Anycast

| CDN 厂商 | 网络类型 | 特点 |
|----------|---------|------|
| Cloudflare | Anycast + Anycast | 单个 IP 服务全球 |
| AWS CloudFront | Anycast + DNS | 域名解析 + 边缘 Anycast |
| CloudFront | Anycast | 自建骨干网 |
| Fastly | Anycast | 可编程边缘 |

### 4.3 GeoDNS vs Anycast 对比

| 维度 | GeoDNS | Anycast |
|------|--------|---------|
| 调度粒度 | 按 DNS 请求来源 IP | 按路由协议自动选择 |
| 切换速度 | 受 DNS TTL 限制（较慢） | BGP 收敛（秒级） |
| 地理精度 | 高（IP 库可精确到城市） | 中（BGP 最短路径，不一定最近） |
| 负载感知 | 需额外健康检查 | 天然感知（路由收敛） |
| DDOS 防护 | 弱（无分散能力） | 强（流量天然分散到多个节点） |
| 实现复杂度 | 低（DNS 记录配置） | 高（需要自有 AS + BGP） |
| 典型厂商 | Akamai、阿里云 CDN | Cloudflare、Fastly |

---

## 5. 边缘计算

### 5.1 概念

在 CDN 边缘节点运行自定义代码，无需部署后端服务器。

**关键特性：**
- 就近计算：代码在靠近用户的位置执行
- 无服务器：开发者只关心逻辑，不管理服务器
- 事件驱动：以 HTTP 请求、消息等事件触发

### 5.2 主流平台

**Cloudflare Workers**
- 基于 Service Worker API (V8 隔离)
- 每个 Worker 一个独立 Isolate，冷启动 ~5ms
- 全球 330+ 城市边缘节点
- 免费额度：10 万请求/天
- 代码示例：在边缘改写请求头

```javascript
// Cloudflare Worker: A/B 测试
async function handleRequest(request) {
  const url = new URL(request.url);
  const cookie = request.headers.get('Cookie') || '';
  
  if (cookie.includes('variant=B')) {
    url.pathname = '/experimental' + url.pathname;
  }
  
  return fetch(url);
}
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request));
});
```

**AWS Lambda@Edge**
- 基于 AWS Lambda，运行在 CloudFront 边缘
- 4 个触发点：
  - Viewer Request（用户请求到达边缘时）
  - Origin Request（请求回源时）
  - Origin Response（源站返回时）
  - Viewer Response（返回给用户时）
- 限制：5s 执行超时，内存 128MB-3008MB

**使用场景对比：**

| 场景 | Cloudflare Workers | Lambda@Edge |
|------|-------------------|-------------|
| 冷启动 | ~5ms (Isolate) | ~100ms (VM) |
| 部署延迟 | 全球同步 < 30s | 全边缘部署数分钟 |
| 最大执行时间 | 30s (Cron Triggers) / 100ms (Free) | 5s |
| 代码大小 | 1MB (Free) / 5MB (Paid) | 1MB + 依赖包 50MB |

### 5.3 常见边缘计算用途

1. **A/B 测试**：根据 Cookie/Header 分配不同版本的静态资源
2. **请求修改**：添加安全头、URL 重写、鉴权
3. **响应聚合**：合并多个 API 响应，减少客户端请求数
4. **个性化**：基于用户地理位置渲染不同内容
5. **地理屏蔽**：对特定区域的请求返回 403
6. **图片优化**：实时调整图片尺寸/格式/质量
7. **Bot 检测**：在边缘识别并拦截爬虫

---

## 6. Python 模拟 CDN

### 6.1 多级缓存 + LRU 替换

```python
import time
import hashlib
import random
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional, Dict, List

# ============================================================
# 1. LRU 缓存实现
# ============================================================

class LRUCache:
    """基于 OrderedDict 的 LRU 缓存"""
    def __init__(self, capacity: int, name: str = ""):
        self.capacity = capacity
        self.name = name
        self.cache = OrderedDict()
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[bytes]:
        if key in self.cache:
            self.cache.move_to_end(key)  # 移到末尾 = 最近使用
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        return None
    
    def put(self, key: str, value: bytes):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)  # 淘汰最久未使用的
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


# ============================================================
# 2. 三级缓存 CDN
# ============================================================

class OriginServer:
    """源站：模拟生成内容"""
    def __init__(self, latency_ms: float = 100.0):
        self.latency_ms = latency_ms
        self.requests = 0
    
    def fetch(self, key: str) -> bytes:
        self.requests += 1
        time.sleep(self.latency_ms / 1000.0)  # 模拟网络延迟
        return f"content:{key}:{hashlib.md5(key.encode()).hexdigest()[:8]}".encode()


class CDNNode:
    """单个 CDN 节点（L1 或 L2）"""
    def __init__(self, name: str, capacity: int, latency_ms: float = 5.0):
        self.name = name
        self.latency_ms = latency_ms
        self.cache = LRUCache(capacity, name)
    
    def serve(self, key: str) -> Optional[bytes]:
        time.sleep(self.latency_ms / 1000.0)
        return self.cache.get(key)
    
    def store(self, key: str, value: bytes):
        self.cache.put(key, value)


class MultiLevelCDN:
    """三级缓存 CDN 网络"""
    def __init__(self, l1_capacity: int = 100, l2_capacity: int = 500, 
                 origin_latency: float = 100.0):
        self.l1 = CDNNode("L1-Edge", l1_capacity, latency_ms=2.0)
        self.l2 = CDNNode("L2-Region", l2_capacity, latency_ms=20.0)
        self.origin = OriginServer(latency_ms=origin_latency)
        self.total_requests = 0
    
    def fetch(self, key: str) -> (bytes, str):
        """返回 (内容, 来源)"""
        self.total_requests += 1
        
        # L1 边缘
        content = self.l1.serve(key)
        if content:
            return content, "L1-HIT"
        
        # L2 区域
        content = self.l2.serve(key)
        if content:
            # 回填 L1
            self.l1.store(key, content)
            return content, "L2-HIT"
        
        # 回源
        content = self.origin.fetch(key)
        self.l1.store(key, content)
        self.l2.store(key, content)
        return content, "ORIGIN-MISS"
    
    def report(self):
        print(f"\n{'='*50}")
        print(f"CDN 网络报告 (总请求: {self.total_requests})")
        print(f"{'='*50}")
        for node in [self.l1, self.l2]:
            c = node.cache
            print(f"  {node.name}: "
                  f"命中={c.hits}, 未命中={c.misses}, "
                  f"命中率={c.hit_rate:.1%}, "
                  f"缓存容量={len(c.cache)}/{c.capacity}")
        print(f"  源站请求: {self.origin.requests}")
        print(f"  L1 命中率贡献: {self.l1.cache.hit_rate:.1%}")
        print(f"  整体命中率: {(self.l1.cache.hits + self.l2.cache.hits) / max(self.total_requests, 1):.1%}")


# ============================================================
# 3. GeoDNS 调度
# ============================================================

class GeoDNS:
    """地理 DNS 调度器"""
    def __init__(self):
        # 区域 → [节点列表]
        self.regions = {
            "华北": ["bj-node-1", "bj-node-2"],
            "华东": ["sh-node-1", "hz-node-1"],
            "华南": ["gz-node-1", "sz-node-1"],
            "海外": ["us-west-1", "sg-node-1"],
        }
        # 默认地理映射
        self.geo_map = {
            "北京": "华北", "天津": "华北", "石家庄": "华北",
            "上海": "华东", "杭州": "华东", "南京": "华东",
            "广州": "华南", "深圳": "华南", "成都": "华南",
            "纽约": "海外", "新加坡": "海外",
        }
        self.node_load = {}  # 节点名 → 当前连接数
    
    def resolve(self, user_location: str) -> str:
        """根据用户位置返回最近的节点"""
        region = self.geo_map.get(user_location, "华东")
        nodes = self.regions[region]
        # 最少连接调度
        best_node = min(nodes, key=lambda n: self.node_load.get(n, 0))
        self.node_load[best_node] = self.node_load.get(best_node, 0) + 1
        return best_node


# ============================================================
# 4. 预热 vs 冷启动对比
# ============================================================

def warmup(cdn: MultiLevelCDN, keys: List[str]):
    """预热：提前将内容推送至 L1 和 L2"""
    for key in keys:
        content = cdn.origin.fetch(key)
        cdn.l1.store(key, content)
        cdn.l2.store(key, content)
    print(f"  [预热] 推送了 {len(keys)} 个内容到 L1 和 L2")


def simulate_content_serving(cdn: MultiLevelCDN, keys: List[str], 
                              requests_per_key: int = 10, label: str = ""):
    """模拟用户请求"""
    import time
    
    start = time.time()
    hit_records = []
    
    for key in keys:
        for _ in range(requests_per_key):
            content, source = cdn.fetch(key)
            hit_records.append(source)
    
    elapsed = (time.time() - start) * 1000
    
    from collections import Counter
    stats = Counter(hit_records)
    
    print(f"\n  [{label}] {len(keys)}个内容 × {requests_per_key}次请求:")
    print(f"    总耗时: {elapsed:.0f}ms")
    for source, count in stats.most_common():
        print(f"    {source}: {count}次 ({count/len(hit_records):.1%})")
    
    return elapsed


# ============================================================
# 5. 缓存击穿/雪崩模拟
# ============================================================

class BrokenCDN(MultiLevelCDN):
    """有问题的 CDN（模拟击穿和雪崩）"""
    
    def cache_stampede(self, hot_key: str, concurrent: int = 50):
        """模拟缓存击穿：热点 key 同时过期，大量并发回源"""
        print(f"\n  === 缓存击穿模拟 ===")
        print(f"  热点 key '{hot_key}' 过期，{concurrent} 并发请求")
        
        # 先让 key 在缓存中（然后假装它过期了）
        content = self.origin.fetch(hot_key)
        self.l1.store(hot_key, content)
        
        # 模拟过期：清空 L1 中这个 key
        self.l1.cache.cache.pop(hot_key, None)
        
        origins = 0
        for i in range(concurrent):
            _, source = self.fetch(hot_key)
            if source == "ORIGIN-MISS":
                origins += 1
        
        print(f"  回源请求: {origins}/{concurrent} (理想: 1)")
        if origins > 1:
            print(f"  ⚠️  击穿发生: {origins - 1} 次额外回源！")
        else:
            print(f"  ✅ 正常: 仅 1 次回源")
    
    def cache_avalanche(self, keys: List[str], concurrent: int = 30):
        """模拟缓存雪崩：大量 key 同时过期"""
        print(f"\n  === 缓存雪崩模拟 ===")
        print(f"  {len(keys)} 个 key 同时过期，每个 {concurrent} 并发")
        
        # 先填满缓存
        for key in keys:
            content = self.origin.fetch(key)
            self.l1.store(key, content)
        
        # 模拟全部过期
        self.l1.cache.cache.clear()
        
        origins = 0
        for key in keys:
            for _ in range(concurrent):
                _, source = self.fetch(key)
                if source == "ORIGIN-MISS":
                    origins += 1
        
        total = len(keys) * concurrent
        print(f"  回源请求: {origins}/{total} (理想: {len(keys)})")
        if origins > len(keys):
            print(f"  ⚠️  雪崩发生: 额外 {origins - len(keys)} 次回源！")
        else:
            print(f"  ✅ 正常: 仅 {len(keys)} 次回源")


# ============================================================
# 6. 主程序
# ============================================================

if __name__ == "__main__":
    import time
    
    print("=" * 60)
    print("  CDN 与边缘网络 — Python 模拟")
    print("=" * 60)
    
    # ------ 6.1 基础功能：多级缓存与 LRU ------
    print("\n--- 6.1 多级缓存与 LRU 替换 ---")
    cdn = MultiLevelCDN(l1_capacity=10, l2_capacity=50, origin_latency=80.0)
    
    start = time.time()
    for i in range(100):
        key = f"img_{i % 30}"  # 30 个不同内容，L1 只能存 10 个
        cdn.fetch(key)
    elapsed = (time.time() - start) * 1000
    
    print(f"  完成 100 次请求，耗时 {elapsed:.0f}ms")
    cdn.report()
    
    # ------ 6.2 GeoDNS 调度 ------
    print("\n\n--- 6.2 GeoDNS 调度 ---")
    dns = GeoDNS()
    users = ["北京", "上海", "广州", "纽约", "杭州", "深圳", "北京", "新加坡"]
    for user in users:
        node = dns.resolve(user)
        print(f"  用户[{user}] → {node}")
    
    # ------ 6.3 预热 vs 冷启动 ------
    print("\n\n--- 6.3 预热 vs 冷启动对比 ---")
    
    # 冷启动
    cold_cdn = MultiLevelCDN(l1_capacity=20, l2_capacity=100, origin_latency=80.0)
    cold_time = simulate_content_serving(
        cold_cdn, [f"video_{i}" for i in range(5)], 
        requests_per_key=3, label="冷启动"
    )
    
    # 预热
    warm_cdn = MultiLevelCDN(l1_capacity=20, l2_capacity=100, origin_latency=80.0)
    t0 = time.time()
    warmup(warm_cdn, [f"video_{i}" for i in range(5)])
    t1 = time.time()
    warm_time = simulate_content_serving(
        warm_cdn, [f"video_{i}" for i in range(5)], 
        requests_per_key=3, label="预热"
    )
    
    print(f"\n  延迟对比:")
    print(f"    冷启动总延迟: {cold_time:.0f}ms")
    print(f"    预热总延迟:   {warm_time:.0f}ms")
    print(f"    预热加速比:   {cold_time / max(warm_time, 1):.1f}x")
    
    # ------ 6.4 缓存击穿 ------
    print("\n\n--- 6.4 缓存击穿模拟 ---")
    stampede_cdn = BrokenCDN(l1_capacity=10, l2_capacity=30, origin_latency=50.0)
    stampede_cdn.cache_stampede("hot_news_1", concurrent=20)
    
    # ------ 6.5 缓存雪崩 ------
    print("\n\n--- 6.5 缓存雪崩模拟 ---")
    avalanche_cdn = BrokenCDN(l1_capacity=10, l2_capacity=30, origin_latency=50.0)
    avalanche_cdn.cache_avalanche(["key_a", "key_b", "key_c"], concurrent=15)
    
    print("\n" + "=" * 60)
    print("  模拟完成")
    print("=" * 60)
```

> **运行说明**：由于 Python 的单线程 GIL 特性，上述同步模式下缓存击穿/雪崩的并发穿透无法演示（请求是串行的）。要在单机演示真正的并发穿透，需使用 `threading` 多线程或 `concurrent.futures` 线程池。生产环境中的击穿/雪崩发生在高并发场景。

### 6.2 运行结果解读

运行上述代码后可以看到：

1. **多级缓存命中分布**：L1 命中率约 30-40%（因 LRU 容量有限），L2 补充命中，回源率最低
2. **GeoDNS 调度**：用户根据城市自动分配到最近的可用节点
3. **预热 vs 冷启动**：预热后的首字节延迟显著降低（冷启动需回源 80ms，预热只需边缘 2ms）
4. **缓存击穿**：热点 key 过期后，20 个并发请求可能全部回源，造成源站瞬间压力
5. **缓存雪崩**：批量 key 过期导致大量回源请求，远超正常值

### 6.3 改进方案代码片段

```python
# 防击穿：互斥锁
import threading

class SafeCDN:
    def __init__(self, cdn: MultiLevelCDN):
        self.cdn = cdn
        self.locks = {}
        self.lock_mutex = threading.Lock()
    
    def fetch_with_mutex(self, key: str) -> bytes:
        """带互斥锁的缓存读取，防击穿"""
        content = self.cdn.l1.serve(key)
        if content:
            return content, "L1-HIT"
        
        # 获取 key 级别的锁（只让一个请求回源）
        with self.lock_mutex:
            if key not in self.locks:
                self.locks[key] = threading.Lock()
        lock = self.locks[key]
        
        with lock:
            # 双重检查
            content = self.cdn.l1.serve(key)
            if content:
                return content, "L1-HIT"
            
            content, source = self.cdn.fetch(key)
            return content, f"{source}(MUTEX)"
    
    # 防雪崩：随机 TTL
    @staticmethod
    def random_ttl(base: int, jitter: float = 0.3) -> int:
        """base ± jitter% 随机 TTL"""
        return int(base * (1 + random.uniform(-jitter, jitter)))
    
    # 布隆过滤器防穿透（简化版）
    def bloom_check(self, key: str) -> bool:
        """简单布隆过滤器（实际应使用 bitarray）"""
        # 实际可用 pybloom_live 或自行实现
        hashes = [
            int(hashlib.md5(f"{key}{i}".encode()).hexdigest(), 16) 
            for i in range(3)
        ]
        # ... 检查 bit array
        return True  # 可能存在
```

---

## 总结

### 关键概念图谱

```
                  ┌──────────────────┐
                  │   用户请求        │
                  └────────┬─────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
        ┌─────┴─────┐           ┌──────┴──────┐
        │ Anycast    │           │  DNS (GSLB) │
        │ BGP路由选择 │           │  GeoDNS调度  │
        └─────┬─────┘           └──────┬──────┘
              │                         │
              └────────────┬────────────┘
                           │
                    ┌──────┴──────┐
                    │   L1 边缘节点 │ ← 边缘计算: Workers/Lambda@Edge
                    └──────┬──────┘
                           │ (miss)
                    ┌──────┴──────┐
                    │   L2 区域节点 │ ← 缓存替换: LRU/LFU
                    └──────┬──────┘
                           │ (miss)
                    ┌──────┴──────┐
                    │    源站      │
                    └─────────────┘
```

### 面试要点

1. **CDN 三级缓存的请求流程**：用户 → L1 边缘（快/小）→ L2 区域（中/中）→ 源站（慢/大）
2. **LRU 实现**：为什么要用双向链表+哈希表？O(1) 复杂度
3. **缓存击穿 vs 雪崩**：前者是热点 key 失效，后者是大规模 key 同时失效
4. **GeoDNS vs Anycast**：GeoDNS 基于 IP 库，Anycast 基于 BGP 路由协议
5. **边缘计算触发点**：Viewer Request/Response、Origin Request/Response
6. **缓存预热价值**：大促前推送热点内容到边缘，避免冷启动回源

### 扩展阅读

- CDN 中的 QUIC/HTTP3：边缘节点的传输层优化
- CDN 与 WebRTC：实时音视频的边缘加速
- CDN 与 DDoS 防护：吸收攻击流量的边缘安全
- 边缘 AI 推理：在 CDN 节点运行轻量级 ML 模型

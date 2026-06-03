# 系统设计 #11：微服务短链接服务

> 架构师视角 · 从零到一完整设计

---

## 1. 需求分析

### 1.1 核心功能

| 功能 | 描述 |
|------|------|
| 生成短链 | 长 URL → 短 code（6~7 位），支持自定义别名 |
| 重定向 | GET /{code} → 302 跳转原始 URL |
| 过期 | TTL 支持（N 天/永久），过期后返回 410 Gone |
| 统计 | 访问次数、独立访客(UV)、IP 分布、来源 Referer |

### 1.2 非功能需求

| 指标 | 目标 | 理由 |
|------|------|------|
| 可用性 | 99.9%（月宕机 < 43min） | 核心链路依赖，用户/广告商可接受 |
| 重定向延迟 | p99 < 10ms | 每次短链点击用户期望即时跳转 |
| 写 QPS | 10W+ | 高峰时段（营销活动）突增 |
| 读 QPS | 100W+ | 重定向是主要流量，读远大于写 |
| 数据持久性 | 99.9999% | 短链映射不可丢（已有链接、二维码分发） |

### 1.3 规模估算

**假设：** DAU = 5000 万，人均每天点击 3 个短链，日均新增 1000 万条短链

```
日均新增写入：    10,000,000 条/天
日均点击读取：    150,000,000 次/天 ≈ 150M 次/天
峰值写 QPS：     10,000,000 × 2 / 86400 ≈ 230/s（均匀分布假设）
                 活动峰值可到 10W/s（削峰填谷后仍要扛）
峰值读 QPS：     150,000,000 × 2 / 86400 ≈ 3,470/s
                 营销活动峰值可达 100W+/s（一个爆款链接发微博）
```

**存储估算：**
```
单条记录 ≈ 256B（id + url + 用户 + 时间 + 索引等）
日均新增数据：  10M × 256B ≈ 2.5 GB/天
3 年存储：      2.5 GB × 365 × 3 ≈ 2.7 TB
               → 考虑索引 + 冗余 ≈ 3.5 TB
```

---

## 2. 架构设计

### 2.1 整体架构

```
┌──────────────────────────────────────────────────────────────────┐
│                         Client (Browser/App)                      │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                     API Gateway (Nginx/Kong)                      │
│    ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│    │ Rate    │ │  Auth    │ │ Request  │ │  Circuit Breaker │  │
│    │ Limiter │ │  Check   │ │  Logging │ │                  │  │
│    └─────────┘ └──────────┘ └──────────┘ └──────────────────┘  │
├──────────────────────────────────────────────────────────────────┤
│                     Service Layer (K8s + gRPC/HTTP)               │
│  ┌────────────────┐ ┌────────────────┐ ┌──────────────────┐     │
│  │ Shorten Service │ │  Redirect      │ │  Stats Service   │     │
│  │ (发号 + 入库)    │ │  Service       │ │  (异步统计分析)   │     │
│  └───────┬────────┘ │  (读缓存+DB)    │ └────────┬─────────┘     │
│          │          └────────┬───────┘          │                │
│          ▼                   ▼                   ▼                │
├──────────────────────────────────────────────────────────────────┤
│                        Data & Cache Layer                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │  Redis   │ │  Bloom   │ │  MySQL   │ │  Message Queue   │   │
│  │ Cluster  │ │ Filter   │ │  Cluster │ │  (Kafka/RMQ)     │   │
│  │ (读缓存)  │ │ (防穿透) │ │ (分片存储)│ │  (统计异步写入)    │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 组件选型理由

| 组件 | 选型 | 理由 |
|------|------|------|
| API Gateway | Nginx + Lua / Kong | 高性能反向代理，Lua 脚本做限流/鉴权，Kong 插件生态丰富 |
| 服务框架 | gRPC (服务间) + HTTP (外部) | gRPC 内部低延迟通信，HTTP 外部 API |
| 服务编排 | Kubernetes | 自动扩缩容，服务发现，滚动升级 |
| 主数据库 | **PostgreSQL** > MySQL | pg 原生支持 JSONB（存扩展字段）、更好的并发控制、分区表成熟；MySQL 亦可但需额外处理 |
| 缓存 | Redis Cluster | 10W+ QPS 支撑，天然支持过期 TTL、LRU 淘汰、pipeline 批量读 |
| 布隆过滤器 | Redis 原生 BF module / Guava | 内存级，百万级元素仅几 MB |
| 消息队列 | Kafka | 高吞吐日志处理，统计异步写，支持重试/持久化 |
| 发号器 | **DB 号段模式** | 下文详述 |

---

## 3. 发号器设计（核心难点）

### 3.1 方案对比

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| UUID | 简单、全局唯一 | 128bit 太长，无序，数据库索引效率低 | ❌ |
| 雪花算法(Snowflake) | 高性能、趋势递增 | **依赖时钟**，时钟回拨导致 ID 冲突；需额外维护 worker ID | ⚠️ |
| Redis INCR | 高性能、天然有序 | **单点瓶颈**，Redis 宕机 ID 丢失/跳跃；上限约 10W/s | ⚠️ |
| **DB 号段模式** | 无时钟依赖、高并发、ID 连续可预测、易扩展 | 需预取机制、号码有间隔浪费 | ✅ **推荐** |

**选型理由：** 号段模式平衡了「全局唯一、高性能、无外部依赖、易扩展」四个约束。每个服务实例本地缓存一段 ID 序列，DB 只记录当前最大分配号。

### 3.2 号段模式详解

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ Service A    │      │ Service B    │      │ Service C    │
│ ID Cache:    │      │ ID Cache:    │      │ ID Cache:    │
│ [1, 1000]    │      │ [1001,2000]  │      │ [2001,3000]  │
└──────┬───────┘      └──────┬───────┘      └──────┬───────┘
       │                     │                     │
       └─────────────────────┼─────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  DB (id_alloc)  │
                    │  max_id = 3000  │
                    │  step  = 1000   │
                    └─────────────────┘
```

**流程：**
1. 每个分片服务启动时，向 DB 申请一段号段：`UPDATE id_alloc SET max_id = max_id + step WHERE tag='short_link' RETURNING max_id`
2. 拿到 `[old_max+1, new_max]`，加载到本地内存
3. 从内存中 CAS 分配（本地无锁队列/AtomicLong）
4. 用尽后再次申请下一段
5. DB 记录当前最大分配号，重启不丢失

**多机部署：** 多个实例不会冲突，因为每个实例取互不重叠的号段。步长建议 1000~10000（步长越大 DB 压力越小，但浪费区间越大）。

### 3.3 Base62 编码

拿到数字 ID 后，转 Base62（0-9a-zA-Z）短字符串：

```
def base62_encode(num: int, length: int = 7) -> str:
    chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    code = []
    while num > 0:
        code.append(chars[num % 62])
        num //= 62
    # 补零左填充到固定长度
    return ''.join(reversed(code)).zfill(length)
```

| ID 位数 | 可容纳短链数 |
|---------|-------------|
| 6 位    | 62^6 ≈ 568 亿 |
| 7 位    | 62^7 ≈ 3.5 万亿 |

**结论：** 6 位已足够（568 亿 > 日均 1000 万 × 3 年 ≈ 110 亿）。预留 7 位做未来扩展。

---

## 4. 存储设计

### 4.1 MySQL/PostgreSQL 表结构

```sql
-- ============ 短链主表 ============
CREATE TABLE short_link (
    id            BIGINT       NOT NULL PRIMARY KEY,   -- 发号器分配的数字 ID
    short_code    VARCHAR(16)  NOT NULL,                -- Base62 编码
    long_url      TEXT         NOT NULL,                -- 原始长 URL
    user_id       VARCHAR(64)  DEFAULT '',              -- 创建者（可选）
    expire_at     TIMESTAMP    DEFAULT NULL,            -- 过期时间 NULL=永不过期
    status        TINYINT      DEFAULT 1,               -- 1=正常 0=禁用 2=过期
    created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE INDEX idx_short_code (short_code)
) PARTITION BY HASH(id) PARTITIONS 256;

-- ============ 发号器表 ============
CREATE TABLE id_allocator (
    tag          VARCHAR(64)  PRIMARY KEY,  -- 业务标识
    max_id       BIGINT       DEFAULT 0,    -- 当前已分配最大 ID
    step         INT          DEFAULT 1000, -- 步长
    version      INT          DEFAULT 0     -- 乐观锁
);

-- ============ 访问日志表（归档用） ============
CREATE TABLE access_log (
    id           BIGSERIAL    PRIMARY KEY,
    short_code   VARCHAR(16)  NOT NULL,
    ip           INET         NOT NULL,
    user_agent   TEXT,
    referer      TEXT,
    country      VARCHAR(64),
    accessed_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
) PARTITION BY RANGE (accessed_at);
-- 按天/月分区，保留 90 天，超期归档到冷存储（HDFS/S3）
```

### 4.2 分表策略

| 维度 | 策略 | 理由 |
|------|------|------|
| 主表分片 | `HASH(id) % 256` | id 均匀分布，避免热点 |
| 访问日志 | 按月分区 + 归档 | 统计查询范围通常 < 30 天，旧数据冷存 |

### 4.3 缓存策略

```
┌─────────┐    GET /abc123     ┌──────────┐
│  Client  │ ──────────────►  │  API GW   │
└─────────┘                   └─────┬────┘
                                    │
                          ┌─────────▼─────────┐
                          │   Bloom Filter     │ ← 不存在 → 直接 404
                          │ checks short_code  │
                          └─────────┬─────────┘
                                    │ 可能存在
                          ┌─────────▼─────────┐
                          │   Redis Cluster    │ ← 命中 → 返回 long_url
                          │  GET short_code    │
                          └─────────┬─────────┘
                                    │ 未命中
                          ┌─────────▼─────────┐
                          │   MySQL Shard      │ ← 命中 → 回写 Redis
                          │  idx_short_code    │      + 设置 TTL
                          └───────────────────┘
```

**缓存要点：**
- **Redis TTL = 短链过期时间**：过期自动淘汰，精确控制缓存生命周期
- **LRU 近似淘汰**：Redis `maxmemory-policy allkeys-lru`，热点保留
- **缓存穿透防护**：布隆过滤器拦截 99.9%+ 的无效 key（爬虫/恶意扫描）
- **缓存击穿防护**：热点 key 加 mutex lock，第一个请求回源 DB，其余等待

### 4.4 布隆过滤器设计

```
元素数量：预估 3 年短链总数 ≈ 110 亿
误判率 p：0.1% (1e-3)
位数组大小 m = -n·ln(p) / (ln2)^2 ≈ 110e9 × 6.91 / 0.48 ≈ 1.58TB

❌ 单纯 Bloom Filter 过大，无法全量放入内存
```

**实际方案：** 分段 Bloom Filter + 时间窗口
- 热点过滤：只缓存最近 30 天内活跃的短链（~3 亿条），Bloom Filter 仅需 ~4.3GB
- 先查 Bloom（热数据）→ Redis → DB
- 非活跃短链直接走 Redis → DB

---

## 5. 核心 API 设计

### 5.1 POST /api/shorten — 生成短链

```
Request:
POST /api/shorten
Authorization: Bearer <token>
Content-Type: application/json

{
    "url": "https://example.com/very/long/url/with/params?q=1",
    "custom_alias": "mybrand",    // 可选自定义
    "expire_in_days": 30           // 可选，默认永久
}

Response 200:
{
    "short_url": "https://k.url/abc123",
    "short_code": "abc123",
    "expire_at": "2026-06-12T10:00:00Z"
}

Response 409 (自定义别名冲突):
{
    "error": "alias_already_exists",
    "message": "Custom alias 'mybrand' already taken"
}
```

**处理流程：**
```
1. 参数校验（URL 格式、白名单域名检查）
2. 如有 custom_alias → 检查唯一性（Redis + DB）
3. 发号器获取 ID → Base62 编码
4. 写入 MySQL short_link 表
5. 写入 Redis（key=short_code, value=long_url, TTL=expire_at）
6. 异步写访问日志到 Kafka（可选，用于统计）
7. 返回短 URL
```

### 5.2 GET /{short_code} — 重定向

```
Request:
GET /abc123
User-Agent: Mozilla/5.0 ...
Referer: https://t.co/...

Response 302:
Location: https://example.com/very/long/url

Response 404:
{ "error": "not_found" }

Response 410:
{ "error": "expired", "message": "This short link has expired" }
```

**处理流程：**
```
1. 提取 short_code，校验格式（alphanumeric 6-7 位）
2. Bloom Filter 检查是否存在（快速拒绝无效 code）
3. Redis GET short_code
   - 命中 → 检查过期 → 302 重定向
   - 未命中 → 查 DB
4. DB 查询 idx_short_code
   - 存在 → 回写 Redis + 302 重定向
   - 不存在 → 404
   - 过期(status=2) → 410
5. 异步写访问日志到 Kafka（MQ 削峰，统计服务消费）
```

### 5.3 GET /api/stats/{short_code} — 统计

```
Request:
GET /api/stats/abc123

Response 200:
{
    "short_code": "abc123",
    "total_clicks": 142857,
    "unique_visitors": 83129,
    "countries": [
        {"country": "CN", "count": 101234},
        {"country": "US", "count": 20456},
        ...
    ],
    "referers": [
        {"source": "twitter.com", "count": 50123},
        {"source": "weibo.com", "count": 30234},
        ...
    ],
    "clicks_per_day": [
        {"date": "2026-05-01", "count": 12000},
        ...
    ]
}
```

**实现方式：**
- 访问日志写入 Kafka，Stats Service 消费后聚合到 Redis/ClickHouse
- 实时聚合：Redis HyperLogLog（UV 估算）+ Sorted Set（每日点击量）
- 离线聚合：每日定时任务将当日数据刷入 ClickHouse（OLAP 查询）
- 统计结果缓存：`stats:{short_code}` TTL=5min

---

## 6. 数据流图

### 6.1 生成短链

```
Client                    API GW              Shorten Svc           ID Allocator    DB/Redis
  │                         │                     │                     │              │
  │  POST /api/shorten      │                     │                     │              │
  │ ─────────────────────►  │                     │                     │              │
  │                         │  gRPC/HTTP          │                     │              │
  │                         │ ──────────────────► │                     │              │
  │                         │                     │ ID段不够?            │              │
  │                         │                     │ ──────────────────► │              │
  │                         │                     │ ◄──── new_segment ──│              │
  │                         │                     │                     │              │
  │                         │                     │ ┌──── ID→Base62 ────┤              │
  │                         │                     │                     │              │
  │                         │                     │ INSERT short_link   │              │
  │                         │                     │ ──────────────────► │  DB          │
  │                         │                     │                     │              │
  │                         │                     │ SET short_code URL  │              │
  │                         │                     │ ──────────────────► │  Redis       │
  │                         │                     │                     │              │
  │  ◄── short_url ─────── │ ◄────────────────── │                     │              │
  │                         │                     │                     │              │
```

### 6.2 重定向

```
Client           API GW        Redirect Svc     Bloom Filter     Redis       DB
  │                │                │                │             │          │
  │ GET /abc123    │                │                │             │          │
  │ ───────────►  │                │                │             │          │
  │               │ gRPC/HTTP      │                │             │          │
  │               │ ─────────────►│                │             │          │
  │               │                │ ── EXISTS? ──►│             │          │
  │               │                │ ◄── NO ──────│  → return 404          │
  │               │                │ ◄── YES ────│             │          │
  │               │                │                │ ── GET ──►│          │
  │               │                │                │ ◄── HIT ──│          │
  │               │                │                │ (or MISS → DB)      │
  │               │                │                │             │          │
  │               │                │ 异步写 Kafka   │             │          │
  │               │                │                │             │          │
  │ 302 Redirect  │                │                │             │          │
  │ ◄────────────│ ◄─────────────│                │             │          │
  │               │                │                │             │          │
```

---

## 7. 伪代码：核心服务

### 7.1 ID 发号器

```python
class IDAllocator:
    """DB 号段模式发号器"""
    def __init__(self, db_pool, tag="short_link", step=1000):
        self.db = db_pool
        self.tag = tag
        self.step = step
        self.current_id = 0
        self.max_id = 0
    
    def next_id(self) -> int:
        if self.current_id >= self.max_id:
            self._alloc_segment()
        id_ = self.current_id
        self.current_id += 1
        return id_
    
    def _alloc_segment(self):
        """使用乐观锁从 DB 申请新号段"""
        with self.db.transaction():
            row = self.db.query(
                "SELECT max_id FROM id_allocator WHERE tag=:tag FOR UPDATE",
                {"tag": self.tag}
            )
            new_max = row.max_id + self.step
            self.db.execute(
                "UPDATE id_allocator SET max_id=:new_max WHERE tag=:tag",
                {"new_max": new_max, "tag": self.tag}
            )
            self.current_id = row.max_id + 1
            self.max_id = new_max
```

### 7.2 短链生成服务

```python
class ShortenService:
    def __init__(self, id_allocator, db, redis, bloom_filter):
        self.alloc = id_allocator   # ID 发号器
        self.db = db                # DB 连接池
        self.redis = redis          # Redis 连接
        self.bloom = bloom_filter   # 布隆过滤器
    
    def create_short_link(self, long_url: str, user_id: str = "",
                          custom_alias: str = "", expire_days: int = 0) -> dict:
        # 1. 参数校验
        validate_url(long_url)
        check_domain_whitelist(long_url)
        if long_url.strip() == "":
            raise InvalidParamError()
        
        # 2. 自定义别名处理
        code = custom_alias or base62_encode(self.alloc.next_id())
        if custom_alias and self.bloom.exists(custom_alias):
            raise AliasExistsError()
        
        # 3. 计算过期时间
        expire_at = None
        if expire_days > 0:
            expire_at = datetime.utcnow() + timedelta(days=expire_days)
        
        # 4. 持久化
        self.db.execute(
            "INSERT INTO short_link (id, short_code, long_url, user_id, expire_at) "
            "VALUES (:id, :code, :url, :uid, :exp)",
            {"id": self.alloc.next_id(), "code": code, "url": long_url,
             "uid": user_id, "exp": expire_at}
        )
        
        # 5. 写缓存
        ttl = calc_ttl_seconds(expire_at) or 86400 * 30
        self.redis.set(f"sl:{code}", long_url, ex=ttl)
        
        # 6. 更新 Bloom Filter
        self.bloom.add(code)
        
        return {
            "short_url": f"https://k.url/{code}",
            "short_code": code,
            "expire_at": expire_at.isoformat() if expire_at else None
        }
```

### 7.3 重定向服务

```python
class RedirectService:
    def __init__(self, redis, db, bloom_filter, kafka_producer):
        self.redis = redis
        self.db = db
        self.bloom = bloom_filter
        self.kafka = kafka_producer  # 异步统计
    
    def resolve(self, short_code: str, request_meta: dict) -> str:
        # 1. 快速拒绝（Bloom Filter）
        if not self.bloom.exists(short_code):
            return None, 404  # not found
        
        # 2. 查 Redis 缓存
        long_url = self.redis.get(f"sl:{short_code}")
        if long_url:
            # 3. 异步写访问日志
            self._log_async(short_code, request_meta)
            return long_url, 302
        
        # 4. 回源 DB（互斥锁防缓存击穿）
        with self.redis.lock(f"lock:{short_code}", ttl=500):
            # 双重检查
            long_url = self.redis.get(f"sl:{short_code}")
            if long_url:
                return long_url, 302
            
            row = self.db.query(
                "SELECT long_url, status, expire_at FROM short_link "
                "WHERE short_code=:code", {"code": short_code}
            )
            if not row:
                # 写入布隆（防反复穿透），但用较小概率允许
                return None, 404
            
            if row.status == 2 or (row.expire_at and row.expire_at < now()):
                return None, 410  # expired
            
            # 回写 Redis
            ttl = calc_ttl_seconds(row.expire_at)
            self.redis.set(f"sl:{short_code}", row.long_url, ex=ttl)
        
        self._log_async(short_code, request_meta)
        return long_url, 302
    
    def _log_async(self, short_code: str, meta: dict):
        """异步写入 Kafka，由 Stats Service 消费"""
        self.kafka.send("access_log", {
            "short_code": short_code,
            "ip": meta.get("ip"),
            "user_agent": meta.get("user_agent"),
            "referer": meta.get("referer"),
            "timestamp": int(time.time() * 1000),
        })
```

### 7.4 统计服务（Kafka 消费者）

```python
class StatsConsumer:
    """消费 Kafka access_log，聚合统计"""
    
    def __init__(self, redis, clickhouse):
        self.redis = redis
        self.ch = clickhouse
    
    def process_message(self, msg: dict):
        code = msg["short_code"]
        ip = msg["ip"]
        day = date.fromtimestamp(msg["timestamp"] / 1000)
        
        pipe = self.redis.pipeline()
        # 总点击量（计数）
        pipe.incr(f"stats:{code}:total")
        
        # UV（HyperLogLog，误差 ~0.81%）
        pipe.pfadd(f"stats:{code}:uv", ip)
        
        # 日点击量（有序集合）
        pipe.zincrby(f"stats:{code}:daily:{day}", 1, str(day))
        
        # IP 国家统计（需要 IP 地理库）
        country = geo_ip(ip)
        pipe.hincrby(f"stats:{code}:countries", country, 1)
        
        pipe.execute()
    
    def batch_to_clickhouse(self):
        """定时批量刷入 ClickHouse 做 OLAP 查询"""
        pass
```

---

## 8. 扩展设计

### 8.1 自定义短链

```
需求：用户希望使用 "mybrand" 而非随机生成的 "abc123"
方案：
- 预留所有自定义别名空间（Bloom Filter + DB 唯一索引）
- 生成自定义短链 → 直接 INSERT，冲突抛 409
- 自定义短链优先级高于生成短链（Redis GET 不分来源）
```

### 8.2 短链回收

```
需求：过期短链的 ID 能否复用？
答案：⚠️ 不建议复用！
理由：
- 复用可能导致旧链接在缓存/第三方平台突然可用
- 用户预期：404 → 回收到某个活动又 200 → 钓鱼风险
- 解法：过期数据标记 status=2，物理删除需确认安全窗口
- ID 充足（6 位有 568 亿），无需回收
```

### 8.3 白名单域名

```
需求：仅允许特定域名生成短链（反钓鱼/安全管控）
方案：
- 解析目标 URL 的 hostname → 查白名单集合
- 白名单维护在 Redis Set `domain_whitelist`
- 运营后台可 CRUD 维护
- 扩展：支持正则匹配 `*.example.com`
```

### 8.4 二维码生成

```
需求：生成短链后自动返回二维码图片
方案：
- QR Code 内置编码就是短 URL（短 URL 天然适合二维码）
- 服务端：POST /api/shorten 可选参数 `return_qrcode=true`
- 返回二维码 Base64 PNG，客户端直接展示
- 或：生成时存到 CDN，返回 URL
- QR Code 库：qrcode (Python) / ZXing (Java)
```

### 8.5 安全防护

| 攻击类型 | 防护措施 |
|---------|---------|
| 恶意生成大量短链 | API Rate Limiter（每用户/每 IP 限制 QPS） |
| 爬虫无效 code 扫描 | Bloom Filter 快速拒绝 + IP 黑名单 |
| 循环重定向 | 检查长链重定向链，超过 N 跳拒绝 |
| 钓鱼链接 | 白名单域名 + URL 安全检查（Google Safe Browsing API） |
| DDoS 短链重定向 | CDN 缓存 + 限流 + 扩容 |

---

## 9. 真实系统对比

### 9.1 bit.ly（世界最大短链服务）

| 特性 | bit.ly | 本设计 |
|------|--------|--------|
| 发号器 | 私有，Hash 而非顺序 ID | 号段模式 + Base62 |
| 短链长度 | 7 字符 | 6~7 字符 |
| 缓存 | Memcached (早期) → Redis (现在) | Redis Cluster |
| 统计 | 实时 + 批量，提供详细受众画像 | 实时 Redis + ClickHouse 离线 |
| 自定义域名 | 支持 (bit.ly 就是 4 级域名) | 预留 |
| API | REST + OAuth | REST + JWT |
| 数据库 | DynamoDB (文中有猜测) | PostgreSQL Shard |

### 9.2 t.cn（新浪短链）

| 特性 | t.cn | 本设计 |
|------|------|--------|
| 发号器 | 自增 ID + 编码（猜测） | 号段模式 |
| 短链长度 | 6 字符（t.cn/AbCdEf） | 6~7 字符 |
| 认证 | 微博登录 | Token/Bearer |
| 额外功能 | 微博分享统计 | 通用统计 |
| 安全 | 微博内容审核 | 白名单 + URL 安全扫描 |
| 目前状态 | 2024 年起逐步关闭 | N/A |

### 9.3 Key Takeaways

1. **发号器是核心瓶颈**：bit.ly 选择无规律 hash 防猜，但代价是冲突检测。号段模式 + Base62 在性能和安全之间折中最好
2. **读比写难 10 倍**：100W+ QPS 读依赖三层缓存（Bloom + Redis + DB），每层都要设计快路径
3. **统计是增值点**：bit.ly 的 business model 靠数据分析，而非链接生成本身
4. **简单不等于简陋**：t.cn 系统并不复杂，靠微博生态闭环活得很好；短链本身是"10行代码能跑但100万QPS才难"的典型

---

## 10. 部署 & 运维

### 10.1 扩容策略

```
流量级别       服务实例       Redis 分片       DB 分片       CDN
< 1K QPS       2             1 主             4 分区        可选
< 10K QPS      4            3 主 3 从         16 分区       静态资源
< 100W QPS     20+          9 主 9 从         256 分区      + 边缘重定向
> 100W QPS     弹性伸缩      动态增减         只读副本       + CDN 302
```

### 10.2 关键监控指标

| 指标 | 告警阈值 | 意义 |
|------|---------|------|
| Redirect p99 latency | > 50ms | 缓存或 DB 性能劣化 |
| DB 号段剩余 < 20% | < 20% | 发号器可能被耗尽，需调大步长或扩实例 |
| Redis miss rate | > 5% | 缓存预热不足或 Bloom Filter 误判过高 |
| Bloom Filter 误判率 | > 1% | 需重建或扩大位数组 |
| Kafka 消费延迟 | > 10s | 统计系统堆积 |

---

*设计日期：2026-05-13*
*下一课建议：系统设计 #12 — 分布式 ID 生成器深度专题（号段/雪花/美团 Leaf/百度 UIDGenerator）*

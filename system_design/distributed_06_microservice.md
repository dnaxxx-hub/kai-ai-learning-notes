# 分布式系统 第6课：微服务治理与服务网格

## 1. 微服务架构核心挑战

### 服务发现
微服务部署后 IP/端口动态变化，服务之间如何互相找到？

| 方案 | 一致性算法 | CAP | 特点 |
|------|-----------|-----|------|
| **Consul** | Raft | CP | 健康检查强、DNS/HTTP双接口 |
| **etcd** | Raft | CP | watch机制、k8s标配 |
| **ZooKeeper** | ZAB | CP | 临时节点+watcher |

### 熔断器（Circuit Breaker）
三状态模型：**Closed → Open → Half-Open**

- **Closed**：正常，请求通过，计数失败次数
- **Open**：失败达到阈值，快速失败，等待超时
- **Half-Open**：超时后放行少量探测请求
- 参数：failure_threshold(如5), recovery_timeout(如5s), success_threshold(如2)

### 重试与退避
指数退避：`sleep = base × 2^attempt`
Full Jitter（推荐）：`sleep = random(0, base × 2^attempt)`
**只有幂等操作可重试**，设置最大重试次数和总超时。

### 限流
- **令牌桶**：恒定速率放令牌，支持突发
- **漏桶**：恒定速率出水，平滑但不能突发
- **滑动窗口**：分桶统计，精确但内存大

## 2. 服务网格（Service Mesh）

核心理念：服务通信逻辑从业务代码剥离到 Sidecar 代理。

### Istio 架构
- **Pilot**（流量管理）：服务发现 + xDS API → Envoy
- **Citadel**（安全）：证书签发 + mTLS
- **Envoy**（数据面）：C++ 实现的高性能代理
- 控制面 vs 数据面分离

### 可观测性三支柱
- **日志**（结构化JSON，ES/Loki存储）
- **指标**（Prometheus + 4个黄金信号：延迟/流量/错误/饱和度）
- **链路追踪**（OpenTelemetry + Jaeger/Zipkin）
  - Trace = 多个 Span 组成树
  - 采样：头上采样（进入时概率）或尾部采样（完成时保留慢/错误请求）

## 3. Python 实现：简化服务治理框架

```python
import time, random, threading, hashlib
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum

@dataclass
class ServiceInstance:
    name: str
    host: str
    port: int
    instance_id: str = ""
    status: str = "UP"

class ServiceRegistry:
    """服务注册中心（线程安全）"""
    def __init__(self, ttl=10.0):
        self._services = defaultdict(dict)
        self._lock = threading.RLock()
        threading.Thread(target=self._health_loop, daemon=True).start()
    
    def register(self, name, host, port):
        inst = ServiceInstance(name, host, port, f"{name}@{host}:{port}")
        with self._lock: self._services[name][inst.instance_id] = inst
        return inst
    
    def deregister(self, name, iid):
        with self._lock:
            if iid in self._services.get(name, {}):
                del self._services[name][iid]; return True
        return False
    
    def discover(self, name):
        with self._lock:
            return [i for i in self._services.get(name, {}).values() if i.status == "UP"]

class CircuitBreaker:
    """三状态熔断器"""
    def __init__(self, name="default", fail_thresh=5, recovery=5.0):
        self.name = name
        self._fail_thresh = fail_thresh
        self._recovery = recovery
        self._state = "CLOSED"
        self._failures = 0
        self._last_fail = 0.0
        self._lock = threading.RLock()
    
    def allow(self):
        with self._lock:
            if self._state == "OPEN" and time.time() - self._last_fail > self._recovery:
                self._state = "HALF_OPEN"
            return self._state != "OPEN"
    
    def success(self):
        with self._lock:
            if self._state == "HALF_OPEN": self._state = "CLOSED"
            self._failures = 0
    
    def failure(self):
        with self._lock:
            self._last_fail = time.time()
            self._failures += 1
            if self._failures >= self._fail_thresh:
                self._state = "OPEN"

class TokenBucket:
    def __init__(self, rate=10.0, burst=20):
        self._rate = rate; self._burst = burst
        self._tokens = burst; self._last = time.time()
    
    def allow(self):
        now = time.time()
        self._tokens = min(self._burst, self._tokens + (now - self._last) * self._rate)
        self._last = now
        if self._tokens >= 1: self._tokens -= 1; return True
        return False

# 演示
registry = ServiceRegistry()
registry.register("auth", "192.168.1.1", 8080)
registry.register("auth", "192.168.1.2", 8080)
print(f"发现 auth 服务: {len(registry.discover('auth'))} 个实例")

cb = CircuitBreaker("auth")
tb = TokenBucket(10, 20)

for i in range(10):
    if tb.allow() and cb.allow():
        success = random.random() > 0.3  # 70%成功率模拟
        if success: cb.success(); print(f"请求{i}: ✅")
        else: cb.failure(); print(f"请求{i}: ❌")
    else:
        print(f"请求{i}: ⛔ 被限流或熔断")
```

## 关键总结
- 微服务治理 = 注册发现 + 熔断 + 限流 + 重试 + 负载均衡
- Service Mesh 通过 Sidecar 实现 0 侵入治理
- 可观测性三支柱：日志/指标/链路追踪

# K8s 调度器实践笔记

> 通过学习实现迷你 K8s 调度器模拟器，深入理解 Kubernetes 核心调度机制

## 1. K8s 调度器架构概览

Kubernetes 调度器 (`kube-scheduler`) 是一个控制平面组件，负责将新创建的 Pod 分配到合适的 Node 上。其核心设计是 **"两阶段调度"**：过滤（Predicates）→ 评分（Priorities）。

### 整体流程

```
Pod 创建 → 加入调度队列 → 过滤阶段(Predicate) → 评分阶段(Priority) → 绑定(Bind)
                              ↓                     ↓
                      过滤掉的节点(不可用)     选择最高分节点
```

### 调度器与控制器管理器

调度器和 ReplicaSet 控制器是独立的组件，通过协调工作：
- **ReplicaSet 控制器**：确保 Pod 副本数达到期望值，创建新 Pod
- **调度器**：将 Pending 状态的 Pod 调度到合适的节点
- 两者通过 API Server 和 etcd 共享集群状态

### 调度器设计特点

- **插件化架构**：过滤和评分算法都是可插拔的
- **可配置调度策略**：通过 `SchedulerConfiguration` 动态配置
- **抢占式调度**：高优先级 Pod 可以抢占低优先级 Pod 的资源
- **调度队列多级化**：ActiveQ、BackoffQ、UnschedulableQ

---

## 2. 过滤/评分/绑定三阶段详解

### 过滤阶段 (Predicates)

过滤阶段的目的是筛选出满足 Pod 运行条件的节点（feasible nodes）。

**常见的 Predicate 插件：**

| 插件名称 | 功能描述 |
|---------|---------|
| `NodeResourcesFit` | 检查节点剩余资源 >= Pod 请求资源 |
| `NodeSelector` | 检查 Pod 的 nodeSelector 标签是否匹配 |
| `NodeAffinity` | 检查 Pod 的 nodeAffinity 规则 |
| `NodeUnschedulable` | 排除被 cordon 的节点 |
| `PodToleratesNodeTaints` | 检查 Pod 能否容忍节点污点 |
| `CheckNodeCondition` | 检查节点状态（Ready/NotReady） |

**在我们的实现中：**
```python
# 过滤链中的四种检查：
predicates = [
    predicate_node_ready,       # 节点可运行
    predicate_node_resources,   # 资源充足
    predicate_node_selector,    # 标签匹配
    predicate_node_affinity,    # 亲和性
]
# 所有检查必须通过（AND 语义）
```

**NodeAffinity 操作符：**
- `In`：标签值在指定集合中
- `NotIn`：标签值不在指定集合中
- `Exists`：标签键存在
- `DoesNotExist`：标签键不存在
- `Gt` / `Lt`：数值比较

**重要设计要点：**
- 多个 `nodeSelectorTerms` 是 OR 关系（满足一个即可）
- 单个 term 内的多个 `matchExpressions` 是 AND 关系（全部满足）
- 过滤阶段一定要有严格的错误信息，便于调度失败排查

### 评分阶段 (Priorities)

评分阶段对过滤后剩下的节点打分，选出最优节点。

**LeastRequestedPriority（最少请求优先）：**

```python
# 算法：空闲资源比例越高，分数越高
score = ((capacity - requested) / capacity) * 10
final_score = (cpu_score + mem_score) / 2.0
```

这意味着：资源越空闲的节点，得分越高，有利于负载均衡。

**BalancedResourceAllocation（资源平衡）：**

```python
# 算法：CPU 和内存使用率差异越小，分数越高
score = 10 - abs(cpu_utilization - mem_utilization) * 10
```

这意味着：如果一个节点 CPU 使用 80% 但内存只用了 20%，分数会很低；如果 CPU 和内存都用了 50%，分数接近 10。

**多评分器组合：**

实践中通常组合使用多个评分器，通过权重加权：
```python
final_score = (lr_score * w_lr + br_score * w_br) / (w_lr + w_br)
```

### 绑定阶段 (Bind)

最简单也最关键的一步：将 Pod 的 `nodeName` 设置为选中的节点，同时在节点上扣除相应资源。

```python
def bind(self, pod, node):
    pod.node = node.name
    pod.status = "Scheduled"
    node.allocate(pod.cpu_request, pod.mem_request)
```

**关键注意**：绑定前需要再次检查资源是否充足，因为自过滤阶段后可能有其他 Pod 被调度到同一节点（竞态条件）。

---

## 3. 调度队列和 Backoff 设计

### 调度队列结构

真实的 `kube-scheduler` 有三个队列：
1. **ActiveQ**：等待调度的 Pod（Heap 实现，按优先级排序）
2. **BackoffQ**：调度失败的 Pod，等待 Backoff 到期后回到 ActiveQ
3. **UnschedulableQ**：调度失败且暂时无法调度的 Pod

### 优先级排序

```python
# Pod 按优先级从高到低排序
# 优先级相同时，按创建时间从早到晚
if self.priority != other.priority:
    return self.priority > other.priority
return self.creation_time < other.creation_time
```

**设计要点：**
- 使用负优先级值实现最大堆效果（Python 的 heapq 是最小堆）
- 时间戳作为第二排序键，保证先进先出

### 指数 Backoff

调度失败的 Pod 不应该立即重试，否则会引起调度器忙碌循环。

```python
# 指数退避算法
backoff = min(base * (2 ^ (retry_count - 1)), max_backoff)

# 示例：基础退避 1 秒
retry 1: 1s    (1 * 2^0)
retry 2: 2s    (1 * 2^1)
retry 3: 4s    (1 * 2^2)
retry 4: 8s    (1 * 2^3)
retry 5: 16s   (1 * 2^4)
retry 6: 32s   (1 * 2^5)
retry 7: 60s   (capped at max)
```

**重要细节：**
- Backoff 到期前，Pod 在队列中但不会被 `pop()` 返回
- 经过 Backoff 后，Pod 有机会被调度到其他节点
- 最大退避时间限制防止无限增长

---

## 4. ReplicaSet 控制器如何维持副本数

### 控制循环模式

ReplicaSet 控制器遵循典型的 **Reconcile（协调）循环** 模式：

```
期望状态 (Desired)   vs   实际状态 (Actual)
    replicas                 matching_pods.count()
          ↘                       ↙
           diff = desired - actual
                  ↓
        diff > 0 → 创建 Pod
        diff < 0 → 删除 Pod
        diff == 0 → 无事可做
```

### 标签选择器

ReplicaSet 通过标签选择器关联 Pod，这也是 Kubernetes 的核心设计哲学：

```python
# selector 定义了哪些 Pod 属于这个 ReplicaSet
selector = {"app": "web", "tier": "frontend"}

# 匹配规则：Pod 的 labels 必须包含 selector 中所有键值对
match = all(pod.labels.get(k) == v for k, v in selector.items())
```

### Pod 模板

ReplicaSet 包含一个 Pod 模板，用来创建新的 Pod：
```python
template = {
    "cpu_request": 200,
    "mem_request": 512,
    "labels": {"app": "web"},
}
```

**设计要点：**
- 名称自动生成以保证唯一性
- 创建时自动应用 Selector 标签
- 新 Pod 加入调度队列等待调度

---

## 5. 健康检查和 Pod 重新调度

### 心跳机制

节点通过定期发送心跳报文来表示健康状态：

```python
class HealthChecker:
    def __init__(self, heartbeat_timeout=10.0, check_interval=5.0):
        self.heartbeat_timeout = heartbeat_timeout
        self.check_interval = check_interval
```

检查逻辑：
1. 按 `check_interval` 间隔检查所有节点
2. 如果 `now - last_heartbeat > heartbeat_timeout`，标记节点为 NotReady
3. NotReady 节点上的所有 Pod 被标记为 Pending，重新加入调度队列

### Pod 重新调度流程

```
节点 NotReady
    ↓
释放节点上 Pod 占用的资源 (release)
    ↓
Pod 状态回退到 Pending
    ↓
Pod 重新加入调度队列
    ↓
调度器重新选择合适节点
    ↓
Pod 在其他节点上运行
```

**注意**：这只是调度器级别的重新调度。在实际 K8s 中，Pod 的运行状态由 kubelet 管理，需要更复杂的生命周期处理。

---

## 6. 遇到的难点

### 难点 1: 评分公式的理解和验证

**问题**：最初理解 `LeastRequestedPriority` 时，以为空节点评分 = 10，但实际上包含 Pod 自身请求资源计算后的真实分数。

**分析**：公式 `(capacity - requested) / capacity * 10` 中，`requested` 是已分配 + 新 Pod 请求。所以在空节点上：
- CPU: `(1000 - 0 - 200) / 1000 * 10 = 8.0`
- Memory: `(2048 - 0 - 512) / 2048 * 10 = 7.5`
- 最终: `(8.0 + 7.5) / 2 = 7.75`

**感悟**：K8s 的评分考虑的是分配后的状态，不只是当前状态。这个设计防止了反反复调度。

### 难点 2: 调度队列和 Backoff 的协作关系

**问题**：需要区分"队列中等待"和"Backoff 中等待"两种状态。

**解决方案**：使用 `backoff_until` 时间戳来控制 Pop 时机，Backoff 期间的 Pod 暂不弹出，使其继续留在堆中等待。

**关键设计**：Pod 被 Requeue 时，推回堆中的同时设置 `backoff_until`，Pop 时检查当前时间是否已过 Backoff 期。

### 难点 3: ReplicaSet 的名称生成

**问题**：ReplicaSet 创建 Pod 时如果名称不唯一，会导致重复调度等问题。

**解决方案**：使用 `owned_pods` 列表跟踪已创建的 Pod 数量，生成递增序号。

**更好的做法**：实际 K8s 中使用 UUID + 模板名称的组合，确保全局唯一。

### 难点 4: 节点故障时的资源释放

**问题**：节点 NotReady 后，Pod 被重新调度到其他节点，但原节点上的资源需要释放。

**解决方案**：在 `_reschedule_pods_on_node` 中先 `node.release()` 再重新入队。

**边界情况**：如果 Pod 同时被多个组件重新调度，可能导致资源双重释放。需要使用更复杂的锁或版本控制机制。

### 难点 5: 调度结果验证

**问题**：如何验证调度器做出了正确的决策（如 gpu-job 必须调度到 node-beta）？

**解决方案**：在测试中使用断言检查最终调度结果。

**更系统的方法**：可以引入调度事件日志、决策追踪，方便调试和验证。

---

## 总结

通过实现这个迷你调度器模拟器，我深入理解了：

1. **K8s 调度器的插件化设计**使其极其灵活
2. **过滤 + 评分两阶段设计**是权衡效率和最优性的关键
3. **调度队列的多级设计**（ActiveQ + BackoffQ + UnschedulableQ）避免调度器空转
4. **控制器模式（Reconcile Loop）**是 K8s 核心设计模式，控制器的幂等性设计至关重要
5. **健康检查机制**保障了集群的自我修复能力

这个模拟器虽然简单，但完整复现了调度的核心流程，是理解 K8s 调度器工作原理的绝佳起点。

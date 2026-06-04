# 混沌工程 — 原则 / 工具 / 实验类型 / 设计 / 案例

## 一、原理与原则

### 核心定义
> 混沌工程是在分布式系统上进行实验的学科，旨在建立系统应对震荡条件的信心。
> —— Principles of Chaos Engineering

### 四大原则
1. **稳态假设（Steady State Hypothesis）**：定义系统的"正常"指标（如延迟 p99 < 200ms、错误率 < 1%）
2. **实验最小化（Minimize Blast Radius）**：先小范围验证（1% 流量→10%→100%），控制影响面
3. **持续自动化运行**：将混沌实验集成到 CI/CD Pipeline，持续验证
4. **实验即证据**：实验结果是系统行为的客观描述，而非主观判断

### 混沌实验流程
```
假设 → 设计实验 → 设定爆炸半径 → 执行 → 验证假设 → 复盘/改进
```

## 二、工具对比

### LitmusChaos
- **Cloud-Native**：Kubernetes 原生，Operator 模式
- **Chaos Hub**：社区贡献的实验模板库
- **Workflow**：编排多个实验的顺序执行
- **仪表盘**：Litmus Portal 提供 Web UI

```yaml
# LitmusChaos 实验示例：Pod 删除
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata: { name: pod-delete }
spec:
  appinfo:
    appns: "default"
    applabel: "app=nginx"
  engineState: "active"
  experiments:
    - name: pod-delete
      spec:
        probe: [{ type: "httpProbe", httpProbe/inputs: { url: "http://nginx/health" }}]
```

### ChaosBlade
- **阿里巴巴开源**，支持 K8s + 主机
- **命令式**：blade create 直接执行
- **场景丰富**：CPU/内存/磁盘/网络/系统时间/进程
- **Java 注入**：支持方法级故障注入

```bash
# CPU 满载实验
blade c cpu fullload --cpu-percent 80

# 网络延迟实验
blade create network delay --time 3000 --interface eth0 --local-port 8080

# 进程 Kill
blade create process kill --process nginx
```

### Gremlin
- **商业产品**：SaaS + 自托管
- **攻击模板**：100+ 预定义实验
- **安全机制**：安全模式（阻止危险实验）、角色权限
- **故障属性**：攻击类型 × 基础设施维度 × 应用维度

### 工具对比
| 特性 | LitmusChaos | ChaosBlade | Gremlin |
|------|-------------|------------|---------|
| 开源 | ✅ (Apache 2.0) | ✅ | ❌ (商业) |
| K8s 原生 | ✅ | ⚠️ 部分 | ✅ |
| 主机支持 | ❌ | ✅ | ✅ |
| UI 仪表盘 | ✅ Portal | ❌ CLI | ✅ |
| 实验编排 | ✅ Workflow | ❌ | ✅ |
| Java 注入 | ❌ | ✅ | ✅ |
| 学习成本 | 中（CRD） | 低（CLI） | 低 |

## 三、实验类型

### 计算类
- **CPU 压力**：指定核数/百分比满载，测试限流和 HPA
- **OOM**：内存溢出，验证 OOM Kill 策略和 Pod 恢复

### 网络类
- **延迟**：模拟网络抖动（100ms/500ms/2000ms），测试超时重试机制
- **丢包**：X% 丢包，测试客户端断线重连
- **分区**：模拟网络分区，验证分布式共识算法（Raft/Paxos）
- **带宽限制**：模拟带宽瓶颈

### 节点类
- **节点停止/重启**：验证 Pod 转移到其他节点
- **磁盘故障**：磁盘写满/IO 高/只读，验证持久化逻辑

### 应用类
- **进程 Kill**：随机 kill 进程，验证进程管理器自愈
- **服务延迟**：特定 API 增加延迟，验证熔断/降级
- **异常返回**：返回 500/503，测试客户端重试和幂等性
- **数据库连接池耗尽**：验证连接池隔离

## 四、实验设计模板

### 完整实验流程
```
1. 定义稳态指标：请求成功率 ≥ 99.9%, p99 < 200ms
2. 设定爆炸半径：仅影响 1 个 Pod（特定 label），不涉及关键数据
3. 执行实验：注入网络延迟 1000ms 到 Nginx Pod
4. 回滚计划：实验结束后自动恢复（timeout: 120s）
5. 指标验证：
   - HPA 是否触发扩容
   - 熔断是否正常打开
   - 是否有级联故障
6. 复盘：记录观察到的行为与假设的差异
```

### 关键安全举措
- **先小后大**：1 实例 → 1 节点 → 1 可用区 → 全局
- **Blast Radius 白名单**：不允许影响有状态服务（数据库、缓存）
- **自动化熔断器**：预设条件触发自动回滚（如错误率 > 5%、p99 > 1000ms）
- **审计日志**：所有混沌实验记录时间、范围、结果

## 五、Netflix Chaos Monkey 案例

### 故事起源
- 2011 年 Netflix 从单体迁移到微服务 + AWS
- 为了验证系统在实例故障时仍能正常工作，开发了 Chaos Monkey
- Simian Army 系列：Chaos Monkey（随机杀实例）、Latency Monkey（注入延迟）、Conformity Monkey（合规检查）

### 效果
- **架构升级**：强制使用无状态设计、客户端重试、服务发现
- **运维成熟**：蓝绿部署、金丝雀发布成为标配
- **文化转变**：从"避免故障"到"拥抱故障，故障是必然的"

### 核心理念
> If you haven't tested your failover, it's not going to work.
> —— Netflix Tech Blog

### 现代混沌实践
- **GameDay**：定期组织故障演练
- **故障注入测试**：集成到 CI Pipeline 中
- **生产环境实验**：非关键路径 + 小比例流量
- **混沌工程平台**：自动化编排，降低人工操作风险

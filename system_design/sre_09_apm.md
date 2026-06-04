# APM 分布式追踪 — OpenTelemetry / 采样 / 链路分析 / 服务地图

## 一、OpenTelemetry SDK 集成

### 自动埋点（Instrumentation）

自动织入代码，无需修改业务逻辑：

| 语言 | 实现方式 | 支持的库 |
|------|----------|----------|
| Java | ByteBuddy Agent | Spring Boot, Tomcat, gRPC, JDBC, Kafka, Redis 等 50+ |
| Python | Monkey Patching | Flask, Django, Requests, SQLAlchemy, Redis |
| Go | 编译期注入 / API | net/http, gRPC, database/sql, Redis |
| Node.js | require hook | Express, Koa, MongoDB, Redis, Apollo |

**Java Agent 示例**：
```bash
java -javaagent:opentelemetry-javaagent.jar \
     -Dotel.service.name=payment-service \
     -Dotel.traces.exporter=otlp \
     -Dotel.exporter.otlp.endpoint=http://otel-collector:4317 \
     -jar app.jar
```

### 手动 Span（Manual Instrumentation）

需要精细控制时：
```java
Span span = tracer.spanBuilder("processPayment")
    .setSpanKind(SpanKind.SERVER)
    .setAttribute("payment.amount", amount)
    .setAttribute("payment.method", method)
    .startSpan();

try (Scope scope = span.makeCurrent()) {
    // 业务逻辑
    result = paymentGateway.charge(amount);
    span.setAttribute("payment.success", true);
} catch (Exception e) {
    span.setAttribute("payment.success", false);
    span.recordException(e);
    throw e;
} finally {
    span.end();
}
```

### OpenTelemetry Collector
```
服务 → OTel Agent/SDK → OTel Collector → 后端（Jaeger/Zipkin/Prometheus/ES）
```
- **Pipeline**（Receivers → Processors → Exporters）
- **Batch Processing**：合并 span 批量发送，减少网络开销
- **Attribute 过滤**：移除敏感字段（手机号、密码）
- **Tail-based Sampling**：在 Collector 层做智能采样

## 二、采样策略

### 头采样（Head-based Sampling）
- **概率采样**：决策在请求进入时做，每个请求独立（如 10%）
  - 优点：简单、性能开销小
  - 缺点：可能漏掉慢请求或异常请求
- **速率限制采样**：每秒最多采样 N 个 span

### 尾采样（Tail-based Sampling）
- 请求完成后，根据条件做决策
- **条件采样**：
  - 延迟 > p99 阈值的请求全采
  - 返回错误的请求全采
  - 正常请求按比例采（如 5%）
- 优点：保证"有价值的"请求被采集
- 缺点：需要缓冲所有 span 再做决策，内存开销大

### 自适应采样
- 根据流量动态调整采样率
- 低流量时全采，高流量时降采样
- **Jaeger 自适应采样**：基于服务级别的 QPS 自动调节

## 三、链路分析（Trace Analysis）

### 瓶颈识别
1. **Span 耗时排序**：在 Trace 内查找耗时最长的 Span
2. **Hot Spot 分析**：跨 Trace 聚合同类 Span，定位慢服务/操作
3. **依赖异常传播**：服务 A 的 500 → 查看子调用链 → 数据库慢查询

```yaml
# 关键分析维度
- 服务级别：平均延迟, p50, p99, 错误率
- 操作级别：/api/orders/create 的端到端时间
- 数据库级别：SQL 查询耗时、连接池等待时间
- 外部调用：第三方 API 响应时间、gRPC 调用延迟
```

### SLA 指标与 SLO 监控
- **Apdex**（Application Performance Index）：用户满意度评分
- **RED 方法**：Rate（请求率）、Errors（错误率）、Duration（延迟）
- **USE 方法**：Utilization、Saturation、Errors（适用于基础设施）

## 四、服务地图（Service Map）

### 自动构建
- **基于 Trace 数据**：分析服务间的 Span 父子关系
- **流量拓扑**：节点（服务）+ 边（调用量/延迟/错误率）
- **实时更新**：服务上下线自动反映在拓扑上

### 典型应用
- **依赖发现**：找出未被记录的隐式依赖（如某服务直接调数据库）
- **调用链分析**：识别"扇出"（Fan-out）过多的服务
- **风险传播**：高扇出的服务故障会连锁影响大量下游

## 五、APM 工具对比

| 特性 | Jaeger | Zipkin | SkyWalking | Pinpoint | Datadog |
|------|--------|--------|------------|----------|---------|
| 架构 | Collector+Query+Agent | Server+Storage | OAP+Agent+UI | Collector+HBase+Agent | SaaS |
| 存储 | ES/Cassandra/Badger | ES/Cassandra | ES/BanyanDB | HBase | SaaS |
| Auto-instrument | OTel Agent | Brave | ByteBuddy | 字节码增强 | dd-java-agent |
| 服务地图 | ✅ | 基础 | ✅ 丰富 | ✅ | ✅ |
| 告警 | 基础 | ❌ | ✅ 内置 | ❌ | ✅ 全面 |
| 部署复杂度 | 中 | 低 | 中 | 高（依赖 HBase） | 低（SaaS） |
| 性能开销 | < 5% | < 5% | < 10% | < 10% | < 3% |
| 社区活跃度 | CNCF 毕业 | 较成熟 | Apache 顶级 | Naver | 商业 |
| 适用场景 | 通用/开源 | 轻量化 | 微服务/中间件 | Java 深度 | 商业化/多云 |

### 选择建议
- **Jaeger + OpenTelemetry**：社区通用方案，推荐首选
- **SkyWalking**：国内主流，对 Java 中间件（Dubbo、Spring Cloud）支持最好
- **Datadog APM**：钱多省心，开箱即用，全栈可观测
- **Pinpoint**：已较少使用，依赖 HBase 运维复杂

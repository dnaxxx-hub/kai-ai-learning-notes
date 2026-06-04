# SRE 纵深 Roadmap — 8课汇总

| # | 课程 | 核心内容 |
|:-:|------|----------|
| 6 | **可观测性三大支柱** | Metrics(Prometheus/OpenMetrics) / Logging(ELK/Loki) / Tracing(OpenTelemetry) 关系与标准 |
| 7 | **Prometheus深度** | 指标类型(Counter/Gauge/Histogram/Summary) / PromQL(sum/rate/histogram_quantile) / 告警规则 / 高可用(Thanos) / 存储优化 |
| 8 | **ELK日志体系** | Logstash管道(grok/geoip) / ES索引(分片/ILM) / Kibana / Loki对比 / 日志成本控制(采样/热温冷) |
| 9 | **APM分布式追踪** | OpenTelemetry SDK(自动/手动) / 采样(头/尾/自适应) / 链路分析 / 服务地图 / 工具对比 |
| 10 | **容器K8s运维** | Pod生命周期(探针) / 资源管理(cgroup/OOM) / 调度策略 / HPA/VPA/cluster-autoscaler / 安全策略 |
| 11 | **混沌工程** | 原则 / LitmusChaos/ChaosBlade / 实验类型(CPU/网络/节点故障) / Netflix Chaos Monkey |
| 12 | **容灾与备份** | RPO/RTO / 备份策略(全量/增量/异地) / 异地多活(两地三中心) / 故障切换 / GameDay |
| 13 | **故障响应** | Severity P0-P3 / On-call轮值 / Incident流程(发现→缓解→复盘) / 5Whys / 工具对比 |

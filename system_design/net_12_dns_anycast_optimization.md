# 计算机网络 #12：DNS 与任播优化

## DNS 协议深度
- 标准查询：UDP 53，最多 512 字节（无 EDNS）
- EDNS（RFC 6891）：扩展机制，支持 >512 字节
- DNSSEC（RFC 4033-4035）：数字签名验证，防 DNS 劫持
- DNS-over-HTTPS（DoH）：HTTPS 加密传输，防中间人
- DNS-over-TLS（DoT）：独立 TLS 连接

## 全球 DNS 架构
```
客户端 → 递归解析器(ISP/8.8.8.8) → 根服务器(13组) → TLD(.com/.cn) → 权威服务器
```
- 13 组根服务器（A-M），除 letter 外还有 hundreds of instances via Anycast
- 递归解析器缓存结果（TTL 控制）

## 任播路由（Anycast）
- 同一 IP 从多个位置通告 BGP
- 路由到最近的可用节点
- 常用：DNS 根服务器、CDN 边缘节点、Cloudflare 1.1.1.1

## CDN 调度策略
| 调度方式 | 粒度 | 实时性 | 延迟 |
|----------|------|--------|------|
| DNS 调度 | 域名级 | 分钟级 | 低 |
| HTTP 重定向 | URL 级 | 请求级 | 中 |
| GSLB | IP 级 | 秒级 | 中 |

## 实践经验
- 合理配置 TTL：稳定性（高 TTL）vs 灵活性（低 TTL）
- ALIAS 记录：CNAME 在根域不可用时的替代
- GeoDNS：按地理位置返回不同 IP
- DNS 防 DDoS：Anycast + 多节点 + 流量清洗

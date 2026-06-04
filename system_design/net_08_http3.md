# 计算机网络 #8：HTTP/3

## QPACK 头部压缩
- HTTP/2 的 HPACK 依赖有序流（TCP 保证顺序）
- QUIC 的流独立，不能有序 → QPACK 重新设计
- 编解码器 + 动态表在两个端点维护
- 通过专用单向流同步表更新

## HTTP/3 帧结构
```
QUIC Stream (ID=0, 单向控制流)
└── HTTP/3 Frame
    ├── DATA        (请求/响应体)
    ├── HEADERS     (QPACK 压缩的头)
    ├── SETTINGS    (配置参数)
    ├── GOAWAY      (优雅关闭)
    └── CANCEL_PUSH (取消推送)
```
- 单向控制流（Stream 0）：SETTINGS / GOAWAY
- 双向请求流：HEADERS + DATA
- 推送流（服务器主动推送，已弃用）

## 服务端推送（已弃用）
- HTTP/2 的服务端推送效果不好（客户端可能已缓存）
- HTTP/3 仍保留 `CANCEL_PUSH` 帧，但建议不再使用
- 替代：`103 Early Hints` + 预加载链接

## 迁移到 HTTP/3 方案
1. 客户端库：quiche(Cloudflare) / msquic(MS) / lsquic(LiteSpeed)
2. 反向代理：nginx(quiche patch) / Caddy / H2O
3. CDN：Cloudflare / Fastly 全量支持
4. 回退：ALT-SVC header 宣告 HTTP/3 支持，无法连接回退到 HTTP/1.1/2

## 实践
```nginx
# nginx + quiche
listen 443 quic reuseport;
add_header Alt-Svc 'h3=":443"; ma=86400';
```

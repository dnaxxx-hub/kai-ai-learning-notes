# 安全协议实战

## TLS 1.3 握手

TLS 1.3 (RFC 8446) 大幅简化握手流程，移除不安全特性，默认使用 (EC)DHE 密钥交换。

### 完整握手（1-RTT）

```
Client                          Server
  |                                |
  |--- ClientHello (key_share) --->|
  |                                |
  |<-- ServerHello + Encrypted     |
  |    Extensions + Certificate    |
  |    + CertificateVerify +       |
  |    ServerFinished              |
  |                                |
  |--- ClientFinished ------------>|
  |                                |
  |<======== Application Data =====|
```

- **ClientHello**: 加密套件列表 + key_share (ECDHE 公钥)
- **ServerHello**: 选定套件 + 服务器 key_share
- **证书验证**: Certificate + CertificateVerify 签名认证
- **Finished**: HMAC 确认握手完整

### PSK / 0-RTT（Pre-Shared Key）

预共享密钥模式，重复连接时无需完整握手：

```
0-RTT:
Client --- ClientHello (PSK + early_data) --->
Server <--- ServerHello + ServerFinished ------->
         <====== Application Data (immediately)  |
```

**风险**: 0-RTT 数据易受重放攻击，需要服务端去重检测。

## WireGuard 协议

WireGuard 是极简 VPN 协议（~4000 行代码），内核内实现。

### 协议结构：Noise_IKpsk2

基于 Noise Protocol Framework 的 Noise_IKpsk2 模式。

| 步骤 | 方向 | 内容 |
|------|------|------|
| 1 | ← | 服务器静态公钥 (s) |
| 2 | → | 临时公钥 (e) + 加密的静态公钥 |
| 3 | ← | 服务器临时公钥 (e') + 加密负载 |

### KDF（密钥派生函数）

基于 Blake2s + HKDF 的链式派生：

```
KDF1: 临时密钥 = HKDF(PRK, initiator_ephemeral)
KDF2: 发送密钥 = HKDF(临时密钥, DH(...))
KDF3: 接收密钥 = HKDF(发送密钥, DH(...))
```

### 对等管理

- **CryptoKey Routing**: 每个对等体（peer）绑定一个公钥 + 允许的 IP 范围
- **沉默协议**: 不对非对等的连接做任何响应（抗端口扫描）
- **会话过期**: 3 分钟内无数据自动销毁会话

```bash
# 配置 WireGuard
[Interface]
PrivateKey = <private_key>
Address = 10.0.0.1/24

[Peer]
PublicKey = <peer_public_key>
AllowedIPs = 10.0.0.2/32
Endpoint = 203.0.113.2:51820
```

## OpenSSL 编程

### SSL_CTX 生命周期

```c
// 1. 初始化
SSL_library_init();
SSL_CTX *ctx = SSL_CTX_new(TLS_server_method()); // 或 TLS_client_method()

// 2. 加载证书和密钥
SSL_CTX_use_certificate_file(ctx, "cert.pem", SSL_FILETYPE_PEM);
SSL_CTX_use_PrivateKey_file(ctx, "key.pem", SSL_FILETYPE_PEM);

// 3. 设置验证模式
SSL_CTX_set_verify(ctx, SSL_VERIFY_PEER | SSL_VERIFY_FAIL_IF_NO_PEER_CERT, verify_callback);

// 4. 创建 SSL 对象
SSL *ssl = SSL_new(ctx);
SSL_set_fd(ssl, socket_fd);

// 5. 握手
SSL_accept(ssl);   // 服务端
SSL_connect(ssl);  // 客户端

// 6. 数据传输
SSL_read(ssl, buf, size);
SSL_write(ssl, data, len);
```

### 证书链验证回调

```c
int verify_callback(int preverify_ok, X509_STORE_CTX *ctx) {
    X509 *cert = X509_STORE_CTX_get_current_cert(ctx);
    int err = X509_STORE_CTX_get_error(ctx);
    
    if (!preverify_ok) {
        // 自定义验证逻辑
        // 检查 subject/issuer/自签名/过期等
        return 1; // 跳过检查（危险！仅测试用）
    }
    return 1;
}
```

**安全警告**: 生产环境必须检查证书链和主机名（`SSL_CTX_set1_host()`）。

## 常见攻击

| 攻击 | 目标协议 | 原理 | 缓解 |
|------|---------|------|------|
| **BEAST** (2011) | TLS 1.0 (CBC) | 选择明文攻击破 CBC IV | 升级 TLS 1.1+ |
| **CRIME** (2012) | TLS 压缩 | 压缩后长度泄露明文 | 禁用压缩 |
| **POODLE** (2014) | SSL 3.0 | Padding oracle 破 CBC | 弃用 SSL 3.0 |
| **Heartbleed** (2014) | OpenSSL (TLS) | 心跳扩展越界读 | 升级 OpenSSL 1.0.1g+ |
| **Logjam** (2015) | DHE_EXPORT | 降级 DHE 至 512-bit | 禁用 EXPORT 套件 |
| **DROWN** (2016) | SSLv2 + TLS | 利用 SSLv2 破 TLS | 禁用 SSLv2 |

### Heartbleed（CVE-2014-0160）

漏洞代码在 `t1_lib.c` 的心跳处理函数中：

```c
// 漏洞: payload 长度未检查，memcpy 直接从心跳请求中读取
memcpy(bp, pl, payload);  // payload 由攻击者控制！
// 泄露的内容: 服务器内存中的密钥、会话 Cookie、用户数据
```

**检查**: `openssl version -a` 查看版本是否为 1.0.1~1.0.1f。

## mTLS 双向认证

TLS 加强版：客户端也需要提供证书。

```
Client                          Server
  |                                |
  |--- ClientHello --------------->|
  |<-- ServerHello + Certificate   |
  |    + CertificateRequest        |  ← 要求客户端证书
  |--- Certificate (client) ------>|  ← 客户端提供证书
  |--- CertificateVerify --------->|
  |--- Finished ------------------>|
  |<-- Finished -------------------|
  |<====== Application Data ======>|
```

### 配置（OpenSSL）

```c
// 服务端要求客户端证书
SSL_CTX_set_verify(ctx, 
    SSL_VERIFY_PEER | SSL_VERIFY_FAIL_IF_NO_PEER_CERT,
    verify_callback);

// 设置信任的 CA 列表（验证客户端证书用）
SSL_CTX_load_verify_locations(ctx, "ca.crt", NULL);

// 客户端加载自己的证书
SSL_CTX_use_certificate_file(ctx, "client.crt", SSL_FILETYPE_PEM);
SSL_CTX_use_PrivateKey_file(ctx, "client.key", SSL_FILETYPE_PEM);
```

**应用场景**: Kubernetes (kubelet API)、gRPC 鉴权、企业内部微服务认证。

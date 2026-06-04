# TLS/安全传输 — 加密通信基石

## 为什么需要 TLS？

| 风险 | 无TLS | 有TLS |
|------|-------|-------|
| 窃听(Eavesdropping) | 明文流量可抓包 | 加密不可读 |
| 篡改(Tampering) | 中间人可以改数据 | 完整性校验, 篡改即被发现 |
| 冒充(Impersonation) | 可伪造服务器 | 证书验证身份 |

## TLS 1.3 握手流程 (1-RTT)

```
Client                                               Server
  |                                                    |
  | ── ClientHello ──────────────────────────────────>  |
  |  随机数 + 支持的密码套件列表 + Key Share(公钥)       |
  |                                                    |
  | <── ServerHello ─────────────────────────────────  |
  |  选定的密码套件 + 服务器Key Share(公钥) + 证书      |
  |                                                    |
  | <── EncryptedExtensions + Finished ──────────────  |
  |  服务器握手完成                                    |
  |                                                    |
  | ── Finished ─────────────────────────────────────>  |
  |  客户端握手完成                                    |
  |                                                    |
  | ======== 握手完成, 开始加密通信 ==================== |
  | ── Application Data (HTTP请求) ────────────────>   |
  | <── Application Data (HTTP响应) ────────────────── │
```

### TLS 1.3 相比 1.2 的改进

| 特性 | TLS 1.2 | TLS 1.3 |
|------|---------|---------|
| 握手 | 2-RTT | 1-RTT (0-RTT复用) |
| 密码套件 | 30+种(太多) | 5种(精简) |
| 支持前向安全 | 可选 | 强制 |
| 0-RTT | 不支持 | 支持 |
| 会话恢复 | Session ID/Ticket | PSK + 0-RTT |
| 移除了 | - | RSA密钥交换, 静态DH, RC4, 3DES等不安全算法 |

### 0-RTT 会话恢复

```
Client (有之前会话的 PSK)
  |                                                    |
  | ── ClientHello + PSK + 0-RTT Data ──────────────>  |
  |  首次包就发了加密请求!(如HTTP GET /index.html)      |
  |                                                    |
  | <── ServerHello + Finished ─────────────────────  |
  |                                                    |
  | <── Application Data (响应) ────────────────────── |
```

**注意**: 0-RTT 数据有重放攻击风险 → 不使用POST/写操作。

## 证书链 (Certificate Chain)

```
客户端信任根(Root CA)            例:
      │                          DigiCert Global Root CA (自签名)
      │                          指纹已知, 嵌入操作系统/浏览器
  中间CA(Intermediate CA)
      │                          DigiCert TLS RSA SHA256 2020 CA1
      │                          由根CA签署
  服务器证书(Leaf/End-Entity)
      │                          *.google.com
                                 由中间CA签署
```

### 证书验证过程

```
1. 浏览器收到服务器证书 *.google.com
2. 检查证书链: *google.com ← 中间CA1 ← 根CA
3. 验证签名: 每级用上级公钥验证签名
4. 检查有效期: notBefore - notAfter
5. 检查域名: CN/SAN 中是否包含目标域名
6. 检查吊销状态: CRL / OCSP
7. 全部通过 → 建立信任
```

### X.509 证书结构

```
Certificate:
    Version: 3 (0x02)
    Serial Number: 1234567890
    Signature Algorithm: sha256WithRSAEncryption
    Issuer: C=US, O=DigiCert Inc, CN=DigiCert TLS RSA SHA256 2020 CA1
    Validity
        Not Before: Oct 15 00:00:00 2023
        Not After : Oct 14 23:59:59 2024
    Subject: C=US, ST=California, L=Mountain View, O=Google LLC, CN=*.google.com
    Subject Public Key Info:
        Public Key Algorithm: id-ecPublicKey
            Public-Key: (256 bit)
            pub: 04:xx:xx:xx:...
    X509v3 extensions:
        Subject Alternative Name (SAN): *.google.com, google.com, *.youtube.com
        Extended Key Usage: TLS Web Server Authentication
```

## 加密套件 (Cipher Suite)

### TLS 1.2 格式
```
TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
 │     │    │       │         │
 │     │    │       │         └── PRF哈希算法(HMAC-SHA256)
 │     │    │       └── AEAD加密算法(AES-128-GCM)
 │     │    └── 认证算法 (证书类型: RSA)
 │     └── 密钥交换 (ECDHE - 椭圆曲线Diffie-Hellman)
 └── 协议
```

### TLS 1.3 格式 (精简为5种)

| 套件 | 用途 |
|------|------|
| TLS_AES_128_GCM_SHA256 | 标准推荐, 高性能 |
| TLS_AES_256_GCM_SHA384 | 高安全性, 稍慢 |
| TLS_CHACHA20_POLY1305_SHA256 | 移动端(无AES硬件加速时快) |
| TLS_AES_128_CCM_SHA256 | IoT设备(低资源) |
| TLS_AES_128_CCM_8_SHA256 | 极高限制场景 |

**TLS 1.3 只保留了 AEAD 加密**:
- 加密+认证一步完成
- 移除了CBC模式(易受padding oracle攻击)
- 强制前向安全(PFS): 私钥泄露不影响历史会话

## 前向安全 (Perfect Forward Secrecy)

```
非PFS (RSA密钥交换):
  服务器私钥泄露 → 所有历史会话可被解密

PFS (ECDHE密钥交换):
  临时会话密钥: 每次握手生成临时公钥/私钥对
  服务器私钥泄露 → 无法解密历史会话(因为临时密钥已丢弃)
  
  结论: PFS保护了**历史通信**安全
```

## SNI (Server Name Indication)

**问题**: 一台服务器托管多个TLS站点, 握手的时不知道客户端请求哪个域名。

**解决**: SNI 扩展允许客户端在 ClientHello 中发送目标域名。

```
ClientHello:
  ...
  extensions:
    server_name (type=host_name, value=www.example.com)
    ...

服务器根据域名选择对应证书:
  - www.example.com → example.com 证书
  - www.google.com  → google.com 证书
```

**SNI 的问题**: 明文传输域名 → 被中间人窥探访问了哪些网站。
**解决方案**: ECH (Encrypted Client Hello) — 加密SNI, 仍处于标准化中。

## 实操命令

```bash
# 查看服务器的TLS证书链
openssl s_client -connect google.com:443 -showcerts

# 查看详细TLS信息
openssl s_client -connect google.com:443 -debug

# 测试TLS版本支持
openssl s_client -tls1_2 -connect example.com:443
openssl s_client -tls1_3 -connect example.com:443

# 测试OCSP stapling
openssl s_client -connect google.com:443 -status

# 查看证书详情
openssl x509 -in cert.pem -text -noout

# 生成自签名证书(测试用)
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout key.pem -out cert.pem \
  -days 365 \
  -subj "/CN=localhost"

# 查看SSL/TLS握手调试
curl -v https://example.com
# 输出中 * SSL connection using TLSv1.3 / AES256-GCM-SHA256

# SSLyze 扫描 (安装: pip install sslyze)
sslyze --regular example.com:443

# testssl.sh 完整检测
./testssl.sh --full example.com
```

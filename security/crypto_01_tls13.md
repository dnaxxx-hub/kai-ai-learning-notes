# TLS 1.3 握手全流程深度

> 从 TCP→TLS→HTTP/2 的完整安全会话建立

## 一、TLS 演进时间线

```
TLS 1.0 (1999) ── SSL 3.0 升级版, RC4/MD5
TLS 1.1 (2006) ── CBC 防护, 移除 CBC IV 可预测
TLS 1.2 (2008) ── AEAD (GCM/CCM), SHA256, ECDHE
TLS 1.3 (2018) ── 1-RTT/0-RTT, 移除不安全套件, 强制PFS
```

## 二、TLS 1.3 1-RTT 握手 (完整握手)

```
Client                                    Server
  │                                          │
  │  ── ClientHello ──────────────────────►  │
  │   - 支持的 cipher suites                │
  │   - key_share (EC DHE 公钥)            │
  │   - supported_versions: 1.3             │
  │   - signature_algorithms                │
  │   - session_id (兼容)                   │
  │                                          │
  │  ◄── ServerHello ─────────────────────  │
  │   - 选择的 cipher suite                 │
  │   - key_share (服务器 ECDHE 公钥)       │
  │   - 协商的版本: 1.3                     │
  │                                          │
  │  ◄── EncryptedExtensions ─────────────  │
  │   - ALPN (HTTP/2)                       │
  │   - server_name 确认                    │
  │                                          │
  │  ◄── Certificate ────────────────────  │
  │   - 服务器证书链 (X.509 v3)             │
  │   - (可选) OCSP Stapling                │
  │                                          │
  │  ◄── CertificateVerify ──────────────  │
  │   - 证书私钥签名 (证明持证)              │
  │                                          │
  │  ◄── Finished ──────────────────────  │
  │   - HMAC 验证握手完整性                  │
  │                                          │
  │  此时双方都有 (EC)DHE 共享密钥 +         │
  │  证书链已验证 = handshake_secret         │
  │                                          │
  │  ── Finished ────────────────────────►  │
  │   - 客户端验证握手完整性                  │
  │                                          │
  │  ── Application Data ───────────────►  │
  │   - 受 AEAD 加密保护的数据               │
  │                                          │
  ✅ 连接建立 (1-RTT, 实际2次往返)
```

### 1-RTT 关键优化

相比 TLS 1.2，TLS 1.3 减少到 1-RTT：
- 不再需要单独的 ServerKeyExchange / ClientKeyExchange 消息
- key_share 直接在 ClientHello 中发送 → 减少1次RTT
- 服务器可以在 Certificate 之后立即发出 Finished

## 三、TLS 1.3 0-RTT (会话恢复)

```
Client                                    Server
  │                                          │
  │  ── ClientHello ──────────────────────►  │
  │   - pre_shared_key (PSK)                │
  │   - early_data (应用数据)               │
  │   - key_share (DH 公钥)                 │
  │                                          │
  │  ◄── ServerHello ─────────────────────  │
  │  ◄── EncryptedExtensions ─────────────  │
  │  ◄── (Early Data 已接收)              │
  │  ◄── Finished ──────────────────────  │
  │                                          │
  │  ── Finished ────────────────────────►  │
  │                                          │
  ✅ 0-RTT — 客户端在第一个包中就发送数据
```

### 0-RTT 风险
- **重放攻击**: 0-RTT 数据可能被中间人截获重放
- 服务器必须使用重放缓冲区或限制 0-RTT 为幂等操作
- 典型应用: HTTP GET 请求（安全），POST 转账（不安全）

## 四、密钥派生链

```
(EC)DHE 共享密钥
    │
    ▼
early_secret   ← PSK (预共享密钥或 0)
    │
    ▼
handshake_secret  ← (EC)DHE 输出
    │
    ├─ client_handshake_traffic_secret
    ├─ server_handshake_traffic_secret
    │
    ▼
master_secret
    │
    ├─ client_application_traffic_secret  → 客户端流量密钥
    ├─ server_application_traffic_secret  → 服务器流量密钥
    ├─ exporter_master_secret             → 密钥导出
    └─ resumption_master_secret           → 会话恢复
```

### HKDF 扩展 (HMAC-based Key Derivation Function)

```
HKDF-Extract(salt, ikm) → PRK
    HMAC-Hash(salt, ikm)  // 提取伪随机密钥

HKDF-Expand(PRK, info, L) → OKM
    T(0) = ""
    T(i) = HMAC-Hash(PRK, T(i-1) || info || i)
    OKM = first L bytes of T(1) || T(2) || ...
```

## 五、TLS 1.3 vs 1.2 对比

| 特性 | TLS 1.2 | TLS 1.3 |
|------|---------|---------|
| 握手RTT | 2-RTT | 1-RTT / 0-RTT |
| 密码套件 | ~37种 | 5种 (AEAD only) |
| PFS | 可选 | 强制 |
| 静态RSA | ✅ | ❌ 移除 |
| 压缩 | ✅ | ❌ 移除 |
| 重协商 | ✅ | ❌ 移除 |
| DH 参数在握手最初 | ❌ (ServerKeyExchange) | ✅ (ClientHello key_share) |
| 加密的证书 | ❌ | ✅ |

## 六、TLS 1.3 只保留 5 种密码套件

```
TLS_AES_128_GCM_SHA256        — 最常用, 硬件加速
TLS_AES_256_GCM_SHA384        — 更高安全
TLS_CHACHA20_POLY1305_SHA256  — 移动端, 无AES硬件时
TLS_AES_128_CCM_SHA256        — IoT/受限设备
TLS_AES_128_CCM_8_SHA256      — 更短MAC, 几乎不用
```

## 七、证书链验证

```
客户端收到 Certificate 消息:
    Server Certificate (叶证书)
        ↑ 签名
    Intermediate CA Certificate
        ↑ 签名
    Root CA Certificate (信任锚, 不在TLS中发送)
        ↓
    客户端检查:
    1. 每个签名的有效性和算法
    2. 证书是否过期
    3. 是否被吊销 (CRL / OCSP)
    4. 域名是否匹配 SubjectAltName
```

## 八、实际抓包分析

```
Wireshark 过滤: tls.handshake.type == 1 (ClientHello)

No.  Type      Info
 1   ClientHello  Version: TLS 1.3, Cipher Suites: 17 suites
       Key Share: secp256r1 (x25519 offered)
       ALPN: h2, http/1.1
 2   ServerHello  Version: TLS 1.3, Cipher: TLS_AES_128_GCM_SHA256
       Key Share: secp256r1
 3   EncryptedExtensions  ALPN: h2
 4   Certificate  1 cert (2048-bit RSA)
 5   CertificateVerify  signature: rsa_pss_rsae_sha256
 6   Finished  verify_data: 32 bytes
 7   Finished  verify_data: 32 bytes
 8   Application Data  (encrypted HTTP/2 Settings)
```

---

**一句话总结**: TLS 1.3 通过减少握手RTT、移除不安全选项、强制PFS，在保证安全的同时将握手延迟降低 50%-100%。

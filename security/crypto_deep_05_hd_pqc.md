# HD钱包 + 抗量子密码

> 密钥管理的实践密码学

## 一、HD钱包 (Hierarchical Deterministic Wallet)

### BIP32 — 分层确定性

问题：如果每个地址单独生成密钥，备份就是噩梦。

```text
BIP32 方案:
        
        主种子 (Mnemonic → Seed)
            │
        ┌───┴───┐
    主密钥(m)    主链码(c)
        │
    ┌───┼──────────────┐
    │                │
  子密钥(m/0)      子密钥(m/1)
    │                │
  m/0/0  m/0/1     m/1/0
```

### 密钥派生

```
CKDpriv((k_par, c_par), i) → (k_i, c_i)

// 普通派生 (i < 2^31)
I = HMAC-SHA512(c_par, Ser_P(point(k_par)) || Ser_32(i))
  k_i = parse_256(I_L) + k_par (mod n)
  c_i = I_R

// 硬化派生 (i >= 2^31)
I = HMAC-SHA512(c_par, 0x00 || ser_256(k_par) || Ser_32(i))
  k_i = parse_256(I_L) + k_par (mod n)
  c_i = I_R
```

**硬化 vs 普通**：
- 普通: 知道父公钥 + i 可以算出子公钥
- 硬化: 必须知道父私钥才能派生

### BIP39 — 助记词

将 128-256 位熵编码为助记词:

```
熵 (128bit)
  │  SHA256 前 4bit 作为校验和
  ▼
132bits → 11bit × 12组 → 12个助记词（2048词库）

助记词
  │  PBKDF2(password=mnemonic, salt="mnemonic"+passphrase, 2048轮)
  ▼
种子 (512bit)
  │  HMAC-SHA512
  ▼
主密钥 + 主链码
```

### BIP44 — 多币种路径

```
m / purpose' / coin_type' / account' / change / address_index

m/44'/0'/0'/0/0   ← 比特币的第一个地址
m/44'/60'/0'/0/0  ← 以太坊的第一个地址
m/44'/195'/0'/0/0 ← TRON的第一个地址

purpose': 44=BIP44
coin_type': 0=BTC, 60=ETH, 195=TRX
account': 用户账户
change: 0=外部地址(收款), 1=找零地址
address_index: 第N个地址
```

### 硬件钱包安全

```
硬件钱包 ── USB/BLE ── PC/手机
    │                       │
 安全芯片 → 私钥永远不离开    │
    │                       │
 签名请求 ←──── 交易数据 ─────
    │                       │
 交易签名 ────→ 广播到网络
```

**威胁模型**：
- 即使 PC 被攻破，私钥安全
- 侧信道攻击: 功耗分析、电磁辐射 → 需要安全芯片 (Secure Element)
- 物理攻击: 探针 → 封装防护 + 零化

## 二、抗量子密码 (Post-Quantum Cryptography)

### 为什么需要？

Shor算法理论证明: `O(log³ n)` 时间内分解大整数

| 算法 | 经典复杂度 | 量子复杂度 | 受影响 |
|------|-----------|-----------|--------|
| RSA-2048 分解 | ~2¹⁰²⁴ | ~2³⁰ (~1秒) | ❌ |
| ECDH (secp256k1) | ~2¹²⁸ | ~2⁸⁶ | ❌ |
| SHA-256 | ~2²⁵⁶ | ~2¹²⁸ (Grover) | 减半, 仍安全 |
| AES-128 | ~2¹²⁸ | ~2⁶⁴ (Grover) | 用AES-256 |

### NIST PQC 标准 (2024年选定的获胜方案)

#### 1. CRYSTALS-Kyber (KEM — 密钥封装)

```
Kyber-512: NIST Level 1 (≈ AES-128)
Kyber-768: NIST Level 3 (≈ AES-192)
Kyber-1024: NIST Level 5 (≈ AES-256)

基于 Module-LWE (Learning With Errors):
  Given:   A (k×k 矩阵), t = A·s + e
  Find:    s (私钥)
  Hard:    e 是小的随机噪声

密钥大小 (Kyber-768):
  公钥: 1184 bytes (RSA-2048的1/2)
  私钥: 2400 bytes
  密文: 1088 bytes
```

#### 2. CRYSTALS-Dilithium (数字签名)

```
Dilithium-2: 签名大小 ~2420 bytes
基于 Module-LWE + Module-SIS

签名生成:
  z = y + c·s₁   (其中 y 是掩码, c 是挑战哈希, s₁ 是私钥)
  如果 z 太大 → 重新开始 (拒绝采样)
```

#### 3. FALCON (替代签名方案)

```
签名大小: 666 bytes (比Dilithium小3.7倍!)
基于: NTRU格
缺点: 实现复杂 (浮点FFT)
```

### 格密码基础 (Lattice)

```
格 L = { a₁·b₁ + a₂·b₂ + ... + aₙ·bₙ | aᵢ ∈ Z }
     = 整数系数基向量的所有线性组合

几何上看: 高维空间中的"倾斜棋盘"

关键困难问题:
  SVP (最短向量问题): 在格中找到最短的非零向量
  CVP (最近向量问题): 找到距目标最近的格点
  LWE (带误差学习): 在带误差的线性方程中恢复秘密
  
  → 这些问题目前没有多项式量子算法
```

### 混合密码方案 (Hybrid)

实际部署中，TLS 1.3 密钥交换:

```
EC(DHE) + Kyber
   │         │
   ▼         ▼
共享密钥 ← 混合模式 → 共享密钥
   │              │
   └── KDF ──────┘
        │
        ▼
   应用密钥
```

这样既防御现在攻击，又防御未来量子攻击（Store Now, Decrypt Later）。

### PQC 迁移时间线

```
2024 ──── NIST 标准发布
2025-2027 ──── 浏览器/服务器逐步支持
2028-2030 ──── 大规模部署
2035 ──── 旧密码退役

建议: 新的密钥交换立即启用混合模式 (ECDH + Kyber)
```

---

**一句话总结**: HD钱包用分层派生解决密钥管理问题，PQC在量子计算到来前替换RSA/ECC。

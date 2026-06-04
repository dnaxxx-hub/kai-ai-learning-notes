# Mini Blockchain 实践 — 从零构建一个纯 Python 区块链

> **日期**: 2025-05-24  
> **作者**: AI Engineer  
> **源码**: `mini_blockchain.py`  
> **目标**: 零外部依赖，用 Python 标准库实现一个可运行的区块链节点

---

## 1. 项目架构概览

### 1.1 模块划分

```
mini_blockchain.py
├── 工具函数 (sha256, json_dumps)
├── Transaction  —— 交易结构 + 交易池
├── MerkleTree   —— Merkle 树 (交易完整性)
├── Block        —— 区块结构 (header + body)
├── Blockchain   —— 区块链主类 (挖矿/验证/共识)
├── HTTP API     —— http.server 实现的 RESTful 接口
└── CLI 入口     —— argparse 参数解析
```

### 1.2 数据流

```
用户/客户端
    │
    ▼
POST /transactions/new ───→ Transaction 对象 ──→ 交易池 (pending_transactions)
    │
    ▼
GET /mine ───→ 打包交易 + 生成 coinbase ──→ PoW 挖矿 ──→ 区块入链 ──→ 清空已挖交易
    │
    ▼
GET /chain ───→ 序列化全链数据 ──→ JSON 响应
    │
    ▼
GET /nodes/resolve ───→ 拉取对等节点链 ──→ 最长链替换 ──→ 同步状态
```

---

## 2. 核心模块设计

### 2.1 Transaction（交易）

**设计思路**: 
- 最简单模型：sender → recipient → amount
- 用 SHA-256 对整个交易内容哈希生成 `tx_id`，作为唯一标识
- `signature` 字段预留——生产环境中需要用 ECDSA 签名，这里简化为字符串
- `coinbase_tx()` 工厂函数创建矿工奖励交易，sender 为空字符串

**关键代码**:
```python
class Transaction:
    def __init__(self, sender, recipient, amount, signature=""):
        self.tx_id = sha256(json_dumps({
            'sender': sender, 'recipient': recipient,
            'amount': amount, 'signature': signature,
        }))

def coinbase_tx(recipient, reward=50.0):
    tx = Transaction(sender="", recipient=recipient, amount=reward)
    tx.signature = "coinbase"
    return tx
```

### 2.2 MerkleTree（默克尔树）

**设计思路**:
- 二叉树结构，叶子节点是交易的 `tx_id`
- 自底向上逐层哈希，每对 sibling 拼接后 SHA-256
- 奇数节点时复制最后一个节点（和比特币一样）
- 最终得到的 Merkle Root 存入区块头

**关键代码**:
```python
class MerkleTree:
    @staticmethod
    def _build_tree(leaves):
        if not leaves:
            return ""
        level = leaves[:]
        while len(level) > 1:
            if len(level) % 2 == 1:
                level.append(level[-1])  # 奇数时复制最后一个
            next_level = []
            for i in range(0, len(level), 2):
                combined = level[i] + level[i + 1]
                next_level.append(sha256(combined))
            level = next_level
        return level[0]
```

### 2.3 Block（区块）

**设计思路**:
- 区块头: `index + timestamp + merkle_root + previous_hash + nonce`
- 区块体: `transactions` 列表
- `compute_hash()` 只对区块头字段哈希（header-only）
- 每次调用 `compute_hash()` 重新计算，确保 nonce 更新后哈希变化

**关键代码**:
```python
class Block:
    def compute_hash(self):
        header = json_dumps({
            'index': self.index,
            'timestamp': self.timestamp,
            'merkle_root': self.merkle_root,
            'previous_hash': self.previous_hash,
            'nonce': self.nonce,
        })
        return sha256(header)
```

---

## 3. PoW 难度调整机制

### 工作原理

```
目标条件: block.hash.startswith("0" * difficulty)
         └── difficulty = 4 → 前4位必须是 0 → "0000xxxxxxxx..."

挖矿流程:
1. 从 nonce = 0 开始
2. 计算 block.hash = sha256(header_with_nonce)
3. 检查 hash[:difficulty] == "0" * difficulty
4. 不满足 → nonce += 1 → 回到步骤2
5. 满足 → 挖矿成功，返回 nonce
```

### 复杂度分析

| difficulty | 概率 (1/16^d) | 平均尝试次数 |
|-----------|---------------|-------------|
| 1         | 1/16          | ~16         |
| 2         | 1/256         | ~256        |
| 3         | 1/4096        | ~4K         |
| 4         | 1/65536       | ~65K        |
| 5         | 1/1,048,576   | ~1M         |

**经验**: difficulty=4 时本机约 0.5-2秒 挖一个块，适合演示。
调高到 5-6 则会显著变慢，但更接近真实网络的难度。

### 关键代码
```python
def proof_of_work(self, block):
    target = "0" * self.difficulty
    nonce = 0
    block.nonce = nonce
    while True:
        block_hash = block.compute_hash()
        if block_hash.startswith(target):
            block.hash = block_hash
            return nonce
        nonce += 1
        block.nonce = nonce
```

**注意**: 每次循环必须更新 `block.nonce` 再调用 `compute_hash()`，
否则哈希永远不会变化，陷入死循环。

---

## 4. Merkle 树构建过程

### 示例

```
交易列表: [tx_a, tx_b, tx_c, tx_d]

构建过程:
         root = H(H(ab) + H(cd))
        /                      \
  H(ab) = H(a+b)           H(cd) = H(c+d)
      /        \              /        \
  tx_a        tx_b        tx_c        tx_d

如果只有 [tx_a, tx_b, tx_c]:
         root = H(H(ab) + H(cc))
        /                      \
    H(ab)                   H(cc) = H(c+c)
    /    \                    /        \
 tx_a    tx_b              tx_c       tx_c  ← 复制
```

### 验证

在 `Blockchain.validate_block()` 中，我们重新构建 Merkle 树
并与区块中存储的 `merkle_root` 比对，以此检测交易数据是否被篡改：
```python
merkle = MerkleTree(block.transactions)
if merkle.root != block.merkle_root:
    return False  # 交易被篡改！
```

---

## 5. HTTP API 设计

### 为什么不用 Flask？

> 协议要求「零外部依赖」，所以使用标准库 `http.server`。

### 端点和用法

| 方法 | 路径 | 功能 | 请求体 | 响应 |
|------|------|------|--------|------|
| GET | `/chain` | 获取全链 | — | 完整区块链 JSON |
| POST | `/transactions/new` | 提交交易 | `{sender, recipient, amount}` | tx_id |
| GET | `/mine` | 挖矿 | — | 新块信息 |
| GET | `/validate` | 验证链完整性 | — | `{valid: bool}` |
| POST | `/nodes/register` | 注册对等节点 | `{url: ...}` | pees 列表 |
| GET | `/nodes/resolve` | 共识同步 | — | 替换结果 |
| GET | `/pending` | 待处理交易 | — | 交易列表 |

### 实现细节

- 使用 `ThreadedHTTPServer` 支持并发请求
- 所有响应添加 `Access-Control-Allow-Origin: *` 支持跨域
- 通过类变量 `BlockchainHTTPHandler.blockchain` 共享区块链实例
- 手动解析 JSON body：`self.rfile.read(content_length)`

---

## 6. 最长链共识实现

### 原理

```
节点 A (链长 5)             节点 B (链长 7)
        │                          │
        └────── 发起 resolve ──────┘
                 │
                 ▼
          B 链更长且有效
                 │
                 ▼
          A 替换为 B 的链
```

### 避免的坑

1. **必须先验证再替换** — 不能只看长度，还要验证 PoW 和哈希链
2. **用对方的 difficulty 验证？NO！** — 使用自己的 difficulty 验证，否则攻击者用 difficulty=1 随意产生长链
3. **同步时的超时** — 设置 `timeout=5` 防止网络问题卡住节点

### 关键代码
```python
def resolve_conflicts(self, other_chain_data):
    other_chain = [Block.from_dict(b) for b in other_chain_data]
    if len(other_chain) <= len(self.chain):
        return False  # 我们的链更长或等长
    if not self.validate_chain(other_chain):
        return False  # 对方链无效
    self.chain = other_chain
    return True
```

---

## 7. 遇到的坑和解决方案

### 坑 1: `json_dumps` 的一致性

**问题**: 区块链是分布式系统，不同机器上 `json.dumps` 的 key 顺序可能不同，
导致同一组数据在不同节点上算出不同的哈希。

**解决**: 使用 `sort_keys=True` 确保 key 顺序一致：
```python
def json_dumps(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'))
```
`separators=(',', ':')` 去掉空格，进一步压缩。

### 坑 2: 哈希计算的边界条件

**问题**: 空交易列表时 `MerkleTree` 返回空字符串 `""`，但 `sha256("")` 是有效哈希。
genesis block 的 previous_hash 需要特殊处理。

**解决**: genesis block 硬编码 `previous_hash = "0" * 64` 作为标志。

### 坑 3: 交易池清理

**问题**: 挖矿后 `pending_transactions` 中的 coinbase 交易也要被移除，
如果不清除，下次挖矿会包含重复交易。

**解决**: `mine_block()` 中记录所有被挖交易的 tx_id，然后 `clear_pending()` 过滤：
```python
def mine_block(self, miner_address):
    block_transactions = [coinbase] + self.pending_transactions[:]
    # ... 挖矿 ...
    mined_ids = {tx.tx_id for tx in block_transactions}
    self.clear_pending(mined_ids)
```

### 坑 4: `http.server` 是单线程的

**问题**: 默认 `HTTPServer` 是单线程的，挖矿时（同步耗时操作）
会阻塞其他 API 请求。

**解决**: 使用 `ThreadingMixIn` 或 `socketserver.ThreadingMixIn`：
```python
class ThreadedHTTPServer(http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True
```

### 坑 5: nonce 更新时机

**问题**: 如果 `while True` 循环中先计算哈希再更新 nonce，
会导致第一次计算用 nonce=0，然后 nonce 变成 1，再回来时 nonce=1 的哈希没被验证。

**解决**: 循环体顶部先 `block.nonce = nonce` 再计算：
```python
while True:
    block.nonce = nonce          # ← 先更新
    block_hash = block.compute_hash()  # ← 再计算
    if block_hash.startswith(target):
        block.hash = block_hash
        return nonce
    nonce += 1                    # ← 最后递增
```

---

## 8. 运行指南

### 启动第一个节点
```bash
python mini_blockchain.py --port 5000 --difficulty 4
```

### 启动第二个节点（连接第一个）
```bash
python mini_blockchain.py --port 5001 --difficulty 4 --peers http://localhost:5000
```

### 提交交易
```bash
curl -X POST http://localhost:5000/transactions/new \
  -H "Content-Type: application/json" \
  -d '{"sender": "alice", "recipient": "bob", "amount": 10}'
```

### 挖矿
```bash
curl http://localhost:5000/mine
```

### 查看链
```bash
curl http://localhost:5000/chain | python -m json.tool
```

### 验证
```bash
curl http://localhost:5000/validate
```

### 共识同步
```bash
curl http://localhost:5001/nodes/resolve
```

---

## 9. 未来扩展方向

### 9.1 UTXO 模型

当前是**账户/余额模型**（sender → recipient），可以改为 **UTXO 模型**：
- 每笔交易引用之前的未花费输出
- 输出包含锁定脚本（类似比特币的 Script）
- 天然支持多输入/多输出
- 更易验证双花

### 9.2 P2P 网络

当前节点通过 HTTP API 手动同步，可以改为真正的 P2P 网络：
- 使用 WebSocket 或 TCP 连接
- 节点发现（DHT/种子节点）
- 区块广播（Gossip 协议）
- 交易广播

### 9.3 轻节点（SPV）

简化支付验证（Simplified Payment Verification）：
- 只保存区块头（80字节/块），不保存完整交易
- 使用 Merkle Proof 验证交易是否包含在区块中
- 适合移动端/浏览器端

### 9.4 智能合约

- 在交易中加入可执行的脚本
- 实现简单的图灵不完备脚本语言（如比特币 Script）
- 或通过 Gas 限制实现图灵完备（如以太坊 EVM）

### 9.5 性能优化

- **调整难度**: 根据出块时间动态调整（比特币每2016块调整一次）
- **批量挖矿**: 多个 nonce 并行验证
- **持久化**: 用文件或数据库存储链（当前全在内存中）

---

## 10. 总结

这个迷你区块链项目从零实现了一个可运行的区块链节点，涵盖了：

| 概念 | 实现程度 | 说明 |
|------|---------|------|
| 区块 | ✅ | 完整区块头+区块体 |
| 链 | ✅ | 链表结构，hash 链接 |
| PoW | ✅ | 难度可调，nonce 递增 |
| 交易 | ✅ | 基础转账 + 交易池 |
| Merkle 树 | ✅ | 完整构建 + 验证 |
| 链验证 | ✅ | 哈希链接 + PoW + Merkle |
| REST API | ✅ | 7 个端点，http.server |
| 共识 | ✅ | 最长链替换 |
| 签名 | ⚠️ | 字段预留，未实现 ECDSA |
| 持久化 | ❌ | 仅内存存储 |
| P2P | ❌ | HTTP API 手动同步 |

**核心理念**: 区块链 = 链表 × 哈希函数 × 共识机制
- 链表保证顺序
- 哈希保证不可篡改
- PoW 保证出块成本
- 最长链规则保证一致性

---

> **下一步**: 可以基于这个框架添加 UTXO、P2P 广播、动态难度等特性，
> 逐步将其发展为一个功能完整的区块链系统。

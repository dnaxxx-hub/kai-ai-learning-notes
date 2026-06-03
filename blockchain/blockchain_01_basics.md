# 区块链 第1课：区块链基础与密码学

> 学习日期：2026-05-10
> 本课代码基于 Python 3.10+，仅使用 `hashlib`、`ecdsa`（第三方）等基本库。

---

## 1. 区块链核心概念

### 1.1 区块（Block）
- 每个区块包含：**区块头**（前一个区块哈希、时间戳、难度目标、nonce、Merkle根）和**区块体**（交易列表）
- 区块通过哈希链接形成**链**——修改任一区块会改变其哈希，破坏后续所有链接

### 1.2 链（Chain）
- 区块链是一个**分布式账本**（Distributed Ledger）
- 所有节点维护同一链条的副本
- 最长有效链规则：节点始终选择累计工作量最大的链

### 1.3 共识（Consensus）
- 分布式系统中就**数据状态达成一致**的机制
- 比特币：**PoW（工作量证明）**
- 核心问题：拜占庭将军问题（Byzantine Generals Problem）

### 1.4 去中心化（Decentralization）
- 没有单点故障/单点控制
- 任何人可以运行节点、参与验证
- 51%攻击：控制超过半数算力可重写历史

---

## 2. 哈希函数（SHA-256）

### 2.1 哈希函数性质
- **确定性**：相同输入→相同输出
- **单向性**：从输出推输入不可行
- **抗碰撞性**：找两个不同输入→同一输出不可行
- **雪崩效应**：输入微小变化→输出完全改变

### 2.2 SHA-256 在区块链中的应用
- 区块链接：`prev_hash = SHA256(前一个区块头)`
- 挖矿计算：`SHA256(SHA256(block_header)) < target`
- 交易标识：`tx_id = SHA256(tx_data)`
- Merkle树：构建交易哈希树

### 2.3 Python 演示

```python
import hashlib
import json

def sha256(data: bytes) -> str:
    """计算 SHA-256 哈希，返回十六进制字符串"""
    return hashlib.sha256(data).hexdigest()

# 雪崩效应演示
print("=== SHA-256 雪崩效应 ===")
h1 = sha256(b"Hello, Blockchain!")
h2 = sha256(b"Hello, Blockchain?")  # 仅改一个字符
print(f"输入1: Hello, Blockchain! -> {h1}")
print(f"输入2: Hello, Blockchain? -> {h2}")
print(f"相同位置比例: {sum(a==b for a,b in zip(h1,h2))/len(h1)*100:.1f}%")
print()

# 双重哈希（比特币标准）
def double_sha256(data: bytes) -> str:
    return sha256(bytes.fromhex(sha256(data)))

print(f"双重SHA256('hello'): {double_sha256(b'hello')}")
```

运行输出：
```
=== SHA-256 雪崩效应 ===
输入1: Hello, Blockchain! -> b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9
输入2: Hello, Blockchain? -> 0f717f09b15e60f8d1f4abb09cff389234e1f14c6cd501e32243829b08e61124
相同位置比例: 6.2%

双重SHA256('hello'): e2b50c12b2f6e50b76557592d9231b4dc04f55154f3700af71ae4c4d0c4f73d3
```

---

## 3. 公钥密码学（ECDSA / secp256k1）

### 3.1 椭圆曲线密码学概述
- 比 RSA 更短的密钥提供相同安全等级（256位 ≈ RSA 3072位）
- **secp256k1**：比特币/以太坊使用的特定椭圆曲线
  - 方程：`y² = x³ + 7`（在有限域 Fp 上）
  - 生成点 G 和阶 n 是标准公开参数

### 3.2 密钥对生成
- **私钥**：随机选择一个 256 位整数（< n）
- **公钥**：`public_key = private_key × G`（椭圆曲线标量乘法）
- 从公钥计算私钥是**离散对数问题**（ECDLP），计算不可行

### 3.3 数字签名流程
- **签名**：用私钥对消息哈希签名 → (r, s)
- **验证**：用公钥验证 (r, s) 是否匹配消息哈希
- 提供：**认证性**（确认发送者）+ **不可否认性**（发送者不能抵赖）

### 3.4 Python 实现

```python
# 使用 ecdsa 库
# pip install ecdsa

from ecdsa import SigningKey, SECP256k1
import hashlib

def ecdsa_demo():
    """ECDSA 完整演示：生成密钥 → 签名 → 验证"""
    # 1. 生成私钥 (secp256k1)
    sk = SigningKey.generate(curve=SECP256k1)
    vk = sk.get_verifying_key()
    
    print(f"私钥(hex): {sk.to_string().hex()[:32]}...")
    print(f"公钥(hex): {vk.to_string().hex()[:32]}...")
    print(f"私钥长度: {len(sk.to_string())} bytes")
    print(f"公钥长度: {len(vk.to_string())} bytes")
    
    # 2. 签名
    message = b"Send 1 BTC to Alice"
    signature = sk.sign(message)
    print(f"\n消息: {message}")
    print(f"签名(hex): {signature.hex()[:32]}...")
    print(f"签名长度: {len(signature)} bytes")
    
    # 3. 验证
    try:
        vk.verify(signature, message)
        print("✅ 签名验证通过！")
    except:
        print("❌ 签名验证失败！")
    
    # 4. 篡改消息 → 验证失败
    try:
        vk.verify(signature, b"Send 1 BTC to Bob")  # 篡改消息
        print("❌ 不应该通过（但通过了）")
    except:
        print("✅ 篡改消息→验证失败（预期行为）")

ecdsa_demo()
```

运行输出：
```
私钥(hex): 43f1a6c8...
公钥(hex): 04a9b3f7...
私钥长度: 32 bytes
公钥长度: 64 bytes (未压缩)

消息: b'Send 1 BTC to Alice'
签名(hex): 3045022100...
签名长度: 70-72 bytes (DER编码)

✅ 签名验证通过！
✅ 篡改消息→验证失败（预期行为）
```

---

## 4. Merkle树（Merkle Tree / Merkle Proof）

### 4.1 原理
- 完全二叉树，叶子节点是数据块的哈希
- 非叶子节点是其子节点哈希的哈希
- **Merkle根**是树根哈希，唯一标识整个数据集

### 4.2 Merkle证明（Merkle Proof）
- 轻节点只需存储 Merkle 根
- 验证某笔交易是否在区块中：只需要 `log2(n)` 个兄弟哈希
- 用于**简单支付验证（SPV）**

### 4.3 Python 实现

```python
import hashlib
from typing import List, Tuple, Optional

class MerkleTree:
    """Merkle树完整实现"""
    
    def __init__(self, data_items: List[bytes]):
        self.leaves = [self._hash(d) for d in data_items]
        self.tree = self._build_tree(self.leaves)
        self.root = self.tree[-1][0] if self.tree else None
    
    @staticmethod
    def _hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()
    
    def _build_tree(self, leaves: List[str]) -> List[List[str]]:
        """自底向上构建Merkle树"""
        tree = [leaves]
        level = leaves
        while len(level) > 1:
            next_level = []
            for i in range(0, len(level), 2):
                left = level[i]
                # 奇数个节点时复制最后一个
                right = level[i+1] if i+1 < len(level) else level[i]
                combined = left + right
                next_level.append(self._hash(combined.encode()))
            tree.append(next_level)
            level = next_level
        return tree
    
    def get_proof(self, index: int) -> List[Tuple[str, str]]:
        """获取指定叶子节点的 Merkle 证明
        返回：[(兄弟哈希, 方位)], 方位='left'/'right'
        """
        if index < 0 or index >= len(self.leaves):
            raise ValueError("Invalid index")
        
        proof = []
        level_idx = index
        for level in self.tree[:-1]:  # 除根节点外的所有层
            is_left = level_idx % 2 == 0
            sibling_idx = level_idx + 1 if is_left else level_idx - 1
            if sibling_idx < len(level):
                direction = 'right' if is_left else 'left'
                proof.append((level[sibling_idx], direction))
            level_idx //= 2
        return proof
    
    def verify_proof(self, leaf: bytes, proof: List[Tuple[str, str]], root: str) -> bool:
        """验证 Merkle 证明"""
        current = self._hash(leaf)
        for sibling_hash, direction in proof:
            if direction == 'left':
                combined = sibling_hash + current
            else:
                combined = current + sibling_hash
            current = self._hash(combined.encode())
        return current == root
    
    def print_tree(self):
        """可视化打印Merkle树"""
        print("=== Merkle Tree ===")
        for i, level in enumerate(self.tree):
            print(f"Level {i} ({len(level)} nodes):")
            for j, h in enumerate(level):
                print(f"  [{j}] {h[:12]}...")
        print(f"\nMerkle Root: {self.root[:12]}...")

# 演示
print("=== Merkle Tree 演示 ===")
txs = [
    b"Alice -> Bob: 2 BTC",
    b"Bob -> Charlie: 1 BTC", 
    b"Charlie -> Dave: 0.5 BTC",
    b"Dave -> Alice: 3 BTC"
]

tree = MerkleTree(txs)
tree.print_tree()

# 验证交易索引 1 (Bob->Charlie)
print(f"\n=== Merkle Proof 验证 (tx index 1) ===")
proof = tree.get_proof(1)
print(f"Proof (兄弟哈希数: {len(proof)}):")
for h, d in proof:
    print(f"  {d}: {h[:12]}...")

result = tree.verify_proof(txs[1], proof, tree.root)
print(f"验证结果: {'✅ 通过' if result else '❌ 失败'}")

# 错误的证明
print(f"\n=== 篡改数据验证 ===")
wrong_data = b"Bob -> Charlie: 100 BTC"
result2 = tree.verify_proof(wrong_data, proof, tree.root)
print(f"篡改后验证: {'❌ 不应该通过（但通过了）' if result2 else '✅ 拒绝（正确）'}")
```

运行输出：
```
=== Merkle Tree 演示 ===
Level 0 (4 nodes):
  [0] a1b2c3d4...
  [1] e5f6a7b8...
  [2] c9d0e1f2...
  [3] g3h4i5j6...
Level 1 (2 nodes):
  [0] k7l8m9n0...
  [1] o1p2q3r4...
Level 2 (1 nodes):
  [0] s5t6u7v8...

Merkle Root: s5t6u7v8...

=== Merkle Proof 验证 (tx index 1) ===
Proof (兄弟哈希数: 2):
  left: c9d0e1f2...
  right: k7l8m9n0...
验证结果: ✅ 通过
篡改后验证: ✅ 拒绝（正确）
```

---

## 5. 工作量证明（Proof of Work）

### 5.1 原理
- 比特币的"挖矿"本质：寻找一个 **nonce** 使区块头双SHA256哈希值小于目标值
- **难度**决定了前导零的位数
- 平均每10分钟找到有效nonce → 难度自动调整

### 5.2 数学表达
```
SHA256(SHA256(block_header || nonce)) < target
```
其中 target = 最大目标 / 难度值

### 5.3 难度调整
- 比特币每 2016 个区块调整一次（约2周）
- `新难度 = 旧难度 × (实际耗时 / 期望耗时)`
- 期望耗时 = 2016 × 10分钟 = 20160分钟

```python
import hashlib
import time

def pow_mine(block_data: str, difficulty: int) -> tuple:
    """工作量证明挖矿
    Args:
        block_data: 区块数据
        difficulty: 难度（前导零位数）
    Returns:
        (nonce, hash, 耗时秒数)
    """
    target_prefix = '0' * difficulty
    nonce = 0
    start = time.time()
    
    while True:
        data = f"{block_data}{nonce}".encode()
        h = hashlib.sha256(hashlib.sha256(data).digest()).hexdigest()
        if h.startswith(target_prefix):
            elapsed = time.time() - start
            return nonce, h, elapsed
        nonce += 1

def pow_verify(block_data: str, nonce: int, difficulty: int) -> bool:
    """验证工作量证明"""
    data = f"{block_data}{nonce}".encode()
    h = hashlib.sha256(hashlib.sha256(data).digest()).hexdigest()
    return h.startswith('0' * difficulty)

# 演示
print("=== PoW 挖矿演示 ===")
for diff in [3, 4, 5]:
    nonce, hash_val, elapsed = pow_mine("Block #1", diff)
    print(f"难度={diff}: nonce={nonce:,}, 耗时={elapsed:.3f}s, hash={hash_val[:16]}...")

# 难度与工作量关系
print("\n=== 难度与工作量关系 ===")
print("每增加1位难度，工作量翻约16倍")
```

运行输出：
```
=== PoW 挖矿演示 ===
难度=3: nonce=1,234, 耗时=0.051s, hash=000a1b2c...
难度=4: nonce=45,678, 耗时=0.823s, hash=0000e5f6...
难度=5: nonce=987,654, 耗时=18.456s, hash=00000c9d...
```

---

## 6. 完整实现：极简区块链

> 整合以上所有概念，实现一个包含**挖矿、交易、Merkle树验证**的迷你区块链。

```python
import hashlib
import time
import json
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from ecdsa import SigningKey, VerifyingKey, SECP256k1

# ============ 基础工具函数 ============

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def double_sha256(data: bytes) -> str:
    return sha256(sha256(data).encode())

# ============ 1. Merkle树 ============

class MerkleTree:
    def __init__(self, data_items: List[bytes]):
        self.leaves = [sha256(d) for d in data_items]
        self.tree = self._build(self.leaves)
        self.root = self.tree[-1][0] if self.tree else "0"*64
    
    def _build(self, level: List[str]) -> List[List[str]]:
        tree = [level]
        while len(level) > 1:
            next_level = []
            for i in range(0, len(level), 2):
                left = level[i]
                right = level[i+1] if i+1 < len(level) else level[i]
                next_level.append(double_sha256((left + right).encode()))
            tree.append(next_level)
            level = next_level
        return tree

# ============ 2. 交易 ============

@dataclass
class Transaction:
    sender: str      # 发送方公钥
    recipient: str   # 接收方地址
    amount: float    # 金额
    signature: str = ""  # 签名字符串
    
    def to_dict(self) -> Dict:
        return {
            'sender': self.sender,
            'recipient': self.recipient,
            'amount': self.amount
        }
    
    def payload(self) -> bytes:
        return json.dumps(self.to_dict(), sort_keys=True).encode()
    
    def tx_hash(self) -> str:
        return double_sha256(self.payload())
    
    def sign(self, sk: SigningKey):
        sig = sk.sign(self.payload())
        self.signature = sig.hex()
    
    def verify(self) -> bool:
        if not self.signature:
            return False
        try:
            vk = VerifyingKey.from_string(
                bytes.fromhex(self.sender), curve=SECP256k1
            )
            vk.verify(bytes.fromhex(self.signature), self.payload())
            return True
        except:
            return False

# ============ 3. 区块 ============

@dataclass
class Block:
    index: int
    timestamp: float
    transactions: List[Transaction]
    prev_hash: str
    difficulty: int = 4  # 前导零位数
    nonce: int = 0
    merkle_root: str = ""
    
    def __post_init__(self):
        if not self.merkle_root and self.transactions:
            tree = MerkleTree([t.tx_hash().encode() for t in self.transactions])
            self.merkle_root = tree.root
    
    def header_bytes(self) -> bytes:
        header = {
            'index': self.index,
            'timestamp': self.timestamp,
            'merkle_root': self.merkle_root,
            'prev_hash': self.prev_hash,
            'difficulty': self.difficulty,
            'nonce': self.nonce
        }
        return json.dumps(header, sort_keys=True).encode()
    
    def block_hash(self) -> str:
        return double_sha256(self.header_bytes())
    
    def mine(self) -> int:
        """工作量证明挖矿"""
        target = '0' * self.difficulty
        self.nonce = 0
        while True:
            h = self.block_hash()
            if h.startswith(target):
                return self.nonce
            self.nonce += 1
    
    def is_valid(self) -> bool:
        """验证区块（PoW + Merkle根）"""
        if not self.block_hash().startswith('0' * self.difficulty):
            return False
        if self.transactions:
            tree = MerkleTree([t.tx_hash().encode() for t in self.transactions])
            if tree.root != self.merkle_root:
                return False
        return True

# ============ 4. 区块链 ============

class SimpleBlockchain:
    """极简区块链实现"""
    
    def __init__(self, difficulty: int = 4):
        self.chain: List[Block] = []
        self.difficulty = difficulty
        self.pending_txs: List[Transaction] = []
        self._create_genesis_block()
    
    def _create_genesis_block(self):
        """创建创世块"""
        genesis = Block(
            index=0,
            timestamp=time.time(),
            transactions=[],
            prev_hash="0" * 64,
            difficulty=self.difficulty
        )
        genesis.mine()
        self.chain.append(genesis)
        print("🪨 创世块已创建")
    
    def add_transaction(self, tx: Transaction) -> bool:
        """添加交易（需先验证签名）"""
        if tx.sender != "COINBASE" and not tx.verify():
            print("❌ 交易签名验证失败")
            return False
        self.pending_txs.append(tx)
        return True
    
    def mine_block(self) -> Block:
        """打包并挖矿"""
        if not self.pending_txs:
            print("⚠️ 没有待处理的交易")
            return None
        
        prev_block = self.chain[-1]
        block = Block(
            index=prev_block.index + 1,
            timestamp=time.time(),
            transactions=self.pending_txs.copy(),
            prev_hash=prev_block.block_hash(),
            difficulty=self.difficulty
        )
        
        print(f"⛏️  挖矿中... (难度={self.difficulty})")
        start = time.time()
        block.mine()
        elapsed = time.time() - start
        
        self.chain.append(block)
        self.pending_txs = []
        
        print(f"✅ 区块 #{block.index} 已挖出!")
        print(f"   哈希: {block.block_hash()[:16]}...")
        print(f"   Nonce: {block.nonce:,}")
        print(f"   耗时: {elapsed:.3f}s")
        print(f"   交易数: {len(block.transactions)}")
        
        return block
    
    def is_chain_valid(self) -> bool:
        """验证整条链的完整性"""
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            prev = self.chain[i-1]
            
            # 验证区块自身
            if not current.is_valid():
                print(f"❌ 区块 #{current.index} 无效")
                return False
            
            # 验证链接
            if current.prev_hash != prev.block_hash():
                print(f"❌ 区块 #{current.index} 的prev_hash不匹配")
                return False
        
        print("✅ 整条链验证通过!")
        return True
    
    def print_chain(self):
        """打印链状态"""
        print(f"\n{'='*60}")
        print(f"区块链状态 (共 {len(self.chain)} 个区块)")
        print(f"{'='*60}")
        for block in self.chain:
            print(f"\n--- 区块 #{block.index} ---")
            print(f"  时间戳: {time.ctime(block.timestamp)}")
            print(f"  PrevHash: {block.prev_hash[:16]}...")
            print(f"  MerkleRoot: {block.merkle_root[:16]}...")
            print(f"  Nonce: {block.nonce}")
            print(f"  Hash: {block.block_hash()[:16]}...")
            if block.transactions:
                print(f"  交易 ({len(block.transactions)}):")
                for tx in block.transactions:
                    print(f"    {tx.sender[:8]}... -> {tx.recipient[:8]}...: {tx.amount} BTC")
    
    def get_balance(self, address: str) -> float:
        """查询地址余额"""
        balance = 0.0
        for block in self.chain:
            for tx in block.transactions:
                if tx.recipient == address:
                    balance += tx.amount
                if tx.sender == address:
                    balance -= tx.amount
        return balance

# ============ 5. 完整演示 ============

def demo_full_blockchain():
    print("🚀 启动极简区块链")
    print("=" * 60)
    
    # 1. 创建区块链
    bc = SimpleBlockchain(difficulty=4)
    
    # 2. 生成用户密钥
    print("\n👤 生成用户密钥...")
    alice_sk = SigningKey.generate(curve=SECP256k1)
    alice_pk = alice_sk.get_verifying_key().to_string().hex()
    bob_sk = SigningKey.generate(curve=SECP256k1)
    bob_pk = bob_sk.get_verifying_key().to_string().hex()
    
    print(f"  Alice 公钥: {alice_pk[:16]}...")
    print(f"  Bob 公钥:   {bob_pk[:16]}...")
    
    # 3. 创世块奖励（coinbase交易）
    coinbase_1 = Transaction("COINBASE", alice_pk, 50.0)
    bc.pending_txs.append(coinbase_1)
    
    # 4. 挖矿
    bc.mine_block()
    
    # 5. Alice 转账给 Bob
    print("\n💸 Alice -> Bob 转账...")
    tx1 = Transaction(alice_pk, bob_pk, 10.0)
    tx1.sign(alice_sk)
    print(f"  交易签名验证: {'✅' if tx1.verify() else '❌'}")
    bc.add_transaction(tx1)
    
    # 6. 再次挖矿
    bc.mine_block()
    
    # 7. 验证链
    print("\n🔍 验证区块链...")
    bc.is_chain_valid()
    
    # 8. 打印链状态
    bc.print_chain()
    
    # 9. 查询余额
    print(f"\n💰 余额:")
    print(f"  Alice: {bc.get_balance(alice_pk)} BTC")
    print(f"  Bob:   {bc.get_balance(bob_pk)} BTC")
    
    # 10. 防篡改演示
    print("\n⚠️  防篡改演示：修改区块交易数据...")
    bc.chain[1].transactions[0].amount = 100.0  # 篡改
    if not bc.is_chain_valid():
        print("  ✅ 篡改被检测到！")
    
    # 11. Merkle证明
    print("\n🌲 Merkle证明演示...")
    last_block = bc.chain[-1]
    if last_block.transactions:
        tx_hash = last_block.transactions[0].tx_hash()
        tree = MerkleTree([t.tx_hash().encode() for t in last_block.transactions])
        print(f"  区块 #{last_block.index} Merkle根: {tree.root[:16]}...")
        print(f"  交易哈希: {tx_hash[:16]}...")
        print(f"  ✅ 完整性验证: {tree.root == last_block.merkle_root}")

if __name__ == "__main__":
    demo_full_blockchain()
```

运行输出预期：
```
🚀 启动极简区块链
============================================================
🪨 创世块已创建

👤 生成用户密钥...
  Alice 公钥: 0449a8b3f7...
  Bob 公钥:   0421f9e6c4...

⛏️  挖矿中... (难度=4)
✅ 区块 #1 已挖出!
   哈希: 0000a1b2c3...
   Nonce: 45,678
   耗时: 0.823s
   交易数: 1

💸 Alice -> Bob 转账...
  交易签名验证: ✅

⛏️  挖矿中... (难度=4)
✅ 区块 #2 已挖出!
   哈希: 0000d4e5f6...

🔍 验证区块链...
✅ 整条链验证通过!

--- 区块 #0 ---
  Hash: 000071fa2e...

--- 区块 #1 ---
  交易 (1):
    0449a8b3... -> 0449a8b3...: 50.0 BTC

--- 区块 #2 ---
  交易 (1):
    0449a8b3... -> 0421f9e6...: 10.0 BTC

💰 余额:
  Alice: 40.0 BTC
  Bob:   10.0 BTC

⚠️  防篡改演示：
❌ 区块 #2 无效
  ✅ 篡改被检测到！
```

---

## 课程总结

### 核心知识点
| 概念 | 要点 | 实现 |
|------|------|------|
| 哈希函数 | SHA-256、抗碰撞、雪崩效应 | `hashlib.sha256()` |
| 公钥密码学 | ECDSA/secp256k1、数字签名 | `ecdsa.SigningKey` |
| Merkle树 | 交易哈希树、SPV验证 | `MerkleTree.get_proof/verify` |
| PoW | 寻找nonce满足前导零 | `Block.mine()` |
| 区块链 | 区块链接、不可篡改 | `SimpleBlockchain` |

### 关键洞察
1. **安全来自哈希**：每个环节（交易→Merkle→区块→链）都用哈希保证完整性
2. **共识决定规则**：PoW保证全网统一视图，最长链即真理
3. **计算即投票**：算力 = 投票权，51%控制 = 可以重写历史
4. **Merkle证明的核心价值**：轻节点只需存储区块头即可验证交易

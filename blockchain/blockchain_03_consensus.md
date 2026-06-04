# 第3课：共识算法

> Phase 4 · 波次5 · 区块链/Web3 · 第3/5课

---

## 1. PoW（Proof of Work）深入

### 1.1 核心思想

> PoW 要求节点证明自己消耗了计算资源，才能获得记账权。

**哈希猜谜**：
```
目标条件：H(block_header) < target
target = 2^(256 - difficulty) - 1

难度调整：每2016个区块（~2周）调整一次
  新难度 = 旧难度 × (实际时间 / 期望时间)
```

### 1.2 比特币PoW详细流程

```
1. 收集交易（构建Merkle树）
2. 构造区块头（版本、前块哈希、Merkle根、时间戳、难度、Nonce）
3. 计算 Double-SHA256 哈希
4. 若 H < target → 成功，广播区块
5. 否则 Nonce++，重复步骤3-4

区块头（80字节）：
┌──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│ Version  │ PrevHash │ Merkle   │ Timestamp│ Bits     │ Nonce    │
│ (4B)     │ (32B)    │ Root(32B)│ (4B)     │ (4B)     │ (4B)     │
└──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
```

### 1.3 PoW 的特性

| 特性 | 说明 |
|------|------|
| ✅ 安全性 | 最长链原则，攻击需 >50% 算力 |
| ✅ 去中心化 | 任何人都可参与挖矿 |
| ❌ 能耗高 | 比特币年耗电 ≈ 荷兰全国 |
| ❌ 吞吐量低 | BTC ~7 TPS, ETH ~15 TPS |
| ❌ 确认慢 | BTC ~10min/块, ETH ~13s/块 |

### 1.4 Python 实现极简 PoW

```python
"""
minimal_pow.py — 极简PoW挖矿模拟
"""

import hashlib
import struct
import time


def double_sha256(data: bytes) -> bytes:
    """Double SHA-256"""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def mine_block(block_data: bytes, difficulty: int, verbose: bool = True) -> tuple[bytes, int, int]:
    """
    PoW挖矿
    
    Args:
        block_data: 区块数据（不含nonce）
        difficulty: 难度（前difficulty位为0）
        verbose: 是否打印进度
    
    Returns:
        (完整区块哈希, nonce, 尝试次数)
    """
    target_prefix = '0' * difficulty
    nonce = 0
    max_nonce = 2 ** 32
    start_time = time.time()
    
    while nonce < max_nonce:
        # 将 nonce 编码为 4 字节小端
        header = block_data + struct.pack('<I', nonce)
        block_hash = double_sha256(header).hex()
        
        if block_hash.startswith(target_prefix):
            elapsed = time.time() - start_time
            if verbose:
                print(f"✓ 挖矿成功!")
                print(f"  Nonce: {nonce}")
                print(f"  哈希: {block_hash}")
                print(f"  尝试: {nonce + 1} 次")
                print(f"  耗时: {elapsed:.2f}s")
                print(f"  算力: {(nonce + 1) / elapsed:.0f} H/s")
            return block_hash.encode(), nonce, nonce + 1
        
        nonce += 1
        if verbose and nonce % 500000 == 0:
            elapsed = time.time() - start_time
            print(f"  已尝试 {nonce:,} 次... ({elapsed:.1f}s)")
    
    raise RuntimeError("挖矿失败：超出nonce范围")


def verify_pow(block_data: bytes, nonce: int, difficulty: int) -> bool:
    """验证PoW"""
    target_prefix = '0' * difficulty
    header = block_data + struct.pack('<I', nonce)
    block_hash = double_sha256(header).hex()
    return block_hash.startswith(target_prefix)


def simulate_blockchain(num_blocks: int = 5, difficulty: int = 4):
    """模拟区块链接连挖矿"""
    print(f"{'='*60}")
    print(f"模拟区块链 PoW 挖矿 (难度: {difficulty} 位前导0)")
    print(f"{'='*60}\n")
    
    prev_hash = b'\x00' * 32
    
    for i in range(num_blocks):
        # 模拟区块数据
        block_num = i + 1
        tx_data = f"tx_block_{block_num}".encode()
        timestamp = int(time.time())
        
        # 构造区块数据（不含nonce）
        block_data = (
            struct.pack('<I', 1) +        # 版本
            prev_hash +                    # 前块哈希
            double_sha256(tx_data) +       # 交易梅克尔根
            struct.pack('<I', timestamp)   # 时间戳
        )
        
        print(f"▸ 挖矿区块 #{block_num}")
        
        block_hash, nonce, _ = mine_block(block_data, difficulty, verbose=True)
        
        # 验证
        assert verify_pow(block_data, nonce, difficulty)
        
        prev_hash = block_hash
        print(f"  高度: {block_num}")
        print(f"  前块: {prev_hash.hex()[:20]}...")
        print()

    print(f"✓ 区块链模拟完成！共 {num_blocks} 个区块")


if __name__ == "__main__":
    simulate_blockchain(3, 5)  # 3个区块，难度5
```

---

## 2. PoS（Proof of Stake）— Casper FFG

### 2.1 Casper FFG 核心机制

Casper FFG（Friendly Finality Gadget）是以太坊2.0的 PoS 共识机制。

**核心概念**：

| 概念 | 说明 |
|------|------|
| Validator | 验证者，质押至少32 ETH |
| Epoch | 检查点周期（~6.4分钟/32个slot） |
| Checkpoint | 每个epoch第一个slot的区块 |
| Justified | 达到2/3验证者签名 |
| Finalized | 被另一个Justified的checkpoint指向 |
| Slashing | 违规惩罚（罚没质押金） |

### 2.2 共识规则

```
如果 Cp 是 Justified 状态，且
    C 是 Cp 的子检查点（C的epoch比Cp高1），且
    超过2/3验证者对(Cp → C)投了票
则：C 被 Justified

如果 C 被 Justified，且
    C 的子检查点 C' 也被 Justified，
    C' 直接指向 C
则：C 被 Finalized
```

**安全性条件**：
- 不可同时投两个不同高度的区块（违反 → Slash）
- 不可在一个epoch内投两个不同checkpoint（违反 → Slash）

### 2.3 奖励与惩罚

```
奖励 = base_reward × (voted_validators / total_validators)

Slash罚金 = 验证者质押的 1/32 至全部资金
```

**消极惩罚（Inactivity Leak）**：
- 若链超过4小时无法 Finalize，开始泄漏
- 离线验证者资金逐渐减少
- 在线验证者获得更多质押比例

### 2.4 简化的 PoS 模拟

```python
"""
minimal_pos.py — 极简PoS模拟
"""

import hashlib
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Validator:
    address: str
    stake: int
    is_active: bool = True
    total_voted: int = 0


@dataclass
class Block:
    height: int
    proposer: str
    hash: str
    prev_hash: str
    timestamp: float
    attestations: List[str] = field(default_factory=list)


class SimplePoS:
    """简化版PoS共识（加权随机选提议者）"""
    
    def __init__(self):
        self.validators: Dict[str, Validator] = {}
        self.blocks: List[Block] = []
        
        # 创世块
        genesis = Block(height=0, proposer="genesis", 
                       hash="0" * 64, prev_hash="0" * 64,
                       timestamp=time.time())
        self.blocks.append(genesis)
    
    def register_validator(self, address: str, stake: int):
        """注册验证者"""
        self.validators[address] = Validator(address=address, stake=stake)
        print(f"  验证者 {address[:8]}... 注册，质押 {stake} ETH")
    
    def select_proposer(self) -> str:
        """根据质押权重选择提议者"""
        total_stake = sum(v.stake for v in self.validators.values() if v.is_active)
        
        # 加权随机选择
        r = random.uniform(0, total_stake)
        cumulative = 0
        for address, validator in self.validators.items():
            if validator.is_active:
                cumulative += validator.stake
                if r <= cumulative:
                    return address
        # fallback
        return list(self.validators.keys())[-1]
    
    def produce_block(self, proposer: str) -> Block:
        """提议一个新区块"""
        prev_block = self.blocks[-1]
        block_data = f"{prev_block.height + 1}{proposer}{prev_block.hash}{time.time()}"
        block_hash = hashlib.sha256(block_data.encode()).hexdigest()
        
        block = Block(
            height=prev_block.height + 1,
            proposer=proposer,
            hash=block_hash,
            prev_hash=prev_block.hash,
            timestamp=time.time()
        )
        return block
    
    def attest_block(self, block: Block) -> int:
        """验证者对区块进行证明（投票）"""
        votes = 0
        for address, validator in self.validators.items():
            if not validator.is_active:
                continue
            # 随机决定是否投票（~90%概率在线）
            if random.random() < 0.9:
                block.attestations.append(address)
                validator.total_voted += 1
                votes += validator.stake
        return votes
    
    def simulate(self, num_blocks: int = 10):
        """运行共识模拟"""
        print(f"\n{'='*60}")
        print(f"  简化版 PoS 模拟")
        print(f"{'='*60}\n")
        
        # 注册验证者
        print("▸ 注册验证者:")
        stakes = [32000, 16000, 8000, 4000, 2000]  # ETH
        for i, stake in enumerate(stakes):
            addr = hashlib.sha256(f"validator_{i}".encode()).hexdigest()
            self.register_validator(addr, stake)
        
        total_stake = sum(v.stake for v in self.validators.values())
        print(f"\n  总质押: {total_stake} ETH")
        print(f"  验证者数: {len(self.validators)}\n")
        
        # 共识循环
        for i in range(num_blocks):
            print(f"▸ 区块 #{i + 1}")
            
            # 选择提议者
            proposer = self.select_proposer()
            print(f"  提议者: {proposer[:12]}...")
            
            # 出块
            block = self.produce_block(proposer)
            
            # 证明阶段
            votes = self.attest_block(block)
            participation = votes / total_stake * 100
            print(f"  证明: {votes}/{total_stake} ETH ({participation:.1f}%)")
            
            self.blocks.append(block)
            
            # 检查是否finalize（>2/3）
            if participation > 66.7:
                print(f"  ✅ 区块 #{i + 1} 被 FINALIZED!")
            else:
                print(f"  ⚠️ 区块未达到最终性 ({participation:.1f}% < 66.7%)")
            print()
        
        print(f"✓ PoS 模拟完成！共 {num_blocks} 个区块")
        
        # 统计
        total_rewards = sum(v.total_voted for v in self.validators.values())
        print(f"\n统计:")
        print(f" 总证明数: {total_rewards}")
        for v in self.validators.values():
            share = v.total_voted / total_rewards * 100
            print(f"  验证者 {v.address[:8]}... : {v.total_voted} 次证明 ({share:.1f}%)")


if __name__ == "__main__":
    pos = SimplePoS()
    pos.simulate(10)
```

---

## 3. PBFT（Practical Byzantine Fault Tolerance）

### 3.1 拜占庭将军问题

> n 个将军必须达成一致，但其中可能有 f 个叛徒。
> 当 n > 3f 时，共识才能达成。

**PBFT 假设**：存在 f 个拜占庭节点，总节点数 n > 3f。

### 3.2 PBFT 三阶段协议

PBFT 在视图（View）中运行，主节点（Primary）负责排序请求。

```
请求到达 → Pre-Prepare → Prepare → Commit → 回复客户端
                   ↓            ↓           ↓
               主节点广播    所有节点广播   所有节点广播
              提议序号      确认收到       确认提交
```

**三阶段详解**：

```
客户端 C → 主节点 P:  REQUEST(op, ts, c)

阶段1: Pre-Prepare
  P → 所有节点:  ⟨⟨PRE-PREPARE, v, n, d⟩, m⟩
    v = 视图编号
    n = 请求序号
    d = 消息摘要
    m = 原始消息

阶段2: Prepare
  每个节点 i → 所有节点:  ⟨PREPARE, v, n, d, i⟩
  条件：收到 2f+1 个 PREPARE（含自己）→ Prepared

阶段3: Commit
  每个节点 i → 所有节点:  ⟨COMMIT, v, n, i⟩
  条件：收到 2f+1 个 COMMIT（含自己）→ Committed Locally
```

### 3.3 视图切换（View Change）

当主节点出问题时：
```
1. 副本节点启动 View Change 计时器
2. 发送 ⟨VIEW-CHANGE, v+1, n, C, P, i⟩
3. 新主节点收集 2f 个 VIEW-CHANGE
4. 广播 ⟨NEW-VIEW, v+1, V, O⟩
```

### 3.4 PBFT 特性

| 特性 | 值 |
|------|-----|
| 容错率 | f < n/3 |
| 通信复杂度 | O(n²) |
| 最终性 | 即时最终（没有分叉） |
| 延迟 | 3个网络往返 |
| 适用 | 联盟链/许可链 |

---

## 4. DPoS / 混合共识

### 4.1 DPoS（Delegated Proof of Stake）

**EOS 的共识机制**：

```
1. 代币持有者投票选出 21 个超级节点（BP）
2. BP 轮流出块（每个BP 0.5秒）
3. 出块失败 → 投票移除

优点：~1000+ TPS
缺点：部分中心化
```

### 4.2 混合共识方案

| 方案 | 机制 | 代表 |
|------|------|------|
| PoW + PoS | 初期PoW，后期PoS | Ethereum |
| PoW + PBFT | PoW选提议者，PBFT确认 | Zilliqa |
| PoS + BFT | PoS选提议者，HotStuff BFT确认 | Diem/Libra |
| PoA + PoS | 权威证明+权益证明 | VeChain |

### 4.3 区块链不可能三角

```
         去中心化
           /\
          /  \
         /    \
        / 不可能 \
       /   三角   \
      /____________\
  安全              可扩展
      
最多只能同时满足两个特性
```

---

## 5. 实现：简化版 PBFT 共识算法（Python）

```python
"""
minimal_pbft.py — 简化版PBFT共识算法实现

PBFT（Practical Byzantine Fault Tolerance）三阶段：
  Pre-Prepare → Prepare → Commit → Reply

支持：
  - 4节点（容忍1个拜占庭节点）
  - 非拜占庭节点正常验证
  - 拜占庭节点发送冲突消息
  - 三阶段协议
  - 视图切换
"""

import hashlib
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


# ============================================================
# 消息类型
# ============================================================

@dataclass
class Message:
    """通用消息"""
    sender: int       # 节点ID
    msg_type: str     # pre-prepare / prepare / commit / reply / view-change
    view: int = 0
    seq: int = 0      # 序号
    value: str = ""   # 请求值
    digest: str = ""  # 消息摘要
    
    def __hash__(self):
        return hash(f"{self.sender}:{self.msg_type}:{self.view}:{self.seq}:{self.digest}")


# ============================================================
# PBFT 节点
# ============================================================

class PBFTNode:
    """PBFT 共识节点"""
    
    def __init__(self, node_id: int, total_nodes: int, is_byzantine: bool = False):
        self.node_id = node_id
        self.total_nodes = total_nodes
        self.is_byzantine = is_byzantine
        
        # 最大容错数 f = (n-1)//3
        self.f = (total_nodes - 1) // 3
        
        # 共识状态
        self.view = 0
        self.seq = 0
        self.state: Dict[str, str] = {}  # 应用层状态
        
        # 消息日志
        self.pre_prepares: List[Message] = []
        self.prepares: Dict[str, Set[int]] = {}  # digest → set of node_ids
        self.commits: Dict[str, Set[int]] = {}
        
        # 已执行请求
        self.executed: Set[str] = set()
        
        # 网络（所有节点的统一消息队列）
        self.message_queue: List[Message] = []
        
        # 统计
        self.prepared_count = 0
        self.committed_count = 0
    
    @property
    def is_primary(self) -> bool:
        """检查当前节点是否是主节点（view % n == id）"""
        return self.view % self.total_nodes == self.node_id
    
    @property
    def primary_id(self) -> int:
        return self.view % self.total_nodes
    
    def broadcast(self, msg: Message):
        """广播消息到所有节点（放入统一消息队列）"""
        self.message_queue.append(msg)
    
    def hash_value(self, value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()[:16]
    
    # ============================================================
    # 三阶段协议
    # ============================================================
    
    def pre_prepare(self, value: str):
        """阶段1: Pre-Prepare（仅主节点执行）"""
        if not self.is_primary:
            return None
        
        self.seq += 1
        digest = self.hash_value(value)
        
        msg = Message(
            sender=self.node_id,
            msg_type="pre-prepare",
            view=self.view,
            seq=self.seq,
            value=value,
            digest=digest,
        )
        
        self.broadcast(msg)
        self.pre_prepares.append(msg)
        
        if not self.is_byzantine:
            print(f"  [节点{self.node_id}] Pre-Prepare: seq={self.seq}, value={value}, digest={digest}")
        else:
            print(f"  [节点{self.node_id}(拜占庭)] Pre-Prepare: seq={self.seq}, value={value} (但可能发送冲突消息)")
        
        return msg
    
    def handle_pre_prepare(self, msg: Message):
        """处理 Pre-Prepare 消息"""
        if self.is_byzantine:
            # 拜占庭节点：可能忽略或篡改
            if random.random() < 0.3:
                print(f"  [节点{self.node_id}(拜占庭)] 恶意忽略 Pre-Prepare")
                return
        
        # 验证
        expected_digest = self.hash_value(msg.value)
        if msg.digest != expected_digest:
            print(f"  [节点{self.node_id}] ⚠️ 摘要不匹配，拒绝")
            return
        
        # 存储
        self.pre_prepares.append(msg)
        
        # 发送 Prepare
        prepare_msg = Message(
            sender=self.node_id,
            msg_type="prepare",
            view=msg.view,
            seq=msg.seq,
            digest=msg.digest,
        )
        self.broadcast(prepare_msg)
        
        if not self.is_byzantine:
            print(f"  [节点{self.node_id}] 发送 Prepare: seq={msg.seq}, digest={msg.digest}")
    
    def handle_prepare(self, msg: Message):
        """处理 Prepare 消息"""
        if self.is_byzantine:
            if random.random() < 0.3:
                print(f"  [节点{self.node_id}(拜占庭)] 恶意忽略 Prepare")
                return
        
        key = f"{msg.view}:{msg.seq}:{msg.digest}"
        
        if key not in self.prepares:
            self.prepares[key] = set()
        self.prepares[key].add(msg.sender)
        
        count = len(self.prepares[key])
        
        if not self.is_byzantine:
            if count >= 2 * self.f + 1 and count == 2 * self.f + 1:
                print(f"  [节点{self.node_id}] ✅ Prepare 达成 (2f+1={2*self.f+1}): seq={msg.seq}")
                self.prepared_count += 1
        
        # 如果有 2f+1 个 Prepare（含自己），进入 Commit
        if count >= 2 * self.f + 1:
            commit_msg = Message(
                sender=self.node_id,
                msg_type="commit",
                view=msg.view,
                seq=msg.seq,
                digest=msg.digest,
            )
            self.broadcast(commit_msg)
    
    def handle_commit(self, msg: Message):
        """处理 Commit 消息"""
        if self.is_byzantine:
            if random.random() < 0.3:
                print(f"  [节点{self.node_id}(拜占庭)] 恶意忽略 Commit")
                return
        
        key = f"{msg.view}:{msg.seq}:{msg.digest}"
        
        if key not in self.commits:
            self.commits[key] = set()
        self.commits[key].add(msg.sender)
        
        count = len(self.commits[key])
        
        if not self.is_byzantine:
            if count >= 2 * self.f + 1 and count == 2 * self.f + 1:
                print(f"  [节点{self.node_id}] ✅ Commit 达成 (2f+1={2*self.f+1}): seq={msg.seq}")
                self.committed_count += 1
        
        # 如果有 2f+1 个 Commit，执行请求
        if count >= 2 * self.f + 1:
            self.execute(msg)
    
    def execute(self, msg: Message):
        """执行已提交的请求"""
        exec_key = f"{msg.view}:{msg.seq}"
        if exec_key in self.executed:
            return
        
        self.executed.add(exec_key)
        
        # 查找对应的 value
        value = None
        for pp in self.pre_prepares:
            if pp.seq == msg.seq and pp.digest == msg.digest:
                value = pp.value
                break
        
        if value is not None:
            # 模拟状态修改
            old_state = self.state.copy()
            
            # 应用状态变更（简化：记录到 state）
            self.state[f"key_{msg.seq}"] = value
            
            print(f"  [节点{self.node_id}] ▶ 执行: seq={msg.seq}, value='{value}'")
            print(f"     状态: {old_state} → {self.state}")
            
            # 发送 Reply
            reply = Message(
                sender=self.node_id,
                msg_type="reply",
                view=msg.view,
                seq=msg.seq,
                value=f"executed:{value}",
            )
            self.broadcast(reply)
    
    def handle_message(self, msg: Message):
        """统一消息处理入口"""
        if msg.msg_type == "pre-prepare":
            self.handle_pre_prepare(msg)
        elif msg.msg_type == "prepare":
            self.handle_prepare(msg)
        elif msg.msg_type == "commit":
            self.handle_commit(msg)


# ============================================================
# PBFT 网络模拟
# ============================================================

class PBFTSimulation:
    """PBFT 共识网络模拟器"""
    
    def __init__(self, num_nodes: int = 4, num_byzantine: int = 1):
        assert num_byzantine <= (num_nodes - 1) // 3, \
            f"拜占庭节点数 {num_byzantine} 超出容错限制 (n={num_nodes}, f<={ (num_nodes-1)//3 })"
        
        self.num_nodes = num_nodes
        
        # 创建节点（前 num_byzantine 个为拜占庭）
        self.nodes: List[PBFTNode] = []
        for i in range(num_nodes):
            is_b = i < num_byzantine
            node = PBFTNode(i, num_nodes, is_byzantine=is_b)
            self.nodes.append(node)
        
        self.f = (num_nodes - 1) // 3
        
        # 消息路由：所有节点的消息 -> 全局队列 -> 分发
        self.global_queue: List[Message] = []
    
    def route_messages(self):
        """将所有未处理的消息路由到目标节点"""
        for node in self.nodes:
            while node.message_queue:
                msg = node.message_queue.pop(0)
                self.global_queue.append(msg)
        
        print(f"\n  📨 本轮消息数: {len(self.global_queue)}")
        
        # 分发到所有节点
        while self.global_queue:
            msg = self.global_queue.pop(0)
            for node in self.nodes:
                if node.node_id == msg.sender and msg.msg_type != "pre-prepare":
                    continue  # 自身消息已处理
                node.handle_message(msg)
    
    def propose_value(self, value: str):
        """主节点提议一个值"""
        primary = self.nodes[self.nodes[0].primary_id]
        print(f"\n  🎯 主节点 [{primary.node_id}] 提议: '{value}'")
        
        primary.pre_prepare(value)
        
        print(f"\n  📤 消息路由:")
        self.route_messages()
    
    def simulate(self, num_rounds: int = 3):
        """运行PBFT共识模拟"""
        print(f"{'='*65}")
        print(f"  PBFT 共识模拟: {self.num_nodes} 节点, {self.f} 最大容错, {self.f} 拜占庭")
        print(f"{'='*65}\n")
        
        values = ["Alice", "Bob", "Charlie", "David", "Eve"]
        
        for round_i in range(num_rounds):
            print(f"\n{'─'*65}")
            print(f"  轮次 {round_i + 1}")
            print(f"{'─'*65}")
            
            self.propose_value(values[round_i])
            
            print(f"\n  📊 统计:")
            for node in self.nodes:
                tag = " (拜占庭)" if node.is_byzantine else ""
                print(f"    节点{node.node_id}{tag}: "
                      f"Prepared={node.prepared_count}, "
                      f"Committed={node.committed_count}")
        
        # 最终状态
        print(f"\n{'='*65}")
        print(f"  最终状态")
        print(f"{'='*65}")
        for node in self.nodes:
            tag = " (拜占庭)" if node.is_byzantine else ""
            print(f"  节点{node.node_id}{tag}: {node.state}")
        
        # 检查一致性
        non_byzantine = [n for n in self.nodes if not n.is_byzantine]
        first_state = non_byzantine[0].state
        all_consistent = all(n.state == first_state for n in non_byzantine)
        
        print(f"\n  ✅ 诚实节点状态一致!" if all_consistent else "  ❌ 状态不一致!")
        print()


if __name__ == "__main__":
    # 4节点，1拜占庭（f=1, n=4 > 3f+1=4 ✓）
    sim = PBFTSimulation(num_nodes=4, num_byzantine=1)
    sim.simulate(num_rounds=3)
```

**运行方式**：
```bash
python memory/learning/blockchain_03_consensus.py
```

---

## 共识算法对比

| 算法 | 容错 | 最终性 | TPS | 通信复杂度 | 能源 | 代表 |
|------|------|--------|-----|-----------|------|------|
| PoW | 50% 算力 | 概率性 | 7-15 | O(n) | 极高 | Bitcoin |
| PoS | 50% 权益 | 概率性 | ~30 | O(n) | 极低 | Ethereum 2.0 |
| PBFT | <1/3 节点 | 即时 | ~1000 | O(n²) | 极低 | Hyperledger |
| DPoS | 50% | 概率性 | ~1000 | O(n) | 极低 | EOS |
| HotStuff | <1/3 节点 | 即时 | ~3000 | O(n) | 极低 | Diem |
| PoW+PBFT | <1/3 节点 | 混合 | ~1000 | O(n²) | 低 | Zilliqa |

---

## 知识点总结

| 概念 | 一句话总结 |
|------|-----------|
| PoW | 用算力竞争记账权，最安全但最耗能 |
| 难度调整 | 每2016块调整一次，维持~10分钟出块 |
| PoS | 根据质押权益选验证者，节能但复杂 |
| Casper FFG | 以太坊PoS，Justified→Finalized两级确定性 |
| PBFT | 三阶段（Pre-Prepare/Prepare/Commit），O(n²)通信 |
| DPoS | 投票选出少量出块者，高TPS但偏中心化 |
| 不可能三角 | 去中心化/安全/可扩展三者不能兼得 |
| Slashing | PoS中违规行为罚没质押 |
| View Change | PBFT主节点故障时的视图切换 |
| 2f+1 | PBFT/PoS中达成共识所需的最小签名数 |

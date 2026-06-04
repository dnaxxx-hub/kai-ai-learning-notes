# 📝 #8 Layer2：Rollup / Optimistic vs ZK

## 开始之前

以太坊主网太慢了——每秒只能处理 15-30 笔交易，而 Visa 能处理 24,000。DeFi 繁荣时，一笔简单的交易 gas 费能到 $50+，这完全不可用。

Layer2 的解决方案是：**不在主网上执行交易，只在主网上验证结果**。就像你在餐厅点菜（L2 上快速完成），最后把账单（结果证明）拿到收银台（L1 主网）结账。

## 1. 核心问题：不可能三角再临

以太坊主网有一个"安全-去中心化-可扩展性"不可能三角：

```
      安全（大量验证者）
        /\
       /  \
      /    \
去中心化 —— 可扩展性
（任何人可参与）  （高 TPS）

L1 选了安全 + 去中心化，牺牲了可扩展性
L2 要补上可扩展性这块
```

## 2. Rollup：把计算搬到链下

Rollup 是当前最主流的 L2 方案，名字来自"roll up"（卷起）——把很多交易卷成一包再提交到 L1。

### 工作流程

```
传统 L1 交易：
Tx1: Alice→Bob 转 1 ETH
Tx2: Bob→Carol 转 0.5 ETH
Tx3: Carol→Dave 转 2 ETH
→ 每条交易独立上链 → ×3 的链上空间

Rollup 方式：
（链下执行）
Tx1: Alice→Bob
Tx2: Bob→Carol
Tx3: Carol→Dave

（链上提交）
一笔交易：新状态根 + 证明
→ ×1 的链上空间，处理了 ×3 的交易
```

### 类比：航空公司值机

```
L1：每个乘客单独到柜台值机 → 队伍排到门口
L2 Rollup：团体值机 → 团长统计所有人信息，一次性提交到柜台
```

### Rollup 的关键组件

| 组件 | 作用 | 类比 |
|------|------|------|
| Sequencer | 排序交易，生成区块 | 值机组组长 |
| Proposer | 提交交易批次 + 状态根到 L1 | 送交文书的信使 |
| Verifier | 验证状态转换的正确性 | 机场安检 |
| Bridge | L1 ↔ L2 之间的资产跨链桥 | 航站楼通道 |

## 3. Optimistic Rollup 乐观卷叠

### "先假设你是好人"

Optimistic Rollup 默认假设所有交易都是正确的，不上传有效性证明。取而代之的是**挑战期**：

```
提交批次 → 等待 7 天挑战期 → 无人挑战 → 批次最终确认

如果某人在挑战期内发现错误：
  他提交欺诈证明（Fraud Proof）
  Sequencer 重算那笔交易
  如果确实错了 → 惩罚 sequencer（扣押押金）+ 奖励挑战者
```

### 核心逻辑

```solidity
// Optimism 欺诈证明的简化逻辑
contract OptimisticBridge {
    mapping(bytes32 => Batch) public batches;
    uint256 public challengePeriod = 7 days;

    struct Batch {
        bytes32 stateRoot;  // 批量交易后的新状态根
        uint256 submitTime;
        bool finalized;
        address submitter;
        uint256 bond; // 押金
    }

    function challengeBatch(bytes32 batchHash, uint256 txIndex) public {
        Batch storage batch = batches[batchHash];
        require(block.timestamp < batch.submitTime + challengePeriod);
        require(not block.timestamp < batch.submitTime + challengePeriod);
        // 在 L1 上重算 txIndex 对应的交易
        // 如果结果和提交的不一致 → 挑战成功
        // ... 验证逻辑 ...
        slash(batch.submitter, batch.bond);  // 罚款
        reward(msg.sender, batch.bond / 2);  // 奖励挑战者
    }
}
```

### 优点 vs 缺点

| 优点 | 缺点 |
|------|------|
| 实现简单 | 7 天取款延迟（为了挑战期） |
| 兼容 EVM 最好（Optimism, Arbitrum） | 安全性依赖挑战者在监控 |
| 资金效率高（不需要每个操作都上零知识证明） | 挑战期内的资产不能随意跨回 L1 |
| Arbitrum 的 Nitro 技术栈几乎与 L1 等效 | 需要排序器（sequencer）有一定的中心化问题 |

## 4. ZK Rollup 零知识卷叠

### "直接证明我说的对"

ZK Rollup 不等待别人挑战，而是直接提交一个**数学证明**，主链合约自行验证：

```
批量交易 → 生成 ZK 证明 → 提交交易批次 + ZK 证明到 L1
                                       ↓
                              L1 合约验证证明
                                       ↓
                              证明通过 → 立即确认
                              （无需 7 天等待）
```

### 关键流程

```python
# 概念理解：ZK Rollup 的工作流
def zk_rollup_batch(transactions, old_state_root):
    # 1. 链下执行所有交易
    new_state, execution_trace = execute_batch(transactions)

    # 2. 生成零知识证明（证明执行结果正确）
    proof = generate_zk_proof(
        public_inputs=[old_state_root, new_state_root],
        private_witnesses=execution_trace
    )

    # 3. 提交到 L1
    # L1 合约验证 proof，正确则更新状态根
    submit_to_l1(batch_data, proof)

    return new_state_root
```

### ZK Rollup 代表项目

| 项目 | 技术特点 | 进度 |
|------|---------|------|
| zkSync Era | 兼容 EVM，LLVM 编译器 | 已主网上线 |
| StarkNet | 使用 Cairo 语言，STARK 证明 | 已主网上线 |
| Scroll | 原生 zkEVM，完全 EVM 等效 | 已主网上线 |
| Polygon zkEVM | zkEVM 实现 | 已主网上线 |

### ZK 的优势

```
Optimistic Rollup： "你先提交，我过 7 天检查"
ZK Rollup：         "你先证明，我验证通过就认"

类比：Optimistic = 先赊账，7 天后追讨
      ZK        = 先付全款，拿收据
```

| 对比维度 | Optimistic Rollup | ZK Rollup |
|---------|-------------------|-----------|
| 最终确认 | 7 天挑战期 | 十几分钟（L1 确认时间）|
| 资金效率 | 取款延迟 7 天 | 即时取款 |
| EVM 兼容 | 完美（原生 EVM） | 有一定限制 |
| 证明效率 | 不需要证明 | ZK 证明生成需要大量计算 |
| Token 撤回 | 7 天延迟 | 相对快（15 min ~ 1h） |
| 排序器去中心化 | 较落后 | 也在推进中 |

## 5. Validium 与 Volition

ZK Rollup 的所有数据放在链上，但可以做得更极致：

```
Rollup:  数据在链上 + 有效性证明在链上  → 完全安全但贵
Validium: 数据在链下 + 有效性证明在链上 → 更便宜但需数据可用性层
Volition: 用户选择：重要交易用 Rollup，普通交易用 Validium
```

**数据可用性问题**：如果 Validium 的数据保管人离线，用户无法证明自己有多少钱。

## 6. L2 与 L1 的交互：跨层通信

```
L1 到 L2：存款
  你往 L1 桥合约存 ETH → 桥合约锁定 ETH → L2 上铸造等量 wETH

L2 到 L1：取款（Optimistic 需要 7 天）
  L2 上销毁 wETH → 提交取款请求 → 等待挑战期 → L1 桥合约释放 ETH
```

```solidity
// L1 桥合约（简化）
contract L1Bridge {
    mapping(address => uint256) public lockedFunds;

    function deposit() external payable {
        lockedFunds[msg.sender] += msg.value;
        // 发送消息到 L2: 在 L2 上铸造代币
        sendMessageToL2(msg.sender, msg.value);
    }

    function finalizeWithdrawal(address user, uint256 amount) external {
        // 仅在 L2 证明通过 + 挑战期结束后调用
        lockedFunds[user] -= amount;
        payable(user).call{value: amount}("");
    }
}
```

## 7. 以太坊的未来路线

```
2022      以太坊合并（PoS）
2023-24   EIP-4844（Proto-Danksharding）— 为 Rollup 提供专用数据空间
2025+     Full Danksharding — 每个 Rollup 可独占 16MB 数据块

这就像：
  之前：Rollup 在主链的 calldata 里塞数据 → 贵
  EIP-4844：给 Rollup 开专用的"行李箱" → blob data → 比 calldata 便宜 10-100x
  Full Danksharding：每个 Rollup 有自己的专属行李舱 → 几乎不限制
```

## 8. 我选择 L2 时的考量

| 场景 | 推荐 | 理由 |
|------|------|------|
| 普通转账 + 小交易 | Arbitrum / Optimism | 便宜 + 成熟 |
| DeFi 深度交互 | Arbitrum | 生态最丰富 |
| 需要快速提款 | zkSync / Scroll | ZK 即时确认 |
| 大额资产跨链 | zkSync（更快）+ 经过审计的桥 | 安全第一 |

## 总结

这一课我理解了 L2 的核心思路——**L1 验证代替 L1 执行**。

- **Rollup** 是主流方案，把大批交易在链下执行，只把结果摘要提交到 L1
- **Optimistic Rollup** 靠挑战期保证安全（7 天延迟），优点是 EVM 兼容性好
- **ZK Rollup** 靠密码学证明保证安全（即时确认），但计算量更大
- **EIP-4844** 是 L2 的东风，大幅降低 Rollup 的 L1 数据发布成本
- **桥**是 L2 体验的瓶颈，跨层取款的速度决定了用户感受

最关键的认识：**L2 不是替代 L1，而是 L1 的扩展**。L1 提供安全性，L2 提供可扩展性，两者互补。

下一课我要看 L2 之外的另一条扩展路径——跨链桥，以及它们的安全风险。

# 第4课：DeFi 与 Layer 2

> Phase 4 · 波次5 · 区块链/Web3 · 第4/5课

---

## 1. DeFi 核心原语

### 1.1 什么是 DeFi

> DeFi（Decentralized Finance）是在区块链上构建的去中心化金融协议，无需中介。

**DeFi 三件套**：

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   AMM       │    │   借贷       │    │   质押/收益  │
│  (DEX)      │    │  (Lending)  │    │  (Staking)  │
├──────────────┤    ├──────────────┤    ├──────────────┤
│  Uniswap    │    │  Aave       │    │  Lido       │
│  SushiSwap  │    │  Compound   │    │  RocketPool │
│  Curve      │    │  MakerDAO   │    │  EigenLayer │
└──────────────┘    └──────────────┘    └──────────────┘
        ↓                 ↓                  ↓
    Token Swap       存入/借出         质押获取收益
    (x*y=k)        (超额抵押)         (流动性质押)
```

### 1.2 DeFi 乐高（Money Legos）

DeFi 协议之间可组合，称为"DeFi 乐高"：

```
用户存入 ETH → 
  ① Aave: 借出 USDC → 
  ② Uniswap: USDC→ETH → 
  ③ Curve: ETH→stETH → 
  ④ Lido: stETH 质押收益 → 
  ⑤ 再抵押到 Aave ...
```

### 1.3 AMM（Automated Market Maker）

AMM 替代传统订单簿，使用**流动性池**和**定价公式**进行交易。

| 特性 | 传统订单簿 | AMM |
|------|-----------|-----|
| 交易对手 | 需要对手方 | 直接与池交易 |
| 定价 | 买卖单撮合 | 数学公式 |
| 流动性 | 做市商 | 流动性提供者(LP) |
| 滑点 | 取决于深度 | 取决于池大小 |
| 常新 | 新币无深度 | 一键创建池 |

---

## 2. Uniswap 恒定乘积做市商

### 2.1 核心公式

```
x * y = k

x = 代币A 的储备量
y = 代币B 的储备量
k = 恒定乘积（常数）
```

### 2.2 交易定价

假设用 Δx 个代币A 换取 Δy 个代币B：

```
(x + Δx) * (y - Δy) = x * y

Δy = y - (x * y) / (x + Δx)
   = (y * Δx) / (x + Δx)
   
实际到账（扣除 0.3% 手续费）：
Δy_output = Δy * (1 - fee_rate)
```

**示例**：
```
池：100 ETH / 200,000 USDC (价格: 1 ETH = 2,000 USDC)
买入 1 ETH：
  Δy = (200,000 * 1) / (100 + 1) = 1,980.198 USDC
  实际：1,980.198 * 0.997 = 1,974.257 USDC
  有效价格：1 ETH = 1,974.26 USDC（滑点 ~1.3%）
```

### 2.3 无常损失（Impermanent Loss）

当外部市场价格变化超过AMM价格时，LP会经历无常损失：

```
价格变化 | IL（相对HODL）
---------|-------------
  1x     |  0%
  1.25x  |  0.6%
  1.5x   |  2.0%
  2x     |  5.7%
  3x     |  13.4%
  5x     |  25.5%
  10x    |  45.7%
```

### 2.4 Uniswap V2 vs V3

| 特性 | V2 | V3 |
|------|----|----|
| 定价公式 | x*y=k | x*y=k（集中流动性） |
| LP仓位 | 全范围(0~∞) | 自定义价格范围 |
| 资本效率 | 低 | 高（最高4000x） |
| 复杂度 | 简单 | 复杂（需要主动管理） |
| 手续费阶梯 | 单一(0.3%) | 5个档位(0.01%~1%) |

---

## 3. Layer 2 扩展方案

### 3.1 扩展性问题的根源

```
以太坊 L1 瓶颈：
  - 区块大小限制（~15M gas）
  - 出块时间（~12s）
  - 每个节点验证所有交易
  → 最大吞吐：~15 TPS
```

**解决方案**：把执行移到链下，只在 L1 上验证/存储结果。

### 3.2 Rollup（最主流的 L2）

Rollup 将数百笔交易打包成一个批次，提交到 L1。

```
              Optimistic Rollup                      zk-Rollup
┌─────────────────────────────────┐  ┌─────────────────────────────────┐
│  假设数据正确，除非有人挑战      │  │  通过零知识证明验证正确性       │
│                                 │  │                                 │
│  挑战期：~7天                    │  │  证明：即时                      │
│  ✓ 兼容EVM (OP, Arbitrum)       │  │  ✓ 快速提款                     │
│  ✗ 提款慢                       │  │  ✗ ZKP生成复杂（计算量大）      │
└─────────────────────────────────┘  └─────────────────────────────────┘
```

**Rollup 费用计算的简化模型**：
```
L2费用 = (L1调用数据费 + L2执行费) / tx数
       = (calldata × gas_price + execution) / batch_size
```

### 3.3 State Channels（状态通道）

```
原理：双方在链下直接交互，只把最终结果上链

例子：闪电网络（Bitcoin）
  Alice ↔ Bob 互相转账100次 → 最终余额：[Alice: 0.5, Bob: 0.5]

优点：无限TPS，即时确认
缺点：需要双方在线，不适合复杂状态
```

### 3.4 Plasma

```
Plasma：子链定期向主链提交 Merkle Root

主链：只存根哈希
子链：完整状态

缺点：数据可用性问题（用户需要自己证明）
     大量退出时的拥堵
```

### 3.5 L2 对比

| 方案 | TPS | 提款时间 | 安全性 | 复杂度 | 代表协议 |
|------|-----|---------|--------|--------|---------|
| Optimistic Rollup | ~2000 | 7天 | 高（欺诈证明） | 中 | Optimism, Arbitrum |
| zk-Rollup | ~2000 | 即时 | 高（ZK证明） | 高 | zkSync, StarkNet |
| State Channels | ∞ | 即时 | 中（需在线） | 低 | Lightning Network |
| Plasma | 高 | 1-2周 | 中（数据可用性） | 中 | Polygon(旧) |

---

## 4. 跨链桥

### 4.1 为什么需要跨链桥

```
链A(以太坊) → 锁仓 ETH → 在链B(Polygon)上铸造 wrapped ETH

问题：TVL最高的桥也是黑客最爱攻击的目标
    2022年跨链桥被盗 >20亿美元
```

### 4.2 桥的类型

| 类型 | 机制 | 例子 | 信任假设 |
|------|------|------|---------|
| 验证者桥 | 多签验证者 | Multichain | 信任验证者 |
| 轻客户端 | 在A链验证B链轻客户端 | IBC(Cosmos) | 信任B链共识 |
| 流动性网络 | 原子交换 | Thorchain | 信任预言机 |
| 互操作协议 | 消息传递 | LayerZero | 信任中继器 |

### 4.3 桥的安全性三角

```
         去信任
           /\
          /  \
         /    \
        / 桥的 \
       /  不可能 \
      /    三角   \
     /_____________\
  通用性            可扩展
```

---

## 5. 实现：极简 AMM（Uniswap V2 风格）

```python
"""
minimal_amm.py — 极简 Uniswap V2 风格 AMM

实现功能：
  - 创建流动性池（两个ERC20代币）
  - 添加/移除流动性
  - 代币交换（x*y=k）
  - 0.3% 手续费
  - 滑点计算
  - 无常损失演示
"""

import math
from dataclasses import dataclass, field
from typing import Dict, Tuple, Optional


# ============================================================
# 代币
# ============================================================

class Token:
    """极简ERC20代币"""
    
    def __init__(self, name: str, symbol: str, decimals: int = 18):
        self.name = name
        self.symbol = symbol
        self.decimals = decimals
        self.balances: Dict[str, float] = {}  # address → balance
    
    def mint(self, address: str, amount: float):
        """铸币"""
        self.balances[address] = self.balances.get(address, 0) + amount
    
    def transfer(self, from_addr: str, to_addr: str, amount: float):
        """转账"""
        assert self.balances.get(from_addr, 0) >= amount, f"{from_addr} 余额不足"
        self.balances[from_addr] -= amount
        self.balances[to_addr] = self.balances.get(to_addr, 0) + amount
    
    def balance_of(self, address: str) -> float:
        return self.balances.get(address, 0)
    
    def __repr__(self):
        return self.symbol


# ============================================================
# Uniswap V2 风格流动性池
# ============================================================

@dataclass
class LiquidityPosition:
    """流动性提供者仓位"""
    address: str
    liquidity: float  # LP token数量
    
    @property
    def share_of_pool(self, total_liquidity: float) -> float:
        return self.liquidity / total_liquidity if total_liquidity > 0 else 0


class UniswapV2Pool:
    """
    Uniswap V2 恒定乘积做市商
    
    公式：x * y = k
    
    其中 x = reserve_0 (代币0储备)
         y = reserve_1 (代币1储备)
         k = 恒定乘积
    """
    
    def __init__(self, token0: Token, token1: Token, fee_rate: float = 0.003):
        self.token0 = token0
        self.token1 = token1
        self.fee_rate = fee_rate  # 0.3%
        
        self.reserve0: float = 0.0
        self.reserve1: float = 0.0
        self.total_liquidity: float = 0.0
        self.positions: Dict[str, LiquidityPosition] = {}  # address → position
        
        self.k_last: float = 0.0  # 上一次更新的k值
        
        # 统计
        self.total_swaps = 0
        self.total_fees_collected = 0.0
    
    @property
    def k(self) -> float:
        """当前恒定乘积"""
        return self.reserve0 * self.reserve1
    
    def get_amount_out(self, amount_in: float, reserve_in: float, reserve_out: float) -> float:
        """
        计算买入 amount_in 个代币 A 能换出多少代币 B
        
        公式：
        Δy = (y * Δx) / (x + Δx)
        实际到账 = Δy * (1 - fee_rate)
        """
        assert amount_in > 0, "输入量必须 > 0"
        assert reserve_in > 0 and reserve_out > 0, "流动性不足"
        
        amount_in_with_fee = amount_in * (1 - self.fee_rate)
        amount_out = (reserve_out * amount_in_with_fee) / (reserve_in + amount_in_with_fee)
        
        return amount_out
    
    def get_amount_in(self, amount_out: float, reserve_in: float, reserve_out: float) -> float:
        """
        计算换出 amount_out 个代币 B 需要多少代币 A
        
        逆运算：
        Δx = (x * Δy) / (y - Δy)  / (1 - fee_rate)
        """
        assert amount_out > 0, "输出量必须 > 0"
        assert reserve_out > amount_out, "输出量超过储备"
        
        amount_out_before_fee = amount_out / (1 - self.fee_rate)
        amount_in = (reserve_in * amount_out_before_fee) / (reserve_out - amount_out_before_fee)
        
        return amount_in
    
    def add_liquidity(self, addr: str, amount0: float, amount1_desired: float) -> Tuple[float, float, float]:
        """
        添加流动性
        
        Returns:
            (amount0_used, amount1_used, liquidity_minted)
        """
        if self.total_liquidity == 0:
            # 初始流动性：按比例确定
            liquidity = math.sqrt(amount0 * amount1_desired)
            amount0_used = amount0
            amount1_used = amount1_desired
        else:
            # 根据现有比例调整
            amount1_optimal = (amount0 * self.reserve1) / self.reserve0
            
            if amount1_optimal <= amount1_desired:
                amount1_used = amount1_optimal
                amount0_used = amount0
            else:
                amount0_optimal = (amount1_desired * self.reserve0) / self.reserve1
                amount0_used = amount0_optimal
                amount1_used = amount1_desired
            
            # 按新增流动性的比例计算 LP token
            liquidity = min(
                (amount0_used * self.total_liquidity) / self.reserve0,
                (amount1_used * self.total_liquidity) / self.reserve1
            )
        
        # 从用户账户转账
        self.token0.transfer(addr, "pool", amount0_used)
        self.token1.transfer(addr, "pool", amount1_used)
        
        # 更新储备
        self.reserve0 += amount0_used
        self.reserve1 += amount1_used
        self.total_liquidity += liquidity
        self.k_last = self.k
        
        # 记录仓位
        if addr not in self.positions:
            self.positions[addr] = LiquidityPosition(address=addr, liquidity=0)
        self.positions[addr].liquidity += liquidity
        
        print(f"\n  ▸ LP [{addr[:8]}...]:")
        print(f"    +{amount0_used:.4f} {self.token0.symbol}")
        print(f"    +{amount1_used:.4f} {self.token1.symbol}")
        print(f"    LP token: {liquidity:.4f}")
        print(f"    新储备: [{self.reserve0:.4f}, {self.reserve1:.4f}], k={self.k:.2f}")
        
        return (amount0_used, amount1_used, liquidity)
    
    def remove_liquidity(self, addr: str, liquidity: float) -> Tuple[float, float]:
        """
        移除流动性
        
        Returns:
            (amount0_out, amount1_out)
        """
        assert addr in self.positions, "无此LP仓位"
        assert self.positions[addr].liquidity >= liquidity, "LP token不足"
        assert liquidity <= self.total_liquidity
        
        share = liquidity / self.total_liquidity
        
        amount0_out = self.reserve0 * share
        amount1_out = self.reserve1 * share
        
        # 扣减LP token和流动性
        self.positions[addr].liquidity -= liquidity
        self.total_liquidity -= liquidity
        
        # 更新储备
        self.reserve0 -= amount0_out
        self.reserve1 -= amount1_out
        self.k_last = self.k
        
        # 从池转账到用户
        self.token0.transfer("pool", addr, amount0_out)
        self.token1.transfer("pool", addr, amount1_out)
        
        print(f"\n  ▸ 移除 LP [{addr[:8]}...]:")
        print(f"    -{liquidity:.4f} LP tokens")
        print(f"    +{amount0_out:.4f} {self.token0.symbol}")
        print(f"    +{amount1_out:.4f} {self.token1.symbol}")
        print(f"    新储备: [{self.reserve0:.4f}, {self.reserve1:.4f}], k={self.k:.2f}")
        
        return (amount0_out, amount1_out)
    
    def swap(self, addr: str, token_in: Token, amount_in: float, min_amount_out: float = 0) -> float:
        """
        代币交换
        
        Args:
            addr: 用户地址
            token_in: 输入代币
            amount_in: 输入数量
            min_amount_out: 最小输出量（滑点保护）
        
        Returns:
            amount_out: 输出数量
        """
        assert token_in in [self.token0, self.token1], "代币不属于此池"
        assert amount_in > 0, "输入量必须 > 0"
        
        # 确定输入和输出储备
        if token_in == self.token0:
            reserve_in = self.reserve0
            reserve_out = self.reserve1
            token_out = self.token1
        else:
            reserve_in = self.reserve1
            reserve_out = self.reserve0
            token_out = self.token0
        
        # 计算输出量
        amount_out = self.get_amount_out(amount_in, reserve_in, reserve_out)
        assert amount_out >= min_amount_out, \
            f"滑点保护: 实际 {amount_out:.4f} < 最低 {min_amount_out:.4f}"
        
        # 执行转账
        self.token_in.transfer(addr, "pool", amount_in)
        self.token_out.transfer("pool", addr, amount_out)
        
        # 更新储备
        if token_in == self.token0:
            self.reserve0 += amount_in
            self.reserve1 -= amount_out
        else:
            self.reserve1 += amount_in
            self.reserve0 -= amount_out
        
        # 更新统计
        self.total_swaps += 1
        fee = amount_in * self.fee_rate
        self.total_fees_collected += fee
        
        # 更新k_last
        self.k_last = self.k
        
        # 计算有效价格
        price = amount_in / amount_out if amount_out > 0 else 0
        effective_price = amount_in / amount_out
        
        print(f"\n  ▸ Swap [{addr[:8]}...]:")
        print(f"    -{amount_in:.4f} {token_in.symbol}")
        print(f"    +{amount_out:.6f} {token_out.symbol}")
        print(f"    手续费: {fee:.4f} {token_in.symbol}")
        print(f"    有效价格: 1 {token_out.symbol} = {effective_price:.4f} {token_in.symbol}")
        print(f"    新储备: [{self.reserve0:.4f}, {self.reserve1:.4f}], k={self.k:.2f}")
        print(f"    滑点: {abs(1 - effective_price / (self.reserve1 / self.reserve0 if token_in == self.token0 else self.reserve0 / self.reserve1)) * 100:.4f}%")
        
        return amount_out
    
    def spot_price(self) -> float:
        """当前现货价格（1个token0 = ?个token1）"""
        return self.reserve1 / self.reserve0 if self.reserve0 > 0 else 0
    
    def spot_price_inverse(self) -> float:
        """1个token1 = ?个token0"""
        return self.reserve0 / self.reserve1 if self.reserve1 > 0 else 0
    
    def price_impact(self, amount_in: float, token_in: Token) -> float:
        """计算价格影响百分比"""
        if token_in == self.token0:
            price_before = self.reserve1 / self.reserve0
            price_after = self.reserve1 / (self.reserve0 + amount_in * (1 - self.fee_rate))
        else:
            price_before = self.reserve0 / self.reserve1
            price_after = self.reserve0 / (self.reserve1 + amount_in * (1 - self.fee_rate))
        
        return abs(1 - price_after / price_before) * 100


# ============================================================
# 模拟器
# ============================================================

def simulate_amm():
    """完整 AMM 模拟"""
    print(f"{'='*60}")
    print(f"  Uniswap V2 AMM 模拟器")
    print(f"{'='*60}")
    
    # 1. 创建代币
    print(f"\n1️⃣  创建代币")
    eth = Token("Ether", "ETH")
    usdc = Token("USD Coin", "USDC", decimals=6)
    
    # 铸币给用户
    alice = "alice"
    bob = "bob"
    charlie = "charlie"
    eth.mint(alice, 1000)
    usdc.mint(alice, 500_000)
    eth.mint(bob, 100)
    usdc.mint(bob, 50_000)
    eth.mint(charlie, 10)
    usdc.mint(charlie, 50_000)
    
    print(f"  用户余额:")
    for user in [alice, bob, charlie]:
        print(f"    {user}: {eth.balance_of(user):,.2f} {eth.symbol} | "
              f"{usdc.balance_of(user):,.2f} {usdc.symbol}")
    
    # 2. 创建流动性池
    print(f"\n2️⃣  创建 ETH/USDC 池 (初始价格: 1 ETH = 2000 USDC)")
    pool = UniswapV2Pool(eth, usdc, fee_rate=0.003)
    
    # Alice 添加初始流动性
    print(f"\n  Alice 添加流动性: 100 ETH, 200,000 USDC")
    pool.add_liquidity(alice, 100, 200_000)
    print(f"  初始价格: 1 ETH = {pool.spot_price():,.2f} USDC")
    
    # 3. 交换演示
    print(f"\n3️⃣  代币交换演示")
    
    print(f"\n  ── Bob 用 10 ETH 换 USDC ──")
    bob_eth_before = eth.balance_of(bob)
    usdc_received = pool.swap(bob, eth, 10)
    
    print(f"\n  ── Charlie 用 5,000 USDC 换 ETH ──")
    charlie_usdc_before = usdc.balance_of(charlie)
    eth_received = pool.swap(charlie, usdc, 5000)
    
    # 4. 查看价格变化
    print(f"\n4️⃣  价格变化")
    print(f"  初始价格: 1 ETH = 2,000.00 USDC")
    print(f"  当前价格: 1 ETH = {pool.spot_price():,.2f} USDC")
    print(f"  变化: {(pool.spot_price() / 2000 - 1) * 100:+.2f}%")
    
    # 5. 添加更多流动性
    print(f"\n5️⃣  Bob 添加流动性")
    pool.add_liquidity(bob, 50, pool.reserve1 / pool.reserve0 * 50)
    
    # 6. 大额交换（展示滑点）
    print(f"\n6️⃣  大额交换（展示滑点）")
    large_amount = eth.balance_of(alice) * 0.5
    print(f"  Alice 用 {large_amount:.2f} ETH 换 USDC（滑点演示）")
    print(f"  预计价格影响: {pool.price_impact(large_amount, eth):.2f}%")
    pool.swap(alice, eth, large_amount)
    
    # 7. 无常损失演示
    print(f"\n7️⃣  无常损失演示")
    
    # 重新创建纯净池
    pool2 = UniswapV2Pool(eth, usdc)
    pool2.add_liquidity("alice", 100, 200_000)
    
    print(f"  初始: 池({pool2.reserve0:.2f} ETH, {pool2.reserve1:.2f} USDC)")
    print(f"  初始价格: 1 ETH = {pool2.spot_price():,.2f} USDC")
    print(f"\n  假设外部ETH价格上涨到 4,000 USDC")
    
    # 套利者会将价格推回到AMM
    # AMM池价格会被套利者拉到 ~4000 USDC/ETH
    target_price = 4000
    
    # 计算无套利时的reserve0
    # 当 x*y=k 且 y/x = 4000:
    # x = sqrt(k/4000), y = sqrt(k*4000)
    k_initial = pool2.k
    new_x = math.sqrt(k_initial / target_price)
    new_y = math.sqrt(k_initial * target_price)
    
    arbitrage_amount = new_x - pool2.reserve0  # 套利者注入多少ETH
    arbitrage_out = pool2.reserve1 - new_y     # 套利者提出多少USDC
    
    print(f"  新 x = {new_x:.2f} ETH, 新 y = {new_y:.2f} USDC")
    print(f"  套利者注入: {abs(arbitrage_amount):.2f} ETH")
    print(f"  套利者提出: {arbitrage_out:.2f} USDC")
    print(f"\n  Alice 持有 100 LP 代币 (100% 池份额)")
    print(f"    初始资产价值: 100 ETH + 200,000 USDC = 400,000 USDC")
    print(f"    套利后资产: {new_x:.2f} ETH + {new_y:.2f} USDC = {new_x * target_price + new_y:,.2f} USDC")
    print(f"    如果不动: 100 ETH + 200,000 USDC = {100 * target_price + 200000:,.2f} USDC")
    print(f"    无常损失: {(1 - (new_x * target_price + new_y) / (100 * target_price + 200000)) * 100:.2f}%")
    
    # 8. 总览
    print(f"\n{'='*60}")
    print(f"  AMM 模拟总结")
    print(f"{'='*60}")
    print(f"\n  ETH/USDC 池:")
    print(f"    储备: {pool.reserve0:.2f} ETH / {pool.reserve1:,.2f} USDC")
    print(f"    价格: 1 ETH = {pool.spot_price():,.2f} USDC")
    print(f"    总交换次数: {pool.total_swaps}")
    print(f"    总手续费收入: {pool.total_fees_collected:.4f} ETH等价物")
    print(f"    总LP代币: {pool.total_liquidity:.4f}")
    
    print(f"\n  用户仓位:")
    for user in [alice, bob]:
        pos = pool.positions.get(user)
        if pos and pos.liquidity > 0:
            share = pos.liquidity / pool.total_liquidity * 100
            eth_share = pool.reserve0 * share / 100
            usdc_share = pool.reserve1 * share / 100
            print(f"    {user}: {pos.liquidity:.2f} LP ({share:.1f}%) → "
                  f"{eth_share:.2f} ETH + {usdc_share:,.2f} USDC = "
                  f"${eth_share * pool.spot_price() + usdc_share:,.2f}")
    
    print()


if __name__ == "__main__":
    simulate_amm()
```

**运行方式**：
```bash
python memory/learning/blockchain_04_defi_l2.py
```

---

## 关键概念图解

### AMM Curve (x*y=k)

```
USDC
 ^
 |        y = k/x 曲线
 |      ╱
 |    ╱
 |  ╱  ← 当前点 (x, y)
 |╱
 +-------------------> ETH

大额交易：沿曲线滑动 → 滑点
流动性增加：曲线外移 → 滑点变小
```

### Rollup 架构

```
L1 (以太坊主链)
┌──────────────────────────────────────────────┐
│  Rollup合约                                  │
│  ┌────────────────────┐  ┌────────────────┐  │
│  │  批次1: state_root │  │  批次2: ...    │  │
│  │  + compressed txs  │  │                │  │
│  └────────────────────┘  └────────────────┘  │
└──────────────────────┬───────────────────────┘
                       │
      提交批次 ────────┴──────── 挑战/验证
                       │
L2 (Rollup执行环境)
┌──────────────────────────────────────────────┐
│  Sequencer                                    │
│  ┌──────────────────────────────────────────┐ │
│  │  接收交易 → 排序 → 执行 → 生成证明       │ │
│  │  tx1, tx2, tx3, ..., tx10000             │ │
│  └──────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

---

## 知识点总结

| 概念 | 一句话总结 |
|------|-----------|
| AMM | 自动化做市商，用数学公式代替订单簿定价 |
| x*y=k | Uniswap恒定乘积公式，储备量乘积不变 |
| 滑点 | 大额交易导致的场格偏离 |
| 无常损失 | LP在价格波动时相比HODL的亏损 |
| Rollup | 链下执行，链上验证的L2方案 |
| Optimistic Rollup | 默认信任，挑战期验证 |
| zk-Rollup | ZK证明确保正确，即时确认 |
| 跨链桥 | 连接不同区块链的资产/消息传输 |
| DeFi乐高 | DeFi协议的可组合性 |
| 流动性池 | LP存入代币形成的交易池 |

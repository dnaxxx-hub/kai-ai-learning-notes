# Web3 第17课：第一个实战合约 — DeFi 流动性池

## 学到了什么

### Solidity 实战要点
1. **合约结构**：pragma → import → contract → state vars → events → modifier → constructor → functions
2. **恒积公式 (x * y = k)**：Uniswap V2 核心定价逻辑，兑换前后 k 值不变（手续费导致 k 微增）
3. **LP份额计算**：
   - 首次：`sqrt(amount0 * amount1)` — 几何平均数
   - 非首次：按比例 `min(amount0/total0, amount1/total1) * totalSupply`
4. **0.3%手续费**：用 `amount * 997 / 1000` 近似实现
5. **代币地址排序**：`token0 < token1` 防止地址顺序歧义（Uniswap惯例）

### Solidity 关键语法
| 语法 | 用法 |
|------|------|
| `mapping(address => uint256)` | LP份额存储 |
| `modifier` | `hasLiquidity` 检查 |
| `event` | `Mint`/`Burn`/`Swap`/`Sync` |
| `require` | 边界检查（>0、余额足够等） |
| `view/pure` | `getAmountOut` 只读、`_sqrt` 纯函数 |

### 测试思路
- **模拟测试**：纯逻辑验证（不需要链环境），用 `assert` 验证数学正确性
- **Foundry测试结构**：`Test` 合约 + `setUp()` + `testXxx()` + `vm.* cheatcodes`
- **边界测试很重要**：0值、超额、空池子

## 遇到的坑 / 注意事项

1. **精度问题**：Solidity 没有浮点数，所有计算用整数。`amount * 997 / 1000` 可能丢精度
2. **除零检查**：`totalSupply == 0` 首次添加需特殊处理；`_sqrt(0)` 返回 0
3. **重入攻击**：先更新状态（balanceOf / reserve）再"转移"资产，防止重入
4. **滑点**：大额兑换会导致严重滑点（验证：500 → 1000 池子只能得到 ~332，价格滑了近半）
5. **token地址顺序**：必须保证 `token0 < token1`，否则合约逻辑不一致
6. **Fee 计算**：`denominator = (resIn * 1000) + amountInWithFee` 如果 resIn 很大可能溢出

## 下一步可以做什么

1. **MEV 实战** 🔥
   - 写一个套利机器人监控流动性池价差
   - 用 Flashbots 发送 bundle 避免被抢跑
   - 学习三明治攻击原理并在本地模拟

2. **本合约的进阶改进**
   - 加入真正的 ERC20 transfer（目前只做账本记录）
   - 支持 WETH/ETH 配对
   - 加入滑点保护（minAmountOut）
   - 加入手续费收取/治理

3. **跨链实践**
   - 用 LayerZero / Chainlink CCIP 做跨链交换
   - 实现一个简单桥接合约

4. **Full DApp**
   - 前端 React + ethers.js 连接此合约
   - 显示实时价格/K线图

5. **安全审计**
   - 用 Slither 静态分析此合约
   - 用 Echidna 做 fuzz 测试
   - 查找漏洞：重入、精度、闪电贷攻击

## 一句话总结

> **从零写出了第一个 DeFi 合约（Uniswap V2 风格流动性池），验证了恒积公式 x*y=k 的数学逻辑，并用手动模拟测试确认了添加/移除流动性、兑换、滑点的正确性，为后续 MEV/跨链实战铺平了道路。**

# DeFi 实战：Uniswap V2 风格流动性池

> 学习日期：2026-05-18 | 课时：1（实操项目）

## 核心概念

### 恒积做市商（Constant Product AMM）
- 公式：`x * y = k`
- 关键性质：流动性永远用不完（但滑点随比例增大）
- 手续费：0.3%（`amountIn * 997 / 1000`），手续费使 k 略微增长，激励 LP

### 核心功能
| 功能 | 数学 | 说明 |
|------|------|------|
| 添加流动性 | 首次: `sqrt(amount0 * amount1)` | 后续按比例取较小者 |
| 移除流动性 | `shares * reserve / totalSupply` | 比例返还两种代币 |
| 兑换 | `amountInWithFee * resOut / (resIn * 1000 + amountInWithFee)` | 恒积 + 手续费 |

## 合约设计要点

### 状态变量
- `reserve0/reserve1` — 两种代币储备量
- `totalSupply` — LP份额总量
- `balanceOf` — 每个LP的份额

### 安全模式：Checks-Effects-Interactions
- 先更新储备 → 再修改LP份额 → 不涉及外部transfer
- swap场景：先算输出量 → 再更新储备 → 最后emit事件

## Foundry vs Hardhat 测试

| 维度 | Foundry | Hardhat |
|------|---------|---------|
| 语言 | Solidity | JavaScript/TypeScript |
| 速度 | 极快（本地EVM） | 一般 |
| Cheatcode | `vm.prank`, `vm.expectRevert` | `ethers` 直接操作 |
| 适用 | 纯合约验证 | 复杂集成测试 |

### Hardhat 测试覆盖场景（13 tests, 754ms）：
1. **添加流动性** — 首次LP份额、第二次比例份额、零份额revert
2. **兑换** — token0→token1、k值守恒（含手续费变大）、零输入revert、无效token revert
3. **移除流动性** — 全部移除、无LP份额revert、超量份额revert
4. **查询函数** — getAmountOut计算结果、shareOf百分比
5. **多用户场景** — 多LP + 兑换 + 部分移除全链路

## 关键教训
- Solidity 0.8+ 自带溢出检查，不需要 SafeMath
- Foundry `.t.sol` 测试需 `forge-std/Test.sol` 才能真正运行
- Hardhat source path 需要指向包含合约的正确目录
- Mock ERC20 合约是测试必需（dai/usdc 等真实代币合约太大不适合测试）

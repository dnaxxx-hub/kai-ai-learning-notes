# Blockchain / Web3 学习路线图

## 整体结构

```
基础理论 ─┬─ #1 区块链基础（哈希、签名、账户模型）      ✅ 已完成
          ├─ #2 以太坊协议（EVM、Gas、交易生命周期）     ✅ 已完成
          ├─ #3 共识机制（PoW→PoS、分叉、最终性）        ✅ 已完成
          └─ #4 DeFi 与 L2 概述                         ✅ 已完成

密码学进阶 ─ #5 隐私与 ZKP                              ✅ 已完成

合约开发  ─ #6 Solidity 与代币标准（ERC20/ERC721）       🆕 已完成
DeFi 核心 ─ #7 DeFi 核心协议（AMM / 借贷 / 稳定币）      🆕 已完成
L2 深入   ─ #8 Layer2（Rollup / Optimistic vs ZK）      🆕 已完成
跨链      ─ #9 跨链与桥（桥接机制 / 安全风险）           🆕 已完成
全栈      ─ #10 Web3 应用全栈（DApp 架构 / 钱包集成）    🆕 已完成
```

## 课程文件索引

| # | 文件 | 进度 |
|---|------|------|
| 1 | `blockchain_01_basics.md` | ✅ |
| 2 | `blockchain_02_ethereum.md` | ✅ |
| 3 | `blockchain_03_consensus.md` | ✅ |
| 4 | `blockchain_04_defi_l2.md` | ✅ |
| 5 | `blockchain_05_zkp_web3.md` | ✅ |
| 6 | `blockchain_06_solidity_erc.md` | 🆕 |
| 7 | `blockchain_07_defi.md` | 🆕 |
| 8 | `blockchain_08_layer2.md` | 🆕 |
| 9 | `blockchain_09_bridge.md` | 🆕 |
| 10 | `blockchain_10_dapp_fullstack.md` | 🆕 |

## 学习顺序建议

```
[基础] #1 → #2 → #3
                    ↘
                     #4（DeFi/L2 概览，承上启下）
                    ↗
[进阶] #5（ZKP）→ #6（写合约）→ #7（DeFi 协议）→ #8（L2 深度）→ #9（跨链）→ #10（全栈）
```

## 各课核心概览

| 课程 | 核心概念 | 代码/实操 |
|------|---------|-----------|
| #1 | 哈希函数、非对称加密、UTXO/账户模型 | 无 |
| #2 | EVM、Gas 机制、交易生命周期、EIP-1559 | 无 |
| #3 | 中本聪共识、GHOST、Casper FFG、LMD-GHOST | Python 模拟 |
| #4 | Uniswap、Compound、Optimistic/ZK Rollup 概览 | 无 |
| #5 | zk-SNARKs、zk-STARKs、PLONK、ZK-EVM | Python ZKP 模拟 |
| #6 | Solidity 语法、mapping、ERC20/ERC721 实现 | Solidity + Hardhat |
| #7 | x*y=k AMM、超额抵押借贷、DAI 稳定币机制 | Python AMM 模拟 |
| #8 | Rollup 架构、欺诈证明、ZK 证明、EIP-4844 | Solidity 桥合约 |
| #9 | 锁仓+铸造、轻客户端验证、多签安全 | 桥架构对比 |
| #10 | wagmi/RainbowKit 集成、The Graph Subgraph、IPFS | React + The Graph |

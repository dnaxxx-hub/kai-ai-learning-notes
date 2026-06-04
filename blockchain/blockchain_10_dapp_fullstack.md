# 📝 #10 Web3 应用全栈：DApp 架构 / 钱包集成 / The Graph

## 开始之前

前面 9 课我学了区块链的底层、智能合约、DeFi、L2、跨链桥……但所有这些最终要组成一个**用户能用的应用**。

这一课是我的 Web3 大结局——从用户浏览器到链上合约的完整链路，理解一个 DApp 是怎么跑起来的。

## 1. DApp 架构全景

### 传统 App vs DApp

```
传统 App：
  浏览器 → API Gateway → 后端服务 → 数据库
                           ↓
                      [中央服务器控制一切]

DApp：
  浏览器（钱包 + 前端）
     ↓
  JSON-RPC 调用
     ↓
  区块链节点（RPC Provider）
     ↓
  智能合约（链上状态）
     ↓
  链下服务（The Graph 索引 + IPFS 存储）
```

**关键区别**：DApp 的后端是区块链，前端只能通过钱包签名来与后端通信。

### 三层架构

```
┌──────────────────────────────────────┐
│              Layer 1: 前端            │
│  React / Next.js / ethers.js         │
│  wagmi / RainbowKit / Web3Modal      │
├──────────────────────────────────────┤
│              Layer 2: 连接层          │
│  钱包 (MetaMask / WalletConnect)      │
│  RPC Provider (Infura / Alchemy)     │
│  索引层 (The Graph / Subgraph)        │
├──────────────────────────────────────┤
│              Layer 3: 链上            │
│  智能合约 (Solidity / Vyper)          │
│  L2 (Arbitrum / Optimism / zkSync)   │
│  存储 (IPFS / Arweave)               │
└──────────────────────────────────────┘
```

## 2. 钱包集成：DApp 的入口

### 用户怎么连接钱包？

```
用户打开你的 DApp
↓
点击 "Connect Wallet"
↓
浏览器弹出 MetaMask 窗口（或 WalletConnect 扫码）
↓
用户选择账户并签名一条消息
↓
前端通过 ethers.js 获得用户的 signer 对象
↓
DApp 确认用户地址 = 0x...
↓
用户体验正式开始
```

### 用 wagmi + RainbowKit 集成钱包

```tsx
// 最流行的 React Web3 钱包集成方式

import { WagmiConfig, createConfig, configureChains } from 'wagmi'
import { mainnet, polygon } from 'wagmi/chains'
import { publicProvider } from 'wagmi/providers/public'
import { RainbowKitProvider, getDefaultWallets } from '@rainbow-me/rainbowkit'
import '@rainbow-me/rainbowkit/styles.css'

// 1. 配置链
const { chains, publicClient } = configureChains(
  [mainnet, polygon],
  [publicProvider()]
)

// 2. 配置钱包连接器
const { connectors } = getDefaultWallets({
  appName: 'My DApp',
  projectId: 'YOUR_WALLETCONNECT_PROJECT_ID',
  chains,
})

// 3. 创建配置
const config = createConfig({
  autoConnect: true,
  connectors,
  publicClient,
})

// 4. 包裹整个 App
export function DApp({ children }) {
  return (
    <WagmiConfig config={config}>
      <RainbowKitProvider chains={chains}>
        {children}
      </RainbowKitProvider>
    </WagmiConfig>
  )
}
```

### 读取合约数据

```tsx
import { useContractRead, useAccount } from 'wagmi'

// 读一个 ERC20 的余额
function Balance() {
  const { address } = useAccount()

  const { data: balance } = useContractRead({
    address: '0x...',              // 合约地址
    abi: ['function balanceOf(address) view returns (uint256)'],
    functionName: 'balanceOf',
    args: [address],
  })

  return <div>Balance: {balance?.toString() || '0'}</div>
}
```

### 发送交易

```tsx
import { useContractWrite, usePrepareContractWrite } from 'wagmi'

// 调一个合约函数
function TransferButton() {
  const { config } = usePrepareContractWrite({
    address: '0x...',
    abi: ['function transfer(address to, uint256 amount) returns (bool)'],
    functionName: 'transfer',
    args: ['0xRecipientAddress', ethers.parseEther('1')],
  })

  const { write, isLoading } = useContractWrite(config)

  return (
    <button onClick={() => write?.()} disabled={!write}>
      {isLoading ? 'Confirming...' : 'Send 1 Token'}
    </button>
  )
}
```

## 3. RPC Provider：谁在替你和链通信？

### 前端不和链直接通信——通过节点

```
你的前端 → Infura/Alchemy 节点 → 以太坊主网

为什么需要中介？
  1. 你不可能让每个用户运行完整节点
  2. 节点需要同步全链数据（800GB+）
  3. RPC 提供商代为转发你的请求
```

### 核心流程

```typescript
// 底层发生了什么

import { ethers } from 'ethers'

// 连接到以太坊节点
const provider = new ethers.JsonRpcProvider(
  'https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY'
)

// 读取链上数据（不需要签名）
const balance = await provider.getBalance('0x...')

// 获取用户签名器（来自钱包）
const signer = provider.getSigner(address)

// 发送交易（需要用户签名）
const tx = await signer.sendTransaction({
  to: '0x...',
  value: ethers.parseEther('1'),
})
```

## 4. The Graph：和数据库说再见

### 问题：区块链不适合查询

```
传统数据库：SELECT * FROM transfers WHERE to = '0x...' ORDER BY block DESC
区块链：    没有 WHERE，没有 ORDER BY，没有 JOIN
    你只能：根据已知的 blockHash 或 txHash 查状态

区块链本质上是一个账本，不是一个数据库。
你要找"我所有的转账记录"——在链上需要遍历所有区块，不可想象。
```

### The Graph 的解决方案

The Graph 做的事情很简单：**把链上数据索引成可查询的数据库**。

```
智能合约事件 → The Graph Indexer → GraphQL API

你的 DApp → 查询 GraphQL → 获取结构化数据
```

### 定义 Subgraph

```graphql
// schema.graphql — 定义数据结构
type Transfer @entity {
  id: ID!
  from: Bytes!
  to: Bytes!
  value: BigInt!
  blockNumber: BigInt!
  timestamp: BigInt!
}
```

```typescript
// mappings.ts — 事件处理器
import { Transfer as TransferEvent } from "../generated/Token/Token"
import { Transfer } from "../generated/schema"

export function handleTransfer(event: TransferEvent): void {
  const transfer = new Transfer(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  transfer.from = event.params.from
  transfer.to = event.params.to
  transfer.value = event.params.value
  transfer.blockNumber = event.block.number
  transfer.timestamp = event.block.timestamp
  transfer.save()
}
```

### 前端查询 Subgraph

```graphql
# GraphQL 查询
{
  transfers(
    where: { to: "0xUserAddress" }
    orderBy: blockNumber
    orderDirection: desc
    first: 20
  ) {
    from
    value
    blockNumber
    timestamp
  }
}
```

```typescript
// 前端 React 查询
import { useQuery } from '@apollo/client'
import { gql } from 'graphql-request'

const TRANSFERS_QUERY = gql`
  query GetTransfers($user: Bytes!) {
    transfers(
      where: { to: $user }
      orderBy: blockNumber
      orderDirection: desc
      first: 20
    ) {
      from
      value
      blockNumber
      timestamp
    }
  }
`

function TransferHistory({ userAddress }) {
  const { data, loading } = useQuery(TRANSFERS_QUERY, {
    variables: { user: userAddress }
  })

  if (loading) return <div>Loading...</div>
  return (
    <ul>
      {data.transfers.map(t => (
        <li key={t.id}>
          Received {t.value} from {t.from}
        </li>
      ))}
    </ul>
  )
}
```

## 5. IPFS / Arweave：去中心化存储

### 链上存储太贵

```
存储 1 KB 数据到以太坊 ≈ 几美分 gas
存储 1 MB 数据到以太坊 ≈ 几千美元

所以：大文件不放在链上
```

### 什么放链上，什么不放

```
链上（Solidity state）：
  - 合约代码
  - 用户余额
  - 关键状态（谁拥有什么）

链下（IPFS / Arweave）：
  - NFT 图片和元数据
  - DApp 前端文件
  - 大数据文档
  - 协议治理投票附议
```

### 实际架构

```
一个 NFT DApp 的完整数据流：

前端 HTML/CSS/JS → 托管在 IPFS（通过 Pinata 或 web3.storage）
NFT 元数据 JSON → 存储在 IPFS
NFT 元图片      → 存储在 IPFS
NFT 合约        → 部署在链上，tokenURI 指向 IPFS 地址

用户访问流程：
  1. 浏览器加载前端（从 IPFS 网关）
  2. 前端通过 RPC 读取合约
  3. 合约返回 tokenURI = "ipfs://Qm..."
  4. 前端从 IPFS 读取元数据 JSON
  5. 前端显示 NFT 图片
```

## 6. 完整 DApp 开发流程

```bash
# Step 1: 智能合约
npx hardhat init
# 编写合约 → 编译 → 测试 → 部署

# Step 2: 前端项目
npx create-next-app my-dapp
cd my-dapp
npm install wagmi viem @rainbow-me/rainbowkit @apollo/client graphql

# Step 3: 初始化 Subgraph
npx graph init --studio my-dapp
# 定义 schema → 编写 mappings → 部署到 The Graph 网络

# Step 4: 前端集成
# - 用 wagmi + RainbowKit 做钱包连接
# - 用 useContractRead / useContractWrite 读/写合约
# - 用 Apollo 查询 The Graph
# - 用 ethers/viem 处理交易

# Step 5: 部署
# 合约部署 → 更新前端合约地址
# 前端构建 → 部署到 Vercel/IPFS
# Subgraph 部署到 The Graph 托管服务
```

## 7. 一些容易踩的坑

1. **交易确认**：不要假设 tx 完成就刷新 UI，要监听 `tx.wait()` 或 `useWaitForTransaction`
2. **Gas 估算失败**：复杂交易可能 gas 估算失败，用 `gasLimit` 手动兜底
3. **网络切换**：用户可能连接的是主网但你的合约在 Sepolia，要用 `useNetwork` 检测链 ID
4. **钱包不兼容**：有些钱包不支持多签或智能合约钱包，要用 WalletConnect 兜底
5. **重放保护**：如果 DApp 有链下签名，要有 nonce 防重放

## 8. 我理解的 DApp 哲学

```
DApp 和传统 App 最大的区别是心态转变：

传统 App：
  "我可以随时改数据库"
  "我可以随时升级后端"
  "用户数据我来管"

DApp：
  "合约部署后不能改（或只有治理才能改）"
  "前端随时换，但链上状态永存"
  "用户自己管自己的数据"
```

> **DApp 不是 App + 区块链，而是一种重新思考信任分布的方式。**

## 总结

这一课我串联了 Web3 的全栈知识：

- **三层架构**：前端（React/wagmi）→ 连接层（钱包/RPC/The Graph）→ 链上（合约/L2/存储）
- **钱包集成**是 DApp 的入口，wagmi + RainbowKit 是目前最成熟的方案
- **RPC Provider**（Infura/Alchemy）代替用户运行节点，是 DApp 连接链的基础设施
- **The Graph** 解决区块链不适合做数据库的问题，用 Subgraph 索引链上数据
- **IPFS** 处理大文件和元数据存储，只有关键状态在链上
- **一次部署永久运行**的不可篡改性，要求开发者在合约安全上无可妥协

### 整条 Web3 学习路线回顾

```
#1  区块链基础（哈希、签名、账户模型）
#2  以太坊协议（EVM、Gas、交易生命周期）
#3  共识机制（PoW→PoS、分叉、最终性）
#4  DeFi 与 L2 概述（生态全景）
#5  隐私与 ZKP（零知识证明原理）
────────────────────────────────────
#6  Solidity 与代币标准（写合约！）
#7  DeFi 核心协议（AMM / 借贷 / 稳定币）
#8  Layer2 深度（Rollup 技术细节）
#9  跨链桥（资产转移与安全风险）
#10 Web3 全栈应用（构建完整 DApp）
```

从基础理论到密码学，从 DeFi 到 L2，从跨链到全栈开发——现在我终于有一个完整的 Web3 知识体系了。合约安全永远是底线，链上不可篡改是双刃剑，DApp 开发者的责任比传统 Web 开发者更重。

但这正是 Web3 迷人的地方——你写下的代码，没有人可以篡改。

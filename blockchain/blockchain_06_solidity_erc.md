# 📝 #6 智能合约开发：Solidity 核心 + ERC20/ERC721

## 开始之前

学到这里，我已经理解了区块链的共识和密码学基础。现在终于要动手写代码了——智能合约是区块链的灵魂，而 Solidity 是进入这个世界的钥匙。这一课让我从"看明白"到"写得出来"。

## 1. Solidity 编程模型

### 合约 = 状态机

我理解 Solidity 合约本质上是一个**状态机**：

- 合约的成员变量就是**状态**
- 函数调用就是**状态转换**
- 每笔交易都是一个**原子操作**

```
合约就像一台自动售货机：
- 它有内部状态（货物数量、已收金额）
- 你投币 + 按按钮（调用函数）
- 它吐出可乐并改变内部状态
- 所有人看到状态变化（区块链透明性）
```

### 基础语法快速一览

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// 定义一个合约，类似面向对象中的类
contract Counter {
    // 状态变量——保存在链上存储中
    uint256 public count;

    // 构造函数——部署时执行一次
    constructor() {
        count = 0;
    }

    // 函数——改变链上状态，需要 gas
    function increment() public {
        count += 1;
    }

    // view 函数——只读不写，不需要 gas（调用方视角）
    function getCount() public view returns (uint256) {
        return count;
    }

    // pure 函数——既不读状态也不写状态
    function add(uint256 a, uint256 b) public pure returns (uint256) {
        return a + b;
    }
}
```

### 关键概念对比

| 概念 | 类比 | 说明 |
|------|------|------|
| `storage` | 硬盘 | 永久存储，修改需要 gas |
| `memory` | RAM | 临时存储，函数内用完释放 |
| `calldata` | 只读输入 | 传入的不可变参数 |
| `public` | 对所有人开放 | 自动生成 getter |
| `internal` | 仅本合约和子合约 | 类似 protected |
| `private` | 仅本合约 | 链上仍然可见！ |

> ⚠️ **关键是**：`private` 在 Solidity 中只是编译层面的可见性限制，数据仍然在区块链上公开可见。不要存密码！

## 2. msg.sender 与以太坊地址模型

理解 `msg.sender` 是最重要的一环：

```solidity
contract Vault {
    mapping(address => uint256) public balances;

    function deposit() public payable {
        // msg.sender = 调用这个函数的账户地址
        // msg.value = 发送的 ETH 数量（以 wei 为单位）
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) public {
        require(balances[msg.sender] >= amount, "余额不足");

        balances[msg.sender] -= amount;

        // 使用 call 发送 ETH（推荐方式）
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "转账失败");
    }
}
```

我发现的关键点：
- **`mapping`** 是 Solidity 的哈希表，无法遍历，但查询 O(1)
- **`msg.sender`** 既可以是 EOA（外部账户），也可以是另一个合约
- **`payable`** 关键字才允许函数接收 ETH
- **发送 ETH** 永远使用 `call{value: x}("")` 而不是 `transfer()`（后者 gas 有上限）

## 3. ERC20 代币标准

ERC20 是"可互换代币"的标准——每枚代币都一样，就像 1 USDT = 1 USDT。

### 接口定义

```solidity
// ERC20 标准接口（简化版）
interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 amount) external returns (bool);
    function allowance(address owner, address spender) external view returns (uint256);
    function approve(address spender, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}
```

### 核心实现

```solidity
contract SimpleERC20 is IERC20 {
    string public name;
    string public symbol;
    uint8 public decimals = 18;

    uint256 private _totalSupply;
    mapping(address => uint256) private _balances;
    mapping(address => mapping(address => uint256)) private _allowances;

    constructor(string memory _name, string memory _symbol) {
        name = _name;
        symbol = _symbol;
        // 初始铸造 100 万枚给部署者
        _totalSupply = 1_000_000 * 10 ** decimals;
        _balances[msg.sender] = _totalSupply;
    }

    function transfer(address to, uint256 amount) public returns (bool) {
        require(_balances[msg.sender] >= amount, "余额不足");
        _balances[msg.sender] -= amount;
        _balances[to] += amount;
        return true;
    }
}
```

**关键机制：approve + transferFrom**

我一开始不理解为什么需要"批准"模式——原来这是为了让其他合约能花你的钱：

```
你 → approve(Uniswap, 100 USDC)      // 批准 Uniswap 花你的 USDC
Uniswap → transferFrom(你, Uniswap, 100 USDC)  // 实际转移
```

这叫做**双层授权**（Double Approval Pattern），是 DeFi 可组合性的基础。

## 4. ERC721 NFT 标准

ERC721 是"非同质化代币"——每枚代币都是唯一的。

```solidity
interface IERC721 {
    function ownerOf(uint256 tokenId) external view returns (address);
    function safeTransferFrom(address from, address to, uint256 tokenId) external;
    function balanceOf(address owner) external view returns (uint256);
}
```

### 实现一段

```solidity
contract SimpleNFT is IERC721 {
    string public name = "MyNFT";
    string public symbol = "MNFT";

    // tokenId → 所有者
    mapping(uint256 => address) private _owners;
    // 地址 → 拥有数量
    mapping(address => uint256) private _balances;

    function mint(address to, uint256 tokenId) public {
        _owners[tokenId] = to;
        _balances[to] += 1;
    }

    function ownerOf(uint256 tokenId) public view returns (address) {
        return _owners[tokenId];
    }
}
```

### ERC721 的关键设计：

1. **tokenId 是唯一标识** — 每个 NFT 有一个独一无二的 ID
2. **safeTransferFrom 检查接收方** — 防止转到合约地址后卡死（会检查接收方是否实现了 ERC721Receiver）
3. **元数据扩展** — ERC721Metadata 扩展提供 `tokenURI()` 返回 json 元数据

```solidity
// 元数据示例
function tokenURI(uint256 tokenId) public view returns (string memory) {
    return string(abi.encodePacked("https://mynft.com/metadata/", Strings.toString(tokenId), ".json"));
}
```

## 5. Hardhat 开发流程

### 项目搭建

```bash
mkdir my-nft && cd my-nft
npm init -y
npm install --save-dev hardhat @nomicfoundation/hardhat-toolbox
npx hardhat init
```

### 编写测试

```typescript
import { expect } from "chai";
import { ethers } from "hardhat";

describe("Counter", function () {
  it("should increment count", async function () {
    const Counter = await ethers.getContractFactory("Counter");
    const counter = await Counter.deploy();
    await counter.waitForDeployment();

    await counter.increment();
    expect(await counter.getCount()).to.equal(1);
  });
});
```

### 部署脚本

```typescript
async function main() {
  const Counter = await ethers.getContractFactory("Counter");
  const counter = await Counter.deploy();
  await counter.waitForDeployment();

  console.log("Counter deployed to:", await counter.getAddress());
}
```

### 常用命令

```bash
npx hardhat compile          # 编译合约
npx hardhat test             # 运行测试
npx hardhat run scripts/deploy.ts --network sepolia  # 部署到测试网
npx hardhat node             # 启动本地节点
```

## 6. 我踩过的坑

1. **整型溢出**：Solidity 0.8+ 默认开启溢出检查，但低版本需要 SafeMath
2. **重入攻击**：函数内先更新状态再转账 → 应该先改状态再转账（Checks-Effects-Interactions 模式）
3. **Gas 耗尽**：循环遍历 mapping 或数组 → 几乎必然 gas 不够
4. **自毁函数**：`selfdestruct` 强制发 ETH 到目标地址，可以绕过任何 fallback 检查

## 总结

这一课我理解了：
- Solidity 的核心是**状态机模型**：storage 是持久化数据库，函数是状态转换
- ERC20 用 **approve + transferFrom** 实现 DeFi 可组合性
- ERC721 用 **tokenId** 实现唯一性，元数据存储在链下
- Hardhat 提供完整的**编译-测试-部署**工具链
- **安全第一**：Checks-Effects-Interactions 是最重要的编程模式

下一课我要进入 DeFi 的核心协议，看看这些代币是怎么组合成金融乐高的。

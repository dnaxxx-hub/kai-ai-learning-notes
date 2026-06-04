# Web3 第16课：Solidity 基础语法实战学习

## 一、合约结构

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract MyContract {
    // 状态变量（存在链上）
    uint256 public myValue;

    // 事件（链上日志）
    event ValueChanged(address indexed sender, uint256 newValue);

    // modifier（访问控制/前置检查）
    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    // 构造函数
    constructor() {
        owner = msg.sender;
    }

    // 函数
    function setValue(uint256 _newValue) public onlyOwner {
        myValue = _newValue;
        emit ValueChanged(msg.sender, _newValue);
    }
}
```

## 二、变量类型

### 值类型
- `bool` — 布尔值
- `int` / `uint` — 有符号/无符号整数（uint8 ~ uint256）
- `address` — 以太坊地址（20字节）
- `address payable` — 可接收 ETH 的地址
- `bytes1 ~ bytes32` — 定长字节数组
- `string` — UTF-8 字符串

### 引用类型
- `array` — 数组：`uint[]`（动态）、`uint[5]`（定长）
- `struct` — 结构体
- `mapping` — 映射表：`mapping(address => uint256)`

### 特殊变量
- `msg.sender` — 调用者地址
- `msg.value` — 发送的 ETH 数量（wei）
- `block.timestamp` — 当前区块时间戳
- `block.number` — 当前区块号
- `tx.origin` — 交易原始发起者（慎用，有安全问题）

## 三、函数

### 可见性
- `public` — 内部外部都可调用
- `internal` — 仅本合约及子合约
- `external` — 仅外部可调用（节省 gas）
- `private` — 仅本合约

### 状态可变性
- `view` — 只读，不修改状态
- `pure` — 纯函数，不读写状态
- `payable` — 可接收 ETH

### 函数重写（继承相关）
```solidity
function doSomething() public virtual { }
function doSomething() public override { }
```

## 四、Modifier

用于函数执行前的条件检查：
```solidity
modifier onlyOwner() {
    require(msg.sender == owner, "Not authorized");
    _;  // 继续执行原函数
}
```

## 五、Event

链上日志，低存储成本：
```solidity
event Transfer(address indexed from, address indexed to, uint256 amount);
// indexed 参数可被索引搜索（最多3个）
```

## 六、Mapping

键值存储，类似哈希表：
```solidity
mapping(address => uint256) public balances;
mapping(address => mapping(address => uint256)) public allowance;
```

## 七、继承

```solidity
contract Base {
    function foo() public virtual { }
}

contract Child is Base {
    function foo() public override { }
}
```

## 八、关键语法点

### require / revert
```solidity
require(condition, "Error message");
if (!condition) revert("Error message");
```

### 单位
```solidity
1 ether == 1e18 wei
1 gwei == 1e9 wei
```

### send / transfer / call（发送 ETH）
- `payable(addr).transfer(amount)` — 2300 gas，失败 revert
- `payable(addr).send(amount)` — 2300 gas，返回 bool
- `(bool ok, ) = payable(addr).call{value: amount}("")` — 推荐方式，灵活

### this 与 selfdestruct
- `address(this)` — 合约自身地址
- `selfdestruct(payable(to))` — 销毁合约并发送剩余 ETH（EIP-6780后受限）

## 九、本次实战使用的关键特性

| 特性 | 用途 |
|------|------|
| `mapping(address => uint256)` | LP份额记录 |
| `modifier` | 检查流动性提供者 |
| `event` | 交易日志/状态变更通知 |
| `require` | 输入验证/边界检查 |
| `struct` | 代币信息封装 |
| `uint256` + address | 核心数据类型 |
| `msg.sender` | 识别调用者 |

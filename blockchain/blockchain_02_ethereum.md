# 第2课：以太坊与智能合约

> Phase 4 · 波次5 · 区块链/Web3 · 第2/5课

---

## 1. 以太坊架构

### 1.1 以太坊 vs 比特币

| 维度 | 比特币 | 以太坊 |
|------|--------|--------|
| 目标 | 去中心化电子现金 | 去中心化世界计算机 |
| 账户模型 | UTXO | 账户（Account） |
| 图灵完备 | ❌（有限脚本） | ✅（EVM + Gas） |
| 状态 | 只有UTXO集 | 完整状态树 |

### 1.2 EVM（以太坊虚拟机）

EVM 是一个**准图灵完备**的虚拟机（准——因为受 Gas 限制），运行在以太坊节点中。

关键特性：
- **栈式架构**：256位字宽栈，最大1024深度
- **指令集**：约140个操作码（arithmetic, memory, storage, control flow）
- **沙盒隔离**：每个合约独立执行环境
- **确定性**：相同输入 → 相同输出

### 1.3 账户模型

两种账户类型：

| 特性 | EOA（外部账户） | 合约账户 |
|------|-----------------|----------|
| 有私钥 | ✅ | ❌ |
| 可发起交易 | ✅ | ❌（通过交易触发） |
| 有代码 | ❌ | ✅ |
| 有存储 | ❌ | ✅ |

账户状态：
```
{
  nonce:     uint64,    // 已发出交易数（EOA）/ 已创建合约数（Contract）
  balance:   uint256,   // 余额（Wei）
  storageRoot: bytes32, // 存储树根哈希
  codeHash:  bytes32    // 合约代码哈希（EOA为空）
}
```

### 1.4 Gas 机制

Gas 是执行计算所需的"燃料"，防止无限循环：

```
交易费用 = Gas Used × Gas Price
```

| 操作 | Gas 成本 |
|------|---------|
| ADD/SUB | 3 |
| MUL/DIV | 5 |
| SSTORE（0→非0） | 20,000 |
| SSTORE（非0→0） | 2,900（退款） |
| SLOAD | 100 |
| CALL | 700 |
| CREATE | 32,000 |

---

## 2. 交易格式与状态转换

### 2.1 交易格式

```
{
  nonce:    uint64,       // 发送者nonce
  gasPrice: uint256,      // Gas单价
  gasLimit: uint64,       // 最大Gas
  to:       address,      // 目标地址(空=合约创建)
  value:    uint256,      // 转账金额(Wei)
  data:     bytes,        // 调用数据/合约创建代码
  v, r, s:  bytes,        // 签名
}
```

EIP-1559 引入后的新格式（Type 2）：
```
{
  chainId:  uint64,
  nonce:    uint64,
  maxPriorityFeePerGas: uint256,  // 小费
  maxFeePerGas:         uint256,  // 总上限
  gasLimit: uint64,
  to:       address,
  value:    uint256,
  data:     bytes,
  accessList: [...],     // 可选的提前声明访问的地址/存储键
}
```

### 2.2 状态转换函数

```
σ[t+1] = Υ(σ[t], T)

Υ = 状态转换函数
σ[t] = 当前状态
T = 交易
```

**简化版状态转换**

```python
def apply_transaction(state, tx):
    # 1. 验证签名
    sender = recover_sender(tx)
    
    # 2. 检查nonce
    assert state[sender].nonce == tx.nonce
    
    # 3. 扣除上限费用
    max_cost = tx.gasLimit * tx.maxFeePerGas + tx.value
    assert state[sender].balance >= max_cost
    state[sender].balance -= max_cost
    state[sender].nonce += 1
    
    # 4. 执行
    if tx.to is None:
        # 合约创建
        contract_addr = create_contract(state, sender, tx)
        return contract_addr
    else:
        # 消息调用
        result = execute_message(state, tx.to, sender, tx.value, tx.data)
        return result
```

---

## 3. 智能合约基础

### 3.1 什么是智能合约

> 智能合约是部署在区块链上的**不可篡改**、**确定性执行**的程序代码。

**生命周期**：
1. 编写（Solidity/Vyper）
2. 编译为字节码
3. 部署（CREATE 交易）
4. 调用（通过交易或消息调用）

### 3.2 ABI（Application Binary Interface）

ABI 定义了调用合约函数的编码格式：

```
函数选择器 = keccak256("transfer(address,uint256)")[:4]

参数编码：根据Solidity类型的ABI编码规则依次编码
```

---

## 4. Solidity 语言概念

### 4.1 基本语法示例

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract Counter {
    // 状态变量（存储在链上）
    uint256 public count;
    address public owner;

    // 事件
    event Incremented(uint256 newCount);

    // 修饰符
    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    // 构造函数
    constructor() {
        owner = msg.sender;
        count = 0;
    }

    // 函数
    function increment() external onlyOwner {
        count += 1;
        emit Incremented(count);
    }

    // view 函数（不消耗Gas调用）
    function getCount() external view returns (uint256) {
        return count;
    }

    // pure 函数（不读也不写状态）
    function add(uint256 a, uint256 b) external pure returns (uint256) {
        return a + b;
    }
}
```

### 4.2 关键概念

| 概念 | 说明 |
|------|------|
| `storage` | 持久化存储，永久保存 |
| `memory` | 临时内存，函数调用后清除 |
| `calldata` | 只读调用数据 |
| `msg.sender` | 调用者地址 |
| `tx.origin` | 原始交易发送者 |
| `this` | 合约自身地址 |
| `require()` | 条件检查，失败则回退 |
| `revert()` | 主动回退 |
| `assert()` | 内部错误检查 |

### 4.3 数据位置

```solidity
contract DataLocations {
    // storage - 状态变量（自动）
    uint256[] public arr;

    function demo() external {
        // memory - 局部变量（不持久化）
        uint256[] memory localArr = new uint256[](3);
        
        // storage 引用
        uint256[] storage arrRef = arr;
        arrRef.push(42); // 会修改状态变量

        // calldata - 只读（函数参数）
    }
}
```

---

## 5. ERC-20 与 ERC-721 标准

### 5.1 ERC-20 (同质化代币)

标准接口：

```solidity
interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 amount) external returns (bool);
    function allowance(address owner, address spender) external view returns (uint256);
    function approve(address spender, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
}
```

**极简ERC-20实现**：
```solidity
contract MinimalERC20 is IERC20 {
    string public name;
    string public symbol;
    uint8 public decimals = 18;
    uint256 public totalSupply;
    
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    constructor(string memory _name, string memory _symbol, uint256 _initialSupply) {
        name = _name;
        symbol = _symbol;
        totalSupply = _initialSupply * 10**decimals;
        balanceOf[msg.sender] = totalSupply;
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        emit Transfer(msg.sender, to, amount);
        return true;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        allowance[from][msg.sender] -= amount;
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        emit Transfer(from, to, amount);
        return true;
    }
}
```

### 5.2 ERC-721 (非同质化代币 / NFT)

标准接口：

```solidity
interface IERC721 {
    function balanceOf(address owner) external view returns (uint256);
    function ownerOf(uint256 tokenId) external view returns (address);
    function safeTransferFrom(address from, address to, uint256 tokenId) external;
    function transferFrom(address from, address to, uint256 tokenId) external;
    function approve(address to, uint256 tokenId) external;
    function getApproved(uint256 tokenId) external view returns (address);
    function setApprovalForAll(address operator, bool approved) external;
    function isApprovedForAll(address owner, address operator) external view returns (bool);
}
```

关键区别：
- **ERC-20**：每个代币可互换（1 USDC = 1 USDC）
- **ERC-721**：每个代币唯一（每件NFT不同）
- **ERC-1155**：混合标准（同批次多类型代币）

---

## 6. 实现：极简 EVM（Python）

下面实现一个极简EVM，支持：
- 栈操作（PUSH, POP, DUP, SWAP）
- 算术（ADD, SUB, MUL）
- 存储（SSTORE, SLOAD）
- 环境信息（ADDRESS, BALANCE, CALLER）
- RETURN 返回数据

```python
"""
minimal_evm.py — Python实现极简EVM

支持操作码：
- 算术/栈：STOP(0x00), ADD(0x01), SUB(0x03), MUL(0x02)
- 栈操作：PUSH1(0x60), PUSH32(0x7f), POP(0x50), DUP1(0x80), SWAP1(0x90)
- 存储：SLOAD(0x54), SSTORE(0x55)
- 环境：ADDRESS(0x30), BALANCE(0x31), CALLER(0x33)
- 返回：RETURN(0xf3)

执行示例：
  600160005500 — PUSH1 01 | PUSH1 00 | SSTORE
  等价于 Solidity: storage[0] = 1
"""

from dataclasses import dataclass, field
from typing import Optional, Dict
import hashlib


@dataclass
class Account:
    """以太坊账户"""
    address: bytes
    nonce: int = 0
    balance: int = 0
    code: bytes = b""
    storage: Dict[bytes, bytes] = field(default_factory=dict)


class Stack:
    """256位栈（256-bit word stack）"""
    
    def __init__(self, max_depth: int = 1024):
        self.items: list[bytes] = []
        self.max_depth = max_depth
    
    def push(self, value: bytes):
        assert len(self.items) < self.max_depth, "Stack overflow"
        assert len(value) <= 32, f"Value too large: {len(value)} bytes"
        # 左填充到32字节
        padded = value.rjust(32, b'\x00') if len(value) < 32 else value[-32:]
        self.items.append(padded)
    
    def pop(self) -> bytes:
        assert len(self.items) > 0, "Stack underflow"
        return self.items.pop()
    
    def peek(self, depth: int = 0) -> bytes:
        assert depth < len(self.items), "Stack too shallow"
        return self.items[-(depth + 1)]
    
    def dup(self, n: int):
        """DUP1 = depth 0, DUP2 = depth 1, ..."""
        value = self.peek(n)
        self.push(value)
    
    def swap(self, n: int):
        """SWAP1: swap 1st with 2nd, SWAP2: swap 1st with 3rd"""
        idx = -(n + 1)
        self.items[-1], self.items[idx] = self.items[idx], self.items[-1]
    
    @property
    def size(self) -> int:
        return len(self.items)


class Memory:
    """EVM内存（字节数组，按需扩展）"""
    
    def __init__(self):
        self.bytes = bytearray()
    
    def store(self, offset: int, value: bytes):
        """在 offset 处写入 value"""
        end = offset + len(value)
        if end > len(self.bytes):
            self.bytes.extend(b'\x00' * (end - len(self.bytes)))
        self.bytes[offset:end] = value
    
    def load(self, offset: int, size: int) -> bytes:
        """从 offset 读取 size 字节"""
        end = offset + size
        if end > len(self.bytes):
            self.bytes.extend(b'\x00' * (end - len(self.bytes)))
        return bytes(self.bytes[offset:end])
    
    def __len__(self):
        return len(self.bytes)


def to_uint256(b: bytes) -> int:
    """bytes → int（大端序）"""
    return int.from_bytes(b, byteorder='big')


def from_uint256(v: int) -> bytes:
    """int → bytes32"""
    return v.to_bytes(32, byteorder='big')


def parse_push_opcode(opcode: int) -> Optional[int]:
    """判断是否是PUSH指令，返回要压入的字节数"""
    if 0x60 <= opcode <= 0x7f:
        return opcode - 0x60 + 1  # PUSH1=1, PUSH2=2, ..., PUSH32=32
    return None


class EVM:
    """极简EVM执行引擎"""
    
    def __init__(self, code: bytes):
        self.code = code
        self.pc = 0  # 程序计数器
        self.stack = Stack()
        self.memory = Memory()
        self.stopped = False
        self.return_data = b""
        self.gas_used = 0
        
        # 环境（简化）
        self.address = bytes.fromhex("deadbeef" * 4)  # 0xdead...dead
        self.caller = bytes.fromhex("cafebabe" * 4)   # 0xcafe...babe
        self.state: Dict[bytes, Account] = {}
        self.value = 0  # msg.value
    
    def get_state_account(self, addr: bytes) -> Account:
        if addr not in self.state:
            self.state[addr] = Account(address=addr)
        return self.state[addr]
    
    def run(self) -> bytes:
        """执行字节码，返回return_data"""
        
        while not self.stopped and self.pc < len(self.code):
            opcode = self.code[self.pc]
            self.pc += 1
            
            # 检查是否是 PUSH 指令
            push_bytes = parse_push_opcode(opcode)
            if push_bytes is not None:
                data = self.code[self.pc:self.pc + push_bytes]
                assert len(data) == push_bytes, "PUSH beyond code end"
                self.pc += push_bytes
                self.stack.push(data)
                self.gas_used += 3
                continue
            
            if opcode == 0x00:  # STOP
                self.stopped = True
                self.gas_used += 0
            
            elif opcode == 0x01:  # ADD
                a, b = to_uint256(self.stack.pop()), to_uint256(self.stack.pop())
                self.stack.push(from_uint256((a + b) & ((1 << 256) - 1)))
                self.gas_used += 3
            
            elif opcode == 0x02:  # MUL
                a, b = to_uint256(self.stack.pop()), to_uint256(self.stack.pop())
                result = (a * b) & ((1 << 256) - 1)
                self.stack.push(from_uint256(result))
                self.gas_used += 5
            
            elif opcode == 0x03:  # SUB
                a, b = to_uint256(self.stack.pop()), to_uint256(self.stack.pop())
                result = (a - b) & ((1 << 256) - 1)
                self.stack.push(from_uint256(result))
                self.gas_used += 3
            
            elif opcode == 0x04:  # DIV
                a, b = to_uint256(self.stack.pop()), to_uint256(self.stack.pop())
                result = 0 if b == 0 else a // b
                self.stack.push(from_uint256(result))
                self.gas_used += 5
            
            elif opcode == 0x50:  # POP
                self.stack.pop()
                self.gas_used += 2
            
            elif opcode == 0x54:  # SLOAD
                key = self.stack.pop()
                account = self.get_state_account(self.address)
                value = account.storage.get(key, b'\x00' * 32)
                self.stack.push(value)
                self.gas_used += 100
            
            elif opcode == 0x55:  # SSTORE
                value = self.stack.pop()
                key = self.stack.pop()
                account = self.get_state_account(self.address)
                old_value = account.storage.get(key, b'\x00' * 32)
                # Gas 成本简化：新存储20,000，修改2,900
                if old_value == b'\x00' * 32:
                    self.gas_used += 20000
                else:
                    self.gas_used += 2900
                if value == b'\x00' * 32:
                    if key in account.storage:
                        del account.storage[key]
                else:
                    account.storage[key] = value
            
            elif opcode == 0x30:  # ADDRESS
                self.stack.push(self.address)
                self.gas_used += 2
            
            elif opcode == 0x31:  # BALANCE
                addr = self.stack.pop()
                account = self.get_state_account(addr)
                self.stack.push(from_uint256(account.balance))
                self.gas_used += 100
            
            elif opcode == 0x33:  # CALLER
                self.stack.push(self.caller)
                self.gas_used += 2
            
            elif opcode == 0x80:  # DUP1
                self.stack.dup(0)
                self.gas_used += 3
            
            elif opcode == 0x90:  # SWAP1
                self.stack.swap(1)
                self.gas_used += 3
            
            elif opcode == 0xf3:  # RETURN
                offset = to_uint256(self.stack.pop())
                size = to_uint256(self.stack.pop())
                self.return_data = self.memory.load(offset, size)
                self.stopped = True
                self.gas_used += 0
            
            elif opcode == 0x52:  # MSTORE
                offset = to_uint256(self.stack.pop())
                value = self.stack.pop()
                self.memory.store(offset, value)
                self.gas_used += 3
            
            elif opcode == 0x51:  # MLOAD
                offset = to_uint256(self.stack.pop())
                value = self.memory.load(offset, 32)
                self.stack.push(value)
                self.gas_used += 3
            
            else:
                raise ValueError(f"Unknown opcode: 0x{opcode:02x} at pc={self.pc - 1}")
        
        return self.return_data


def disassemble(code: bytes) -> str:
    """反汇编字节码为可读形式"""
    lines = []
    pc = 0
    while pc < len(code):
        op = code[pc]
        pc += 1
        push_n = parse_push_opcode(op)
        if push_n is not None:
            data = code[pc:pc + push_n]
            data_hex = data.hex()
            pc += push_n
            lines.append(f"  {pc - 1 - push_n:04x}  PUSH{push_n}  0x{data_hex}")
        else:
            names = {
                0x00: "STOP", 0x01: "ADD", 0x02: "MUL", 0x03: "SUB",
                0x04: "DIV", 0x50: "POP", 0x51: "MLOAD", 0x52: "MSTORE",
                0x54: "SLOAD", 0x55: "SSTORE",
                0x30: "ADDRESS", 0x31: "BALANCE", 0x33: "CALLER",
                0x80: "DUP1", 0x90: "SWAP1",
                0xf3: "RETURN",
            }
            name = names.get(op, f"UNKNOWN(0x{op:02x})")
            lines.append(f"  {pc - 1:04x}  {name}")
    return "\n".join(lines)


# ============================================================
# 测试用例
# ============================================================

def test_arithmetic():
    """测试算术运算：PUSH1 02 | PUSH1 03 | ADD | RETURN"""
    # 计算 3 + 2 = 5
    # 步骤: PUSH1 03 → PUSH1 02 → ADD → 结果放入内存 → RETURN
    code = bytes([
        0x60, 0x03,       # PUSH1 03
        0x60, 0x02,       # PUSH1 02
        0x01,             # ADD → stack: [5]
        0x60, 0x00,       # PUSH1 00 (offset)
        0x52,             # MSTORE → memory[0:32] = 5
        0x60, 0x20,       # PUSH1 32 (size)
        0x60, 0x00,       # PUSH1 00 (offset)
        0xf3,             # RETURN
    ])
    
    print("=== 算术测试: 3+2 ===")
    print("字节码:", code.hex())
    print("\n反汇编:")
    print(disassemble(code))
    
    evm = EVM(code)
    result = evm.run()
    value = to_uint256(result)
    print(f"\n结果: {value} (期望值: 5) ✓" if value == 5 else f"\n结果: {value} (期望值: 5) ✗")
    print(f"Gas使用: {evm.gas_used}")
    print()


def test_storage():
    """测试存储：SSTORE(0x00, 0x42) → SLOAD(0x00)"""
    # 存储 key=0, value=0x42 到 storage
    code = bytes([
        0x60, 0x42,       # PUSH1 0x42 (value)
        0x60, 0x00,       # PUSH1 0x00 (key)
        0x55,             # SSTORE → storage[0] = 0x42
        0x60, 0x00,       # PUSH1 0x00 (key)
        0x54,             # SLOAD → push storage[0] to stack
        0x60, 0x00,       # PUSH1 0x00 (memory offset)
        0x52,             # MSTORE
        0x60, 0x20,       # PUSH1 32 (size)
        0x60, 0x00,       # PUSH1 0x00 (offset)
        0xf3,             # RETURN
    ])
    
    print("=== 存储测试: storage[0] = 0x42 ===")
    print("字节码:", code.hex())
    print("\n反汇编:")
    print(disassemble(code))
    
    evm = EVM(code)
    result = evm.run()
    value = to_uint256(result)
    expected = 0x42
    print(f"\n结果: {value} (期望值: {expected}) {'✓' if value == expected else '✗'}")
    
    # 验证存储状态
    stored = to_uint256(evm.get_state_account(evm.address).storage.get(b'\x00' * 32, b''))
    print(f"链上存储值: {stored} {'✓' if stored == expected else '✗'}")
    print(f"Gas使用: {evm.gas_used}")
    print()


def test_complex():
    """复杂计算: (10 + 20) * 3 - 5 = 85"""
    # stack 演化:
    # PUSH1 10 → [10]
    # PUSH1 20 → [10, 20]
    # ADD → [30]
    # PUSH1 3 → [30, 3]
    # MUL → [90]
    # PUSH1 5 → [90, 5]
    # SUB → [85]
    code = bytes([
        0x60, 0x0a,       # PUSH1 10
        0x60, 0x14,       # PUSH1 20
        0x01,             # ADD → 30
        0x60, 0x03,       # PUSH1 3
        0x02,             # MUL → 90
        0x60, 0x05,       # PUSH1 5
        0x03,             # SUB → 85
        0x60, 0x00,       # PUSH1 0
        0x52,             # MSTORE
        0x60, 0x20,       # PUSH1 32
        0x60, 0x00,       # PUSH1 0
        0xf3,             # RETURN
    ])
    
    print("=== 复杂计算: (10 + 20) * 3 - 5 ===")
    print("字节码:", code.hex())
    print("\n反汇编:")
    print(disassemble(code))
    
    evm = EVM(code)
    result = evm.run()
    value = to_uint256(result)
    print(f"\n结果: {value} (期望值: 85) {'✓' if value == 85 else '✗'}")
    print(f"Gas使用: {evm.gas_used}")
    print()


def test_counter_simulation():
    """
    模拟一个简单的计数器合约
    
    假设存储槽 0 是计数器值
    字节码: 
      SLOAD(0) → 读取当前计数
      ADD(1)   → 加1
      SSTORE(0) → 存回
      RETURN → 返回新值
    """
    # 先初始化 storage[0] = 0
    init_code = bytes([
        0x60, 0x00,       # PUSH1 0 (value)
        0x60, 0x00,       # PUSH1 0 (key)
        0x55,             # SSTORE → storage[0] = 0
    ])
    
    # 递增函数:
    # 1. SLOAD(0) → 读取当前值
    # 2. PUSH1 1 → 压入1
    # 3. ADD → 加1
    # 4. PUSH1 0 → 存储位置
    # 5. SWAP1 → 交换值和位置
    # 6. SSTORE → 存储新值
    # 7. 读取结果到内存并RETURN
    increment_code = bytes([
        0x60, 0x00,       # PUSH1 0 (key)
        0x54,             # SLOAD → [count]
        0x60, 0x01,       # PUSH1 1
        0x01,             # ADD → [count+1]
        0x60, 0x00,       # PUSH1 0
        0x90,             # SWAP1 → [key, count+1]
        0x55,             # SSTORE → storage[0] = count+1
        0x60, 0x00,       # PUSH1 0 (key)
        0x54,             # SLOAD → [new_count]
        0x60, 0x00,       # PUSH1 0
        0x52,             # MSTORE
        0x60, 0x20,       # PUSH1 32
        0x60, 0x00,       # PUSH1 0
        0xf3,             # RETURN
    ])
    
    full_code = init_code + increment_code
    
    print("=== 计数器模拟: storage[0]++ ===")
    print("字节码:", full_code.hex())
    print("\n反汇编:")
    print(disassemble(full_code))
    
    evm = EVM(full_code)
    result = evm.run()
    value = to_uint256(result)
    print(f"\n第1次递增后: {value} {'✓' if value == 1 else '✗'}")
    
    # 状态保留，重新执行递增部分
    evm2 = EVM(increment_code)
    evm2.state = evm.state
    evm2.address = evm.address
    evm2.caller = evm.caller
    result2 = evm2.run()
    value2 = to_uint256(result2)
    print(f"第2次递增后: {value2} {'✓' if value2 == 2 else '✗'}")
    
    evm3 = EVM(increment_code)
    evm3.state = evm2.state
    evm3.address = evm2.address
    evm3.caller = evm2.caller
    result3 = evm3.run()
    value3 = to_uint256(result3)
    print(f"第3次递增后: {value3} {'✓' if value3 == 3 else '✗'}")
    
    print()


if __name__ == "__main__":
    test_arithmetic()
    test_storage()
    test_complex()
    test_counter_simulation()
```

**运行方式**：
```bash
python memory/learning/blockchain_02_ethereum.py
```

**输出的EVM结构图**：
```
┌─────────────────────────────────────────────────────────────┐
│                    EVM Execution Context                    │
├────────────┬────────────────────────────────────────────────┤
│    Code    │  PUSH1 42  PUSH1 00  SSTORE  ...              │
├────────────┼────────────────────────────────────────────────┤
│    PC      │  Program Counter → 指向当前指令               │
├────────────┼────────────────────────────────────────────────┤
│   Stack    │  256-bit word stack                            │
│            │  ┌─────┐  ┌─────┐  ┌─────┐                    │
│            │  │  42 │  │  0  │  │  .. │  ← top             │
│            │  └─────┘  └─────┘  └─────┘                    │
├────────────┼────────────────────────────────────────────────┤
│  Memory    │  字节数组（按需扩展）                          │
│            │  [00 00 ... 00 2a 00 00 ...]                  │
├────────────┼────────────────────────────────────────────────┤
│  Storage   │  永久存储（key→value，合约账户专属）           │
│            │  {0x0000...0000 → 0x0000...002a, ...}         │
├────────────┼────────────────────────────────────────────────┤
│ Gas Used   │  累计Gas消耗                                   │
├────────────┼────────────────────────────────────────────────┤
│   World    │  所有账户状态                                  │
│   State    │  { addr1: {nonce, balance, storage, code},    │
│            │    addr2: {nonce, balance, storage, code} }   │
└────────────┴────────────────────────────────────────────────┘
```

---

## 知识点总结

| 概念 | 一句话总结 |
|------|-----------|
| EVM | 基于栈的准图灵完备虚拟机，256位字宽 |
| 账户模型 | EOA（私钥控制）和 Contract Account（代码控制） |
| Gas | 计算燃料，防止无限循环，按操作定价 |
| 智能合约 | 部署在链上不可篡改的程序 |
| Solidity | 以太坊主流合约语言，编译为EVM字节码 |
| ERC-20 | 同质化代币标准（transfer/approve/transferFrom） |
| ERC-721 | NFT标准，每个代币唯一 |
| ABI | 编码/解码合约调用的接口规范 |
| SSTORE | 写一次存储20,000 Gas（昂贵！） |
| RETURN | 从EVM返回数据到调用者 |

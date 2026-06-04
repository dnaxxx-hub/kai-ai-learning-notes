# 反向工程与安全 — 深度学习笔记

> 从 PE 格式到密码学实现，构建完整的逆向工程与安全知识体系

---

## 一、PE 文件格式深度解析

### 1.1 DOS 头（IMAGE_DOS_HEADER）

PE 文件起始于 MS-DOS MZ 头，向后兼容的遗留结构：

```c
typedef struct _IMAGE_DOS_HEADER {
    WORD  e_magic;      // "MZ" (0x5A4D)
    WORD  e_cblp;       // 最后页的字节数
    WORD  e_cp;         // 文件页数
    WORD  e_crlc;       // 重定位项数
    WORD  e_cparhdr;    // 头部以段落计的大小
    WORD  e_minalloc;   // 最小额外分配
    WORD  e_maxalloc;   // 最大额外分配
    WORD  e_ss;         // 初始 SS
    WORD  e_sp;         // 初始 SP
    WORD  e_csum;       // 校验和
    WORD  e_ip;         // 初始 IP
    WORD  e_cs;         // 初始 CS
    WORD  e_lfarlc;     // 重定位表偏移
    WORD  e_ovno;       // 覆盖号
    WORD  e_res[4];     // 保留
    WORD  e_oemid;      // OEM ID
    WORD  e_oeminfo;    // OEM 信息
    WORD  e_res2[10];   // 保留
    LONG  e_lfanew;     // → NT 头的文件偏移（关键）
} IMAGE_DOS_HEADER;
```

**关键字段**：`e_lfanew` 指向 PE 签名（"PE\0\0"）的偏移。

### 1.2 NT 头（IMAGE_NT_HEADERS）

```c
typedef struct _IMAGE_NT_HEADERS {
    DWORD Signature;                       // "PE\0\0" (0x00004550)
    IMAGE_FILE_HEADER FileHeader;
    IMAGE_OPTIONAL_HEADER OptionalHeader;
} IMAGE_NT_HEADERS;
```

**FileHeader** 关键字段：
- `Machine`: 0x014C (x86), 0x8664 (x64), 0x01C4 (ARM)
- `NumberOfSections`: 节表数量
- `SizeOfOptionalHeader`: OptionalHeader 大小
- `Characteristics`: 文件属性（EXE/DLL/系统文件...）

**OptionalHeader** 关键字段（32 与 64 位版差异）：
- `Magic`: 0x10B (PE32), 0x20B (PE32+)
- `AddressOfEntryPoint`: 入口点 RVA
- `ImageBase`: 首选加载基址
- `SizeOfImage`: 内存映像大小
- `DataDirectory[16]`: 数据目录数组

### 1.3 节表（IMAGE_SECTION_HEADER）

```
每个节头 40 字节，Name[8] + VirtualSize + VirtualAddress + SizeOfRawData + 
PointerToRawData + PointerToRelocations + ... + Characteristics
```

**常见节区**：
| 节名 | 用途 | 常见特征 |
|------|------|----------|
| `.text` | 代码节 | 可执行，不可写 |
| `.data` | 已初始化全局变量 | 可读写 |
| `.rdata` | 只读数据（导入/导出表） | 只读 |
| `.bss` | 未初始化数据 | 可读写 |
| `.idata` | 导入表（旧链接器） | 只读 |
| `.edata` | 导出表 | 只读 |
| `.reloc` | 重定位表 | 可丢弃 |
| `.rsrc` | 资源 | 只读 |
| `.tls` | 线程局部存储 | 可读写 |

### 1.4 导入表（IMAGE_IMPORT_DESCRIPTOR）

```
每个 IID 20 字节，以全零结构终止：
- OriginalFirstThunk (INT): 导入名称表 RVA
- TimeDateStamp: 通常为 0（绑定导入时设置）
- ForwarderChain: 转发链
- Name: DLL 名称 RVA
- FirstThunk (IAT): 导入地址表 RVA
```

**IAT 解析流程**：
1. 遍历 IID 数组直到全零
2. 通过 Name 字段获取 DLL 名称
3. 遍历 INT/IAT 数组获取导入函数
4. IMAGE_ORDINAL_FLAG (0x80000000/0x8000000000000000) 判断是序号还是名称导入
5. 名称导入：IMAGE_IMPORT_BY_NAME（Hint + Name）

### 1.5 导出表（IMAGE_EXPORT_DIRECTORY）

```c
typedef struct _IMAGE_EXPORT_DIRECTORY {
    DWORD Characteristics;
    DWORD TimeDateStamp;
    WORD  MajorVersion;
    WORD  MinorVersion;
    DWORD Name;               // DLL 名称 RVA
    DWORD Base;               // 序号基数
    DWORD NumberOfFunctions;  // 函数总数
    DWORD NumberOfNames;      // 名称数
    DWORD AddressOfFunctions; // 函数地址数组 RVA
    DWORD AddressOfNames;     // 函数名称数组 RVA
    DWORD AddressOfNameOrdinals; // 序号数组 RVA
} IMAGE_EXPORT_DIRECTORY;
```

**导出查找**：名称 → NameOrdinals → AddressOfFunctions[ordinal]

### 1.6 资源表（IMAGE_RESOURCE_DIRECTORY）

三层结构：
```
Resource Directory → Resource Directory Entry → 
  Resource Directory (ID 级) → Entry → 
    Resource Directory (语言级) → Entry → Data Entry
```

- 资源类型（常见）：1=光标, 2=位图, 3=图标, 4=菜单, 5=对话框, 6=字符串表, 9=加速键, 10=RC数据, 12=组光标, 14=组图标, 16=版本信息, 24=清单

### 1.7 TLS 回调（IMAGE_TLS_DIRECTORY）

```
TLS 目录包含：
- StartAddressOfRawData / EndAddressOfRawData：TLS 模板数据
- AddressOfIndex：TLS 索引
- AddressOfCallBacks：TLS 回调函数数组（以 NULL 终止）
  → 这些回调在入口点之前执行！
```

**反调试用途**：TLS 回调在入口点之前执行，可用来检测调试器。

### 1.8 重定位表（IMAGE_BASE_RELOCATION）

```c
typedef struct _IMAGE_BASE_RELOCATION {
    DWORD VirtualAddress;  // 页起始 RVA
    DWORD SizeOfBlock;     // 块大小（+8 为表项数）
    WORD  TypeOffset[1];   // 项数组
} IMAGE_BASE_RELOCATION;
```

**重定位类型**：
- IMAGE_REL_BASED_ABSOLUTE (0)：跳过对齐
- IMAGE_REL_BASED_HIGH (1)：高位
- IMAGE_REL_BASED_LOW (2)：低位
- IMAGE_REL_BASED_HIGHLOW (3)：32 位
- IMAGE_REL_BASED_DIR64 (10)：64 位

**计算公式**：`ValueAtOffset += Delta = NewBase - OldBase`

---

## 二、x86-64 汇编回顾（逆向视角）

### 2.1 寄存器（x64——8 + 8 + 6 = 22 个关键寄存器）

| 类型 | 寄存器 | 说明 |
|------|--------|------|
| 通用 | RAX, RCX, RDX, RBX, RSP, RBP, RSI, RDI | 32 位用 E- 前缀 |
| 扩展 | R8–R15 | x64 新增 |
| XMM | XMM0–XMM15 | SSE/AVX 浮点 |
| 段 | CS, DS, ES, FS, GS | FS 在 x64 Windows 指向 TEB |

### 2.2 x64 调用约定（Microsoft x64）

- **前 4 个参数**：RCX, RDX, R8, R9
- **额外参数**：栈（从右向左压入）
- **返回值**：RAX
- **Shadow Space**：被调用者在栈上留 32 字节（4×8）
- **栈对齐**：16 字节（call 压 8 字节返回后 = 未对齐，被调用者 push rbp = 对齐）
- **异常处理**：基于表的结构化异常处理（.pdata 节）

### 2.3 常见逆向指令模式

```
# 函数序言
push rbp
mov  rbp, rsp
sub  rsp, 0x40

# PE/B 加载基址获取（Shellcode 常用）
call $+5
pop  rax         ; rax = 当前 IP

# 反调试 - PEB 检查
mov rax, gs:[0x60]  ; rax = PEB
mov al, [rax+0x02]  ; PEB->BeingDebugged

# 调用约定模式
mov rcx, arg1
mov rdx, arg2
call func

# JIT/优化
lea  rcx, [rcx+rdx*4]  ; 用 LEA 代替 MUL
xor  eax, eax           ; 清零——最常见的指令
test ecx, ecx
jz   .label             ; 分支
```

---

## 三、反调试技术

### 3.1 IsDebuggerPresent（最基础）

```c
// 原理：检查 PEB->BeingDebugged 标志
BOOL IsDebuggerPresent() {
    return NtCurrentPeb()->BeingDebugged;
}
```

**绕过方法**：
- 手动将 `PEB + 0x02` 字节修改为 0
- Hook NtQueryInformationProcess

### 3.2 NtGlobalFlag

```c
// 检查进程堆标志位
// 当被调试时，ntdll!NtGlobalFlag != 0
// 正常 = 0，调试时 = 0x70 (FLG_HEAP_ENABLE_TAIL_CHECK | 
//   FLG_HEAP_ENABLE_FREE_CHECK | FLG_HEAP_VALIDATE_PARAMETERS)
ULLONG NtGlobalFlag() {
    PPEB peb = NtCurrentPeb();
    // NtGlobalFlag 位于 PEB + 0x68 (x64) 或 PEB + 0x68 (x86)
    return *(ULONG_PTR*)((PBYTE)peb + 0xBC); // x86
}
```

### 3.3 TLS 回调

在入口点执行前运行的代码——URL 下载器、反调试检查

```c
// 注册 TLS 回调
void NTAPI TlsCallback(PVOID DllHandle, DWORD Reason, PVOID Reserved) {
    if (IsDebuggerPresent())
        ExitProcess(-1);
}
```

### 3.4 NtQueryInformationProcess

```
ProcessDebugPort      (0x07)：返回 -1 表示被调试
ProcessDebugFlags     (0x1F)：返回 0 表示被调试
ProcessDebugObjectHandle (0x1E)：返回非 0 句柄表示被调试
```

```c
NTSTATUS NtQueryInformationProcess(
    HANDLE ProcessHandle,
    PROCESSINFOCLASS ProcessInformationClass,
    PVOID ProcessInformation,
    ULONG ProcessInformationLength,
    PULONG ReturnLength
);
```

### 3.5 Hardware Breakpoints 检查

通过 `GetThreadContext` 检查 Dr0–Dr3 寄存器是否非零：

```c
bool CheckHardwareBP() {
    CONTEXT ctx = { .ContextFlags = CONTEXT_DEBUG_REGISTERS };
    GetThreadContext(GetCurrentThread(), &ctx);
    return ctx.Dr0 || ctx.Dr1 || ctx.Dr2 || ctx.Dr3;
}
```

### 3.6 Timestamp 检查

```c
// 单步调试时指令间隔远大于正常执行
bool CheckTiming(volatile LONGLONG *counter) {
    LONGLONG t1 = __rdtsc();
    // 执行一小段代码
    Sleep(1);
    LONGLONG t2 = __rdtsc();
    return (t2 - t1) > EXPECTED_THRESHOLD;
}
```

### 3.7 其他常见技术

| 技术 | 描述 | 绕过方法 |
|------|------|----------|
| NtClose(INVALID_HANDLE) | 调试器容易崩溃 | 处理异常 |
| INT 3/2D 断点 | int 0x03/0x2D 检查 | 跳过 |
| ProcessHeap 标志 | 调试时堆标志变化 | 手动修复 |
| DebugObject 检测 | NtQueryObject | Hook |
| 父进程检查 | explorer.exe vs 调试器 | 模拟父进程 |

---

## 四、反反调试技术

### 4.1 SMC（自修改代码，Self-Modifying Code）

```asm
; 执行时解密代码
_start:
    lea rsi, encrypted_code
    lea rdi, decrypted_buffer
    mov ecx, code_size
    ; 逐字节 XOR 解密
.loop:
    lodsb
    xor al, key_byte
    stosb
    loop .loop
    jmp decrypted_buffer  ; 跳到解密后的代码
```

**特点**：静态分析无效，必须动态跟踪——但动态跟踪又触发反调试。

### 4.2 代码混淆

**控制流平坦化（OLLVM）**：
```
原始: A → B → C
混淆后: A → Dispatcher → B → Dispatcher → C → Dispatcher
```

**虚假控制流**：在真实分支间插入永远不可能走到的死代码。

**指令替换**：
```
ADD EAX, 5  → SUB EAX, -5
PUSH EBP; MOV EBP, ESP  → XCHG ESP, EBP; PUSH EBP; POP EBP
```

**子表达式展开**：
```
A = B + C + D → A = (B + C) + D; 或 A = B + (C + D);
```

### 4.3 OLLVM（Obfuscator-LLVM）

基于 LLVM 的代码混淆框架（已停更，Clang 15+ 需补丁）：
- **Bogus Control Flow（BCF）**：虚假控制流
- **Control Flow Flattening（CFF）**：控制流平坦化
- **Instruction Substitution（ISub）**：指令替换
- **Basic Block Splitting**：基本块拆分

### 4.4 其他防御

- **花指令**（Junk Code）：插入永远不会执行但混淆反汇编器的字节序列
- **多态代码**（Polymorphic Code）：每次变异但功能相同的代码
- **变形代码**（Metamorphic Code）：完全重写自身，不保留模式

---

## 五、Shellcode 编写基础

### 5.1 基本原则

1. **避免空字节**（0x00）：strcpy/strcat 类漏洞利用截断条件
2. **位置无关**：不能有绝对地址引用
3. **紧凑性**：空间限制（几十到几百字节）
4. **API 解析**：通过 PEB 遍历 kernel32 → 查找 GetProcAddress

### 5.2 经典 Shellcode 结构

```asm
; Step 1: 获取 kernel32 基址（FS/GS 段→PEB→PEB_LDR_DATA→InMemoryOrderModuleList）
xor  ecx, ecx
mov  eax, fs:[ecx + 0x30]   ; PEB
mov  eax, [eax + 0x0C]      ; PEB->Ldr
mov  esi, [eax + 0x1C]      ; Ldr->InMemoryOrderModuleList.Flink
lodsd                        ; 第二个模块
xchg esi, eax
lodsd                        ; kernel32 base

; Step 2: 解析 kernel32 导出表 → GetProcAddress
mov  ebp, eax               ; ebp = kernel32 base
mov  eax, [ebp + 0x3C]      ; e_lfanew
mov  edx, [ebp+eax+0x78]    ; 导出表 RVA
add  edx, ebp               ; edx = 导出表 VA
mov  ebx, [edx+0x24]        ; NameOrdinals
add  ebx, ebp
; ...（后续查表获取函数地址）

; Step 3: 调用 API
push 0x00687373             ; "ss\0"
push 0x65796577             ; "weye"
push 0x646F6362             ; "bcmd"
push esp                    ; "cmd.exe\0"
call eax                    ; WinExec("cmd.exe", SW_HIDE)
```

### 5.3 API Hash 技术

```c
// 哈希函数（如 ROR13）替代字符串存储
DWORD HashString(char *str) {
    DWORD hash = 0;
    while (*str) {
        hash = (hash >> 13) | (hash << 19);  // ROR 13
        hash += *str++;
    }
    return hash;
}
```

---

## 六、加壳与脱壳

### 6.1 UPX（Ultimate Packer for eXecutables）

**加壳流程**：
1. 压缩原始 PE（LZMA/NRV2B）
2. 创建新的 PE 结构（极小）
3. 加解密 stubs（入口点指向 UPX 解压代码）
4. 运行时解压 → 跳转 OEP

**脱壳标志**：
- 入口点：`PUSHAD; MOV ESI, ...`（典型 UPX 序言）
- `.UPX0` / `.UPX1` 节名
- **手动脱壳**：监视 ESP 变化（ESP 定律）、在 PUSHAD 处断点

**ESP 定律**（快速脱 UPX/NSPack/ASPack）：
1. 在 OEP 设断，运行后按 PUSHAD
2. 记录 ESP，在硬件访问断点配合
3. 运行到 OEP 附近

### 6.2 VMProtect

**工作原理**：
- 将 x86 代码翻译为虚拟机的自定义字节码
- 虚拟机解释器（VM Entry）执行字节码
- 每次加壳变异的随机指令集

**对抗手段**：
- 无完美脱壳（理论上）
- 跟踪 VM Entry → 记录字节码 → 反向翻译
- 主动记录：跟踪解释器执行的每条指令

### 6.3 常见加壳识别

| 壳名 | 特征 | 脱壳难度 |
|------|------|----------|
| UPX | `.UPX0`/`.UPX1` 节、NRV 压缩 | ★☆☆☆☆ |
| ASPack | `.adata` 节, `POPAD` 后 JMP OEP | ★★☆☆☆ |
| NSPack | `.nsp0`/`.nsp1` 节 | ★★☆☆☆ |
| Themida | `.themida` 节、虚拟机代码 | ★★★★★ |
| VMProtect | `.vmp0`/`.vmp1` 节 | ★★★★★ |
| Enigma | 多层混淆+反调试 | ★★★☆☆ |

### 6.4 熵值分析

未加壳代码通常在 **5.0–6.5** 之间；
加壳/加密后熵值可接近 **7.8–7.99**（接近均匀分布）。

```
节名         原始熵值    加壳后熵值
.text        6.4         7.8
.data        3.2         4.5
.rsrc        4.1         7.5
```

---

## 七、密码学应用

### 7.1 TLS 1.3 握手（简化版）

```
Client                              Server
  |                                    |
  |— ClientHello (KeyShare, +SigAlgs) →|
  |                                    |
  |← ServerHello + KeyShare           |
  |← EncryptedExtensions              |
  |← Certificate(Cert + Signature)    |
  |← CertificateVerify                |
  |← Finished (MAC of handshake)      |
  |                                    |
  |— Finished (MAC of handshake)     →|
  |                                    |
  |========= Application Data ========>|
  |<======== Application Data ========|
```

**TLS 1.3 核心改进**：
- 1-RTT 握手（流量 1 次往返）
- 0-RTT 恢复（需要 PSK 预共享密钥）
- 废弃不安全密码套件（RC4、3DES、CBC-Mode）
- 使用 HKDF + HMAC 派生密钥

### 7.2 数字签名

**流程**：
1. **签名**：Hash(Message) → Sign(PrivateKey, Hash) → Signature
2. **验证**：Hash(Message) → Verify(PublicKey, Hash, Signature)

**签名算法**：
- RSA-PSS（概率签名方案）
- ECDSA（基于椭圆曲线）
- EdDSA / Ed25519

### 7.3 证书验证（X.509）

```
证书链验证：
Root CA (自签名) → Intermediate CA → Leaf Certificate
     |                      |                |
  信任锚点              验证签名         验证签名
                                      + 域名匹配
                                      + 有效期
                                      + CRL/OCSP 吊销
```

### 7.4 常见攻击

| 攻击 | 原理 | 防御 |
|------|------|------|
| TLS 降级 | 强制使用弱密码套件 | 禁用旧版 TLS |
| 证书伪造 | 颁发虚假证书 | 证书透明度(CT) |
| 中间人(MITM) | 拦截密钥协商 | 证书锁定/HPKP |

---

## 八、对称加密

### 8.1 AES-GCM（Galois/Counter Mode）

**为什么是 GCM？**
- 同时提供 **机密性**（CTR 模式加密）
- 和 **认证**（GHASH 消息认证码）
- 并行化友好、不需要填充

**结构**：
```
初始化向量 (12 字节推荐)
  ↓
递增计数器 → AES加密 → 密钥流 ⊕ 明文 → 密文
                                    ↓
           GHASH(附加数据 || 密文 || len(AAD)||len(Ciphertext))
                                    ↓
                  ⊕ AES(J0) → 认证标签 (16 字节)
```

**为什么 12 字节 IV？**
- 直接作为 J0（Counter 0）；非 12 字节需通过 GHASH 转换

**AES 轮数**：
- AES-128: 10 轮
- AES-192: 12 轮
- AES-256: 14 轮

### 8.2 ChaCha20 流密码

**优点**：软件实现比 AES 快 3 倍（无硬件加速时）

**初始状态**（16 × 32-bit 矩阵）：
```
"expand 32-byte k" | Key(256-bit)
Key(续)            | Counter(64-bit) | Nonce(64-bit)
```

**核心轮函数**：Quarter Round (QR)
```
a += b; d ^= a; d <<<= 16;
c += d; b ^= c; b <<<= 12;
a += b; d ^= a; d <<<= 8;
c += d; b ^= c; b <<<= 7;
```

ChaCha20 = 20 轮（10 次 double round，每次 DEOR/ODER）

---

## 九、非对称加密

### 9.1 RSA-OAEP

**RSA 基础**：
```
密钥生成：
1. 选择两个大素数 p, q（2048+ 位）
2. n = p × q
3. φ(n) = (p-1)(q-1)
4. 选择 e（通常 65537）, gcd(e, φ(n)) = 1
5. d = e⁻¹ mod φ(n)
6. 公钥 (n, e), 私钥 (n, d)

加密：c = mᵉ mod n
解密：m = cᵈ mod n
```

**OAEP（最优非对称加密填充）**：
```
m = 消息
r = 随机数

OAEP(m) = (m ⊕ G(r)) || (H(m ⊕ G(r)) ⊕ r)
          ↑ 掩码消息       ↑ 随机数掩码

G, H = MGF1 (Mask Generation Function, 基于哈希)
```

**OAEP 为什么重要**：直接 RSA 是确定性加密，OAEP 增加随机性防止选择明文攻击。

### 9.2 ECC（椭圆曲线密码学）

**核心思想**：`Q = d × G`（点乘运算）
- G 是生成元（基点）
- d 是私钥（随机整数）
- Q 是公钥（曲线上点）

**安全强度对比**：
| 对称强度 | RSA 密钥 | ECC 密钥 | 安全年限 |
|----------|----------|----------|----------|
| 80       | 1024     | 160      | 2015     |
| 112      | 2048     | 224      | 2030     |
| 128      | 3072     | 256      | 2040+    |
| 256      | 15360    | 512      | 2080+    |

**常见曲线**：P-256 (secp256r1), P-384, P-521, Curve25519 (X25519)

---

## 十、哈希算法

### 10.1 SHA-256

**结构**：Merkle-Damgård 结构 + Davies-Meyer 压缩函数

```
输入填充 → 消息分块 (512 位) → 压缩函数 → 8 × 32 位状态

压缩函数（64 轮）：
- 消息调度：W₀ = M_block, Wₜ = σ₁(Wₜ₋₂) + Wₜ₋₇ + σ₀(Wₜ₋₁₅) + Wₜ₋₁₆
- 64 个常数 K₀...K₆₃（前 64 个素数立方根的小数部分）
- 8 个工作变量 a...h
- Σ₀, Σ₁, σ₀, σ₁, Ch, Maj 函数
```

**SHA-2 系列**：
| 算法 | 输出位 | 安全强度 | 块大小 |
|------|--------|----------|--------|
| SHA-224 | 224 | 112 | 512 |
| SHA-256 | 256 | 128 | 512 |
| SHA-384 | 384 | 192 | 1024 |
| SHA-512 | 512 | 256 | 1024 |

### 10.2 SHA-3 (Keccak)

**结构**：海绵结构（Sponge Construction），非 Merkle-Damgård！

```
吸收阶段：            挤压阶段：
M₀ → M₁ → ... → Mₙ → → Z₀ → Z₁ → ...
|     |           |     |
f     f           f     f

f = Keccak-f[1600] 置换（24 轮）

五步轮函数：
θ: 列奇偶校验和扩散
ρ: 带状循环位移
π: Lane 重排
χ: 非线性层（与/非/异或）
ι: 轮常数异或

Keccak-f[1600] 状态：5×5×64 = 1600 位
```

**SHA-3 变体**：SHA3-224(1152), SHA3-256(1088), SHA3-384(832), SHA3-512(576)  
括号内为吸收速率 r

**并行海绵**：Keccak 容易并行化的海绵结构与 SHA-256 的串行 M-D 结构不同

### 10.3 哈希的安全性

| 性质 | 说明 | 强度 (SHA-256) |
|------|------|---------------|
| 抗原像（单向） | 给定 H(x)，无法求 x | 2²⁵⁶ |
| 抗第二原像 | 给定 x，无法求 x'≠x 使 H(x)=H(x') | 2²⁵⁶ |
| 抗碰撞 | 无法找到 x≠y 使 H(x)=H(y) | 2¹²⁸ |

---

## 十一、常见 Web 攻击与防御

### 11.1 SQL 注入

**原理**：未清理的用户输入拼接 SQL 查询

```sql
-- 经典
' OR '1'='1' -- 
' UNION SELECT username, password FROM users --

-- 防御
参数化查询 / ORM / PreparedStatement / 输入验证
```

### 11.2 XSS（跨站脚本）

| 类型 | 说明 | 示例 |
|------|------|------|
| 反射型 | 参数直接输出 | `<script>alert(1)</script>` |
| 存储型 | 存入数据库 | 评论框恶意脚本 |
| DOM型 | 客户端 JS 执行 | `location.hash` 注入 |

**防御**：输出编码（HTML Entity Encode）、CSP（内容安全策略）

### 11.3 CSRF（跨站请求伪造）

**原理**：利用用户已登录状态，诱骗用户点击恶意请求

```html
<img src="https://bank.com/transfer?to=attacker&amount=10000" />
```

**防御**：
- CSRF Token（嵌入表单的随机令牌）
- SameSite Cookie (=Strict/Lax)
- 二次确认（转账必须输入密码）
- Referer / Origin 检查

### 11.4 SSRF（服务端请求伪造）

**原理**：服务器端发起未过滤的 HTTP 请求，访问内部网络

```python
# 脆弱代码
url = request.GET['url']
data = urlopen(url)  # 可访问 169.254.169.254 (云元数据)

# 防御
白名单域名 / URL Scheme 限制 / 禁止内网地址
```

**经典攻击**：AWS/GCP/Azure 元数据服务 `http://169.254.169.254/latest/meta-data/`

---

## 十二、总结：技能图谱

```
逆向工程安全工程师技能树
├── PE/ELF/Mach-O 格式
│   ├── 节表/段表
│   ├── 导入导出表
│   ├── 重定位表
│   └── 资源/TLS
├── 静态分析
│   ├── IDA Pro / Ghidra
│   ├── 反汇编优化
│   └── 控制流分析
├── 动态分析
│   ├── x64dbg / WinDbg
│   ├── GDB / LLDB
│   └── 调试器检测绕过
├── 加壳与脱壳
│   ├── UPX / Themida / VMP
│   ├── 内存 dump
│   └── OEP 搜索
├── Shellcode
│   ├── Win32 API 解析
│   ├── 空字节过滤
│   └── Stage 加载器
├── Web 安全
│   ├── SQLi / XSS / CSRF / SSRF
│   ├── 文件包含 / RCE
│   └── SSRF 到 RCE
└── 密码学
    ├── 对称：AES / ChaCha20
    ├── 非对称：RSA / ECC
    ├── 哈希：SHA-2 / SHA-3
    └── 协议：TLS / SSH / IPsec
```

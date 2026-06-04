# 逆向工程 — 第八课：代码注入 + API HOOK (Detour)

## 核心能力
1. ✅ **Detour HOOK** — x64 远程进程原地修改，`mov rax, addr; jmp rax` 12字节跳板
2. ✅ **Trampoline** — 备份原始指令 + 跳回原函数继续执行
3. ✅ **VirtualAllocEx** — 目标进程中动态分配 RWX 内存
4. ✅ **CreateRemoteThread** — 远程线程执行注入代码
5. ✅ **DLL Injection** — 远程调用 LoadLibraryW

## 验证结果

### 内联 Detour HOOK（核心验证）

```
原始代码:
  4c 8b dc 48 81 ec 88 00 00 00   → mov r11, rsp; sub rsp, 0x88

Detour 注入后:
  48 b8 00 00 57 62 54 02 00 00   → mov rax, 0x25462570000 (hook stub)
  ff e0                           → jmp rax
  → jmp to 0x25462570000 ✓

Trampoline:
  @ 0x25462580000:
    4c 8b dc 48 81 ec 88 00 00 00  ← 原始指令备份
    48 b8 [target+12]                ← mov rax, return_addr
    ff e0                            ← jmp rax
```

### 注入方式对比

| 方式 | 方法 | 优点 | 缺点 |
|------|------|------|------|
| DLL注入 | CreateRemoteThread + LoadLibraryW | 简单、稳定 | 需要DLL文件 |
| Shellcode | 写机器码到远程 + 远程线程执行 | 无文件残留 | 编码复杂 |
| Detour | 修改函数前5-12字节 | 实时拦截 | 线程安全需小心 |

### Detour 在 x64 的特殊处理

x86 的 `jmp rel32` (5字节) 只有 ±2GB 范围。x64 用：
```asm
mov rax, target_addr  ; 48 b8 ... (10字节)
jmp rax               ; ff e0 (2字节)
总长: 12字节
```

要求被 hook 的函数开头至少有 12 字节可修改。

## DLL 注入命令
```bash
# 需要目标 PID 和管理员权限
python re_08_inject_hook.py inject <PID> <DLL_PATH>
```

## 关键技术点
- `VirtualAllocEx(MEM_COMMIT, PAGE_EXECUTE_READWRITE)` 分配远程 RWX 段
- `WriteProcessMemory` 写入 shellcode / hook code
- `CreateRemoteThread` 在目标中执行
- x64 注意：`LoadLibraryW` 地址要通过 `GetModuleHandleW("kernel32") + GetProcAddress` 获取
- 注入后要在目标进程空间清理（`VirtualFreeEx`）

## 下节 (re_09) 计划
- PE 解析扩展：导出表（EDT）手动解析
- 不使用 GetProcAddress，直接遍历导出表找函数地址
- 从 PEB 定位 kernel32 → 解析导出表 → 找函数

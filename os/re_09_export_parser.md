# 逆向工程 — 第九课：PE 导出表解析 (EDT)

## 核心能力
1. ✅ 完全不依赖 Win32 API 解析 PE 导出表
2. ✅ 手动读取 PE 头 → DataDirectory[0] → IMAGE_EXPORT_DIRECTORY
3. ✅ 通过 AddressOfNames / AddressOfNameOrdinals / AddressOfFunctions 三张表定位函数
4. ✅ 1693 个 kernel32 导出函数完整解析

## 验证结果
```
kernel32.dll @ 0x7ff8e1420000
  ExportDir RVA=0xa4bc0
  Functions=1693 Names=1693

Key function locations (absolute + RVA):
  GetProcAddress      → ordinal=734  RVA=0x33d00  abs=0x7ff8e1453d00
  LoadLibraryA        → ordinal=1013 RVA=0x42cd0  abs=0x7ff8e1462cd0
  LoadLibraryW        → ordinal=1016 RVA=0x3f710  abs=0x7ff8e145f710
  VirtualAlloc        → ordinal=1557 RVA=0x33d20  abs=0x7ff8e1453d20
  VirtualProtect      → ordinal=1563 RVA=0x38200  abs=0x7ff8e1458200
  CreateRemoteThread  → ordinal=261  RVA=0x42d60  abs=0x7ff8e1462d60
```

## PE 导出表结构

### 三张表 (Three-level lookup)
```
AddressOfNames           → ["AcquireSRWLockExclusive", ...]
AddressOfNameOrdinals    → [0, 1, 2, ..., 734, ...]  (ordinal for each name)
AddressOfFunctions       → [0x8e17, 0x8e50, ..., 0x33d00, ...]  (RVA for each ordinal)
```

查找过程：
```
for i in range(NumberOfNames):
    name_ptr = AddressOfNames[i]         → 名字字符串RVA
    if name == target:
        ordinal = AddressOfNameOrdinals[i] → 序号
        func_rva = AddressOfFunctions[ordinal] → 函数地址RVA
```

### IMAGE_EXPORT_DIRECTORY 字段偏移
```
+0x00: Characteristics   (4 bytes)
+0x04: TimeDateStamp     (4)
+0x08: Version           (4)
+0x0c: Name              (4)
+0x10: Base              (4)
+0x14: NumberOfFunctions (4)
+0x18: NumberOfNames     (4)
+0x1c: AddressOfFunctions (4) ← RVA
+0x20: AddressOfNames    (4) ← RVA
+0x24: AddressOfNameOrdinals (4) ← RVA
```

## 定位 DataDirectory[0] (导出表)
```python
# x64 PE32+ 流程:
dos = read(base, 64)
e_lfanew = struct.unpack("<I", dos[0x3C:0x40])[0]
pe_sig = read(base + e_lfanew, 4)           # 应该 = "PE\0\0"
file_hdr_offset = base + e_lfanew + 4
opt_hdr_offset = file_hdr_offset + 20       # IMAGE_FILE_HEADER is 20 bytes
# PE32+ optional header:
#   Magic(2) + linker(2) + code fields(28) + image base(8) + ...
#   DataDirectory starts at opt_hdr_offset + 112 (for PE32+)
data_dir_offset = opt_hdr_offset + 112
export_rva = read_dword(data_dir_offset)     # RVA of export dir
export_addr = image_base + export_rva         # Absolute address
```

## 实际应用
PE 导出表解析是 shellcode 和反调试工具的基石：
1. **Shellcode 标准入口**：PEB → kernel32 → 导出表 → GetProcAddress → 其他函数
2. **反检测**：检查目标函数的导出 RVA 是否被修改（inline hook 检测）
3. **手工调用**：无需 GetProcAddress，直接按 ordinal 调用

## 下节 (re_10) 计划
- 反调试技术 (IsDebuggerPresent / NtQueryInformationProcess / NtSetInformationThread)
- 基于调试寄存器的反调试
- 反反调试 (PEB!BeingDebugged 覆盖)

# 逆向工程 — 第五课：软件断点 + 远程内存

## 核心能力
通过 Windows Debug API 完整实现了：
1. ✅ 以 DEBUG_PROCESS 标志启动目标进程
2. ✅ 通过 ctypes Structure 正确解析调试事件
3. ✅ 远程内存读写 (ReadProcessMemory / WriteProcessMemory)
4. ✅ 内存保护属性修改 (VirtualProtectEx)
5. ✅ 指令缓存刷新 (FlushInstructionCache)
6. ✅ 软件断点设置 (0xCC / INT3)

## 验证结果
```
python re_05_bp_full.py
→ CREATE_PROCESS: notepad.exe base=0x7ff7b39a0000
→ DOS: MZ OK (e_lfanew=0xf8)
→ PE: signature OK
→ .text: 开头是 cc cc cc cc 4c 8b dc ... (MSVC hotpatch int3)
→ BP set @ base+0x1000
→ 断点捕获: ntdll!DbgBreakPoint → 调试循环正常工作
```

## 关键发现

### MSVC Hotpatch Preamble
现代 MSVC 在每个函数入口前插入 5 个 `0xCC` 字节：
```
cc cc cc cc cc | 4c 8b dc 48 81 ec 88 00 00 00 ...
^ hotpatch    ^ 实际入口 (mov rsp, rsp; sub rsp, ...)
```
这是为 Windows 热补丁（Hotpatch）预留的，可以在运行时替换函数实现。

### 断点执行流程
```
DebugActiveProcess → ntdld!DbgBreakPoint (int3)
                  → Windows 调度 → 触发 EXCEPTION_DEBUG_EVENT
                  → 我们的调试器捕获
                  → ContinueDebugEvent(DBG_CONTINUE) → 恢复
```

如果设0xCC在已有0xCC的位置，breakpoint在单步执行时只命中ntdll的断点，
因为CPU在遇到0xCC时触发异常，而异常处理会寻找最近的异常处理器。

## 技术笔记
- `WaitForDebugEvent` timeout=100ms 用于非阻塞 polling
- `VirtualProtectEx` 需要 `PROCESS_VM_OPERATION` 权限
- `FlushInstructionCache` 在修改代码段后必须调用
- x64 下 `CreateProcess` 的 `creationflags=0x00000001` = `DEBUG_PROCESS`
- 被调试进程需要 `DebugSetProcessKillOnExit(True/False)` 控制退出行为

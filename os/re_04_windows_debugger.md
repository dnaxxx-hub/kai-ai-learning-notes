# 逆向工程 — 第四课：Windows Debug API 调试器

## 核心成果
用纯 Python + ctypes 实现了一个最小调试器，可以：
- Attach 到运行中的外部进程
- 捕获所有 Debug Event
- 区分 EXCEPTION_BREAKPOINT / SINGLE_STEP / ACCESS_VIOLATION
- 读取线程上下文（寄存器状态）
- 控制调试循环继续或终止

## 验证结果
```
Python MiniDebugger → Attach → notepad.exe (PID 20960)
  ↓
WaitForDebugEvent → CREATE_PROCESS (base=0x7ff62ccb0000)
                  → EXCEPTION (ntdll!DbgBreakPoint @ 0x7ff8e2dc0ae0)
```

## 关键技术点

### Windows Debug API 核心函数
```
DebugActiveProcess(pid)    → 成为进程的调试器
WaitForDebugEvent(&event)  → 阻塞等待调试事件
ContinueDebugEvent(pid, tid, flag) → 恢复进程执行
DBG_CONTINUE               → 异常已处理
DBG_EXCEPTION_NOT_HANDLED  → 交给进程处理
```

### Breakpoint 机制
当 DebugActiveProcess 时，Windows 自动在被调试进程的第一个线程入口点
插入 int 3 断点。这就是为什么 attach 后立即收到 BREAKPOINT 事件。

### 寄存器转储问题
GetThreadContext 需要进程挂起状态或特定权限。
实际调试器会在断点后自动挂起线程，我们的简易版没有做。

## 下一步 (re_05)
- 软件断点 (替换字节为 0xCC)
- 硬件断点 (DR0-DR3 寄存器)
- 单步跟踪 (EFLAGS.TF)
- 内存读写

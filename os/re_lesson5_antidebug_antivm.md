# 第5课：反调试/反虚拟化技术

## 一、反调试技术总览

### 1.1 反调试检测原理
```
应用程序 (Ring3)
├── API 层检测       → PEB.BeingDebugged, NtQueryInformationProcess
├── 时间检测         → rdtsc, GetTickCount, QueryPerformanceCounter
├── 异常检测         → ZwQueryInformationThread, 异常处理链
├── 断点检测         → 软件断点(0xCC), 硬件断点(DR寄存器)
├── 代码完整性检测   → CRC校验, checksum比较
└── 调试器检测       → 窗口类名, 进程名, 调试特权

内核 (Ring0)
├── SSDT 钩子检测
├── KI_USER_SHARED_DATA
├── NtGlobalFlag
└── KdDebuggerEnabled
```

---

## 二、经典反调试技术 & 对抗

### 2.1 IsDebuggerPresent (PEB.BeingDebugged)

**检测代码:**
```c
// Windows API (最基础)
BOOL IsDebugged() {
    return IsDebuggerPresent();
}

// 手动实现（不调用 API，更难 hook）
BOOL IsDebugged_Manual() {
#ifdef _WIN64
    return *(BYTE*)(__readgsqword(0x60) + 2);  // PEB.BeingDebugged
#else
    return *(BYTE*)(__readfsdword(0x30) + 2);  // PEB.BeingDebugged
#endif
}

// 更隐蔽的方式
BOOL IsDebugged_NtDll() {
    HMODULE hNtdll = GetModuleHandleA("ntdll.dll");
    FARPROC pFunc = GetProcAddress(hNtdll, "NtQueryInformationProcess");
    // ... 调用 NtQueryInformationProcess
    return FALSE;
}
```

**绕过方法:**
1. **x64dbg ScyllaHide:** 自动清理 PEB 标志位
2. **手动修改:** 找到 `[PEB+2]` 字节设为 0
3. **NOP 修补:** 将 `IsDebuggerPresent` 调用 patch 为 `xor eax,eax; ret`

### 2.2 NtQueryInformationProcess

**检测代码:**
```c
typedef NTSTATUS (NTAPI* pNtQueryInformationProcess)(
    HANDLE ProcessHandle,
    PROCESSINFOCLASS ProcessInformationClass,
    PVOID ProcessInformation,
    ULONG ProcessInformationLength,
    PULONG ReturnLength
);

#define ProcessDebugPort 7
#define ProcessDebugObjectHandle 30
#define ProcessDebugFlags 31

BOOL CheckDebugPort() {
    pNtQueryInformationProcess NtQueryInfo = (pNtQueryInformationProcess)
        GetProcAddress(GetModuleHandleA("ntdll.dll"), "NtQueryInformationProcess");

    DWORD debugPort = 0;
    NTSTATUS status = NtQueryInfo(
        GetCurrentProcess(),
        (PROCESSINFOCLASS)ProcessDebugPort,  // 7
        &debugPort,
        sizeof(debugPort),
        NULL
    );
    return (debugPort != 0);  // 非0表示被调试
}

BOOL CheckDebugObject() {
    HANDLE hDebugObject = NULL;
    NtQueryInformationProcess(
        GetCurrentProcess(),
        (PROCESSINFOCLASS)ProcessDebugObjectHandle,  // 30
        &hDebugObject,
        sizeof(HANDLE),
        NULL
    );
    return (hDebugObject != NULL);
}

BOOL CheckDebugFlags() {
    LONG flags = 0;
    NtQueryInformationProcess(
        GetCurrentProcess(),
        (PROCESSINFOCLASS)ProcessDebugFlags,  // 31
        &flags,
        sizeof(flags),
        NULL
    );
    return (flags != 1);  // 1 = 无调试器
}
```

### 2.3 NtGlobalFlag 检测

```c
BOOL CheckNtGlobalFlag() {
#ifdef _WIN64
    DWORD offset = __readgsdword(0x60);  // PEB
#else
    DWORD offset = __readfsdword(0x30);  // PEB
#endif

    // PEB.BeingDebugged
    if (*(BYTE*)(offset + 2)) return TRUE;

    // PEB.NtGlobalFlag (偏移 0xBC x86, 0xBC x64)
    DWORD ntGlobalFlag = *(DWORD*)(offset + 0xBC);
    
    // 调试器设置的标志
    const DWORD FLG_HEAP_ENABLE_TAIL_CHECK    = 0x10;
    const DWORD FLG_HEAP_ENABLE_FREE_CHECK    = 0x20;
    const DWORD FLG_HEAP_VALIDATE_PARAMETERS  = 0x40;
    const DWORD debugFlags = FLG_HEAP_ENABLE_TAIL_CHECK |
                             FLG_HEAP_ENABLE_FREE_CHECK |
                             FLG_HEAP_VALIDATE_PARAMETERS;

    return ((ntGlobalFlag & debugFlags) == debugFlags);
}
```

### 2.4 堆标志检测

```c
BOOL CheckHeapFlags() {
    // PEB.ProcessHeap (偏移 0x18 x86, 0x30 x64)
    HANDLE hHeap;
#ifdef _WIN64
    hHeap = (HANDLE)__readgsqword(0x60 + 0x30);
    // 从 ProcessHeaps 列表检查
    DWORD flags = *(DWORD*)((ULONG_PTR)hHeap + 0x70);  // x64 Flags 偏移
#else
    hHeap = (HANDLE)__readfsdword(0x30 + 0x18);
    DWORD flags = *(DWORD*)((ULONG_PTR)hHeap + 0x0C);  // x86 Flags 偏移
#endif
    return ((flags & 2) != 0);  // HEAP_GROWABLE 未设置时表示被调试
}
```

---

## 三、时间差检测

### 3.1 rdtsc 指令检测 (Ring3 + Ring0)

```c
#include <intrin.h>

BOOL CheckRDTSCTiming() {
    // 方法1: 直接测量性能
    ULARGE_INTEGER start, end;
    int junk;
    
    start.QuadPart = __rdtscp(&junk);
    // 执行一些简单操作
    __cpuid((int*)junk, 0);
    end.QuadPart = __rdtscp(&junk);
    
    // 如果时间差过大，可能被调试器单步执行
    return ((end.QuadPart - start.QuadPart) > 0xFFF);
}

BOOL CheckTiming_API() {
    DWORD startTick = GetTickCount();
    Sleep(200);                           // 等待200ms
    DWORD endTick = GetTickCount();
    
    // 实际经过的时间应该 >= 200ms
    // 如果远大于200ms，可能在debugger单步跟踪
    return ((endTick - startTick) > 500);
}

BOOL CheckPerformanceCounter() {
    LARGE_INTEGER freq, start, end;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&start);
    
    Sleep(100);
    
    QueryPerformanceCounter(&end);
    double elapsed = (end.QuadPart - start.QuadPart) * 1000.0 / freq.QuadPart;
    
    // 异常的时间差 = 被调试
    return (elapsed > 500.0);
}
```

### 3.2 中断指令异常检测 (INT 3 / INT 2D)

```c
#include <signal.h>

// 异常处理函数（检测断点是否被移除）
static LONG WINAPI Int3Handler(EXCEPTION_POINTERS* ExceptionInfo) {
    if (ExceptionInfo->ExceptionRecord->ExceptionCode == STATUS_BREAKPOINT) {
        // 检查是否正确触发
        ExceptionInfo->ContextRecord->Eip++;
        return EXCEPTION_CONTINUE_EXECUTION;
    }
    return EXCEPTION_CONTINUE_SEARCH;
}

BOOL CheckInt3() {
    AddVectoredExceptionHandler(1, Int3Handler);
    
    __try {
        __debugbreak();  // 触发 INT 3
        // 如果能到这里，说明调试器处理了异常（跳过了）
        // ==> 被调试!
        RemoveVectoredExceptionHandler(Int3Handler);
        return TRUE;
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        // 没被调试，我们自己处理了异常
        RemoveVectoredExceptionHandler(Int3Handler);
        return FALSE;
    }
}

// INT 2D 检测 (x86 only)
__declspec(naked) BOOL CheckInt2D() {
    __asm {
        push ebp
        mov ebp, esp
        xor eax, eax
        
        __asm __emit 0xF4  // HLT 指令代替 INT 2D（效果类似）
        
        // 如果调试器处理了异常，会继续到这里
        // ==> 没被调试
        mov eax, 0
        pop ebp
        ret
        
        // 如果没人处理异常，系统会 crash
        // 实际使用需配合 SEH
    }
}
```

---

## 四、硬件断点检测 (DR寄存器)

```c
// 检查调试寄存器
BOOL CheckHardwareBreakpoints() {
    CONTEXT ctx = {0};
    ctx.ContextFlags = CONTEXT_DEBUG_REGISTERS;
    
    if (GetThreadContext(GetCurrentThread(), &ctx)) {
        // 检查 DR0-DR3
        if (ctx.Dr0 != 0 || ctx.Dr1 != 0 || ctx.Dr2 != 0 || ctx.Dr3 != 0)
            return TRUE;
        // 检查 DR6 (DR6 低位表示已触发的硬件断点)
        if (ctx.Dr6 & 0x0F)
            return TRUE;
    }
    return FALSE;
}

// 手动读取 DR 寄存器 (Ring0 下)
BOOL ReadDebugRegisters() {
    CONTEXT ctx;
    ctx.ContextFlags = CONTEXT_DEBUG_REGISTERS;
    RtlCaptureContext(&ctx);
    
    // 任何非零的 DR0-DR3 都表示有硬件断点
    return ctx.Dr0 || ctx.Dr1 || ctx.Dr2 || ctx.Dr3;
}
```

---

## 五、软件断点检测 (0xCC)

```c
// 方法1: 校验函数入口
BOOL CheckCodePatch(const char* funcAddr, BYTE originalByte) {
    // 0xCC = INT 3 断点
    // 0xEB = JMP 短跳转
    // 0xE9 = JMP 长跳转
    // 0x90 = NOP
    BYTE firstByte = *(BYTE*)funcAddr;
    return firstByte == 0xCC;
}

// 方法2: 计算校验和
DWORD CalculateChecksum(PBYTE addr, DWORD size) {
    DWORD sum = 0;
    for (DWORD i = 0; i < size; i++) {
        sum += addr[i];
    }
    return sum;
}

// 方法3: 反调试 + 代码完整性
BOOL CheckIntegrity() {
    static DWORD baseChecksum = 0;
    HMODULE hMod = GetModuleHandle(NULL);
    PIMAGE_DOS_HEADER dos = (PIMAGE_DOS_HEADER)hMod;
    PIMAGE_NT_HEADERS nt = (PIMAGE_NT_HEADERS)((BYTE*)hMod + dos->e_lfanew);
    
    // 校验代码段
    IMAGE_SECTION_HEADER* sections = IMAGE_FIRST_SECTION(nt);
    for (int i = 0; i < nt->FileHeader.NumberOfSections; i++) {
        if (sections[i].Characteristics & IMAGE_SCN_MEM_EXECUTE) {
            DWORD current = CalculateChecksum(
                (PBYTE)hMod + sections[i].VirtualAddress,
                sections[i].SizeOfRawData
            );
            if (current != baseChecksum) {
                return FALSE;  // 代码被修改!
            }
        }
    }
    return TRUE;
}
```

---

## 六、反虚拟化技术

### 6.1 VirtualBox 检测

```c
// 注册表检测
BOOL CheckVirtualBoxRegistry() {
    HKEY hKey;
    // VBoxGuest 驱动
    if (RegOpenKeyEx(HKEY_LOCAL_MACHINE,
        "HARDWARE\\DEVICEMAP\\Scsi\\Scsi Port 0\\Scsi Bus 0\\Target Id 0\\Logical Unit Id 0",
        0, KEY_READ, &hKey) == ERROR_SUCCESS) {
        char buffer[256] = {0};
        DWORD size = sizeof(buffer);
        RegQueryValueEx(hKey, "Identifier", NULL, NULL, (LPBYTE)buffer, &size);
        RegCloseKey(hKey);
        if (strstr(buffer, "VBOX")) return TRUE;
    }
    return FALSE;
}

BOOL CheckVirtualBoxProcesses() {
    HANDLE hSnap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    PROCESSENTRY32 pe = { sizeof(PROCESSENTRY32) };
    Process32First(hSnap, &pe);
    do {
        if (_stricmp(pe.szExeFile, "VBoxService.exe") == 0 ||
            _stricmp(pe.szExeFile, "VBoxTray.exe") == 0) {
            CloseHandle(hSnap);
            return TRUE;
        }
    } while (Process32Next(hSnap, &pe));
    CloseHandle(hSnap);
    return FALSE;
}

// 检测 VBox 硬件设备
BOOL CheckVirtualBoxDevices() {
    // 检查系统设备中是否有 VBox 相关
    HKEY hKey;
    if (RegOpenKeyEx(HKEY_LOCAL_MACHINE,
        "SYSTEM\\CurrentControlSet\\Enum\\PCI", 0, KEY_READ, &hKey) == ERROR_SUCCESS) {
        // 枚举子键，查找 VEN_80EE (VirtualBox)
        // ...
        RegCloseKey(hKey);
    }
    return FALSE;
}
```

### 6.2 VMware 检测

```c
// VMware I/O 端口检测 (经典)
BOOL CheckVMwareBackdoor() {
    __try {
        __asm {
            mov eax, 'VMXh'       // VMware magic
            mov ebx, 0            // 任意值
            mov ecx, 0xA          // 获取 VMware 版本
            mov edx, 'VX'         // 端口
            in eax, dx            // !!! 关键: IN 指令
            // 如果在 VMware 上运行，ebx 返回 'VMXx'
            // 如果是物理机，触发异常
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        return FALSE;  // 物理机
    }
    return TRUE;  // VMware
}

// x64 版本（64位不支持 __asm，使用 __writemsr 或其他方式）
BOOL CheckVMwareRegKeys() {
    HKEY hKey;
    if (RegOpenKeyEx(HKEY_LOCAL_MACHINE,
        "SOFTWARE\\VMware, Inc.\\VMware Tools",
        0, KEY_READ, &hKey) == ERROR_SUCCESS) {
        RegCloseKey(hKey);
        return TRUE;
    }
    return FALSE;
}
```

### 6.3 CPUID 指令检测

```c
#include <intrin.h>

int __cpuidex(int info[4], int function_id, int subfunction_id) {
    __cpuidex(info, function_id, subfunction_id);
    return 0;
}

BOOL CheckHypervisorCPUID() {
    int cpuInfo[4] = {0};
    __cpuid(cpuInfo, 1);
    
    // ECX bit 31 = Hypervisor Present
    if (cpuInfo[2] & (1 << 31)) {
        // 进一步检测是哪种虚拟机
        char vendor[13] = {0};
        __cpuid(cpuInfo, 0x40000000);
        memcpy(vendor, &cpuInfo[1], 4);
        memcpy(vendor + 4, &cpuInfo[2], 4);
        memcpy(vendor + 8, &cpuInfo[3], 4);
        
        if (strstr(vendor, "Microsoft Hv"))    // Hyper-V
            return TRUE;
        if (strstr(vendor, "VMwareVMware"))     // VMware
            return TRUE;
        if (strstr(vendor, "VBoxVBoxVBox"))     // VirtualBox
            return TRUE;
        if (strstr(vendor, "KVMKVMKVM"))        // KVM
            return TRUE;
        // 其他: "XenVMMXenVMM", "prl hyperv" (Parallels)
    }
    return FALSE;
}

// 检测是否在 Wine 中运行
BOOL CheckWine() {
    // wine_get_version() 是 Wine 特有的导出函数
    HMODULE hNtdll = GetModuleHandleA("ntdll.dll");
    FARPROC wineBuild = GetProcAddress(hNtdll, "wine_build_id");
    return (wineBuild != NULL);
}

// 检测虚拟 MAC 地址前缀
BOOL CheckVMwareMAC(PBYTE mac) {
    const BYTE vmwarePrefixes[][3] = {
        {0x00, 0x05, 0x69},
        {0x00, 0x0C, 0x29},
        {0x00, 0x1C, 0x14},
        {0x00, 0x50, 0x56}
    };
    for (int i = 0; i < sizeof(vmwarePrefixes) / 3; i++) {
        if (memcmp(mac, vmwarePrefixes[i], 3) == 0)
            return TRUE;
    }
    return FALSE;
}
```

### 6.4 反沙箱技术

```c
// 检测通用沙箱特征
BOOL CheckSandbox() {
    // 1. 检查磁盘大小 (沙箱通常 < 60GB)
    ULARGE_INTEGER freeBytes, totalBytes;
    GetDiskFreeSpaceEx("C:\\", &freeBytes, &totalBytes, NULL);
    if (totalBytes.QuadPart < 60LL * 1024 * 1024 * 1024)
        return TRUE;
    
    // 2. 检查内存大小 (沙箱通常 < 4GB)
    MEMORYSTATUSEX mem = { sizeof(MEMORYSTATUSEX) };
    GlobalMemoryStatusEx(&mem);
    if (mem.ullTotalPhys < 2048LL * 1024 * 1024)  // < 2GB
        return TRUE;
    
    // 3. 检查最近修改的文件数量太少
    // ... (沙箱文件少)
    
    // 4. 检查用户名
    char username[256];
    DWORD size = sizeof(username);
    GetUserNameA(username, &size);
    if (strstr(username, "admin") || 
        strstr(username, "sandbox") ||
        strstr(username, "malware") ||
        strstr(username, "virus"))
        return TRUE;
    
    // 5. 检查显示分辨率（沙箱往往 1024x768）
    int screenX = GetSystemMetrics(SM_CXSCREEN);
    int screenY = GetSystemMetrics(SM_CYSCREEN);
    if (screenX <= 1024 && screenY <= 768)
        return TRUE;
    
    return FALSE;
}
```

---

## 七、TLS 回调反调试

```c
// TLS 回调在程序入口点之前执行
// 用于在调试器附加前执行反检测

#pragma comment(linker, "/INCLUDE:__tls_used")

VOID NTAPI TLSCallback(PVOID DllHandle, DWORD Reason, PVOID Reserved) {
    if (Reason == DLL_PROCESS_ATTACH) {
        // 在 main() 之前运行反调试检查
        if (IsDebuggerPresent()) {
            MessageBox(NULL, "调试器检测到!", "Error", MB_OK | MB_ICONERROR);
            ExitProcess(-1);
        }
    }
}

// 注册 TLS 回调
#pragma data_seg(".CRT$XLX")
PIMAGE_TLS_CALLBACK pTLS_CALLBACKS[] = { TLSCallback, NULL };
#pragma data_seg()
```

---

## 八、对抗技术总结

| 反调试技术 | 检测方法 | 绕过工具/方法 |
|-----------|---------|--------------|
| `IsDebuggerPresent` | PEB+2 | ScyllaHide, 手动patch |
| `NtQueryInfoProcess` | API监控 | 驱动级别hook, ScyllaHide |
| `NtGlobalFlag` | PEB偏移 | ScyllaHide, 手动清除标志 |
| `rdtsc` 时间差 | CPU周期 | 断点跳过, 修改返回 |
| `0xCC` 校验 | 代码CRC | 调试点跳过, 原值恢复 |
| DR 寄存器 | 硬件断点 | 清空DR0-DR3 |
| INT 2D/INT 3 | 异常 | 异常处理绕过 |
| VirtualBox 检测 | 多种特征 | 修改虚拟机配置 |
| VMware 检测 | I/O端口 | 修改 .vmx 配置 |
| CPUID 检测 | hypervisor位 | 硬件虚拟化VT-x |
| TLS 回调 | 入口点之前 | 断点拦截TLS |

---

## 九、配套代码项目

详见配套代码项目:
- `projects/arch_reverse/lesson5_antidebug/antidebug_detector.py` — 反调试检测扫描器
- `projects/arch_reverse/lesson5_antidebug/antidebug_c_demo.c` — C语言反调试示例

---

## 参考资料
- [The "Ultimate" Anti-Debugging Reference (Peter Ferrie)](https://anti-debug.checkpoint.com/)
- [Anti Debugging Techniques (Sudeep Singh)](https://www.codeproject.com/Articles/894781/Anti-Debugging-Techniques)
- [Uninformed Research: Anti-Debug](http://uninformed.org/)
- [x64dbg ScyllaHide](https://github.com/x64dbg/ScyllaHide)

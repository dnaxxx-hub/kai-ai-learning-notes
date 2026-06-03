# 第10课：系统编程

## 1. syscall 调用链：应用 → libc → 内核 → 返回

```
以 read() 系统调用为例：

┌──────────────────────────────────────────────────────────┐
│                    用户空间 (ring 3)                       │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  应用代码:                                                │
│  ┌────────────────────────────────────┐                  │
│  │ char buf[1024];                    │                  │
│  │ int n = read(fd, buf, 1024);       │  ← 应用程序调用  │
│  │ printf("read %d bytes\n", n);      │                  │
│  └──────────────────┬─────────────────┘                  │
│                     │                                     │
│                     ▼                                     │
│  ┌────────────────────────────────────┐                  │
│  │ libc (glibc/musl):                │                  │
│  │ read() wrapper function            │  ← C库封装       │
│  │ 1. 准备参数:                         │                  │
│  │    RDI = fd, RSI = buf, RDX = 1024 │                  │
│  │ 2. 设置 syscall number:             │                  │
│  │    RAX = __NR_read (0)             │                  │
│  │ 3. 执行 syscall 指令 ↴              │                  │
│  └──────────────────┬─────────────────┘                  │
│                     │                                     │
└─────────────────────┼────────────────────────────────────┘
                      │  syscall 指令 (CPU 特权级切换)
                      ▼
┌──────────────────────────────────────────────────────────┐
│                    内核空间 (ring 0)                       │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  入口: entry_SYSCALL_64 (arch/x86/entry/entry_64.S)      │
│  ┌────────────────────────────────────┐                  │
│  │ 1. 保存用户态寄存器 (pt_regs)       │                  │
│  │ 2. 切换内核栈                       │                  │
│  │ 3. 按 RAX 查 sys_call_table[]      │                  │
│  │    调用 sys_read()                  │                  │
│  └──────────────────┬─────────────────┘                  │
│                     ▼                                     │
│  ┌────────────────────────────────────┐                  │
│  │ sys_read() (fs/read_write.c)       │                  │
│  │ 1. fget(fd) → 获取 file 结构指针    │                  │
│  │ 2. file->f_op->read() → VFS 调用    │                  │
│  │ 3. 驱动层 read → copy_to_user()    │                  │
│  │ 4. 返回实际读取字节数               │                  │
│  └──────────────────┬─────────────────┘                  │
│                     ▼                                     │
│  ┌────────────────────────────────────┐                  │
│  │ 返回路径:                           │                  │
│  │ 1. RAX = 返回值 (读取字节数)         │                  │
│  │ 2. 恢复用户态寄存器                  │                  │
│  │ 3. sysretq 指令返回 ring 3          │                  │
│  └────────────────────────────────────┘                  │
│                                                          │
└──────────────────────────────────────────────────────────┘
                      │  sysret 指令
                      ▼
┌──────────────────────────────────────────────────────────┐
│                    用户空间 (ring 3)                       │
├──────────────────────────────────────────────────────────┤
│  libc:                                                    │
│  1. 检查返回值（错误时设置 errno）                          │
│  2. return 给应用程序                                     │
│                                                          │
│  应用: n = read(...) 得到实际数据                          │
└──────────────────────────────────────────────────────────┘

时间线:
  应用 → [0.1μs] → libc → [0.01μs] → syscall指令 → [~0.5-3μs] → 内核处理 → [~0.01μs] → sysret → 返回
  整个 read 耗时 ≈ 1~10μs (取决于是否反复进出)
```

## 2. x64 syscall 指令

```
用户态进入内核态有两种方式:
  ┌─────────────────────┬─────────────────────────────────┐
  │ 传统 int 0x80 (32位) │ 现代 syscall/sysret (64位)      │
  ├─────────────────────┼─────────────────────────────────┤
  │ 中断门               │ 专用指令                         │
  │ ~2μs 切换           │ ~0.1μs 切换                      │
  │ 慢（查 IDT）         │ 快（MSR 直接跳转）                │
  │ 兼容遗留             │ 默认 (Linux x64)                 │
  └─────────────────────┴─────────────────────────────────┘
```

### syscall 调用约定

```
调用前 (用户态):
  RAX = 系统调用号      (e.g. 0=read, 1=write, 2=open)
  RDI = 第1个参数       (e.g. fd)
  RSI = 第2个参数       (e.g. buf)
  RDX = 第3个参数       (e.g. count)
  R10 = 第4个参数       (注意: 不是 RCX, syscall 会覆盖 RCX)
  R8  = 第5个参数
  R9  = 第6个参数

执行:
  syscall     ← CPU 自动将 RIP → MSR(LSTAR), RFLAGS → R11
                    设置 CS/SS 为内核段, 跳转到 entry_SYSCALL_64

返回:
  RAX = 返回值 (正数=成功, 负数=错误码, libc 转成 errno)

  sysretq     ← CPU 恢复用户态 CS/SS, 从 R11 恢复 RFLAGS
```

### 常用 syscall 表

```
      系统调用号       名称      功能              参数
      ─────────       ────      ────              ────
x64:   0              read     读取文件           fd, buf, count
x64:   1              write    写入文件           fd, buf, count
x64:   2              open     打开文件           pathname, flags, mode
x64:   3              close    关闭文件           fd
x64:   9              mmap     内存映射           addr, length, prot, flags, fd, offset
x64:  57              fork     创建进程           (无参数)
x64:  59              execve   执行程序           filename, argv, envp
x64:  60              exit     退出进程           error_code
x64:  62              kill     发送信号           pid, sig
x64:  63              uname    获取系统信息       buf
x64:  72              fcntl    文件控制           fd, cmd, ...
```

## 3. 常见 syscall 详解

### open → read → write → close

```
应用层:  int fd = open("test.txt", O_RDWR | O_CREAT, 0644);
                ↕
syscall:  sys_openat(AT_FDCWD, "test.txt", O_RDWR|O_CREAT, 0644)
内核:      do_sys_openat2() → get_unused_fd()
           → do_filp_open() → path_openat() → lookup_open()
           → vfs_open() → dentry_open() → 调用文件系统
           → fd_install(fd, file) → 返回 fd
                ↕
应用层:  int n = write(fd, "hello", 5);
                ↕
syscall:  sys_write(fd, "hello", 5)
内核:      ksys_write() → fdget_pos() → file->f_op->write_iter()
           → 驱动层/文件系统实现 → vfs_write()
                ↕
应用层:  n = read(fd, buf, 5);
                ↕
syscall:  sys_read(fd, buf, 5)
内核:      ksys_read() → fdget_pos() → file->f_op->read_iter()
           → 实现层 → copy_to_user()
                ↕
应用层:  close(fd);
                ↕
syscall:  sys_close(fd)
内核:      filp_close() → fput() → 释放资源
```

### fork

```
应用:  pid_t pid = fork();
                      ↕
syscall:  sys_clone(NULL, 0, NULL, NULL, 0)  ← fork 实际调用 clone
                      ↕
内核:  内核栈:
       1. dup_task_struct() → 复制进程描述符
       2. copy_process() → 复制内存、文件描述符、信号等
       3. 分配新 PID
       4. 子进程放入就绪队列
       5. 返回: 父进程 → 子PID, 子进程 → 0
                      ↕
应用:  if (pid == 0) { /* 子进程 */ }
       else           { /* 父进程 */ }
```

### execve

```
应用:  execve("/bin/ls", ["ls", "-l"], envp);
                      ↕
syscall:  sys_execve("/bin/ls", argv, envp)
                      ↕
内核:  1. do_execveat_common() → open_exec() → 打开可执行文件
       2. load_elf_binary() → 解析 ELF 头
       3. setup_new_exec() → 清空旧内存映射
       4. load_elf_interp() → 加载动态链接器 ld.so
       5. start_thread(new_ip = ELF入口, new_sp) → 设置新 RIP/RSP
                      ↕
应用:  /bin/ls 运行起来（完全替换了旧的进程映像）
```

### mmap

```
应用:  void *p = mmap(NULL, 4096, PROT_READ|PROT_WRITE,
                      MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
                      ↕
syscall:  sys_mmap(0, 4096, PROT_READ|PROT_WRITE,
                   MAP_PRIVATE|MAP_ANONYMOUS, -1, 0)
                      ↕
内核:  do_mmap() → get_unmapped_area() → find VMA gap
       → mmap_region() → 创建 vm_area_struct
       → 匿名 (缺页时分配物理页)
       → 文件: 调用 file->f_op->mmap() → 建立页表映射
       → 返回虚拟地址
```

## 4. strace 用法示例分析

```bash
# ──────── 基本用法 ────────

# 跟踪一个命令的所有 syscall
$ strace ls -l
execve("/bin/ls", ["ls", "-l"], [/* 28 vars */]) = 0
brk(NULL)                               = 0x555555554000
access("/etc/ld.so.preload", R_OK)      = -1 ENOENT
openat(AT_FDCWD, "/etc/ld.so.cache", O_RDONLY|O_CLOEXEC) = 3
fstat(3, {st_mode=S_IFREG|0644, ...})   = 0
mmap(NULL, 124220, PROT_READ, MAP_PRIVATE, 3, 0) = 0x7f...
close(3)                                = 0
...
# ────────── 常用选项 ──────────

# 统计 syscall 调用次数和耗时
$ strace -c ls -l
% time     seconds  usecs/call     calls    errors syscall
------ ----------- ----------- --------- --------- ----------------
 34.21    0.000120           7        17           newfstatat
 15.67    0.000055           7         8           read
 10.26    0.000036           6         6           mmap
  ...      ...              ...       ...         ...

# 跟踪特定 syscall (过滤)
$ strace -e trace=openat,read,write ls
openat(AT_FDCWD, ".", O_RDONLY|O_NONBLOCK|O_DIRECTORY|...)=3
...

# 显示时间戳
$ strace -t ls              # 绝对时间
$ strace -ttt ls            # 微秒级 Unix 时间戳
$ strace -r ls              # 相对时间 (syscall间耗时)

# 跟踪网络相关
$ strace -e trace=network curl http://example.com

# 跟踪子进程 (多进程程序)
$ strace -f bash -c "ls && pwd"

# 显示参数详情
$ strace -v ls              # 展开结构体

# 打印字符串最大长度
$ strace -s 256 readelf -h a.out

# ────────── 实战分析 ──────────
# 跟踪 cat hello.txt
$ strace cat hello.txt
execve("/bin/cat", ["cat", "hello.txt"], [/* ... */]) = 0   # 1. 启动
brk(NULL)                 = 0x...                            # 2. 堆初始化
openat(AT_FDCWD, "hello.txt", O_RDONLY) = 3                 # 3. 打开文件 (fd=3)
read(3, "Hello, World!\n", 131072)       = 14               # 4. 读取 14 字节
write(1, "Hello, World!\n", 14)          = 14               # 5. 写入 stdout
read(3, "", 131072)                      = 0                # 6. 读完了(EOF)
close(3)                                  = 0                # 7. 关闭文件

# ────────── 调试技巧 ──────────
$ strace -o trace.log ./program          # 输出到文件
$ strace -p 1234                         # 附加到运行中的进程
$ strace -e fault=read:error=EIO:when=3  # 模拟第3次read出错
$ strace -e trace=signal                 # 只跟踪信号
$ strace -e trace=desc                   # 只跟踪文件描述符操作
```

## 总结

```
syscall = 用户态 → 内核态的唯一合法入口

调用链: 应用 → libc (参数包装) → syscall指令 → 内核处理 → 返回

关键点:
① syscall 和函数调用的区别：特权级切换 + 查表分发
② libc 透明处理：用户写 read() 和写普通函数一样
③ errno 机制：内核返回负值 → libc 转为正数 errno
④ strace 是用户态视角的最佳调试工具
```

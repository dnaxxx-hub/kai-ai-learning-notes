# 沙箱逃逸

## Seccomp-BPF

Seccomp (Secure Computing Mode) 限制进程可用的系统调用。通过 BPF (Berkeley Packet Filter) 规则过滤 syscall。

### 配置方式

```c
// prctl 方式（简单）
prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &prog);

// seccomp() 系统调用（推荐，Linux 3.17+）
struct sock_fprog prog = { .len = len, .filter = filter };
seccomp(SECCOMP_SET_MODE_FILTER, SECCOMP_FILTER_FLAG_LOG, &prog);

// libseccomp 高级 API
scmp_filter_ctx ctx = seccomp_init(SCMP_ACT_KILL);
seccomp_rule_add(ctx, SCMP_ACT_ALLOW, SCMP_SYS(open), 0);
seccomp_load(ctx);
```

### 规则示例

```bash
# 只允许 read/write/exit
# 禁止 execve/open/fork
# CTF 中常见沙箱: 开放 ORW (open-read-write)，禁 SHELL
seccomp-tools dump ./binary  # seccomp-tools 查看规则
```

### 绕过

- **利用已打开的 fd**: 沙箱禁 open 但 fd 0/1/2 保持打开
- **ORW shellcode**: 只许 read/write 时，写 open→read→write 链读 flag 文件
- **x32 模式**: 32-bit syscall 号不同（如 32-bit open=5，64-bit open=2），沙箱可能只过滤了 native 调用
- **retf 切换模式**: 通过 retf 切到 32-bit 代码段绕过 64-bit 只过滤

## Chroot / Jail 突破

chroot 将进程根目录限制在指定目录，**但并非完整隔离**。

```c
chroot("/tmp/jail");
chdir("/");         // 必须！
```

### 突破方法

- **`chdir("..")` 逃逸**: 未调用 `chdir("/")` 时，可通过 `chdir("../../../")` 逃出根目录

```c
mkdir("escape"); chroot("escape"); chdir("../../..");
// → 现在 chroot 在 escape，但 cwd 在主系统根目录
// → 通过 open("../..") 访问主系统文件
```

- **保留 fd**: chroot 前打开的 fd 仍然引用原文件系统，可 `fchdir(fd)` 逃逸
- **clone 新 namespace**: 创建新 mount namespace 后直接 unmount 根目
- **`/proc/1/root`**: 通过 `/proc/1/root/` 访问宿主文件系统（需 procfs 挂载）

## Namespace 隔离限制

Linux namespace 将全局资源隔离开：

| Namespace | 隔离资源 | 突破思路 |
|-----------|---------|---------|
| **mount** | 文件系统挂载点 | unshare + pivot_root 逃逸 |
| **net** | 网络栈 | 通过 /proc 访问宿主 netns |
| **pid** | 进程 ID | 挂载 /proc 后查看宿主进程 |
| **user** | UID/GID | 用户 namespace 可嵌套 |
| **uts** | 主机名 | 信息隔离，难利用 |

**典型 bypass**: 挂载宿主的 `/proc` → 写入 `/proc/1/root` 执行任意文件。

## Docker 逃逸

### CVE-2019-5736（runC 逃逸）

**原理**: 攻击者覆盖容器内的 `/proc/self/exe`（指向宿主机 runC 可执行文件），容器内修改该文件 → 宿主下次执行 `docker exec` 时触发恶意代码。

**条件**: 宿主机 runC < 1.0-rc6，攻击者有容器内 root 权限。

### --privileged 提权

`docker run --privileged` 赋予容器所有能力（capabilities），包括：
- `CAP_SYS_ADMIN`: 挂载、namespace 操作
- `CAP_NET_ADMIN`: 修改网络
- 访问宿主设备（/dev/sda 等）

**逃逸**:
```bash
# 挂载宿主根目录
mount /dev/sda1 /mnt
chroot /mnt && cat /etc/shadow

# 写 SSH key
echo "ssh-rsa AAA..." >> /mnt/root/.ssh/authorized_keys
```

### /proc/1/root 逃逸

```bash
# 宿主机进程 /proc/1 在容器内可见
cat /proc/1/root/etc/shadow

# 向宿主机写文件（需写权限）
echo "payload" > /proc/1/root/tmp/pwn
```

## KVM / QEMU 逃逸

虚拟化管理程序上的逃逸利用 VMM 漏洞。

| 漏洞 | 描述 | 攻击者输入 |
|------|------|-----------|
| **CVE-2017-2636** | 内核 `n_hdlc` 模块 double-free | 串口驱动输入 |
| **CVE-2018-16882** | KVM MMIO 越界访问 | I/O 端口操作 |
| **Venom (CVE-2015-3456)** | FDC 控制器溢出 | 虚拟软驱操作 |
| **CVE-2019-14835** | KVM 嵌套虚拟化 bug | vmcall 指令 |

### 防御

- 使用 `seccomp=on`（QEMU 3.0+）
- 移除不必要的设备（`-nodefaults`, `-device` 白名单）
- 使用 KSM 禁用（`echo 2 > /sys/kernel/mm/ksm/run`）
- 最小权限原则：容器不要 `--privileged`，不用 `--cap-add=SYS_ADMIN`

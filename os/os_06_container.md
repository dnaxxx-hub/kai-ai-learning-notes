# 操作系统 第6课：容器化技术与内核隔离

## 容器 vs 虚拟机

| 特性 | 容器 | 虚拟机 |
|------|------|--------|
| 内核 | 共享宿主机内核 | 独立内核 |
| 启动时间 | 毫秒级 | 秒级 |
| 资源开销 | 几乎零额外开销 | 每个VM完整OS |
| 隔离粒度 | Namespace + Cgroup | 硬件虚拟化 |
| 镜像大小 | MB级 | GB级 |

## Namespace 隔离

Linux 8种 Namespace（每种隔离一组资源）：

| 类型 | 系统参数 | 隔离内容 |
|------|---------|---------|
| PID | CLONE_NEWPID | 进程ID，容器内PID从1开始 |
| Network | CLONE_NEWNET | 网络设备、IP、端口、路由表 |
| Mount | CLONE_NEWNS | 挂载点，每个容器有自己的文件系统视图 |
| UTS | CLONE_NEWUTS | 主机名和域名 |
| IPC | CLONE_NEWIPC | 进程间通信资源（消息队列、信号量） |
| User | CLONE_NEWUSER | 用户和组ID，容器内root≠宿主机root |
| Cgroup | CLONE_NEWCGROUP | Cgroup 根目录 |
| Time | CLONE_NEWTIME | 系统时间（Linux 5.6+） |

## Cgroups（Control Groups）

资源限制：CPU、内存、IO、PID 数量等。

```
/sys/fs/cgroup/
├── cpu/          # CPU 配额（cfs_period_us/cfs_quota_us）
├── memory/       # 内存限制（memory.limit_in_bytes）
├── blkio/        # 块设备IO限速
├── pids/         # 进程数上限
└── devices/      # 设备访问控制
```

CPU 配额示例：Docker 的 `--cpus=1.5`
```
/sys/fs/cgroup/cpu/docker/<cid>/cpu.cfs_period_us = 100000 (100ms)
/sys/fs/cgroup/cpu/docker/<cid>/cpu.cfs_quota_us  = 150000 (1.5核)
```

## UnionFS / 镜像分层

Docker 镜像由多层（Layer）组成，每层只存增量变化。

```
容器层（读写层） ← 容器的修改写在这里
  └── 镜像层5（只读）
    └── 镜像层4
      └── 镜像层3
        └── 镜像层2
          └── 镜像层1（基础镜像，如 alpine）
```

### OverlayFS 原理
- **lowerdir** = 镜像层（只读）
- **upperdir** = 容器层（读写）
- **merged** = 合并后的视图（容器看到的是这个）
- **workdir** = 工作目录
- 写时复制（Copy-on-Write）：修改底层文件时，先复制到 upperdir 再修改

## 简化容器运行时模拟

```python
import os, threading, time

class SimpleContainer:
    """简化容器运行时模拟（不含真实的 Linux Namespace）"""
    
    def __init__(self, name, image, cpu_limit=1.0, mem_limit_mb=256):
        self.name = name
        self.image = image
        self.pid = None
        self.status = "created"
        self.cpu_limit = cpu_limit
        self.mem_limit = mem_limit_mb
        self.processes = []
        self.mounts = {}  # host_path → container_path
    
    def add_mount(self, host_path, container_path, readonly=False):
        self.mounts[host_path] = (container_path, readonly)
    
    def start(self, cmd):
        self.status = "running"
        self.pid = id(self)  # 模拟PID
        t = threading.Thread(target=self._run, args=(cmd,), daemon=True)
        t.start()
    
    def _run(self, cmd):
        print(f"[{self.name}] 容器启动 (PID={self.pid})")
        print(f"[{self.name}] 镜像: {self.image}")
        print(f"[{self.name}] CPU限制: {self.cpu_limit} 核")
        print(f"[{self.name}] 内存限制: {self.mem_limit}MB")
        print(f"[{self.name}] 执行命令: {cmd}")
        print(f"[{self.name}] 挂载: {self.mounts}")
        print(f"[{self.name}] PID Namespace: PID从1开始")
        print(f"[{self.name}] Network Namespace: 独立网络栈")
        print(f"[{self.name}] Mount Namespace: 独立文件系统视图")
        print(f"[{self.name}] UTS Namespace: 主机名=container-{self.name}")
        time.sleep(0.1)
        for i in range(3):
            print(f"[{self.name}] 进程[i={i}]: 运行中...")
            time.sleep(0.05)
        print(f"[{self.name}] 进程退出")
        self.status = "exited"
    
    def stop(self):
        self.status = "stopped"
    
    def __repr__(self):
        return f"Container({self.name}, image={self.image}, status={self.status})"

# 演示
c1 = SimpleContainer("web-1", "nginx:alpine", cpu_limit=1.0, mem_limit_mb=128)
c1.add_mount("/data/config", "/etc/nginx/conf.d", readonly=True)
c1.start("nginx -g 'daemon off;'")

c2 = SimpleContainer("app-1", "python:3.11-slim", cpu_limit=2.0, mem_limit_mb=512)
c2.start("python app.py")

time.sleep(0.5)
print(f"\n容器状态: {c1}, {c2}")
print(f"\n--- 分层文件系统模拟 ---")
print("容器层 (可写): /var/lib/docker/overlay2/<cid>/diff/")
print("镜像层1: /var/lib/docker/overlay2/<hash1>/diff/ (基础OS)")
print("镜像层2: /var/lib/docker/overlay2/<hash2>/diff/ (nginx)")
print("镜像层3: /var/lib/docker/overlay2/<hash3>/diff/ (配置文件)")
print("合并层: /var/lib/docker/overlay2/<cid>/merged/")
print("CoW: 如果修改 /etc/nginx/nginx.conf → 复制到容器层再改")
```

## 关键总结
- Namespace：8种隔离维度，每种隔离一组内核资源
- Cgroup：CPU/内存/IO 硬限制，防止资源争抢
- OverlayFS：分层镜像 + CoW，实现秒级启动和 MB级增量
- 容器 ≠ 轻量级VM，是进程级隔离（共享内核）

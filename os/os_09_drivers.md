# 第9课：设备驱动

## 1. Linux 驱动模型：设备分类

```
┌──────────────────────────────────────────┐
│               Linux 设备驱动               │
├──────────┬───────────┬───────────────────┤
│   char   │   block   │       net         │
│ 字符设备  │  块设备   │     网络设备       │
├──────────┼───────────┼───────────────────┤
│ 字节流    │ 块I/O     │ 数据包             │
│ /dev/tty  │ /dev/sda  │ eth0/wlan0        │
│ /dev/mem  │ /dev/nvme │ lo                │
│ 串口、GPIO │ 硬盘、SSD  │ 网卡              │
│ open/read │ mount/fs  │ socket interface  │
│ write/ioctl│ page cache│ sk_buff           │
└──────────┴───────────┴───────────────────┘
```

### 三大设备类型

| 类型 | 特征 | 设备号 | 操作接口 | 示例 |
|------|------|--------|----------|------|
| **char** | 字节流，顺序访问 | 主+次 | `file_operations` | 键盘、串口、GPU |
| **block** | 块(512B/4KB)，随机访问 | 主+次 | `block_device_operations` | 磁盘、SSD |
| **net** | 数据包(packet)，异步 | 无设备号 | `net_device_ops` | 以太网、WiFi |

## 2. 驱动架构：生命周期

```
┌─────────────────────────────────────────────────────┐
│              字符设备驱动完整生命周期                    │
├─────────────────────────────────────────────────────┤
│                                                       │
│  module_init(my_init)        ← 模块入口                 │
│     │                                                 │
│     ▼                                                 │
│  probe()                                              │
│     │  1. alloc_chrdev_region()  — 分配设备号           │
│     │  2. cdev_init()           — 初始化 cdev           │
│     │  3. cdev_add()            — 注册到内核             │
│     │  4. class_create() + device_create() — 创建设备节点│
│     ▼                                                 │
│  ┌─────────── 用户调用 ────────────┐                   │
│  │                                  │                   │
│  │  open() → 设备文件 → VFS → 驱动  │                   │
│  │      │ 分配私有数据/硬件初始化     │                   │
│  │      ▼                           │                   │
│  │  read()/write()                  │                   │
│  │      │ copy_to_user/copy_from_user│                  │
│  │      ▼                           │                   │
│  │  ioctl() → 硬件控制命令           │                   │
│  │      ▼                           │                   │
│  │  release() → 释放资源             │                   │
│  └──────────────────────────────────┘                   │
│                                                       │
│  module_exit(my_exit)           ← 模块卸载              │
│     │                                                 │
│     ▼                                                 │
│  cleanup()                                             │
│      unregister_chrdev_region()                        │
│      device_destroy() + class_destroy()                │
│                                                       │
└─────────────────────────────────────────────────────┘
```

### 核心数据结构：`file_operations`

```c
/* Linux 内核中字符设备驱动的核心结构体 */
struct file_operations {
    struct module *owner;
    loff_t (*llseek) (struct file *, loff_t, int);
    ssize_t (*read) (struct file *, char __user *, size_t, loff_t *);
    ssize_t (*write) (struct file *, const char __user *, size_t, loff_t *);
    int (*mmap) (struct file *, struct vm_area_struct *);
    int (*open) (struct inode *, struct file *);
    int (*release) (struct inode *, struct file *);
    long (*unlocked_ioctl) (struct file *, unsigned int, unsigned long);
};
// 每个设备驱动只需实现其中需要的方法，不需要的设为 NULL
```

## 3. 中断处理：上半部 vs 下半部

```
                    ┌─────────────┐
                    │  硬件中断触发  │
                    └──────┬──────┘
                           ▼
              ┌────────────────────────┐
              │    interrupt handler    │  ← 上半部 (top half)
              │   (中断上下文, 不可睡眠) │      atomic context
              │   • 保存寄存器           │
              │   • 确认中断             │
              │   • 记录关键状态          │
              │   • 调度 bottom half     │
              │   • 尽快返回             │
              └───────────┬────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
    ┌──────────┐   ┌──────────┐   ┌──────────────┐
    │ tasklet  │   │ workqueue │   │ softirq      │
    │ (软中断)  │   │ (工作队列) │   │ (软中断)      │
    ├──────────┤   ├──────────┤   ├──────────────┤
    │ 立即执行  │   │ 延迟执行  │   │ 内核线程      │
    │ 中断上下文│   │ 进程上下文│   │ 特定场景      │
    │ 不可睡眠  │   │ 可以睡眠  │   │ 网络RX/TX等   │
    │ 原子操作  │   │ 开锁/malloc│  │              │
    │ 快速处理  │   │ 复杂处理  │   │              │
    └──────────┘   └──────────┘   └──────────────┘

    Clock:  中断触发 → [~1-5μs] top half → [~10-100μs] bottom half
```

### bottom half 机制对比

| 特性 | tasklet | workqueue | softirq |
|------|---------|-----------|---------|
| 上下文 | 中断上下文（atomic） | 进程上下文 | 中断上下文 |
| 可睡眠 | ❌ | ✅ | ❌ |
| 并发 | 单核串行 | 多核并行 | 多核并行 |
| 性能 | 较快 | 较慢（可睡眠） | 最快 |
| 典型用途 | 网卡收包 | USB子系统 | 网络RX/TX、timer |
| 创建方式 | `DECLARE_TASKLET()` | `INIT_WORK()` | 静态分配 |

## 4. 简单字符设备驱动伪代码

```python
#!/usr/bin/env python3
"""
伪代码：Linux 字符设备驱动 核心流程
注：用 Python 模拟内核驱动生命周期和数据结构
"""

class FileOperations:
    """对应内核 struct file_operations"""
    def __init__(self):
        self.owner = None
        self.open = None
        self.read = None
        self.write = None
        self.release = None
        self.unlocked_ioctl = None

class CharDevice:
    """模拟一个简单的字符设备驱动"""
    
    # ───────────────── 驱动生命周期 ─────────────────
    
    @classmethod
    def init_module(cls):
        """
        module_init() 入口。
        Linux: module_init(my_init)
        """
        dev = cls()
        dev.probe()
        return dev
    
    def probe(self):
        """
        探测/初始化阶段
        Linux:
            alloc_chrdev_region(&dev_num, 0, 1, "mydev")
            cdev = cdev_alloc()
            cdev->ops = &my_fops
            cdev_add(cdev, dev_num, 1)
            class_create(THIS_MODULE, "mydev_class")
            device_create(my_class, NULL, dev_num, NULL, "mydev")
        """
        self.major = 240        # 主设备号 (动态分配)
        self.minor = 0          # 次设备号
        self.buffer = bytearray(1024)   # 内核缓冲区 (kmalloc)
        self.usage_count = 0    # 引用计数
        self.private_data = {}  # 私有数据
        
        # 注册 file_operations
        self.fops = FileOperations()
        self.fops.owner = "THIS_MODULE"
        self.fops.open = self.open  # → 放到 fops 表中
        self.fops.read = self.read
        self.fops.write = self.write
        self.fops.release = self.release
        
        print(f"[probe] 注册设备: major={self.major}, minor={self.minor}")
        print(f"[probe] 创建 /dev/mydev (主设备号 {self.major})")
        return 0  # 成功
    
    # ───────────────── file_operations 实现 ─────────────────
    
    def open(self, inode, filep):
        """
        open("/dev/mydev", O_RDWR)
        Linux:
            static int my_open(struct inode *inode, struct file *filep) {
                struct my_dev *dev = container_of(inode->i_cdev, ...);
                filep->private_data = dev;
                // 硬件初始化：reset、配置寄存器、开启中断等
                return 0;
            }
        """
        self.usage_count += 1
        print(f"[open] 设备打开, 当前使用计数: {self.usage_count}")
        # 真实驱动会：ioremap、request_irq、配置DMA等
        return 0
    
    def read(self, filep, buf, count, f_pos):
        """
        read(fd, user_buf, 100)
        Linux:
            static ssize_t my_read(struct file *filep, char __user *buf,
                                   size_t count, loff_t *f_pos) {
                struct my_dev *dev = filep->private_data;
                ret = copy_to_user(buf, dev->buffer + *f_pos, count);
                // copy_to_user → 内核空间→用户空间拷贝
                *f_pos += count - ret;
                return count - ret;
            }
        """
        # 模拟从内核缓冲区拷贝数据到用户空间
        read_size = min(count, len(self.buffer))
        data = bytes(self.buffer[:read_size])
        print(f"[read] 读取 {read_size} bytes (f_pos={f_pos})")
        # copy_to_user(data, buf) — 需要检查指针合法性
        return data, read_size
    
    def write(self, filep, buf, count, f_pos):
        """
        write(fd, "hello", 5)
        Linux:
            static ssize_t my_write(struct file *filep, const char __user *buf,
                                    size_t count, loff_t *f_pos) {
                struct my_dev *dev = filep->private_data;
                ret = copy_from_user(dev->buffer, buf + *f_pos, count);
                // 硬件写：outb() / iowrite32() / writel()
                return count - ret;
            }
        """
        write_size = min(count, len(self.buffer))
        # copy_from_user(buf → kernel buffer)
        self.buffer[:write_size] = buf[:write_size]
        print(f"[write] 写入 {write_size} bytes")
        return write_size
    
    def release(self, inode, filep):
        """
        close(fd)
        Linux: 减少引用计数，必要时释放硬件资源
        """
        self.usage_count -= 1
        print(f"[release] 设备关闭, 剩余使用计数: {self.usage_count}")
        return 0
    
    # ───────────────── 中断处理 ─────────────────
    
    def interrupt_handler(self, irq):
        """
        Linux: static irqreturn_t my_interrupt(int irq, void *dev_id)
        
        === 上半部 (top half) — 中断上下文 ===
        - 保存硬件状态寄存器
        - 调度 tasklet/workqueue
        - 尽快返回 IRQ_HANDLED
        
        === 下半部 (bottom half) — 延迟处理 ===
        - tasklet:   在软中断上下文立即执行
        - workqueue: 在进程上下文排队等待
        """
        print(f"[IRQ handler - top half] 处理中断 {irq}")
        print("  → 保存硬件状态寄存器")
        print("  → 确认中断（清中断标志）")
        print("  → 调度 tasklet（快速路径）或 workqueue（慢速路径）")
        return "IRQ_HANDLED"
    
    def tasklet_handler(self, data):
        """
        tasklet 处理函数（软中断上下文）
        用于：数据复制、定时器等轻量操作
        """
        print("[tasklet - bottom half] 快速处理，不可睡眠")
        print("  → 读取硬件 FIFO 到缓冲区")
        print("  → 唤醒等待的 read() 进程")
    
    def workqueue_handler(self, work):
        """
        workqueue 处理函数（内核线程上下文）
        用于：复杂I/O、锁操作、睡眠等待等
        """
        print("[workqueue - bottom half] 慢速处理，可以睡眠")
        print("  → 可能的 DMA 完成处理")
        print("  → 通知用户态事件")
    
    # ───────────────── 模块卸载 ─────────────────
    
    def cleanup_module(self):
        """
        module_exit() 清理
        Linux:
            device_destroy(my_class, dev_num)
            class_destroy(my_class)
            unregister_chrdev_region(dev_num, 1)
            cdev_del(cdev)
            free_irq(irq, dev_id)
            iounmap(io_base)
        """
        print("[cleanup] 卸载驱动")
        print("  → device_destroy() — 删除设备节点")
        print("  → unregister_chrdev_region() — 释放设备号")
        print("  → free_irq() — 释放中断")
        print("  → iounmap() — 取消 I/O 内存映射")
        print("  → kfree() — 释放内核缓冲区")

# ───────────────── 驱动注册示例 ─────────────────
if __name__ == "__main__":
    print("=" * 60)
    print(" Linux 字符设备驱动模拟")
    print("=" * 60)
    
    # 模块加载
    dev = CharDevice.init_module()
    
    # 用户态操作模拟
    print("\n--- 用户态操作 ---")
    dev.open(None, None)
    dev.read(None, None, 64, 0)
    dev.write(None, b"Hello from userspace", 21, 0)
    dev.interrupt_handler(42)
    dev.tasklet_handler(None)
    dev.release(None, None)
    
    # 模块卸载
    print("\n--- 模块卸载 ---")
    dev.cleanup_module()
```

## 5. DPC (Windows) vs Tasklet (Linux)

```
┌──────────────────────────────────────────────────────────────┐
│              Windows DPC  vs  Linux Tasklet                   │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Windows: IRQL (Interrupt Request Level)                      │
│                                                               │
│  HIGH → POWER_LEVEL            │  Linux: 中断优先级           │
│         PROCESSOR_LEVEL        │                              │
│         CLOCK_LEVEL            │  高 → NMI / Machine Check    │
│         PROFILE_LEVEL          │      硬件中断 (IRQ)           │
│         ←─── DPC LEVEL ───→    │      ←── softirq/tasklet ──→ │
│         APC_LEVEL              │      内核线程                 │
│  LOW  → PASSIVE_LEVEL          │  低 → 用户态                   │
│                                                               │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  DPC (Deferred Procedure Call)       Tasklet                  │
│  ─────────────────────────────       ──────────────────       │
│                                                               │
│  1. ISR 结束时调度 DPC               1. ISR 调度 tasklet       │
│     KeInsertQueueDpc()                  tasklet_schedule()     │
│                                                               │
│  2. 所有处理器 ISR 完成后             2. 软中断 ksoftirqd      │
│     内核检查 DPC 队列                  处理 tasklet 列表       │
│                                                               │
│  3. DPC 在 IRQL = DISPATCH_LEVEL     3. tasklet 在软中断      │
│     执行 ← 不可被线程抢占               上下文执行              │
│                                                               │
│  4. 可多处理器并行                    4. 同类型串行执行        │
│     DPC 可同时运行                      同一 tasklet 不并行    │
│                                                               │
│  5. 相同优先级：按插入顺序             5. 优先级高于 workqueue  │
│     FIFO 队列                          仅次于硬件中断          │
│                                                               │
├──────────────────────────────────────────────────────────────┤
│  本质：两者都是"在中断返回后、不立刻在中断上下文执行完           │
│  所有工作，而是推迟一部分到较低优先级执行"的机制。              │
│  都是不可睡眠的延迟过程调用。                                 │
└──────────────────────────────────────────────────────────────┘
```

### 总结

```
驱动 = 内核模块 + file_operations 表 + 中断处理 + 硬件访问

关键原则：
① 上半部做最少的事（保存状态、调度下半部）
② 下半部做实际工作
③ 中断上下文不能睡眠 → 复杂任务用 workqueue
④ copy_to/from_user 保证内核↔用户空间安全
⑤ 引用计数防止热拔插时的竞态
```

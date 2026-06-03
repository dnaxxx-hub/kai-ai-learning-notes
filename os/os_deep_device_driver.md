# OS 设备驱动深度解析

> 学习笔记：从内核视角理解 Linux 设备驱动架构

---

## 目录

1. [驱动基础 — 设备、模块与接口](#1-驱动基础--设备模块与接口)
2. [字符设备驱动 — 最简驱动模型](#2-字符设备驱动--最简驱动模型)
3. [块设备驱动 — I/O 栈与调度器](#3-块设备驱动--io-栈与调度器)
4. [中断处理 — 上半部与下半部](#4-中断处理--上半部与下半部)
5. [DMA 与 I/O 内存 — 直接访问硬件](#5-dma-与-io-内存--直接访问硬件)
6. [总线模型 — Platform / PCI / USB](#6-总线模型--platform--pci--usb)
7. [总结与实战建议](#7-总结与实战建议)

---

## 1. 驱动基础 — 设备、模块与接口

### 1.1 设备类型分类

Linux 将硬件设备抽象为三大类，以 `/dev` 下的文件为入口供用户态访问：

| 类型 | 特点 | 典型设备 | 内核标识 |
|------|------|----------|----------|
| **字符设备** | 流式 I/O，无缓冲，顺序读写 | 键盘、鼠标、串口、GPU | `struct cdev` |
| **块设备** | 随机访问，有缓冲，按块读写 | 硬盘、SSD、U盘 | `struct gendisk` |
| **网络设备** | 数据包收发，不是文件 | 网卡、WiFi | `struct net_device` |

> 字符设备和块设备都通过 `/dev` 节点暴露，网络设备则通过 `socket` 接口访问。

### 1.2 设备号 — 主设备号与次设备号

设备号是内核定位驱动的关键索引：

```
设备号 (dev_t, 32-bit)
  ├── 主设备号 (12 bit)  →  标识设备驱动
  └── 次设备号 (20 bit)  →  标识同驱动下的具体设备
```

**主设备号分配策略：**
- **静态分配**：`register_chrdev_region(MKDEV(major, 0), count, name)`
- **动态分配**：`alloc_chrdev_region(&dev, 0, count, name)` — 推荐，避免冲突

在 `/proc/devices` 中可以查看当前系统已注册的设备号。

### 1.3 file_operations 结构体

这是驱动与 VFS（虚拟文件系统）之间的契约。每个操作都是一个函数指针：

```c
struct file_operations {
    struct module *owner;
    loff_t (*llseek)  (struct file *, loff_t, int);
    ssize_t (*read)   (struct file *, char __user *, size_t, loff_t *);
    ssize_t (*write)  (struct file *, const char __user *, size_t, loff_t *);
    long   (*unlocked_ioctl) (struct file *, unsigned int, unsigned long);
    int    (*open)    (struct inode *, struct file *);
    int    (*release) (struct inode *, struct file *);
    // ... 更多回调
};
```

> 用户态 `open("/dev/xxx")` → VFS → 驱动 `xxx_open()`。用户不感知驱动细节。

### 1.4 模块初始化和卸载

Linux 驱动以内核模块（`.ko`）形式加载：

```c
module_init(my_init);      // insmod 时调用
module_exit(my_exit);      // rmmod 时调用
MODULE_LICENSE("GPL");
MODULE_AUTHOR("Your Name");
```

**初始化典型流程：**
```
1. alloc_chrdev_region()      — 分配设备号
2. cdev_init() + cdev_add()   — 注册字符设备
3. class_create()              — 创建设备类
4. device_create()             — 自动创建 /dev 节点 (udev)
```

**卸载相反流程：**
```
1. device_destroy() + class_destroy()
2. cdev_del()
3. unregister_chrdev_region()
```

### 1.5 udev 设备文件自动创建

传统 Linux 需要 `mknod` 手动创建设备节点。现代内核使用 **devtmpfs + udev** 自动管理：

- 驱动调用 `device_create()` → 内核发送 uevent 到用户态
- `udevd` 监听 uevent → 在 `/dev` 下创建对应节点
- 权限和命名规则可在 `/etc/udev/rules.d/` 中自定义

---

## 2. 字符设备驱动 — 最简驱动模型

### 2.1 cdev 结构体

内核用 `cdev` 表示一个字符设备：

```c
struct cdev {
    struct kobject kobj;           // 内核对象（用于引用计数和 sysfs）
    struct module *owner;          // 所属模块
    const struct file_operations *ops;  // 操作函数表
    struct list_head list;         // 链表节点
    dev_t dev;                     // 设备号
    unsigned int count;            // 次设备号数量
};
```

**注册流程：**

```c
// 静态分配并初始化
struct cdev my_cdev;
cdev_init(&my_cdev, &fops);
my_cdev.owner = THIS_MODULE;
cdev_add(&my_cdev, dev_num, 1);

// 或动态分配
struct cdev *my_cdev = cdev_alloc();
my_cdev->ops = &fops;
my_cdev->owner = THIS_MODULE;
cdev_add(my_cdev, dev_num, 1);
```

### 2.2 open / release

`open()` 在设备首次被访问时触发，`release()` 在最后一个 `close()` 时触发：

```c
static int dev_open(struct inode *inode, struct file *filp) {
    // 从 inode 获取 cdev，存入 filp 的私有数据
    struct my_dev *dev = container_of(inode->i_cdev, struct my_dev, cdev);
    filp->private_data = dev;

    // 原子操作记录打开次数
    atomic_inc(&dev->open_count);
    try_module_get(THIS_MODULE);  // 防止模块卸载
    return 0;
}

static int dev_release(struct inode *inode, struct file *filp) {
    struct my_dev *dev = filp->private_data;
    atomic_dec(&dev->open_count);
    module_put(THIS_MODULE);
    return 0;
}
```

### 2.3 read / write — 用户态与内核态数据拷贝

这是驱动开发最关键的环节之一。内核不能直接解引用用户空间指针，必须使用专用 API：

| API | 方向 | 特点 |
|-----|------|------|
| `copy_to_user(void __user *to, const void *from, unsigned long n)` | 内核 → 用户 | 自动处理缺页，会阻塞 |
| `copy_from_user(void *to, const void __user *from, unsigned long n)` | 用户 → 内核 | 同上 |
| `put_user(x, ptr)` | 内核 → 用户 | 单值拷贝（简单类型） |
| `get_user(x, ptr)` | 用户 → 内核 | 单值读取 |

**典型 read 实现：**

```c
static ssize_t dev_read(struct file *filp, char __user *buf,
                        size_t count, loff_t *f_pos) {
    struct my_dev *dev = filp->private_data;
    ssize_t ret;

    // 检查读位置是否超出数据长度
    if (*f_pos >= dev->data_len)
        return 0;

    // 限制读取长度
    if (*f_pos + count > dev->data_len)
        count = dev->data_len - *f_pos;

    // 拷贝到用户空间
    if (copy_to_user(buf, dev->data + *f_pos, count))
        return -EFAULT;

    *f_pos += count;
    return count;
}
```

**典型 write 实现：**

```c
static ssize_t dev_write(struct file *filp, const char __user *buf,
                         size_t count, loff_t *f_pos) {
    struct my_dev *dev = filp->private_data;

    if (count > MAX_BUF_SIZE)
        return -ENOSPC;

    if (copy_from_user(dev->data, buf, count))
        return -EFAULT;

    dev->data_len = count;
    *f_pos += count;
    return count;
}
```

### 2.4 unlocked_ioctl — 设备控制命令

`ioctl` 提供 read/write 之外的设备特定操作（如配置参数、设置模式等）。

```c
static long dev_ioctl(struct file *filp, unsigned int cmd, unsigned long arg) {
    struct my_dev *dev = filp->private_data;

    switch (cmd) {
    case MY_IOCTL_SET_SIZE:
        dev->buf_size = arg;
        break;
    case MY_IOCTL_GET_STATUS:
        if (put_user(dev->status, (int __user *)arg))
            return -EFAULT;
        break;
    default:
        return -ENOTTY;  // 未定义的 ioctl 命令
    }
    return 0;
}
```

> 注意：现代内核使用 `unlocked_ioctl`（不带大内核锁），不再使用 `ioctl`。

### 2.5 llseek — 文件指针定位

```c
static loff_t dev_llseek(struct file *filp, loff_t offset, int whence) {
    struct my_dev *dev = filp->private_data;
    loff_t new_pos;

    switch (whence) {
    case SEEK_SET: new_pos = offset; break;
    case SEEK_CUR: new_pos = filp->f_pos + offset; break;
    case SEEK_END: new_pos = dev->data_len + offset; break;
    default: return -EINVAL;
    }

    if (new_pos < 0) return -EINVAL;
    filp->f_pos = new_pos;
    return new_pos;
}
```

---

## 3. 块设备驱动 — I/O 栈与调度器

### 3.1 块 vs 字符 — 本质区别

| 维度 | 字符设备 | 块设备 |
|------|----------|--------|
| 数据访问 | 流式、顺序 | 随机、按块 |
| 缓冲 | 无（或用户态缓冲） | 内核页缓存 + 块缓冲 |
| I/O 请求 | 直接的 read/write 调用 | 请求队列 + 调度器 |
| 最小单元 | 字节 | 扇区（512B/4KB） |
| 挂载文件系统 | 否 | 是 |

### 3.2 block_device_operations

块设备的操作比字符设备更简洁，因为 I/O 细节由请求队列处理：

```c
struct block_device_operations {
    int  (*open)   (struct block_device *, fmode_t);
    void (*release)(struct gendisk *, fmode_t);
    int  (*ioctl)  (struct block_device *, fmode_t, unsigned, unsigned long);
    int  (*getgeo) (struct block_device *, struct hd_geometry *);
    struct module *owner;
};
```

### 3.3 请求队列 — 传统 request_fn vs blk-mq

**传统单队列模式（Legacy）：**

```c
struct request_queue *q = blk_init_queue(my_request_fn, &my_lock);
```

所有 I/O 请求进入单条队列，由调度器排序后交给驱动：

```
上层文件系统 → BIO → 电梯调度 → request_queue → request_fn → 磁盘
```

**现代 blk-mq 多队列模式：**

```c
struct blk_mq_tag_set tag_set;
tag_set.ops = &my_mq_ops;
tag_set.nr_hw_queues = nr_cpus;  // 硬件队列数 = CPU 数
blk_mq_alloc_disk(&tag_set, &dev);

// blk-mq ops 只提供 queue_rq 回调
static blk_status_t my_queue_rq(struct blk_mq_hw_ctx *hctx,
                                const struct blk_mq_queue_data *bd) {
    struct request *req = bd->rq;
    blk_mq_start_request(req);
    // 处理请求...
    blk_mq_end_request(req, BLK_STS_OK);
    return BLK_STS_OK;
}
```

**优势：** 每个 CPU 有独立队列，无需全局锁，适配 NVMe 等多队列 SSD。

### 3.4 I/O 调度算法

| 调度器 | 特点 | 适用场景 |
|--------|------|----------|
| **NOOP** | 纯 FIFO，不做合并排序 | NVMe/SSD（无机械寻道） |
| **CFQ** (Completely Fair Queuing) | 按进程公平分配 I/O 时间片 | 传统机械硬盘 |
| **Deadline** | 每请求设截止时间，防饿死 | 需要延迟保证的场景 |
| **mq-deadline** | Deadline 的 blk-mq 版本 | 现代多队列设备 |

### 3.5 BIO（块 I/O 请求）

BIO 是块层与文件系统之间的核心数据结构：

```
struct bio {
    struct bio      *bi_next;     // 链表连接
    struct block_device *bi_bdev; // 目标块设备
    struct bvec_iter    bi_iter;  // 迭代位置
    unsigned short      bi_vcnt;  // bio_vec 数量
    struct bio_vec      *bi_io_vec; // 数据段数组
    bio_end_io_t        *bi_end_io; // 完成回调
};

struct bio_vec {
    struct page *bv_page;  // 页框
    unsigned int bv_len;   // 长度
    unsigned int bv_offset; // 页内偏移
};
```

**I/O 路径完整流程：**
```
应用程序 (read/write)
    ↓
VFS / syscall
    ↓
文件系统 (ext4/xfs/btrfs)
    ↓ 分配 BIO，提交到块层
块层 / 通用块层 (generic block layer)
    ↓ 合并/拆分 BIO
I/O 调度器 (deadline/cfq/mq-deadline)
    ↓ 生成 request
驱动程序 (blk-mq queue_rq)
    ↓
硬件 (NVMe/SATA/虚拟磁盘)
```

---

## 4. 中断处理 — 上半部与下半部

### 4.1 为什么需要拆分？

中断处理必须在最短时间内完成。但真实场景中，处理一个中断往往包含：

- **紧急工作**：保存硬件状态、清除中断标志、接收数据（**上半部**）
- **非紧急工作**：将数据拷贝到用户缓冲区、唤醒等待进程、协议栈处理（**下半部**）

**核心思想：上半部屏蔽中断执行紧急代码，下半部开中断执行剩余工作。**

### 4.2 注册中断处理函数

```c
// 中断号 17, 共享中断需 IRQF_SHARED
ret = request_irq(irq_num, my_interrupt_handler,
                  IRQF_SHARED, "my_device", dev);

// 或使用 devm_ 自动管理
devm_request_irq(dev, irq_num, handler, IRQF_SHARED, "my_dev", dev);
```

**上半部实现：**

```c
static irqreturn_t my_interrupt_handler(int irq, void *dev_id) {
    struct my_dev *dev = (struct my_dev *)dev_id;

    // 1. 读取硬件状态寄存器
    u32 status = ioread32(dev->regs + STATUS_REG);

    // 2. 如果非本设备中断，返回 IRQ_NONE（共享中断时必做）
    if (!(status & IRQ_PENDING))
        return IRQ_NONE;

    // 3. 清除中断标志
    iowrite32(status | IRQ_ACK, dev->regs + STATUS_REG);

    // 4. 保存紧急数据
    dev->raw_data = ioread32(dev->regs + DATA_REG);

    // 5. 调度下半部 → 方式有多种
    schedule_work(&dev->work);  // workqueue 方式
    // tasklet_schedule(&dev->tasklet);  // tasklet 方式

    return IRQ_HANDLED;
}
```

### 4.3 下半部实现方式对比

| 机制 | 上下文 | 可睡眠 | 特性 |
|------|--------|--------|------|
| **软中断 (softirq)** | 中断上下文 | ❌ 否 | 最轻量，由内核直接调用，固定数量 |
| **tasklet** | 基于软中断 | ❌ 否 | 简单 API，同一 tasklet 串行执行 |
| **workqueue** | 进程上下文 | ✅ 是 | 最灵活，可使用内核 API，可重调度 |
| **threaded IRQ** | 内核线程 | ✅ 是 | 直接注册为线程，与上半部分离 |

**workqueue 实现：**

```c
// 在 probe 中初始化
INIT_WORK(&dev->work, my_work_handler);

// 下半部函数
static void my_work_handler(struct work_struct *work) {
    struct my_dev *dev = container_of(work, struct my_dev, work);
    // 可以安全调用 copy_to_user、kmalloc(GFP_KERNEL) 等
    copy_to_user(dev->user_buf, &dev->raw_data, sizeof(dev->raw_data));
    wake_up_interruptible(&dev->read_wait);
}
```

**threaded IRQ 实现（最推荐的新方式）：**

```c
// request_threaded_irq(irq, handler, thread_fn, flags, name, dev)
// handler == NULL 时，用系统默认的上半部（立刻唤醒线程）
request_threaded_irq(irq, NULL, my_thread_fn, IRQF_SHARED, "my_dev", dev);

static irqreturn_t my_thread_fn(int irq, void *dev_id) {
    // 运行在内核线程中，可睡眠，可持有互斥锁
    struct my_dev *dev = dev_id;
    mutex_lock(&dev->lock);
    // ... 复杂处理 ...
    mutex_unlock(&dev->lock);
    return IRQ_HANDLED;
}
```

### 4.4 共享中断与 MSI-X

**共享中断：** 多个设备共用同一个 IRQ 线，handler 必须检查是否是自己的中断：
```c
if (!(status & MY_DEVICE_IRQ_BIT))
    return IRQ_NONE;  // 不处理，留给下一个 handler
```

**MSI-X (Message Signaled Interrupts eXtended)：**
- 每个设备功能有独立中断向量
- 无需 IRQ 线共享，无需轮询
- PCIe 设备首选，性能最优

### 4.5 软中断与 tasklet 实现

内核中有固定数量的软中断（软中断向量）：
```
HI_SOFTIRQ       — 高优先级 tasklet
TIMER_SOFTIRQ    — 定时器
NET_TX_SOFTIRQ   — 网络发送
NET_RX_SOFTIRQ   — 网络接收
BLOCK_SOFTIRQ    — 块设备
TASKLET_SOFTIRQ  — 普通 tasklet
```

tasklet 本质上是对软中断的封装。每个 tasklet 保证同一时刻只在同一个 CPU 上执行（串行化）。

---

## 5. DMA 与 I/O 内存 — 直接访问硬件

### 5.1 DMA 直接内存访问

传统 PIO（Programmed I/O）：CPU 逐字节搬运数据 → 效率低下。

DMA：硬件直接搬运，CPU 只负责设置参数，完成后设备发中断通知。

```
无 DMA:      CPU → [数据] → 设备 (CPU 全程参与)
有 DMA:      CPU 设置 DMA 描述符 → DMA 引擎搬运 → 中断通知 CPU
```

### 5.2 DMA 映射类型

| 类型 | API | 特点 |
|------|-----|------|
| **流式映射** | `dma_map_single() / dma_unmap_single()` | 用于单次传输，缓存一致性需手动同步 |
| **一致性映射** | `dma_alloc_coherent()` | 用于长期共享内存，自动维护一致性 |

**流式 DMA 完整流程：**

```c
// 1. 分配 DMA 缓冲区（内核页对齐）
buf = kmalloc(size, GFP_KERNEL | GFP_DMA);

// 2. 映射为 DMA 地址（流式，方向到设备）
dma_addr = dma_map_single(dev, buf, size, DMA_TO_DEVICE);
if (dma_mapping_error(dev, dma_addr)) {
    kfree(buf);
    return -ENOMEM;
}

// 3. 告诉硬件 DMA 地址，触发传输
iowrite32(dma_addr, dev->regs + DMA_ADDR_REG);
iowrite32(size, dev->regs + DMA_SIZE_REG);
iowrite32(1, dev->regs + DMA_START_REG);

// 4. 传输完成后（中断中），解除映射
dma_unmap_single(dev, dma_addr, size, DMA_TO_DEVICE);

// 5. 确保 CPU 能看到数据
dma_sync_single_for_cpu(dev, dma_addr, size, DMA_FROM_DEVICE);
```

### 5.3 IOMMU / IO 内存屏障

**IOMMU**：为 I/O 设备提供虚拟地址映射，类似 CPU 的 MMU：
- 设备只能访问 IOMMU 映射的内存区域（安全隔离）
- 允许大块不连续的物理内存呈现为连续的 DMA 地址

**IO 内存屏障**：控制 CPU 和硬件之间的内存访问顺序：

```c
wmb();   // 写屏障 — 确保之前的写操作在后续写之前完成
rmb();   // 读屏障 — 确保之前的读操作在后续读之前完成
mb();    // 全屏障
mmiowb(); // MMIO 写屏障 — 保证对 PCI 设备的写顺序
```

典型用法（先写数据到内存，再通知硬件 DMA）：

```c
memcpy(buf, data, len);
wmb();                       // 确保数据已写入内存
iowrite32(1, regs + GO_REG); // 然后才通知硬件
```

### 5.4 MMIO vs PIO

| 方式 | 说明 | 使用场景 |
|------|------|----------|
| **PIO (端口 I/O)** | `inb()/outb()` 访问独立 I/O 端口空间 | x86 传统设备 |
| **MMIO (内存映射 I/O)** | `ioread32()/iowrite32()` 将寄存器映射到内存地址空间 | 现代设备（PCIe） |

MMIO 通过 `ioremap()` 建立页表映射：

```c
void __iomem *regs = ioremap(pci_resource_start(pdev, 0), resource_size);
u32 val = ioread32(regs + 0x10);
iowrite32(val | BIT(0), regs + 0x10);
iounmap(regs);  // 清理
```

---

## 6. 总线模型 — Platform / PCI / USB

### 6.1 Linux 设备模型基础

内核用三个核心概念驱动一切：

```
Device ←→ Bus ←→ Driver
    ↑                  ↑
描述硬件设备      提供 probe/remove 回调
                  BUS 匹配成功后调用 probe
```

匹配时，Bus 会尝试将 device 和 driver 配对（通过 name、ID table、device tree 兼容属性等），配对成功则调用 driver 的 `probe()`。

### 6.2 Platform Driver（平台驱动）

用于非枚举型总线（SoC 内部集成设备，如 GPIO、I2C、SPI）：

**平台设备（通常由 Device Tree 或 ACPI 描述）：**

```dts
// Device Tree 中的设备节点
my_device: my-device@1c00000 {
    compatible = "my-company,my-device";
    reg = <0x1c00000 0x1000>;
    interrupts = <0 42 4>;
};
```

**平台驱动代码：**

```c
static struct of_device_id my_of_match[] = {
    { .compatible = "my-company,my-device" },
    { }
};
MODULE_DEVICE_TABLE(of, my_of_match);

static int my_probe(struct platform_device *pdev) {
    struct resource *res;
    void __iomem *regs;
    int irq;

    // 获取 I/O 内存资源
    res = platform_get_resource(pdev, IORESOURCE_MEM, 0);
    regs = devm_ioremap_resource(&pdev->dev, res);

    // 获取中断号
    irq = platform_get_irq(pdev, 0);

    // 分配设备私有结构，注册中断，注册设备等
    // ...

    return 0;
}

static int my_remove(struct platform_device *pdev) {
    // 清理资源
    return 0;
}

static struct platform_driver my_driver = {
    .probe  = my_probe,
    .remove = my_remove,
    .driver = {
        .name = "my_device",
        .of_match_table = my_of_match,
        .pm = &my_pm_ops,  // 电源管理
    },
};
module_platform_driver(my_driver);
```

### 6.3 PCI 子系统

PCI 是可枚举的：通过遍历 PCI 配置空间能找到所有设备。

```c
static struct pci_device_id my_pci_ids[] = {
    { PCI_DEVICE(0x1234, 0x5678) },  // vendor=0x1234, device=0x5678
    { }
};
MODULE_DEVICE_TABLE(pci, my_pci_ids);

static int my_pci_probe(struct pci_dev *pdev, const struct pci_device_id *id) {
    // 启用设备
    pci_enable_device(pdev);
    pci_set_master(pdev);

    // 分配 PCI 资源
    pci_request_regions(pdev, "my_device");

    // 建立 MMIO 映射
    void __iomem *bar0 = pci_iomap(pdev, 0, 0);

    // 设置 DMA
    dma_set_mask(&pdev->dev, DMA_BIT_MASK(64));

    return 0;
}

static struct pci_driver my_pci_driver = {
    .name     = "my_device",
    .id_table = my_pci_ids,
    .probe    = my_pci_probe,
    .remove   = my_pci_remove,
};
module_pci_driver(my_pci_driver);
```

### 6.4 USB 子系统

USB 驱动通过 `usb_driver` 注册，匹配基于 `usb_device_id`：

```c
static struct usb_device_id my_usb_ids[] = {
    { USB_DEVICE(0x1234, 0x5678) },
    { }
};
MODULE_DEVICE_TABLE(usb, my_usb_ids);

static int my_usb_probe(struct usb_interface *interface,
                        const struct usb_device_id *id) {
    struct usb_device *udev = interface_to_usbdev(interface);
    struct usb_host_interface *iface_desc = interface->cur_altsetting;

    // 遍历端点
    for (int i = 0; i < iface_desc->desc.bNumEndpoints; i++) {
        struct usb_endpoint_descriptor *endpoint = &iface_desc->endpoint[i].desc;
        // 配置 endpoint
    }

    return 0;
}

static struct usb_driver my_usb_driver = {
    .name       = "my_device",
    .id_table   = my_usb_ids,
    .probe      = my_usb_probe,
    .disconnect = my_usb_disconnect,
};
module_usb_driver(my_usb_driver);
```

### 6.5 Power Management

`dev_pm_ops` 提供 suspend/resume 回调：

```c
static int my_suspend(struct device *dev) {
    // 保存硬件寄存器状态
    // 关闭时钟
    // 进入低功耗模式
    return 0;
}

static int my_resume(struct device *dev) {
    // 恢复时钟
    // 恢复硬件寄存器状态
    // 重新初始化
    return 0;
}

static const struct dev_pm_ops my_pm_ops = {
    .suspend  = my_suspend,
    .resume   = my_resume,
    .freeze   = my_suspend,  // hibernation
    .thaw     = my_resume,
    .poweroff = my_suspend,
    .restore  = my_resume,
};
```

支持 Runtime PM（运行时电源管理）：

```c
// 在 probe 中启用
pm_runtime_enable(dev);
pm_runtime_set_autosuspend_delay(dev, 1000); // 1秒无活动后挂起
pm_runtime_use_autosuspend(dev);

// 使用时唤醒
pm_runtime_get_sync(dev);
// ... 使用设备 ...
pm_runtime_mark_last_busy(dev);
pm_runtime_put_autosuspend(dev);
```

---

## 7. 总结与实战建议

### 7.1 驱动开发十大原则

1. **始终检查返回值** — `copy_to_user`、`kmalloc`、`request_irq` 都可能失败
2. **优先使用 devm_ API** — 自动资源管理，减少泄漏
3. **用户态指针不可信** — 必须用 `copy_from_user`，不能直接解引用
4. **中断上下文限制** — 不能睡眠、不能持有互斥锁（spinlock 可用）
5. **使用合适的下半部** — 轻量用 tasklet，复杂用 workqueue，推荐 threaded IRQ
6. **并发安全** — 自旋锁、互斥锁、RCU、原子操作选合适的
7. **DMA 注意一致性** — 流式映射需 `dma_sync_*` 同步
8. **正确使用屏障** — 确保 CPU 与设备之间的内存访问顺序
9. **设备树兼容性** — 用 `of_match_table` 支持 DTS
10. **模块卸载安全** — `try_module_get()` / `module_put()` 防止卸载时正在使用

### 7.2 现代 Linux 驱动发展方向

| 传统方式 | 现代方式 |
|----------|----------|
| `request_irq()` | `devm_request_irq()` + threaded IRQ |
| 单队列 request_fn | blk-mq 多队列 |
| 手动资源管理 | devm_ 自动管理 |
| platform_device 手动注册 | Device Tree / ACPI 自动注册 |
| big kernel lock | per-device lock + RCU |
| `class_create` + `device_create` | 自动 devtmpfs |

### 7.3 推荐学习路径

1. 阅读 **Linux Device Drivers, 3rd Edition (LDD3)** — 经典入门（部分内容已过时）
2. 阅读内核源码：`drivers/char/`、`drivers/block/`、`drivers/pci/`
3. 动手写简单的字符设备驱动（内存模拟设备）
4. 用 QEMU + 虚拟设备练习中断和 DMA
5. 给 RPi/BeagleBone 编写 GPIO/I2C 平台驱动

---

*学习日期：2025-07-07*
*参考资料：Linux Kernel Documentation, LDD3, kernel v6.x source code*

# #11 Linux 内核模块开发 & 系统编程实战

> 系统程序员视角：从零构建内核模块，深入理解内核态编程范式
> 预设前10课已掌握进程调度、内存管理、设备驱动、文件系统基础
> 日期：2026-05-13

---

## 1. 内核模块基础

### 1.1 模块是什么？

内核模块（LKM）是可在**运行时**动态加载到内核的代码，无需重新编译内核或重启系统。

**用户态 vs 内核态编程对照：**

| 维度 | 用户态程序 | 内核模块 |
|------|-----------|----------|
| 入口 | `main()` | `module_init()` 宏注册的函数 |
| 退出 | `return`/`exit()` | `module_exit()` 宏注册的函数 |
| 内存空间 | 虚拟地址空间 | 内核地址空间（1:1映射） |
| 库依赖 | glibc/动态链接 | 无libc，只能使用内核导出的API |
| 浮点运算 | 随意使用 | 默认禁止（需额外保存FPU状态） |
| 崩溃影响 | 仅当前进程 | 整个系统panic |
| 调试方式 | gdb/strace | printk/ftrace/kgdb |

### 1.2 模块基本结构

```c
#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>

static int __init my_init(void)
{
    printk(KERN_INFO "Hello, kernel world!\n");
    return 0;
}

static void __exit my_exit(void)
{
    printk(KERN_INFO "Goodbye, kernel!\n");
}

module_init(my_init);
module_exit(my_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Kai");
MODULE_DESCRIPTION("A simple demo module");
MODULE_VERSION("0.1");
```

关键点：
- `MODULE_LICENSE("GPL")` — 缺失或非GPL兼容，内核标记为"污染"，部分API不可用
- `__init`/`__exit` — 告知内核这些函数仅在初始化/清理时使用，可回收内存

### 1.3 模块参数传递

```c
#include <linux/moduleparam.h>
static int debug_level = 0;
static char *device_name = "default_dev";
module_param(debug_level, int, 0644);
module_param(device_name, charp, 0644);
MODULE_PARM_DESC(debug_level, "Debug level (0-3)");
```

加载：`insmod mymodule.ko debug_level=2`
参数出现在 `/sys/module/mymodule/parameters/debug_level`，运行时可通过 `echo` 修改。

### 1.4 Kbuild Makefile

```makefile
obj-m += mymodule.o
KDIR := /lib/modules/$(shell uname -r)/build
PWD  := $(shell pwd)
all:
	$(MAKE) -C $(KDIR) M=$(PWD) modules
clean:
	$(MAKE) -C $(KDIR) M=$(PWD) clean
```

`KDIR` 指向内核源码树，Ubuntu需安装 `linux-headers-$(uname -r)`。

模块符号导出：
```c
EXPORT_SYMBOL(my_function);
EXPORT_SYMBOL_GPL(my_gpl_function);  // 仅GPL模块可用
```

### 1.5 加载/卸载管理

```bash
insmod mymodule.ko           # 简单加载
modprobe mymodule            # 智能加载（自动解决依赖）
rmmod mymodule               # 卸载
lsmod                        # 查看已加载模块
modinfo mymodule.ko          # 模块信息
```

版本校验通过 **vermagic** 机制，不匹配返回 `Invalid module format`。

### 1.6 /proc 与 /sys 文件系统接口

| 接口 | 适用场景 | 优缺点 |
|------|---------|--------|
| `/proc` | 读取内核统计信息 | 简单但不够结构化 |
| `/sys` | 导出设备/驱动属性 | 结构化、统一模型 |
| `ioctl` | 自定义设备控制 | 灵活但需设备文件 |

---

## 2. 字符设备驱动实战

### 2.1 file_operations 结构体

```c
struct file_operations {
    struct module *owner;
    ssize_t (*read)(struct file *, char __user *, size_t, loff_t *);
    ssize_t (*write)(struct file *, const char __user *, size_t, loff_t *);
    int (*open)(struct inode *, struct file *);
    int (*release)(struct inode *, struct file *);
    long (*unlocked_ioctl)(struct file *, unsigned int, unsigned long);
};
```

用户态 `open("/dev/mydev")` → 内核态 `my_open(inode, file)`

### 2.2 主次设备号

```c
// 方式一：手动指定（可能冲突）
register_chrdev_region(MKDEV(MY_MAJOR, 0), 1, "mydev");

// 方式二：动态分配（推荐）
dev_t dev_num;
alloc_chrdev_region(&dev_num, 0, 1, "mydev");
int major = MAJOR(dev_num);
```

### 2.3 cdev 初始化和设备文件创建

```c
#include <linux/cdev.h>
#include <linux/device.h>

static struct cdev my_cdev;
static struct class *my_class;
static struct device *my_device;

// 初始化
cdev_init(&my_cdev, &my_fops);
my_cdev.owner = THIS_MODULE;
cdev_add(&my_cdev, dev_num, 1);

// 自动创建 /dev/ 节点（udev通知）
my_class = class_create(THIS_MODULE, "mydev_class");
my_device = device_create(my_class, NULL, dev_num, NULL, "mydev%d", 0);

// 清理
device_destroy(my_class, dev_num);
class_destroy(my_class);
cdev_del(&my_cdev);
unregister_chrdev_region(dev_num, 1);
```

### 2.4 数据拷贝：用户态 ↔ 内核态

**所有用户态地址必须用专门API访问！** 直接解引用会触发段错误或安全漏洞。

```c
// 正确做法
copy_to_user(buf_user, kernel_buf, count);     // 内核→用户
copy_from_user(kernel_buf, buf_user, count);   // 用户→内核
// 返回值：剩余未拷贝字节数，0=全部成功
```

为什么不能直接解引用？地址空间隔离、缺页处理、SMAP/SMEP硬件保护。

### 2.5 ioctl 实现

命令编码宏：`_IO/_IOR/_IOW/_IOWR(type, nr, data_type)`

```c
#define MYDEV_IOC_MAGIC 'M'
#define MYDEV_RESET    _IO(MYDEV_IOC_MAGIC, 0)
#define MYDEV_GET_STAT _IOR(MYDEV_IOC_MAGIC, 1, struct mydev_stat)

static long my_ioctl(struct file *filp, unsigned int cmd, unsigned long arg)
{
    struct mydev_stat stat;
    switch (cmd) {
    case MYDEV_RESET:
        break;
    case MYDEV_GET_STAT:
        if (copy_to_user((void __user *)arg, &stat, sizeof(stat)))
            return -EFAULT;
        break;
    default:
        return -ENOTTY;
    }
    return 0;
}
```

---

## 3. 内核内存管理

### 3.1 kmalloc vs vmalloc

| 特性 | kmalloc | vmalloc |
|------|---------|---------|
| 物理连续性 | ✅ 物理连续 | ❌ 物理非连续 |
| 分配速度 | 快（slab分配器） | 慢（需构建页表） |
| 最大大小 | ≤4MB | 可达数百MB |
| 是否可睡眠 | 取决于flags | 总是可能睡眠 |
| DMA兼容 | ✅ | ❌ |

```c
void *kmalloc(size_t size, gfp_t flags);
void kfree(const void *ptr);
void *vmalloc(unsigned long size);
void vfree(const void *addr);
```

### 3.2 GFP Flags：上下文决定一切

| 上下文 | 允许的GFP flags |
|--------|-----------------|
| 进程上下文（可睡眠） | GFP_KERNEL（首选） |
| 中断上半部（hardirq） | GFP_ATOMIC |
| 软中断/tasklet | GFP_ATOMIC |
| spinlock持有中 | GFP_ATOMIC |
| mutex持有中 | GFP_KERNEL |

**关键规则：中断上下文只能用 GFP_ATOMIC**

### 3.3 slab 分配器

内核用slab管理小内存对象（kmalloc背后实现）。可自定义slab cache：

```c
struct kmem_cache *my_cache = kmem_cache_create("my_object",
    sizeof(struct my_obj), 0, SLAB_HWCACHE_ALIGN, NULL);
struct my_obj *p = kmem_cache_alloc(my_cache, GFP_KERNEL);
kmem_cache_free(my_cache, p);
kmem_cache_destroy(my_cache);
```

### 3.4 内存池（mempool）

预分配一批内存，在内存压力下保证分配不失败。适用于I/O调度器、块设备驱动等关键路径。

---

## 4. 内核同步机制

### 4.1 选择指南

| 场景 | 机制 | 特性 |
|------|------|------|
| 短临界区，不可睡眠 | spinlock | 自旋等待，关闭抢占 |
| 临界区较长/需睡眠 | mutex | 互斥锁，可睡眠 |
| 读多写少 | RCU | 无锁读，写时复制 |
| 等待事件完成 | completion | 1→1通知 |
| 等待条件成立 | wait queue | 生产者-消费者 |

### 4.2 spinlock — 自旋锁

**关键：持有spinlock期间不能睡眠，不能调用可睡眠函数。**

```c
spin_lock_irqsave(&lock, flags);   // 推荐：禁用中断+保存状态
spin_unlock_irqrestore(&lock, flags);
```

`irqsave` 防止死锁：持有锁时发生中断→中断处理程序尝试获取同一锁→死锁。

### 4.3 mutex — 互斥锁

```c
mutex_lock(&my_mutex);
// 可安全调用copy_from_user等阻塞函数
mutex_unlock(&my_mutex);
```

### 4.4 RCU — Read-Copy-Update

读路径完全无锁，写者创建新副本原子替换指针，等待grace period后释放旧数据。

读多写少场景（路由表、文件系统缓存）的终极优化。

### 4.5 completion & wait queue

- **completion**：1→1通知，`wait_for_completion` / `complete`
- **wait queue**：生产者-消费者，`wait_event_interruptible` / `wake_up_interruptible`

---

## 5. 中断与延时

### 5.1 上半部 vs 下半部

- **上半部（hardirq）**：关中断执行，极短，仅保存数据+调度下半部
- **下半部（deferred work）**：开中断执行，可做大量处理

### 5.2 下半部的层次关系

```
softirq → 高性能但较底层
  └── tasklet → softirq上的友好封装，同一tasklet不会并发
  └── 网络RX/TX → 直接用softirq

workqueue → 内核线程，可以睡眠
threaded IRQ → 一个内核线程处理一个中断
```

### 5.3 Workqueue 使用

```c
// 上半部注册
request_irq(irq_num, my_handler, IRQF_SHARED, "mydev", this_module);

// 上半部调度work
DECLARE_WORK(my_work, work_handler);
schedule_work(&my_work);   // 在进程上下文中执行，可以睡眠

// 自定义workqueue（独立内核线程）
my_wq = alloc_workqueue("my_wq", WQ_UNBOUND, 0);
queue_work(my_wq, &my_work);
```

---

## 6. 调试技术

| 技术 | 用法 | 适用场景 |
|------|------|---------|
| printk | `printk(KERN_INFO "...")` | 最常用，日志在dmesg |
| /proc/sys | 创建proc/sysfs文件 | 运行时查看/修改 |
| ftrace | `echo function > /sys/kernel/debug/tracing/current_tracer` | 函数调用追踪 |
| kprobe | `kprobe` | 动态插入探测点 |
| kgdb | 通过串口/kgdboc | 完整内核调试 |
| panic/oops | 分析内核崩溃信息 | 严重错误诊断 |

查看日志：`dmesg | tail` 或 `cat /var/log/kern.log`

---

## 7. 完整Demo：虚拟字符设备

一个完整的内核模块，实现：
- 动态分配设备号
- 类+设备自动创建 `/dev/` 节点
- `open/read/write/release/ioctl` 全部实现
- safe模式使用 `copy_to_user`/`copy_from_user`
- 使用mutex保护并发访问

完整代码在 `D:\kai_knowledge\code\kernel_demo\virt_char_dev/`
（注：Windows环境用WSL验证，或作为学习参考）

---

## 8. 实验Idea

1. **WSL2中编译内核模块**：WSL2支持内核模块，需重新编译内核启用 `CONFIG_MODULES`
2. **虚拟字符设备**：实现上述完整demo，用 `dd` / `cat` / 用户态程序测试
3. **/proc文件**：创建 `/proc/mydev_stats` 暴露驱动运行统计
4. **等待队列**：实现阻塞读，用户进程在无数据时睡眠
5. **debugfs接口**：通过debugfs开关调试日志级别

---

## 9. 总结

内核模块开发是理解操作系统内部机制的最佳实践路径：

1. **模块结构**：init/exit、参数、LICENSE、Kbuild系统
2. **字符驱动**：file_operations、设备号、cdev、copy_to/from_user
3. **内存管理**：kmalloc/vmalloc/GFP flags/slab/mempool
4. **同步机制**：spinlock/mutex/RCU/completion/wait queue
5. **中断处理**：上半部+下半部(tasklet/workqueue/threaded IRQ)
6. **调试**：printk/ftrace/kprobe/kgdb

**下一方向**：系统设计工程化 — 理论学完10课，可以做mini项目落地。

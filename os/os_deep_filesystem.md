# OS 文件系统深度探秘

> 从 VFS 抽象到底层磁盘布局，从 EXT4/XFS/Btrfs 到页缓存与 I/O 栈，深入理解操作系统的文件系统全貌。

---

## 1. VFS — 虚拟文件系统层

VFS（Virtual File System）是 Linux 内核中最优雅的抽象之一。它定义了一套通用的文件模型，让上层应用程序可以无视底层文件系统的差异，统一使用 `open/read/write/close` 系统调用。

### 1.1 四大核心对象

| 对象 | 含义 | 生命周期 | 关键字段 |
|---|---|---|---|
| **super_block** | 超级块，描述已挂载文件系统 | 挂载到卸载 | s_type(文件系统类型)、s_root(根dentry)、s_blocksize |
| **inode** | 索引节点，描述一个文件/目录的元数据 | 文件创建到删除 | i_mode(权限)、i_uid、i_size、i_blocks、i_op、i_fop |
| **dentry** | 目录项，路径名与 inode 的缓存映射 | 路径解析后存在 dcache 中 | d_name(文件名)、d_parent(父目录)、d_inode |
| **file** | 打开文件描述，进程视角的打开文件 | open() 到 close() | f_dentry、f_op、f_pos(文件偏移) |

**关键关系：**
```
进程 fd 表 → struct file → struct dentry → struct inode → 磁盘数据
```

多个 `file` 可以通过同一个 `dentry` 指向同一个 `inode`（同一文件被多次打开时）。硬链接则是一个 `dentry` 指向另一个 inode。

### 1.2 操作集合

VFS 将操作抽象为两个主要结构体：

```c
// inode 级别的操作（创建/删除/重命名文件/目录等）
struct inode_operations {
    struct dentry *(*lookup)(struct inode *, struct dentry *, unsigned int);
    int (*create)(struct inode *, struct dentry *, umode_t, bool);
    int (*link)(struct dentry *, struct inode *, struct dentry *);
    int (*unlink)(struct inode *, struct dentry *);
    int (*mkdir)(struct inode *, struct dentry *, umode_t);
    int (*rmdir)(struct inode *, struct dentry *);
    int (*rename)(struct inode *, struct dentry *, ...);
    int (*setattr)(struct dentry *, struct iattr *);
};

// 文件级别的操作（读/写/定位/内存映射等）
struct file_operations {
    loff_t (*llseek)(struct file *, loff_t, int);
    ssize_t (*read)(struct file *, char __user *, size_t, loff_t *);
    ssize_t (*write)(struct file *, const char __user *, size_t, loff_t *);
    int (*mmap)(struct file *, struct vm_area_struct *);
    int (*open)(struct inode *, struct file *);
    int (*release)(struct inode *, struct file *);
    int (*fsync)(struct file *, loff_t, loff_t, int);
};
```

每个文件系统提供自己的 `inode_operations` 和 `file_operations` 实现，VFS 通过函数指针调用，实现**多态**。

### 1.3 文件系统注册与挂载

```
register_filesystem(struct file_system_type *fs_type)
    ↓
挂载时调用 mount() → fs_type->mount()
    ↓
返回 super_block → 关联到 vfsmount
    ↓
dentry 解析挂载点
```

典型的 VFS 路径解析过程（以 `/usr/share/file.txt` 为例）：

1. 从当前进程的 `fs->root` 获取根 dentry
2. 逐层 `dentry->d_inode->i_op->lookup()` 查找子项
3. 缓存结果到 dcache（目录项缓存）
4. 最终 `dentry` 绑定到目标 inode
5. 返回 `file` 结构体给进程

---

## 2. Linux 主流文件系统

### 2.1 EXT4 — 成熟可靠的全能战士

EXT4 是目前 Linux 的默认文件系统，是 EXT3 的继任者。

#### 磁盘布局

```
+--------+--------+--------+--------+--------+--------+
| Boot   | Block  | Block  |  ...   | Block  | Block  |
| Sector | Group0 | Group1 |        | GroupN | GroupN |
+--------+--------+--------+--------+--------+--------+
```

每个块组（Block Group）结构：
```
+----------+----------+----------+----------+-----------+
| Super    | Group    | Block    | Inode    | Inode     | Data   |
| Block    | Descr    | Bitmap   | Bitmap   | Table     | Blocks |
+----------+----------+----------+----------+-----------+
```

#### inode 结构

inode 占用 256 字节（默认可配置），前 15 个 block 指针：
- 前 12 个：**直接块指针**（直接访问数据块）
- 第 13 个：**一级间接块指针**（指向一个块，块内全是块指针）
- 第 14 个：**二级间接块指针**（指向一个块，该块内全是"一级间接块指针"）
- 第 15 个：**三级间接块指针**

对于 4KB 块大小、指针占 4 字节：
- 直接可访问：12 × 4KB = 48KB
- 一级间接：4096/4 × 4KB = 4MB
- 二级间接：1024 × 1024 × 4KB = 4GB
- 三级间接：1024 × 1024 × 1024 × 4KB = 4TB

#### Extent 树（EXT4 重要特性）

对于大文件，EXT4 引入了 extent（扩展区）替代传统块映射：
- 一个 extent 描述一段连续的物理块区：[起始块号, 长度]
- 4 字节的 extent 可覆盖 128MB（4KB 块大小下：32768 个连续块）
- extent 组织成 Htree（B-tree 变体），深度通常为 2

```c
struct ext4_extent {
    __le32  ee_block;   // 逻辑块号
    __le16  ee_len;     // extent 长度
    __le16  ee_start_hi;// 起始物理块号高16位
    __le32  ee_start_lo;// 起始物理块号低32位
};
```

#### JBD2 日志

EXT3/4 使用 JBD2（Journaling Block Device 2）实现元数据日志：
- **三种日志模式**：journal（全数据日志）、ordered（仅元数据日志，数据先落盘）、writeback（仅元数据日志，数据延迟落盘）
- **日志事务**：原子操作，一组 block 要么全部写入，要么回滚
- 日志存储在单独的文件（`.journal`）或内嵌的日志区域

#### 延迟分配与多块分配

- **Delayed Allocation**：`write()` 时不分配磁盘块，仅在 `writeback` 时分配，让内核看到更多脏页，做出更好的连续分配决策
- **mballoc**：多块分配器，一次分配连续块组，减少碎片

### 2.2 XFS — 高性能大文件专家

XFS 由 SGI 开发，为大规模并行 I/O 设计，2001 年移植到 Linux。

#### 核心设计

- **分配组（Allocation Group）**：将磁盘分为多个 AG，每个 AG 独立管理自己的空间，支持并行访问
- **B+ 树管理一切**：inode、空闲空间、目录条目全部使用 B+ 树
- **延迟日志**：日志先写入内存缓冲区，累积后再批量化提交，减少 I/O
- **动态 inode 分配**：inode 按需分配，不预先保留固定数量的 inode 槽位

#### 关键数据结构

- **AG header**：包含 AGF（空闲空间信息）、AGI（inode 信息）、AGFL（空闲列表）
- **B+ 树索引**：inode B+ 树按 inode 号索引，空闲空间 B+ 树按块号/大小双重索引
- **日志**：通过循环缓冲区实现，日志条目包含事务号和校验码

#### XFS 优势场景

- 大文件读写（文件可以大到 8EiB）
- 高并发（多 AG 并行）
- 大规模目录（B+ 树目录，百万级文件）

### 2.3 Btrfs — 写时复制的新一代文件系统

Btrfs（B-tree File System）由 Oracle 开发，目标是提供类似 ZFS 的高级功能。

#### 写时复制（Copy-on-Write, COW）

修改数据时，不覆盖原位置，而是在新位置写入，更新元数据指针：
- **快照**：O(1) 时间创建子卷的快照，仅复制元数据根指针
- **校验和**：数据和元数据都有 CRC32/SHA256 校验，静默数据损坏可检测
- **碎片问题**：COW 会导致更严重的碎片，需要定期 `btrfs filesystem defragment`

#### 子卷与快照

```
顶级子卷 (subvolid=5)
├── @ (根文件系统)
│   ├── home
│   └── var
├── @home
└── @snapshots
    ├── @_20240101
    └── @home_20240101
```

- 子卷可以独立挂载
- 快照就是子卷的 COW 副本
- 支持只读/可读写快照

#### 其他特性

- **在线碎片整理**：`btrfs filesystem defragment`
- **在线压缩**：zlib/lzo/zstd 可选
- **RAID 支持**：软件 RAID 0/1/5/6/10
- **数据平衡**：`btrfs balance` 重新分配数据

---

## 3. 页缓存 & I/O 栈

### 3.1 页缓存（Page Cache）

页缓存是内核最核心的缓存机制，它将磁盘数据缓存在物理内存中。

#### 核心结构

```
address_space（每个 inode 一个）
├── i_mmap（共享映射的 vm_area_struct）
├── page_tree / xarray（页缓存树，存储所有缓存页）
└── a_ops（地址空间操作：readpage/writepage/releasepage）
```

**内核 xarray**（从 Linux 4.20 起替代 radix tree）：
- 更好的 RCU 支持（无锁读）
- 更紧凑的内存布局
- 支持任何类型的指针存储

#### 页缓存读流程

```
read() 系统调用
  → 检查 page_tree 中是否有缓存页
  → 命中：直接返回（Page Cache Hit）
  → 未命中：触发 page fault
    → 分配新页
    → a_ops->readpage() 从磁盘读入
    → 加入 page_tree
    → 返回数据给用户
```

### 3.2 回写机制

Linux 的脏页回写由 `writeback` 机制管理（内核线程，替代了早期的 pdflush）：

**触发条件：**
1. 脏页比例超过 `dirty_background_ratio`（默认 10%）→ 后台刷出
2. 脏页比例超过 `dirty_ratio`（默认 20%）→ 同步阻塞写入
3. 脏页存在超过 `dirty_expire_centisecs`（默认 30 秒）
4. 调用 `sync()` / `fsync()` 显式刷出

**关键参数（`/proc/sys/vm/`）：**
```
dirty_background_ratio = 10    # 后台刷出阈值（%总内存）
dirty_ratio = 20              # 同步阻塞阈值
dirty_expire_centisecs = 3000 # 脏页过期时间（1/100秒）
dirty_writeback_centisecs = 500 # 回写线程唤醒间隔
```

### 3.3 直接 I/O vs 缓冲 I/O

| 特性 | 缓冲 I/O（默认） | 直接 I/O（O_DIRECT） |
|---|---|---|
| 页缓存 | 使用 | 绕过 |
| 内存拷贝 | 从 page cache 拷贝到用户缓冲区 | 直接从设备到用户缓冲区（DMA） |
| 写入保证 | 不保证立即落盘 | 保证写完即落盘 |
| 对齐要求 | 无 | 块大小对齐 |
| 吞吐量 | 小文件快 | 大文件快，但绕过缓存 |

### 3.4 I/O 调度器

当多个进程并发 I/O 时，调度器决定请求的顺序：

| 调度器 | 特点 | 适用场景 |
|---|---|---|
| **noop** | FIFO + 简单合并 | 纯 SSD/NVMe |
| **deadline** | 每个请求有截止时间，读写分别排队 | 通用，有延迟保障 |
| **CFQ** | 完全公平队列，每个进程分配时间片 | HDD，桌面系统 |
| **mq-deadline** | deadline 的多队列版本 | 现代高速存储 |
| **BFQ** | 音频/桌面友好，低延迟 | 交互式系统 |

### 3.5 io_uring — 现代异步 I/O

Linux 5.1 引入的革命性异步 I/O 框架：

```
SQ 环（提交队列）          CQ 环（完成队列）
┌──────────────┐          ┌──────────────┐
│  SQE          │  submit  │  CQE          │
│  SQE          │ ────────→│  CQE          │
│  SQE          │  syscall  │  CQE          │
│  SQE          │          │  CQE          │
└──────────────┘          └──────────────┘
```

**核心优势：**
- **零系统调用开销**（提交多个请求只需一次 `io_uring_enter`）
- **共享内存环形缓冲区**（用户态和内核态共享 SQ/CQ 环）
- **支持缓冲 I/O 和直接 I/O**
- **支持 poll 模式**：完全跳过中断处理

---

## 4. 文件系统关键机制

### 4.1 碎片整理

**EXT4 碎片整理：**
- **在线**：`e4defrag /path`（对单个文件/目录整理）
- **离线**：`e2fsck -f /dev/sda1 && resize2fs /dev/sda1` 或 `dump/restore`

**XFS：**
- 使用 `xfs_fsr`（文件系统重组器），对碎片化文件进行迁移

**Btrfs：**
- `btrfs filesystem defragment -r /path` 在线整理

### 4.2 fsck — 文件系统检查

fsck（file system check）运行在几个阶段：

```
阶段1：检查 inode（类型/权限/链接计数）
阶段2：检查目录条目（dentry 的有效性）
阶段3：检查目录连接（含孤儿 inode）
阶段4：检查引用计数（inode 的 i_nlink）
阶段5：检查块位图（super_block 中的位图一致性）
```

EXT4 的 `e2fsck` 还会进行 **inode 扫描** 来修复损坏的 inode 表。

### 4.3 Quota — 磁盘配额

Linux 支持用户/组级别的磁盘配额：
- **硬限制**：超过即报错（EDQUOT）
- **软限制**：允许超过，但有宽限期
- **inode 配额**：限制文件数量
- **block 配额**：限制磁盘空间

### 4.4 ACL / 扩展属性

**ACL（Access Control List）**：
- 在传统 `rwx` 权限之外提供更细粒度的访问控制
- 每个文件可以有多个 user/group 条目
- POSIX ACL 和 NFSv4 ACL 两种标准

**扩展属性（xattr）**：
- `user.*`：用户空间使用（如 Samba 的 DOS 属性、桌面应用的元数据）
- `system.*`：内核使用（如 ACL、CAPABILITY）
- `security.*`：安全模块（SELinux、AppArmor）

---

## 5. 总结与对比

### 三大文件系统横向对比

| 特性 | EXT4 | XFS | Btrfs |
|---|---|---|---|
| 诞生年份 | 2008 | 2001（Linux移植） | 2009 |
| 最大文件 | 16TB | 8EiB | 16EiB |
| 最大分区 | 1EiB | 8EiB | 16EiB |
| inode分配 | 静态（格式化时确定） | 动态 | 动态 |
| 日志 | JBD2（元数据/数据） | 延迟日志 | COW替代日志 |
| 校验和 | 仅元数据 | 元数据（v5 superblock） | 数据+元数据 |
| 快照 | ❌ | ❌（需要LVM） | ✅ 原生支持 |
| 压缩 | ❌ | ❌ | ✅ 在线压缩 |
| SSD优化 | discard/noatime | discard | COW+校验和 |
| 碎片防护 | extent + 延迟分配 | B+树连续空间分配 | COW导致碎片 |

### 核心思路

1. **VFS** 是所有文件系统的统一接口层，理解它等于理解了 Linux 的一切文件操作
2. **EXT4** 的设计做了大量折中：静态 inode 保证性能但浪费空间，extent 树加速大文件但小文件使用传统块映射
3. **XFS** 的 B+树和分配组设计从一开始就为并发和大文件而生
4. **Btrfs** 通过 COW 实现对磁盘状态的"事务性管理"，压缩/校验/快照都是 COW 的自然延伸
5. **页缓存**是文件性能的核心，理解脏页回写机制能避免"数据丢失"和"OOM杀进程"
6. **io_uring** 正在重塑 Linux I/O 模型，从系统调用到共享内存环形缓冲区，效率跨越式提升

---

*本笔记由 AI 辅助基于 Linux 内核源码、各文件系统文档以及实操经验整理，2025年。*

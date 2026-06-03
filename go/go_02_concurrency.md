# Go 并发深度：GMP、Channel、sync 包源码

## GMP 模型

- **G** = goroutine（轻量线程，栈 2KB 起步，可动态增长）
- **M** = machine（OS 线程，与 CPU 核数对应）
- **P** = processor（调度上下文，默认 GOMAXPROCS 个）

```
Goroutine 创建 → 本地队列(P.local) → 全局队列 → 工作窃取
M 阻塞 → 创建/唤醒新的 M → P 解绑 → P 绑定其他 M
```

- **工作窃取**：某个 P 的本地队列空时，从其他 P 或全局队列偷 G
- **系统调用**：G 进入 syscall → M 阻塞 → P 交出 → 其他 M 绑定 P 继续
- **netpoller**：网络 IO 的 G 通过 epoll/kqueue 异步唤醒，不阻塞 M

## channel 底层（hchan）

```go
// runtime/chan.go 简化
type hchan struct {
    qcount   uint           // 缓冲区元素数
    dataqsiz uint           // 缓冲区大小
    buf      unsafe.Pointer // 环形缓冲区指针
    elemsize uint16
    sendx    uint           // 发送索引
    recvx    uint           // 接收索引
    recvq    waitq          // 接收等待队列（sudog 链表）
    sendq    waitq          // 发送等待队列
    lock     mutex
}
```

**CSP 模型**：不通过共享内存通信，通过通信共享内存。

## sync.Mutex 饥饿模式

```go
// 正常模式：自旋 + CAS 尝试获取锁
// 饥饿模式：goroutine 等待超过 1ms 或队列尾部
//   → 直接排队，新 goroutine 不自旋不尝试
//   → 保证公平，防止 goroutine "饿死"
//
// 源码入口: src/sync/mutex.go
func (m *Mutex) Lock() {
    // 快速路径: CAS 直接获取
    if atomic.CompareAndSwapInt32(&m.state, 0, mutexLocked) {
        return
    }
    m.lockSlow() // 慢路径：自旋/阻塞/饥饿处理
}
```

## sync.RWMutex

```go
type RWMutex struct {
    w           Mutex  // 写锁互斥
    writerSem   uint32 // 写等待信号量
    readerSem   uint32 // 读等待信号量
    readerCount int32  // 正=读计数，负=有写者等待
    readerWait  int32  // 写者需等待的读者数
}
// 写锁获取：锁定 w + readerCount 设为负数 → 等待现有读者完成
// 读锁获取：readerCount+1 → 如果为负（有写者等待）→ 阻塞
```

## sync.Once

```go
type Once struct {
    done uint32
    m    Mutex
}
func (o *Once) Do(f func()) {
    if atomic.LoadUint32(&o.done) == 0 {
        o.doSlow(f)
    }
}
func (o *Once) doSlow(f func()) {
    o.m.Lock()
    defer o.m.Unlock()
    if o.done == 0 {
        defer atomic.StoreUint32(&o.done, 1)
        f()
    }
}
// 双重检查锁定（Double-checked Locking）
```

## sync.WaitGroup

```go
type WaitGroup struct {
    noCopy noCopy
    state1 [12]byte // 高8位=计数器+等待数，低4位=信号量
}
// Add(delta) → 原子操作更新计数器
// Done() → Add(-1) → 计数器归零时触发信号量唤醒所有等待者
// Wait() → 检查计数器，非0则阻塞于信号量
```

## 关键代码片段

```go
// 扇出扇入模式
func fanOut(ch <-chan int, n int) []<-chan int {
    cs := make([]<-chan int, n)
    for i := 0; i < n; i++ {
        cs[i] = worker(ch)
    }
    return cs
}

func merge(cs ...<-chan int) <-chan int {
    out := make(chan int)
    var wg sync.WaitGroup
    for _, c := range cs {
        wg.Add(1)
        go func(ch <-chan int) {
            defer wg.Done()
            for v := range ch {
                out <- v
            }
        }(c)
    }
    go func() { wg.Wait(); close(out) }()
    return out
}
```

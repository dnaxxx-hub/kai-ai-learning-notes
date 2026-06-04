# 嵌入式 C 深度：第 1 课

> 从 MCU 裸机到上位机模拟，理解底层硬件抽象在 C 中的表达。

---

## 一、中断系统原理

### 1.1 中断向量表

ARM Cortex-M 使用向量表中断，前 16 项为系统异常，之后为外设中断（IRQ）。

```c
/* ARM Cortex-M 向量表布局（链接脚本中定义） */
typedef void (*isr_t)(void);

__attribute__((section(".isr_vector")))
isr_t __isr_vector[] = {
	(isr_t)0x20001000,    /* 栈顶 */
	[1]  = _reset,        /* Reset */
	[2]  = _nmi,
	[3]  = _hard_fault,
	/* ... */
	[16] = TIM2_IRQHandler,    /* IRQ0 */
	[17] = TIM3_IRQHandler,    /* IRQ1 */
};
```

### 1.2 中断使能与现场保护

```c
static inline void irq_enable(void)
{
	__asm volatile("cpsie i" ::: "memory");
}

static inline void irq_disable(void)
{
	__asm volatile("cpsid i" ::: "memory");
}

void TIM2_IRQHandler(void)
{
	/* 硬件已自动压栈: R0-R3, R12, LR, PC, xPSR */
	if (TIM2->SR & TIM_SR_UIF) {
		TIM2->SR &= ~TIM_SR_UIF;       /* 清标志 */
		systick_callback();
	}
}
```

### 1.3 ARM vs Windows 模拟

| 特性 | ARM Cortex-M | Windows 模拟 |
|------|-------------|-------------|
| 中断入口 | 硬件查向量表跳转 | `signal()` / `SetUnhandledExceptionFilter` |
| 现场保护 | 硬件自动压栈（8 字） | 不自动，需 `setjmp/longjmp` 手动保存 |
| 优先级 | 内置 NVIC（256 级抢占） | 无硬件优先级，模拟层自行调度 |
| 临界区 | `cpsid i` 全局关中断 | `EnterCriticalSection` 或 `InterlockedExchange` |
| 嵌套深度 | 硬件自动记录 BASEPRI | 手动维护嵌套计数 |

**模拟层推荐：** 用 `CRITICAL_SECTION` 替代关中断，用回调表模拟向量表。

---

## 二、定时器编程与软件定时器

### 2.1 硬件定时器配置

以 STM32 TIM2 为例：

```c
#define TIM2_BASE	0x40000000UL

struct tim_regs {
	volatile uint32_t CR1;
	volatile uint32_t CR2;
	volatile uint32_t SMCR;
	volatile uint32_t DIER;
	volatile uint32_t SR;
	volatile uint32_t EGR;
	volatile uint32_t CCMR1;
	volatile uint32_t CCMR2;
	volatile uint32_t CCER;
	volatile uint32_t CNT;
	volatile uint32_t PSC;
	volatile uint32_t ARR;
};

#define TIM2	((struct tim_regs *)TIM2_BASE)

void timer_init(void)
{
	/* 72 MHz / (7199 + 1) = 10 kHz -> 100 us/tick */
	TIM2->PSC = 7199;
	TIM2->ARR = 9999;          /* 100 us * 10000 = 1 s 溢出 */
	TIM2->DIER |= TIM_DIER_UIE;/* 使能更新中断 */
	TIM2->CR1  |= TIM_CR1_CEN; /* 启动 */
}
```

### 2.2 软件定时器 —— slist 管理

软件定时器通过单向链表（slist）管理。每个定时器是一个节点，超时或周期到达时触发回调。

```c
struct sw_timer {
	struct sw_timer *next;
	uint32_t        expire;    /* 绝对 tick */
	uint32_t        period;    /* 0 = 一次性, >0 = 周期 */
	void (*cb)(void *arg);
	void            *arg;
};

static struct sw_timer *timer_head;   /* slist 头指针 */
static volatile uint32_t system_tick; /* 1 ms 递增 */

void sw_timer_add(struct sw_timer *t, uint32_t delay_ms,
		  uint32_t period_ms, void (*cb)(void *), void *arg)
{
	uint32_t save = irq_save();          /* 关中断 */
	t->expire = system_tick + delay_ms;
	t->period = period_ms;
	t->cb     = cb;
	t->arg    = arg;
	t->next   = timer_head;              /* 头插 */
	timer_head = t;
	irq_restore(save);
}

void sw_timer_tick(void)
{
	struct sw_timer *t = timer_head;
	uint32_t now = system_tick;

	while (t) {
		if (now >= t->expire) {
			t->cb(t->arg);             /* 触发回调 */
			if (t->period)
				t->expire = now + t->period; /* 续期 */
			else
				sw_timer_del(t);     /* 一次性，摘除 */
		}
		t = t->next;
	}
}
```

> **ARM 注意：** 所有共享数据的操作（链表修改）必须关中断保护。在 Windows 模拟层，`irq_save/irq_restore` 映射为 `CRITICAL_SECTION`。

### 2.3 精度差异

| 平台 | 硬件定时器精度 | 软件定时器最小粒度 |
|------|--------------|-----------------|
| Cortex-M | 1~10 us (APB timer) | 1 ms (主循环轮询) |
| Windows | 1~15 ms (timeGetTime) | ~15 ms (WM_TIMER) |
| Windows (高精度) | 0.5 us (QueryPerformanceCounter) | 1 ms (多媒体定时器) |

---

## 三、内存映射寄存器与 volatile

### 3.1 为什么加 volatile

```c
/* 错误：编译器优化会死循环 */
uint32_t *flag = (uint32_t *)0x40020000;
while (*flag == 0)   /* 编译器可能只读一次 !!! */
	;

/* 正确：每次都从外设读取 */
volatile uint32_t *flag = (volatile uint32_t *)0x40020000;
while (*flag == 0)
	;
```

`volatile` 告诉编译器：
- 禁止将该变量的访问优化掉
- 每次使用都从内存/外设地址重新读取
- 禁止两次读/写操作的合并

### 3.2 典型外设寄存器封装

```c
/* GPIOC 输出寄存器封装 */
#define GPIOC_BASE	0x40011000UL

struct gpio_regs {
	volatile uint32_t CRL;     /* 0x00 */
	volatile uint32_t CRH;     /* 0x04 */
	volatile uint32_t IDR;     /* 0x08 */
	volatile uint32_t ODR;     /* 0x0C */
	volatile uint32_t BSRR;    /* 0x10 */
	volatile uint32_t BRR;     /* 0x14 */
	volatile uint32_t LCKR;    /* 0x18 */
};

#define GPIOC	((struct gpio_regs *)GPIOC_BASE)

void led_on(void)
{
	GPIOC->BSRR = (1 << 13);   /* BSRR 写 1 置位 */
}

void led_off(void)
{
	GPIOC->BRR = (1 << 13);    /* BRR 写 1 复位 */
}
```

### 3.3 位带操作（ARM Cortex-M3/4 特有）

```c
/* 将外设地址 0x4001100C 的第 13 位映射到位带别名区 */
#define BITBAND_PERI(addr, bit) \
	((volatile uint32_t *)(0x42000000UL + \
	 ((uint32_t)(addr) - 0x40000000UL) * 32 + (bit) * 4))

/* 原子级位操作 */
*BITBAND_PERI(&GPIOC->ODR, 13) = 1;  /* 单指令置位 */
```

**Windows 模拟：** 没有位带，改用 `reg |= BIT(x)` + `reg &= ~BIT(x)`。

---

## 四、DMA + 环形缓冲区

### 4.1 环形缓冲区数据结构

```c
struct ringbuf {
	uint8_t         *buf;      /* 内存池 */
	volatile size_t  head;     /* 写指针 (DMA 写入端) */
	volatile size_t  tail;     /* 读指针 (CPU 读取端) */
	size_t           size;     /* 必须是 2 的幂 */
};

static inline bool ringbuf_empty(const struct ringbuf *r)
{
	return r->head == r->tail;
}

static inline size_t ringbuf_avail(const struct ringbuf *r)
{
	return r->size - (r->head - r->tail);  /* 模运算由 2 的幂保证 */
}

static inline void ringbuf_put(struct ringbuf *r, uint8_t b)
{
	r->buf[r->head & (r->size - 1)] = b;   /* 按位与代替取模 */
	r->head++;
}
```

### 4.2 DMA 与环形缓冲区联动

DMA 从外设（如 UART）接收数据，自动写入环形缓冲区，CPU 仅在主循环中消费。

```c
/* DMA 完成中断 —— 写入环形缓冲区 */
void DMA1_Channel5_IRQHandler(void)
{
	if (DMA1->ISR & DMA_ISR_TCIF5) {
		DMA1->IFCR |= DMA_IFCR_CTCIF5;
		ringbuf_put(&rx_ring, dma_rx_byte);  /* 单字节入队 */
		/* 重新触发 DMA 单次传输 */
		DMA1->CCR5 |= DMA_CCR5_EN;
	}
}

/* 主循环消费 */
void uart_poll(void)
{
	uint8_t byte;

	while (!ringbuf_empty(&rx_ring)) {
		byte = rx_ring.buf[rx_ring.tail & (rx_ring.size - 1)];
		rx_ring.tail++;
		process_byte(byte);
	}
}
```

### 4.3 ARM vs Windows 模拟

| 特性 | ARM Cortex-M | Windows 模拟 |
|------|-------------|-------------|
| DMA 控制器 | 硬件 DMA，自动搬运 | `CreateThread` + 内存复制模拟 |
| 中断与主循环同步 | 中断写 head，主循环读 tail | 高精度线程写，主线程读 |
| 缓存一致性 | Cortex-M3+ 无 D-cache 问题 | x86 TSO 模型，无需 mfence |
| 内存屏障 | `__DSB()` / `__DMB()` | `MemoryBarrier()` / `_ReadWriteBarrier` |
| 典型速率 | UART: 115200 bps (DMA 零中断) | 模拟: 串口文件读写，速率不限 |

### 4.4 关键：2 的幂加速

```c
/* 除法和取模 -> 移位和按位与 */
index = r->head % size;       /* 通用: 除法，慢 */
index = r->head & (size - 1); /* size=2^n: 与运算，1 指令 */
```

ARM Cortex-M 无硬件除法器（M0/M3）或除法慢（M4），此优化显著。

---

## 五、总结：裸机思维 vs 模拟思维

| 裸机概念 | C 语言工具 | Windows 映射 |
|---------|-----------|-------------|
| 中断 | ISR 函数 + 向量表 | Win32 callback / thread signal |
| 临界区 | `cpsid i` / `cpsie i` | `CRITICAL_SECTION` / `InterlockedXxx` |
| 寄存器 | `volatile` 指针强转 | 虚拟地址映射或模拟结构体 |
| DMA | 外设寄存器配置 | `memcpy` 模拟 + 线程同步 |
| 时间 | SysTick 定时器 | `QueryPerformanceCounter` |

> 写的每一行 C，要么在裸金属上直接控制硬件，要么在 OS 上模拟硬件。
> 理解底层表达，方能写出跨平台健壮的嵌入式 C。

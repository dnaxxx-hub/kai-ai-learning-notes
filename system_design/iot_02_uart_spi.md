# IoT 第2课：UART & SPI 通信

> 嵌入式串行通信基础：UART 异步收发与 SPI 同步总线

---

## 一、UART

### 1.1 基本原理

UART（Universal Asynchronous Receiver/Transmitter）是**异步串行**通信协议。

- TX → RX（交叉连接）
- 无时钟线，双方约定相同**波特率**
- 帧格式：起始位(0) + 数据位(5~8) + 校验位(可选) + 停止位(1/2)

```
空闲  起始   D0  D1  D2  D3  D4  D5  D6  D7  停止  空闲
 ─────┐   ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐   ───
       └──┘ └──┘ └──┘ └──┘ └──┘ └──┘ └──┘ └──┘ └──┘
        ↑ LSB first
```

### 1.2 硬件寄存器（ARM Cortex-M）

以 STM32 USART1 为例，寄存器映射：

```c
// 寄存器基地址 + 偏移（ARM 物理地址）
struct uart_regs {
        volatile uint32_t SR;   // 0x00 状态寄存器
        volatile uint32_t DR;   // 0x04 数据寄存器
        volatile uint32_t BRR;  // 0x08 波特率寄存器
        volatile uint32_t CR1;  // 0x0C 控制寄存器1
        volatile uint32_t CR2;  // 0x10 控制寄存器2
        volatile uint32_t CR3;  // 0x14 控制寄存器3
};
#define USART1 ((struct uart_regs *)0x40011000)
```

发送一个字节（轮询）：

```c
void uart_putc(char c)
{
        while (!(USART1->SR & (1 << 7)))  // 等待 TXE（发送缓冲区空）
                ;
        USART1->DR = c;
}
```

接收一个字节（轮询）：

```c
char uart_getc(void)
{
        while (!(USART1->SR & (1 << 5)))  // 等待 RXNE（接收非空）
                ;
        return USART1->DR & 0xFF;
}
```

### 1.3 用 libkds rbuf 做 FIFO

`rbuf` 是一个 ring buffer，头文件 `libkds/rbuf.h`。uart 中断收发示例：

```c
#include <libkds/rbuf.h>

#define RBUF_SZ 64
struct kds_rbuf rx_fifo;

void uart_isr(void)
{
        char c = USART1->DR & 0xFF;     // 硬件读
        kds_rbuf_push(&rx_fifo, c);     // 推入 FIFO
}

char uart_read(void)
{
        while (kds_rbuf_empty(&rx_fifo))
                ;                        // 等待 FIFO 非空
        return kds_rbuf_pop(&rx_fifo);   // 从 FIFO 弹出
}
```

初始化与配置：

```c
void uart_init(int baud)
{
        USART1->BRR = 8000000 / baud;   // 8MHz 时钟
        USART1->CR1 = (1 << 13) |        // UE: 使能 USART
                      (1 << 3)  |        // TE: 发送使能
                      (1 << 2)  |        // RE: 接收使能
                      (1 << 5);          // RXNEIE: 接收中断
        kds_rbuf_init(&rx_fifo, RBUF_SZ);
}
```

**对比总结：**

| 方式 | 优点 | 缺点 |
|------|------|------|
| 轮询寄存器 | 简单、无依赖 | CPU 空转、丢数据 |
| 中断 + FIFO | 高效、不丢数据 | 需中断 + ring buffer |

---

## 二、SPI

### 2.1 基本原理

SPI（Serial Peripheral Interface）是**同步**全双工总线。

- **SCLK** — 时钟（Master 产生）
- **MOSI** — Master Out Slave In
- **MISO** — Master In Slave Out
- **CS** — Chip Select（片选，低电平有效）

```
Master ──SCLK──→ Slave
        ──MOSI──→
        ←─MISO───
        ──CS────→ (每设备一根)
```

### 2.2 SPI 四种模式（CPOL / CPHA）

由时钟极性 CPOL 和相位 CPHA 决定：

| 模式 | CPOL | CPHA | 采样沿 | 数据输出沿 |
|------|------|------|--------|------------|
| 0    | 0    | 0    | 上升沿 | 下降沿 |
| 1    | 0    | 1    | 下降沿 | 上升沿 |
| 2    | 1    | 0    | 下降沿 | 上升沿 |
| 3    | 1    | 1    | 上升沿 | 下降沿 |

直观记忆：

```
Mode 0: 空闲低 → 上升沿采样 (最常见)
Mode 3: 空闲高 → 上升沿采样
```

CPOL = 空闲电平；CPHA = 0 时第一个边沿采样，CPHA = 1 时第二个边沿采样。

### 2.3 ARM 寄存器（SPI 硬件）

以 STM32 SPI1 为例：

```c
struct spi_regs {
        volatile uint32_t CR1;   // 0x00 控制寄存器1
        volatile uint32_t CR2;   // 0x04 控制寄存器2
        volatile uint32_t SR;    // 0x08 状态寄存器
        volatile uint32_t DR;    // 0x0C 数据寄存器
        volatile uint32_t CRCPR; // 0x10 CRC 多项式
        volatile uint32_t RXCRCR;// 0x14 接收 CRC
        volatile uint32_t TXCRCR;// 0x18 发送 CRC
};
#define SPI1 ((struct spi_regs *)0x40013000)
```

SPI 配置（模式0，8位，Master）：

```c
void spi_init(void)
{
        SPI1->CR1 = (1 << 2)  |        // Master
                    (1 << 3)  |        // 8-bit
                    (0 << 0);          // CPOL=0, CPHA=0 → Mode 0
        SPI1->CR1 |= (1 << 6);         // SPI 使能
}
```

SPI 收发一个字节（硬件）：

```c
uint8_t spi_xfer(uint8_t tx)
{
        while (!(SPI1->SR & (1 << 1))) // 等待 TXE
                ;
        SPI1->DR = tx;                  // 写入发送
        while (!(SPI1->SR & (1 << 0))) // 等待 RXNE
                ;
        return SPI1->DR;                // 读取接收
}
```

读取传感器示例（CS 手动控制）：

```c
uint8_t spi_read_reg(uint8_t addr)
{
        GPIO_CS_LOW();                  // 拉低片选
        spi_xfer(addr);                  // 发送寄存器地址
        uint8_t val = spi_xfer(0xFF);   // 发送 dummy 同时读回
        GPIO_CS_HIGH();                 // 拉高片选
        return val;
}
```

### 2.4 Bit-bang 实现 SPI

在没有硬件 SPI 外设时，用 GPIO 模拟（bit-bang）。

引脚定义：

```c
#define SCK_PIN  0
#define MOSI_PIN 1
#define MISO_PIN 2
#define CS_PIN   3
#define GPIO_PORT ((GPIO_TypeDef *)GPIOA)

#define SCK_HIGH()  GPIO_PORT->BSRR = (1 << SCK_PIN)
#define SCK_LOW()   GPIO_PORT->BRR  = (1 << SCK_PIN)
#define MOSI_HIGH() GPIO_PORT->BSRR = (1 << MOSI_PIN)
#define MOSI_LOW()  GPIO_PORT->BRR  = (1 << MOSI_PIN)
#define MISO_READ() ((GPIO_PORT->IDR >> MISO_PIN) & 1)
#define CS_LOW()    GPIO_PORT->BRR  = (1 << CS_PIN)
#define CS_HIGH()   GPIO_PORT->BSRR = (1 << CS_PIN)
```

Bit-bang SPI Mode 0（CPOL=0, CPHA=0）：

```c
uint8_t spi_bb_xfer(uint8_t tx)
{
        uint8_t rx = 0;

        for (int i = 7; i >= 0; i--) {   // MSB first
                if (tx & (1 << i))
                        MOSI_HIGH();
                else
                        MOSI_LOW();
                SCK_HIGH();              // 上升沿 → 采样 MISO
                if (MISO_READ())
                        rx |= (1 << i);
                SCK_LOW();               // 下降沿 → 更新 MOSI
        }
        return rx;
}
```

Bit-bang SPI Mode 3（CPOL=1, CPHA=1）：

```c
uint8_t spi_bb_mode3_xfer(uint8_t tx)
{
        uint8_t rx = 0;

        for (int i = 7; i >= 0; i--) {
                SCK_LOW();               // 下降沿 → 更新 MOSI
                if (tx & (1 << i))
                        MOSI_HIGH();
                else
                    MOSI_LOW();
                SCK_HIGH();              // 上升沿 → 采样 MISO
                if (MISO_READ())
                        rx |= (1 << i);
        }
        return rx;
}
```

写入与读取传感器（bit-bang）：

```c
void bb_write_reg(uint8_t addr, uint8_t val)
{
        CS_LOW();
        spi_bb_xfer(addr | 0x80);        // 写标志
        spi_bb_xfer(val);
        CS_HIGH();
}

uint8_t bb_read_reg(uint8_t addr)
{
        CS_LOW();
        uint8_t val = spi_bb_xfer(addr & 0x7F); // 读标志
        val = spi_bb_xfer(0xFF);                 // dummy 读回
        CS_HIGH();
        return val;
}
```

### 2.5 硬件 SPI vs Bit-bang 对比

| 维度 | 硬件 SPI | Bit-bang |
|------|----------|----------|
| 速度 | 最高几十 MHz | 受 GPIO 翻转速度限制（~MHz） |
| CPU 占用 | 低（DMA 可为 0） | 100% 占用 |
| 灵活性 | 固定引脚 | 任意 GPIO |
| 适用场景 | 高速设备（LCD、Flash） | 低速调试、引脚复用受限 |

---

## 三、速查对照表

| 协议 | 类型 | 时钟线 | 连线数 | 全双工 | 速率 |
|------|------|--------|--------|--------|------|
| UART | 异步 | 无 | 2 | 是 | 典型 115200 bps |
| SPI  | 同步 | SCLK  | 4 | 是 | 可达 80 MHz |
| I²C  | 同步 | SCL   | 2 | 否 | 标准 100 kHz |

**选型建议：**
- 调试日志 → UART（最简单）
- 高速传感器/LCD/Flash → SPI
- 引脚紧张、多设备总线 → I²C

# 第3课：I²C 总线协议与实现

> **ARM 硬件 vs 模拟抽象层**：本章区分"硬件外设寄存器操作"(STM32 HAL)和"纯软件模拟"(bit-bang / Python)，标注「🔧硬件」和「💻模拟」。

---

## 1. 原理

I²C 是两线同步串行总线：**SCL**（时钟）和 **SDA**（数据），均为开漏输出，需外接上拉电阻（典型 4.7kΩ）。

```
          VCC (3.3V)
           ┌┤
           │ 4.7kΩ     4.7kΩ
SCL ───────┴──────────┬──
SDA ──────────────────┴──
      开漏 + 上拉，线"与"逻辑
```

### 起始 / 停止条件

| 条件 | SCL | SDA |
|------|-----|-----|
| **START** | 高 | 下降沿 |
| **STOP** | 高 | 上升沿 |

```
START: ▔▔╲___   (SCL=H, SDA_↓)
STOP:  ___╱▔▔   (SCL=H, SDA_↑)
```

### 地址帧

7 位从机地址 + R/W 位（0=写，1=读），MSB 优先。

```
| S | A6 A5 A4 A3 A2 A1 A0 | R/W | ACK |
| S |    7-bit addr         | 1/0 | 低=ACK |
```

---

## 2. 时序描述

```
SCL ▔▔╲____╱▔▔╲____╱▔▔╲____╱▔▔
SDA     D7   D6   D5  ... D0
        └──── 每时钟 1 bit ────┘
```

- SCL 高电平时 SDA 数据有效
- SCL 低电平时 SDA 可变化
- 每字节后接收器拉低 SDA 为 **ACK**（保持高为 **NACK**）

```
主机发送字节 0x53 → 从机 ACK:
SDA: 0 1 0 1 0 0 1 1 | 0
                  字节完成 → ACK
```

---

## 3. 寄存器映射（🔧硬件：STM32F103 I2C1）

| 偏移 | 寄存器 | 作用 |
|------|--------|------|
| 0x00 | CR1   | 控制：PE/START/STOP/ACK |
| 0x04 | CR2   | 频率配置 FREQ |
| 0x08 | OAR1  | 自身地址 |
| 0x0C | DR    | 数据寄存器（读/写） |
| 0x14 | SR1   | 状态：SB/ADDR/BTF/RxNE/TxE |
| 0x18 | SR2   | 状态：BUSY/MSL/TRA |

**物理地址**：I2C1 = `0x40005400`，I2C2 = `0x40005800`

```c
// 🔧 硬件：直接操作寄存器
#define I2C1_BASE   0x40005400
#define I2C1_CR1    (*(volatile uint32_t *)(I2C1_BASE + 0x00))
#define I2C1_SR1    (*(volatile uint32_t *)(I2C1_BASE + 0x14))
#define I2C1_DR     (*(volatile uint32_t *)(I2C1_BASE + 0x0C))

// 发送起始条件
I2C1_CR1 |= (1 << 8);  // START = 1
while (!(I2C1_SR1 & (1 << 0))); // 等待 SB
```

---

## 4. 中断收发状态机（🔧硬件）

### 主机发送状态机

```
START → ADDR → DATA0 → DATA1 → ... → DATA_n → STOP
         │        │
         │ISR:    │ISR:
         │SR1_SB  │SR1_TxE
```

```c
// 🔧 硬件：中断主发
typedef enum { I2C_IDLE, I2C_START, I2C_ADDR, I2C_TX, I2C_STOP } i2c_state_t;

void I2C1_EV_IRQHandler(void) {
	static i2c_state_t st = I2C_IDLE;
	static uint8_t *buf;
	static int len, idx;

	switch (st) {
	case I2C_START:
		DR = (addr << 1) | 0; // + W
		st = I2C_ADDR; break;
	case I2C_ADDR:
		(void)SR2; // 清除 ADDR
		DR = buf[idx++]; st = I2C_TX; break;
	case I2C_TX:
		if (idx < len) { DR = buf[idx++]; }
		else { CR1 |= (1 << 9); st = I2C_STOP; } // STOP
		break;
	default: break;
	}
}
```

### 主机接收状态机

```
START → ADDR → DATA0 → DATA1 → ... → DATA_n → NACK + STOP
```

RxNE 标志位触发中断，最后一字节发 NACK 后 STOP。

---

## 5. Bit-bang 实现（💻模拟：纯 GPIO）

```c
// 💻 模拟：纯 GPIO 模拟 I²C
#define SCL_H  gpio_set(PIN_SCL, 1)
#define SCL_L  gpio_set(PIN_SCL, 0)
#define SDA_H  gpio_set(PIN_SDA, 1)
#define SDA_L  gpio_set(PIN_SDA, 0)
#define SDA_R  gpio_read(PIN_SDA)

void i2c_start(void) {
	SDA_H; SCL_H; delay(); SDA_L; delay(); SCL_L;
}

void i2c_stop(void) {
	SDA_L; SCL_H; delay(); SDA_H; delay();
}

void i2c_restart(void) {
	i2c_stop(); i2c_start(); // 重复起始
}

int i2c_send_byte(uint8_t b) {
	for (int i = 7; i >= 0; i--) {
		(b >> i) & 1 ? SDA_H : SDA_L;
		delay(); SCL_H; delay(); SCL_L;
	}
	SDA_H; SCL_H; delay(); // 第9脉冲
	int ack = SDA_R ? 1 : 0;
	SCL_L; return ack;     // 0=ACK
}

uint8_t i2c_recv_byte(int ack) {
	uint8_t b = 0; SDA_H; // 释放 SDA
	for (int i = 7; i >= 0; i--) {
		SCL_H; delay(); b |= (SDA_R << i); SCL_L;
	}
	ack ? SDA_L : SDA_H;  // ACK=低
	SCL_H; delay(); SCL_L;
	return b;
}
```

---

## 6. libkds 集成（💻模拟：slist 管理从设备）

```c
// 💻 模拟：libkds slist 多从设备枚举
#include <kds/slist.h>

typedef struct {
	slist_node_t node;
	uint8_t addr;
	char name[16];
	int (*init)(void);
} i2c_slave_t;

static slist_t slaves = SLIST_INIT(slaves);

void i2c_slave_register(i2c_slave_t *s) {
	slist_append(&slaves, &s->node);
}

i2c_slave_t *i2c_slave_find(uint8_t addr) {
	slist_node_t *n;
	slist_foreach(&slaves, n) {
		i2c_slave_t *s = container_of(n, i2c_slave_t, node);
		if (s->addr == addr) return s;
	}
	return NULL;
}

// 枚举所有从设备
void i2c_enumerate(void) {
	for (int a = 1; a < 127; a++) {
		i2c_start();
		if (i2c_send_byte(a << 1) == 0) {
			printf("发现设备 @ 0x%02X\n", a);
		}
		i2c_stop();
	}
}
```

---

## 7. 对比表：I²C vs UART vs SPI

| 特性 | I²C | UART | SPI |
|------|-----|------|-----|
| 速度 | 100k~3.4Mbps | ≤10Mbps | ≤50Mbps |
| 引脚数 | 2 (SCL+SDA) | 2 (TX+RX) | 4 (SCLK+MOSI+MISO+CS) |
| 拓扑 | 多主多从（总线） | 点对点 | 一主多从（菊花链） |
| 地址 | 7/10bit 软件寻址 | 无 | CS 片选硬件 |
| 收发 | 半双工（开漏） | 全双工 | 全双工 |
| 距离 | ≤1m | ≤10m（RS232 降速） | ≤0.3m |
| 从机数 | 127 | 2 | 受限于 CS 引脚 |
| 复杂度 | ★★★☆ | ★★☆☆ | ★★☆☆ |

**选型建议**：传感器→I²C，芯片间高速→SPI，远距离→UART。

---

## 8. Windows 模拟 Python 脚本（💻模拟）

```python
# 💻 模拟：Windows Python 主从通信
import time, threading

# ————— 抽象位操作 —————
class BitBangI2C:
    def __init__(self):
        self.scl = 0; self.sda = 1

    def _delay(self): time.sleep(0.001)

    def start(self):
        self.sda = 1; self.scl = 1; self._delay()
        self.sda = 0; self._delay(); self.scl = 0

    def stop(self):
        self.sda = 0; self.scl = 1; self._delay()
        self.sda = 1; self._delay()

    def send_byte(self, b):
        for i in range(7, -1, -1):
            self.sda = (b >> i) & 1; self._delay()
            self.scl = 1; self._delay(); self.scl = 0
        self.sda = 1; self.scl = 1; self._delay()
        ack = self.sda == 0; self.scl = 0; return ack

    def recv_byte(self, ack=True):
        self.sda = 1; b = 0
        for i in range(7, -1, -1):
            self.scl = 1; self._delay()
            b |= (self.sda << i); self.scl = 0
        self.sda = 0 if ack else 1
        self.scl = 1; self._delay(); self.scl = 0
        return b

# ————— 主设备通信 —————
bus = BitBangI2C()

def master_write(addr, data):
    bus.start()
    bus.send_byte((addr << 1) | 0)  # +W
    for b in data:
        bus.send_byte(b)
    bus.stop()

def master_read(addr, n):
    bus.start()
    bus.send_byte((addr << 1) | 1)  # +R
    vals = [bus.recv_byte(i < n - 1) for i in range(n)]
    bus.stop(); return vals

# 从设备类
class Slave:
    def __init__(self, addr):
        self.addr = addr; self.regs = [0] * 256
    def write(self, d): self.regs[self.addr] = d[0]
    def read(self, n):  return self.regs[self.addr:self.addr + n]

slv = Slave(0x50)
master_write(0x50, [0x10, 0x42])                    # 写
val = master_read(0x50, 2)                           # 读
print(f"从设备 0x50 读取: {[hex(v) for v in val]}")
```

---

## 总结

| 层次 | 关键点 |
|------|--------|
| 原理 | 开漏 + 上拉，START/STOP/ACK 协议 |
| 🔧硬件 | 状态机中断收发，CR1/SR1/DR 寄存器 |
| 💻模拟 | bit-bang GPIO 模拟，slist 管理设备 |
| 对比 | I²C 平衡速度、引脚与复杂度 |
| 调试 | Python 脚本验证协议逻辑 |

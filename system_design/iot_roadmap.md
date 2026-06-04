# 嵌入式/物联网学习路线图

> 从 C 实战到硬件底层的完整链路
> 环境：Windows 11 + QEMU + arm-none-eabi-gcc 交叉编译
> 前置基础：libkds 数据结构库、C11 多线程、嵌入式位操作

---

## 1. 嵌入式 C 深度

### 1.1 中断与定时器
```c
// 中断向量表结构（ARM Cortex-M）
typedef void (*ISR)(void);
ISR vector_table[256] __attribute__((section(".isr_vector")));

// 软件模拟定时器中断
typedef struct {
    void (*callback)(void);
    uint32_t period_ms;
    uint32_t counter;
    uint8_t enabled;
} soft_timer_t;

void timer_isr_handler(soft_timer_t *timers, int count) {
    for (int i = 0; i < count; i++) {
        if (timers[i].enabled) {
            timers[i].counter++;
            if (timers[i].counter >= timers[i].period_ms / 10) {
                timers[i].counter = 0;
                timers[i].callback();
            }
        }
    }
}
```

### 1.2 内存映射寄存器
```c
// 寄存器地址映射
#define GPIO_BASE      0x40020000
#define GPIO_MODER     (*(volatile uint32_t *)(GPIO_BASE + 0x00))
#define GPIO_ODR       (*(volatile uint32_t *)(GPIO_BASE + 0x14))
#define GPIO_BSRR      (*(volatile uint32_t *)(GPIO_BASE + 0x18))

// 位操作宏
#define SET_BIT(reg, bit)     ((reg) |= (1UL << (bit)))
#define CLR_BIT(reg, bit)     ((reg) &= ~(1UL << (bit)))
#define READ_BIT(reg, bit)    (((reg) >> (bit)) & 1UL)

// 模拟：Windows 上用内存映射文件模拟
void gpio_write(int pin, int val) {
    if (val) SET_BIT(GPIO_BSRR, pin);
    else     SET_BIT(GPIO_BSRR, pin + 16);
}
```

### 1.3 DMA（直接内存访问）
- CPU 发起传输后交给 DMA 控制器，CPU 可并行处理
- 常用场景：ADC 采样、SPI/UART 数据传输、内存拷贝
- 结合 libkds 环形缓冲区：DMA 写入环形缓冲区，CPU 从另一端读取

```c
// DMA + 环形缓冲区模式（概念）
// DMA 自动将外设数据写入 ringbuf
// CPU 从 ringbuf 读取处理
// 零拷贝：DMA 直接写入 buffer，无需 CPU 搬运
```

### 1.4 低功耗设计
- **睡眠模式**：CPU 停止，外设运行，中断唤醒
- **停止模式**：CPU + 大部分外设停止，RTC 保留
- **待机模式**：仅保留唤醒引脚和 RTC
- **WFI/WFE 指令**：等待中断/等待事件

---

## 2. RTOS 核心概念（FreeRTOS）

### 2.1 任务调度
```c
// FreeRTOS 任务创建
void vTaskFunction(void *pvParameters) {
    while (1) {
        // 任务逻辑
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

void main(void) {
    xTaskCreate(vTaskFunction, "Task1", 128, NULL, 1, NULL);
    vTaskStartScheduler();  // 启动调度器
    // 不会执行到这里
}
```

### 2.2 任务优先级与调度策略
| 策略 | 说明 | 适用场景 |
|------|------|---------|
| 抢占式 | 高优先级任务抢占低优先级 | 硬实时 |
| 合作式 | 任务主动让出 CPU | 软实时 |
| 时间片轮转 | 同优先级共享时间片 | 一般用途 |

### 2.3 同步与通信
```c
// 队列（Queue）
QueueHandle_t xQueue;
xQueue = xQueueCreate(10, sizeof(uint32_t));
// 发送方
xQueueSend(xQueue, &data, portMAX_DELAY);
// 接收方
xQueueReceive(xQueue, &received, portMAX_DELAY);

// 信号量（Semaphore）
SemaphoreHandle_t xSemaphore;
xSemaphore = xSemaphoreCreateBinary();
xSemaphoreGive(xSemaphore);       // 释放
xSemaphoreTake(xSemaphore, 1000); // 获取（等待1s）

// 互斥锁（Mutex）— 带优先级继承
xSemaphore = xSemaphoreCreateMutex();
```

### 2.4 内存管理方案
| 方案 | 特点 | 适用 |
|------|------|------|
| heap_1 | 只能分配不能释放，无碎片 | 极简单场景 |
| heap_2 | 支持释放，可能碎片 | 一般场景 |
| heap_3 | 包装 malloc/free，线程安全 | 有标准库 |
| heap_4 | 合并相邻空闲块，减少碎片 | **推荐** |
| heap_5 | heap_4 + 多不连续内存区 | 多内存区场景 |

---

## 3. 通信协议：UART / I2C / SPI

### 3.1 UART（异步串行）
```c
// 环形缓冲区 + UART 驱动（概念）
typedef struct {
    uint8_t buffer[256];
    volatile uint16_t head, tail;
} ringbuf_t;

// UART 中断接收 — 数据放入环形缓冲区
void UART_IRQHandler(void) {
    if (/* RX 非空 */) {
        uint8_t byte = UART->DR;
        ringbuf->buffer[ringbuf->head] = byte;
        ringbuf->head = (ringbuf->head + 1) % 256;
    }
}
```
- libkds `rbuf` 可直接作为 UART 接收缓冲区
- 波特率计算、停止位、校验位配置

### 3.2 I2C（同步串行，多主多从）
- SCL（时钟）+ SDA（数据）两线制
- 起始条件：SCL 高电平时 SDA 下降沿 → 停止条件：SCL 高电平时 SDA 上升沿
- 7 位地址空间，仲裁机制
- **C 模拟实现**：用 GPIO 位操作模拟 I2C 时序（bit-banging）

### 3.3 SPI（同步串行，全双工）
- MOSI/MISO/SCLK/CS 四线
- 4 种模式：时钟极性(CPOL) + 时钟相位(CPHA)
- 速度高于 I2C，常用于 ADC/DAC/SD 卡/显示屏
- **可用 libkds 的 rbuf 模拟 SPI FIFO**

### 3.4 对比
| 协议 | 线数 | 速度 | 距离 | 主从 |
|------|------|------|------|------|
| UART | 2 | ≤1Mbps | 中等 | 点对点 |
| I2C | 2 | ≤3.4Mbps | 短 | 多主多从 |
| SPI | 4 | ≤50MHz | 短 | 一主多从 |

---

## 4. 传感器数据处理

### 4.1 ADC 采样与移动平均
```c
#define WINDOW_SIZE 16

typedef struct {
    uint16_t buffer[WINDOW_SIZE];
    uint8_t index;
    uint32_t sum;
} moving_avg_t;

uint16_t moving_avg_filter(moving_avg_t *ma, uint16_t sample) {
    ma->sum -= ma->buffer[ma->index];
    ma->buffer[ma->index] = sample;
    ma->sum += sample;
    ma->index = (ma->index + 1) % WINDOW_SIZE;
    return ma->sum / WINDOW_SIZE;
}
```

### 4.2 一阶卡尔曼滤波器
```c
// 一维卡尔曼滤波（C 实现）
typedef struct {
    float x;      // 状态估计
    float p;      // 估计误差协方差
    float q;      // 过程噪声
    float r;      // 测量噪声
} kalman_1d_t;

float kalman_update(kalman_1d_t *kf, float z) {
    // 预测
    float p_pred = kf->p + kf->q;
    // 更新
    float k = p_pred / (p_pred + kf->r);  // 卡尔曼增益
    kf->x = kf->x + k * (z - kf->x);
    kf->p = (1 - k) * p_pred;
    return kf->x;
}
```

### 4.3 数据融合
- 互补滤波（加速度计 + 陀螺仪 → 姿态角）
- 加权平均（多传感器加权，方差越小权重越大）
- 中值滤波（消除脉冲噪声）

---

## 5. 硬件桥接模拟（Windows 上）

### 5.1 GPIO 控制模拟
```c
// 模拟硬件寄存器
typedef struct {
    volatile uint32_t moder;
    volatile uint32_t otyper;
    volatile uint32_t ospeedr;
    volatile uint32_t pupdr;
    volatile uint32_t idr;
    volatile uint32_t odr;
    volatile uint32_t bsrr;
} gpio_regs_t;

// Windows 上：结构体数组模拟
gpio_regs_t gpio_ports[6]; // PORTA~PORTF

void gpio_set_mode(int port, int pin, int mode) {
    uint32_t shift = pin * 2;
    gpio_ports[port].moder &= ~(3UL << shift);
    gpio_ports[port].moder |= ((uint32_t)mode << shift);
}
```

### 5.2 PWM 模拟
```c
// 软件 PWM（Windows 线程模拟）
DWORD WINAPI pwm_thread(LPVOID param) {
    int period_ms = *(int*)param;
    int duty_ms = period_ms / 2; // 50% 占空比
    
    while (1) {
        gpio_write(PIN, 1);
        Sleep(duty_ms);
        gpio_write(PIN, 0);
        Sleep(period_ms - duty_ms);
    }
    return 0;
}
```

---

## 6. 物联网协议

### 6.1 MQTT
- **发布/订阅**模型，消息代理(Broker)转发
- QoS 0/1/2：最多一次 → 至少一次 → 恰好一次
- 保留消息、遗嘱消息(Last Will)
- **PC 上即可跑**：Mosquitto broker + paho-mqtt C 客户端

### 6.2 CoAP（受约束应用协议）
- 基于 UDP，类似 HTTP 的 RESTful 设计
- 轻量级，适合低功耗设备
- 观察模式(Observe)：服务器推送资源变化

### 6.3 LwIP（轻量级 TCP/IP 栈）
- 无操作系统的 TCP/IP 栈，广泛用于嵌入式
- **RAW API**：无 OS，回调模式
- **Netconn API**：有 OS，类 BSD socket
- **Socket API**：完整 POSIX socket

### 6.4 低功耗广域网（LPWAN）
- LoRaWAN：长距离低速率，星型拓扑
- NB-IoT：蜂窝基站，高覆盖率
- 概念理解即可，真实环境需要硬件

---

## 7. Windows 嵌入式开发环境

### 7.1 工具链
```bash
# 安装 ARM 交叉编译器（Windows）
# 下载 arm-gnu-toolchain-*.exe 并安装
# 添加到 PATH

# 验证
arm-none-eabi-gcc --version

# 编译裸机程序
arm-none-eabi-gcc -mcpu=cortex-m3 -mthumb \
    -nostartfiles -Tlinker.ld \
    -o firmware.elf main.c startup.c
```

### 7.2 QEMU 模拟
```bash
# QEMU 模拟 STM32
qemu-system-arm -machine stm32-p103 \
    -kernel firmware.elf \
    -nographic

# 可用板子
qemu-system-arm -M help | grep -i stm
# stm32-p103 — STM32F103
# netduino2 — Cortex-M4
```

### 7.3 FreeRTOS 模拟器
```bash
# Windows 上直接用 VS/GCC 编译运行 FreeRTOS 模拟器
# FreeRTOS/FreeRTOS/Demo/WIN32-MSVC — 完整 Win32 模拟
# 无需硬件即可体验任务调度、队列、信号量
```

### 7.4 推荐实践路径
```
1. QEMU + 裸机 C（LED 闪烁、UART 输出）
2. QEMU + FreeRTOS（多任务、队列通信）
3. QEMU + LwIP（TCP echo server）
4. Windows 原生模拟 + MQTT 客户端（连公共 broker）
```

---

## 8. 与现有栈的集成

### libkds 在嵌入式中的使用场景
| 结构 | 嵌入式场景 | 说明 |
|------|-----------|------|
| 环形缓冲区(rbuf) | UART RX/TX FIFO、DMA 缓冲 | ✅ 直接可用 |
| 哈希表(hmap) | 设备注册表、配置查找 | 需评估内存 |
| 动态数组(darr) | 传感器数据批量采集 | ✅ 轻量好用 |
| 二叉堆(bheap) | 优先级任务队列、实时调度 | 可替代 RTOS 队列 |
| 链表(slist) | 内存块管理、定时器链表 | 适合动态场景 |

### Python 绑定桥梁
- libkds → ctypes → Python：PC 上调试嵌入式算法
- 传感器滤波算法先 Python 验证 → 再转 C 部署
- 用 Python 生成回测数据 → C 处理 → 结果可视化

---

## 学习计划（8 课）

| 课 | 主题 | 实操内容 | Windows 可行性 |
|----|------|---------|:------------:|
| 1 | 嵌入式 C 深入 | 中断模拟 + 内存映射寄存器存取 | ✅ QEMU |
| 2 | 通信协议(上) | UART 环形缓冲区 + SPI 模拟 FIFO | ✅ 纯 C |
| 3 | 通信协议(下) | I2C bit-banging + 协议栈对比 | ✅ 纯 C |
| 4 | RTOS 基础 | FreeRTOS 任务/队列/信号量 | ✅ 模拟器 |
| 5 | 传感器处理 | 卡尔曼滤波 + 移动平均 + 互补滤波 | ✅ Python→C |
| 6 | MQTT 与 CoAP | Mosquitto broker + MQTT 客户端 | ✅ 本机 |
| 7 | LwIP 与 TCP/IP | 模拟 TCP echo server | ✅ QEMU |
| 8 | 综合项目 | 虚拟传感器采集→MQTT 发布→Python 接收展示 | ✅ Windows 全链路 |

> **依赖关系**：1→2→3（第一周），4可选并行，5依赖1，6/7依赖3

---

## D 盘同步
完成学习后同步到 D:\kai_knowledge\learning\

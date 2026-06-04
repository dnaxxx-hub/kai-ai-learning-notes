# IoT 第5课：GPIO / PWM / ADC 硬件抽象层 (HAL)

> 基于 STM32F407 (ARM Cortex-M4)，寄存器级编程，零依赖 HAL 库

---

## 一、GPIO HAL 设计

### 1.1 寄存器布局 (STM32F4)

| 外设 | 基址 |
|------|------|
| GPIOA | `0x40020000` |
| GPIOB | `0x40020400` |
| GPIOC | `0x40020800` |
| GPIOD | `0x40020C00` |
| GPIOE | `0x40021000` |

每个 GPIO 端口的寄存器偏移（以 GPIOA_BASE 为基址，+0x00 ~ +0x24）：

| 偏移 | 寄存器 | 用途 | 宽度 |
|------|--------|------|------|
| 0x00 | MODER | 模式选择 (输入/输出/复用/模拟) | 32bit, 每 pin 2bit |
| 0x04 | OTYPER | 输出类型 (推挽/开漏) | 32bit, 每 pin 1bit |
| 0x08 | OSPEEDR | 输出速度 | 32bit, 每 pin 2bit |
| 0x0C | PUPDR | 上下拉配置 | 32bit, 每 pin 2bit |
| 0x10 | IDR | 输入数据寄存器 | 32bit, 低 16bit 有效 |
| 0x14 | ODR | 输出数据寄存器 | 32bit, 低 16bit 有效 |
| 0x18 | BSRR | 位设置/复位寄存器 | 32bit, 低16置位高16复位 |
| 0x24 | AFR[0] | 复用功能低 (pin 0-7) | 32bit |
| 0x28 | AFR[1] | 复用功能高 (pin 8-15) | 32bit |

### 1.2 类型定义与宏

```c
// gpio_hal.h
#ifndef GPIO_HAL_H
#define GPIO_HAL_H

#include <stdint.h>

/* GPIO 基址 */
#define GPIOA_BASE      0x40020000UL
#define GPIOB_BASE      0x40020400UL
#define GPIOC_BASE      0x40020800UL
#define GPIOD_BASE      0x40020C00UL
#define GPIOE_BASE      0x40021000UL

/* GPIO 寄存器偏移 */
#define GPIO_MODER      0x00
#define GPIO_OTYPER     0x04
#define GPIO_OSPEEDR    0x08
#define GPIO_PUPDR      0x0C
#define GPIO_IDR        0x10
#define GPIO_ODR        0x14
#define GPIO_BSRR       0x18

/* GPIO 模式 */
typedef enum {
    GPIO_MODE_INPUT  = 0,
    GPIO_MODE_OUTPUT = 1,
    GPIO_MODE_AF     = 2,
    GPIO_MODE_ANALOG = 3
} gpio_mode_t;

/* 上下拉 */
typedef enum {
    GPIO_PUPD_NONE    = 0,
    GPIO_PUPD_PULLUP  = 1,
    GPIO_PUPD_PULLDOWN = 2
} gpio_pupd_t;

/* GPIO 配置结构体 */
typedef struct {
    uint32_t    port;       /* GPIOA_BASE / GPIOB_BASE ... */
    uint8_t     pin;        /* 0-15 */
    gpio_mode_t mode;       /* 输入/输出/复用/模拟 */
    gpio_pupd_t pupd;       /* 上下拉 */
} gpio_cfg_t;

#endif
```

### 1.3 函数实现

```c
// gpio_hal.c
#include "gpio_hal.h"

/* GPIO 初始化：配置模式 + 上下拉 */
void gpio_init(gpio_cfg_t *cfg)
{
    volatile uint32_t *moder = (uint32_t *)(cfg->port + GPIO_MODER);
    volatile uint32_t *pupdr = (uint32_t *)(cfg->port + GPIO_PUPDR);
    uint32_t shift = cfg->pin * 2;

    *moder &= ~(3UL << shift);          /* 清除两位 */
    *moder |= (cfg->mode & 3) << shift; /* 写入模式 */
    *pupdr &= ~(3UL << shift);
    *pupdr |= (cfg->pupd & 3) << shift;
}

/* GPIO 写引脚：val=0 低电平, val=1 高电平 */
void gpio_write(uint32_t port, uint8_t pin, uint8_t val)
{
    volatile uint32_t *bsrr = (uint32_t *)(port + GPIO_BSRR);
    if (val)
        *bsrr = (1UL << pin);           /* BSRR 低16位置位 */
    else
        *bsrr = (1UL << (pin + 16));    /* BSRR 高16位复位 */
}

/* GPIO 读引脚：返回 0 或 1 */
uint8_t gpio_read(uint32_t port, uint8_t pin)
{
    volatile uint32_t *idr = (uint32_t *)(port + GPIO_IDR);
    return (*idr >> pin) & 1;
}

/* GPIO 翻转引脚：异或 ODR 对应位 */
void gpio_toggle(uint32_t port, uint8_t pin)
{
    volatile uint32_t *odr = (uint32_t *)(port + GPIO_ODR);
    *odr ^= (1UL << pin);
}
```

### 1.4 位带操作 (Bit-banding)

Cortex-M3/M4 支持位带别名区，将一个 bit 映射到 alias 地址的一个 word。

**位带公式：**
```
alias_addr = alias_base + (bit_offset * 4)
bit_offset = (addr - peri_base) * 8 + bit_num
```

```c
/* 位带宏：直接操作 GPIO ODR 和 IDR 的单个 bit */
#define BITBAND_PERI_BASE   0x40000000UL
#define BITBAND_PERI_ALIAS  0x42000000UL

#define BITBAND_ADDR(addr, bit)                                    \
    (BITBAND_PERI_ALIAS +                                          \
     (((uint32_t)(addr) - BITBAND_PERI_BASE) * 32 + (bit) * 4))

/* GPIOA ODR bit 5 的位带地址 */
#define PA5_OUT  (*(volatile uint32_t *)BITBAND_ADDR(GPIOA_BASE + GPIO_ODR, 5))

/* 用例：位带操作 */
void bitband_demo(void)
{
    PA5_OUT = 1;  /* PA5 置高 */
    PA5_OUT = 0;  /* PA5 置低 */
}
```

---

## 二、PWM HAL 设计

### 2.1 定时器 TIMx 寄存器 (STM32F4)

| 寄存器 | 偏移 | 用途 |
|--------|------|------|
| TIM_CR1  | 0x00 | 控制寄存器1 (CEN 使能, DIR 计数方向) |
| TIM_DIER | 0x0C | 中断使能寄存器 |
| TIM_SR   | 0x10 | 状态寄存器 (UIF 更新中断标志) |
| TIM_PSC  | 0x28 | 预分频器 (16bit, 实际值 = PSC+1) |
| TIM_ARR  | 0x2C | 自动重载寄存器 (决定周期) |
| TIM_CCR1 | 0x34 | 捕获/比较寄存器1 (决定占空比) |
| TIM_CCR2 | 0x38 | 捕获/比较寄存器2 |
| TIM_CCR3 | 0x3C | 捕获/比较寄存器3 |
| TIM_CCR4 | 0x40 | 捕获/比较寄存器4 |

**定时器基址**：TIM2=0x40000000, TIM3=0x40000400, TIM4=0x40000800, TIM5=0x40000C00

### 2.2 PWM 初始化与占空比设置

```c
// pwm_hal.h
#ifndef PWM_HAL_H
#define PWM_HAL_H

#include <stdint.h>

typedef struct {
    uint32_t tim_base;   /* TIM2/TIM3/TIM4 基址 */
    uint8_t  channel;    /* 1-4, 对应 CCR1-CCR4 */
    uint32_t period;     /* ARR 值, 决定频率 */
    uint16_t prescaler;  /* PSC 值, 决定分频 */
} pwm_cfg_t;

void pwm_init(pwm_cfg_t *cfg);
void pwm_set_duty(pwm_cfg_t *cfg, uint16_t duty);

#endif
```

```c
// pwm_hal.c
#include "pwm_hal.h"

#define TIM_CR1  0x00
#define TIM_DIER 0x0C
#define TIM_SR   0x10
#define TIM_PSC  0x28
#define TIM_ARR  0x2C
#define TIM_CCR1 0x34
#define TIM_CCR2 0x38
#define TIM_CCR3 0x3C
#define TIM_CCR4 0x40

/* 启动 PWM: 设置 PSC, ARR, 使能计数器 */
void pwm_init(pwm_cfg_t *cfg)
{
    volatile uint32_t *psc  = (uint32_t *)(cfg->tim_base + TIM_PSC);
    volatile uint32_t *arr  = (uint32_t *)(cfg->tim_base + TIM_ARR);
    volatile uint32_t *cr1  = (uint32_t *)(cfg->tim_base + TIM_CR1);
    volatile uint32_t *ccmr;   /* 需根据 channel 计算偏移 */
    uint32_t ccmr_offset;
    uint8_t  ch = cfg->channel;

    *psc = cfg->prescaler;
    *arr = cfg->period;

    /* CCMR1 (ch1/ch2) 偏移=0x18, CCMR2 (ch3/ch4) 偏移=0x1C */
    ccmr_offset = (ch <= 2) ? 0x18 : 0x1C;
    ccmr = (uint32_t *)(cfg->tim_base + ccmr_offset);

    if (ch == 1 || ch == 3) {
        /* OCxM[2:0] = 110 (PWM mode 1), OCxPE = 1 */
        *ccmr = (*ccmr & ~0x70) | (0x60 | 0x08);
        /* CCER 使能: CCxE=1 */
        *(volatile uint32_t *)(cfg->tim_base + 0x20) |= (1 << ((ch-1)*4));
    } else {
        /* 同理处理 ch2/ch4, bit 偏移不同 */
        *ccmr = (*ccmr & ~0x7000) | (0x6000 | 0x800);
        *(volatile uint32_t *)(cfg->tim_base + 0x20) |= (1 << ((ch-1)*4));
    }
    *cr1 |= 1; /* CEN 使能计数器 */
}

/* 设置占空比: duty 范围 0 ~ cfg->period */
void pwm_set_duty(pwm_cfg_t *cfg, uint16_t duty)
{
    uint32_t ccr_addr = cfg->tim_base + TIM_CCR1 + (cfg->channel - 1) * 4;
    *(volatile uint32_t *)ccr_addr = duty;
}
```

### 2.3 呼吸灯示例

```c
/* 呼吸灯: PA5 (TIM2_CH1) 渐亮渐暗 */
void breath_led_demo(void)
{
    pwm_cfg_t pwm = {
        .tim_base  = 0x40000000UL,  /* TIM2 */
        .channel   = 1,
        .period    = 999,
        .prescaler = 83             /* 84MHz / (83+1) = 1MHz → 1kHz PWM */
    };
    int duty, dir = 1;

    pwm_init(&pwm);
    while (1) {
        pwm_set_duty(&pwm, duty);
        duty += dir * 5;
        if (duty >= 999) dir = -1;
        if (duty <= 0)   dir =  1;
        for (volatile int i = 0; i < 50000; i++); /* 延时 */
    }
}
```

---

## 三、ADC HAL 设计

### 3.1 ADC 寄存器 (STM32F4)

| 寄存器 | 偏移 | 用途 |
|--------|------|------|
| ADC_CR1   | 0x04 | 控制1 (SCAN扫描, EOCIE中断) |
| ADC_CR2   | 0x08 | 控制2 (ADON启动, CONT连续, SWSTART) |
| ADC_SMPR1 | 0x0C | 采样时间寄存器1 (ch 10-18) |
| ADC_SMPR2 | 0x10 | 采样时间寄存器2 (ch 0-9) |
| ADC_SQR1  | 0x2C | 规则序列寄存器1 (序列长度) |
| ADC_SQR3  | 0x34 | 规则序列寄存器3 (第1个转换) |
| ADC_DR    | 0x4C | 数据寄存器 (12bit 右对齐) |

**ADC 基址**：ADC1=0x40012000, ADC2=0x40012100, ADC3=0x40012200

### 3.2 ADC 函数实现

```c
// adc_hal.h
#ifndef ADC_HAL_H
#define ADC_HAL_H

#include <stdint.h>

typedef struct {
    uint32_t adc_base;   /* ADC1/2/3 基址 */
    uint8_t  channel;    /* 0-18 */
    uint8_t  sample_cyc; /* 采样周期: 3/15/28/56/84/112/144/480 */
} adc_cfg_t;

void adc_init(adc_cfg_t *cfg);
uint16_t adc_read(adc_cfg_t *cfg);
void adc_continuous(adc_cfg_t *cfg, uint16_t *buf, uint32_t len);

#endif
```

```c
// adc_hal.c
#include "adc_hal.h"

#define ADC_CR1   0x04
#define ADC_CR2   0x08
#define ADC_SMPR2 0x10
#define ADC_SQR3  0x34
#define ADC_DR    0x4C
#define ADC_SR    0x00

/* ADC 单次转换初始化 */
void adc_init(adc_cfg_t *cfg)
{
    volatile uint32_t *cr2  = (uint32_t *)(cfg->adc_base + ADC_CR2);
    volatile uint32_t *cr1  = (uint32_t *)(cfg->adc_base + ADC_CR1);
    volatile uint32_t *smpr = (uint32_t *)(cfg->adc_base + ADC_SMPR2);
    volatile uint32_t *sqr3 = (uint32_t *)(cfg->adc_base + ADC_SQR3);
    uint8_t ch = cfg->channel;

    *cr2 |= 1;                      /* ADON 上电 */
    /* 采样时间: ch 0-9 在 SMPR2 */
    *smpr &= ~(7UL << (ch * 3));
    *smpr |= (cfg->sample_cyc & 7) << (ch * 3);
    /* 规则序列: 长度=1, 第1个 = channel */
    *sqr3 = (*sqr3 & ~0x1F) | (ch & 0x1F);
    *cr1 &= ~(3 << 24);            /* 分辨率 12bit (默认) */
}

/* 单次读取: 触发转换 → 等待完成 → 读结果 */
uint16_t adc_read(adc_cfg_t *cfg)
{
    volatile uint32_t *cr2 = (uint32_t *)(cfg->adc_base + ADC_CR2);
    volatile uint32_t *sr  = (uint32_t *)(cfg->adc_base + ADC_SR);

    *cr2 |= (1 << 30);             /* SWSTART 启动转换 */
    while (!(*sr & 2));             /* 等待 EOC 标志 */
    return *(uint16_t *)(cfg->adc_base + ADC_DR);
}

/* 连续模式: 自动循环转换, 结果写入 buf */
void adc_continuous(adc_cfg_t *cfg, uint16_t *buf, uint32_t len)
{
    volatile uint32_t *cr2 = (uint32_t *)(cfg->adc_base + ADC_CR2);
    *cr2 |= (1 << 1);               /* CONT=1 连续模式 */
    *cr2 |= (1 << 30);              /* 首次 SWSTART */
    for (uint32_t i = 0; i < len; i++)
        buf[i] = adc_read(cfg);
}
```

---

## 四、Windows 模拟 (Python)

纯软件模拟 GPIO / PWM / ADC 行为，无需硬件即可调试。

### 4.1 GPIO 模拟

```python
class GpioHal:
    MODER = {k: 0 for k in range(16)}  # 0=input 1=output
    ODR = 0
    IDR = 0

    @classmethod
    def init(cls, port, pin, mode, pupd=0):
        cls.MODER[pin] = mode

    @classmethod
    def write(cls, port, pin, val):
        if val:
            cls.ODR |= (1 << pin)
        else:
            cls.ODR &= ~(1 << pin)

    @classmethod
    def read(cls, port, pin):
        return (cls.IDR >> pin) & 1

    @classmethod
    def toggle(cls, port, pin):
        cls.ODR ^= (1 << pin)

    @classmethod
    def state(cls):
        """当前 ODR 二进制字符串"""
        return f"GPIO ODR: {cls.ODR:016b}"

# 测试
GpioHal.init('A', 5, 1)     # PA5 输出
GpioHal.write('A', 5, 1)    # PA5 = 1
print(GpioHal.state())       # → GPIO ODR: 0000000000100000
GpioHal.toggle('A', 5)      # PA5 = 0
```

### 4.2 PWM 模拟

```python
class PwmHal:
    _channels = {}

    @classmethod
    def init(cls, tim, channel, period=999, prescaler=0):
        key = (tim, channel)
        cls._channels[key] = {'period': period, 'duty': 0, 'enabled': True}

    @classmethod
    def set_duty(cls, tim, channel, duty):
        key = (tim, channel)
        if key in cls._channels:
            cls._channels[key]['duty'] = min(duty, cls._channels[key]['period'])

    @classmethod
    def get_duty_ratio(cls, tim, channel):
        """返回 0.0~1.0 占空比"""
        ch = cls._channels.get((tim, channel))
        if not ch or ch['period'] == 0:
            return 0.0
        return ch['duty'] / ch['period']

# 测试：模拟呼吸灯
PwmHal.init('TIM2', 1, period=999)
for duty in range(0, 1000, 5):
    PwmHal.set_duty('TIM2', 1, duty)
    ratio = PwmHal.get_duty_ratio('TIM2', 1)
    bar = '█' * int(ratio * 20) + '░' * (20 - int(ratio * 20))
    print(f"\r{ratio:5.2f} {bar}", end='')
```

### 4.3 ADC 模拟（带温度传感器模拟）

```python
import math, time

class AdcHal:
    _config = {}
    _sim_temp = 25.0  # 模拟温度 °C

    @classmethod
    def init(cls, adc, channel, sample_cyc=3):
        cls._config[(adc, channel)] = sample_cyc

    @classmethod
    def read(cls, adc, channel, noise=True):
        """模拟温度传感器: 25°C = 1350, +1°C → +4.5 LSB"""
        raw = int(1350 + (cls._sim_temp - 25) * 4.5)
        if noise:
            raw += int((hash(str(time.time_ns())) % 21) - 10)
        return max(0, min(4095, raw))

    @classmethod
    def read_temp_c(cls, adc, channel):
        """返回摄氏度"""
        raw = cls.read(adc, channel, noise=True)
        return 25.0 + (raw - 1350) / 4.5

    @classmethod
    def continuous(cls, adc, channel, n):
        return [cls.read(adc, channel) for _ in range(n)]

    @classmethod
    def set_sim_temp(cls, temp_c):
        cls._sim_temp = temp_c

# 测试：模拟温度读取 + LED 渐变
LED_PIN = 5
GpioHal.init('A', LED_PIN, 1)   # PA5 输出
PwmHal.init('TIM2', 1, period=4095)

for temp in [25, 30, 35, 40, 45, 50, 45, 40, 35, 30, 25]:
    AdcHal.set_sim_temp(temp)
    raw = AdcHal.read('ADC1', 0)
    # ADC 值直驱 PWM 占空比 → LED 亮度随温度渐变
    PwmHal.set_duty('TIM2', 1, raw)
    t_c = AdcHal.read_temp_c('ADC1', 0)
    bar = '█' * (raw // 200)
    print(f"  {t_c:5.1f}°C  raw={raw:4d}  PWM={PwmHal.get_duty_ratio('TIM2',1):.2f}  {bar}")
    time.sleep(0.3)
```

### 4.4 整合测试：温度 → LED 亮度

```python
def temperature_led_simulation():
    """完整演示: ADC 模拟温度 → PWM 驱动 LED 亮度"""
    print("=== 温度传感器 → LED 渐变 ===")
    AdcHal.init('ADC1', 0)
    PwmHal.init('TIM2', 1, period=4095)

    for step in range(40):
        # 模拟温度 20~60°C 正弦变化
        temp = 40 + 20 * math.sin(step * 0.3)
        AdcHal.set_sim_temp(temp)

        raw = AdcHal.read('ADC1', 0, noise=True)
        PwmHal.set_duty('TIM2', 1, raw)

        t_c = AdcHal.read_temp_c('ADC1', 0)
        bar = '█' * (raw // 200) + '░' * (20 - raw // 200)
        print(f"  {t_c:5.1f}°C  ADC={raw:4d}  {bar}")
        time.sleep(0.2)

if __name__ == '__main__':
    temperature_led_simulation()
```

---

## 五、libkds 集成：滑动平均滤波

使用 `libkds` 的环形缓冲区 (`rbuf`) 存储 ADC 采样数据，实现滑动平均滤波。

```c
// adc_filter.c — libkds 集成示例
#include <stdint.h>
#include "kds/rbuf.h"       /* libkds 环形缓冲区 */
#include "adc_hal.h"

#define FILTER_WINDOW 16    /* 滑动窗口大小 */

typedef struct {
    adc_cfg_t   adc;        /* ADC 配置 */
    kds_rbuf_t  rbuf;       /* 环形缓冲区 */
    uint16_t    buf[FILTER_WINDOW];  /* 预分配缓冲区 */
} adc_filter_t;

/* 初始化 ADC + 滑动平均滤波器 */
void adc_filter_init(adc_filter_t *f, adc_cfg_t *cfg)
{
    f->adc = *cfg;
    kds_rbuf_init(&f->rbuf, f->buf, FILTER_WINDOW, sizeof(uint16_t));
    adc_init(&f->adc);
}

/* 读取 ADC 并更新滑动平均 */
uint16_t adc_filter_read(adc_filter_t *f)
{
    uint16_t raw = adc_read(&f->adc);
    kds_rbuf_push(&f->rbuf, &raw, 1);

    /* 计算滑动平均 */
    uint32_t sum = 0;
    uint16_t val;
    uint32_t n = kds_rbuf_available(&f->rbuf);
    for (uint32_t i = 0; i < n; i++) {
        kds_rbuf_peek(&f->rbuf, i, &val);
        sum += val;
    }
    return (n > 0) ? (uint16_t)(sum / n) : 0;
}

/* 临界值报警回调 */
typedef void (*alert_fn_t)(uint16_t filtered, uint16_t threshold);

/* 带阈值检测的滤波采集 */
void adc_filter_monitor(adc_filter_t *f, uint16_t threshold, alert_fn_t alert)
{
    uint16_t avg = adc_filter_read(f);
    if (avg > threshold && alert)
        alert(avg, threshold);
}
```

**滑动平均效果**（Python 模拟验证）：

```python
import random, statistics

def sliding_average_demo():
    """模拟 ADC 滑动平均滤波效果"""
    raw = [1000 + int(random.gauss(0, 50)) for _ in range(40)]
    window = 8

    print(f"{'raw':>6} {'smoothed':>8}")
    for i, r in enumerate(raw):
        if i < window - 1:
            s = statistics.mean(raw[:i+1])
        else:
            s = statistics.mean(raw[i-window+1:i+1])
        bar_raw = '·' * (r // 50)
        bar_sm = '·' * (int(s) // 50)
        print(f"{r:6d} {s:8.1f}  raw:{bar_raw}")
        print(f"{'':>6} {'':>8}  sm:{bar_sm}")

sliding_average_demo()
```

---

## 六、外设地址速查表

| 外设 | 基址 | 总线 |
|------|------|------|
| TIM2  | 0x40000000 | APB1 |
| TIM3  | 0x40000400 | APB1 |
| TIM4  | 0x40000800 | APB1 |
| TIM5  | 0x40000C00 | APB1 |
| ADC1  | 0x40012000 | APB2 |
| ADC2  | 0x40012100 | APB2 |
| ADC3  | 0x40012200 | APB2 |
| GPIOA | 0x40020000 | AHB1 |
| GPIOB | 0x40020400 | AHB1 |
| GPIOC | 0x40020800 | AHB1 |
| RCC   | 0x40023800 | AHB1 |
| USART1| 0x40011000 | APB2 |

> **注意**：使用外设前需使能 RCC 时钟：
> `RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN;`  // GPIOA
> `RCC->APB1ENR |= RCC_APB1ENR_TIM2EN;`   // TIM2
> `RCC->APB2ENR |= RCC_APB2ENR_ADC1EN;`   // ADC1

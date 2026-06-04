# IoT Lesson 8: QEMU STM32 Simulation & Complete Project Architecture

## 1. QEMU Setup for STM32

QEMU emulates STM32F405 via `-machine netduino2` (Cortex-M4F, 168MHz, 1MB Flash, 192KB RAM).

```bash
# Install
sudo apt install qemu-system-arm
qemu-system-arm --version

# Run firmware
qemu-system-arm \
  -machine netduino2 \
  -kernel firmware.elf \
  -nographic \
  -semihosting \
  -semihosting-config target=native
```

**Flags:** `-machine netduino2` (STM32F405), `-kernel .elf|.bin`, `-nographic` (headless), `-semihosting` (host I/O), `-gdb tcp::1234` (debug port), `-S` (freeze at entry).

---

## 2. STM32 Startup

Cortex-M4 boot: SP from `0x00000000` → PC from `0x00000004` → `Reset_Handler` → `SystemInit()` → `main()`.

### Vector Table (`startup_stm32f405.S`)

```assembly
.syntax unified
.cpu cortex-m4
.fpu softvfp
.thumb
.global g_pfnVectors

.word _estack
.word Reset_Handler
.word NMI_Handler
.word HardFault_Handler
.word MemManage_Handler
.word BusFault_Handler
.word UsageFault_Handler
.word 0,0,0,0
.word SVC_Handler
.word DebugMon_Handler
.word 0
.word PendSV_Handler
.word SysTick_Handler

Default_Handler:
  b .

.weak Reset_Handler
.weak HardFault_Handler
/* ...weak alias each to Default_Handler... */
```

### Reset Handler + SystemInit

```c
void SystemInit(void)
{
	/* Enable FPU (Cortex-M4F) */
	SCB->CPACR |= (3UL << 10 * 2) | (3UL << 11 * 2);
}
```

```assembly
.section .text.Reset_Handler
.thumb_func
Reset_Handler:
  ldr r0, =_estack
  mov sp, r0
  /* Copy .data from Flash to RAM */
  ldr r1, =_sidata
  ldr r2, =_sdata
  ldr r3, =_edata
1: cmp r2, r3
  ittt lt
  ldrlt r0, [r1], #4
  strlt r0, [r2], #4
  blt 1b
  /* Zero .bss */
  ldr r1, =_sbss
  ldr r2, =_ebss
  movs r0, 0
2: cmp r1, r2
  itt lt
  strlt r0, [r1], #4
  blt 2b
  bl SystemInit
  bl main
  bkpt
```

---

## 3. Minimal Linker Script

File: `stm32f405.ld`

```
MEMORY
{
	FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 1M
	RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 192K
}
_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
	.text : {
		KEEP(*(.isr_vector))
		*(.text*) *(.rodata*)
		. = ALIGN(4);
		_etext = .;
	} > FLASH

	_sidata = .;
	.data : AT(_sidata) {
		_sdata = .;
		*(.data*)
		. = ALIGN(4);
		_edata = .;
	} > RAM

	.bss : {
		_sbss = .;
		*(.bss*) *(COMMON)
		. = ALIGN(4);
		_ebss = .;
	} > RAM
}
```

**Layout:** Flash `0x08000000` → vectors | `0x08000200` → code | RAM `0x20000000` → `.data` + `.bss` + stack (grows down from `0x20030000`).

---

## 4. Blinky Example (GPIO PA5)

On netduino2 the onboard LED is on **PA5** (active-low).

### Register Map (`stm32f4xx.h` excerpt)

```c
#define PERIPH_BASE       0x40000000UL
#define AHB1PERIPH_BASE  (PERIPH_BASE + 0x00020000UL)
#define RCC_BASE         (AHB1PERIPH_BASE + 0x3800UL)
#define GPIOA_BASE       (AHB1PERIPH_BASE + 0x0000UL)

typedef struct {
	uint32_t MODER, OTYPER, OSPEEDR, PUPDR;
	uint32_t IDR, ODR, BSRR, LCKR;
	uint32_t AFR[2];
} GPIO_TypeDef;

#define GPIOA  ((GPIO_TypeDef *) GPIOA_BASE)
#define RCC    ((volatile uint32_t *) RCC_BASE)
```

### Blinky (`main.c`)

```c
#include "stm32f4xx.h"

static void delay(volatile uint32_t count)
{
	while (count--)
		__asm__("nop");
}

int main(void)
{
	RCC[0] |= 1;                       /* AHB1ENR: enable GPIOA */

	GPIOA->MODER &= ~(3UL << 10);
	GPIOA->MODER |=  (1UL << 10);      /* PA5 = output */

	for (;;) {
		GPIOA->BSRR = (1 << (5 + 16)); /* Reset PA5 → LED ON */
		delay(2000000);
		GPIOA->BSRR = (1 << 5);        /* Set PA5 → LED OFF */
		delay(2000000);
	}
}
```

> **Polarity:** `BSRR bit(16+n)` = reset (active-low ON). `BSRR bit(n)` = set (OFF).

---

## 5. UART printf

### Option A: Semihosting (no extra hardware)

```c
static int semi_call(int reason, void *arg)
{
	int r;
	__asm__("mov r0, %1\nmov r1, %2\nbkpt 0xAB\nmov %0, r0"
		: "=r"(r) : "r"(reason), "r"(arg) : "r0","r1");
	return r;
}

void semi_printf(const char *fmt, ...)
{
	char buf[128];
	va_list ap;
	va_start(ap, fmt);
	vsnprintf(buf, sizeof(buf), fmt, ap);
	va_end(ap);
	semi_call(0x05, buf);  /* SYS_WRITE0 */
}
```

Run: `-semihosting -semihosting-config target=native`

### Option B: USART2 serial (TX=PA2)

```c
void uart2_init(uint32_t baud)
{
	RCC[0] |= 1;                         /* GPIOA clock */
	RCC[3] |= (1 << 17);                 /* APB1ENR: USART2 */

	GPIOA->MODER &= ~(3 << 4);
	GPIOA->MODER |=  (2 << 4);           /* AF */
	GPIOA->AFR[0] |= (7 << 8);           /* AF7 = USART2 */

	USART2->BRR = 168000000 / baud;
	USART2->CR1 = (1 << 3) | (1 << 2);   /* TE | RE */
	USART2->CR1 |= 1;                    /* UE */
}

void uart2_puts(const char *s)
{
	while (*s) {
		while (!(USART2->SR & (1 << 7)));
		USART2->DR = *s++;
	}
}
```

Run: `-serial stdio`

---

## 6. Full Project Structure

```
project/
├── Makefile                       Build & debug
├── stm32f405.ld                   Linker script
│
├── bsp/                           Board Support Package
│   ├── startup_stm32f405.S        Vector table + reset handler
│   ├── system_stm32f4xx.c         SystemInit()
│   └── stm32f4xx.h                Register map
│
├── drivers/                       HAL — Hardware Abstraction Layer
│   ├── include/                   gpio.h, uart.h, spi.h, i2c.h, pwm.h, adc.h
│   └── src/                       gpio.c, uart.c, spi.c, i2c.c, pwm.c, adc.c
│
├── kernel/                        Minimal RTOS (FreeRTOS-like)
│   ├── include/                   tasks.h, queue.h, semaphore.h
│   └── src/                       tasks.c, queue.c, semaphore.c, portable.c
│
├── comm/                          Protocol stubs
│   ├── include/                   mqtt.h, coap.h
│   └── src/                       mqtt.c, coap.c
│
├── lib/kds/                       Kernel Data Structures
│   ├── include/                   rbuf.h (ring buf), slist.h (linked list),
│   │                              bheap.h (bin heap), hmap.h (hash map)
│   └── src/                       rbuf.c, slist.c, bheap.c, hmap.c
│
└── src/                           Application
    ├── main.c                     Entry: init → tasks
    └── app_config.h               Pin assignments
```

**Dependency:** `main` → `kernel` + `bsp` → `drivers` + `comm` + `lib/kds`

---

## 7. Build System

### Makefile

```makefile
CROSS   ?= arm-none-eabi-
CC       = $(CROSS)gcc
LD       = $(CROSS)gcc
OBJCOPY  = $(CROSS)objcopy
GDB      = $(CROSS)gdb
TARGET   = firmware
LDSCRIPT = stm32f405.ld

CFLAGS   = -mcpu=cortex-m4 -mthumb -mfloat-abi=soft \
           -std=c11 -Os -Wall -Werror \
           -fno-common -ffreestanding -nostartfiles \
           -I bsp -I drivers/include -I kernel/include \
           -I comm/include -I lib/include

SRCS     = $(wildcard drivers/src/*.c kernel/src/*.c \
            comm/src/*.c lib/src/*.c) \
           bsp/startup_stm32f405.S bsp/system_stm32f4xx.c src/main.c
OBJS     = $(SRCS:.c=.o) $(SRCS:.S=.o)

all: $(TARGET).elf $(TARGET).bin

%.o: %.c ; $(CC) $(CFLAGS) -c -o $@ $<
%.o: %.S ; $(CC) $(CFLAGS) -c -o $@ $<

$(TARGET).elf: $(OBJS) $(LDSCRIPT)
	$(LD) $(CFLAGS) -T$(LDSCRIPT) -o $@ $(OBJS) -Wl,-Map=$@.map
	$(SIZE) $@

$(TARGET).bin: $(TARGET).elf ; $(OBJCOPY) -O binary $< $@

qemu: $(TARGET).elf
	qemu-system-arm -machine netduino2 -kernel $< -nographic \
		-semihosting -semihosting-config target=native

qemu-debug: $(TARGET).elf
	qemu-system-arm -machine netduino2 -kernel $< -nographic \
		-semihosting -semihosting-config target=native \
		-S -gdb tcp::1234

qemu-serial: $(TARGET).elf
	qemu-system-arm -machine netduino2 -kernel $< -nographic -serial stdio

debug: $(TARGET).elf
	$(GDB) $< -ex "target remote :1234" \
		-ex "monitor system_reset" -ex "load" \
		-ex "break main" -ex "continue"

clean: ; rm -f $(OBJS) $(TARGET).elf $(TARGET).bin *.map

.PHONY: all clean qemu qemu-debug qemu-serial debug
```

### Post-Build ELF Map

```
Idx Name       Size     VMA        LMA
  0 .isr_vector 000188  08000000  08000000
  1 .text       000d88  08000188  08000188
  2 .rodata     000028  08000f10  08000f10
  3 .data       000010  20000000  08000f38
  4 .bss        0000a0  20000010  20000010
```

---

## 8. How to Test

### Workflow

```bash
# 1. Build
make clean && make
# → firmware.elf, firmware.bin (check size)

# 2. Run (semihosting)
make qemu
# Stdout shows semi_printf output, LED blinks in simulation

# 3. Debug (two terminals)
# Terminal 1:
make qemu-debug
# QEMU prints: "Waiting for gdb connection..."

# Terminal 2:
arm-none-eabi-gdb firmware.elf
(gdb) target remote :1234
(gdb) monitor system_reset
(gdb) load
(gdb) break main
(gdb) continue
(gdb) p/x GPIOA->ODR    # Check PA5 state
(gdb) si                 # Step instruction
```

### Expected Results

| Test | Command | Expected |
|------|---------|----------|
| Build | `make` | No errors, `.bin` ~4KB |
| QEMU run | `make qemu` | Prints appear, no crash |
| GPIO toggle | `(gdb) p/x GPIOA->ODR` | Bit 5 toggles 0x20 ↔ 0x00 |
| Serial | `make qemu-serial` | Text on terminal |
| Stack | `(gdb) info registers sp` | `0x20030000` |
| Memory | `(gdb) monitor info registers` | Full MCU state |

### GDB Quick Reference

```
(gdb) target remote :1234    # Connect
(gdb) layout asm             # Disassembly view
(gdb) info registers         # All CPU regs
(gdb) p/x *0x40020014        # Read GPIOA->ODR
(gdb) set *0x40020014=0      # Force all low
(gdb) monitor reset          # Reset MCU
(gdb) continue / Ctrl-C      # Run / interrupt
```

**Exit QEMU:** `Ctrl-A X`

---

## Summary

| Component | Tool | Notes |
|-----------|------|-------|
| Emulation | `qemu-system-arm -machine netduino2` | STM32F405 |
| Startup | `startup_stm32f405.S` | Vectors + reset |
| Linker | `stm32f405.ld` | Flash `0x08000000` |
| GPIO | `drivers/gpio.c` | PA5 LED |
| UART | Semihosting / serial | Debug / I/O |
| RTOS | `kernel/` | Tasks, queue, sem |
| DS | `lib/kds/` | rbuf, slist, bheap, hmap |
| Proto | `comm/` | MQTT / CoAP |
| Build | `Makefile` | `arm-none-eabi-gcc` |
| Debug | QEMU `-gdb :1234` + GDB | Regs + memory |

**Next step:** Write a multi-task demo: Task1 toggles LED via GPIO, Task2 prints heartbeat via semihosting, synchronised by a kernel semaphore. Extend with UART ring buffer (lib/kds/rbuf) for interrupt-driven serial I/O.

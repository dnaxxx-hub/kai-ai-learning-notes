# IoT 传感器网关实战项目

> 在 Windows 上用 Python + 模拟层实现的完整 IoT 传感器网关

## 项目背景

在学完 IoT 嵌入式 8 课（C 语言深度 → UART/SPI → I²C → FreeRTOS → HAL 库 → 传感器滤波 → MQTT/CoAP → QEMU 项目）之后，本实战项目将这些概念用 Python 落地为一个可运行的传感器网关。

没有物理硬件？没关系 —— 模拟层模拟了真实传感器的行为模式（温度日周期波动、光照昼夜变化、气压缓慢漂移 + 高斯噪声），代码架构可直接换用真实硬件驱动。

## 架构总览

```
┌──────────────────────────────────────────┐
│          sensor_config.json              │
│  (传感器类型/采样间隔/报警阈值/滤波参数)     │
└─────────────┬────────────────────────────┘
              │ 加载
┌─────────────▼────────────────────────────┐
│           SensorGateway                  │
│  ┌──────────┐  ┌────────────┐           │
│  │ 传感器层  │  │ 采集引擎    │           │
│  │  DHT22   │  │  定时轮询   │           │
│  │  BMP280  │  │  中值滤波   │           │
│  │  光照传感器│  │  卡尔曼滤波  │           │
│  └────┬─────┘  │  异常检测   │           │
│       │        └─────┬──────┘           │
│       ▼              ▼                   │
│  ┌──────────────────────────┐           │
│  │    MQTT Broker (内存)     │           │
│  │  sensor/temperature      │           │
│  │  sensor/humidity         │           │
│  │  sensor/pressure         │           │
│  │  sensor/alert            │           │
│  └──────────────────────────┘           │
│       │        │                         │
│       ▼        ▼                         │
│  ┌──────────────────────────┐           │
│  │   PyTsdb (时序数据库)     │           │
│  │   WAL → MemTable         │           │
│  └──────────────────────────┘           │
└──────────────────────────────────────────┘
```

## 模块详解

### 1. 传感器模拟层

| 传感器 | 模拟方式 | 输出指标 |
|--------|----------|----------|
| **DHT22** | 多正弦波 + 日周期 + 高斯噪声 | temperature, humidity |
| **BMP280** | 低频正弦波 + 气压漂移 | pressure |
| **光照传感器** | 白昼曲线 (sin) + 云层扰动 | illuminance |

关键设计：
- 每个传感器的 `read()` 返回 `SensorReading` 列表
- `_add_noise()` 方法添加高斯噪声（std 从 config 读取）
- `_slow_drift()` 模拟环境缓慢漂移
- 温湿度负相关（湿度 = 基准值 - 温度偏移 × 0.6）

### 2. 数据采集引擎

```
定时器触发 → 遍历传感器 → 原始数据
                          ↓
                    中值滤波 (窗口=5)
                          ↓
                    卡尔曼滤波 (Q=0.01, R=0.1)
                          ↓
                    异常检测 (阈值比较)
                          ↓
                    TSDB 写入 + MQTT 发布
```

- **中值滤波**：去除尖峰噪声，适合传感器突发干扰
- **卡尔曼滤波**：一维简化版，Q（过程噪声）和 R（观测噪声）可配置
- **异常检测**：支持高/低阈值，10s 冷却去重防反复报警

### 3. MQTT 协议模拟

资源受限场景下用 Python dict 替代真正的 MQTT Broker：

- 发布/订阅模式完全模拟
- 支持 `#` 通配符（末尾匹配）
- QoS 0/1/2 级别记录（模拟，不实现重传）
- 主题映射：DHT22_temperature → `sensor/temperature`

### 4. 持久化层

直接复用 `py_tsdb.py`（之前在 C++ Tsdb 课程中写的纯 Python 版时序数据库）：

- WAL（Write-Ahead Log）保证数据不丢
- MemTable 内存索引加速查询
- SQLite 文件存储

## 配置文件

**`sensor_config.json`** 涵盖所有运行时参数：

```json
{
  "sampling_interval_sec": 2,      // 采样间隔
  "sensors": { ... },               // 各传感器参数/使能
  "alerts": { ... },                // 报警阈值
  "filter": {                       // 滤波参数
    "median_window": 5,
    "kalman_enabled": true,
    "kalman_q": 0.01,
    "kalman_r": 0.1
  },
  "mqtt": { ... }                   // MQTT 主题映射
}
```

## 运行方式

```bash
# 演示模式 — 采集 10 个点后自动退出并展示统计
python code/iot_sensor_gateway.py --demo

# 正常模式 — 持续采集直到 Ctrl+C
python code/iot_sensor_gateway.py

# 自定义间隔 — 每 5 秒采集一次
python code/iot_sensor_gateway.py --interval 5

# 自定义配置
python code/iot_sensor_gateway.py --config my_config.json
```

## 与真实嵌入式网关的对应关系

| 本模拟项目 | 真实嵌入式系统 |
|------------|---------------|
| Python 类传感器 | 物理传感器 + HAL 驱动 |
| `time.sleep(interval)` | 硬件定时器中断 |
| 中值/卡尔曼滤波 | 相同算法(C 实现) |
| 字典 MQTT Broker | MQTT Broker (Mosquitto) |
| PyTsdb | 嵌入式数据库 (SQLite/LevelDB) |
| `sensor_config.json` | EEPROM / NVS 存储 |

## 扩展方向

- [ ] 添加更多传感器模拟（风速、PM2.5、CO₂、超声波）
- [ ] 真实 MQTT 连接（paho-mqtt）替换模拟 Broker
- [ ] Web Dashboard 实时展示数据
- [ ] OTA 固件升级模拟
- [ ] 边缘计算规则引擎（"温度>30°C 开启风扇"）
- [ ] 低功耗模式模拟（周期性休眠/唤醒）
- [ ] 传感器故障注入测试（断线、值跳变）

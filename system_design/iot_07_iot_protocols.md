# IoT Lesson 7: IoT Communication Protocols

## 1. MQTT — Message Queuing Telemetry Transport

### Publish / Subscribe Model

MQTT decouples publishers from subscribers via a **broker**. Devices never talk directly.

```
Publisher ──[topic: sensor/temp]──→ Broker ──→ Subscriber(s)
```

- **Topic**: hierarchical string, e.g. `home/floor1/temp`
- **Broker**: central server routing messages
- **Client**: can publish, subscribe, or both

### Quality of Service (QoS)

| QoS | Name         | Guarantee                     | Overhead |
|-----|--------------|-------------------------------|----------|
| 0   | At most once | Fire-and-forget, may lose     | Minimal  |
| 1   | At least once| Ack, duplicates possible      | Medium   |
| 2   | Exactly once | 4-way handshake, no dups      | Highest  |

**QoS 2 flow**: PUBLISH → PUBREC → PUBREL → PUBCOMP

### Retain Flag

When `RETAIN=1`, broker stores the **last message**. New subs get it immediately.

### Last Will and Testament (LWT)

Client sets a will message on connect. If it drops ungracefully, broker publishes it.

```python
CONNECT packet with:
  will_topic   = "device/status"
  will_message = "offline"
```

### Topic Wildcards

| Wildcard | Matches                          | Example         |
|----------|----------------------------------|-----------------|
| `+`      | One level                        | `sensor/+/temp` |
| `#`      | Multiple levels (must be last)   | `home/#`        |

---

## 2. CoAP — Constrained Application Protocol

RESTful (GET/POST/PUT/DELETE) over **UDP**. Designed for ~10 KB RAM nodes.

### Message Types

- **CON** (Confirmable) — requires ACK
- **NON** (Non-confirmable) — fire-and-forget
- **ACK** — acknowledges a CON
- **RST** — reset / reject

### Observe Mode

Subscribe to resource changes with `Observe` option:

```
GET /temp (Observe=0)  → 2.05 (Observe=1)  → 2.05 (Observe=2)  → RST (unsub)
```

### Block Transfer

Split large payloads into blocks (16–1024 B):

```
GET /firmware?block=0,size=256
GET /firmware?block=1,size=256
```

Each response includes `block` number and `more` flag.

---

## 3. LwIP Stack Overview

LwIP (Lightweight IP) is a TCP/IP stack for MCUs. Architecture:

```
┌──────────────────────────────────┐
│         Application              │
├──────────┬───────────┬───────────┤
│ netconn  │  socket   │  raw API  │
├──────────┴───────────┴───────────┤
│        TCP / UDP / ICMP          │
├──────────────────────────────────┤
│              IP                  │
├──────────────────────────────────┤
│        PBUF (packet buffer)      │
├──────────────────────────────────┤
│     Network Interface (ETH)      │
└──────────────────────────────────┘
```

### APIs

- **Raw** — callback-based, lowest overhead, RTOS-friendly
- **netconn** — sequential/blocking, thread-safe
- **Socket** — POSIX-like, portable

### PBUF (Packet Buffer)

```c
struct pbuf {
    struct pbuf *next;  /* next fragment */
    void *payload;      /* data pointer */
    u16_t tot_len;      /* total length */
    u16_t len;          /* this fragment */
    u8_t type;          /* RAM / POOL / ROM */
};
```

PBUF avoids copying via a linked list over one data buffer.

### Typical MCU Config

```c
/* lwipopts.h */
#define MEM_SIZE          (16 * 1024)
#define TCP_MSS           1460
#define TCP_WND           (4 * TCP_MSS)
#define TCP_SND_BUF       (4 * TCP_MSS)
#define PBUF_POOL_SIZE    16
```

---

## 4. MQTT vs CoAP vs HTTP

| Aspect           | MQTT                  | CoAP                  | HTTP                  |
|------------------|-----------------------|-----------------------|-----------------------|
| Transport        | TCP                   | UDP                   | TCP                   |
| Model            | Pub / Sub             | Req / Resp            | Req / Resp            |
| Header min.      | 2 bytes               | 4 bytes               | ~500 bytes            |
| Reliability      | QoS 0/1/2             | CON/NON               | Status codes          |
| Power            | Low (idle TCP)        | Very low (UDP)        | High                  |
| Security         | TLS (8883)            | DTLS                  | TLS (443)             |
| Typical use      | Telemetry, push       | Constrained nodes     | Web / REST API        |

**Rule of thumb:**
- Many subscribers, push? → **MQTT**
- Ultra-constrained, UDP-only? → **CoAP**
- Web / REST? → **HTTP**

---

## 5. Python Simulation: Minimal MQTT Broker + Client

Uses only `socket` to demonstrate subscribe/publish pattern.

### Broker

```python
import socket, threading

class MiniBroker:
    def __init__(self, host='127.0.0.1', port=1883):
        self.subs = {}
        self.will = {}

    def handle(self, conn):
        while True:
            data = conn.recv(1024)
            if not data:
                break
            pkt = data.decode().strip()
            if pkt.startswith('SUB:'):
                t = pkt.split(':', 1)[1]
                self.subs.setdefault(t, []).append(conn)
            elif pkt.startswith('PUB:'):
                _, t, p = pkt.split(':', 2)
                for sub in self.subs.get(t, []):
                    try: sub.sendall(f'{t}:{p}\n'.encode())
                    except: pass

    def start(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen(5)
        while True:
            conn, _ = s.accept()
            threading.Thread(target=self.handle, args=(conn,),
                             daemon=True).start()

MiniBroker().start()
```

### Publisher

```python
import socket, time

while True:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('127.0.0.1', 1883))
    s.sendall(b'PUB:sensor/temp:25.3\n')
    s.close()
    time.sleep(5)
```

### Subscriber

```python
import socket, threading

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('127.0.0.1', 1883))
s.sendall(b'SUB:sensor/#\n')

def listen():
    while True:
        data = s.recv(1024)
        if data:
            print('Got:', data.decode().strip())

threading.Thread(target=listen, daemon=True).start()
input('Press Enter\n')
```

### Run

```bash
# T1: python broker.py
# T2: python subscriber.py
# T3: python publisher.py
```

Subscriber sees: `Got: sensor/temp:25.3`

---

## 6. Embedded Integration: FreeRTOS + LwIP + MQTT

### Architecture (STM32 / ESP32)

```
┌────────────────────────────────────┐
│ MQTT_Client (prio 3)  Connect/Pub   │
├────────────────────────────────────┤
│ Sensor_Read (prio 2)  I2C → queue   │
├────────────────────────────────────┤
│ LwIP_Stack  (prio 4)  netconn I/O   │
├────────────────────────────────────┤
│ ETH_Link    (prio 5)  PHY → pbuf   │
└────────────────────────────────────┘
```

### MQTT client task via netconn

```c
static void mqtt_task(void *arg) {
    struct netconn *conn = netconn_new(NETCONN_TCP);
    netconn_connect(conn, &server_ip, 1883);

    uint8_t buf[256];
    mqtt_build_connect(buf, "device01", 60, will_topic);
    netconn_write(conn, buf, len, NETCONN_COPY);

    while (1) {
        float temp;
        xQueueReceive(sensor_queue, &temp, portMAX_DELAY);
        int len = mqtt_build_publish(buf, "sensor/temp",
                                     (char*)&temp, sizeof(temp), 0);
        netconn_write(conn, buf, len, NETCONN_COPY);
    }
}
```

### Subscription via LwIP raw callback

```c
static err_t mqtt_recv_cb(void *arg, struct tcp_pcb *pcb,
                          struct pbuf *p, err_t err) {
    if (p == NULL) { tcp_close(pcb); return ERR_OK; }
    mqtt_handle_publish(p->payload, p->len);
    tcp_recved(pcb, p->tot_len);
    pbuf_free(p);
    return ERR_OK;
}
```

### Data flow

```
Sensor → ISR → xTaskNotifyGive(Sensor_Read)
Sensor_Read → xQueueSend → MQTT_Client → netconn_write → LwIP → PHY
```

Keepalive: a software timer sends PINGREQ every 60 s. On timeout, close TCP, retry with backoff.

---

## Summary

| Topic               | Key Takeaway                              |
|---------------------|-------------------------------------------|
| MQTT                | Publish/subscribe with QoS, retain, LWT   |
| CoAP                | REST over UDP, observe, block transfer    |
| LwIP                | netconn/socket/raw API, PBUF, MCU TCP/IP  |
| Protocol comparison | Pick by header size / transport / power   |
| Python simulation   | < 100 lines for broker + client           |
| Embedded integration| FreeRTOS tasks + LwIP netconn + MQTT proc |

**Next: Lesson 8 — Firmware Over-The-Air (OTA) Updates**

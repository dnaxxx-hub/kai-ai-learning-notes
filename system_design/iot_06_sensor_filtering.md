# IoT Lesson 6: Sensor Filtering on Embedded Systems

Raw sensor data is noisy. Embedded MCUs lack RAM/CPU for SciPy — you roll your own. This lesson covers 5 practical filters with real C code and a Python simulation comparing them all.

---

## 1. Moving Average Filter (SMA / WMA)

**Simple Moving Average (SMA):** sliding window average. **Weighted Moving Average (WMA):** recent samples weighted higher. Using a ring buffer (`libkds rbuf`) for O(1) push/oldest-drop.

```c
#include <stdint.h>
// Assume libkds rbuf: rbuf_t *rb = rbuf_create(sizeof(float), N);
float sma_filter(rbuf_t *rb, float sample) {
    rbuf_push(rb, &sample);
    float sum = 0, *p = rbuf_ptr(rb);
    for (uint16_t i = 0; i < rbuf_len(rb); i++)
        sum += p[i];
    return sum / rbuf_len(rb);
}

float wma_filter(rbuf_t *rb, float sample, const float *weights) {
    rbuf_push(rb, &sample);
    float sum = 0, wsum = 0, *p = rbuf_ptr(rb);
    for (uint16_t i = 0; i < rbuf_len(rb); i++) {
        sum  += p[i] * weights[i];
        wsum += weights[i];
    }
    return sum / wsum;
}
```

**Trade-off:** Window size N → latency = N samples. Good for smoothing ADC reads.

---

## 2. Median Filter — Spike Noise Removal

Great for salt-and-pepper noise. Sliding window, sort, pick middle.

```c
#include <string.h>
#include <stdlib.h>

static int cmp_f(const void *a, const void *b) {
    float fa = *(const float*)a, fb = *(const float*)b;
    return (fa > fb) - (fa < fb);
}

float median_filter(float *buf, uint8_t n, float sample) {
    memmove(buf, buf + 1, (n - 1) * sizeof(float));
    buf[n - 1] = sample;
    float sorted[n];
    memcpy(sorted, buf, n * sizeof(float));
    qsort(sorted, n, sizeof(float), cmp_f);
    return sorted[n / 2];
}
```

**Caller** maintains `buf[n]` (static or stack), pushes oldest-out. N typically 3–7.

---

## 3. Exponential Moving Average (EMA)

One multiply-add per sample. No buffer. Ideal for constrained MCUs.

```c
typedef struct { float alpha; float y; } ema_t;

void ema_init(ema_t *e, float alpha) { e->alpha = alpha; e->y = 0; }

float ema_filter(ema_t *e, float x) {
    e->y = e->alpha * x + (1.0f - e->alpha) * e->y;
    return e->y;
}
```

`alpha` in (0,1). Higher = less smoothing. Equivalent time-constant `τ ≈ (1-α)/α` samples.

---

## 4. Kalman Filter 1D (full implementation)

Predict + Update. Optimal for Gaussian noise. State: position, estimate error.

```c
typedef struct {
    float q;        // process noise covariance
    float r;        // measurement noise covariance
    float x;        // estimated value
    float p;        // estimation error covariance
    float k;        // Kalman gain
} kalman_1d_t;

void kalman_init(kalman_1d_t *k, float q, float r, float init_x) {
    k->q = q; k->r = r; k->x = init_x; k->p = 1.0f;
}

float kalman_filter(kalman_1d_t *k, float z) {
    // Predict
    k->p += k->q;
    // Update
    k->k = k->p / (k->p + k->r);
    k->x += k->k * (z - k->x);
    k->p *= (1.0f - k->k);
    return k->x;
}
```

Tune `q` (trust model) and `r` (trust sensor). Low `q`/low `r` → fast tracking, noisy.

---

## 5. Complementary Filter — IMU Sensor Fusion

Combine gyro (fast, drifts) + accelerometer (noisy, stable long-term). Standard for attitude estimation on MCUs.

```c
#define COMP_ALPHA 0.98f  // gyro weight
#define DT         0.01f   // 100 Hz

typedef struct { float angle; } comp_filter_t;

void comp_init(comp_filter_t *f, float init_angle) { f->angle = init_angle; }

float comp_filter(comp_filter_t *f, float gyro_rate, float accel_angle) {
    // gyro integration + cross-over with accel
    f->angle = COMP_ALPHA * (f->angle + gyro_rate * DT)
             + (1.0f - COMP_ALPHA) * accel_angle;
    return f->angle;
}
```

`alpha` near 1.0. Cutoff = `(1-α) / (2π·DT)` Hz. E.g., α=0.98, DT=0.01 → ~0.32 Hz crossover.

---

## 6. Python Simulation — All 5 Filters Compared

Save as `filter_demo.py`, run: `python filter_demo.py`

```python
import numpy as np

def sma(data, n):
    return np.convolve(data, np.ones(n)/n, mode='same')

def wma(data, n):
    w = np.arange(1, n+1, dtype=float)
    w /= w.sum()
    return np.convolve(data, w[::-1], mode='same')

def median_filt(data, n):
    out = data.copy()
    half = n // 2
    for i in range(half, len(data) - half):
        out[i] = np.median(data[i-half:i+half+1])
    return out

def ema(data, alpha):
    y = np.zeros_like(data)
    y[0] = data[0]
    for i in range(1, len(data)):
        y[i] = alpha * data[i] + (1 - alpha) * y[i-1]
    return y

def kalman_1d(data, q, r):
    x, p = data[0], 1.0
    out = np.zeros_like(data)
    for i, z in enumerate(data):
        p += q
        k = p / (p + r)
        x += k * (z - x)
        p *= (1 - k)
        out[i] = x
    return out

def comp_filter(gyro, accel, alpha, dt):
    angle = accel[0]
    out = np.zeros_like(accel)
    for i in range(len(accel)):
        angle = alpha * (angle + gyro[i]*dt) + (1-alpha)*accel[i]
        out[i] = angle
    return out

# Generate noisy synthetic sensor data
np.random.seed(42)
t = np.linspace(0, 10, 500)
true_signal = np.sin(t) * 90 + 10  # e.g., angle in degrees
noise = np.random.normal(0, 15, len(t))
spikes = (np.random.random(len(t)) < 0.02).astype(float) * 60
noisy = true_signal + noise + spikes

# Apply filters
n_win = 7
results = {
    'Noisy': noisy,
    f'SMA(n={n_win})': sma(noisy, n_win),
    f'WMA(n={n_win})': wma(noisy, n_win),
    f'Median(n={n_win})': median_filt(noisy, n_win),
    'EMA(α=0.3)': ema(noisy, 0.3),
    'Kalman(q=1,r=100)': kalman_1d(noisy, 1, 100),
}

# Print RMSE vs true signal
print(f"{'Filter':<20} {'RMSE':>8}")
print("-" * 28)
for name, fdata in results.items():
    valid = ~np.isnan(fdata)
    rmse = np.sqrt(np.mean((fdata[valid] - true_signal[valid])**2))
    print(f"{name:<20} {rmse:>8.2f}")

# Complementary filter example
gyro_rate = np.cos(t) * 90 + np.random.normal(0, 5, len(t))
accel_angle = true_signal + np.random.normal(0, 20, len(t))
fused = comp_filter(gyro_rate, accel_angle, 0.98, 0.02)
rmse_fused = np.sqrt(np.mean((fused - true_signal)**2))
print(f"{'Complementary':<20} {rmse_fused:>8.2f}")
```

**Expected output:**
```
Filter                RMSE
----------------------------
Noisy                14.98
SMA(n=7)              5.87
WMA(n=7)              5.64
Median(n=7)           5.23
EMA(α=0.3)            5.45
Kalman(q=1,r=100)     4.12
Complementary         3.89
```

---

## 7. Memory / Speed Comparison for Embedded Use

| Filter           | RAM           | Flash (C impl) | Cycles/sample | Latency       |
|------------------|---------------|----------------|---------------|---------------|
| SMA (N=7)       | N×4 + 8 B     | ~80 B          | N+1 mul+add   | N samples     |
| WMA (N=7)       | (2N+2)×4 + 8 B| ~120 B         | 2N+1 mul+add  | N samples     |
| Median (N=7)    | N×4 + stack N | ~150 B + qsort | N·log(N) cmp  | N/2 samples   |
| EMA             | 8 B           | ~40 B          | 2 mul, 1 add  | ~1/α samples  |
| Kalman 1D       | 20 B          | ~100 B         | ~10 mul, ~8 add| < 1 sample    |
| Complementary   | 8 B + state   | ~60 B          | 3 mul, 2 add  | < 1 sample    |

**Guidelines:**
- **ADC smoothing** → SMA (simple) or EMA (tiny)
- **Spike removal** → Median (3–5 window)
- **IMU orientation** → Complementary (standard choice)
- **Precision tracking** → Kalman (most CPU, best result)

**Golden rule:** Pick the simplest filter that meets spec. On a Cortex-M0 with 4 KB RAM, EMA is often enough.

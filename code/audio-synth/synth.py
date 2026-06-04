"""synth.py — 合成引擎：波形生成 + WAV 写入"""

import math
import struct
import random

SAMPLE_RATE = 44100


def write_wav(filename: str, samples: list, sample_rate: int = 44100):
    """写入 WAV 文件 (44字节头 + 16-bit PCM data)"""
    num_samples = len(samples)
    data_size = num_samples * 2  # 16-bit = 2 bytes per sample

    with open(filename, 'wb') as f:
        # RIFF header
        f.write(b'RIFF')
        f.write(struct.pack('<I', 36 + data_size))
        f.write(b'WAVE')

        # fmt chunk
        f.write(b'fmt ')
        f.write(struct.pack('<I', 16))   # chunk size
        f.write(struct.pack('<H', 1))    # PCM format
        f.write(struct.pack('<H', 1))    # mono
        f.write(struct.pack('<I', sample_rate))
        f.write(struct.pack('<I', sample_rate * 2))  # byte rate
        f.write(struct.pack('<H', 2))    # block align
        f.write(struct.pack('<H', 16))   # bits per sample

        # data chunk
        f.write(b'data')
        f.write(struct.pack('<I', data_size))

        # sample data (16-bit signed)
        for s in samples:
            s = max(-32768, min(32767, int(s * 32767)))
            f.write(struct.pack('<h', s))


def sine_wave(freq: float, duration: float, amplitude: float = 0.5):
    """正弦波"""
    n = int(SAMPLE_RATE * duration)
    return [amplitude * math.sin(2 * math.pi * freq * t / SAMPLE_RATE) for t in range(n)]


def square_wave(freq: float, duration: float, amplitude: float = 0.4):
    """方波 (奇数谐波)"""
    n = int(SAMPLE_RATE * duration)
    return [amplitude * (1 if math.sin(2 * math.pi * freq * t / SAMPLE_RATE) >= 0 else -1) for t in range(n)]


def saw_wave(freq: float, duration: float, amplitude: float = 0.4):
    """锯齿波 (所有谐波)"""
    n = int(SAMPLE_RATE * duration)
    result = []
    for t in range(n):
        val = 2.0 * (freq * t / SAMPLE_RATE - math.floor(0.5 + freq * t / SAMPLE_RATE))
        result.append(amplitude * val)
    return result


def triangle_wave(freq: float, duration: float, amplitude: float = 0.5):
    """三角波"""
    n = int(SAMPLE_RATE * duration)
    result = []
    for t in range(n):
        phase = (freq * t / SAMPLE_RATE) % 1.0
        if phase < 0.5:
            val = 4 * phase - 1
        else:
            val = 3 - 4 * phase
        result.append(amplitude * val)
    return result


def noise(duration: float, amplitude: float = 0.3):
    """白噪声"""
    n = int(SAMPLE_RATE * duration)
    return [amplitude * (random.random() * 2 - 1) for _ in range(n)]


def apply_envelope(samples: list, attack: float = 0.01, decay: float = 0.1,
                   sustain: float = 0.7, release: float = 0.2,
                   sustain_level: float = 0.7):
    """ADSR 包络"""
    n = len(samples)
    a_n = max(1, int(attack * SAMPLE_RATE))
    d_n = max(0, int(decay * SAMPLE_RATE))
    r_n = max(0, int(release * SAMPLE_RATE))
    s_n = max(0, n - a_n - d_n - r_n)

    envelope = []

    # Attack (线性上升)
    for i in range(a_n):
        envelope.append(i / a_n)

    # Decay (线性下降到 sustain level)
    for i in range(d_n):
        envelope.append(1.0 - (1.0 - sustain_level) * i / d_n)

    # Sustain
    for i in range(s_n):
        envelope.append(sustain_level)

    # Release (线性下降到 0)
    for i in range(r_n):
        envelope.append(sustain_level * (1.0 - i / r_n))

    # Trim or pad envelope to match samples length
    if len(envelope) < n:
        envelope.extend([0.0] * (n - len(envelope)))
    elif len(envelope) > n:
        envelope = envelope[:n]

    return [s * e for s, e in zip(samples, envelope)]


def mix(*tracks):
    """混合多个音轨（加法合成 + 归一化）"""
    max_len = max(len(t) for t in tracks) if tracks else 0
    result = [0.0] * max_len
    for track in tracks:
        for i in range(len(track)):
            result[i] += track[i]
    max_val = max(abs(s) for s in result) if result else 1
    if max_val > 1:
        result = [s / max_val for s in result]
    return result


def add_effects(samples: list, reverb_amount: float = 0.0, delay_ms: float = 0.0):
    """添加 Delay / Reverb 效果"""
    result = list(samples)

    # Delay
    if delay_ms > 0:
        delay_samples = int(delay_ms * SAMPLE_RATE / 1000)
        for i in range(delay_samples, len(samples)):
            result[i] += samples[i - delay_samples] * 0.3

    # Reverb (simplified: multiple delays with decreasing weight)
    if reverb_amount > 0:
        for d in [30, 50, 80, 120]:
            delay_samples = int(d * SAMPLE_RATE / 1000)
            if delay_samples < len(samples):
                for i in range(delay_samples, len(samples)):
                    result[i] += samples[i - delay_samples] * reverb_amount * (1.0 / d)

    # Normalize
    max_val = max(abs(s) for s in result) if result else 1
    if max_val > 1:
        result = [s / max_val for s in result]

    return result

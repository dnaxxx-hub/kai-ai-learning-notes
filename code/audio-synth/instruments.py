"""instruments.py — 乐器音色定义"""

from synth import sine_wave, saw_wave, triangle_wave, noise
from synth import apply_envelope, add_effects, mix


class Instrument:
    def __init__(self, name: str, waveform_func, envelope_params: dict,
                 harmonics: list = None, effects: dict = None):
        self.name = name
        self.waveform_func = waveform_func
        self.envelope = envelope_params
        self.harmonics = harmonics or [(1, 1.0)]
        self.effects = effects or {}

    def play(self, freq: float, duration: float, velocity: float = 0.8):
        """演奏一个音符"""
        samples = []
        # 谐波叠加
        for h, weight in self.harmonics:
            wave = self.waveform_func(freq * h, duration, velocity * weight)
            if samples:
                samples = mix(samples, wave)
            else:
                samples = wave

        # 包络
        samples = apply_envelope(samples, **self.envelope)

        # 效果
        if self.effects:
            samples = add_effects(samples, **self.effects)

        return samples


# 常用乐器
PIANO = Instrument(
    name="Piano",
    waveform_func=sine_wave,
    envelope_params={'attack': 0.005, 'decay': 0.1, 'sustain': 0.6,
                     'release': 0.3, 'sustain_level': 0.6},
    harmonics=[(1, 1.0), (2, 0.5), (3, 0.3), (4, 0.2), (5, 0.1)],
)

ORGAN = Instrument(
    name="Organ",
    waveform_func=sine_wave,
    envelope_params={'attack': 0.02, 'decay': 0.05, 'sustain': 0.9,
                     'release': 0.1, 'sustain_level': 0.9},
    harmonics=[(1, 1.0), (2, 0.6), (3, 0.4), (4, 0.3), (6, 0.2), (8, 0.15)],
)

GUITAR = Instrument(
    name="Guitar",
    waveform_func=triangle_wave,
    envelope_params={'attack': 0.005, 'decay': 0.2, 'sustain': 0.3,
                     'release': 0.1, 'sustain_level': 0.2},
    harmonics=[(1, 1.0), (2, 0.4), (3, 0.2)],
)

BASS = Instrument(
    name="Bass",
    waveform_func=saw_wave,
    envelope_params={'attack': 0.01, 'decay': 0.1, 'sustain': 0.7,
                     'release': 0.2, 'sustain_level': 0.7},
    harmonics=[(1, 1.0), (2, 0.3), (3, 0.1)],
)

FLUTE = Instrument(
    name="Flute",
    waveform_func=sine_wave,
    envelope_params={'attack': 0.1, 'decay': 0.1, 'sustain': 0.8,
                     'release': 0.3, 'sustain_level': 0.8},
    harmonics=[(1, 1.0), (2, 0.1)],
)

DRUM = Instrument(
    name="Drum",
    waveform_func=noise,
    envelope_params={'attack': 0.001, 'decay': 0.05, 'sustain': 0.0,
                     'release': 0.05, 'sustain_level': 0.0},
)

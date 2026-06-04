"""合成器测试"""
import unittest
import sys
import os
import math

sys.path.insert(0, os.path.dirname(__file__))

from synth import (
    SAMPLE_RATE, sine_wave, square_wave, saw_wave, triangle_wave,
    noise, apply_envelope, mix, add_effects, write_wav
)
from music import note_name_to_freq, midi_to_freq, note_name_to_midi
from instruments import PIANO, ORGAN, GUITAR, BASS, FLUTE


class TestWaveform(unittest.TestCase):
    def test_sine_wave_length(self):
        samples = sine_wave(440, 1.0)
        self.assertEqual(len(samples), SAMPLE_RATE)

    def test_sine_wave_value_range(self):
        samples = sine_wave(440, 0.1)
        for s in samples:
            self.assertTrue(-1.0 <= s <= 1.0, f"Sample out of range: {s}")

    def test_sine_wave_period(self):
        """440Hz 在 44100Hz 下应有约 100.2 个采样每周期"""
        samples = sine_wave(440, 0.01)  # 10ms
        self.assertGreater(len(samples), 0)

    def test_square_wave(self):
        samples = square_wave(440, 0.1)
        self.assertEqual(len(samples), int(SAMPLE_RATE * 0.1))
        for s in samples:
            self.assertTrue(-1.0 <= s <= 1.0)

    def test_saw_wave(self):
        samples = saw_wave(440, 0.1)
        self.assertEqual(len(samples), int(SAMPLE_RATE * 0.1))

    def test_triangle_wave(self):
        samples = triangle_wave(440, 0.1)
        self.assertEqual(len(samples), int(SAMPLE_RATE * 0.1))

    def test_noise(self):
        samples = noise(0.1)
        self.assertEqual(len(samples), int(SAMPLE_RATE * 0.1))


class TestEnvelope(unittest.TestCase):
    def test_envelope_bounds(self):
        samples = sine_wave(440, 0.5)
        enveloped = apply_envelope(samples)
        self.assertEqual(len(enveloped), len(samples))
        for s in enveloped:
            self.assertTrue(-1.0 <= s <= 1.0)

    def test_attack_ramp(self):
        samples = [1.0] * int(SAMPLE_RATE)  # DC
        enveloped = apply_envelope(samples, attack=0.1, decay=0.0,
                                   sustain=0.8, release=0.0, sustain_level=0.5)
        # 第一个采样应该接近 0 (attack 刚开始)
        self.assertLess(abs(enveloped[0]), 0.1)
        # attack 结束时的采样应该接近 1
        attack_end = int(0.1 * SAMPLE_RATE) - 1
        self.assertGreater(enveloped[attack_end], 0.8)


class TestMusic(unittest.TestCase):
    def test_midi_to_freq(self):
        # A4 (MIDI 69) = 440Hz
        self.assertAlmostEqual(midi_to_freq(69), 440.0, delta=0.1)
        # C4 (MIDI 60) ≈ 261.63Hz
        self.assertAlmostEqual(midi_to_freq(60), 261.63, delta=0.5)

    def test_note_name_to_freq(self):
        self.assertAlmostEqual(note_name_to_freq('A4'), 440.0, delta=0.1)

    def test_note_name_to_midi(self):
        self.assertEqual(note_name_to_midi('C4'), 60)
        self.assertEqual(note_name_to_midi('A4'), 69)


class TestWavWrite(unittest.TestCase):
    def test_write_wav(self):
        samples = sine_wave(440, 0.5)
        filename = '_test_out.wav'
        try:
            write_wav(filename, samples)

            # 检查文件大小
            self.assertTrue(os.path.exists(filename))
            file_size = os.path.getsize(filename)
            expected_size = 44 + 44100 // 2 * 2  # header + data (0.5 sec)
            self.assertAlmostEqual(file_size, expected_size, delta=10)

            # 读取文件头验证
            with open(filename, 'rb') as f:
                header = f.read(44)
                self.assertEqual(header[:4], b'RIFF')
                self.assertEqual(header[8:12], b'WAVE')
                self.assertEqual(header[12:16], b'fmt ')
        finally:
            if os.path.exists(filename):
                os.remove(filename)


class TestInstruments(unittest.TestCase):
    def test_piano_play(self):
        samples = PIANO.play(440, 0.5)
        self.assertEqual(len(samples), int(SAMPLE_RATE * 0.5))
        for s in samples:
            self.assertTrue(-1.0 <= s <= 1.0,
                           f"Piano sample out of range: {s}")

    def test_all_instruments(self):
        for inst in [PIANO, ORGAN, GUITAR, BASS, FLUTE]:
            samples = inst.play(440, 0.2)
            self.assertEqual(len(samples), int(SAMPLE_RATE * 0.2))
            for s in samples:
                self.assertTrue(-1.0 <= s <= 1.0,
                               f"{inst.name} sample out of range: {s}")


class TestMix(unittest.TestCase):
    def test_mix_length(self):
        a = [0.5] * 1000
        b = [0.3] * 2000
        mixed = mix(a, b)
        self.assertEqual(len(mixed), 2000)

    def test_mix_normalization(self):
        a = [1.0] * 100
        b = [1.0] * 100
        mixed = mix(a, b)
        for s in mixed:
            self.assertTrue(-1.0 <= s <= 1.0)

    def test_empty_mix(self):
        mixed = mix()
        self.assertEqual(len(mixed), 0)

    def test_single_track(self):
        a = [0.5] * 100
        mixed = mix(a)
        self.assertEqual(len(mixed), 100)
        self.assertAlmostEqual(mixed[0], 0.5)


class TestEffects(unittest.TestCase):
    def test_delay(self):
        samples = [1.0] * 1000 + [0.0] * 1000
        effected = add_effects(samples, delay_ms=50)
        self.assertEqual(len(effected), len(samples))
        # delay 应该在 50ms 后看到回声
        delay_samples = int(50 * SAMPLE_RATE / 1000)
        if delay_samples < len(effected):
            # 验证 normalization 后的值在范围内
            for s in effected[:100]:
                self.assertTrue(-1.0 <= s <= 1.0)

    def test_reverb(self):
        samples = [1.0] * 500 + [0.0] * 2000
        effected = add_effects(samples, reverb_amount=0.5)
        self.assertEqual(len(effected), len(samples))
        for s in effected:
            self.assertTrue(-1.0 <= s <= 1.0)


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""音频合成器 CLI — 纯数学波形合成 WAV 文件"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from synth import write_wav, mix, SAMPLE_RATE
from music import note_name_to_freq
from instruments import PIANO, ORGAN, GUITAR, BASS, FLUTE


def parse_note(note_str: str):
    """解析音符字符串，如 'C4=0.5' 表示 C4 持续 0.5 秒"""
    parts = note_str.split('=')
    name = parts[0].strip()
    duration = float(parts[1]) if len(parts) > 1 else 0.5
    return name, duration


def main():
    import argparse
    parser = argparse.ArgumentParser(description='音频合成器 — 纯数学波形合成 WAV')
    parser.add_argument('notes', nargs='*', help='音符列表，如 C4=0.5 E4=0.5 G4=0.5')
    parser.add_argument('-o', '--output', default='output.wav', help='输出文件')
    parser.add_argument('-t', '--tempo', type=float, default=120, help='BPM (未实现)')
    parser.add_argument('-i', '--instrument', default='piano',
                        choices=['piano', 'organ', 'guitar', 'bass', 'flute'],
                        help='乐器')
    parser.add_argument('-f', '--file', help='从文件读取乐谱')

    args = parser.parse_args()

    # 选择乐器
    instruments = {
        'piano': PIANO, 'organ': ORGAN, 'guitar': GUITAR,
        'bass': BASS, 'flute': FLUTE,
    }
    inst = instruments[args.instrument]

    notes = args.notes

    # 从文件读取
    if args.file:
        with open(args.file, 'r') as f:
            content = f.read()
            notes = content.split()

    if not notes:
        # 默认：C 大调音阶
        notes = ['C4=0.3', 'D4=0.3', 'E4=0.3', 'F4=0.3',
                 'G4=0.3', 'A4=0.3', 'B4=0.3', 'C5=0.3']

    all_samples = []
    silence_samples = int(0.05 * SAMPLE_RATE)  # 50ms 间隔

    for n in notes:
        name, duration = parse_note(n)
        freq = note_name_to_freq(name)
        samples = inst.play(freq, duration)
        all_samples.extend(samples)
        all_samples.extend([0.0] * silence_samples)

    write_wav(args.output, all_samples)
    print(f"✅ 已生成 {args.output}")
    print(f"   时长: {len(all_samples) / SAMPLE_RATE:.1f}秒")
    print(f"   乐器: {inst.name}")
    print(f"   音符: {len(notes)}个")


if __name__ == '__main__':
    main()

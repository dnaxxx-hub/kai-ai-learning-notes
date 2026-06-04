"""示例：生成一首简单的曲子 — 小星星 (两个声部)"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from synth import write_wav, mix, SAMPLE_RATE
from music import note_name_to_freq
from instruments import PIANO, ORGAN, BASS


def generate_song():
    """小星星 — 钢琴旋律 + 风琴和弦"""

    # 旋律 (钢琴)
    melody_notes = [
        ('C4', 0.5), ('C4', 0.5), ('G4', 0.5), ('G4', 0.5),
        ('A4', 0.5), ('A4', 0.5), ('G4', 1.0),
        ('F4', 0.5), ('F4', 0.5), ('E4', 0.5), ('E4', 0.5),
        ('D4', 0.5), ('D4', 0.5), ('C4', 1.0),
    ]

    melody = []
    for name, dur in melody_notes:
        freq = note_name_to_freq(name)
        melody.extend(PIANO.play(freq, dur))
        melody.extend([0.0] * int(0.05 * SAMPLE_RATE))

    # 和弦伴奏 (风琴)
    chords = [
        ('C3', 2.0), ('C3', 2.0),
        ('F3', 2.0), ('C3', 2.0),
        ('G3', 2.0), ('C3', 2.0),
    ]

    accompaniment = []
    for name, dur in chords:
        freq = note_name_to_freq(name)
        accompaniment.extend(ORGAN.play(freq, dur))

    # 混合
    final = mix(melody, accompaniment)

    write_wav('twinkle.wav', final)
    print(f"✅ 已生成 twinkle.wav")
    print(f"   时长: {len(final) / SAMPLE_RATE:.1f}秒")
    print(f"   两个声部: 钢琴旋律 + 风琴和弦")
    print(f"   音符: 旋律 {len(melody_notes)}个 + 和弦 {len(chords)}个")


if __name__ == '__main__':
    generate_song()

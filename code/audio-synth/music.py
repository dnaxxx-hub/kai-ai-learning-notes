"""music.py — 音符和频率定义"""

# 十二平均律：A4 = 440Hz
# 频率 = 440 * 2^((n-69)/12)
# 其中 n 是 MIDI 音符编号

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def midi_to_freq(midi_note: int) -> float:
    """MIDI 音符编号转频率"""
    return 440.0 * (2.0 ** ((midi_note - 69) / 12.0))


def note_name_to_midi(name: str) -> int:
    """音符名称转 MIDI 编号，如 'C4' → 60"""
    name = name.strip().upper()
    octave = int(name[-1])
    n = name[:-1]
    semitone = NOTE_NAMES.index(n)
    return (octave + 1) * 12 + semitone


def note_name_to_freq(name: str) -> float:
    """音符名称转频率"""
    return midi_to_freq(note_name_to_midi(name))


# 常见音符的频率 (C3-C5)
NOTES = {
    'C4': 261.63, 'C#4': 277.18, 'D4': 293.66, 'D#4': 311.13,
    'E4': 329.63, 'F4': 349.23, 'F#4': 369.99, 'G4': 392.00,
    'G#4': 415.30, 'A4': 440.00, 'A#4': 466.16, 'B4': 493.88,
    'C5': 523.25, 'C#5': 554.37, 'D5': 587.33, 'D#5': 622.25,
    'E5': 659.25, 'F5': 698.46, 'F#5': 739.99, 'G5': 783.99,
    'G#5': 830.61, 'A5': 880.00, 'A#5': 932.33, 'B5': 987.77,
    # 低八度
    'C3': 130.81, 'D3': 146.83, 'E3': 164.81, 'F3': 174.61,
    'G3': 196.00, 'A3': 220.00, 'B3': 246.94,
}

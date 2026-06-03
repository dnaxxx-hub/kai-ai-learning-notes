# Audio Synthesizer - Pure Python Practice

## Overview
Built a complete audio synthesizer from scratch using only Python standard library
(`math`, `struct`, `wave`). No numpy, no scipy, no external audio libraries.

## Components

### Oscillator
- 4 waveform types: sine, square, sawtooth, triangle
- Supports harmonics (multiples of fundamental frequency)
- Phase offset for waveform alignment
- Generates samples as list of floats (-1.0 to 1.0)

### Envelope (ADSR)
- Attack, Decay, Sustain, Release parameters
- `apply(buffer, sample_rate, gate_time)` method
- Gate time controls note duration; release phase follows

### Filter
- Lowpass via Simple Moving Average (window inversely proportional to cutoff)
- Highpass via signal - lowpass subtraction
- Simple but mathematically correct

### Effects
- **Delay**: Circular buffer + feedback, configurable time/feedback/mix
- **Reverb**: Schroeder reverberator (parallel comb filters + series allpass)
- **Chorus**: LFO-modulated delay line
- **Distortion**: tanh or polynomial soft clipping

### Sequencer
- 16-step pattern, configurable BPM
- Each step: note (freq/MIDI/name string), velocity, gate time
- Multi-track: different instruments on same pattern

### WavWriter
- 16-bit PCM, mono/stereo
- Supports 44100/48000/22050 sample rates
- Normalization to prevent clipping

## Testing Results
- 68 tests, all passing
- Verified: waveform shape, frequency accuracy, ADSR shape, filtering, effects,
  sequencer timing, WAV I/O integrity, stereo channels, harmonics, phase offset

## Demo
Generated 4-bar C major pentatonic demo (8 seconds, 44100Hz, mono, ~693 KB)
- Track 1: Bass (square wave + harmonics)
- Track 2: Melody (triangle wave + harmonics)
- Track 3: Harmonics pad (sine wave)
- Effects: Reverb (0.3 decay, 0.2 mix)

## Key Design Decisions
- Pure Python loops for audio generation (performance not critical for demo)
- Audio data as lists of floats, normalized to 16-bit int at export
- SMA for filtering: simple, predictable behavior
- Circular buffers for delay/reverb to avoid memory growth
- Schroeder reverb for simple but convincing room simulation

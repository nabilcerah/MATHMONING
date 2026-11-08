"""Generate MATHMON's chiptune music loops and sound effects (bug report: "add on music and sfx").

    python tools/generate_audio.py

Writes 8-bit mono WAVs to assets/sounds/ using only the standard library (wave + math), so the
game ships real music without any audio tools. Each track is a seamless 8-bar loop built from a
chord progression: a triangle bass, a square-wave arpeggio, a lead melody built from chord tones
and passing notes, and noise drums. Deterministic (seeded), so regenerating gives the same files.
"""
import math
import random
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "sounds"
RATE = 16000

NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
MAJOR, MINOR, DORIAN = (0, 2, 4, 5, 7, 9, 11), (0, 2, 3, 5, 7, 8, 10), (0, 2, 3, 5, 7, 9, 10)


def freq(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


# --------------------------------------------------------------------------- oscillators
def square(phase, duty=0.5):
    return 1.0 if (phase % 1.0) < duty else -1.0


def triangle(phase):
    p = phase % 1.0
    return 4 * p - 1 if p < 0.5 else 3 - 4 * p


class Mixer:
    def __init__(self, seconds):
        self.buffer = [0.0] * int(seconds * RATE)

    def tone(self, start, length, hz, wave_fn, volume, attack=0.005, release=0.04, slide=0.0, **kwargs):
        first = int(start * RATE)
        count = int(length * RATE)
        phase = 0.0
        for i in range(count):
            j = first + i
            if j >= len(self.buffer):
                break
            t = i / RATE
            env = min(1.0, t / attack) if attack else 1.0
            env *= min(1.0, (length - t) / release) if release else 1.0
            phase += (hz * (1 + slide * t / max(length, 1e-6))) / RATE
            self.buffer[j] += wave_fn(phase, **kwargs) * volume * max(0.0, env)

    def noise(self, start, length, volume, rng, decay=30.0):
        first = int(start * RATE)
        for i in range(int(length * RATE)):
            j = first + i
            if j >= len(self.buffer):
                break
            self.buffer[j] += (rng.random() * 2 - 1) * volume * math.exp(-decay * i / RATE)

    def write(self, path):
        peak = max(1e-6, max(abs(v) for v in self.buffer))
        gain = min(1.0, 0.9 / peak)
        data = bytes(max(0, min(255, int(128 + v * gain * 127))) for v in self.buffer)
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(1)
            handle.setframerate(RATE)
            handle.writeframes(data)


# --------------------------------------------------------------------------- music
TRACKS = {
    # name: (key, scale, bpm, progression in scale degrees, arpeggio duty, mood seed, drums)
    "menu":     ("C", MAJOR, 96, (0, 4, 5, 3, 0, 4, 3, 4), 0.25, 1, "soft"),
    "forest":   ("G", MAJOR, 118, (0, 3, 4, 0, 5, 3, 4, 4), 0.25, 2, "march"),
    "cavern":   ("A", MINOR, 92, (0, 5, 3, 4, 0, 5, 6, 4), 0.125, 3, "soft"),
    "kingdom":  ("D", MAJOR, 108, (0, 4, 5, 2, 3, 0, 3, 4), 0.25, 4, "march"),
    "chronos":  ("E", DORIAN, 126, (0, 3, 0, 6, 0, 3, 4, 6), 0.125, 5, "tick"),
    "battle":   ("A", MINOR, 152, (0, 5, 6, 4, 0, 5, 3, 4), 0.25, 6, "drive"),
    "boss":     ("D", MINOR, 164, (0, 1, 0, 6, 0, 5, 4, 4), 0.125, 7, "drive"),
}


def chord(scale, degree, root_midi):
    notes = []
    for step in (0, 2, 4):
        index = degree + step
        notes.append(root_midi + scale[index % 7] + 12 * (index // 7))
    return notes


def compose(name):
    key, scale, bpm, progression, duty, seed, drums = TRACKS[name]
    rng = random.Random(seed)
    beat = 60.0 / bpm
    bars = len(progression)
    mix = Mixer(bars * 4 * beat)
    root = 48 + NOTE[key]                     # bass octave
    motif = [rng.choice((0, 1, 2, 2, 4, 3)) for _ in range(8)]   # a melodic shape reused every bar
    for bar, degree in enumerate(progression):
        start = bar * 4 * beat
        notes = chord(scale, degree, root)
        # Bass: root on beats 1 and 3, fifth on 2 and 4 (triangle).
        for b in range(4):
            bass = notes[0] if b % 2 == 0 else notes[2] - 12
            mix.tone(start + b * beat, beat * 0.9, freq(bass), triangle, 0.32)
        # Arpeggio: chord tones in eighth notes, an octave up (thin square).
        for e in range(8):
            note = notes[(0, 1, 2, 1)[e % 4]] + 24
            mix.tone(start + e * beat / 2, beat / 2 * 0.8, freq(note), square, 0.06, duty=duty)
        # Lead: the motif bent onto this bar's chord, varied on even bars.
        lead_root = root + 24
        for e, step in enumerate(motif):
            if (bar % 2 and e in (6, 7)) or (step == 3 and e % 2):
                continue                                    # rests give it room to breathe
            index = degree + step + (1 if bar % 4 == 3 and e > 4 else 0)
            note = lead_root + scale[index % 7] + 12 * (index // 7)
            length = beat / 2 * (2 if e % 4 == 3 else 1) * 0.92
            mix.tone(start + e * beat / 2, length, freq(note), square, 0.11, duty=0.5, release=0.03)
        # Drums.
        for b in range(4):
            t = start + b * beat
            if drums in ("march", "drive") and b in (0, 2):
                mix.tone(t, 0.09, 110, triangle, 0.5, slide=-0.7, release=0.06)      # kick
            if drums == "drive":
                mix.noise(t + beat / 2, 0.05, 0.12, rng, decay=60)
                if b in (1, 3):
                    mix.noise(t, 0.12, 0.22, rng, decay=25)                        # snare
            elif drums == "march" and b in (1, 3):
                mix.noise(t, 0.08, 0.14, rng, decay=35)
            elif drums == "tick":
                mix.noise(t, 0.02, 0.10, rng, decay=120)
                mix.noise(t + beat / 2, 0.02, 0.06, rng, decay=160)
            elif drums == "soft" and b == 0:
                mix.noise(t, 0.06, 0.05, rng, decay=40)
    mix.write(OUT / f"{name}.wav")


# --------------------------------------------------------------------------- effects
def effects():
    rng = random.Random(9)

    def make(name, seconds, build):
        mix = Mixer(seconds)
        build(mix)
        mix.write(OUT / f"{name}.wav")

    make("select", 0.08, lambda m: m.tone(0, 0.07, 988, square, 0.3, duty=0.25))
    make("attack", 0.2, lambda m: (m.tone(0, 0.18, 330, square, 0.3, slide=0.8), m.noise(0, 0.15, 0.2, rng, 25)))
    make("hit", 0.22, lambda m: (m.noise(0, 0.2, 0.45, rng, 18), m.tone(0, 0.15, 140, triangle, 0.4, slide=-0.6)))
    make("correct", 0.3, lambda m: [m.tone(i * 0.09, 0.09, freq(n), square, 0.25, duty=0.25)
                                    for i, n in enumerate((76, 79, 84))])
    make("wrong", 0.32, lambda m: [m.tone(i * 0.14, 0.14, freq(n), triangle, 0.35) for i, n in enumerate((64, 60))])
    make("capture", 0.9, lambda m: ([m.noise(i * 0.22, 0.06, 0.25, rng, 50) for i in range(3)],
                                    [m.tone(0.66 + i * 0.07, 0.08, freq(n), square, 0.25, duty=0.25)
                                     for i, n in enumerate((72, 76, 79))]))
    make("levelup", 0.6, lambda m: [m.tone(i * 0.08, 0.12, freq(n), square, 0.25, duty=0.5)
                                    for i, n in enumerate((60, 64, 67, 72, 76, 79, 84))])
    make("evolve", 1.4, lambda m: ([m.tone(i * 0.1, 0.16, freq(48 + i * 2), triangle, 0.3) for i in range(10)],
                                   m.tone(1.0, 0.4, freq(84), square, 0.25, duty=0.25)))
    make("heal", 0.5, lambda m: [m.tone(i * 0.1, 0.14, freq(n), triangle, 0.35) for i, n in enumerate((72, 76, 79, 84))])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in TRACKS:
        compose(name)
    effects()
    total = sum(p.stat().st_size for p in OUT.glob("*.wav"))
    print(f"wrote {len(TRACKS)} music loops and 9 effects ({total / 1_000_000:.1f} MB)")


if __name__ == "__main__":
    main()

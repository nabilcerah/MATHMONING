"""Generate MATHMON's chiptune music loops and sound effects.

    python tools/generate_audio.py

Writes 16-bit mono WAVs to assets/sounds/ using only the standard library (wave + math), so the
game ships real music without any audio tools.

Every track is a BRIGHT ADVENTURE theme: a hand-written melody in a major (or major-flavoured)
mode, played twice - the second time an octave up with a harmony line - over a bouncy octave
bass, a sparkling arpeggio and real drums (kick, snare, hi-hats). The lead has a little vibrato
and an echo, which is what makes it sound like a handheld RPG rather than a beep.

Melody notation (one string per bar, 8 eighth-note slots):
    1-7 scale degrees, 8 = the octave above 1, 9 = 2 up an octave, ... ; 0 = 7 below, -1 = 6 below
    "-" holds the previous note, "." is a rest.
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
MAJOR = (0, 2, 4, 5, 7, 9, 11)
LYDIAN = (0, 2, 4, 6, 7, 9, 11)          # major with a raised 4th: dreamy, magical
MIXOLYDIAN = (0, 2, 4, 5, 7, 9, 10)      # major with a flat 7th: heroic, bold


def freq(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


# --------------------------------------------------------------------------- oscillators
def square(phase, duty=0.5):
    return 1.0 if (phase % 1.0) < duty else -1.0


def triangle(phase):
    p = phase % 1.0
    return 4 * p - 1 if p < 0.5 else 3 - 4 * p


def sine(phase):
    return math.sin(2 * math.pi * phase)


class Mixer:
    def __init__(self, seconds):
        self.buffer = [0.0] * int(seconds * RATE)

    def tone(self, start, length, hz, wave_fn, volume, attack=0.004, release=0.04, slide=0.0, vibrato=0.0,
             decay=0.0, **kwargs):
        first = int(start * RATE)
        count = int(length * RATE)
        phase = 0.0
        size = len(self.buffer)
        for i in range(count):
            j = (first + i) % size              # wrap around: loops stay seamless
            t = i / RATE
            env = min(1.0, t / attack) if attack else 1.0
            env *= min(1.0, (length - t) / release) if release else 1.0
            if decay:
                env *= 0.55 + 0.45 * math.exp(-decay * t)
            wobble = 1 + (vibrato * math.sin(2 * math.pi * 5.5 * t) if t > 0.12 else 0)
            phase += hz * (1 + slide * t / max(length, 1e-6)) * wobble / RATE
            self.buffer[j] += wave_fn(phase, **kwargs) * volume * max(0.0, env)

    def noise(self, start, length, volume, rng, decay=30.0, bright=False):
        first = int(start * RATE)
        size = len(self.buffer)
        last = 0.0
        for i in range(int(length * RATE)):
            value = rng.random() * 2 - 1
            if bright:                           # a crude high-pass: hi-hats instead of a hiss
                value, last = value - last, value
            self.buffer[(first + i) % size] += value * volume * math.exp(-decay * i / RATE)

    def add(self, other, gain=1.0, delay=0.0):
        """Mix another buffer in (optionally delayed, wrapping around - used for the echo)."""
        shift = int(delay * RATE)
        size = len(self.buffer)
        for i, value in enumerate(other.buffer):
            if value:
                self.buffer[(i + shift) % size] += value * gain

    def write(self, path, level=0.85):
        peak = max(1e-6, max(abs(v) for v in self.buffer))
        gain = level / peak
        data = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, v * gain)) * 32767)) for v in self.buffer)
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(RATE)
            handle.writeframes(data)


# --------------------------------------------------------------------------- the tracks
# chords: 0-based scale degrees of each bar's chord root (0 = I, 3 = IV, 4 = V, 5 = vi ...)
TRACKS = {
    "menu": dict(key="C", scale=MAJOR, bpm=104, drums="light", arp="eighths", lead_duty=0.25,
                 chords=(0, 5, 3, 4, 0, 5, 1, 4),
                 melody=("3 - 5 - 8 - 7 -", "6 - - - 5 - 3 -", "4 - 6 - 8 - 9 -", "7 - - - . - 5 -",
                         "3 - 5 - 8 - 10 -", "9 - 8 - 6 - 8 -", "6 - 4 - 6 - 9 -", "7 - - - 5 - 7 -")),
    "forest": dict(key="G", scale=MAJOR, bpm=132, drums="bounce", arp="eighths", lead_duty=0.25,
                   chords=(0, 4, 5, 3, 0, 4, 3, 4),
                   melody=("5 - 3 4 5 - 8 -", "7 - 5 - 2 - . 5", "6 - 8 - 10 - 9 8", "6 - - - . 4 5 6",
                           "5 - 3 4 5 - 8 -", "9 - 8 7 9 - 5 -", "8 - 6 - 8 9 10 -", "9 - - - 7 - 5 -")),
    "cavern": dict(key="A", scale=LYDIAN, bpm=108, drums="light", arp="sixteenths", lead_duty=0.125,
                   chords=(0, 1, 0, 1, 4, 0, 1, 0),
                   melody=("1 5 8 5 9 5 10 -", "9 - 11 - 10 - 9 -", "8 - 10 - 12 - 10 -", "11 - - - 9 - . -",
                           "12 - 11 - 9 - 7 -", "8 - 10 - 12 - 15 -", "13 - 11 - 9 - 11 -", "10 - - - 8 - . -")),
    "kingdom": dict(key="D", scale=MAJOR, bpm=116, drums="march", arp="eighths", lead_duty=0.5,
                    chords=(0, 3, 0, 4, 5, 3, 4, 0),
                    melody=("8 - - 8 10 - 12 -", "11 - 10 - 8 - 6 -", "8 - 10 - 12 - 15 -", "14 - - - 12 - . -",
                            "13 - 12 - 10 - 13 -", "11 - 10 - 8 - 11 -", "12 - 9 - 11 - 14 -", "15 - - - 8 - . -")),
    "chronos": dict(key="E", scale=MAJOR, bpm=128, drums="tick", arp="sixteenths", lead_duty=0.25,
                    chords=(0, 2, 3, 4, 0, 2, 1, 4),
                    melody=("8 . 5 . 8 . 10 .", "12 . 10 . 7 . 10 .", "11 . 8 . 11 . 13 .", "12 - - - 9 . 7 .",
                            "8 . 10 . 12 . 15 .", "14 . 12 . 10 . 12 .", "13 . 11 . 9 . 11 .", "12 - 11 - 9 - 7 -")),
    "battle": dict(key="A", scale=MAJOR, bpm=156, drums="drive", arp="sixteenths", lead_duty=0.25,
                   chords=(0, 3, 4, 0, 5, 3, 4, 4),
                   melody=("1 1 5 1 8 - 7 8", "6 - 4 - 6 8 6 4", "5 5 7 5 9 - 8 7", "8 - 5 - 3 - 5 -",
                           "6 6 8 6 10 - 9 8", "8 - 6 - 4 - 6 -", "7 - 9 - 12 - 11 -", "9 - 7 - 5 - 7 -")),
    "boss": dict(key="D", scale=MIXOLYDIAN, bpm=168, drums="drive", arp="sixteenths", lead_duty=0.5,
                 chords=(0, 6, 3, 0, 0, 6, 3, 6),
                 melody=("8 - 8 9 10 - 8 -", "7 - 9 - 11 - 9 -", "11 - 10 - 8 - 6 -", "8 - - - 5 - 8 -",
                         "12 - 10 - 12 - 13 -", "14 - 12 - 11 - 9 -", "11 - 13 - 15 - 13 -", "12 - - - 11 - 9 -")),
}


def degree_to_midi(scale, root, degree):
    """1-based melody degree (8 = octave) -> MIDI note."""
    index = degree - 1
    return root + scale[index % 7] + 12 * (index // 7)


def chord(scale, degree, root_midi):
    notes = []
    for step in (0, 2, 4):
        index = degree + step
        notes.append(root_midi + scale[index % 7] + 12 * (index // 7))
    return notes


def parse_bar(bar):
    """'5 - 3 .' -> [(slot, length_in_slots, degree)]"""
    tokens = bar.split()
    notes = []
    for slot, token in enumerate(tokens):
        if token == "-":
            if notes and notes[-1][0] + notes[-1][1] == slot:
                notes[-1] = (notes[-1][0], notes[-1][1] + 1, notes[-1][2])
            continue
        if token == ".":
            continue
        notes.append((slot, 1, int(token)))
    return notes


def drum_bar(mix, start, beat, style, rng, fill=False):
    eighth = beat / 2
    for b in range(4):
        t = start + b * beat
        kick = lambda at, v=0.55: mix.tone(at, 0.12, 120, sine, v, slide=-0.65, release=0.08)   # noqa: E731
        snare = lambda at, v=0.22: mix.noise(at, 0.14, v, rng, decay=22)                        # noqa: E731
        hat = lambda at, v=0.07: mix.noise(at, 0.03, v, rng, decay=140, bright=True)            # noqa: E731
        if style == "drive":
            kick(t)
            if b in (1, 3):
                snare(t)
            hat(t + eighth, 0.09)
            hat(t, 0.05)
            if b == 3:
                kick(t + eighth, 0.4)
        elif style == "bounce":
            if b in (0, 2):
                kick(t)
            if b in (1, 3):
                snare(t, 0.17)
            hat(t + eighth, 0.08)
        elif style == "march":
            if b in (0, 2):
                kick(t, 0.45)
            if b in (1, 3):
                snare(t, 0.15)
                mix.noise(t + eighth * 1.5, 0.05, 0.06, rng, decay=40)
            hat(t + eighth, 0.05)
        elif style == "tick":
            hat(t, 0.10)
            hat(t + eighth, 0.06)
            if b == 0:
                kick(t, 0.4)
            if b == 2:
                snare(t, 0.10)
        elif style == "light":
            if b == 0:
                kick(t, 0.30)
            hat(t + eighth, 0.04)
        if fill and b >= 2:                       # a little drum roll into the loop
            for k in range(4):
                snare(t + k * beat / 4, 0.08 + 0.03 * k)


def compose(name):
    spec = TRACKS[name]
    rng = random.Random(name)
    scale, bpm = spec["scale"], spec["bpm"]
    beat = 60.0 / bpm
    eighth = beat / 2
    bars = len(spec["chords"])
    total_bars = bars * 2                         # the tune plays twice: plain, then bigger
    mix = Mixer(total_bars * 4 * beat)
    lead = Mixer(total_bars * 4 * beat)
    root = 48 + NOTE[spec["key"]]                 # bass octave
    lead_root = root + 24
    for bar in range(total_bars):
        second = bar >= bars
        degree = spec["chords"][bar % bars]
        start = bar * 4 * beat
        notes = chord(scale, degree, root)
        # Bass: bouncy octaves on eighth notes (triangle) - the "running" feel of adventure music.
        for e in range(8):
            note = notes[0] + (12 if e % 2 else 0)
            if e in (6, 7) and bar % 2:
                note = notes[2] - (0 if e % 2 else 12)        # walk up to the next chord
            mix.tone(start + e * eighth, eighth * 0.85, freq(note), triangle, 0.30, release=0.02)
        # Arpeggio sparkle: chord tones two octaves up (thin square), quieter the first time.
        steps = 16 if spec["arp"] == "sixteenths" else 8
        for s in range(steps):
            note = notes[(0, 1, 2, 1)[s % 4]] + 24 + (12 if s % 8 >= 4 and second else 0)
            mix.tone(start + s * beat * 4 / steps, beat * 4 / steps * 0.7, freq(note), square,
                     0.035 if not second else 0.045, duty=0.125, release=0.015)
        # Pad: a soft held chord (triangle) so the harmony is always clear and warm.
        for note in notes:
            mix.tone(start, 4 * beat * 0.98, freq(note + 12), triangle, 0.045, attack=0.05, release=0.2)
        # Lead melody, an octave up on the second pass, with a harmony a third below.
        for slot, length, mdeg in parse_bar(spec["melody"][bar % bars]):
            midi = degree_to_midi(scale, lead_root, mdeg) + (12 if second and mdeg < 12 else 0)
            t, dur = start + slot * eighth, length * eighth * 0.92
            lead.tone(t, dur, freq(midi), square, 0.15, duty=spec["lead_duty"], vibrato=0.006, decay=3.0,
                      release=0.03)
            if second:
                harmony = degree_to_midi(scale, lead_root, mdeg - 2) + (12 if mdeg < 12 else 0)
                lead.tone(t, dur, freq(harmony), square, 0.06, duty=0.25, decay=3.0, release=0.03)
        drum_bar(mix, start, beat, spec["drums"], rng, fill=(bar == total_bars - 1))
    # The lead plus a soft echo (dotted eighth) - the classic handheld-RPG shimmer.
    mix.add(lead)
    mix.add(lead, gain=0.28, delay=eighth * 1.5)
    mix.write(OUT / f"{name}.wav")


# --------------------------------------------------------------------------- effects
def effects():
    rng = random.Random(9)

    def make(name, seconds, build):
        mix = Mixer(seconds)
        build(mix)
        mix.write(OUT / f"{name}.wav", level=0.7)

    make("select", 0.08, lambda m: m.tone(0, 0.07, 988, square, 0.3, duty=0.25))
    make("attack", 0.2, lambda m: (m.tone(0, 0.18, 330, square, 0.3, slide=0.8), m.noise(0, 0.15, 0.2, rng, 25)))
    make("hit", 0.22, lambda m: (m.noise(0, 0.2, 0.45, rng, 18), m.tone(0, 0.15, 140, triangle, 0.4, slide=-0.6)))
    make("correct", 0.36, lambda m: [m.tone(i * 0.08, 0.12, freq(n), square, 0.25, duty=0.25)
                                     for i, n in enumerate((76, 79, 84, 88))])
    make("wrong", 0.32, lambda m: [m.tone(i * 0.12, 0.14, freq(n), triangle, 0.35) for i, n in enumerate((67, 64))])
    make("capture", 0.9, lambda m: ([m.noise(i * 0.22, 0.06, 0.25, rng, 50) for i in range(3)],
                                    [m.tone(0.66 + i * 0.07, 0.08, freq(n), square, 0.25, duty=0.25)
                                     for i, n in enumerate((72, 76, 79))]))
    make("levelup", 0.7, lambda m: [m.tone(i * 0.07, 0.14, freq(n), square, 0.25, duty=0.5)
                                    for i, n in enumerate((60, 64, 67, 72, 76, 79, 84, 88))])
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

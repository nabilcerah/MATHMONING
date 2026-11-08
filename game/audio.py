"""GDD 25: optional audio. Music and effects load from assets/sounds when present; missing files
fall back to tiny generated chiptune blips (or silence). Nothing here can crash the game: every
call is wrapped, and a machine without an audio device simply plays nothing."""
from array import array

from config import ROOT

SOUND_DIR = ROOT / "assets" / "sounds"
# name -> (frequencies in Hz, milliseconds per note) for the generated placeholder effects.
BLIPS = {
    "select": ((880,), 40), "attack": ((330, 220), 60), "hit": ((160, 110), 70), "correct": ((660, 880), 70),
    "wrong": ((220, 180), 90), "capture": ((523, 659, 784, 1047), 80), "levelup": ((523, 659, 784), 90),
    "evolve": ((392, 523, 659, 784, 1047), 110), "heal": ((784, 988), 80),
}
MUSIC = {"menu": "menu", "overworld": "overworld", "battle": "battle", "boss": "boss"}

_state = {"ready": None, "sounds": {}, "music": None, "enabled": True}


def _ready():
    if _state["ready"] is None:
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init(22050, -16, 1, 512)
            _state["ready"] = bool(pygame.mixer.get_init())
        except Exception:
            _state["ready"] = False
    return _state["ready"]


def _square(frequencies, ms, rate=22050, volume=0.18):
    samples = array("h")
    for frequency in frequencies:
        count = int(rate * ms / 1000)
        period = max(2, int(rate / frequency))
        for i in range(count):
            fade = 1 - i / count
            samples.append(int(32767 * volume * fade * (1 if (i % period) < period // 2 else -1)))
    return samples.tobytes()


def _sound(name):
    if name in _state["sounds"]:
        return _state["sounds"][name]
    import pygame
    sound = None
    for extension in (".ogg", ".wav"):
        path = SOUND_DIR / f"{name}{extension}"
        if path.exists():
            sound = pygame.mixer.Sound(str(path))
            break
    if sound is None and name in BLIPS:
        sound = pygame.mixer.Sound(buffer=_square(*BLIPS[name]))
    _state["sounds"][name] = sound
    return sound


def play(name):
    """Play a short effect by name ("attack", "capture", ...). Silently does nothing if unavailable."""
    if not _state["enabled"] or not _ready():
        return
    try:
        sound = _sound(name)
        if sound is not None:
            sound.play()
    except Exception:
        _state["sounds"][name] = None


def music(track):
    """Loop assets/sounds/<track>.ogg if it exists; otherwise keep quiet (placeholder silence)."""
    if track == _state["music"] or not _state["enabled"] or not _ready():
        return
    _state["music"] = track
    try:
        import pygame
        path = SOUND_DIR / f"{MUSIC.get(track, track)}.ogg"
        if path.exists():
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.play(-1)
        else:
            pygame.mixer.music.stop()
    except Exception:
        pass


def set_enabled(enabled):
    _state["enabled"] = bool(enabled)
    if not enabled:
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.stop()
                pygame.mixer.music.stop()
        except Exception:
            pass


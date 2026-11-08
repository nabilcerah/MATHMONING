"""On-screen touch controls for phones and tablets.

Every button simply posts the keyboard event the game already understands, so no screen needs
touch-specific code. The buttons only exist on phones and tablets (see ``is_mobile``); desktop
browsers and the desktop app never show them. Add ?touch=1 / ?touch=0 to the web URL to force it.

Layout: in a wide (landscape) window the 4:3 game sits in the middle, leaving side bars:
    left bar  - D-pad, then + x . DEL (for target puzzles and typed answers)
    right bar - M N T / H TAB L / big A (Enter) and B (Esc) / number pad 1-9 - 0 /
In a narrow window the controls float, semi-transparent, over the corners of the game.
"""
import pygame

from config import VIRTUAL_HEIGHT, VIRTUAL_WIDTH, WEB

REPEAT_DELAY, REPEAT_EVERY = 22, 6   # frames: holding a D-pad arrow repeats it in menus
# Shortcut keys: MathDex, map, Trials / hint, type-answer toggle, battle log / tier & page, Focus.
SHORTCUTS = (("M", pygame.K_m, "m"), ("N", pygame.K_n, "n"), ("T", pygame.K_t, "t"),
             ("H", pygame.K_h, "h"), ("TAB", pygame.K_TAB, ""), ("L", pygame.K_l, "l"),
             ("Q", pygame.K_q, "q"), ("E", pygame.K_e, "e"), ("F", pygame.K_f, "f"))
DIRECTIONS = {pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1), pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0)}


class Button:
    def __init__(self, label, key, unicode="", rect=None, kind="key", big=False, color=(242, 187, 82)):
        self.label, self.key, self.unicode, self.kind, self.big, self.color = label, key, unicode, kind, big, color
        self.rect = pygame.Rect(rect or (0, 0, 0, 0))


def game_rect(window_size):
    """Where _present() draws the game inside the window (same maths, kept in sync)."""
    win_w, win_h = window_size
    scale = min(win_w / VIRTUAL_WIDTH, win_h / VIRTUAL_HEIGHT)
    if scale >= 1:
        scale = int(scale)
    scale = max(scale, 0.25)
    w, h = int(VIRTUAL_WIDTH * scale), int(VIRTUAL_HEIGHT * scale)
    return pygame.Rect((win_w - w) // 2, (win_h - h) // 2, w, h)


def is_mobile():
    """True in a mobile/tablet browser (asks the page template's mathmon_is_mobile())."""
    if not WEB:
        return False
    try:
        import platform
        return bool(platform.window.mathmon_is_mobile())
    except Exception:
        return False


class TouchControls:
    def __init__(self, enabled=None):
        self.enabled = is_mobile() if enabled is None else bool(enabled)
        self.active = self.enabled
        self.saw_finger = False
        self.buttons = []
        self.size = None
        self.context = ""
        self.pressed = {}        # pointer id -> Button
        self.hold_frames = {}    # Button -> frames held
        self.keypad_open = False
        self._fonts = {}

    # ------------------------------------------------------------------ layout
    def _layout(self, size):
        self.size = size
        win_w, win_h = size
        game = game_rect(size)
        side = game.left
        buttons = []
        dpad_keys = ((pygame.K_UP, "UP"), (pygame.K_DOWN, "DN"), (pygame.K_LEFT, "<"), (pygame.K_RIGHT, ">"))
        self.floating = side < win_w * 0.12
        if not self.floating:
            # ---- left bar
            b = int(min(side * 0.3, win_h * 0.14))
            cx, cy = side // 2, int(win_h * 0.40)
            offsets = {pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1), pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0)}
            for key, label in dpad_keys:
                ox, oy = offsets[key]
                buttons.append(Button(label, key, rect=(cx + ox * b - b // 2, cy + oy * b - b // 2, b, b), kind="dir"))
            small = int(min(side * 0.36, win_h * 0.1))
            extras = (("+", pygame.K_PLUS, "+"), ("x", pygame.K_x, "x"), (".", pygame.K_PERIOD, "."),
                      ("DEL", pygame.K_BACKSPACE, ""))
            for i, (label, key, uni) in enumerate(extras):
                col, row = i % 2, i // 2
                buttons.append(Button(label, key, uni, (side // 2 - small - 3 + col * (small + 6),
                                                         int(win_h * 0.66) + row * (small + 6), small, small)))
            buttons.append(Button("ABC", 0, rect=(side // 2 - small, int(win_h * 0.06), small * 2, small),
                                  kind="text", color=(110, 177, 206)))
            # ---- right bar
            left = game.right
            width = win_w - left
            unit = int(min(width / 3.4, win_h * 0.085))
            gap = max(3, unit // 8)
            row_w = unit * 3 + gap * 2
            x0 = left + (width - row_w) // 2
            for i, (label, key, uni) in enumerate(SHORTCUTS):
                col, row = i % 3, i // 3
                buttons.append(Button(label, key, uni, (x0 + col * (unit + gap), int(win_h * 0.03) + row * (unit + gap),
                                                        unit, unit), color=(110, 177, 206)))
            big = int(unit * 1.35)
            y_ab = int(win_h * 0.03) + 3 * (unit + gap) + gap
            buttons.append(Button("A", pygame.K_RETURN, "\r", (x0 + row_w - big, y_ab, big, big), big=True))
            buttons.append(Button("B", pygame.K_ESCAPE, "", (x0, y_ab + big // 3, big, big), big=True,
                                  color=(235, 112, 92)))
            pad_y = y_ab + big + big // 3 + gap * 2
            keys = "123456789-0/"
            pad_unit = int(min(unit, (win_h - pad_y - gap * 4) / 4))
            pad_w = pad_unit * 3 + gap * 2
            px0 = left + (width - pad_w) // 2
            for i, char in enumerate(keys):
                col, row = i % 3, i // 3
                key = {"-": pygame.K_MINUS, "/": pygame.K_SLASH}.get(char, getattr(pygame, f"K_{char}", 0))
                buttons.append(Button(char, key, char, (px0 + col * (pad_unit + gap), pad_y + row * (pad_unit + gap),
                                                        pad_unit, pad_unit)))
        else:
            # ---- floating over the game (narrow / portrait windows)
            b = int(min(win_w, win_h) * 0.09)
            cx, cy = int(b * 1.7), win_h - int(b * 1.7)
            offsets = {pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1), pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0)}
            for key, label in dpad_keys:
                ox, oy = offsets[key]
                buttons.append(Button(label, key, rect=(cx + ox * b - b // 2, cy + oy * b - b // 2, b, b), kind="dir"))
            big = int(b * 1.2)
            buttons.append(Button("A", pygame.K_RETURN, "\r", (win_w - big - b // 2, win_h - big * 2 - b, big, big), big=True))
            buttons.append(Button("B", pygame.K_ESCAPE, "", (win_w - big * 2 - b, win_h - big - b // 2, big, big),
                                  big=True, color=(235, 112, 92)))
            for i, (label, key, uni) in enumerate(SHORTCUTS + (("123", 0, ""), ("ABC", 0, ""))):
                kind = {"123": "keypad", "ABC": "text"}.get(label, "key")
                small = int(b * 0.8)
                buttons.append(Button(label, key, uni, (b // 4 + i * (small + 4), b // 4, small, small), kind=kind,
                                      color=(110, 177, 206)))
            keys = "123456789-0/"
            pad = int(b * 0.95)
            for i, char in enumerate(keys + "."):
                col, row = i % 3, i // 3
                key = {"-": pygame.K_MINUS, "/": pygame.K_SLASH, ".": pygame.K_PERIOD}.get(char, getattr(pygame, f"K_{char}", 0))
                button = Button(char, key, char, (win_w // 2 - pad * 2 + col * (pad + 4), win_h // 2 - pad * 2 + row * (pad + 4),
                                                  pad, pad), kind="pad")
                buttons.append(button)
            buttons.append(Button("DEL", pygame.K_BACKSPACE, "", (win_w // 2 + pad * 2, win_h // 2 - pad * 2, pad, pad),
                                  kind="pad"))
        self.buttons = buttons

    @staticmethod
    def top_reserved(win_w, win_h):
        """Height of the shortcut row in the floating (portrait) layout, plus a small gap."""
        b = int(min(win_w, win_h) * 0.09)
        return b // 4 + int(b * 0.8) + b // 3

    def visible_buttons(self):
        for button in self.buttons:
            if button.kind == "pad" and not self.keypad_open:
                continue
            if button.kind == "text" and self.context != "name":
                continue
            yield button

    # ------------------------------------------------------------------ input
    def handle(self, event, window_size):
        """Returns True if the event was a touch on the controls (the caller should skip it)."""
        if not self.enabled:
            return False
        kind = event.type
        if kind in (pygame.FINGERDOWN, pygame.FINGERUP, pygame.FINGERMOTION):
            self.saw_finger = True
            point = (event.x * window_size[0], event.y * window_size[1])
            pointer = ("finger", event.finger_id)
            phase = {pygame.FINGERDOWN: "down", pygame.FINGERUP: "up", pygame.FINGERMOTION: "move"}[kind]
        elif kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
            if self.saw_finger:
                return False  # the same touch also arrives as a mouse event: handle it once
            if kind == pygame.MOUSEMOTION and not getattr(event, "buttons", (0,))[0]:
                return False
            point, pointer = event.pos, ("mouse", 0)
            phase = {pygame.MOUSEBUTTONDOWN: "down", pygame.MOUSEBUTTONUP: "up", pygame.MOUSEMOTION: "move"}[kind]
        else:
            return False
        if self.size != tuple(window_size):
            self._layout(tuple(window_size))
        hit = next((b for b in self.visible_buttons() if b.rect.collidepoint(point)), None)
        previous = self.pressed.get(pointer)
        if phase == "up":
            if previous is not None:
                self._release(previous)
                del self.pressed[pointer]
            return previous is not None
        if phase == "move":
            if previous is not None and hit is not previous and previous.kind == "dir":
                self._release(previous)
                del self.pressed[pointer]
                if hit is not None and hit.kind == "dir":
                    self.pressed[pointer] = hit
                    self._press(hit)
            return previous is not None
        if hit is None:
            return False
        self.pressed[pointer] = hit
        self._press(hit)
        return True

    def _press(self, button):
        if button.kind == "keypad":
            self.keypad_open = not self.keypad_open
            return
        if button.kind == "text":
            self._ask_text()
            return
        self.hold_frames[button] = 0
        self._post(pygame.KEYDOWN, button)

    def _release(self, button):
        self.hold_frames.pop(button, None)
        if button.kind not in ("keypad", "text"):
            self._post(pygame.KEYUP, button)

    @staticmethod
    def _post(event_type, button):
        pygame.event.post(pygame.event.Event(event_type, key=button.key, unicode=button.unicode, mod=0, scancode=0,
                                             touch=True))

    def _ask_text(self):
        """Letters for the name screen: the browser's own text box (phone keyboard)."""
        if not WEB:
            return
        try:
            import platform
            answer = platform.window.prompt("Your ranger name:", "")
        except Exception:
            return
        for char in str(answer or "")[:18]:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=0, unicode=char, mod=0, scancode=0, touch=True))

    def update(self):
        """Auto-repeat held D-pad arrows (for menus)."""
        for button in list(self.hold_frames):
            self.hold_frames[button] += 1
            held = self.hold_frames[button]
            if button.kind == "dir" and held >= REPEAT_DELAY and (held - REPEAT_DELAY) % REPEAT_EVERY == 0:
                self._post(pygame.KEYDOWN, button)

    def held_direction(self):
        dx = dy = 0
        for button in self.pressed.values():
            if button.kind == "dir":
                ox, oy = DIRECTIONS[button.key]
                dx, dy = dx + ox, dy + oy
        return max(-1, min(1, dx)), max(-1, min(1, dy))

    # ------------------------------------------------------------------ draw
    def _font(self, size):
        size = max(8, int(size))
        if size not in self._fonts:
            self._fonts[size] = pygame.font.Font(None, size)
        return self._fonts[size]

    def draw(self, window, context=""):
        if not self.active:
            return
        self.context = context
        if self.size != window.get_size():
            self._layout(window.get_size())
        layer = pygame.Surface(window.get_size(), pygame.SRCALPHA)
        down = set(self.pressed.values())
        alpha = 120 if self.floating else 200
        for button in self.visible_buttons():
            r = button.rect
            pressed = button in down or (button.kind == "keypad" and self.keypad_open)
            fill = (*button.color, alpha) if pressed else (28, 42, 65, alpha)
            radius = r.w // 2 if button.big else max(4, r.w // 6)
            pygame.draw.rect(layer, fill, r, border_radius=radius)
            pygame.draw.rect(layer, (*button.color, 230), r, max(2, r.w // 22), border_radius=radius)
            label = self._font(r.h * (0.55 if len(button.label) == 1 else 0.38)).render(
                button.label, True, (19, 25, 42) if pressed else (249, 231, 180))
            layer.blit(label, label.get_rect(center=r.center))
        window.blit(layer, (0, 0))

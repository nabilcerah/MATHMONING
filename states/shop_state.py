"""The village SHOP (GDD 12). LEFT/RIGHT switches between buying and selling."""
from config import PALETTE
from game.ui import panel, text, wrapped
from states.base import LEFT, RIGHT, Screen
from world.shop import Shop


class ShopScreen(Screen):
    def __init__(self, game):
        super().__init__(game)
        self.shop = Shop(self.repo, self.player_id)
        self.mode = "buy"
        self.notice = "Welcome! Everything here is bought with Numera Coins you earn by playing."

    def items(self):
        return self.shop.stock() if self.mode == "buy" else self.shop.sellable()

    def rows(self):
        return 44, 16, 6, 190

    def handle_key(self, key, unicode=""):
        if key in LEFT + RIGHT:
            self.mode = "sell" if self.mode == "buy" else "buy"
            self.selected = 0
            return
        super().handle_key(key, unicode)

    def activate(self, index):
        name, _ = self.items()[index]
        ok, message = self.shop.buy(name) if self.mode == "buy" else self.shop.sell(name)
        self.notice = message
        if ok:
            self.game.on_shop_change()
        if self.mode == "sell" and not self.items():
            self.selected = 0

    def draw(self, surface, frame=0):
        self.draw_frame(surface, "VILLAGE SHOP", footer="LEFT/RIGHT: BUY/SELL   ENTER: TRADE   ESC: LEAVE")
        coins = self.repo.coins(self.player_id)
        bag = self.repo.inventory(self.player_id)
        text(surface, f"COINS {coins}", (314, 28), 11, PALETTE["gold"], align="right")
        for i, label in enumerate(("BUY", "SELL")):
            active = label.lower() == self.mode
            text(surface, label, (10 + i * 44, 28), 11, PALETTE["gold"] if active else PALETTE["muted"])
        entries = self.items()
        if not entries:
            text(surface, "Nothing to sell right now.", (12, 48), 10, PALETTE["muted"])
            return
        labels = [name for name, _ in entries]
        self.draw_list(surface, labels, frame, 44, 16, 6, 184)
        for index, (name, info) in enumerate(entries):
            price = info["price"] if self.mode == "buy" else info.get("sell", 0)
            afford = self.mode == "sell" or coins >= price
            text(surface, f"{price}c", (188, 44 + index * 16), 10, PALETTE["cream"] if afford else PALETTE["coral"],
                 align="right")
        name, info = entries[min(self.selected, len(entries) - 1)]
        panel(surface, (198, 44, 116, 110), PALETTE["night"])
        text(surface, name, (204, 48), 10, PALETTE["gold"])
        text(surface, f"You have: {bag.get(name, 0)}", (204, 62), 9, PALETTE["sky"])
        wrapped(surface, info["description"], (204, 76, 104, 70), 9, PALETTE["white"], 10, 7)

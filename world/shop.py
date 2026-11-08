"""GDD 12: the village shop. Prices come from data/items.json; no real-money purchases exist."""
from monsters.monster_data import items, shop_stock


class Shop:
    def __init__(self, repository, player_id):
        self.repository = repository
        self.player_id = player_id

    @staticmethod
    def stock():
        return [(name, items()[name]) for name in shop_stock()]

    def sellable(self):
        bag = self.repository.inventory(self.player_id)
        return [(name, info) for name, info in items().items() if info.get("sell") and bag.get(name)]

    def buy(self, item, count=1):
        """(ok, message). Coins and the item change together or not at all."""
        info = items().get(item)
        if not info or item not in shop_stock():
            return False, "That isn't for sale."
        if self.repository.buy(self.player_id, item, info["price"], count):
            return True, f"Bought {item} x{count}."
        return False, f"Not enough Numera Coins (need {info['price'] * count})."

    def sell(self, item):
        info = items().get(item, {})
        if not info.get("sell"):
            return False, "The shopkeeper doesn't buy that."
        if self.repository.sell(self.player_id, item, info["sell"]):
            return True, f"Sold {item} for {info['sell']} coins."
        return False, f"You have no {item}."

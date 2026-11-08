"""GDD 4.1: an active party of up to three monsters plus the Monster Sanctuary (storage).

Pure data and rules; saving is done by the repository (database.player_repository).
"""
from monsters.monster_data import rules


class PartyError(ValueError):
    """A party change the rules do not allow (the message is shown to the player)."""


class MonsterParty:
    def __init__(self, party=None, storage=None, active_index=0):
        limits = rules()["party"]
        self.max_party = int(limits["max_party"])
        self.capacity = int(limits["storage_capacity"])
        self.party = list(party or [])[:self.max_party]
        self.storage = list(storage or [])
        self.active_index = active_index if 0 <= active_index < len(self.party) else 0

    # ------------------------------------------------------------------ views
    @property
    def active(self):
        return self.party[self.active_index] if self.party else None

    @property
    def lead(self):
        """The monster that follows you and leads into battle (the first healthy one)."""
        healthy = self.healthy()
        return healthy[0] if healthy else (self.party[0] if self.party else None)

    def healthy(self, exclude=None):
        return [m for m in self.party if not m.fainted and m is not exclude]

    @property
    def all_fainted(self):
        return bool(self.party) and not self.healthy()

    @property
    def party_full(self):
        return len(self.party) >= self.max_party

    @property
    def storage_full(self):
        return len(self.storage) >= self.capacity

    def all_monsters(self):
        return self.party + self.storage

    # ------------------------------------------------------------------ battle
    def start_battle(self):
        """The first healthy party member battles first."""
        lead = self.lead
        self.active_index = self.party.index(lead) if lead in self.party else 0
        return self.active

    def switch_to(self, index):
        if not 0 <= index < len(self.party):
            raise PartyError("There is no monster in that slot.")
        target = self.party[index]
        if target.fainted:
            raise PartyError(f"{target.name} has fainted and cannot battle.")
        if index == self.active_index:
            raise PartyError(f"{target.name} is already battling.")
        self.active_index = index
        return target

    # ------------------------------------------------------------------ collection
    def add(self, monster):
        """A new monster joins the party if there is room, otherwise the Sanctuary.
        Returns "party" or "storage"; raises PartyError if both are full."""
        if not self.party_full:
            self.party.append(monster)
            return "party"
        if not self.storage_full:
            self.storage.append(monster)
            return "storage"
        raise PartyError("Your party and the Monster Sanctuary are both full.")

    def deposit(self, party_index):
        """Party -> Sanctuary. You always keep at least one healthy monster with you."""
        if not 0 <= party_index < len(self.party):
            raise PartyError("There is no monster in that slot.")
        if len(self.party) <= 1:
            raise PartyError("You must keep at least one monster in your party.")
        monster = self.party[party_index]
        if not [m for m in self.party if m is not monster and not m.fainted]:
            raise PartyError("Keep at least one healthy monster in your party.")
        if self.storage_full:
            raise PartyError("The Monster Sanctuary is full.")
        self.party.pop(party_index)
        self.storage.append(monster)
        self.active_index = 0
        return monster

    def withdraw(self, storage_index):
        """Sanctuary -> party (needs a free party slot)."""
        if not 0 <= storage_index < len(self.storage):
            raise PartyError("There is no monster in that box.")
        if self.party_full:
            raise PartyError("Your party already has three monsters. Swap one instead.")
        monster = self.storage.pop(storage_index)
        self.party.append(monster)
        return monster

    def swap(self, party_index, storage_index):
        """Exchange a party monster with a stored one."""
        if not 0 <= party_index < len(self.party) or not 0 <= storage_index < len(self.storage):
            raise PartyError("Pick a party monster and a stored monster to swap.")
        incoming = self.storage[storage_index]
        outgoing = self.party[party_index]
        others_healthy = [m for i, m in enumerate(self.party) if i != party_index and not m.fainted]
        if incoming.fainted and not others_healthy:
            raise PartyError("Keep at least one healthy monster in your party.")
        self.party[party_index], self.storage[storage_index] = incoming, outgoing
        self.active_index = 0
        return incoming, outgoing

    def set_lead(self, party_index):
        """Move a party monster to the front: it leads in battle and follows you."""
        if not 0 <= party_index < len(self.party):
            raise PartyError("There is no monster in that slot.")
        monster = self.party.pop(party_index)
        self.party.insert(0, monster)
        self.active_index = 0
        return monster

    def heal_all(self, fraction=1.0):
        """Restore every party monster (fainted ones included). Returns total HP restored."""
        restored = 0
        for monster in self.party:
            target = max(monster.hp, max(1, round(monster.max_hp * fraction)))
            restored += target - monster.hp
            monster.hp = target
        return restored

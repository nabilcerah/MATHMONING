"""Adapter that lets the bonus modes (Math Arena, Monster Trials) use the GDD party.

Members are ``monsters.monster.Monster`` instances from the active party (up to three).
"""


class Team:
    def __init__(self, repository, player, flags=None, party=None):
        self.repository, self.player = repository, player
        self.party = party or repository.load_party(player.player_id)

    @property
    def members(self):
        return self.party.party

    def spec_of(self, member):
        return member.spec

    def name_of(self, member):
        return member.name

    def leader(self):
        return self.party.lead

    def find(self, species_id):
        return next((m for m in self.members if m.species_id == species_id), None)

    def healthy(self, exclude=None):
        return self.party.healthy(exclude)

    @property
    def max_level(self):
        return max((m.level for m in self.members), default=1)

    def save(self, member):
        self.repository.save_monster(self.player.player_id, member)

    def heal_all(self, fraction=1.0):
        healed = self.party.heal_all(fraction)
        self.repository.save_party(self.player.player_id, self.party)
        return healed

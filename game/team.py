"""Your team: the partner (your starter) plus every MATHMON you have captured.

Each member has its own level, EXP and HP. The partner's numbers live on the Player record
(so old saves keep their starter's progress); captured members live in the team_members table.
Both expose the same attributes - level, exp, hp, max_hp, next_level_exp, add_exp() - so battle
code can treat "the monster that is fighting" the same way whichever it is.
"""
from dataclasses import dataclass

from game.creatures import WILD_BY_NAME, creature_spec, leveled_stats


@dataclass
class TeamMember:
    species: str
    level: int = 1
    exp: int = 0
    hp: int = 1
    max_hp: int = 1
    is_partner = False

    @property
    def next_level_exp(self):
        return self.level * 20

    def add_exp(self, amount):
        self.exp += max(0, amount)
        leveled = False
        while self.exp >= self.next_level_exp:
            self.exp -= self.next_level_exp
            self.level += 1
            self.max_hp += 4
            self.hp = self.max_hp
            leveled = True
        return leveled

    @classmethod
    def caught(cls, species, level):
        max_hp, _ = leveled_stats(WILD_BY_NAME[species], level)
        return cls(species, level, 0, max_hp, max_hp)


class Team:
    def __init__(self, repository, player, flags=None):
        self.repository, self.player = repository, player
        self.player.is_partner = True
        flags = set(flags if flags is not None else repository.world_flags(player.player_id))
        rows = {row["species"]: row for row in repository.team_members(player.player_id)}
        self.members = [player]
        for flag in sorted(flags):
            if not flag.startswith("dex_friend:"):
                continue
            species = flag.split(":", 1)[1]
            if species not in WILD_BY_NAME:
                continue  # a species removed from the game
            if species in rows:
                row = rows[species]
                member = TeamMember(species, row["level"], row["exp"], row["hp"], row["max_hp"])
            else:
                # Captured before monsters had their own levels: join one level below the partner.
                member = TeamMember.caught(species, max(1, player.level - 1))
                repository.save_member(player.player_id, member)
            self.members.append(member)
        chosen = [f.split(":", 1)[1] for f in flags if f.startswith("companion:")]
        self.leader_name = chosen[0] if chosen else None

    # ------------------------------------------------------------------ lookups
    def spec_of(self, member):
        if member is self.player:
            return creature_spec(self.player.creature, self.player.level)
        return WILD_BY_NAME[member.species]

    def name_of(self, member):
        return self.spec_of(member).name

    def leader(self):
        for member in self.members[1:]:
            if member.species == self.leader_name:
                return member
        return self.player

    def find(self, species):
        return next((m for m in self.members[1:] if m.species == species), None)

    def healthy(self, exclude=None):
        return [m for m in self.members if m.hp > 0 and m is not exclude]

    @property
    def max_level(self):
        return max(member.level for member in self.members)

    # ------------------------------------------------------------------ changes
    def save(self, member):
        if member is self.player:
            self.repository.save_player(self.player)
        else:
            self.repository.save_member(self.player.player_id, member)

    def add(self, species, level):
        if self.find(species):
            return self.find(species)
        member = TeamMember.caught(species, level)
        self.repository.save_member(self.player.player_id, member)
        self.members.append(member)
        return member

    def heal_all(self, fraction=1.0):
        """Restore every member (fraction=0.5 is the ranger's rescue after a defeat)."""
        healed = 0
        for member in self.members:
            target = max(member.hp, max(1, int(member.max_hp * fraction)))
            healed += target - member.hp
            member.hp = target
            self.save(member)
        return healed

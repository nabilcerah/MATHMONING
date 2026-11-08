"""GDD 7.7: a deterministic enemy decision system.

Inputs are the enemy's HP, its moves (with their kind as priority), the turn number and whether
it already has a shield up. The same situation always produces the same choice, so battles are
fair and testable. No question is ever asked for an enemy move.
"""


class EnemyAI:
    LOW_HP = 0.35          # below this the enemy may defend
    SPECIAL_EVERY = 3      # a strong attack every third turn...
    BOSS_SPECIAL_EVERY = 2  # ...or every second turn for a boss

    def __init__(self, boss=False):
        self.boss = boss
        self.defended = False

    def choose(self, enemy, turn, shielded=False):
        moves = enemy.moves()
        normals = [m for m in moves if m.kind == "normal"]
        specials = [m for m in moves if m.kind == "special"]
        supports = [m for m in moves if m.kind == "support" and m.effect == "shield"]
        hp_ratio = enemy.hp / max(1, enemy.max_hp)
        # Defensive action: once, when badly hurt and not already shielded.
        if supports and hp_ratio < self.LOW_HP and not shielded and not self.defended:
            self.defended = True
            return supports[0]
        every = self.BOSS_SPECIAL_EVERY if self.boss else self.SPECIAL_EVERY
        if specials and turn % every == every - 1:
            return max(specials, key=lambda m: m.power)
        if normals:
            return max(normals, key=lambda m: m.power)
        damaging = [m for m in moves if m.damaging]
        return max(damaging, key=lambda m: m.power) if damaging else moves[0]

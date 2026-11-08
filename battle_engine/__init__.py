"""Advanced monster battle system: data-driven monsters, deterministic rules, pluggable mechanics.

Layout:
    balance.py       every tunable number (overridable from data/balance.json)
    tiers.py         Common / Uncommon / Rare / Epic / Mythical
    monster_data.py  loads data/monsters/*.json and computes stats
    damage.py        the damage formulas (authoritative)
    monster_ai.py    the deterministic state-machine AI
    phases.py        HP-threshold battle phases
    mechanics/       shields, growth, absorb, split, timeline, gravity, barrier, combos, rules
    engine.py        BattleEngine: ties it all together, no drawing code
    skills.py        trainer skills unlocked by trainer level
    progression.py   trainer XP/levels, monster mastery ranks and rewards
"""

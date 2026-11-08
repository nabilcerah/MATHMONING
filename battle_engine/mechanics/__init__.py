"""Registry of battle mechanics. Monster JSON names a mechanic by its ``type``."""
from battle_engine.mechanics.absorb import EnergyAbsorb
from battle_engine.mechanics.barrier import PuzzleBarrier
from battle_engine.mechanics.base import Mechanic
from battle_engine.mechanics.gravity import GravityField
from battle_engine.mechanics.growth import Growth
from battle_engine.mechanics.operation_combo import OperationCombo
from battle_engine.mechanics.shield import Shield
from battle_engine.mechanics.simple import FastStrikes, RuleShift
from battle_engine.mechanics.split import Split
from battle_engine.mechanics.timeline import Timeline

REGISTRY = {cls.TYPE: cls for cls in (Shield, Growth, EnergyAbsorb, Split, Timeline, GravityField, PuzzleBarrier,
                                       OperationCombo, FastStrikes, RuleShift)}


def create(engine, spec):
    try:
        cls = REGISTRY[spec["type"]]
    except KeyError:
        raise ValueError(f"{engine.defn.id}: unknown mechanic type {spec.get('type')!r}") from None
    return cls(engine, spec)


__all__ = ["Mechanic", "REGISTRY", "create"]

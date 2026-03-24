"""
Tactical configuration for a team's match setup.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .player import Player


class BattingIntent(str, Enum):
    AGGRESSIVE = "aggressive"
    BALANCED = "balanced"
    CONSERVATIVE = "conservative"


class FieldSetting(str, Enum):
    ATTACKING = "attacking"
    STANDARD = "standard"
    DEFENSIVE = "defensive"


class PowerplayStrategy(str, Enum):
    AGGRESSIVE = "aggressive"
    STEADY = "steady"


class DeathOversPlan(str, Enum):
    ALL_OUT_ATTACK = "all_out_attack"
    CALCULATED = "calculated"
    DEFEND = "defend"


@dataclass
class BowlingSlot:
    """Represents a planned bowling assignment."""
    bowler: "Player"
    target_overs: List[int] = field(default_factory=list)   # e.g. [1,2,17,18]
    max_overs: int = 4


@dataclass
class Tactics:
    batting_order: List["Player"] = field(default_factory=list)
    bowling_plan: List[BowlingSlot] = field(default_factory=list)
    batting_intent: BattingIntent = BattingIntent.BALANCED
    field_setting: FieldSetting = FieldSetting.STANDARD
    powerplay_strategy: PowerplayStrategy = PowerplayStrategy.AGGRESSIVE
    death_overs_plan: DeathOversPlan = DeathOversPlan.CALCULATED

    def get_batting_intent_for_phase(self, phase: str) -> BattingIntent:
        """Return intent adjusted for match phase."""
        if phase == "powerplay":
            if self.powerplay_strategy == PowerplayStrategy.AGGRESSIVE:
                return BattingIntent.AGGRESSIVE
            return BattingIntent.BALANCED
        if phase == "death":
            if self.death_overs_plan == DeathOversPlan.ALL_OUT_ATTACK:
                return BattingIntent.AGGRESSIVE
            if self.death_overs_plan == DeathOversPlan.DEFEND:
                return BattingIntent.CONSERVATIVE
        return self.batting_intent

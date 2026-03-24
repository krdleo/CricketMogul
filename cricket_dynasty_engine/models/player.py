"""
Player data model for Cricket Dynasty engine.
All attributes are rated 1–100. 'potential' is excluded from match simulation.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PlayerRole(str, Enum):
    OPENER = "OPENER"
    TOP_ORDER = "TOP_ORDER"
    MIDDLE_ORDER = "MIDDLE_ORDER"
    FINISHER = "FINISHER"
    ALL_ROUNDER = "ALL_ROUNDER"
    FAST_BOWLER = "FAST_BOWLER"
    SPINNER = "SPINNER"
    WICKETKEEPER = "WICKETKEEPER"


class BattingStyle(str, Enum):
    RIGHT = "right"
    LEFT = "left"


class BowlingType(str, Enum):
    RIGHT_FAST = "right_fast"
    LEFT_FAST = "left_fast"
    RIGHT_SPIN_OFF = "right_spin_off"
    RIGHT_SPIN_LEG = "right_spin_leg"
    LEFT_SPIN_ORTHODOX = "left_spin_orthodox"
    LEFT_SPIN_WRIST = "left_spin_wrist"
    NONE = "none"


@dataclass
class Player:
    name: str
    age: int
    role: PlayerRole
    batting_style: BattingStyle
    bowling_type: BowlingType

    # Core attributes (1–100)
    batting_power: int = 50
    batting_technique: int = 50
    pace: int = 1           # only meaningful for fast bowlers
    swing_seam: int = 1     # only meaningful for fast bowlers
    spin: int = 1           # only meaningful for spinners
    economy: int = 50       # all bowlers
    fielding: int = 50
    fitness: int = 75
    temperament: int = 60

    # Dynamic state (changes match-to-match)
    form: float = 1.0       # 0.8–1.2 multiplier
    fatigue: float = 0.0    # 0.0 (fresh) to 1.0 (exhausted)

    def is_bowler(self) -> bool:
        return self.bowling_type != BowlingType.NONE

    def is_pacer(self) -> bool:
        return self.bowling_type in (BowlingType.RIGHT_FAST, BowlingType.LEFT_FAST)

    def is_spinner(self) -> bool:
        return self.bowling_type in (
            BowlingType.RIGHT_SPIN_OFF,
            BowlingType.RIGHT_SPIN_LEG,
            BowlingType.LEFT_SPIN_ORTHODOX,
            BowlingType.LEFT_SPIN_WRIST,
        )

    def effective_fitness(self) -> float:
        """Returns fitness degraded by fatigue (0.0–1.0 scale)."""
        base = self.fitness / 100.0
        return base * (1.0 - self.fatigue * 0.5)

    def __repr__(self) -> str:
        return f"Player({self.name}, {self.role.value})"


@dataclass
class BattingCard:
    player: Player
    runs: int = 0
    balls_faced: int = 0
    fours: int = 0
    sixes: int = 0
    dismissal: Optional[str] = None     # e.g. "caught", "bowled", "not out"
    bowler: Optional[Player] = None
    fielder: Optional[Player] = None

    @property
    def strike_rate(self) -> float:
        if self.balls_faced == 0:
            return 0.0
        return (self.runs / self.balls_faced) * 100.0

    def __repr__(self) -> str:
        return (
            f"{self.player.name}: {self.runs} ({self.balls_faced}b) "
            f"[4s:{self.fours} 6s:{self.sixes}] SR:{self.strike_rate:.1f}"
        )


@dataclass
class BowlingCard:
    player: Player
    balls_bowled: int = 0
    runs_conceded: int = 0
    wickets: int = 0
    wides: int = 0
    no_balls: int = 0

    @property
    def overs(self) -> float:
        complete = self.balls_bowled // 6
        remainder = self.balls_bowled % 6
        return complete + remainder / 10.0

    @property
    def economy(self) -> float:
        overs_bowled = self.balls_bowled / 6.0
        if overs_bowled == 0:
            return 0.0
        return self.runs_conceded / overs_bowled

    def __repr__(self) -> str:
        return (
            f"{self.player.name}: {self.overs:.1f}ov "
            f"{self.runs_conceded}r {self.wickets}w Eco:{self.economy:.2f}"
        )

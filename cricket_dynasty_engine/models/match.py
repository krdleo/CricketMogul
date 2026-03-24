"""
Match input/output data models.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .player import Player, BattingCard, BowlingCard
    from .team import Team
    from .conditions import PitchConditions, WeatherConditions
    from .tactics import Tactics


class BallOutcome(str, Enum):
    DOT = "dot"
    ONE = "1"
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    SIX = "6"
    WICKET = "wicket"
    WIDE = "wide"
    NO_BALL = "no_ball"


class WicketType(str, Enum):
    BOWLED = "bowled"
    CAUGHT = "caught"
    LBW = "lbw"
    RUN_OUT = "run_out"
    STUMPED = "stumped"
    HIT_WICKET = "hit_wicket"


@dataclass
class BallResult:
    over_number: int
    ball_number: int            # 1–6 (or 7+ for extras)
    bowler: "Player"
    batter: "Player"
    outcome: BallOutcome
    runs: int = 0               # runs scored on this ball (includes extras value)
    wicket_type: Optional[WicketType] = None
    fielder: Optional["Player"] = None
    commentary: str = ""

    @property
    def is_legal(self) -> bool:
        return self.outcome not in (BallOutcome.WIDE, BallOutcome.NO_BALL)

    @property
    def is_boundary(self) -> bool:
        return self.outcome in (BallOutcome.FOUR, BallOutcome.SIX)


@dataclass
class OverResult:
    over_number: int            # 1-based
    bowler: "Player"
    balls: List[BallResult] = field(default_factory=list)
    commentary: str = ""
    is_critical: bool = False   # flag for expanded narration

    @property
    def runs(self) -> int:
        return sum(b.runs for b in self.balls)

    @property
    def wickets(self) -> int:
        return sum(1 for b in self.balls if b.outcome == BallOutcome.WICKET)

    @property
    def legal_balls(self) -> int:
        return sum(1 for b in self.balls if b.is_legal)

    @property
    def extras(self) -> int:
        return sum(
            b.runs for b in self.balls
            if b.outcome in (BallOutcome.WIDE, BallOutcome.NO_BALL)
        )

    def __repr__(self) -> str:
        return f"Over {self.over_number}: {self.runs}r {self.wickets}w"


@dataclass
class KeyMoment:
    over: int
    ball: int
    description: str
    moment_type: str    # "wicket", "six", "milestone", "collapse", "last_over_finish"


@dataclass
class InningsResult:
    batting_team: "Team"
    bowling_team: "Team"
    innings_number: int         # 1 or 2
    target: Optional[int] = None  # None for 1st innings

    overs: List[OverResult] = field(default_factory=list)
    batting_cards: List["BattingCard"] = field(default_factory=list)
    bowling_cards: List["BowlingCard"] = field(default_factory=list)
    extras: int = 0

    # Set by simulator at completion
    total_runs: int = 0
    total_wickets: int = 0
    total_overs_bowled: float = 0.0  # e.g. 18.4 if bowled out

    @property
    def run_rate(self) -> float:
        if self.total_overs_bowled == 0:
            return 0.0
        return self.total_runs / self.total_overs_bowled

    def __repr__(self) -> str:
        return (
            f"{self.batting_team.name}: "
            f"{self.total_runs}/{self.total_wickets} "
            f"({self.total_overs_bowled:.1f} ov)"
        )


@dataclass
class MatchResult:
    innings: List[InningsResult] = field(default_factory=list)
    winner: Optional["Team"] = None     # None if tied
    margin: str = ""                    # "5 wickets", "12 runs", "Super Over", "Tie"
    player_of_match: Optional["Player"] = None
    key_moments: List[KeyMoment] = field(default_factory=list)
    seed: int = 0

    def summary(self) -> str:
        lines = []
        for inn in self.innings:
            lines.append(str(inn))
        result = f"Result: {self.winner.name} won by {self.margin}" if self.winner else f"Result: {self.margin}"
        lines.append(result)
        return "\n".join(lines)


@dataclass
class MatchInput:
    home_team: "Team"
    away_team: "Team"
    pitch: "PitchConditions"
    weather: "WeatherConditions"
    home_tactics: "Tactics"
    away_tactics: "Tactics"
    seed: int = 42

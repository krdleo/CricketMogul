"""
Team / Squad model.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .player import Player


@dataclass
class Team:
    name: str
    short_name: str                  # e.g. "MI", "CSK"
    players: List["Player"] = field(default_factory=list)   # Full squad (15-18)
    playing_xi: List["Player"] = field(default_factory=list)  # Match day 11

    def average_batting_quality(self) -> float:
        """Simple batting quality score for the top 7."""
        batters = self.playing_xi[:7]
        if not batters:
            return 50.0
        return sum((p.batting_power + p.batting_technique) / 2 for p in batters) / len(batters)

    def average_bowling_quality(self) -> float:
        bowlers = [p for p in self.playing_xi if p.is_bowler()]
        if not bowlers:
            return 50.0
        scores = []
        for b in bowlers:
            if b.is_pacer():
                scores.append((b.pace + b.swing_seam + b.economy) / 3)
            elif b.is_spinner():
                scores.append((b.spin + b.economy) / 2)
            else:
                scores.append(b.economy)
        return sum(scores) / len(scores)

    def __repr__(self) -> str:
        return f"Team({self.name})"

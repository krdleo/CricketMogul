"""
Pressure Index system.
Pressure ranges from 0.0 (no pressure) to 1.0 (maximum pressure).
It interacts with player temperament to affect effective attributes.
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.player import Player


class MatchStakes:
    LEAGUE = 0.0
    PLAYOFF = 0.15
    ELIMINATOR = 0.20
    FINAL = 0.25


def calculate_pressure(
    over: int,
    innings: int,                   # 1 or 2
    wickets_fallen: int,
    runs_scored: int,
    target: Optional[int] = None,   # only for 2nd innings
    stakes: float = MatchStakes.LEAGUE,
) -> float:
    """
    Return a Pressure Index in [0.0, 1.0].

    Components:
      base_match_pressure  — increases as overs progress; higher in 2nd innings
      situation_pressure   — run rate gap, wickets fallen
      stakes_pressure      — tournament importance
    """

    # ── Base match pressure ─────────────────────────────────────────────
    # Increases linearly from 0.1 at over 1 to 0.35 at over 20
    base = 0.1 + (over - 1) / 19.0 * 0.25

    # 2nd innings adds baseline pressure
    if innings == 2:
        base += 0.08

    # ── Situation pressure ──────────────────────────────────────────────
    sit = 0.0

    # Wickets factor: each wicket down after the 4th adds pressure
    if wickets_fallen >= 4:
        sit += (wickets_fallen - 3) * 0.04
    if wickets_fallen >= 7:
        sit += 0.08   # top order gone, tailenders

    # Chasing pressure: run-rate gap
    if innings == 2 and target is not None:
        overs_remaining = max(1, 20 - over)
        runs_needed = target - runs_scored
        required_rr = runs_needed / overs_remaining if overs_remaining > 0 else 99.0
        current_rr = runs_scored / over if over > 0 else 0.0

        rr_gap = required_rr - current_rr
        if rr_gap > 0:
            # Behind the rate: increasing pressure
            sit += min(0.30, rr_gap * 0.025)
        else:
            # Ahead of rate but not safe
            if -rr_gap < 3:
                sit += 0.05

        # Close finish amplification (within 15 runs, last 5 overs)
        if runs_needed <= 15 and overs_remaining <= 5:
            sit += 0.12

    # ── Clamp ──────────────────────────────────────────────────────────
    raw = base + sit + stakes
    return min(1.0, max(0.0, raw))


def apply_pressure_to_attribute(
    attribute: float,
    pressure: float,
    temperament: int,
) -> float:
    """
    Reduce an attribute value based on pressure and temperament.

    effective = base * (1 - pressure * (1 - temperament/100))

    A player with temperament=90 loses only 10% of the pressure penalty.
    A player with temperament=40 loses 60% of the pressure penalty.
    """
    resilience = temperament / 100.0
    penalty_fraction = pressure * (1.0 - resilience)
    return attribute * (1.0 - penalty_fraction)


def pressure_modifier(
    pressure: float,
    batter: "Player",
    bowler: "Player",
) -> dict:
    """
    Build a probability modifier dict reflecting pressure effects.

    High-pressure / low-temperament batter: more wickets, more dots.
    High-temperament batter under pressure: can actually hit big (big shots outcome).
    """
    batter_res = batter.temperament / 100.0
    bowler_res = bowler.temperament / 100.0

    # Fraction of the pressure penalty the batter absorbs
    batter_effect = pressure * (1.0 - batter_res)  # 0 = ice-cool, 1 = crumbles

    # High-temperament batters under pressure occasionally go big
    big_shot_bonus = 1.0 + pressure * batter_res * 0.15

    return {
        "dot":    1.0 + batter_effect * 0.20,
        "1":      1.0 - batter_effect * 0.05,
        "2":      1.0 - batter_effect * 0.05,
        "3":      1.0,
        "4":      1.0 - batter_effect * 0.10 + pressure * batter_res * 0.08,
        "6":      big_shot_bonus - batter_effect * 0.12,
        "wicket": 1.0 + batter_effect * 0.35,
        "wide":   1.0,
        "no_ball": 1.0,
    }

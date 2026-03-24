"""
Ball Resolver — the heart of the simulation engine.

Pipeline for each delivery:
  1. Base outcome probabilities (by phase)
  2. Batter modifier (power, technique, form)
  3. Bowler modifier (economy, wicket-taking, conditions)
  4. Pitch modifier
  5. Tactical modifier (batting intent + field setting)
  6. Pressure modifier (Pressure Index × temperament)
  7. Fatigue modifier
  8. Normalize → weighted random roll
  9. Post-process: wicket type, fielder, runs value
"""

from __future__ import annotations

import random
from typing import Optional, List, TYPE_CHECKING

from ..models.match import BallResult, BallOutcome, WicketType
from ..models.conditions import PitchConditions, WeatherConditions
from .modifiers import (
    get_phase,
    get_base_probs,
    batter_modifier,
    bowler_modifier,
    pitch_modifier,
    batting_intent_modifier,
    field_setting_modifier,
    fatigue_modifier,
    apply_modifier,
    normalize,
)
from .pressure import pressure_modifier

if TYPE_CHECKING:
    from ..models.player import Player
    from ..models.tactics import Tactics


# ── Wicket type distribution ──────────────────────────────────────────────────
# Probabilities by bowler type — must sum to 1.0
WICKET_TYPE_DIST = {
    "pacer": [
        (WicketType.CAUGHT,     0.52),
        (WicketType.BOWLED,     0.20),
        (WicketType.LBW,        0.16),
        (WicketType.RUN_OUT,    0.06),
        (WicketType.STUMPED,    0.03),
        (WicketType.HIT_WICKET, 0.03),
    ],
    "spinner": [
        (WicketType.CAUGHT,     0.44),
        (WicketType.BOWLED,     0.15),
        (WicketType.LBW,        0.10),
        (WicketType.STUMPED,    0.22),
        (WicketType.RUN_OUT,    0.07),
        (WicketType.HIT_WICKET, 0.02),
    ],
    "default": [
        (WicketType.CAUGHT,     0.50),
        (WicketType.BOWLED,     0.20),
        (WicketType.LBW,        0.15),
        (WicketType.RUN_OUT,    0.10),
        (WicketType.STUMPED,    0.03),
        (WicketType.HIT_WICKET, 0.02),
    ],
}


def _roll_wicket_type(bowler: "Player", rng: random.Random) -> WicketType:
    if bowler.is_pacer():
        dist = WICKET_TYPE_DIST["pacer"]
    elif bowler.is_spinner():
        dist = WICKET_TYPE_DIST["spinner"]
    else:
        dist = WICKET_TYPE_DIST["default"]

    outcomes, weights = zip(*dist)
    return rng.choices(outcomes, weights=weights, k=1)[0]


def _pick_fielder(
    fielding_team: List["Player"],
    wicket_type: WicketType,
    bowler: "Player",
    rng: random.Random,
) -> Optional["Player"]:
    """Return the fielder involved, weighted by fielding attribute."""
    if wicket_type == WicketType.BOWLED:
        return None
    if wicket_type == WicketType.LBW:
        return None

    candidates = [p for p in fielding_team if p != bowler]
    if not candidates:
        return None

    weights = [p.fielding for p in candidates]
    return rng.choices(candidates, weights=weights, k=1)[0]


# ── Main resolution function ──────────────────────────────────────────────────

def resolve_ball(
    batter: "Player",
    bowler: "Player",
    over_number: int,          # 1-based
    ball_number: int,          # 1-based legal ball index
    pitch: PitchConditions,
    weather: WeatherConditions,
    batting_tactics: "Tactics",
    bowling_tactics: "Tactics",
    pressure: float,           # 0.0–1.0 Pressure Index
    fielding_team: Optional[List["Player"]] = None,
    rng: Optional[random.Random] = None,
) -> BallResult:
    """
    Resolve a single delivery and return a BallResult.
    """
    if rng is None:
        rng = random.Random()

    phase = get_phase(over_number)

    # ── Step 1: Base probabilities ─────────────────────────────────────
    probs = get_base_probs(phase)

    # ── Step 2: Batter modifier ────────────────────────────────────────
    probs = apply_modifier(probs, batter_modifier(batter, phase))

    # ── Step 3: Bowler modifier ────────────────────────────────────────
    # Pass current over for spin deterioration
    spin_pitch = PitchConditions(
        type=pitch.type,
        pace_modifier=pitch.pace_modifier,
        spin_modifier=pitch.spin_modifier_at_over(over_number),
        batting_modifier=pitch.batting_modifier,
        deterioration_rate=pitch.deterioration_rate,
    )
    probs = apply_modifier(probs, bowler_modifier(bowler, phase, spin_pitch, weather))

    # ── Step 4: Pitch modifier ─────────────────────────────────────────
    probs = apply_modifier(probs, pitch_modifier(pitch, over_number))

    # ── Step 5: Tactical modifiers ─────────────────────────────────────
    intent = batting_tactics.get_batting_intent_for_phase(phase)
    probs = apply_modifier(probs, batting_intent_modifier(intent.value))
    probs = apply_modifier(probs, field_setting_modifier(bowling_tactics.field_setting.value))

    # ── Step 6: Pressure modifier ──────────────────────────────────────
    probs = apply_modifier(probs, pressure_modifier(pressure, batter, bowler))

    # ── Step 7: Fatigue modifier ───────────────────────────────────────
    probs = apply_modifier(probs, fatigue_modifier(batter, bowler))

    # ── Step 8: Normalize & roll ───────────────────────────────────────
    probs = normalize(probs)
    outcomes = list(probs.keys())
    weights = [probs[o] for o in outcomes]
    raw_outcome = rng.choices(outcomes, weights=weights, k=1)[0]
    outcome = BallOutcome(raw_outcome)

    # ── Step 9: Post-process ───────────────────────────────────────────
    runs = _runs_for_outcome(outcome)
    wicket_type = None
    fielder = None

    if outcome == BallOutcome.WICKET:
        wicket_type = _roll_wicket_type(bowler, rng)
        if fielding_team:
            fielder = _pick_fielder(fielding_team, wicket_type, bowler, rng)

    return BallResult(
        over_number=over_number,
        ball_number=ball_number,
        bowler=bowler,
        batter=batter,
        outcome=outcome,
        runs=runs,
        wicket_type=wicket_type,
        fielder=fielder,
    )


def _runs_for_outcome(outcome: BallOutcome) -> int:
    mapping = {
        BallOutcome.DOT:     0,
        BallOutcome.ONE:     1,
        BallOutcome.TWO:     2,
        BallOutcome.THREE:   3,
        BallOutcome.FOUR:    4,
        BallOutcome.SIX:     6,
        BallOutcome.WICKET:  0,
        BallOutcome.WIDE:    1,
        BallOutcome.NO_BALL: 1,
    }
    return mapping.get(outcome, 0)

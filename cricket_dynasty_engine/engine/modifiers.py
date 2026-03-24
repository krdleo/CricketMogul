"""
Probability modifiers: pitch, match phase, tactics, and fatigue.

Each modifier returns a dict of multipliers keyed by BallOutcome string.
The ball resolver applies them multiplicatively to the base probability vector.
"""

from __future__ import annotations
from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.conditions import PitchConditions, WeatherConditions
    from ..models.tactics import Tactics, BattingIntent, FieldSetting
    from ..models.player import Player


# ── Phase labels ─────────────────────────────────────────────────────────────

def get_phase(over_number: int) -> str:
    """Return the match phase string for a 1-based over number."""
    if over_number <= 6:
        return "powerplay"
    if over_number <= 15:
        return "middle"
    return "death"


# ── Base probability tables ───────────────────────────────────────────────────
# These are the foundation distributions per phase, before any modifiers.
# Keys: dot, 1, 2, 3, 4, 6, wicket, wide, no_ball
# Tuned to approximate IPL aggregate statistics.

BASE_PROBS: Dict[str, Dict[str, float]] = {
    # Calibrated for a 50-stat batter vs 50-stat bowler, balanced pitch, neutral tactics.
    # 75-stat matchups will naturally score more via batter/bowler modifiers.
    "powerplay": {
        "dot":    0.390,
        "1":      0.220,
        "2":      0.055,
        "3":      0.010,
        "4":      0.148,
        "6":      0.065,
        "wicket": 0.052,
        "wide":   0.042,
        "no_ball": 0.018,
    },
    "middle": {
        "dot":    0.415,
        "1":      0.250,
        "2":      0.060,
        "3":      0.010,
        "4":      0.118,
        "6":      0.052,
        "wicket": 0.058,
        "wide":   0.025,
        "no_ball": 0.012,
    },
    "death": {
        "dot":    0.335,
        "1":      0.195,
        "2":      0.045,
        "3":      0.008,
        "4":      0.180,
        "6":      0.118,
        "wicket": 0.060,
        "wide":   0.042,
        "no_ball": 0.017,
    },
}


def get_base_probs(phase: str) -> Dict[str, float]:
    return dict(BASE_PROBS[phase])


# ── Attribute scaling helper ──────────────────────────────────────────────────

def _attr_scale(attr: int, center: int = 50) -> float:
    """
    Map an attribute (1–100) to a multiplicative scale factor centered at 1.0
    when attr == center (50 by default).

    Uses a power law (exponent 0.85) for smooth but meaningful differentiation:
      attr=20 → 0.44   attr=37 → 0.77   attr=50 → 1.00
      attr=75 → 1.41   attr=87 → 1.62   attr=90 → 1.67

    Floor at 0.10 so even the worst player still participates.
    """
    return max(0.10, (attr / center) ** 0.85)


# ── Batter modifier ───────────────────────────────────────────────────────────

def batter_modifier(batter: "Player", phase: str) -> Dict[str, float]:
    """
    Ratio-based batter modifier — all effects scale multiplicatively
    around a neutral point of 1.0 at attribute = 50.

    batting_power    → drives boundary frequency (4s/6s).
                       High power = more boundaries AND slightly more risk.
    batting_technique → drives strike rotation (1s/2s) and wicket avoidance.
                       High technique = fewer dots, more singles, fewer dismissals.

    The combination power=high + technique=low models a slogger:
    many 4s and 6s, but also frequent wickets.
    """
    ps = _attr_scale(batter.batting_power)      # power scale
    ts = _attr_scale(batter.batting_technique)  # technique scale
    f  = batter.form

    mod: Dict[str, float] = {
        # Dot ball inverse of combined batting quality
        "dot":    1.0 / (0.40 * ps + 0.60 * ts),
        # Strike rotation driven by technique
        "1":      ts ** 0.55,
        "2":      ts ** 0.60,
        "3":      1.0,
        # Boundary hitting driven by power
        "4":      ps ** 0.65,
        "6":      ps ** 0.80,
        # Risk: high power slightly raises dismissal chance;
        #       high technique suppresses it significantly.
        "wicket": (ps ** 0.18) / (ts ** 0.55),
        "wide":   1.0,
        "no_ball": 1.0,
    }

    for key in ("1", "2", "3", "4", "6"):
        mod[key] *= f
    mod["wicket"] *= (2.0 - f)   # poor form → more dismissals

    return mod


# ── Bowler modifier ───────────────────────────────────────────────────────────

def bowler_modifier(
    bowler: "Player",
    phase: str,
    pitch: "PitchConditions",
    weather: "WeatherConditions",
) -> Dict[str, float]:
    """
    Ratio-based bowler modifier.

    economy    → tight lines = more dots, fewer boundaries, fewer extras.
                 High economy suppresses scoring across all shot types.
    swing_seam → primary wicket-taking tool for pacers.
                 Amplified by pitch pace_modifier and weather swing bonus.
    spin       → primary wicket-taking tool for spinners.
                 Amplified by pitch spin_modifier (grows with deterioration).
    pace       → additional wicket/dot contribution in powerplay & death.
    """
    eco_s = _attr_scale(bowler.economy)   # economy scale

    # Good economy bowler (eco_s > 1) compresses scoring probabilities.
    # Poor economy bowler (eco_s < 1) leaks runs; extras go up.
    mod: Dict[str, float] = {
        "dot":    eco_s ** 0.65,
        "1":      1.0 / (eco_s ** 0.30),
        "2":      1.0 / (eco_s ** 0.40),
        "3":      1.0,
        "4":      1.0 / (eco_s ** 0.75),
        "6":      1.0 / (eco_s ** 0.80),
        "wicket": 1.0,              # filled in below
        "wide":   1.0 / (eco_s ** 0.50),   # poor economy → more wides
        "no_ball": 1.0 / (eco_s ** 0.30),
    }

    # ── Wicket-taking effectiveness ────────────────────────────────────────
    if bowler.is_pacer():
        effectiveness = (bowler.swing_seam / 100.0) * pitch.pace_modifier
        effectiveness *= (1.0 + weather.swing_bonus)
        if phase in ("powerplay", "death"):
            pace_bonus = max(0.0, (bowler.pace / 100.0 - 0.5)) * 0.35
            effectiveness *= (1.0 + pace_bonus)
    elif bowler.is_spinner():
        effectiveness = (bowler.spin / 100.0) * pitch.spin_modifier_at_over(0)
        if phase == "middle":
            effectiveness *= 1.15
    else:
        effectiveness = 0.28   # part-timers, rare wickets

    # Neutral point: effectiveness = 0.50 (50-stat bowler, balanced pitch)
    # → eff_scale = 1.0 → wicket_mod = 1.0 (no change from base probs)
    eff_scale = max(0.25, effectiveness / 0.50)
    mod["wicket"] = eff_scale ** 0.45

    return mod


# ── Pitch modifier ─────────────────────────────────────────────────────────────

def pitch_modifier(pitch: "PitchConditions", over: int) -> Dict[str, float]:
    """
    Pitch condition modifier, centered at neutral for batting_modifier = 1.0.
    A balanced pitch (bm=1.0) applies no modifier to any outcome.
    Batting paradise (bm=1.15) boosts boundaries, reduces dots/wickets.
    Seaming pitch (bm=0.90) suppresses scoring, aids wicket-taking.
    """
    delta = pitch.batting_modifier - 1.0   # range ~-0.20 to +0.20

    return {
        "dot":    1.0 - delta * 0.85,
        "1":      1.0 + delta * 0.50,
        "2":      1.0 + delta * 0.55,
        "3":      1.0,
        "4":      1.0 + delta * 1.10,
        "6":      1.0 + delta * 1.20,
        "wicket": 1.0 - delta * 0.80,
        "wide":   1.0,
        "no_ball": 1.0,
    }


# ── Tactical modifiers ────────────────────────────────────────────────────────

# How each batting intent shifts probabilities
BATTING_INTENT_MODS: Dict[str, Dict[str, float]] = {
    "aggressive": {
        "dot":    0.88,
        "1":      0.90,
        "2":      0.95,
        "3":      1.0,
        "4":      1.18,
        "6":      1.30,
        "wicket": 1.20,
        "wide":   1.0,
        "no_ball": 1.0,
    },
    "balanced": {
        "dot":    1.0,
        "1":      1.0,
        "2":      1.0,
        "3":      1.0,
        "4":      1.0,
        "6":      1.0,
        "wicket": 1.0,
        "wide":   1.0,
        "no_ball": 1.0,
    },
    "conservative": {
        "dot":    1.10,
        "1":      1.12,
        "2":      1.08,
        "3":      1.0,
        "4":      0.82,
        "6":      0.65,
        "wicket": 0.82,
        "wide":   1.0,
        "no_ball": 1.0,
    },
}

# Field setting shifts boundary probability
FIELD_SETTING_MODS: Dict[str, Dict[str, float]] = {
    "attacking": {
        "dot":    0.94,
        "1":      0.96,
        "2":      0.98,
        "3":      1.0,
        "4":      1.12,
        "6":      1.05,
        "wicket": 1.12,
        "wide":   1.0,
        "no_ball": 1.0,
    },
    "standard": {
        k: 1.0 for k in ("dot","1","2","3","4","6","wicket","wide","no_ball")
    },
    "defensive": {
        "dot":    1.06,
        "1":      1.05,
        "2":      1.04,
        "3":      1.0,
        "4":      0.85,
        "6":      0.82,
        "wicket": 0.90,
        "wide":   1.0,
        "no_ball": 1.0,
    },
}


def batting_intent_modifier(intent: str) -> Dict[str, float]:
    return dict(BATTING_INTENT_MODS.get(intent, BATTING_INTENT_MODS["balanced"]))


def field_setting_modifier(field: str) -> Dict[str, float]:
    return dict(FIELD_SETTING_MODS.get(field, FIELD_SETTING_MODS["standard"]))


# ── Fatigue modifier ──────────────────────────────────────────────────────────

def fatigue_modifier(batter: "Player", bowler: "Player") -> Dict[str, float]:
    """
    Fatigue degrades performance. Low fitness = small penalties to positive outcomes.
    Applied to both batter (scoring) and bowler (wicket-taking/economy).
    """
    batter_fitness = batter.effective_fitness()
    bowler_fitness = bowler.effective_fitness()

    # Tired batter: more dots, slightly more wickets
    batter_penalty = max(0.0, 1.0 - batter_fitness) * 0.15

    # Tired bowler: slightly more runs conceded
    bowler_penalty = max(0.0, 1.0 - bowler_fitness) * 0.10

    return {
        "dot":    1.0 + batter_penalty * 0.5,
        "1":      1.0 - batter_penalty * 0.3,
        "2":      1.0 - batter_penalty * 0.3,
        "3":      1.0,
        "4":      1.0 - batter_penalty * 0.4 + bowler_penalty * 0.2,
        "6":      1.0 - batter_penalty * 0.4 + bowler_penalty * 0.2,
        "wicket": 1.0 + batter_penalty * 0.6,
        "wide":   1.0 + bowler_penalty * 0.5,
        "no_ball": 1.0 + bowler_penalty * 0.3,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def apply_modifier(probs: Dict[str, float], mod: Dict[str, float]) -> Dict[str, float]:
    """Multiply each probability by the corresponding modifier, then renormalize."""
    result = {k: probs[k] * mod.get(k, 1.0) for k in probs}
    total = sum(result.values())
    if total <= 0:
        return probs
    return {k: v / total for k, v in result.items()}


def normalize(probs: Dict[str, float]) -> Dict[str, float]:
    total = sum(probs.values())
    if total <= 0:
        return probs
    return {k: v / total for k, v in probs.items()}

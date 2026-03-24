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


# ── Batter modifier ───────────────────────────────────────────────────────────

def batter_modifier(batter: "Player", phase: str) -> Dict[str, float]:
    """
    Adjust probabilities based on batter attributes.

    batting_power  → raises 4s/6s, slightly raises wickets (risk)
    batting_technique → raises dots→1s (rotation), lowers wicket probability
    form           → global multiplier on positive outcomes
    """
    p = batter.batting_power / 100.0
    t = batter.batting_technique / 100.0
    f = batter.form

    # Power: each +10 above 50 shifts ~0.008 prob from dot → 4/6
    power_delta = (p - 0.5) * 0.06

    # Technique: each +10 above 50 shifts ~0.006 prob from dot → 1/2
    tech_delta = (t - 0.5) * 0.05

    # Risk factor: high power slightly increases wicket chance
    risk = (p - 0.5) * 0.015

    mod = {
        "dot":    1.0 - (power_delta * 0.5) - (tech_delta * 0.6),
        "1":      1.0 + tech_delta * 0.8,
        "2":      1.0 + tech_delta * 0.5,
        "3":      1.0,
        "4":      1.0 + power_delta * 0.9,
        "6":      1.0 + power_delta * 1.2,
        "wicket": 1.0 + risk - (t - 0.5) * 0.08,
        "wide":   1.0,
        "no_ball": 1.0,
    }

    # Apply form as a global multiplier on run-scoring outcomes
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
    Adjust probabilities based on bowler attributes and conditions.

    economy    → more dots, fewer boundaries
    swing_seam → wicket probability for pacers (pitch/weather amplified)
    spin       → wicket probability for spinners (pitch amplified)
    pace       → small wicket/dot bonus in powerplay & death
    """
    eco = bowler.economy / 100.0
    swing = bowler.swing_seam / 100.0
    spn = bowler.spin / 100.0
    pc = bowler.pace / 100.0

    # Economy effect: restricts scoring
    eco_delta = (eco - 0.5) * 0.06

    # Wicket-taking
    if bowler.is_pacer():
        effectiveness = swing * pitch.pace_modifier * (1.0 + weather.swing_bonus)
        # Pace bonus in powerplay and death
        if phase in ("powerplay", "death"):
            effectiveness *= (1.0 + (pc - 0.5) * 0.2)
    elif bowler.is_spinner():
        effectiveness = spn * pitch.spin_modifier_at_over(0)   # caller can override
        # Spinners more effective in middle overs
        if phase == "middle":
            effectiveness *= 1.12
    else:
        effectiveness = 0.3   # part-timers

    wicket_delta = (effectiveness - 0.4) * 0.08

    mod = {
        "dot":    1.0 + eco_delta * 0.7,
        "1":      1.0 - eco_delta * 0.3,
        "2":      1.0 - eco_delta * 0.4,
        "3":      1.0,
        "4":      1.0 - eco_delta * 0.8,
        "6":      1.0 - eco_delta * 0.9,
        "wicket": 1.0 + wicket_delta,
        "wide":   1.0,
        "no_ball": 1.0,
    }

    return mod


# ── Pitch modifier ─────────────────────────────────────────────────────────────

def pitch_modifier(pitch: "PitchConditions", over: int) -> Dict[str, float]:
    """Global pitch modifier applied on top of bowler-specific effects."""
    bm = pitch.batting_modifier
    return {
        "dot":    2.0 - bm,       # batting-friendly → fewer dots
        "1":      bm * 0.95,
        "2":      bm * 1.0,
        "3":      1.0,
        "4":      bm * 1.05,
        "6":      bm * 1.08,
        "wicket": 2.0 - bm,       # batting-friendly → fewer wickets
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

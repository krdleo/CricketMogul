"""
Matrix validator: 5 matchup scenarios run side-by-side to verify the
attribute system scales sensibly across skill tiers.

Each scenario runs 10,000 balls at a representative over (over 10 / middle)
unless the scenario specifically targets a phase (e.g. death overs for tailender).
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from typing import Optional

from ..models.player import Player, PlayerRole, BattingStyle, BowlingType
from ..models.conditions import PitchConditions, WeatherConditions
from ..models.tactics import Tactics, BattingIntent, FieldSetting, PowerplayStrategy, DeathOversPlan
from ..engine.ball_resolver import resolve_ball
from ..models.match import BallOutcome


# ── Player factories ──────────────────────────────────────────────────────────

def _batter(
    name: str,
    power: int,
    technique: int,
    role: PlayerRole = PlayerRole.TOP_ORDER,
    temperament: int = 65,
    form: float = 1.0,
) -> Player:
    return Player(
        name=name,
        age=26,
        role=role,
        batting_style=BattingStyle.RIGHT,
        bowling_type=BowlingType.NONE,
        batting_power=power,
        batting_technique=technique,
        pace=1,
        swing_seam=1,
        spin=1,
        economy=50,
        fielding=60,
        fitness=80,
        temperament=temperament,
        form=form,
        fatigue=0.0,
    )


def _pacer(
    name: str,
    pace: int,
    swing: int,
    economy: int,
    temperament: int = 65,
    form: float = 1.0,
) -> Player:
    return Player(
        name=name,
        age=26,
        role=PlayerRole.FAST_BOWLER,
        batting_style=BattingStyle.RIGHT,
        bowling_type=BowlingType.RIGHT_FAST,
        batting_power=20,
        batting_technique=20,
        pace=pace,
        swing_seam=swing,
        spin=1,
        economy=economy,
        fielding=55,
        fitness=80,
        temperament=temperament,
        form=form,
        fatigue=0.0,
    )


# ── Neutral tactics (balanced everything) ─────────────────────────────────────

def _neutral() -> Tactics:
    return Tactics(
        batting_intent=BattingIntent.BALANCED,
        field_setting=FieldSetting.STANDARD,
        powerplay_strategy=PowerplayStrategy.STEADY,
        death_overs_plan=DeathOversPlan.CALCULATED,
    )


# ── Core simulation ───────────────────────────────────────────────────────────

@dataclass
class ScenarioStats:
    label: str
    description: str
    dot_pct: float
    singles_pct: float
    twos_pct: float
    fours_pct: float
    sixes_pct: float
    wicket_pct: float
    extras_pct: float          # wides + no_balls
    strike_rate: float         # batter's SR (run-scoring balls only / legal balls)
    run_rate: float            # runs per over (includes extras)
    wickets_per_over: float
    boundary_pct: float        # % of balls that go for 4 or 6
    n: int


def simulate_scenario(
    label: str,
    description: str,
    batter: Player,
    bowler: Player,
    pitch: PitchConditions,
    weather: WeatherConditions,
    over_number: int = 10,
    n: int = 10_000,
    seed: int = 42,
    pressure: float = 0.2,
) -> ScenarioStats:
    rng = random.Random(seed)
    tactics = _neutral()
    counter: Counter = Counter()

    for i in range(n):
        result = resolve_ball(
            batter=batter,
            bowler=bowler,
            over_number=over_number,
            ball_number=(i % 6) + 1,
            pitch=pitch,
            weather=weather,
            batting_tactics=tactics,
            bowling_tactics=tactics,
            pressure=pressure,
            fielding_team=None,
            rng=rng,
        )
        counter[result.outcome.value] += 1

    total = sum(counter.values())
    legal = total - counter["wide"] - counter["no_ball"]

    # Runs scored BY THE BATTER (no extras)
    batter_runs = (
        counter["1"] * 1 + counter["2"] * 2 + counter["3"] * 3 +
        counter["4"] * 4 + counter["6"] * 6
    )
    # All runs (including extras)
    total_runs = batter_runs + counter["wide"] + counter["no_ball"]
    boundary_runs = counter["4"] * 4 + counter["6"] * 6

    sr = (batter_runs / legal * 100) if legal > 0 else 0.0
    rr = (total_runs / (legal / 6)) if legal > 0 else 0.0
    wpo = (counter["wicket"] / (legal / 6)) if legal > 0 else 0.0

    return ScenarioStats(
        label=label,
        description=description,
        dot_pct=counter["dot"] / legal * 100 if legal > 0 else 0,
        singles_pct=counter["1"] / total * 100,
        twos_pct=counter["2"] / total * 100,
        fours_pct=counter["4"] / total * 100,
        sixes_pct=counter["6"] / total * 100,
        wicket_pct=counter["wicket"] / total * 100,
        extras_pct=(counter["wide"] + counter["no_ball"]) / total * 100,
        strike_rate=sr,
        run_rate=rr,
        wickets_per_over=wpo,
        boundary_pct=(counter["4"] + counter["6"]) / total * 100,
        n=total,
    )


# ── Display ───────────────────────────────────────────────────────────────────

def _bar(value: float, scale: float, width: int = 20) -> str:
    filled = int(value / scale * width)
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def _delta(value: float, baseline: float) -> str:
    d = value - baseline
    if abs(d) < 0.5:
        return "    —  "
    sign = "+" if d > 0 else ""
    return f"  {sign}{d:+.1f} "


def print_matrix(scenarios: list[ScenarioStats]) -> None:
    """Print all scenarios as a comparative table."""
    W = 14   # column width

    def col(v: str) -> str:
        return str(v).center(W)

    SEP = "─" * (12 + W * len(scenarios))

    print("\n")
    print("╔" + "═" * (10 + W * len(scenarios)) + "╗")
    print("║  MATCHUP MATRIX — Attribute Scaling Validation".ljust(10 + W * len(scenarios)) + "  ║")
    print("╚" + "═" * (10 + W * len(scenarios)) + "╝")

    # Header row
    print(f"\n  {'Metric':<22}", end="")
    for s in scenarios:
        print(col(s.label), end="")
    print()
    print("  " + SEP)

    # Scenario descriptions (2-line wrap)
    print(f"\n  {'Matchup':<22}", end="")
    for s in scenarios:
        # truncate long descriptions for the column
        short = s.description[:W-1]
        print(col(short), end="")
    print()

    print("\n  " + "─" * (10 + W * len(scenarios)))

    # Numeric rows
    rows = [
        ("Strike Rate",     [f"{s.strike_rate:.1f}"      for s in scenarios]),
        ("Run Rate/ov",     [f"{s.run_rate:.2f}"          for s in scenarios]),
        ("Dot Ball %",      [f"{s.dot_pct:.1f}%"          for s in scenarios]),
        ("Boundary % (4+6)",[f"{s.boundary_pct:.1f}%"     for s in scenarios]),
        ("Wickets/ov",      [f"{s.wickets_per_over:.3f}"   for s in scenarios]),
        ("Extras %",        [f"{s.extras_pct:.1f}%"        for s in scenarios]),
        ("4s %",            [f"{s.fours_pct:.1f}%"         for s in scenarios]),
        ("6s %",            [f"{s.sixes_pct:.1f}%"         for s in scenarios]),
        ("Wicket %",        [f"{s.wicket_pct:.1f}%"        for s in scenarios]),
    ]

    for metric, vals in rows:
        print(f"  {metric:<22}", end="")
        for v in vals:
            print(col(v), end="")
        print()

    print("\n  " + SEP)

    # Visual SR bar chart
    print(f"\n  {'Strike Rate bar':<22}", end="")
    for s in scenarios:
        bar = _bar(s.strike_rate, 200, 12)
        print(f"  {bar}", end="")
    print()

    # Visual dot ball bar chart
    print(f"  {'Dot Ball % bar':<22}", end="")
    for s in scenarios:
        bar = _bar(s.dot_pct, 80, 12)
        print(f"  {bar}", end="")
    print()

    # Visual wickets bar chart
    print(f"  {'Wickets/ov bar':<22}", end="")
    for s in scenarios:
        bar = _bar(s.wickets_per_over, 1.5, 12)
        print(f"  {bar}", end="")
    print()

    print(f"\n  Scale: SR bar=0–200, Dot bar=0–80%, Wkt bar=0–1.5/ov\n")

    # Qualitative verdict
    print("  " + "─" * (10 + W * len(scenarios)))
    print(f"\n  {'Expected?':<22}", end="")
    verdicts = _auto_verdict(scenarios)
    for v in verdicts:
        print(col(v), end="")
    print()
    print()


def _auto_verdict(scenarios: list[ScenarioStats]) -> list[str]:
    """
    Automated pass/fail checks against expected behaviour per scenario.
    These ranges are intentionally wide — the engine needs to produce the
    right ORDER and MAGNITUDE of differences, not hit exact targets.
    Fine-grained calibration is Phase 6 (10K match sims vs IPL benchmarks).
    """
    expected = [
        # S1: Elite bat (88/87) vs Avg bowl (47/47/47) on batting pitch
        # → extreme run-scoring; wickets very rare
        dict(min_sr=155, max_sr=999, max_wpo=0.45, min_boundary=22, label="1"),
        # S2: Avg bat (47/47) vs Elite bowl (88/87/87) on seaming pitch
        # → highly suppressed scoring; frequent wickets
        dict(min_sr=0,   max_sr=105, min_wpo=0.42, min_dot=48,     label="2"),
        # S3: Tailender (20/18) vs Good death bowler (78/75/79), death overs
        # → near-powerless; most balls are dots. A dismissal every ~13 balls
        #   is realistic for a #10/#11 (0.40–0.60 wkts/ov).
        dict(min_sr=0,   max_sr=90,  min_wpo=0.38, min_dot=55,     label="3"),
        # S4: Both elite (88/87 each) on balanced pitch
        # → high-quality contest; elite bat and bowl partially cancel
        dict(min_sr=118, max_sr=175, label="4"),
        # S5: Both weak (37/36 each) on balanced pitch
        # → scrappy; dot ball % must be meaningfully higher than S4.
        #   SR is lower but the key story is dots+extras, not SR alone.
        dict(min_sr=70,  max_sr=130, min_dot_vs_s4_delta=6, label="5"),
    ]

    # S4 stats needed for the S5 relative check
    s4_dot = scenarios[3].dot_pct if len(scenarios) > 3 else 0.0

    verdicts = []
    for s, exp in zip(scenarios, expected):
        checks = []
        if "min_sr"       in exp: checks.append(s.strike_rate       >= exp["min_sr"])
        if "max_sr"       in exp: checks.append(s.strike_rate       <= exp["max_sr"])
        if "max_wpo"      in exp: checks.append(s.wickets_per_over  <= exp["max_wpo"])
        if "min_wpo"      in exp: checks.append(s.wickets_per_over  >= exp["min_wpo"])
        if "min_dot"      in exp: checks.append(s.dot_pct           >= exp["min_dot"])
        if "min_boundary" in exp: checks.append(s.boundary_pct      >= exp["min_boundary"])
        # S5 must have more dot balls than S4 (weak players = less rotation)
        if "min_dot_vs_s4_delta" in exp:
            checks.append(s.dot_pct > s4_dot + exp["min_dot_vs_s4_delta"])
        verdicts.append("PASS ✓" if all(checks) else "FAIL ✗")

    return verdicts


# ── Scenario definitions ──────────────────────────────────────────────────────

def build_scenarios(n: int = 10_000, seed: int = 42) -> list[ScenarioStats]:
    weather = WeatherConditions()

    scenarios = []

    # ── S1: Elite batter vs average bowler, batting pitch ─────────────────
    scenarios.append(simulate_scenario(
        label="S1",
        description="EliteBat/AvgBwl/Bat",
        batter=_batter("EliteBat", power=88, technique=87, temperament=80),
        bowler=_pacer("AvgBwl",   pace=48,  swing=47,     economy=47, temperament=55),
        pitch=PitchConditions.batting_paradise(),
        weather=weather,
        over_number=10,
        n=n, seed=seed,
    ))

    # ── S2: Average batter vs elite bowler, seaming pitch ─────────────────
    scenarios.append(simulate_scenario(
        label="S2",
        description="AvgBat/EliteBwl/Seam",
        batter=_batter("AvgBat",   power=48, technique=47, temperament=55),
        bowler=_pacer("EliteBwl",  pace=88,  swing=87,     economy=87, temperament=80),
        pitch=PitchConditions.green_seamer(),
        weather=weather,
        over_number=10,
        n=n, seed=seed,
    ))

    # ── S3: Tailender vs good death bowler, death overs ───────────────────
    scenarios.append(simulate_scenario(
        label="S3",
        description="Tailend/DeathBwl/Death",
        batter=_batter("Tailender", power=20, technique=18,
                       role=PlayerRole.FAST_BOWLER, temperament=40),
        bowler=_pacer("DeathBwl",  pace=78,  swing=75,     economy=79, temperament=75),
        pitch=PitchConditions.balanced(),
        weather=weather,
        over_number=18,      # death overs
        n=n, seed=seed,
    ))

    # ── S4: Both elite, balanced pitch ────────────────────────────────────
    scenarios.append(simulate_scenario(
        label="S4",
        description="EliteBat/EliteBwl/Bal",
        batter=_batter("EliteBat2", power=88, technique=87, temperament=80),
        bowler=_pacer("EliteBwl2", pace=88,   swing=87,     economy=87, temperament=80),
        pitch=PitchConditions.balanced(),
        weather=weather,
        over_number=10,
        n=n, seed=seed,
    ))

    # ── S5: Both weak, balanced pitch ─────────────────────────────────────
    scenarios.append(simulate_scenario(
        label="S5",
        description="WeakBat/WeakBwl/Bal",
        batter=_batter("WeakBat",  power=37, technique=36, temperament=50),
        bowler=_pacer("WeakBwl",   pace=36,  swing=35,     economy=37, temperament=50),
        pitch=PitchConditions.balanced(),
        weather=weather,
        over_number=10,
        n=n, seed=seed,
    ))

    return scenarios


def run_matrix_validation(n: int = 10_000, seed: int = 42) -> None:
    print("\n  Building matchup matrix — 5 scenarios × 10,000 balls each...")
    scenarios = build_scenarios(n=n, seed=seed)
    print_matrix(scenarios)

    # Per-scenario drill-down
    print("\n  ── Per-Scenario Detail ─────────────────────────────────────────\n")
    for s in scenarios:
        _print_scenario_detail(s)


def _print_scenario_detail(s: ScenarioStats) -> None:
    OUTCOMES = ["dot", "1", "2", "3", "4", "6", "wicket", "wide", "no_ball"]
    # Map percentage fields back to individual outcomes for bar chart
    outcome_data = {
        "dot":     s.dot_pct * s.n / 100 / s.n * 100,  # = dot_pct (recalc for consistency)
        "1":       s.singles_pct,
        "2":       s.twos_pct,
        "3":       0.0,  # not stored individually; shown as ~0
        "4":       s.fours_pct,
        "6":       s.sixes_pct,
        "wicket":  s.wicket_pct,
        "wide":    s.extras_pct * 0.72,   # approximate split (wides ~72% of extras)
        "no_ball": s.extras_pct * 0.28,
    }

    print(f"  ┌─ {s.label}: {s.description}")
    print(f"  │  SR: {s.strike_rate:.1f}  RR: {s.run_rate:.2f}/ov  "
          f"Dots: {s.dot_pct:.1f}%  Wkts/ov: {s.wickets_per_over:.3f}  "
          f"Boundaries: {s.boundary_pct:.1f}%")

    BAR_W = 25
    for outcome in OUTCOMES:
        pct = outcome_data.get(outcome, 0.0)
        bar = "█" * int(pct / 60 * BAR_W)
        print(f"  │  {outcome:<8} {pct:>5.1f}%  {bar}")
    print(f"  └{'─' * 55}\n")

"""
Phase 1 validator: simulate N balls between a batter and bowler and print
the outcome distribution alongside IPL benchmarks.
"""

from __future__ import annotations

import random
from collections import Counter
from typing import Optional

from ..models.player import Player, PlayerRole, BattingStyle, BowlingType
from ..models.conditions import PitchConditions, WeatherConditions
from ..models.tactics import Tactics, BattingIntent, FieldSetting, PowerplayStrategy, DeathOversPlan
from ..engine.ball_resolver import resolve_ball
from ..models.match import BallOutcome


def _make_balanced_batter(name: str = "TestBatter") -> Player:
    return Player(
        name=name,
        age=28,
        role=PlayerRole.TOP_ORDER,
        batting_style=BattingStyle.RIGHT,
        bowling_type=BowlingType.NONE,
        batting_power=75,
        batting_technique=75,
        pace=1,
        swing_seam=1,
        spin=1,
        economy=50,
        fielding=60,
        fitness=80,
        temperament=70,
        form=1.0,
        fatigue=0.0,
    )


def _make_balanced_pacer(name: str = "TestPacer") -> Player:
    return Player(
        name=name,
        age=27,
        role=PlayerRole.FAST_BOWLER,
        batting_style=BattingStyle.RIGHT,
        bowling_type=BowlingType.RIGHT_FAST,
        batting_power=20,
        batting_technique=20,
        pace=75,
        swing_seam=75,
        spin=1,
        economy=75,
        fielding=55,
        fitness=80,
        temperament=70,
        form=1.0,
        fatigue=0.0,
    )


def _neutral_tactics() -> Tactics:
    """Fully neutral tactics — no tactical modifiers applied (balanced everything)."""
    return Tactics(
        batting_intent=BattingIntent.BALANCED,
        field_setting=FieldSetting.STANDARD,
        powerplay_strategy=PowerplayStrategy.STEADY,    # no aggressive powerplay bonus
        death_overs_plan=DeathOversPlan.CALCULATED,
    )


def simulate_n_balls(
    n: int = 10_000,
    seed: int = 42,
    over_number: int = 10,      # middle overs by default
    pressure: float = 0.2,
    batter: Optional[Player] = None,
    bowler: Optional[Player] = None,
    pitch: Optional[PitchConditions] = None,
    weather: Optional[WeatherConditions] = None,
) -> dict:
    """Simulate n balls and return a stats dict."""
    rng = random.Random(seed)

    if batter is None:
        batter = _make_balanced_batter()
    if bowler is None:
        bowler = _make_balanced_pacer()
    if pitch is None:
        pitch = PitchConditions.balanced()
    if weather is None:
        weather = WeatherConditions()

    tactics = _neutral_tactics()
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

    # Build stats
    totals = {k: counter.get(k, 0) for k in (
        "dot", "1", "2", "3", "4", "6", "wicket", "wide", "no_ball"
    )}
    total_balls = sum(totals.values())

    # Derived metrics
    legal_balls = total_balls - totals["wide"] - totals["no_ball"]
    runs = (
        totals["1"] * 1 + totals["2"] * 2 + totals["3"] * 3 +
        totals["4"] * 4 + totals["6"] * 6 +
        totals["wide"] + totals["no_ball"]
    )
    boundary_runs = totals["4"] * 4 + totals["6"] * 6
    wickets = totals["wicket"]

    # Determine phase label for benchmark display
    phase_label = "powerplay" if over_number <= 6 else ("death" if over_number >= 16 else "middle")

    return {
        "n_balls": total_balls,
        "counts": totals,
        "percentages": {k: v / total_balls * 100 for k, v in totals.items()},
        "legal_balls": legal_balls,
        "runs": runs,
        "wickets": wickets,
        "run_rate_per_over": runs / (legal_balls / 6) if legal_balls > 0 else 0,
        "dot_pct": totals["dot"] / legal_balls * 100 if legal_balls > 0 else 0,
        "boundary_run_pct": boundary_runs / runs * 100 if runs > 0 else 0,
        "wicket_per_over": wickets / (legal_balls / 6) if legal_balls > 0 else 0,
        "phase": phase_label,
    }


def print_distribution(stats: dict, title: str = "Ball Outcome Distribution") -> None:
    counts = stats["counts"]
    pcts = stats["percentages"]
    n = stats["n_balls"]

    BAR_WIDTH = 30
    OUTCOMES = ["dot", "1", "2", "3", "4", "6", "wicket", "wide", "no_ball"]

    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print(f"  Balls simulated: {n:,}")
    print(f"{'═' * 60}")
    print(f"  {'Outcome':<10} {'Count':>7}  {'%':>6}  {'Bar'}")
    print(f"  {'-'*55}")

    for outcome in OUTCOMES:
        count = counts[outcome]
        pct = pcts[outcome]
        bar = "█" * int(pct / 100 * BAR_WIDTH)
        print(f"  {outcome:<10} {count:>7,}  {pct:>5.2f}%  {bar}")

    print(f"  {'-'*55}")
    print(f"\n  Derived Metrics")
    print(f"  {'─'*55}")
    # Phase-specific IPL benchmarks (team averages; 75-stat players will score above these)
    phase = stats.get("phase", "middle")
    rr_bench   = {"powerplay": "7.5–9.2", "middle": "7.5–8.5", "death": "10.0–12.0"}.get(phase, "8.2–8.7")
    dot_bench  = {"powerplay": "33–39%",  "middle": "38–44%",  "death": "31–37%"}.get(phase, "35–42%")
    bnd_bench  = {"powerplay": "55–65%",  "middle": "45–58%",  "death": "60–72%"}.get(phase, "55–65%")
    wpo_bench  = {"powerplay": "0.20–0.35","middle": "0.30–0.40","death": "0.30–0.42"}.get(phase, "~0.35")

    print(f"  Run rate (per over)  : {stats['run_rate_per_over']:>6.2f}   [IPL {phase}: {rr_bench}]")
    print(f"  Dot ball %           : {stats['dot_pct']:>6.2f}%  [IPL {phase}: {dot_bench}]")
    print(f"  Boundary run %       : {stats['boundary_run_pct']:>6.2f}%  [IPL {phase}: {bnd_bench}]")
    print(f"  Wickets per over     : {stats['wicket_per_over']:>6.3f}   [IPL {phase}: {wpo_bench}]")
    print(f"{'═' * 60}\n")


def run_phase_comparison(n: int = 10_000, seed: int = 42) -> None:
    """Compare distributions across powerplay, middle, and death overs."""
    phase_overs = {"Powerplay (over 3)": 3, "Middle (over 10)": 10, "Death (over 18)": 18}

    batter = _make_balanced_batter()
    bowler = _make_balanced_pacer()
    pitch = PitchConditions.balanced()
    weather = WeatherConditions()

    for label, over in phase_overs.items():
        stats = simulate_n_balls(
            n=n, seed=seed, over_number=over,
            batter=batter, bowler=bowler,
            pitch=pitch, weather=weather,
        )
        print_distribution(stats, title=f"Phase: {label}  ({n:,} balls)")

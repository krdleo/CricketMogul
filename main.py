"""
Cricket Dynasty Engine — CLI entry point.

Usage:
  python main.py phase1           # Ball distribution: 75 batter vs 75 bowler, 10K balls
  python main.py phase1 --full    # Also compare across all three match phases
  python main.py matrix           # Attribute scaling matrix: 5 matchup scenarios
"""

import argparse

from cricket_dynasty_engine.analysis.validator import (
    simulate_n_balls,
    print_distribution,
    run_phase_comparison,
)
from cricket_dynasty_engine.analysis.matrix_validator import run_matrix_validation


def cmd_phase1(args) -> None:
    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║        Cricket Dynasty Engine — Phase 1 Validation       ║")
    print("║   Batter: batting_power=75, batting_technique=75         ║")
    print("║   Bowler: pace=75, swing_seam=75, economy=75             ║")
    print("║   Pitch: balanced  |  Tactics: balanced/standard         ║")
    print("╚══════════════════════════════════════════════════════════╝")

    stats = simulate_n_balls(n=10_000, seed=42, over_number=10)
    print_distribution(stats, title="10,000 balls — Middle Overs (balanced conditions)")

    if args.full:
        run_phase_comparison(n=10_000, seed=42)


def cmd_matrix(args) -> None:
    run_matrix_validation(n=10_000, seed=42)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cricket Dynasty Engine")
    subparsers = parser.add_subparsers(dest="command")

    p1 = subparsers.add_parser("phase1", help="Phase 1: ball distribution validation")
    p1.add_argument("--full", action="store_true", help="Show all three phase comparisons")

    subparsers.add_parser("matrix", help="Attribute scaling matrix: 5 matchup scenarios")

    args = parser.parse_args()

    if args.command == "phase1":
        cmd_phase1(args)
    elif args.command == "matrix":
        cmd_matrix(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

"""
Match conditions: pitch and weather.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class PitchType(str, Enum):
    BATTING = "batting"
    SEAMING = "seaming"
    SPINNING = "spinning"
    BALANCED = "balanced"


class WeatherCondition(str, Enum):
    CLEAR = "clear"
    OVERCAST = "overcast"       # helps swing/seam bowlers
    HUMID = "humid"             # aids swing
    HOT = "hot"                 # tires players faster
    DRY = "dry"                 # benefits spinners (dusty)


@dataclass
class PitchConditions:
    type: PitchType = PitchType.BALANCED
    pace_modifier: float = 1.0      # 0.8–1.2 multiplier on pace/swing effectiveness
    spin_modifier: float = 1.0      # 0.8–1.2 multiplier on spin effectiveness
    batting_modifier: float = 1.0   # 0.8–1.2 multiplier on batting effectiveness
    deterioration_rate: float = 0.01  # per over, added to spin_modifier (spin benefits later)

    def spin_modifier_at_over(self, over: int) -> float:
        """Pitch deteriorates over time, benefiting spin."""
        return min(1.3, self.spin_modifier + self.deterioration_rate * over)

    @classmethod
    def balanced(cls) -> "PitchConditions":
        return cls(type=PitchType.BALANCED)

    @classmethod
    def batting_paradise(cls) -> "PitchConditions":
        return cls(
            type=PitchType.BATTING,
            pace_modifier=0.85,
            spin_modifier=0.85,
            batting_modifier=1.15,
            deterioration_rate=0.005,
        )

    @classmethod
    def green_seamer(cls) -> "PitchConditions":
        return cls(
            type=PitchType.SEAMING,
            pace_modifier=1.2,
            spin_modifier=0.85,
            batting_modifier=0.9,
            deterioration_rate=0.008,
        )

    @classmethod
    def dusty_turner(cls) -> "PitchConditions":
        return cls(
            type=PitchType.SPINNING,
            pace_modifier=0.9,
            spin_modifier=1.2,
            batting_modifier=0.88,
            deterioration_rate=0.015,
        )


@dataclass
class WeatherConditions:
    condition: WeatherCondition = WeatherCondition.CLEAR
    temperature: int = 28       # Celsius
    humidity: int = 50          # percent
    wind_speed: int = 10        # km/h

    @property
    def swing_bonus(self) -> float:
        """Overcast/humid conditions aid swing bowlers."""
        if self.condition == WeatherCondition.OVERCAST:
            return 0.12
        if self.condition == WeatherCondition.HUMID:
            return 0.08
        return 0.0

    @property
    def fatigue_rate_multiplier(self) -> float:
        """Hot weather increases fatigue accumulation."""
        if self.condition == WeatherCondition.HOT or self.temperature > 35:
            return 1.2
        return 1.0

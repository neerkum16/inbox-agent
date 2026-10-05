"""
Deterministic random utility functions for the Bank Database.
"""

import random
from decimal import Decimal, ROUND_HALF_UP
from typing import Mapping, Sequence, TypeVar

T = TypeVar("T")


class RandomUtils:
    """Independent deterministic random generator backed by random.Random."""

    def __init__(self, seed: int):
        if not isinstance(seed, int):
            raise TypeError("seed must be an integer.")
        self.random = random.Random(seed)

    def randint(self, minimum: int, maximum: int) -> int:
        if minimum > maximum:
            raise ValueError("minimum cannot be greater than maximum.")
        return self.random.randint(minimum, maximum)

    def choice(self, items: Sequence[T]) -> T:
        if not items:
            raise ValueError("Cannot select from an empty collection.")
        return self.random.choice(items)

    def sample(self, items: Sequence[T], count: int) -> list[T]:
        if count < 0:
            raise ValueError("count cannot be negative.")
        if count > len(items):
            raise ValueError("count cannot exceed collection size.")
        return self.random.sample(list(items), count)

    def probability(self) -> float:
        return self.random.random()

    def decimal(
        self,
        minimum,
        maximum,
        precision: int = 2,
    ) -> Decimal:
        if precision < 0:
            raise ValueError("precision cannot be negative.")

        minimum_value = Decimal(str(minimum))
        maximum_value = Decimal(str(maximum))

        if minimum_value > maximum_value:
            raise ValueError("minimum cannot be greater than maximum.")

        scale = Decimal(10) ** precision
        minimum_scaled = int((minimum_value * scale).to_integral_value(rounding=ROUND_HALF_UP))
        maximum_scaled = int((maximum_value * scale).to_integral_value(rounding=ROUND_HALF_UP))

        value = self.random.randint(minimum_scaled, maximum_scaled)
        quantizer = Decimal("1").scaleb(-precision)
        return (Decimal(value) / scale).quantize(quantizer, rounding=ROUND_HALF_UP)

    def weighted_choice(self, weights: Mapping[T, float]) -> T:
        if not weights:
            raise ValueError("Weights cannot be empty.")

        normalized = []
        total_weight = 0.0

        for item, weight in weights.items():
            numeric_weight = float(weight)
            if numeric_weight < 0:
                raise ValueError(f"Weight cannot be negative: {item}={weight}")
            if numeric_weight > 0:
                normalized.append((item, numeric_weight))
                total_weight += numeric_weight

        if total_weight <= 0:
            raise ValueError("Total weight must be greater than zero.")

        threshold = self.random.random() * total_weight
        cumulative = 0.0

        for item, weight in normalized:
            cumulative += weight
            if threshold < cumulative:
                return item

        return normalized[-1][0]

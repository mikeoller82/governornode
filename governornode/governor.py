"""LoopGovernor and EntropyMonitor — enforcement components for GovernorNode."""

import math
from collections import Counter


class GovernorExceededError(RuntimeError):
    """Raised when a GovernorNode limit is breached."""
    pass


class LoopGovernor:
    """Tracks iteration count and enforces limits."""

    def __init__(self, max_iterations: int = 25, max_oscillations: int = 5):
        self.max_iterations = max_iterations
        self.max_oscillations = max_oscillations
        self._iteration = 0
        self._last_output: dict | None = None
        self._oscillation_count = 0

    def check(self, output: dict) -> None:
        """Check iteration and oscillation limits. Raises on violation."""
        self._iteration += 1

        if self._iteration > self.max_iterations:
            raise GovernorExceededError(
                f"Node exceeded max_iterations={self.max_iterations} "
                f"(iteration={self._iteration})"
            )

        # Oscillation detection: compare output to last output
        if self._last_output is not None and output == self._last_output:
            self._oscillation_count += 1
        else:
            self._oscillation_count = 0

        if self._oscillation_count >= self.max_oscillations:
            raise GovernorExceededError(
                f"Node exceeded max_oscillations={self.max_oscillations} "
                f"(oscillation_count={self._oscillation_count})"
            )

        self._last_output = output

    @property
    def iteration(self) -> int:
        return self._iteration

    def reset(self) -> None:
        """Reset counters (but not policy)."""
        self._iteration = 0
        self._last_output = None
        self._oscillation_count = 0


class EntropyMonitor:
    """Tracks plan diversity (Shannon entropy) across recent outputs.

    Higher entropy = more varied outputs (healthier exploration).
    Low entropy = repetitive/stuck behavior.
    """

    def __init__(self, window: int = 10):
        self.window = window
        self._history: list[tuple] = []

    @staticmethod
    def _make_hashable(obj):
        """Recursively convert dicts/lists to hashable tuples."""
        if isinstance(obj, dict):
            return tuple(sorted(
                (k, EntropyMonitor._make_hashable(v)) for k, v in obj.items()
            ))
        elif isinstance(obj, list):
            return tuple(EntropyMonitor._make_hashable(v) for v in obj)
        elif isinstance(obj, set):
            return tuple(sorted(EntropyMonitor._make_hashable(v) for v in obj))
        return obj

    def record(self, output: dict) -> None:
        """Record an output, maintaining the rolling window."""
        key = self._make_hashable(output)
        self._history.append(key)
        if len(self._history) > self.window:
            self._history.pop(0)

    def get_entropy(self) -> float:
        """Compute Shannon entropy over the current window.

        Returns 0.0 if no data or all identical.
        Max is log2(window) for uniform distribution.
        """
        if len(self._history) < 2:
            return 0.0

        counts = Counter(self._history)
        total = len(self._history)
        entropy = 0.0
        for count in counts.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy

    def get_unique_count(self) -> int:
        """Number of unique outputs in the window."""
        return len(set(self._history))

    def reset(self) -> None:
        self._history.clear()

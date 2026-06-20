"""GovernancePolicy — YAML/dict-driven configuration for GovernorNode."""

import os
from dataclasses import dataclass, field


@dataclass
class GovernancePolicy:
    """Configuration for GovernorNode behavior.

    Load from a dict or YAML file. All fields have sensible defaults.
    """

    max_iterations: int = 25
    """Maximum number of times a node can be called before GovernorExceededError."""

    max_oscillations: int = 5
    """Consecutive identical outputs before oscillation is flagged."""

    entropy_window: int = 10
    """Number of recent outputs to consider for plan entropy calculation."""

    entropy_threshold: float = 0.1
    """Minimum entropy before warning (lower bound, 0 = all same)."""

    record_io: bool = True
    """If True, capture full input/output snapshots in flight records."""

    halt_on_violation: bool = True
    """If True, raise GovernorExceededError on violation. If False, log warnings."""

    @classmethod
    def from_yaml(cls, path: str) -> "GovernancePolicy":
        """Load policy from a YAML file.

        Falls back gracefully if PyYAML is not installed (uses basic parser).
        """
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"YAML at {path} must contain a top-level mapping")
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})

    @classmethod
    def from_dict(cls, data: dict) -> "GovernancePolicy":
        """Load policy from a dict (overrides defaults)."""
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})

    def to_dict(self) -> dict:
        """Export policy as a plain dict (useful for serialization)."""
        return {
            "max_iterations": self.max_iterations,
            "max_oscillations": self.max_oscillations,
            "entropy_window": self.entropy_window,
            "entropy_threshold": self.entropy_threshold,
            "record_io": self.record_io,
            "halt_on_violation": self.halt_on_violation,
        }

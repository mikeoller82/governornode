"""GovernorNode MVP — LangGraph governance wrapper.

Drop-in governance for LangGraph agents: iteration limits, oscillation detection,
flight recorder audit trails, and plan entropy monitoring.
"""

from .core import GovernorNode
from .graph import GovernorStateGraph
from .policy import GovernancePolicy
from .recorder import FlightDataRecorder, FlightRecord
from .governor import GovernorExceededError, LoopGovernor, EntropyMonitor

__all__ = [
    "GovernorNode",
    "GovernorStateGraph",
    "GovernancePolicy",
    "FlightDataRecorder",
    "FlightRecord",
    "GovernorExceededError",
    "LoopGovernor",
    "EntropyMonitor",
]

__version__ = "1.0.0"

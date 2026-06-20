"""GovernorNode — the primary wrapper that adds governance to any LangGraph node."""

import time
from typing import Any, Callable

from .policy import GovernancePolicy
from .recorder import FlightDataRecorder
from .governor import LoopGovernor, EntropyMonitor, GovernorExceededError


class GovernorNode:
    """Wraps a LangGraph node function with governance controls.

    Usage:
        def my_node(state: dict) -> dict:
            return {"result": process(state)}

        policy = GovernancePolicy(max_iterations=10, max_oscillations=3)
        governed = GovernorNode(node=my_node, name="reasoner", policy=policy)

        # Use governed in LangGraph just like the original node
        builder.add_node("reasoner", governed)
    """

    def __init__(
        self,
        node: Callable,
        name: str = "governed_node",
        policy: GovernancePolicy | None = None,
    ):
        self._node = node
        self._name = name
        self._policy = policy or GovernancePolicy()
        self._recorder = FlightDataRecorder()
        self._governor = LoopGovernor(
            max_iterations=self._policy.max_iterations,
            max_oscillations=self._policy.max_oscillations,
        )
        self._entropy = EntropyMonitor(window=self._policy.entropy_window)

    def __call__(self, state: dict, **kwargs) -> dict:
        """Execute the wrapped node with governance enforcement.

        Args:
            state: Current LangGraph state dict.
            **kwargs: Additional keyword arguments passed to the wrapped node.

        Returns:
            The output from the wrapped node.

        Raises:
            GovernorExceededError: If iteration or oscillation limits are breached.
        """
        start = time.perf_counter()
        input_snapshot = dict(state) if self._policy.record_io else None
        error: str | None = None
        output: dict | None = None
        oscillation = False
        entropy = None

        try:
            output = self._node(state, **kwargs) if kwargs else self._node(state)

            # Enforce limits
            self._governor.check(output)

            # Track entropy
            self._entropy.record(output)
            entropy = self._entropy.get_entropy()

        except GovernorExceededError as gve:
            # Re-raise unless halt_on_violation is False
            if self._policy.halt_on_violation:
                raise
            error = str(gve)
            output = state  # pass through state on soft violation

        except Exception as e:
            # Record failure but don't swallow
            error = f"{type(e).__name__}: {e}"
            if self._policy.halt_on_violation:
                raise
            # If halt_on_violation is False, still record and return empty
            output = {}

        finally:
            latency = (time.perf_counter() - start) * 1000  # ms
            output_snapshot = dict(output) if (output and self._policy.record_io) else None

            self._recorder.record(
                node_name=self._name,
                iteration=self._governor.iteration,
                input_snapshot=input_snapshot,
                output_snapshot=output_snapshot,
                latency_ms=latency,
                oscillation_detected=bool(oscillation),
                entropy=entropy,
                error=error,
            )

        return output if output is not None else {}

    def get_recorder(self) -> FlightDataRecorder:
        return self._recorder

    def reset(self) -> None:
        """Reset iteration counter and recorder (but not policy)."""
        self._governor.reset()
        self._recorder.clear()
        self._entropy.reset()

    @property
    def name(self) -> str:
        return self._name

    @property
    def iteration(self) -> int:
        return self._governor.iteration

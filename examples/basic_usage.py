"""Basic usage: wrap a simple LangGraph node with governance."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from governornode import GovernorNode, GovernancePolicy
from governornode.governor import GovernorExceededError


def main():
    # ── A simple node that appends a thought ────────────────────────────────
    def reasoning_node(state: dict) -> dict:
        thought = f"thought_{state.get('step', 0) + 1}"
        messages = state.get("messages", []) + [thought]
        return {"step": state.get("step", 0) + 1, "messages": messages}

    # ── Wrap it with governance ────────────────────────────────────────────
    policy = GovernancePolicy(max_iterations=5)
    governor = GovernorNode(node=reasoning_node, name="reasoner", policy=policy)

    # ── Run within limits ──────────────────────────────────────────────────
    state = {"step": 0, "messages": []}
    for _ in range(5):
        state = governor(state)
        print(f"  Step {state['step']}: {state['messages'][-1]}")

    # ── Governor prevents overflow ─────────────────────────────────────────
    print("\n  Attempting step 6 (should be blocked)...")
    try:
        state = governor(state)
    except GovernorExceededError as e:
        print(f"  BLOCKED: {e}")

    # ── Inspect the flight recorder ────────────────────────────────────────
    print(f"\n  Flight records captured: {governor.get_recorder().get_record_count()}")
    print(f"  Latest iteration: {governor.iteration}")
    print(f"\n  JSON audit trail:")
    print(governor.get_recorder().to_json())


if __name__ == "__main__":
    main()

"""ReAct loop with GovernorNode — simulates a tool-calling agent with governance.

This demonstrates how GovernorNode prevents runaway tool-calling loops by
limiting iterations and detecting oscillation (same tool call repeated).
"""

import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from governornode import GovernorNode, GovernancePolicy
from governornode.governor import GovernorExceededError


# ── Simulated tool registry ────────────────────────────────────────────────

def search_tool(query: str) -> str:
    """Simulate a search API call."""
    time.sleep(0.01)  # fake latency
    return f"Results for '{query}': [doc1, doc2, doc3]"


def calculator_tool(expr: str) -> str:
    """Simple calculator."""
    try:
        return str(eval(expr))
    except:
        return "Error: invalid expression"


# ── The agent node (ReAct loop step) ──────────────────────────────────────

def react_agent(state: dict) -> dict:
    """A ReAct agent step: decide → tool call → observe."""
    step = state.get("step", 0) + 1
    messages = list(state.get("messages", []))
    tool_call_count = state.get("tool_calls", 0)

    # Simulate agent reasoning
    if step == 1:
        # First step: decide to search
        messages.append("Thought: I need to find information about AI governance.")
        messages.append("Action: search(query='AI governance frameworks 2026')")
        result = search_tool("AI governance frameworks 2026")
        messages.append(f"Observation: {result}")
        tool_call_count += 1
    elif step == 2:
        # Second step: calculate
        messages.append("Thought: Let me calculate the market size.")
        messages.append("Action: calculator(expr='65 + 25 + 10')")
        result = calculator_tool("65 + 25 + 10")
        messages.append(f"Observation: Sum = {result}")
        tool_call_count += 1
    elif step == 3:
        # Third step: final answer
        messages.append("Thought: I have enough information.")
        messages.append("Answer: The simulation predicts 65% Standardized Orchestration, 25% Sovereign Audit, 10% Swarm.")
    else:
        # Oscillation: repeating same action
        messages.append(f"Thought: Step {step} — still thinking...")
        messages.append("Action: search(query='same query again')")
        result = search_tool("same query again")
        messages.append(f"Observation: {result}")
        tool_call_count += 1

    return {
        "step": step,
        "messages": messages,
        "tool_calls": tool_call_count,
    }


def main():
    # ── Tight governance: 4 max iterations, 2 max oscillations ──────────────
    policy = GovernancePolicy(
        max_iterations=4,
        max_oscillations=2,
        entropy_window=5,
    )
    agent = GovernorNode(node=react_agent, name="react_agent", policy=policy)

    state = {"step": 0, "messages": [], "tool_calls": 0}

    print("=" * 60)
    print("GovernorNode — ReAct Loop Simulation")
    print("=" * 60)

    try:
        while True:
            state = agent(state)
            print(f"\n--- Step {state['step']} (tool calls: {state['tool_calls']}) ---")
            # Show last message
            last = state["messages"][-1]
            print(f"  → {last[:80]}...")

    except GovernorExceededError as e:
        print(f"\n{'=' * 60}")
        print(f"GOVERNOR STOPPED LOOP: {e}")
        print(f"{'=' * 60}")

    # ── Audit trail ────────────────────────────────────────────────────────
    print(f"\nTotal steps executed: {agent.iteration}")
    print(f"Total tool calls: {state['tool_calls']}")
    print(f"\nFlight recorder has {agent.get_recorder().get_record_count()} records")

    # Show entropy over the run
    records = agent.get_recorder().get_records()
    entropy_values = [r.entropy for r in records if r.entropy is not None]
    if entropy_values:
        print(f"Entropy range: {min(entropy_values):.3f} — {max(entropy_values):.3f}")

    # ── Save audit trail ───────────────────────────────────────────────────
    audit_path = os.path.join(os.path.dirname(__file__), "..", "flight_recorder_react.json")
    with open(audit_path, "w") as f:
        f.write(agent.get_recorder().to_json())
    print(f"\nAudit trail saved to: {audit_path}")
    print(f"\nInspect with: cat {audit_path} | python -m json.tool")


if __name__ == "__main__":
    main()

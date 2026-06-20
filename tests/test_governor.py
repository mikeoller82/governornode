"""Tests for GovernorNode MVP — RED phase (all tests should fail initially)."""

import json
import os
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from governornode import (
    GovernorNode,
    GovernorStateGraph,
    GovernancePolicy,
    FlightRecord,
    FlightDataRecorder,
    GovernorExceededError,
    LoopGovernor,
    EntropyMonitor,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def simple_node():
    """A node that increments a counter."""
    def node(state: dict) -> dict:
        return {"counter": state.get("counter", 0) + 1}
    return node


@pytest.fixture
def oscillating_node():
    """A node that repeats the same output (oscillation)."""
    def node(state: dict) -> dict:
        return {"value": "same"}
    return node


@pytest.fixture
def identity_node():
    def node(state: dict) -> dict:
        return dict(state)
    return node


@pytest.fixture
def default_policy():
    return GovernancePolicy()


# ── AC-1: GovernorNode passes calls through ───────────────────────────────

class TestGovernorNodePassthrough:
    def test_returns_modified_state(self, simple_node, default_policy):
        gov = GovernorNode(node=simple_node, name="counter", policy=default_policy)
        result = gov({"counter": 0})
        assert result == {"counter": 1}

    def test_identity_passthrough(self, identity_node, default_policy):
        gov = GovernorNode(node=identity_node, name="identity", policy=default_policy)
        result = gov({"x": 1, "y": 2})
        assert result == {"x": 1, "y": 2}


# ── AC-2: Max iteration enforcement ───────────────────────────────────────

class TestMaxIterations:
    def test_raises_after_limit(self, simple_node):
        policy = GovernancePolicy(max_iterations=3)
        gov = GovernorNode(node=simple_node, name="counter", policy=policy)
        gov({"counter": 0})
        gov({"counter": 1})
        gov({"counter": 2})
        with pytest.raises(GovernorExceededError, match="iteration"):
            gov({"counter": 3})

    def test_allows_under_limit(self, simple_node):
        policy = GovernancePolicy(max_iterations=10)
        gov = GovernorNode(node=simple_node, name="counter", policy=policy)
        for i in range(10):
            gov({"counter": i})
        # Should not raise


# ── AC-3: Oscillation detection ───────────────────────────────────────────

class TestOscillation:
    def test_raises_on_oscillation(self, oscillating_node):
        policy = GovernancePolicy(max_oscillations=5)
        gov = GovernorNode(node=oscillating_node, name="osc", policy=policy)
        for _ in range(5):
            gov({"state": "running"})
        with pytest.raises(GovernorExceededError, match="oscillation"):
            gov({"state": "running"})

    def test_no_false_positive_on_varying_output(self, simple_node):
        policy = GovernancePolicy(max_oscillations=5)
        gov = GovernorNode(node=simple_node, name="counter", policy=policy)
        for i in range(10):
            gov({"counter": i})
        # Counter always changes → no oscillation


# ── AC-4: Flight recorder accumulates records ─────────────────────────────

class TestFlightRecorder:
    def test_records_accumulate(self, simple_node, default_policy):
        gov = GovernorNode(node=simple_node, name="counter", policy=default_policy)
        recorder = gov.get_recorder()
        assert len(recorder.get_records()) == 0

        gov({"counter": 0})
        gov({"counter": 1})
        gov({"counter": 2})

        assert len(recorder.get_records()) == 3

    def test_record_has_fields(self, simple_node, default_policy):
        gov = GovernorNode(node=simple_node, name="counter", policy=default_policy)
        gov({"counter": 5})
        record = gov.get_recorder().get_records()[0]
        assert record.node_name == "counter"
        assert record.iteration == 1
        assert isinstance(record.timestamp, float)
        assert record.latency_ms >= 0
        assert record.output_snapshot == {"counter": 6}

    def test_serialize_to_json(self, simple_node, default_policy):
        gov = GovernorNode(node=simple_node, name="counter", policy=default_policy)
        gov({"counter": 0})
        gov({"counter": 1})
        json_str = gov.get_recorder().to_json()
        data = json.loads(json_str)
        assert len(data) == 2
        assert data[0]["node_name"] == "counter"
        assert data[0]["iteration"] == 1

    def test_record_on_failure(self, default_policy):
        def failing_node(state):
            raise ValueError("boom")
        gov = GovernorNode(node=failing_node, name="failing", policy=default_policy)
        with pytest.raises(ValueError):
            gov({"x": 1})
        records = gov.get_recorder().get_records()
        assert len(records) == 1
        assert records[0].error is not None
        assert "boom" in records[0].error


# ── AC-5: GovernorStateGraph works as drop-in ─────────────────────────────

class TestGovernorStateGraph:
    def test_compiles_and_runs(self, simple_node):
        from langgraph.graph import StateGraph
        from typing import TypedDict

        class State(TypedDict):
            counter: int

        graph = GovernorStateGraph(State)
        graph.add_node("increment", simple_node)
        graph.set_entry_point("increment")
        graph.set_finish_point("increment")
        app = graph.compile()
        result = app.invoke({"counter": 0})
        assert result == {"counter": 1}

    def test_governor_enforces_on_graph(self):
        """GovernorStateGraph wraps nodes and enforces limits."""
        from typing import TypedDict

        class State(TypedDict):
            counter: int

        def slow_node(state: dict) -> dict:
            return {"counter": state.get("counter", 0) + 1}

        policy = GovernancePolicy(max_iterations=3)
        graph = GovernorStateGraph(State, default_policy=policy)
        graph.add_node("loop", slow_node)
        graph.set_entry_point("loop")
        graph.set_finish_point("loop")
        app = graph.compile()
        app.invoke({"counter": 0})
        app.invoke({"counter": 0})
        # After reset between invocations, should work fine
        assert True

    def test_governor_raises_in_single_invoke(self):
        """When used in a cycle, governor catches runaway loops."""
        from typing import TypedDict, Literal
        from langgraph.graph import END

        class State(TypedDict):
            counter: int

        def loop_node(state: dict) -> dict:
            c = state.get("counter", 0) + 1
            return {"counter": c}

        def router(state: dict) -> Literal["loop", "__end__"]:
            return "__end__" if state["counter"] >= 5 else "loop"

        policy = GovernancePolicy(max_iterations=3)
        graph = GovernorStateGraph(State, default_policy=policy)
        graph.add_node("loop", loop_node)
        graph.set_entry_point("loop")
        graph.add_conditional_edges("loop", router, {"loop": "loop", "__end__": END})
        app = graph.compile()

        with pytest.raises(GovernorExceededError, match="iteration"):
            app.invoke({"counter": 0})


# ── AC-6: YAML policy loading ─────────────────────────────────────────────

class TestPolicyLoading:
    def test_from_dict(self):
        policy = GovernancePolicy(max_iterations=10, max_oscillations=3)
        assert policy.max_iterations == 10
        assert policy.max_oscillations == 3

    def test_from_yaml(self):
        yaml_content = """
max_iterations: 7
max_oscillations: 2
entropy_window: 5
entropy_threshold: 0.2
record_io: true
halt_on_violation: true
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name
        try:
            policy = GovernancePolicy.from_yaml(yaml_path)
            assert policy.max_iterations == 7
            assert policy.max_oscillations == 2
            assert policy.entropy_window == 5
            assert policy.entropy_threshold == 0.2
        finally:
            os.unlink(yaml_path)

    def test_default_values(self):
        policy = GovernancePolicy()
        assert policy.max_iterations == 25
        assert policy.max_oscillations == 5
        assert policy.entropy_window == 10
        assert policy.entropy_threshold == 0.1
        assert policy.record_io is True
        assert policy.halt_on_violation is True


# ── AC-7 & AC-8: Entropy monitoring ───────────────────────────────────────

class TestEntropyMonitor:
    def test_high_entropy(self):
        """Many unique outputs → high entropy."""
        monitor = EntropyMonitor(window=10)
        # Different outputs produce high entropy
        for i in range(10):
            monitor.record({"value": i})
        entropy = monitor.get_entropy()
        assert entropy > 0.5

    def test_low_entropy(self):
        """Same output repeated → entropy approaches 0."""
        monitor = EntropyMonitor(window=10)
        for _ in range(10):
            monitor.record({"value": "A"})
        entropy = monitor.get_entropy()
        assert entropy < 0.01

    def test_mixed_entropy(self):
        """Two alternating outputs → moderate entropy."""
        monitor = EntropyMonitor(window=10)
        for i in range(10):
            monitor.record({"value": "A" if i % 2 == 0 else "B"})
        entropy = monitor.get_entropy()
        assert 0.5 < entropy < 1.1  # log2(2) = 1.0 max for 2 symbols


# ── EC-1: Record on exception ─────────────────────────────────────────────

class TestEdgeCases:
    def test_multiple_governors_independent(self, simple_node, identity_node):
        policy = GovernancePolicy(max_iterations=3)
        gov1 = GovernorNode(node=simple_node, name="counter", policy=policy)
        gov2 = GovernorNode(node=identity_node, name="pass", policy=policy)
        gov1({"counter": 0})
        gov1({"counter": 1})
        gov1({"counter": 2})
        with pytest.raises(GovernorExceededError):
            gov1({"counter": 3})
        # gov2 still works independently
        result = gov2({"x": 1})
        assert result == {"x": 1}

    def test_reset_clears_counters(self, simple_node):
        policy = GovernancePolicy(max_iterations=3)
        gov = GovernorNode(node=simple_node, name="counter", policy=policy)
        gov({"counter": 0})
        gov({"counter": 1})
        gov.reset()
        assert len(gov.get_recorder().get_records()) == 0  # recorder cleared
        gov({"counter": 0})  # Should work after reset
        assert gov.iteration == 1  # counter reset to 1
        assert len(gov.get_recorder().get_records()) == 1  # new call recorded

    def test_halt_on_violation_false(self, simple_node):
        policy = GovernancePolicy(max_iterations=3, halt_on_violation=False)
        gov = GovernorNode(node=simple_node, name="counter", policy=policy)
        gov({"counter": 0})
        gov({"counter": 1})
        gov({"counter": 2})
        # Should not raise on 4th call with halt_on_violation=False
        result = gov({"counter": 3})
        assert result is not None


# ── NFR-1: Performance overhead ───────────────────────────────────────────

class TestPerformance:
    def test_overhead_under_5ms(self, identity_node):
        policy = GovernancePolicy(record_io=False, max_iterations=10000, max_oscillations=10000)
        gov = GovernorNode(node=identity_node, name="fast", policy=policy)

        # Warmup
        for _ in range(100):
            gov({"x": 1})

        # Measure
        start = time.perf_counter()
        for _ in range(1000):
            gov({"x": 1})
        elapsed = time.perf_counter() - start
        per_call_ms = (elapsed / 1000) * 1000
        assert per_call_ms < 5, f"Overhead {per_call_ms:.3f}ms exceeds 5ms limit"

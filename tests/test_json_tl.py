"""Tests for json_tl.py — JSON-TL validator and converter.

Tests cover:
- Envelope validation (required fields, UUIDs, version)
- Event validation (span_type, iteration, status, timestamps)
- Error object validation
- Converter: FlightRecords → JSON-TL
- Edge cases: empty traces, missing fields, invalid types
"""

import json
import os
import sys
import tempfile
import uuid

# Ensure the parent directory is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from json_tl import (
    validate_trace,
    convert_flight_records,
    VALID_SPAN_TYPES,
    VALID_STATUSES,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


def make_valid_event(overrides: dict | None = None) -> dict:
    """Create a minimal valid trace event."""
    event = {
        "event_id": str(uuid.uuid4()),
        "span_type": "agent",
        "timestamp": "2026-06-19T14:30:00.000Z",
        "iteration": 1,
        "status": "ok",
    }
    if overrides:
        event.update(overrides)
    return event


def make_valid_envelope(overrides: dict | None = None, event_count: int = 1) -> dict:
    """Create a minimal valid trace envelope."""
    env = {
        "json_tl_version": "0.1.0",
        "trace_id": str(uuid.uuid4()),
        "session_id": str(uuid.uuid4()),
        "events": [make_valid_event() for _ in range(event_count)],
    }
    if overrides:
        env.update(overrides)
    return env


# ── Envelope Validation Tests ───────────────────────────────────────────────


class TestEnvelopeValidation:
    def test_valid_envelope_passes(self):
        """AC-1: A valid envelope with required fields passes validation."""
        env = make_valid_envelope()
        errors = validate_trace(env)
        assert len(errors) == 0, f"Expected 0 errors, got: {errors}"

    def test_missing_json_tl_version(self):
        """FR-5: Missing json_tl_version fails."""
        env = make_valid_envelope()
        del env["json_tl_version"]
        errors = validate_trace(env)
        assert any("json_tl_version" in e for e in errors), errors

    def test_missing_trace_id(self):
        """EC-2: Missing trace_id fails."""
        env = make_valid_envelope()
        del env["trace_id"]
        errors = validate_trace(env)
        assert any("trace_id" in e for e in errors), errors

    def test_missing_session_id(self):
        """FR-5: Missing session_id fails."""
        env = make_valid_envelope()
        del env["session_id"]
        errors = validate_trace(env)
        assert any("session_id" in e for e in errors), errors

    def test_missing_events_array(self):
        """FR-5: Missing events fails."""
        env = make_valid_envelope()
        del env["events"]
        errors = validate_trace(env)
        assert any("events" in e for e in errors), errors

    def test_empty_trace_is_valid(self):
        """EC-1: Empty events array is valid."""
        env = make_valid_envelope(event_count=0)
        errors = validate_trace(env)
        assert len(errors) == 0, f"Expected 0 errors, got: {errors}"

    def test_invalid_trace_id_format(self):
        """EC-2: Non-UUID trace_id fails."""
        env = make_valid_envelope()
        env["trace_id"] = "not-a-uuid"
        errors = validate_trace(env)
        assert any("trace_id" in e and "UUID" in e for e in errors), errors

    def test_invalid_version_format(self):
        """Version must be semver-like."""
        env = make_valid_envelope()
        env["json_tl_version"] = "abc"
        errors = validate_trace(env)
        assert any("json_tl_version" in e for e in errors), errors

    def test_parent_trace_id_valid(self):
        """FR-9: parent_trace_id must be valid UUID if present."""
        env = make_valid_envelope()
        env["parent_trace_id"] = "not-a-uuid"
        errors = validate_trace(env)
        assert any("parent_trace_id" in e for e in errors), errors

    def test_parent_trace_id_null(self):
        """Null parent_trace_id is allowed."""
        env = make_valid_envelope()
        env["parent_trace_id"] = None
        errors = validate_trace(env)
        assert len(errors) == 0, f"Expected 0 errors, got: {errors}"

    def test_policy_snapshot_types(self):
        """Policy snapshot fields must be correct types."""
        env = make_valid_envelope()
        env["policy_snapshot"] = {
            "max_iterations": "ten",  # wrong type
            "max_oscillations": -1,
        }
        errors = validate_trace(env)
        assert len(errors) > 0, "Expected policy type errors"


# ── Event Validation Tests ──────────────────────────────────────────────────


class TestEventValidation:
    def test_valid_event_passes(self):
        """AC-1: A valid event passes validation."""
        event = make_valid_event()
        errors = validate_trace({"json_tl_version": "0.1.0", "trace_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()), "events": [event]})
        assert len(errors) == 0, f"Expected 0 errors, got: {errors}"

    def test_missing_event_id(self):
        """Event must have event_id."""
        event = make_valid_event({"event_id": None})
        del event["event_id"]
        errors = validate_trace({"json_tl_version": "0.1.0", "trace_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()), "events": [event]})
        assert any("event_id" in e for e in errors), errors

    def test_invalid_span_type(self):
        """EC-3: Invalid span_type is rejected."""
        event = make_valid_event({"span_type": "invalid_type"})
        errors = validate_trace({"json_tl_version": "0.1.0", "trace_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()), "events": [event]})
        assert any("span_type" in e for e in errors), errors

    def test_all_valid_span_types(self):
        """All enum values for span_type pass."""
        for st in VALID_SPAN_TYPES:
            event = make_valid_event({"span_type": st})
            errors = validate_trace({"json_tl_version": "0.1.0", "trace_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()), "events": [event]})
            assert len(errors) == 0, f"Failed for span_type={st}: {errors}"

    def test_all_valid_statuses(self):
        """All enum values for status pass."""
        for st in VALID_STATUSES:
            event = make_valid_event({"status": st})
            errors = validate_trace({"json_tl_version": "0.1.0", "trace_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()), "events": [event]})
            assert len(errors) == 0, f"Failed for status={st}: {errors}"

    def test_negative_iteration(self):
        """EC-4: Negative iteration is rejected."""
        event = make_valid_event({"iteration": -1})
        errors = validate_trace({"json_tl_version": "0.1.0", "trace_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()), "events": [event]})
        assert any("iteration" in e for e in errors), errors

    def test_non_utc_timestamp(self):
        """Timestamp must end with Z."""
        event = make_valid_event({"timestamp": "2026-06-19T14:30:00.000+00:00"})
        errors = validate_trace({"json_tl_version": "0.1.0", "trace_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()), "events": [event]})
        assert any("timestamp" in e and "Z" in e for e in errors), errors

    def test_duplicate_event_ids(self):
        """Duplicate event_id within same envelope is caught."""
        shared_id = str(uuid.uuid4())
        env = make_valid_envelope(event_count=0)
        env["events"] = [
            make_valid_event({"event_id": shared_id}),
            make_valid_event({"event_id": shared_id}),
        ]
        errors = validate_trace(env)
        assert any("Duplicate" in e for e in errors), errors


# ── Error Object Tests ──────────────────────────────────────────────────────


class TestErrorObject:
    def test_error_present_when_status_error(self):
        """AC-6: Error object has type and message when status is error."""
        event = make_valid_event({
            "status": "error",
            "error": {"type": "ToolTimeoutError", "message": "Tool timed out"},
        })
        errors = validate_trace({"json_tl_version": "0.1.0", "trace_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()), "events": [event]})
        assert len(errors) == 0, f"Expected 0 errors, got: {errors}"

    def test_error_missing_type(self):
        """Error object without type field fails."""
        event = make_valid_event({
            "status": "error",
            "error": {"message": "Something broke"},
        })
        errors = validate_trace({"json_tl_version": "0.1.0", "trace_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()), "events": [event]})
        assert any("type" in e for e in errors), errors

    def test_error_missing_message(self):
        """Error object without message field fails."""
        event = make_valid_event({
            "status": "error",
            "error": {"type": "GenericError"},
        })
        errors = validate_trace({"json_tl_version": "0.1.0", "trace_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()), "events": [event]})
        assert any("message" in e for e in errors), errors

    def test_error_not_object(self):
        """Error must be an object or null, not a string."""
        event = make_valid_event({
            "status": "error",
            "error": "something broke",
        })
        errors = validate_trace({"json_tl_version": "0.1.0", "trace_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()), "events": [event]})
        assert any("error" in e for e in errors), errors


# ── Converter Tests ─────────────────────────────────────────────────────────


class TestConverter:
    def test_empty_records(self):
        """Empty flight records produce a valid envelope with no events."""
        trace = convert_flight_records([])
        assert trace["json_tl_version"] == "0.1.0"
        assert trace["events"] == []
        assert "trace_id" in trace
        assert "session_id" in trace

    def test_single_record(self):
        """A single flight record converts to one trace event."""
        records = [
            {
                "node_name": "test_node",
                "timestamp": 1781873451.212,
                "iteration": 1,
                "latency_ms": 10.5,
                "entropy": 0.5,
                "oscillation_detected": False,
                "error": None,
                "input_snapshot": {"query": "test"},
                "output_snapshot": {"result": "done"},
            }
        ]
        trace = convert_flight_records(records, agent_id="test-agent")
        assert len(trace["events"]) == 1
        ev = trace["events"][0]
        assert ev["span_name"] == "test_node"
        assert ev["iteration"] == 1
        assert ev["entropy"] == 0.5
        assert ev["status"] == "ok"
        assert ev["input_snapshot"] == {"query": "test"}
        assert "event_id" in ev
        assert trace["agent_id"] == "test-agent"

    def test_record_with_error(self):
        """Record with error produces a governor_halt event with error object."""
        records = [
            {
                "node_name": "agent",
                "timestamp": 1781873451.212,
                "iteration": 5,
                "latency_ms": 0.01,
                "entropy": None,
                "oscillation_detected": True,
                "error": "Node exceeded max_iterations=4 (iteration=5)",
                "input_snapshot": None,
                "output_snapshot": None,
            }
        ]
        trace = convert_flight_records(records)
        ev = trace["events"][0]
        assert ev["status"] == "governor_halt"
        assert ev["error"]["type"] == "GovernorExceededError"
        assert "max_iterations" in ev["error"]["message"]

    def test_multiple_records(self):
        """Multiple records produce ordered events."""
        records = [
            {"node_name": "step1", "timestamp": 100.0, "iteration": 1, "latency_ms": 1.0, "entropy": 0.0, "oscillation_detected": False, "error": None, "input_snapshot": None, "output_snapshot": None},
            {"node_name": "step2", "timestamp": 200.0, "iteration": 2, "latency_ms": 2.0, "entropy": 1.0, "oscillation_detected": False, "error": None, "input_snapshot": None, "output_snapshot": None},
        ]
        trace = convert_flight_records(records)
        assert len(trace["events"]) == 2
        assert trace["events"][0]["span_name"] == "step1"
        assert trace["events"][1]["span_name"] == "step2"

    def test_converter_produces_valid_trace(self):
        """Converted trace passes validation."""
        records = [
            {"node_name": "test", "timestamp": 1781873451.0, "iteration": 1, "latency_ms": 1.0, "entropy": 0.5, "oscillation_detected": False, "error": None, "input_snapshot": None, "output_snapshot": None},
            {"node_name": "test", "timestamp": 1781873452.0, "iteration": 2, "latency_ms": 2.0, "entropy": 1.0, "oscillation_detected": False, "error": None, "input_snapshot": None, "output_snapshot": None},
        ]
        trace = convert_flight_records(records, policy_snapshot={"max_iterations": 10, "halt_on_violation": True})
        errors = validate_trace(trace)
        assert len(errors) == 0, f"Converted trace has validation errors: {errors}"
        assert trace["policy_snapshot"] == {"max_iterations": 10, "halt_on_violation": True}


# ── Edge Case Tests ─────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_not_an_object(self):
        """Root must be an object."""
        errors = validate_trace([])
        assert len(errors) > 0

    def test_events_not_array(self):
        """Events field must be an array."""
        env = make_valid_envelope()
        env["events"] = "not-an-array"
        errors = validate_trace(env)
        assert any("events" in e for e in errors), errors

    def test_event_not_an_object(self):
        """Each event must be an object."""
        env = make_valid_envelope(event_count=0)
        env["events"] = ["string-event"]
        errors = validate_trace(env)
        assert len(errors) > 0

    def test_additional_fields_allowed(self):
        """AC-9: Custom metadata fields must survive with no errors."""
        event = make_valid_event({
            "metadata": {"temperature": 0.0, "model": "gpt-4", "custom_field": "anything"},
        })
        errors = validate_trace({"json_tl_version": "0.1.0", "trace_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()), "events": [event]})
        assert len(errors) == 0, f"Expected 0 errors, got: {errors}"

    def test_many_events_validation(self):
        """Validation is fast for 100 events (NFR-2)."""
        env = make_valid_envelope(event_count=0)
        env["events"] = [make_valid_event() for _ in range(100)]
        import time
        start = time.perf_counter()
        errors = validate_trace(env)
        elapsed = time.perf_counter() - start
        assert len(errors) == 0
        assert elapsed < 0.1, f"Validation took {elapsed*1000:.1f}ms (NFR-2: <100ms)"

    def test_large_snapshot_allowed(self):
        """EC-7: Large snapshots are allowed by schema."""
        large_data = {"data": "x" * 10_000}
        event = make_valid_event({
            "input_snapshot": large_data,
            "output_snapshot": large_data,
        })
        errors = validate_trace({"json_tl_version": "0.1.0", "trace_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()), "events": [event]})
        assert len(errors) == 0, f"Expected 0 errors, got: {errors}"

    def test_max_depth_circular(self):
        """EC-6: Circular parent references pass validation (consumer concern)."""
        env = make_valid_envelope(event_count=0)
        e1 = make_valid_event({"event_id": "evt-001", "parent_event_id": "evt-002"})
        e2 = make_valid_event({"event_id": "evt-002", "parent_event_id": "evt-001"})
        env["events"] = [e1, e2]
        errors = validate_trace(env)
        # Circular reference is syntactically valid — consumers handle it
        assert len(errors) == 0, f"Expected 0 errors, got: {errors}"

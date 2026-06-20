"""JSON-TL (JSON Trace Language) reference implementation.

Validator and converter for the OpenTelemetry-for-AI-agents trace format.

Usage:
    # Validate a trace file
    python json_tl.py validate path/to/trace.json

    # Convert a FlightDataRecorder JSON export to JSON-TL
    python json_tl.py convert path/to/flight_records.json --output trace.json

    # Validate with verbose output
    python json_tl.py validate path/to/trace.json --verbose
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

# Path to the canonical schema file
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "json-tl-schema.json")

# ── Span Type Enum ──────────────────────────────────────────────────────────

VALID_SPAN_TYPES = frozenset({"agent", "tool", "llm", "observation", "router", "governor"})
VALID_STATUSES = frozenset({"ok", "error", "governor_halt", "timeout", "cancelled"})

# ── Validation Engine ───────────────────────────────────────────────────────


class JsonTLValidationError(Exception):
    """A validation error with a specific message and path."""

    def __init__(self, message: str, path: str = "$"):
        self.path = path
        super().__init__(f"[{path}] {message}")


def validate_trace(trace: dict, schema: dict | None = None) -> list[str]:
    """Validate a JSON-TL trace envelope against the schema.

    Returns a list of error messages (empty = valid).
    """
    errors: list[str] = []

    def _err(msg: str, path: str = "$"):
        errors.append(f"[{path}] {msg}")

    # ── Envelope required fields ────────────────────────────────────────
    for field in ("json_tl_version", "trace_id", "session_id", "events"):
        if field not in trace:
            _err(f"Missing required field: '{field}'", "$")

    if "json_tl_version" in trace:
        ver = trace["json_tl_version"]
        if not isinstance(ver, str) or not ver[0].isdigit():
            _err(f"json_tl_version must be a semver string, got {type(ver).__name__}", "$.json_tl_version")

    # ── UUID validation ─────────────────────────────────────────────────
    if "trace_id" in trace:
        _validate_uuid(trace["trace_id"], "$.trace_id", errors)
    if "session_id" in trace:
        _validate_uuid(trace["session_id"], "$.session_id", errors)
    if "parent_trace_id" in trace and trace["parent_trace_id"] is not None:
        _validate_uuid(trace["parent_trace_id"], "$.parent_trace_id", errors)

    # ── Policy snapshot ─────────────────────────────────────────────────
    if "policy_snapshot" in trace and trace["policy_snapshot"] is not None:
        ps = trace["policy_snapshot"]
        if not isinstance(ps, dict):
            _err("policy_snapshot must be an object or null", "$.policy_snapshot")
        else:
            for key in ("max_iterations", "max_oscillations", "entropy_window"):
                if key in ps and (not isinstance(ps[key], int) or ps[key] < 0):
                    _err(f"{key} must be a non-negative integer", f"$.policy_snapshot.{key}")

    # ── Events ──────────────────────────────────────────────────────────
    if "events" in trace:
        if not isinstance(trace["events"], list):
            _err("events must be an array", "$.events")
        else:
            seen_ids: set = set()
            for i, event in enumerate(trace["events"]):
                path = f"$.events[{i}]"
                _validate_event(event, path, errors, seen_ids)

    return errors


def _validate_uuid(value: Any, path: str, errors: list):
    """Validate a UUID string."""
    if not isinstance(value, str):
        errors.append(f"[{path}] Must be a string, got {type(value).__name__}")
        return
    try:
        uuid.UUID(value)
    except ValueError:
        errors.append(f"[{path}] Invalid UUID: '{value}'")


def _validate_event(event: dict, path: str, errors: list, seen_ids: set):
    """Validate a single trace event."""
    if not isinstance(event, dict):
        errors.append(f"[{path}] Must be an object, got {type(event).__name__}")
        return

    # Required fields
    for field in ("event_id", "span_type", "timestamp", "iteration", "status"):
        if field not in event:
            errors.append(f"[{path}] Missing required field: '{field}'")

    # event_id
    if "event_id" in event:
        eid = event["event_id"]
        if eid in seen_ids:
            errors.append(f"[{path}] Duplicate event_id: '{eid}'")
        seen_ids.add(eid)

    # span_type
    if "span_type" in event and event["span_type"] not in VALID_SPAN_TYPES:
        errors.append(
            f"[{path}.span_type] Invalid span_type '{event['span_type']}'. "
            f"Must be one of: {', '.join(sorted(VALID_SPAN_TYPES))}"
        )

    # timestamp
    if "timestamp" in event:
        ts = event["timestamp"]
        if not isinstance(ts, str):
            errors.append(f"[{path}.timestamp] Must be a string")
        elif not ts.endswith("Z"):
            errors.append(f"[{path}.timestamp] Must be UTC (ending with Z)")

    # iteration
    if "iteration" in event:
        it = event["iteration"]
        if not isinstance(it, int) or it < 0:
            errors.append(f"[{path}.iteration] Must be a non-negative integer")

    # cumulative_iterations
    if "cumulative_iterations" in event and event["cumulative_iterations"] is not None:
        ci = event["cumulative_iterations"]
        if not isinstance(ci, int) or ci < 0:
            errors.append(f"[{path}.cumulative_iterations] Must be a non-negative integer or null")

    # entropy
    if "entropy" in event and event["entropy"] is not None:
        ent = event["entropy"]
        if not isinstance(ent, (int, float)) or ent < 0:
            errors.append(f"[{path}.entropy] Must be a non-negative number or null")

    # status
    if "status" in event and event["status"] not in VALID_STATUSES:
        errors.append(
            f"[{path}.status] Invalid status '{event['status']}'. "
            f"Must be one of: {', '.join(sorted(VALID_STATUSES))}"
        )

    # error
    if "error" in event and event["error"] is not None:
        err = event["error"]
        if not isinstance(err, dict):
            errors.append(f"[{path}.error] Must be an object or null")
        else:
            for ef in ("type", "message"):
                if ef not in err:
                    errors.append(f"[{path}.error] Missing required field: '{ef}'")

    # duration_ms
    if "duration_ms" in event and event["duration_ms"] is not None:
        d = event["duration_ms"]
        if not isinstance(d, (int, float)) or d < 0:
            errors.append(f"[{path}.duration_ms] Must be a non-negative number or null")


# ── Converter: FlightDataRecorder → JSON-TL ────────────────────────────────


def convert_flight_records(
    records: list[dict],
    agent_id: str = "governornode-agent",
    agent_version: str = "",
    policy_snapshot: dict | None = None,
) -> dict:
    """Convert GovernorNode FlightDataRecorder JSON to a JSON-TL trace envelope.

    Args:
        records: List of FlightRecord dicts from the recorder.
        agent_id: Identifier for the agent.
        agent_version: Git SHA or version string.
        policy_snapshot: Governance policy config at time of execution.

    Returns:
        A JSON-TL TraceEnvelope dict.
    """
    if not records:
        envelope = {
            "json_tl_version": "0.1.0",
            "trace_id": str(uuid.uuid4()),
            "session_id": str(uuid.uuid4()),
            "events": [],
        }
        if agent_id:
            envelope["agent_id"] = agent_id
        if agent_version:
            envelope["agent_version"] = agent_version
        if policy_snapshot:
            envelope["policy_snapshot"] = policy_snapshot
        return envelope

    trace_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    events = []
    for i, rec in enumerate(records):
        # Parse timestamp from FlightRecord format (Unix timestamp)
        ts_unix = rec.get("timestamp", 0)
        try:
            dt = datetime.fromtimestamp(ts_unix, tz=timezone.utc)
            iso_ts = dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond:06d}"[:3] + "Z"
        except (OSError, ValueError):
            iso_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        event = {
            "event_id": str(uuid.uuid4()),
            "parent_event_id": None,
            "span_type": "agent" if not rec.get("error") else "governor",
            "span_name": rec.get("node_name", "unknown"),
            "timestamp": iso_ts,
            "duration_ms": rec.get("latency_ms", 0.0),
            "iteration": rec.get("iteration", i + 1),
            "cumulative_iterations": rec.get("iteration", i + 1),
            "entropy": rec.get("entropy"),
            "oscillation_detected": bool(rec.get("oscillation_detected", False)),
            "status": "error" if rec.get("error") else "ok",
            "input_snapshot": rec.get("input_snapshot"),
            "output_snapshot": rec.get("output_snapshot"),
            "error": None,
            "policy_snapshot": None,
            "metadata": {},
        }

        if rec.get("error"):
            event["error"] = {
                "type": "GovernorExceededError",
                "message": str(rec["error"]),
                "code": 1001,
            }
            event["status"] = "governor_halt"

        events.append(event)

    envelope = {
        "json_tl_version": "0.1.0",
        "trace_id": trace_id,
        "session_id": session_id,
        "events": events,
    }

    if agent_id:
        envelope["agent_id"] = agent_id
    if agent_version:
        envelope["agent_version"] = agent_version
    if policy_snapshot:
        envelope["policy_snapshot"] = policy_snapshot

    envelope["metadata"] = {
        "framework": "governornode-mvp",
        "event_count": len(events),
        "converted_by": "json_tl.py",
        "converted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    }

    return envelope


# ── CLI ─────────────────────────────────────────────────────────────────────


def _load_json(path: str) -> dict | list:
    with open(path) as f:
        return json.load(f)


def cmd_validate(args: list[str]) -> int:
    """Validate a JSON file as JSON-TL."""
    if not args:
        print("Usage: json_tl.py validate <path/to/trace.json> [--verbose]")
        return 1

    path = args[0]
    verbose = "--verbose" in args

    if not os.path.exists(path):
        print(f"File not found: {path}")
        return 1

    try:
        trace = _load_json(path)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading JSON: {e}")
        return 1

    if not isinstance(trace, dict):
        print("Error: JSON root must be an object")
        return 1

    errors = validate_trace(trace)

    if not errors:
        event_count = len(trace.get("events", []))
        print(f"✓ VALID — {event_count} events, {len(errors)} errors")
        if verbose:
            print(f"  trace_id: {trace.get('trace_id', 'N/A')}")
            print(f"  session_id: {trace.get('session_id', 'N/A')}")
            print(f"  version: {trace.get('json_tl_version', 'N/A')}")
            if "agent_id" in trace:
                print(f"  agent: {trace['agent_id']}")
        return 0
    else:
        print(f"✗ INVALID — {len(errors)} error(s):")
        for err in errors:
            print(f"  • {err}")
        return 1


def cmd_convert(args: list[str]) -> int:
    """Convert FlightDataRecorder JSON export to JSON-TL."""
    if not args:
        print("Usage: json_tl.py convert <path/to/flight_records.json> [--output trace.json]")
        return 1

    path = args[0]
    output_path = None
    if "--output" in args:
        idx = args.index("--output")
        if idx + 1 < len(args):
            output_path = args[idx + 1]

    if not os.path.exists(path):
        print(f"File not found: {path}")
        return 1

    try:
        records = _load_json(path)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading JSON: {e}")
        return 1

    if isinstance(records, dict):
        # Maybe it's a list wrapped in a key?
        for possible_key in ("records", "data", "events", "items"):
            if possible_key in records and isinstance(records[possible_key], list):
                records = records[possible_key]
                break

    if not isinstance(records, list):
        print("Error: Flight records must be a JSON array or a dict with a list field")
        return 1

    trace = convert_flight_records(records, agent_id="governornode-agent")

    output = output_path or os.path.splitext(path)[0] + "_json-tl.json"
    with open(output, "w") as f:
        json.dump(trace, f, indent=2)

    print(f"✓ Converted {len(records)} records → JSON-TL trace")
    print(f"  Output: {output}")
    print(f"  trace_id: {trace['trace_id']}")

    # Auto-validate
    errors = validate_trace(trace)
    if errors:
        print(f"  ⚠ {len(errors)} validation warning(s):")
        for err in errors[:3]:
            print(f"    • {err}")
    else:
        print(f"  ✓ Valid JSON-TL")

    return 0


def main():
    if len(sys.argv) < 2:
        print("JSON-TL: OpenTrace for AI Agents")
        print()
        print("Usage:")
        print("  python json_tl.py validate <file.json>       Validate a JSON-TL trace")
        print("  python json_tl.py convert <records.json>     Convert FlightRecords to JSON-TL")
        print()
        print("Options:")
        print("  --verbose              Verbose validation output")
        print("  --output <path>        Output path for conversion")
        return 1

    cmd = sys.argv[1]
    rest = sys.argv[2:]

    if cmd == "validate":
        return cmd_validate(rest)
    elif cmd == "convert":
        return cmd_convert(rest)
    else:
        print(f"Unknown command: {cmd}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

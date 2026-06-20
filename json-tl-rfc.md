# JSON-TL (JSON Trace Language) Schema RFC
## Open Standard for AI Agent Execution Tracing

| Field | Value |
|-------|-------|
| **Status** | `DRAFT v0.1` |
| **Author** | Hermes Agent O / AIToolInsider |
| **Date** | 2026-06-19 |
| **License** | Apache 2.0 |
| **Repository** | `github.com/aitoolinsider/json-tl-spec` (planned) |

---

## 1. Context

### The Problem

AI agent execution is a black box. When an agent makes a wrong decision, overspends on API calls, or violates a compliance boundary, there is no standardized way to answer:

- **What happened?** What sequence of LLM calls, tool invocations, and observations led to this output?
- **Why did it happen?** What was the input state at each decision boundary?
- **Who is accountable?** Which agent version, policy, and configuration was active?
- **How do we prove compliance?** Can we replay the trace for an auditor?

Current approaches are fragmented:
- LangGraph captures raw state but has no standardized trace export
- OpenTelemetry captures infrastructure observability but not agent-level semantics (thoughts, tool calls, governance decisions)
- LLM providers each have their own logging format
- No standard exists for *governance metadata* — iteration counts, entropy, oscillation flags, policy snapshots

### The Opportunity

The industry shift to governed orchestration (2027-2029 time horizon) demands an open, portable trace format. JSON-TL fills the same role for AI agents that OpenTelemetry fills for distributed systems: **a vendor-neutral, schema-defined standard for capturing, exporting, and auditing execution traces.**

### Design Principles

1. **Open-first.** Apache 2.0 license. No vendor lock-in. Community governance.
2. **Governance-native.** Iteration counts, entropy, oscillation detection, policy snapshots are first-class fields — not afterthoughts.
3. **Trace-compatible.** JSON-TL spans can be converted to OpenTelemetry or stored in any observability backend.
4. **Human-readable AND machine-parseable.** JSON Schema v4 validation. Can be piped to `jq`, loaded into Grafana, or served to a SOC2 auditor.
5. **Minimal overhead.** A single trace event is < 1 KB. No mandatory external dependencies.

---

## 2. Functional Requirements

### FR-1: Event Model

The schema MUST define a top-level `TraceEvent` object that captures a single atomic execution step in an agent loop.

### FR-2: Span Hierarchy

Events MUST support parent-child relationships to model nested execution (e.g., Agent → Tool → LLM Call → Observation → Agent).

### FR-3: Governance Metadata

Every event MUST include iteration number, cumulative iteration count, and MAY include entropy and oscillation flag.

### FR-4: Policy Snapshots

The schema MUST support embedding the active governance policy configuration at the time of execution for audit trail completeness.

### FR-5: Transport Envelope

The schema MUST define a `TraceEnvelope` wrapper with version, trace_id, agent_id, session_id, timestamp, and event array.

### FR-6: Error Recording

Events MUST support recording errors at any span level without breaking the trace structure.

### FR-7: Input/Output Capture

Events MUST support optional input_snapshot and output_snapshot fields at every level.

### FR-8: Compliance Signing

The envelope SHOULD support an optional `signature` field for integrity verification (HMAC or JWS).

### FR-9: Context Propagation

The trace_id MUST propagate across agent restarts, sub-agents, and distributed node execution.

### FR-10: Extensibility

The schema MUST support arbitrary custom metadata via a `metadata` map on every event.

---

## 3. Non-Functional Requirements

| NFR | Metric | Threshold |
|-----|--------|-----------|
| NFR-1 | Event size | < 1 KB for a typical event (no payload truncation) |
| NFR-2 | Validation speed | Schema validation for 1000 events < 100ms |
| NFR-3 | Serialization | Round-trip lossless through JSON.parse/stringify |
| NFR-4 | Backward compatibility | New fields MUST NOT break existing consumers (additive only) |
| NFR-5 | Encoding | Strict UTF-8. All text fields MUST be valid Unicode. |
| NFR-6 | Schema adherence | JSON Schema v4 (draft-04) compliant |

---

## 4. Schema Specification

### 4.1 TraceEnvelope

The top-level container. Always the root of a JSON-TL payload.

```json
{
  "json_tl_version": "0.1.0",
  "trace_id": "uuid-v7-string",
  "agent_id": "string",
  "agent_version": "string",
  "session_id": "uuid-v7-string",
  "parent_trace_id": "string | null",
  "policy_snapshot": { },
  "events": [ "TraceEvent..." ],
  "metadata": { },
  "signature": "string | null"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `json_tl_version` | `string` | **MUST** | Semver of the JSON-TL spec this payload conforms to |
| `trace_id` | `string` | **MUST** | UUIDv7 identifying the entire trace run |
| `agent_id` | `string` | **MUST** | Identifier for the agent executable/configuration |
| `agent_version` | `string` | **SHOULD** | Git SHA or semver of the agent code |
| `session_id` | `string` | **MUST** | UUIDv7 identifying this specific run session |
| `parent_trace_id` | `string | null` | **SHOULD** | Set when this is a sub-agent trace, linking to parent |
| `policy_snapshot` | `object | null` | **SHOULD** | Serialized governance policy active during this trace |
| `events` | `array[TraceEvent]` | **MUST** | Ordered list of trace events |
| `metadata` | `object` | **MAY** | Arbitrary key-value metadata |
| `signature` | `string | null` | **MAY** | HMAC-SHA256 or JWS signature over the canonical payload |

### 4.2 TraceEvent

An atomic execution step.

```json
{
  "event_id": "uuid-v7-string",
  "parent_event_id": "string | null",
  "span_type": "string",
  "span_name": "string",
  "timestamp": "ISO-8601-string",
  "duration_ms": "number",
  "iteration": "int",
  "cumulative_iterations": "int",
  "entropy": "float | null",
  "oscillation_detected": "boolean",
  "status": "string",
  "input_snapshot": "object | null",
  "output_snapshot": "object | null",
  "error": "object | null",
  "policy_snapshot": "object | null",
  "metadata": "object | null"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `event_id` | `string` | **MUST** | UUIDv7 |
| `parent_event_id` | `string | null` | **SHOULD** | Links to the parent event in nested execution |
| `span_type` | `string` | **MUST** | Fixed enum: `agent`, `tool`, `llm`, `observation`, `router`, `governor` |
| `span_name` | `string` | **SHOULD** | Human-readable label (e.g., "search_web", "reasoning_step") |
| `timestamp` | `string` | **MUST** | ISO 8601 with millisecond precision (e.g., `2026-06-19T14:30:00.123Z`) |
| `duration_ms` | `number` | **SHOULD** | Wall-clock duration of this span in milliseconds |
| `iteration` | `int` | **MUST** | Iteration number of this node within the agent loop (1-indexed) |
| `cumulative_iterations` | `int` | **SHOULD** | Total iterations across all nodes in the trace so far |
| `entropy` | `float | null` | **SHOULD** | Plan entropy at this point (Shannon entropy over last N outputs). `null` if not computed |
| `oscillation_detected` | `boolean` | **MAY** | `true` if this step was flagged as an oscillation repeat |
| `status` | `string` | **MUST** | `ok`, `error`, `governor_halt`, `timeout`, or `cancelled` |
| `input_snapshot` | `object | null` | **MAY** | Full input state at event start. Omitted for size sensitivity. |
| `output_snapshot` | `object | null` | **MAY** | Full output state at event completion. |
| `error` | `object | null` | **SHOULD** | Present when status is `error` or `governor_halt` |
| `policy_snapshot` | `object | null` | **SHOULD** | Policy config at event time (overrides envelope-level if present) |
| `metadata` | `object | null` | **MAY** | Arbitrary extensibility key-value map |

### 4.3 ErrorObject

```json
{
  "type": "string",
  "message": "string",
  "code": "int | null",
  "stack": "string | null"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `string` | **MUST** | Machine-readable error type (e.g., `GovernorExceededError`, `ToolTimeoutError`, `LLMProviderError`) |
| `message` | `string` | **MUST** | Human-readable error description |
| `code` | `int | null` | **MAY** | Error code for programmatic handling |
| `stack` | `string | null` | **MAY** | Stack trace or execution context |

### 4.4 SpanType Enum

| Value | Meaning |
|-------|---------|
| `agent` | Top-level agent reasoning step (thought/decision) |
| `tool` | External tool invocation (API call, search, calculator, DB query) |
| `llm` | Underlying LLM call (completion, chat, embedding) |
| `observation` | Output from a tool or LLM being fed back into the agent |
| `router` | Decision point that determines next execution path |
| `governor` | Governance action (limit enforcement, policy check, entropy computation) |

---

## 5. Acceptance Criteria

| ID | Requirement | Given / When / Then |
|----|-------------|---------------------|
| AC-1 | FR-1, FR-7 | GIVEN an agent completes one execution step WHEN the trace is serialized THEN the event MUST contain event_id, span_type, timestamp, iteration, status, and MAY contain input/output snapshots |
| AC-2 | FR-2 | GIVEN a nested execution (agent calls tool calls LLM) WHEN trace events are generated THEN the tool event MUST set parent_event_id to the agent event_id and the LLM event MUST set parent_event_id to the tool event_id |
| AC-3 | FR-3 | GIVEN a trace with governance active WHEN any event is recorded THEN it MUST include iteration and cumulative_iterations, and SHOULD include entropy |
| AC-4 | FR-4 | GIVEN a governance policy is active WHEN the trace begins THEN the envelope MUST include policy_snapshot with all current governance parameters |
| AC-5 | FR-5 | GIVEN any JSON-TL payload WHEN parsed as JSON THEN it MUST contain json_tl_version, trace_id, session_id, and events array |
| AC-6 | FR-6 | GIVEN an agent step fails with an error WHEN the event is recorded THEN status MUST be "error" and error object MUST be present with type and message |
| AC-7 | FR-8 | GIVEN a signature is computed WHEN the envelope includes signature THEN it MUST be valid HMAC-SHA256 over the canonical JSON serialization of envelope (excluding signature field itself) |
| AC-8 | FR-9 | GIVEN an agent spawns a sub-agent WHEN the sub-agent trace is created THEN its envelope MUST include parent_trace_id set to the parent trace_id |
| AC-9 | FR-10 | GIVEN a custom field (e.g., "temperature", "model_name") WHEN added to an event's metadata THEN schema validation MUST pass and the field MUST survive round-trip |
| AC-10 | FR-3 | GIVEN an oscillation is detected WHEN the event is recorded THEN oscillation_detected MUST be true |
| AC-11 | NFR-1 | GIVEN a typical trace event (no snapshots, no error) WHEN serialized to JSON THEN the string length MUST be under 1024 characters |
| AC-12 | NFR-3 | GIVEN any valid JSON-TL payload WHEN JSON.parse then JSON.stringify is applied THEN all fields MUST be preserved (lossless round-trip) |

---

## 6. Edge Cases

| ID | Scenario | Expected Behavior |
|----|----------|-------------------|
| EC-1 | Empty trace (no events) | Envelope with events: [] is valid. Must still have trace_id, session_id, version. |
| EC-2 | Missing trace_id | Schema MUST reject. trace_id is required. |
| EC-3 | Invalid span_type | Schema MUST reject with enum validation error. |
| EC-4 | Negative iteration | Schema MUST reject. iteration MUST be >= 0. |
| EC-5 | Orphan child event | Event with parent_event_id that does not match any event_id in the same envelope. This is ALLOWED (cross-envelope linking). |
| EC-6 | Circular parent reference | If event A has parent_event_id == event B and event B has parent_event_id == event A, consumers SHOULD detect and terminate at depth 256. |
| EC-7 | Very large snapshot (>10MB) | Schema allows it. Implementations SHOULD truncate or compress large snapshots with a warning. |
| EC-8 | Non-UTF-8 in text fields | Schema MUST reject. All string fields MUST be valid UTF-8. |
| EC-9 | Missing json_tl_version | Envelope is invalid. Consumer MUST NOT process without version. |
| EC-10 | Concurrent events with same timestamp | Allowed. event_id provides uniqueness. Consumers MUST order by (timestamp, event_id) for deterministic order. |

---

## 7. JSON Schema (Draft-04)

The canonical schema is at `json-tl-schema.json` (adjacent file). Key validation rules:

```json
{
  "$schema": "http://json-schema.org/draft-04/schema#",
  "id": "https://raw.githubusercontent.com/aitoolinsider/json-tl-spec/v0.1/schema.json",
  "title": "JSON-TL Trace Envelope",
  "type": "object",
  "required": ["json_tl_version", "trace_id", "session_id", "events"],
  "properties": {
    "json_tl_version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "trace_id": { "type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$" },
    "session_id": { "type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$" },
    "events": {
      "type": "array",
      "minItems": 0,
      "items": { "$ref": "#/definitions/TraceEvent" }
    }
  },
  "definitions": {
    "TraceEvent": {
      "type": "object",
      "required": ["event_id", "span_type", "timestamp", "iteration", "status"],
      "properties": {
        "event_id": { "type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$" },
        "span_type": { "type": "string", "enum": ["agent", "tool", "llm", "observation", "router", "governor"] },
        "iteration": { "type": "integer", "minimum": 0 },
        "status": { "type": "string", "enum": ["ok", "error", "governor_halt", "timeout", "cancelled"] }
      }
    }
  }
}
```

Full schema in `json-tl-schema.json`.

---

## 8. Examples

### 8.1 Minimal Agent Trace

```json
{
  "json_tl_version": "0.1.0",
  "trace_id": "019529b0-1234-7e00-a000-000000000001",
  "agent_id": "governornode-react-agent-v1",
  "agent_version": "abc123def",
  "session_id": "019529b0-5678-7e00-a000-000000000002",
  "policy_snapshot": {
    "max_iterations": 10,
    "max_oscillations": 3,
    "entropy_window": 10,
    "entropy_threshold": 0.1,
    "record_io": true,
    "halt_on_violation": true
  },
  "events": [
    {
      "event_id": "019529b0-0001-7e00-a000-000000000001",
      "parent_event_id": null,
      "span_type": "agent",
      "span_name": "reasoning_step",
      "timestamp": "2026-06-19T14:30:00.000Z",
      "duration_ms": 120.5,
      "iteration": 1,
      "cumulative_iterations": 1,
      "entropy": null,
      "oscillation_detected": false,
      "status": "ok",
      "input_snapshot": {"messages": ["User: find AI governance data"]},
      "output_snapshot": {"messages": ["User: find AI governance data", "Thought: I need to search"]},
      "error": null,
      "policy_snapshot": null,
      "metadata": {"model": "claude-sonnet-4", "temperature": 0.0}
    }
  ],
  "signature": null
}
```

### 8.2 Trace with Governance Halt

```json
{
  "json_tl_version": "0.1.0",
  "trace_id": "019529b0-aaaa-7e00-a000-000000000003",
  "agent_id": "react-agent",
  "session_id": "019529b0-bbbb-7e00-a000-000000000004",
  "events": [
    {
      "event_id": "evt-001",
      "parent_event_id": null,
      "span_type": "agent",
      "span_name": "loop_step",
      "timestamp": "2026-06-19T14:31:00.000Z",
      "duration_ms": 50.0,
      "iteration": 1,
      "cumulative_iterations": 1,
      "entropy": 0.0,
      "status": "ok"
    },
    {
      "event_id": "evt-006",
      "parent_event_id": null,
      "span_type": "governor",
      "span_name": "iteration_limit",
      "timestamp": "2026-06-19T14:31:05.000Z",
      "duration_ms": 0.01,
      "iteration": 6,
      "cumulative_iterations": 6,
      "entropy": 0.0,
      "oscillation_detected": true,
      "status": "governor_halt",
      "error": {
        "type": "GovernorExceededError",
        "message": "Node exceeded max_iterations=5 (iteration=6)",
        "code": 1001
      },
      "metadata": { "violation_type": "iteration_limit" }
    }
  ]
}
```

---

## 9. Out of Scope

| Item | Reason |
|------|--------|
| Binary transport (Protobuf, Avro) | JSON-TL is a serialization format, not a transport protocol. Binary encoding MAY be added in a future extension. |
| Streaming protocol | JSON-TL defines the data model, not the delivery mechanism (Kafka, HTTP, file drop). Streaming boundaries (e.g., NDJSON) MAY be specified separately. |
| UI visualization | Schema-specified. Grafana, Datadog, and custom dashboards consume the format. |
| LLM prompt/response storage | JSON-TL captures metadata about LLM calls (span_type: "llm") but prompt/response payloads live in the snapshot fields, not in a separate schema. |
| Real-time alerting | JSON-TL is a recording format. Alerting rules are orthogonal. |
| Backend-specific storage | JSON-TL events can be stored in S3, Elasticsearch, SQLite, or any observability backend. The schema is storage-agnostic. |
| Authentication/authorization | The trace format records agent identity (agent_id, session_id) but does not define access control. |

---

## 10. Data Model Summary

```
┌──────────────────────────────┐
│       TraceEnvelope          │
│  ┌────────────────────────┐  │
│  │ json_tl_version: str   │  │
│  │ trace_id: UUIDv7       │──┼── Parent/child linking via
│  │ session_id: UUIDv7     │  │    parent_trace_id
│  │ agent_id: str          │  │
│  │ agent_version: str?    │  │
│  │ parent_trace_id: str?  │──┼── Cross-session linking
│  │ policy_snapshot: obj?  │  │
│  │ signature: str?        │  │
│  │ metadata: obj?         │  │
│  │ events: [TraceEvent]   │  │
│  └────────────────────────┘  │
└──────────────────────────────┘

┌──────────────────────────────┐
│         TraceEvent           │
│  event_id: UUIDv7            │
│  parent_event_id: str?       │──┼── Span hierarchy
│  span_type: enum             │
│  span_name: str?             │
│  timestamp: ISO-8601         │
│  duration_ms: number?        │
│  iteration: int              │
│  cumulative_iterations: int? │
│  entropy: float?             │──┼── Governance metrics
│  oscillation_detected: bool  │
│  status: enum                │
│  input_snapshot: obj?        │
│  output_snapshot: obj?       │
│  error: ErrorObject?         │
│  policy_snapshot: obj?       │
│  metadata: obj?              │──┼── Extensibility
└──────────────────────────────┘
```

---

## 11. Governance Integration

JSON-TL is designed to pair natively with GovernorNode (see `governornode-mvp`). Every `FlightRecord` in the GovernorNode maps directly to a `TraceEvent`:

```
FlightRecord           →  TraceEvent
─────────────────────────────────────
node_name             →  span_name
timestamp             →  timestamp
iteration             →  iteration
input_snapshot        →  input_snapshot
output_snapshot       →  output_snapshot
latency_ms            →  duration_ms
oscillation_detected  →  oscillation_detected
entropy               →  entropy
error                 →  error
```

The `GovernancePolicy` serializes to `policy_snapshot`.

**Mapping code** will be provided in the reference implementation (`json_tl.py`).

---

## 12. Open Questions (for community discussion)

| # | Question |
|---|----------|
| OQ-1 | Should `span_type` be extensible via registration (like HTTP content-type) or free-form? |
| OQ-2 | Should large snapshots (>1 MB) be stored separately with a content-addressable hash reference? |
| OQ-3 | What is the max recommended event count per envelope before chunking? 10K? 100K? |
| OQ-4 | Should the schema include a `compression` hint (gzip, zstd) for the payload? |
| OQ-5 | Should we define an NDJSON variant for streaming ingestion? |
| OQ-6 | What is the *minimum* viable set of fields that every JSON-TL implementation MUST support? |
| OQ-7 | How do we handle PII/sensitive data in snapshot fields? Should there be a `redacted` marker? |

---

## 13. Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-06-19 | Hermes Agent O | Initial RFC draft — core schema, span types, governance integration, acceptance criteria |

---

## References

1. [OpenTelemetry Trace Specification](https://opentelemetry.io/docs/specs/otel/trace/) — inspiration for span model
2. [CloudEvents](https://cloudevents.io/) — envelope design patterns
3. [JSON Schema (draft-04)](https://json-schema.org/specification-links#draft-4) — validation
4. [GovernorNode MVP](https://github.com/aitoolinsider/governornode-mvp) — reference implementation (flight recorder → JSON-TL mapping)
5. [UUIDv7](https://www.ietf.org/archive/id/draft-ietf-uuidrev-4123.html) — time-ordered unique identifiers

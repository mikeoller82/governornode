# GovernorNode MVP — LangGraph Governance Wrapper

**Author:** Mike Oller  
**Date:** 2026-06-19  
**Status:** Approved  
**Version:** 1.0.0

## Context

The AI industry is transitioning from "Wild West" agentic experimentation to governed orchestration. LangGraph is the dominant framework for building agent loops (ReAct, Reflexion), but it has no built-in governance — no iteration limits, no oscillation detection, no flight recorder for audit trails.

The GovernorNode MVP provides a drop-in wrapper that adds governance to any LangGraph node without changing the underlying agent logic. It aligns with the "Standardized Orchestration" scenario (65% probability) where governor-loop engineering becomes standard infrastructure.

## Functional Requirements

| ID | Description | Priority |
| - | - | - |
| FR-1 | GovernorNode MUST wrap any LangGraph callable node and forward calls transparently | HIGH |
| FR-2 | GovernorNode MUST track iteration count per node execution | HIGH |
| FR-3 | GovernorNode MUST enforce a configurable max iteration limit (default: 25) | HIGH |
| FR-4 | GovernorNode MUST detect oscillation (repeating state patterns) and halt with an error | HIGH |
| FR-5 | GovernorNode MUST record every execution as a FlightRecord with timestamp, input, output, latency | HIGH |
| FR-6 | GovernorNode MUST serialize FlightRecords to JSON for audit trail | MEDIUM |
| FR-7 | GovernancePolicy MUST load from YAML file or dict | MEDIUM |
| FR-8 | GovernorStateGraph MUST be a drop-in replacement for langgraph.graph.StateGraph | HIGH |
| FR-9 | GovernorNode MUST measure entropy (plan diversity) across consecutive calls | MEDIUM |
| FR-10 | GovernorNode MUST raise GovernorExceededError when limits are breached | HIGH |


## Non-Functional Requirements

| ID | Description | Threshold |
| - | - | - |
| NFR-1 | Overhead of wrapped node MUST be under 5ms per call (excluding node execution) | \<5ms |
| NFR-2 | FlightRecord serialization MUST NOT block node execution | async-ready |
| NFR-3 | Policy YAML MUST be self-documenting with comments | all fields documented |


## API Contracts

```
class GovernancePolicy:  
    max\_iterations: int = 25          \# Max calls to a single node  
    max\_oscillations: int = 5          \# Consecutive same-output before oscillation flagged  
    entropy\_window: int = 10           \# Window for plan entropy calculation  
    entropy\_threshold: float = 0.1     \# Min entropy before warning  
    record\_io: bool = True             \# Capture full input/output in recorder  
    halt\_on\_violation: bool = True     \# Raise error vs. warn  
  
class FlightRecord:  
    node\_name: str  
    timestamp: float  
    iteration: int  
    input\_snapshot: dict  
    output\_snapshot: dict  
    latency\_ms: float  
    oscillation\_detected: bool  
    entropy: float | None  
  
class GovernorNode:  
    def \_\_init\_\_(self, node: Callable, name: str, policy: GovernancePolicy | None = None): ...  
    def \_\_call\_\_(self, state: dict) -\> dict: ...  
    def get\_recorder(self) -\> FlightDataRecorder: ...  
    def reset(self) -\> None: ...  
  
class GovernorStateGraph(StateGraph):  
    def add\_node(self, key: str, node: Callable, \*\*kwargs) -\> Self: ...
```

## Acceptance Criteria

| ID | Given | When | Then |
| - | - | - | - |
| AC-1 | A GovernorNode wraps a simple state modifier | Called with state | Returns modified state identical to unwrapped node |
| AC-2 | A node with max\_iterations=3 is called 3 times | Called 4th time | Raises GovernorExceededError |
| AC-3 | A node returns identical output 6 times with max\_oscillations=5 | Called 6th time | Raises GovernorExceededError with "oscillation" message |
| AC-4 | FlightRecorder has 0 records | After 3 node calls | Recorder has 3 records |
| AC-5 | A GovernorStateGraph compiles into a runnable app | Compiled and invoked | Returns correct result matching ungoverned graph |
| AC-6 | Policy loaded from YAML matches policy from dict | Both created | Identical behavior |
| AC-7 | Entropy monitor observes 5 unique outputs in window 10 | Checked after 10 calls | Entropy \> 0.5 |
| AC-8 | Entropy monitor observes 1 unique output in window 10 | Checked after 10 calls | Entropy approaches 0.0 |


## Edge Cases

| ID | Description |
| - | - |
| EC-1 | GovernorNode wrapping a node that itself raises an exception — governor should still record the attempt |
| EC-2 | Multiple GovernorNodes in the same graph with independent policies |
| EC-3 | Reset clears iteration count and recorder but not policy |
| EC-4 | Policy with halt\_on\_violation=False logs warnings instead of raising errors |


## Out of Scope

- Distributed/governor-node-as-a-service — this is a local Python wrapper only

- Integration with external monitoring APIs (Datadog, Prometheus) — future

- LangGraph checkpointer integration — raw StateGraph only

- Async nodes — sync-only for MVP


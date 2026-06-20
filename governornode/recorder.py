"""FlightDataRecorder — audit trail for GovernorNode executions."""

import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class FlightRecord:
    """A single recorded event from a GovernorNode execution."""

    node_name: str
    timestamp: float
    iteration: int
    input_snapshot: dict | None = None
    output_snapshot: dict | None = None
    latency_ms: float = 0.0
    oscillation_detected: bool = False
    entropy: float | None = None
    error: str | None = None


class FlightDataRecorder:
    """Collects and stores FlightRecords for audit trail."""

    def __init__(self):
        self._records: list[FlightRecord] = []

    def record(
        self,
        node_name: str,
        iteration: int,
        input_snapshot: dict | None = None,
        output_snapshot: dict | None = None,
        latency_ms: float = 0.0,
        oscillation_detected: bool = False,
        entropy: float | None = None,
        error: str | None = None,
    ) -> FlightRecord:
        """Create and store a FlightRecord."""
        record = FlightRecord(
            node_name=node_name,
            timestamp=time.time(),
            iteration=iteration,
            input_snapshot=input_snapshot,
            output_snapshot=output_snapshot,
            latency_ms=latency_ms,
            oscillation_detected=oscillation_detected,
            entropy=entropy,
            error=error,
        )
        self._records.append(record)
        return record

    def get_records(self) -> list[FlightRecord]:
        """Return all records."""
        return list(self._records)

    def get_record_count(self) -> int:
        return len(self._records)

    def clear(self) -> None:
        """Erase all records."""
        self._records.clear()

    def to_json(self, indent: int = 2) -> str:
        """Serialize all records to JSON."""
        def _serialize(r: FlightRecord) -> dict:
            d = asdict(r)
            return d
        return json.dumps([_serialize(r) for r in self._records], indent=indent)

    def last_n(self, n: int) -> list[FlightRecord]:
        """Return the last N records."""
        return self._records[-n:]

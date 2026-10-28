"""
Sovereign Protocol Definitions
Defines message schemas, state enums, and Lamport logical clock.
"""
from __future__ import annotations

import json
import time
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class NodeStatus(str, Enum):
    FOLLOWER = "FOLLOWER"
    ELECTING = "ELECTING"
    LEADER = "LEADER"
    DEAD = "DEAD"
    ALIVE = "FOLLOWER"  # Backward compatibility alias


class AlgorithmType(str, Enum):
    BULLY = "bully"
    RING = "ring"


class MessageType(str, Enum):
    # Failure detection
    HEARTBEAT = "HEARTBEAT"
    HEARTBEAT_ACK = "HEARTBEAT_ACK"

    # Bully Algorithm
    ELECTION = "ELECTION"
    OK = "OK"
    COORDINATOR = "COORDINATOR"

    # Ring Algorithm
    RING_ELECTION = "RING_ELECTION"
    RING_COORDINATOR = "RING_COORDINATOR"

    # Control from Gateway / Orchestrator
    CONTROL = "CONTROL"

    # Event telemetry sent from Node to Gateway
    EVENT = "EVENT"


class ControlAction(str, Enum):
    KILL = "kill"
    REVIVE = "revive"
    SET_ALGORITHM = "set_algorithm"
    SET_NETWORK = "set_network"
    MEMBERSHIP = "membership"
    START_ELECTION = "start_election"
    GET_STATE = "get_state"


class LamportClock:
    """Thread-safe / Async-safe Lamport Logical Clock."""
    def __init__(self, initial_time: int = 0) -> None:
        self._value: int = initial_time

    @property
    def value(self) -> int:
        return self._value

    def tick(self) -> int:
        """Increment on local event or before sending a message."""
        self._value += 1
        return self._value

    def update(self, received_time: int) -> int:
        """Update upon receiving a message with a timestamp: L = max(L, L_recv) + 1."""
        self._value = max(self._value, received_time) + 1
        return self._value

    def reset(self, new_val: int = 0) -> None:
        self._value = new_val

    def __repr__(self) -> str:
        return f"LamportClock({self._value})"


class Message(BaseModel):
    """Unified network message schema as specified in SRS Section 8."""
    model_config = ConfigDict(populate_by_name=True)

    type: MessageType
    from_node: int = Field(alias="from")
    to_node: int = Field(alias="to")
    election_id: Optional[str] = None
    algorithm: AlgorithmType = AlgorithmType.BULLY
    payload: Dict[str, Any] = Field(default_factory=dict)
    lamport: int = 0
    ts: float = Field(default_factory=time.time)
    delivered: bool = True

    @property
    def payload_leader(self) -> Optional[int]:
        val = self.payload.get("leader")
        return int(val) if val is not None else None

    @property
    def payload_initiator(self) -> Optional[int]:
        val = self.payload.get("initiator")
        return int(val) if val is not None else None

    @property
    def payload_ids(self) -> List[int]:
        raw = self.payload.get("ids", self.payload.get("alive", []))
        return [int(x) for x in raw]

    def to_json(self) -> str:
        """Serialize as a single line JSON string terminated by newline."""
        return self.model_dump_json(by_alias=True) + "\n"

    @classmethod
    def from_json(cls, raw: str) -> Message:
        """Parse from JSON string."""
        return cls.model_validate_json(raw.strip())


class EventMessage(BaseModel):
    """Telemetry message sent to the Gateway for real-time visualization."""
    model_config = ConfigDict(populate_by_name=True)

    type: str = "EVENT"
    event_type: str  # "MESSAGE_SENT", "MESSAGE_RECEIVED", "STATE_CHANGED", "LEADER_ELECTED"
    node_id: int
    data: Dict[str, Any]
    lamport: int
    ts: float = Field(default_factory=time.time)

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True) + "\n"

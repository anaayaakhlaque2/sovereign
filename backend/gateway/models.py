"""
SQLModel database entities for recording elections, events, and metrics.
"""
from __future__ import annotations

import time
from typing import Optional
from sqlmodel import Field, SQLModel


class ElectionRecord(SQLModel, table=True):
    __tablename__ = "elections"

    id: Optional[int] = Field(default=None, primary_key=True)
    election_id: str = Field(index=True, unique=True)
    algorithm: str
    node_count: int = 5
    initiator_id: Optional[int] = None
    winner_id: Optional[int] = None
    start_ts: float = Field(default_factory=time.time)
    end_ts: Optional[float] = None
    duration_ms: Optional[float] = None
    election_messages: int = 0
    delivered_messages: int = 0
    failed_to_dead_node: int = 0
    heartbeat_messages: int = 0
    total_messages: int = 0


class EventRecord(SQLModel, table=True):
    __tablename__ = "events"

    id: Optional[int] = Field(default=None, primary_key=True)
    election_id: Optional[str] = Field(default=None, index=True)
    event_type: str
    node_id: int
    from_node: Optional[int] = None
    to_node: Optional[int] = None
    msg_type: Optional[str] = None
    lamport: int = 0
    ts: float = Field(default_factory=time.time, index=True)
    details_json: str = "{}"

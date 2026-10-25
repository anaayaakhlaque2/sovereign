"""
Telemetry and WebSocket Broadcaster
Receives TCP events from nodes, persists to SQLite, counts messages, and streams to UI via WebSockets.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Set
from fastapi import WebSocket
from sqlmodel import Session, select

from backend.gateway.database import engine
from backend.gateway.models import ElectionRecord, EventRecord
from backend.gateway.supervisor import ClusterSupervisor
from backend.protocol import EventMessage, MessageType, NodeStatus

logger = logging.getLogger("sovereign.telemetry")


def _persist_event_sync(
    election_id: Optional[str],
    event_type: str,
    node_id: int,
    from_node: Optional[int],
    to_node: Optional[int],
    msg_type: Optional[str],
    lamport: int,
    ts: float,
    evt_data: Dict[str, Any],
    supervisor_algorithm: str,
    supervisor_node_count: int,
) -> None:
    try:
        with Session(engine) as session:
            event_rec = EventRecord(
                election_id=election_id,
                event_type=event_type,
                node_id=node_id,
                from_node=from_node,
                to_node=to_node,
                msg_type=msg_type,
                lamport=lamport,
                ts=ts,
                details_json=json.dumps(evt_data),
            )
            session.add(event_rec)

            if election_id:
                stmt = select(ElectionRecord).where(ElectionRecord.election_id == election_id)
                election_rec = session.exec(stmt).first()

                algo = evt_data.get("algorithm", supervisor_algorithm)

                if not election_rec:
                    election_rec = ElectionRecord(
                        election_id=election_id,
                        algorithm=algo,
                        node_count=supervisor_node_count,
                        initiator_id=from_node,
                        start_ts=ts,
                    )
                    session.add(election_rec)

                if msg_type in (MessageType.HEARTBEAT.value, MessageType.HEARTBEAT_ACK.value):
                    election_rec.heartbeat_messages += 1
                elif msg_type in (
                    MessageType.ELECTION.value,
                    MessageType.OK.value,
                    MessageType.COORDINATOR.value,
                    MessageType.RING_ELECTION.value,
                    MessageType.RING_COORDINATOR.value,
                ):
                    election_rec.election_messages += 1

                election_rec.total_messages += 1

                if msg_type in (MessageType.COORDINATOR.value, MessageType.RING_COORDINATOR.value):
                    winner = evt_data.get("payload", {}).get("leader", from_node)
                    election_rec.winner_id = winner
                    election_rec.end_ts = ts
                    election_rec.duration_ms = max(0.0, (ts - election_rec.start_ts) * 1000)

                    pending_stmt = select(ElectionRecord).where(ElectionRecord.winner_id == None).where(ElectionRecord.start_ts >= ts - 15.0)
                    for p in session.exec(pending_stmt).all():
                        p.winner_id = winner
                        if not p.end_ts:
                            p.end_ts = ts
                            p.duration_ms = max(0.0, (ts - p.start_ts) * 1000)

            session.commit()
    except Exception as e:
        logger.debug(f"Telemetry DB persistence error: {e}")


class TelemetryHub:
    def __init__(self, supervisor: ClusterSupervisor, port: int = 9090) -> None:
        self.supervisor = supervisor
        self.port = port
        self.active_websockets: Set[WebSocket] = set()
        self._server: Optional[asyncio.Server] = None
        self._running: bool = False

        # Live election stats tracker: election_id -> ElectionRecord
        self.active_elections: Dict[str, ElectionRecord] = {}

    # -------------------------------------------------------------------------
    # WebSocket Management
    # -------------------------------------------------------------------------

    async def connect_client(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_websockets.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_websockets)}")

        # Send initial snapshot of cluster state
        snapshot = {
            "type": "SNAPSHOT",
            "nodes": list(self.supervisor.node_cache.values()),
            "leader": self.supervisor.current_leader,
            "algorithm": self.supervisor.current_algorithm.value,
            "node_count": self.supervisor.node_count,
            "chaos": self.supervisor.chaos_running,
            "delay": self.supervisor.simulated_delay,
            "drop_rate": self.supervisor.simulated_drop_rate,
        }
        await websocket.send_text(json.dumps(snapshot))

    def disconnect_client(self, websocket: WebSocket) -> None:
        self.active_websockets.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_websockets)}")

    async def broadcast_ws(self, data: Dict[str, Any]) -> None:
        """Broadcasts JSON payload to all connected WebSockets."""
        if not self.active_websockets:
            return

        msg = json.dumps(data)
        stale = set()
        for ws in self.active_websockets:
            try:
                await ws.send_text(msg)
            except Exception:
                stale.add(ws)

        for s in stale:
            self.active_websockets.discard(s)

    # -------------------------------------------------------------------------
    # TCP Telemetry Receiver from Node processes
    # -------------------------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        self._server = await asyncio.start_server(
            self._handle_telemetry_client,
            "127.0.0.1",
            self.port,
        )
        logger.info(f"Telemetry receiver listening on 127.0.0.1:{self.port}")

    async def stop(self) -> None:
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        logger.info("Telemetry receiver stopped.")

    async def _handle_telemetry_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while self._running:
                line = await reader.readline()
                if not line:
                    break
                raw = line.decode("utf-8").strip()
                if not raw:
                    continue

                try:
                    data = json.loads(raw)
                    await self._process_event(data)
                except Exception as ex:
                    logger.debug(f"Telemetry parse error: {ex}")
        except Exception:
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _process_event(self, data: Dict[str, Any]) -> None:
        event_type = data.get("event_type")
        node_id = data.get("node_id", 0)
        evt_data = data.get("data", {})
        lamport = data.get("lamport", 0)
        ts = data.get("ts", time.time())

        # Update node cache in supervisor
        if event_type == "STATE_CHANGED" or event_type == "LEADER_ELECTED":
            status = evt_data.get("status")
            leader_id = evt_data.get("leader_id")

            if node_id in self.supervisor.node_cache:
                if status:
                    self.supervisor.node_cache[node_id]["status"] = status
                if leader_id is not None:
                    self.supervisor.node_cache[node_id]["leader_id"] = leader_id
                elif status == NodeStatus.DEAD.value:
                    self.supervisor.node_cache[node_id]["leader_id"] = None

            if status == NodeStatus.LEADER.value:
                self.supervisor.current_leader = node_id
            elif status == NodeStatus.DEAD.value and self.supervisor.current_leader == node_id:
                self.supervisor.current_leader = None

        # Message tracking & election counting
        election_id = evt_data.get("election_id")
        msg_type = evt_data.get("type")
        from_node = evt_data.get("from")
        to_node = evt_data.get("to")

        if msg_type in (MessageType.COORDINATOR.value, MessageType.RING_COORDINATOR.value):
            winner = evt_data.get("payload", {}).get("leader", from_node)
            self.supervisor.current_leader = winner

        # Stream event out over WebSocket immediately (zero latency, zero disk I/O blocking)
        ws_payload = {
            "type": "EVENT",
            "event_type": event_type,
            "node_id": node_id,
            "data": evt_data,
            "lamport": lamport,
            "ts": ts,
            "leader": self.supervisor.current_leader,
        }
        await self.broadcast_ws(ws_payload)

        # Offload SQLite synchronous disk commit to worker thread so event loop never lags
        asyncio.create_task(
            asyncio.to_thread(
                _persist_event_sync,
                election_id,
                event_type,
                node_id,
                from_node,
                to_node,
                msg_type,
                lamport,
                ts,
                evt_data,
                self.supervisor.current_algorithm.value,
                self.supervisor.node_count,
            )
        )

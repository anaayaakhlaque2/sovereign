"""
Telemetry and WebSocket Broadcaster
Receives TCP events from nodes, persists to SQLite, counts messages, and streams to UI via WebSockets.
"""
from __future__ import annotations

import asyncio
from collections import Counter
import json
import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple
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

                # Count a message once, at the SENDER, when it is sent. Do NOT also count the receiver event.
                if event_type == "MESSAGE_SENT":
                    delivered = evt_data.get("delivered", True)
                    if msg_type in (MessageType.HEARTBEAT.value, MessageType.HEARTBEAT_ACK.value):
                        election_rec.heartbeat_messages += 1
                    elif msg_type in (
                        MessageType.ELECTION.value,
                        MessageType.OK.value,
                        MessageType.COORDINATOR.value,
                        MessageType.RING_ELECTION.value,
                        MessageType.RING_COORDINATOR.value,
                    ):
                        if delivered:
                            election_rec.delivered_messages += 1
                            election_rec.election_messages += 1
                        else:
                            election_rec.failed_to_dead_node += 1

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
        # Version tracker per node: node_id -> (lamport, ts) (Suspect g)
        self.node_versions: Dict[int, Tuple[int, float]] = {}
        self.last_invariant_result: Dict[str, Any] = {}

    def get_cluster_snapshot(self) -> Dict[str, Any]:
        """
        Rule R1 & Step 4: Single source of truth for the cluster.
        leader_id = leader reported by the majority of ALIVE nodes.
        agreed = true ONLY when all alive nodes report the same leader_id.
        """
        nodes = []
        alive_leaders: List[int] = []
        alive_nodes: List[int] = []

        all_ids = sorted(list(self.supervisor.node_ports.keys()))
        for nid in all_ids:
            cached = self.supervisor.node_cache.get(nid, {})
            st = cached.get("status", NodeStatus.FOLLOWER.value)
            lid = cached.get("leader_id")
            if lid is not None:
                lid = int(lid)

            nodes.append({
                "id": nid,
                "status": st,
                "leader_id": lid,
            })

            if st != NodeStatus.DEAD.value:
                alive_nodes.append(nid)
                if lid is not None:
                    alive_leaders.append(lid)

        leader_id: Optional[int] = None
        agreed = False

        if alive_nodes and alive_leaders:
            counts = Counter(alive_leaders)
            top_leader, count = counts.most_common(1)[0]
            # Majority of alive nodes report top_leader
            if count > len(alive_nodes) / 2:
                leader_id = top_leader
            # Agreed: every single alive node reports the same leader_id
            agreed = (len(alive_leaders) == len(alive_nodes)) and (len(counts) == 1)

        return {
            "type": "SNAPSHOT",
            "nodes": nodes,
            "leader_id": leader_id,
            "agreed": agreed,
            "algorithm": self.supervisor.current_algorithm.value,
            "node_count": len(self.supervisor.node_ports),
            "chaos": self.supervisor.chaos_running,
            "delay": self.supervisor.simulated_delay,
            "drop_rate": self.supervisor.simulated_drop_rate,
        }

    def check_invariants(self) -> Dict[str, Any]:
        """
        STEP 5: Assert and log loudly:
        I1: exactly one alive node has status LEADER
        I2: that node's id == max(alive ids)
        I3: every alive node's leader_id equals it
        I4: snapshot leader_id (UI) equals it within 5 s
        """
        nodes_state = self.supervisor.node_cache
        alive = [nid for nid, c in nodes_state.items() if c.get("status") != NodeStatus.DEAD.value]
        if not alive:
            return {
                "passed": True,
                "I1": True,
                "I2": True,
                "I3": True,
                "I4": True,
                "message": "all nodes dead",
            }

        leader_nodes = [nid for nid in alive if nodes_state[nid].get("status") == NodeStatus.LEADER.value]
        max_alive_id = max(alive)
        snapshot = self.get_cluster_snapshot()

        i1 = (len(leader_nodes) == 1)
        i2 = i1 and (leader_nodes[0] == max_alive_id)
        expected_leader = leader_nodes[0] if i1 else max_alive_id
        i3 = all(nodes_state[nid].get("leader_id") == expected_leader for nid in alive)
        i4 = (snapshot.get("agreed") is True) and (snapshot.get("leader_id") == expected_leader)

        all_passed = i1 and i2 and i3 and i4
        res = {
            "passed": all_passed,
            "I1": i1,
            "I2": i2,
            "I3": i3,
            "I4": i4,
            "leader_nodes": leader_nodes,
            "max_alive_id": max_alive_id,
            "expected_leader": expected_leader,
            "snapshot_leader": snapshot.get("leader_id"),
            "snapshot_agreed": snapshot.get("agreed"),
            "node_states": {nid: {"status": c.get("status"), "leader_id": c.get("leader_id")} for nid, c in nodes_state.items()},
        }
        if not all_passed:
            logger.warning(
                f"[bold red]INVARIANT VIOLATION DETECTED[/]: I1={i1}, I2={i2}, I3={i3}, I4={i4} | States: {res['node_states']}"
            )
        else:
            logger.info(
                f"[bold green]Invariants I1-I4 Satisfied[/]: Leader={expected_leader}, Agreed={snapshot.get('agreed')}"
            )
        return res

    # -------------------------------------------------------------------------
    # WebSocket Management
    # -------------------------------------------------------------------------

    async def connect_client(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_websockets.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_websockets)}")

        # Send initial snapshot of cluster state (Single Source of Truth)
        snapshot = self.get_cluster_snapshot()
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
        node_id = int(data.get("node_id", 0))
        evt_data = data.get("data", {})
        lamport = int(data.get("lamport", 0))
        ts = float(data.get("ts", time.time()))

        # Check version: order by (lamport, ts) to ignore stale events (Suspect g)
        version = (lamport, ts)
        if version < self.node_versions.get(node_id, (-1, 0.0)):
            logger.debug(f"Ignoring stale event from Node {node_id} (version {version} < {self.node_versions.get(node_id)})")
            return
        self.node_versions[node_id] = version

        # Update node cache in supervisor with reporting node's own state
        if event_type in ("STATE_CHANGED", "LEADER_ELECTED"):
            status = evt_data.get("status")
            raw_leader = evt_data.get("leader_id")
            leader_id = int(raw_leader) if raw_leader is not None else None

            if node_id in self.supervisor.node_cache:
                if status:
                    self.supervisor.node_cache[node_id]["status"] = status
                if leader_id is not None:
                    self.supervisor.node_cache[node_id]["leader_id"] = leader_id
                elif status == NodeStatus.DEAD.value:
                    self.supervisor.node_cache[node_id]["leader_id"] = None

        # Recompute canonical snapshot from nodes' own views (Rule R1, Suspect d)
        snapshot = self.get_cluster_snapshot()
        self.supervisor.current_leader = snapshot["leader_id"] if snapshot["agreed"] else None

        # Check invariants if election status changed (STEP 5)
        if event_type in ("STATE_CHANGED", "LEADER_ELECTED"):
            self.last_invariant_result = self.check_invariants()

        # Message tracking & election counting
        election_id = evt_data.get("election_id")
        msg_type = evt_data.get("type")
        raw_from = evt_data.get("from")
        from_node = int(raw_from) if raw_from is not None else None
        raw_to = evt_data.get("to")
        to_node = int(raw_to) if raw_to is not None else None

        # Stream event out over WebSocket immediately (zero latency, zero disk I/O blocking)
        ws_payload = {
            "type": "EVENT",
            "event_type": event_type,
            "node_id": node_id,
            "data": evt_data,
            "lamport": lamport,
            "ts": ts,
            "leader": self.supervisor.current_leader,
            "snapshot": snapshot,
        }
        await self.broadcast_ws(ws_payload)

        # Broadcast canonical snapshot on state change
        if event_type in ("STATE_CHANGED", "LEADER_ELECTED"):
            await self.broadcast_ws(snapshot)

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

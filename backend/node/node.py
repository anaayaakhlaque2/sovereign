"""
Sovereign Node Process
Independent OS process representing a kingdom node (castle).
Runs an async TCP server, interacts with peers, manages state, algorithms, and sends telemetry.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import sys
import time
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.logging import RichHandler

from backend.config import NODE_COUNT, get_node_ports
from backend.node.bully import BullyElection
from backend.node.heartbeat import HeartbeatDetector
from backend.node.ring import RingElection
from backend.protocol import (
    AlgorithmType,
    ControlAction,
    EventMessage,
    LamportClock,
    Message,
    MessageType,
    NodeStatus,
)

# Rich setup for viva / terminal demo
console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, console=console, show_path=False)],
)
logger = logging.getLogger("sovereign.node")


class Node:
    def __init__(
        self,
        node_id: int,
        port: int,
        peers: Dict[int, int],
        algorithm: AlgorithmType = AlgorithmType.BULLY,
        gateway_host: str = "127.0.0.1",
        gateway_port: Optional[int] = None,
        heartbeat_interval: float = 1.0,
        heartbeat_timeout: float = 2.2,
        ok_timeout: float = 1.0,
        coordinator_timeout: float = 3.0,
        ring_token_timeout: Optional[float] = None,
    ) -> None:
        self.node_id = node_id
        self.port = port
        self.peers = dict(peers)  # {id: port}
        self.peers[self.node_id] = self.port
        self.algorithm = algorithm
        self.gateway_host = gateway_host
        self.gateway_port = gateway_port

        # State (Rule R2)
        self.status = NodeStatus.FOLLOWER
        self.leader_id: Optional[int] = None
        self.clock = LamportClock()
        self.sent_messages: List[Dict[str, Any]] = []

        # Network fault injection
        self.network_delay: float = 0.0
        self.drop_rate: float = 0.0

        # Subsystems
        self.bully = BullyElection(
            node_id=self.node_id,
            get_peers=lambda: self.peers,
            send_message=self._send_direct,
            broadcast_message=self._broadcast_direct,
            on_state_change=self._on_state_change,
            get_lamport=lambda: self.clock.value,
            ok_timeout=ok_timeout,
            coordinator_timeout=coordinator_timeout,
            is_alive=lambda: self.status != NodeStatus.DEAD,
        )
        self.ring = RingElection(
            node_id=self.node_id,
            get_peers=lambda: self.peers,
            send_message_to_node=self._send_to_node_id,
            on_state_change=self._on_state_change,
            get_lamport=lambda: self.clock.value,
            token_timeout=ring_token_timeout,
            is_alive=lambda: self.status != NodeStatus.DEAD,
        )
        self.heartbeat = HeartbeatDetector(
            node_id=self.node_id,
            get_leader_id=lambda: self.leader_id,
            send_heartbeat=self._send_heartbeat,
            on_leader_failed=self._on_leader_failed,
            ping_interval=heartbeat_interval,
            timeout=heartbeat_timeout,
        )

        self._server: Optional[asyncio.Server] = None
        self._running: bool = False

    @property
    def current_election_id(self) -> Optional[str]:
        if self.algorithm == AlgorithmType.BULLY:
            return self.bully.current_election_id
        return self.ring.current_election_id

    # -------------------------------------------------------------------------
    # Server Lifecycle
    # -------------------------------------------------------------------------

    async def start(self) -> None:
        """Starts the node TCP server and begins heartbeat detection."""
        self._running = True
        self._server = await asyncio.start_server(
            self._handle_client,
            "127.0.0.1",
            self.port,
        )
        logger.info(f"[bold green]Node {self.node_id}[/] listening on port {self.port} (Algo: {self.algorithm.value})")
        self.heartbeat.start()
        await self._send_event("STATE_CHANGED", {"status": self.status.value, "leader_id": self.leader_id})
        # Suspect j: on start, query peers to discover if a leader is already established
        asyncio.create_task(self._query_peer_for_leader())

    async def stop(self) -> None:
        """Stops the node cleanly."""
        self._running = False
        await self.heartbeat.stop()
        self.bully.cancel_timers()
        self.ring.reset()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        logger.info(f"Node {self.node_id} stopped.")

    # -------------------------------------------------------------------------
    # Network Communication
    # -------------------------------------------------------------------------

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
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
                    # Check if it's a CONTROL message
                    if data.get("type") == MessageType.CONTROL.value:
                        reply = await self._handle_control(data)
                        if reply:
                            writer.write((json.dumps(reply) + "\n").encode("utf-8"))
                            await writer.drain()
                        continue

                    # If node is dead, refuse/ignore regular peer messages
                    if self.status == NodeStatus.DEAD:
                        writer.close()
                        await writer.wait_closed()
                        return

                    # Otherwise, standard protocol message: acknowledge receipt
                    writer.write(b'{"ack": true}\n')
                    await writer.drain()

                    msg = Message.model_validate(data)
                    asyncio.create_task(self._process_incoming_message(msg))
                except Exception as ex:
                    logger.warning(f"Node {self.node_id}: Malformed message: {ex}")
        except Exception as e:
            logger.debug(f"Node {self.node_id} client handler: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _process_incoming_message(self, msg: Message) -> None:
        # If node is dead, ignore all election/heartbeat messages completely!
        if self.status == NodeStatus.DEAD:
            return

        # Check simulated network drop
        if self.drop_rate > 0.0 and random.random() < self.drop_rate:
            logger.warning(f"Node {self.node_id}: Dropped incoming {msg.type} from Node {msg.from_node} (drop rate: {self.drop_rate})")
            return

        # Check simulated delay
        if self.network_delay > 0.0:
            await asyncio.sleep(self.network_delay)

        # Lamport logical clock update (Rule R5)
        self.clock.update(msg.lamport)

        # Emit telemetry event
        await self._send_event("MESSAGE_RECEIVED", {
            "from": msg.from_node,
            "to": self.node_id,
            "type": msg.type.value,
            "election_id": msg.election_id,
            "algorithm": msg.algorithm.value,
            "payload": msg.payload,
        })

        # Message dispatch
        mtype = msg.type
        if mtype == MessageType.HEARTBEAT:
            # Only leader (or if electing self) replies to heartbeat
            if self.node_id == self.leader_id or self.status == NodeStatus.LEADER:
                ack = Message(
                    type=MessageType.HEARTBEAT_ACK,
                    from_node=self.node_id,
                    to_node=msg.from_node,
                    lamport=self.clock.tick(),
                    algorithm=self.algorithm,
                )
                await self._send_direct(ack)

        elif mtype == MessageType.HEARTBEAT_ACK:
            self.heartbeat.record_ack(msg.from_node)

        elif mtype == MessageType.ELECTION:
            await self.bully.handle_election_message(msg)

        elif mtype == MessageType.OK:
            await self.bully.handle_ok_message(msg)

        elif mtype == MessageType.COORDINATOR:
            await self.bully.handle_coordinator_message(msg)

        elif mtype == MessageType.RING_ELECTION:
            await self.ring.handle_election_token(msg)

        elif mtype == MessageType.RING_COORDINATOR:
            await self.ring.handle_coordinator_token(msg)

    async def _send_to_node_id(self, target_id: int, msg: Message) -> bool:
        """Sends a message to a specific node by ID."""
        msg.to_node = target_id
        return await self._send_direct(msg)

    async def _send_direct(self, msg: Message) -> bool:
        """Sends a Message over TCP to target node."""
        if self.status == NodeStatus.DEAD:
            return False

        target_id = msg.to_node
        if target_id not in self.peers:
            logger.warning(f"Node {self.node_id}: Unknown target node {target_id}")
            return False

        target_port = self.peers[target_id]
        msg.lamport = self.clock.tick()
        raw = msg.to_json()

        is_election_msg = msg.type in (
            MessageType.ELECTION,
            MessageType.OK,
            MessageType.COORDINATOR,
            MessageType.RING_ELECTION,
            MessageType.RING_COORDINATOR,
        )

        # Retry under lossy fault injection (suspect k)
        max_attempts = 3 if self.drop_rate > 0.0 else 1
        for attempt in range(max_attempts):
            if attempt > 0:
                await asyncio.sleep(0.05)

            # Apply network drop
            if self.drop_rate > 0.0 and random.random() < self.drop_rate:
                logger.warning(f"Node {self.node_id}: Dropped outgoing {msg.type} to {target_id} (attempt {attempt + 1})")
                if attempt == max_attempts - 1:
                    if is_election_msg:
                        self.sent_messages.append({
                            "from": self.node_id,
                            "to": target_id,
                            "type": msg.type.value,
                            "election_id": msg.election_id,
                            "algorithm": msg.algorithm.value,
                            "payload": msg.payload,
                            "delivered": False,
                        })
                    return False
                continue

            # Apply network delay
            if self.network_delay > 0.0:
                await asyncio.sleep(self.network_delay)

            try:
                # Step 1: Connect
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", target_port),
                    timeout=1.0,
                )
            except (ConnectionRefusedError, OSError) as err:
                logger.warning(f"Node {self.node_id}: Connect failed to {target_id} (port {target_port}): {err}")
                if is_election_msg:
                    self.sent_messages.append({
                        "from": self.node_id,
                        "to": target_id,
                        "type": msg.type.value,
                        "election_id": msg.election_id,
                        "algorithm": msg.algorithm.value,
                        "payload": msg.payload,
                        "delivered": False,
                    })
                return False

            try:
                # Step 2: Write
                writer.write(raw.encode("utf-8"))
                await writer.drain()

                # Step 3: Read ACK
                ack_raw = await asyncio.wait_for(reader.readline(), timeout=0.5)
                if not ack_raw:
                    writer.close()
                    await writer.wait_closed()
                    if is_election_msg:
                        self.sent_messages.append({
                            "from": self.node_id,
                            "to": target_id,
                            "type": msg.type.value,
                            "election_id": msg.election_id,
                            "algorithm": msg.algorithm.value,
                            "payload": msg.payload,
                            "delivered": False,
                        })
                    return False

                writer.close()
                await writer.wait_closed()

                if is_election_msg:
                    self.sent_messages.append({
                        "from": self.node_id,
                        "to": target_id,
                        "type": msg.type.value,
                        "election_id": msg.election_id,
                        "algorithm": msg.algorithm.value,
                        "payload": msg.payload,
                        "delivered": True,
                    })

                # Telemetry: delivered successfully
                await self._send_event("MESSAGE_SENT", {
                    "from": self.node_id,
                    "to": target_id,
                    "type": msg.type.value,
                    "election_id": msg.election_id,
                    "algorithm": msg.algorithm.value,
                    "payload": msg.payload,
                    "delivered": True,
                })
                return True
            except Exception as err:
                logger.warning(f"Node {self.node_id}: Write/Read failed to {target_id} (port {target_port}): {err}")
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass
                if is_election_msg:
                    self.sent_messages.append({
                        "from": self.node_id,
                        "to": target_id,
                        "type": msg.type.value,
                        "election_id": msg.election_id,
                        "algorithm": msg.algorithm.value,
                        "payload": msg.payload,
                        "delivered": False,
                    })
                return False
        return False

    async def _broadcast_direct(self, msg: Message, target_ids: List[int]) -> None:
        """Broadcasts a message to multiple targets in parallel."""
        tasks = [self._send_to_node_id(target, msg.model_copy(deep=True)) for target in target_ids]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_heartbeat(self, leader_id: int) -> bool:
        """Sends a HEARTBEAT ping to leader."""
        msg = Message(
            type=MessageType.HEARTBEAT,
            from_node=self.node_id,
            to_node=leader_id,
            algorithm=self.algorithm,
        )
        return await self._send_direct(msg)

    # -------------------------------------------------------------------------
    # State & Election Transitions
    # -------------------------------------------------------------------------

    async def _on_state_change(self, new_status: NodeStatus, new_leader: Optional[int]) -> None:
        if self.status == NodeStatus.DEAD:
            logger.warning(f"Node {self.node_id}: Ignoring state change to {new_status} because node is DEAD!")
            return
        old_status = self.status
        self.status = new_status
        if new_leader is not None:
            self.leader_id = new_leader
            self.heartbeat.reset()

        logger.info(
            f"Node {self.node_id}: State changed -> [bold cyan]{new_status.value}[/], Leader -> [bold yellow]{self.leader_id}[/]"
        )

        event_name = "LEADER_ELECTED" if new_status == NodeStatus.LEADER else "STATE_CHANGED"
        await self._send_event(event_name, {
            "old_status": old_status.value,
            "status": self.status.value,
            "leader_id": self.leader_id,
        })

    async def _on_leader_failed(self) -> None:
        """Triggered by heartbeat detector when leader is unresponsive."""
        logger.warning(f"[bold red]Node {self.node_id}: Detected failure of leader {self.leader_id}![/]")
        self.leader_id = None
        self.heartbeat.reset()
        # Rule R3: Never start an election while already ELECTING.
        if self.status not in (NodeStatus.DEAD, NodeStatus.ELECTING):
            await self.trigger_election()

    async def trigger_election(self) -> None:
        """Initiates an election using current active algorithm."""
        # Rule R3: Never start an election while already ELECTING.
        if self.status in (NodeStatus.DEAD, NodeStatus.ELECTING):
            return

        if self.algorithm == AlgorithmType.BULLY:
            await self.bully.start_election()
        else:
            await self.ring.start_election()

    # -------------------------------------------------------------------------
    # Control Messages (Gateway / Orchestrator API)
    # -------------------------------------------------------------------------

    async def _handle_control(self, data: Dict[str, Any]) -> Dict[str, Any]:
        action = data.get("action")
        logger.info(f"Node {self.node_id}: Received CONTROL action: {action}")

        if action == ControlAction.KILL.value:
            self.status = NodeStatus.DEAD
            self.leader_id = None
            await self.heartbeat.stop()
            self.bully.cancel_timers()
            self.ring.reset()
            await self._send_event("STATE_CHANGED", {"status": NodeStatus.DEAD.value, "leader_id": None})
            return {"status": "ok", "node_id": self.node_id, "state": "DEAD"}

        elif action == ControlAction.REVIVE.value:
            # Rule R7 & User Request: Reviving a node immediately starts an election
            self.status = NodeStatus.FOLLOWER
            self.leader_id = None
            self.ring.reset()
            self.bully.cancel_timers()
            self.heartbeat.reset()
            self.heartbeat.start()
            await self._send_event("STATE_CHANGED", {"status": NodeStatus.FOLLOWER.value, "leader_id": self.leader_id})

            if self.algorithm == AlgorithmType.BULLY:
                logger.info(f"Node {self.node_id}: Revived in Bully mode, initiating takeover election...")
                asyncio.create_task(self.bully.start_election())
            else:
                logger.info(f"Node {self.node_id}: Revived in Ring mode, initiating ring election...")
                asyncio.create_task(self.ring.start_election())

            return {"status": "ok", "node_id": self.node_id, "state": "FOLLOWER"}

        elif action == ControlAction.SET_ALGORITHM.value:
            algo_str = data.get("algorithm", "bully").lower()
            self.algorithm = AlgorithmType(algo_str)
            logger.info(f"Node {self.node_id}: Algorithm switched to {self.algorithm.value}")
            return {"status": "ok", "algorithm": self.algorithm.value}

        elif action == ControlAction.SET_NETWORK.value:
            self.network_delay = float(data.get("delay", 0.0))
            self.drop_rate = float(data.get("drop_rate", 0.0))
            return {"status": "ok", "delay": self.network_delay, "drop_rate": self.drop_rate}

        elif action == ControlAction.MEMBERSHIP.value:
            # Update peer list
            new_peers = data.get("peers", {})
            self.peers = {int(k): int(v) for k, v in new_peers.items()}
            self.peers[self.node_id] = self.port
            logger.info(f"Node {self.node_id}: Membership updated: {self.peers}")
            return {"status": "ok", "peers": self.peers}

        elif action == ControlAction.START_ELECTION.value:
            # If forced, cancel electing check and start fresh
            if self.status != NodeStatus.DEAD:
                if self.algorithm == AlgorithmType.BULLY:
                    asyncio.create_task(self.bully.start_election())
                else:
                    asyncio.create_task(self.ring.start_election())
            return {"status": "ok", "message": "election_triggered"}

        elif action == ControlAction.GET_STATE.value:
            return {
                "id": self.node_id,
                "port": self.port,
                "status": self.status.value,
                "leader_id": self.leader_id,
                "algorithm": self.algorithm.value,
                "current_election_id": self.current_election_id,
                "lamport": self.clock.value,
                "peers": list(self.peers.keys()),
            }

        return {"status": "error", "message": f"unknown action {action}"}

    async def _query_peer_for_leader(self) -> None:
        """In Ring mode, a revived node asks an alive peer for the current leader (Rule R7)."""
        await asyncio.sleep(0.2)
        if self.status == NodeStatus.DEAD:
            return

        other_peers = [pid for pid in self.peers if pid != self.node_id]
        for pid in sorted(other_peers):
            if self.status == NodeStatus.DEAD:
                return
            port = self.peers[pid]
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", port),
                    timeout=0.5,
                )
                req = {"type": MessageType.CONTROL.value, "action": ControlAction.GET_STATE.value}
                writer.write((json.dumps(req) + "\n").encode("utf-8"))
                await writer.drain()
                resp = await asyncio.wait_for(reader.readline(), timeout=0.5)
                writer.close()
                await writer.wait_closed()
                if resp and self.status != NodeStatus.DEAD:
                    state = json.loads(resp.decode("utf-8").strip())
                    lid = state.get("leader_id")
                    if lid and lid != self.node_id:
                        if lid < self.node_id:
                            logger.info(f"Node {self.node_id}: Peer {pid} reported lower leader {lid}. Initiating takeover election.")
                            asyncio.create_task(self.trigger_election())
                            return
                        self.leader_id = lid
                        self.status = NodeStatus.FOLLOWER
                        await self._send_event("STATE_CHANGED", {"status": self.status.value, "leader_id": self.leader_id})
                        logger.info(f"Node {self.node_id}: Learned leader {self.leader_id} from peer {pid}")
                        return
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Gateway Telemetry Dispatcher
    # -------------------------------------------------------------------------

    async def _send_event(self, event_type: str, data: Dict[str, Any]) -> None:
        if not self.gateway_port:
            return

        evt = EventMessage(
            event_type=event_type,
            node_id=self.node_id,
            data=data,
            lamport=self.clock.value,
            ts=time.time(),
        )
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(self.gateway_host, self.gateway_port),
                timeout=0.3,
            )
            writer.write(evt.to_json().encode("utf-8"))
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Sovereign Distributed Node Process")
    parser.add_argument("--id", type=int, required=True, help="Numeric node ID (e.g. 1)")
    parser.add_argument("--port", type=int, required=True, help="Port to listen on (e.g. 9001)")
    parser.add_argument("--peers", type=str, default="{}", help="JSON dictionary of id:port peers")
    parser.add_argument("--algo", type=str, default="bully", choices=["bully", "ring"], help="Election algorithm")
    parser.add_argument("--gateway-port", type=int, default=None, help="Gateway telemetry port")
    parser.add_argument("--ping-interval", type=float, default=1.0, help="Heartbeat ping interval in seconds")
    parser.add_argument("--heartbeat-timeout", type=float, default=2.2, help="Heartbeat timeout in seconds")

    args = parser.parse_args()

    raw_peers = json.loads(args.peers)
    peers = {int(k): int(v) for k, v in raw_peers.items()}

    node = Node(
        node_id=args.id,
        port=args.port,
        peers=peers,
        algorithm=AlgorithmType(args.algo),
        gateway_port=args.gateway_port,
        heartbeat_interval=args.ping_interval,
        heartbeat_timeout=args.heartbeat_timeout,
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(node.start())
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info(f"Node {args.id} exiting upon user request...")
    finally:
        loop.run_until_complete(node.stop())


if __name__ == "__main__":
    main()

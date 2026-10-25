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
        heartbeat_interval: float = 2.0,
        heartbeat_timeout: float = 3.0,
        ok_timeout: float = 1.5,
        coordinator_timeout: float = 4.0,
    ) -> None:
        self.node_id = node_id
        self.port = port
        self.peers = dict(peers)  # {id: port}
        self.peers[self.node_id] = self.port
        self.algorithm = algorithm
        self.gateway_host = gateway_host
        self.gateway_port = gateway_port

        # State
        self.status = NodeStatus.ALIVE
        self.leader_id: Optional[int] = None
        self.clock = LamportClock()

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
            ok_timeout=ok_timeout,
            coordinator_timeout=coordinator_timeout,
        )
        self.ring = RingElection(
            node_id=self.node_id,
            get_peers=lambda: self.peers,
            send_message_to_node=self._send_to_node_id,
            on_state_change=self._on_state_change,
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
                        continue

                    # Otherwise, standard protocol message: acknowledge receipt
                    writer.write(b'{"ack": true}\n')
                    await writer.drain()

                    msg = Message.model_validate(data)
                    await self._process_incoming_message(msg)
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

        # Lamport logical clock update
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

        # Apply network drop
        if self.drop_rate > 0.0 and random.random() < self.drop_rate:
            logger.warning(f"Node {self.node_id}: Dropped outgoing {msg.type} to {target_id}")
            return False

        # Apply network delay
        if self.network_delay > 0.0:
            await asyncio.sleep(self.network_delay)

        target_port = self.peers[target_id]
        msg.lamport = self.clock.tick()
        raw = msg.to_json()

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", target_port),
                timeout=1.0,
            )
            writer.write(raw.encode("utf-8"))
            await writer.drain()

            # Wait for socket-level ACK from peer to confirm node is alive
            ack_raw = await asyncio.wait_for(reader.readline(), timeout=0.5)
            if not ack_raw:
                writer.close()
                await writer.wait_closed()
                return False

            writer.close()
            await writer.wait_closed()

            # Telemetry
            await self._send_event("MESSAGE_SENT", {
                "from": self.node_id,
                "to": target_id,
                "type": msg.type.value,
                "election_id": msg.election_id,
                "algorithm": msg.algorithm.value,
                "payload": msg.payload,
            })
            return True
        except Exception:
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
        await self.trigger_election()

    async def trigger_election(self) -> None:
        """Initiates an election using current active algorithm."""
        if self.status == NodeStatus.DEAD:
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
            self.status = NodeStatus.ALIVE
            self.leader_id = None
            self.ring.reset()
            self.bully.cancel_timers()
            self.heartbeat.reset()
            self.heartbeat.start()
            await self._send_event("STATE_CHANGED", {"status": NodeStatus.ALIVE.value, "leader_id": self.leader_id})

            # In both Bully and Ring modes, a revived node initiates an election to resolve leadership
            # Bully: highest node asserts immediate dominance / takeover (FR-8)
            # Ring: token traverses active ring to discover / elect highest alive node
            logger.info(
                f"Node {self.node_id}: Revived in {self.algorithm.value} mode, initiating election..."
            )
            asyncio.create_task(self.trigger_election())
            return {"status": "ok", "node_id": self.node_id, "state": "ALIVE"}

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
            asyncio.create_task(self.trigger_election())
            return {"status": "ok", "message": "election_triggered"}

        elif action == ControlAction.GET_STATE.value:
            return {
                "id": self.node_id,
                "port": self.port,
                "status": self.status.value,
                "leader_id": self.leader_id,
                "algorithm": self.algorithm.value,
                "lamport": self.clock.value,
                "peers": list(self.peers.keys()),
            }

        return {"status": "error", "message": f"unknown action {action}"}

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
            # Gateway might not be listening yet; node continues running safely
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Sovereign Distributed Node Process")
    parser.add_argument("--id", type=int, required=True, help="Numeric node ID (e.g. 1)")
    parser.add_argument("--port", type=int, required=True, help="Port to listen on (e.g. 9001)")
    parser.add_argument("--peers", type=str, default="{}", help="JSON dictionary of id:port peers")
    parser.add_argument("--algo", type=str, default="bully", choices=["bully", "ring"], help="Election algorithm")
    parser.add_argument("--gateway-port", type=int, default=None, help="Gateway telemetry port")
    parser.add_argument("--ping-interval", type=float, default=2.0, help="Heartbeat ping interval in seconds")
    parser.add_argument("--heartbeat-timeout", type=float, default=3.0, help="Heartbeat timeout in seconds")

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

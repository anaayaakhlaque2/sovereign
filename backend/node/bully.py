"""
Bully Leader Election Algorithm Implementation
Implements Garcia-Molina (1982) specification according to Sovereign rules.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set
from backend.protocol import AlgorithmType, Message, MessageType, NodeStatus

logger = logging.getLogger("sovereign.bully")


class BullyElection:
    def __init__(
        self,
        node_id: int,
        get_peers: Callable[[], Dict[int, int]],  # id -> port
        send_message: Callable[[Message], Coroutine[Any, Any, bool]],
        broadcast_message: Callable[[Message, List[int]], Coroutine[Any, Any, None]],
        on_state_change: Callable[[NodeStatus, Optional[int]], Coroutine[Any, Any, None]],
        get_lamport: Optional[Callable[[], int]] = None,
        ok_timeout: float = 1.0,
        coordinator_timeout: float = 3.0,
    ) -> None:
        self.node_id = node_id
        self.get_peers = get_peers
        self.send_message = send_message
        self.broadcast_message = broadcast_message
        self.on_state_change = on_state_change
        self.get_lamport = get_lamport

        self.ok_timeout = ok_timeout
        self.coordinator_timeout = coordinator_timeout

        self.current_election_id: Optional[str] = None
        self.election_initiator_id: Optional[int] = None
        self._ok_timer_task: Optional[asyncio.Task] = None
        self._coord_timer_task: Optional[asyncio.Task] = None
        self._received_ok: bool = False
        self._counter: int = 0
        self._handled_elections: Set[str] = set()

    def cancel_timers(self) -> None:
        current = asyncio.current_task()
        if self._ok_timer_task and not self._ok_timer_task.done() and self._ok_timer_task is not current:
            self._ok_timer_task.cancel()
        if self._coord_timer_task and not self._coord_timer_task.done() and self._coord_timer_task is not current:
            self._coord_timer_task.cancel()
        self._ok_timer_task = None
        self._coord_timer_task = None

    async def start_election(self, forced_election_id: Optional[str] = None) -> None:
        """Starts a Bully election from this node."""
        self.cancel_timers()
        self._counter += 1
        lamp = self.get_lamport() if self.get_lamport else self._counter
        self.current_election_id = forced_election_id or f"bully-{self.node_id}-{lamp}-{uuid.uuid4().hex[:6]}"
        self._handled_elections.add(self.current_election_id)
        self.election_initiator_id = self.node_id
        self._received_ok = False

        logger.info(f"Node {self.node_id}: Starting Bully election {self.current_election_id}")
        await self.on_state_change(NodeStatus.ELECTING, None)

        peers = self.get_peers()
        higher_nodes = sorted([pid for pid in peers.keys() if pid > self.node_id])

        if not higher_nodes:
            # Highest ID in the cluster: declare leadership immediately!
            logger.info(f"Node {self.node_id}: No higher nodes found. Becoming LEADER!")
            await self._declare_leadership()
            return

        # Send ELECTION message to all higher nodes
        msg = Message(
            type=MessageType.ELECTION,
            from_node=self.node_id,
            to_node=0,  # placeholder
            election_id=self.current_election_id,
            algorithm=AlgorithmType.BULLY,
            payload={"initiator": self.node_id},
        )
        await self.broadcast_message(msg, higher_nodes)

        # Start waiting for OK response
        self._ok_timer_task = asyncio.create_task(self._wait_for_ok())

    async def _wait_for_ok(self) -> None:
        try:
            await asyncio.sleep(self.ok_timeout)
            if not self._received_ok:
                logger.info(f"Node {self.node_id}: OK timeout expired with no responses. Declaring leadership!")
                await self._declare_leadership()
        except asyncio.CancelledError:
            pass

    async def _wait_for_coordinator(self) -> None:
        try:
            await asyncio.sleep(self.coordinator_timeout)
            logger.warning(
                f"Node {self.node_id}: COORDINATOR timeout expired! Higher node may have crashed. Restarting election."
            )
            await self.start_election()
        except asyncio.CancelledError:
            pass

    async def _declare_leadership(self) -> None:
        self.cancel_timers()
        await self.on_state_change(NodeStatus.LEADER, self.node_id)

        # Broadcast COORDINATOR to all other peers
        peers = self.get_peers()
        other_peers = sorted([pid for pid in peers.keys() if pid != self.node_id])

        msg = Message(
            type=MessageType.COORDINATOR,
            from_node=self.node_id,
            to_node=0,
            election_id=self.current_election_id,
            algorithm=AlgorithmType.BULLY,
            payload={"leader": self.node_id},
        )
        await self.broadcast_message(msg, other_peers)
        logger.info(f"Node {self.node_id}: Announced as COORDINATOR to peers {other_peers}")

    async def handle_election_message(self, msg: Message) -> None:
        """Handle incoming ELECTION message."""
        sender = int(msg.from_node)

        # Rule 2: A node receiving ELECTION from a lower id replies OK immediately,
        # then starts its own election (only once per election_id).
        if self.node_id > sender:
            ok_msg = Message(
                type=MessageType.OK,
                from_node=self.node_id,
                to_node=sender,
                election_id=msg.election_id,
                algorithm=AlgorithmType.BULLY,
                payload={},
            )
            await self.send_message(ok_msg)

            # Start own election only once per election_id
            election_id = msg.election_id or f"bully-{self.node_id}-{self._counter}"
            if election_id not in self._handled_elections:
                self._handled_elections.add(election_id)
                await self.start_election(forced_election_id=election_id)

    async def handle_ok_message(self, msg: Message) -> None:
        """Handle incoming OK message from a higher node."""
        logger.info(f"Node {self.node_id}: Received OK from higher node {msg.from_node}")
        self._received_ok = True
        if self._ok_timer_task and not self._ok_timer_task.done():
            self._ok_timer_task.cancel()
            self._ok_timer_task = None

        # Rule 3: If initiator receives at least one OK, it stops and waits T_coord=3.0s
        # for a COORDINATOR message. If none arrives, restart the election.
        if not self._coord_timer_task or self._coord_timer_task.done():
            self._coord_timer_task = asyncio.create_task(self._wait_for_coordinator())

    async def handle_coordinator_message(self, msg: Message) -> None:
        """Handle incoming COORDINATOR message."""
        raw_leader = msg.payload.get("leader", msg.from_node)
        new_leader = int(raw_leader) if raw_leader is not None else int(msg.from_node)

        # Rule 5: A node receiving COORDINATOR from a lower id than itself must reject it
        # and start its own election (a higher node has returned).
        if new_leader < self.node_id:
            logger.warning(
                f"Node {self.node_id}: Received COORDINATOR from lower node {new_leader}! Bullying and initiating takeover election."
            )
            asyncio.create_task(self.start_election())
            return

        logger.info(f"Node {self.node_id}: Acknowledged new COORDINATOR {new_leader}")
        self.cancel_timers()
        self.current_election_id = None
        self.election_initiator_id = None
        # Rule R6: sets leader_id, sets status to FOLLOWER (or LEADER if winner)
        status = NodeStatus.LEADER if new_leader == self.node_id else NodeStatus.FOLLOWER
        await self.on_state_change(status, new_leader)

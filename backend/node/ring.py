"""
Ring Leader Election Algorithm Implementation
Implements FR-6, FR-9, and Section 9 specifications.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Callable, Coroutine, Dict, List, Optional
from backend.protocol import AlgorithmType, Message, MessageType, NodeStatus

logger = logging.getLogger("sovereign.ring")


class RingElection:
    def __init__(
        self,
        node_id: int,
        get_peers: Callable[[], Dict[int, int]],  # id -> port
        send_message_to_node: Callable[[int, Message], Coroutine[Any, Any, bool]],
        on_state_change: Callable[[NodeStatus, Optional[int]], Coroutine[Any, Any, None]],
        election_timeout: float = 3.0,
    ) -> None:
        self.node_id = node_id
        self.get_peers = get_peers
        self.send_message_to_node = send_message_to_node
        self.on_state_change = on_state_change
        self.election_timeout = election_timeout

        self.current_election_id: Optional[str] = None
        self.current_initiator_id: Optional[int] = None
        self._counter: int = 0
        self._active: bool = False
        self._timer_task: Optional[asyncio.Task] = None

    def cancel_timers(self) -> None:
        current = asyncio.current_task()
        if self._timer_task and not self._timer_task.done() and self._timer_task is not current:
            self._timer_task.cancel()
        self._timer_task = None

    def reset(self) -> None:
        """Resets active election state and cancels timers."""
        self.cancel_timers()
        self._active = False
        self.current_election_id = None
        self.current_initiator_id = None

    async def _wait_election_timeout(self) -> None:
        try:
            await asyncio.sleep(self.election_timeout)
            if self._active:
                logger.warning(
                    f"Node {self.node_id}: Ring election {self.current_election_id} timed out. Resetting active state."
                )
                self._active = False
                self.current_election_id = None
                self.current_initiator_id = None
        except asyncio.CancelledError:
            pass

    def get_ring_successors(self) -> List[int]:
        """Returns the circular ordered list of successors for this node."""
        peers = self.get_peers()
        all_ids = sorted(list(peers.keys()))
        if not all_ids or all_ids == [self.node_id]:
            return []

        # Find index of self
        if self.node_id in all_ids:
            idx = all_ids.index(self.node_id)
            # Successors in ring order: after self, wrapping around before self
            return all_ids[idx + 1 :] + all_ids[:idx]
        else:
            return all_ids

    async def forward_around_ring(self, msg: Message) -> bool:
        """Attempts to send message to the next alive neighbor, skipping dead ones."""
        successors = self.get_ring_successors()
        if not successors:
            logger.info(f"Node {self.node_id}: No other peers in ring!")
            return False

        for target in successors:
            msg.to_node = target
            success = await self.send_message_to_node(target, msg)
            if success:
                logger.debug(f"Node {self.node_id}: Forwarded {msg.type} to next ring neighbor {target}")
                return True
            else:
                logger.warning(f"Node {self.node_id}: Ring neighbor {target} unreachable, skipping to next...")

        logger.error(f"Node {self.node_id}: All ring successors unreachable!")
        return False

    async def start_election(self) -> None:
        """Starts a Ring election initiated by this node."""
        self.cancel_timers()
        self._counter += 1
        election_id = f"ring-{self.node_id}-{self._counter}-{uuid.uuid4().hex[:6]}"
        self.current_election_id = election_id
        self.current_initiator_id = self.node_id
        self._active = True
        self._timer_task = asyncio.create_task(self._wait_election_timeout())

        logger.info(f"Node {self.node_id}: Starting Ring election {election_id}")
        await self.on_state_change(NodeStatus.ELECTING, None)

        successors = self.get_ring_successors()
        if not successors:
            # Only node in cluster -> become leader immediately
            logger.info(f"Node {self.node_id}: Alone in ring. Becoming LEADER!")
            await self.on_state_change(NodeStatus.LEADER, self.node_id)
            self.reset()
            return

        msg = Message(
            type=MessageType.RING_ELECTION,
            from_node=self.node_id,
            to_node=0,
            election_id=election_id,
            algorithm=AlgorithmType.RING,
            payload={
                "initiator": self.node_id,
                "alive": [self.node_id],
            },
        )
        sent = await self.forward_around_ring(msg)
        if not sent:
            # If all other nodes are dead, this node is sole survivor and becomes leader
            logger.info(f"Node {self.node_id}: No ring peers responded. Becoming LEADER!")
            await self.on_state_change(NodeStatus.LEADER, self.node_id)
            self.reset()

    async def handle_election_token(self, msg: Message) -> None:
        """Handle incoming RING_ELECTION token."""
        payload = msg.payload
        initiator = payload.get("initiator", msg.from_node)
        alive_nodes: List[int] = payload.get("alive", [])

        # Concurrent election resolution:
        # If we are already participating in an election with a HIGHER initiator ID, drop this one!
        if self._active and self.current_initiator_id is not None:
            if initiator < self.current_initiator_id:
                logger.info(
                    f"Node {self.node_id}: Dropping Ring election from lower initiator {initiator} in favor of {self.current_initiator_id}"
                )
                return

        self.current_election_id = msg.election_id
        self.current_initiator_id = initiator
        self._active = True

        # Has the token completed the circuit and returned to initiator?
        if initiator == self.node_id:
            logger.info(
                f"Node {self.node_id}: Ring election token returned! Alive nodes collected: {alive_nodes}"
            )
            self.cancel_timers()
            # Determine winner: node with highest ID
            if not alive_nodes:
                alive_nodes = [self.node_id]
            winner = max(alive_nodes)
            logger.info(f"Node {self.node_id}: Ring election WINNER is node {winner}")

            # Send RING_COORDINATOR token around the ring
            coord_msg = Message(
                type=MessageType.RING_COORDINATOR,
                from_node=self.node_id,
                to_node=0,
                election_id=msg.election_id,
                algorithm=AlgorithmType.RING,
                payload={
                    "initiator": self.node_id,
                    "leader": winner,
                },
            )
            # Update self state
            status = NodeStatus.LEADER if winner == self.node_id else NodeStatus.ALIVE
            await self.on_state_change(status, winner)

            await self.forward_around_ring(coord_msg)
            self.reset()
            return

        # Not initiator: append self to alive list if not already there and forward
        if self.node_id not in alive_nodes:
            alive_nodes.append(self.node_id)
            payload["alive"] = alive_nodes

        self.cancel_timers()
        self._timer_task = asyncio.create_task(self._wait_election_timeout())
        await self.on_state_change(NodeStatus.ELECTING, None)
        msg.from_node = self.node_id
        await self.forward_around_ring(msg)

    async def handle_coordinator_token(self, msg: Message) -> None:
        """Handle incoming RING_COORDINATOR token."""
        payload = msg.payload
        initiator = payload.get("initiator")
        leader = payload.get("leader")

        logger.info(f"Node {self.node_id}: Received RING_COORDINATOR token with leader {leader}")
        status = NodeStatus.LEADER if leader == self.node_id else NodeStatus.ALIVE
        await self.on_state_change(status, leader)
        self.reset()

        # If we are NOT the original initiator who sent the coordinator token, forward it!
        if initiator != self.node_id:
            msg.from_node = self.node_id
            await self.forward_around_ring(msg)
        else:
            logger.info(f"Node {self.node_id}: RING_COORDINATOR token completed circle. Election complete!")

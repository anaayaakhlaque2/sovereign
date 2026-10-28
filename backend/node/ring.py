"""
Ring Leader Election Algorithm Implementation
Implements Chang-Roberts (1979) collect-list variant according to Sovereign specifications.
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
        get_lamport: Optional[Callable[[], int]] = None,
        token_timeout: Optional[float] = None,
        is_alive: Optional[Callable[[], bool]] = None,
    ) -> None:
        self.node_id = int(node_id)
        self.get_peers = get_peers
        self.send_message_to_node = send_message_to_node
        self.on_state_change = on_state_change
        self.get_lamport = get_lamport
        self.token_timeout = token_timeout
        self.is_alive = is_alive

        self.current_election_id: Optional[str] = None
        self.current_initiator_id: Optional[int] = None
        self.current_election_lamport: int = 0
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

    def get_ring_successors(self) -> List[int]:
        """Returns circular ordered list of successors (ascending order, wrapping from max to min)."""
        peers = self.get_peers()
        all_ids = sorted([int(k) for k in peers.keys()])
        if not all_ids or all_ids == [self.node_id]:
            return []

        if self.node_id in all_ids:
            idx = all_ids.index(self.node_id)
            return all_ids[idx + 1:] + all_ids[:idx]
        return all_ids

    async def forward_around_ring(self, msg: Message) -> bool:
        """Attempts to send message to next alive neighbor, skipping dead ones."""
        successors = self.get_ring_successors()
        if not successors:
            logger.info(f"Node {self.node_id}: No other peers in ring!")
            return False

        for target in successors:
            msg.to_node = int(target)
            success = await self.send_message_to_node(int(target), msg)
            if success:
                logger.debug(f"Node {self.node_id}: Forwarded {msg.type} to next ring neighbor {target}")
                return True
            else:
                logger.warning(f"Node {self.node_id}: Ring neighbor {target} unreachable, skipping to next...")

        logger.error(f"Node {self.node_id}: All ring successors unreachable!")
        return False

    async def _wait_election_timeout(self, timeout: float) -> None:
        try:
            await asyncio.sleep(timeout)
            if self._active and self.current_initiator_id == self.node_id:
                logger.warning(
                    f"Node {self.node_id}: Ring token timed out after {timeout:.1f}s. Restarting with new election_id."
                )
                await self.start_election()
        except asyncio.CancelledError:
            pass

    async def start_election(self) -> None:
        """Starts a Ring election initiated by this node."""
        if self.is_alive and not self.is_alive():
            return
        self.cancel_timers()
        self._counter += 1
        lamp = self.get_lamport() if self.get_lamport else self._counter
        election_id = f"ring-{self.node_id}-{lamp}-{uuid.uuid4().hex[:6]}"
        self.current_election_id = election_id
        self.current_initiator_id = self.node_id
        self.current_election_lamport = lamp
        self._active = True

        peers = self.get_peers()
        ring_size = max(1, len(peers))
        timeout = self.token_timeout if self.token_timeout is not None else (3.0 * ring_size * 0.5)
        self._timer_task = asyncio.create_task(self._wait_election_timeout(timeout))

        logger.info(f"Node {self.node_id}: Starting Ring election {election_id}")
        await self.on_state_change(NodeStatus.ELECTING, None)

        successors = self.get_ring_successors()
        if not successors:
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
                "ids": [self.node_id],
                "alive": [self.node_id],
            },
        )
        sent = await self.forward_around_ring(msg)
        if not sent:
            logger.info(f"Node {self.node_id}: No ring peers responded. Becoming LEADER!")
            await self.on_state_change(NodeStatus.LEADER, self.node_id)
            self.reset()

    async def handle_election_token(self, msg: Message) -> None:
        """Handle incoming RING_ELECTION token."""
        payload = msg.payload
        initiator = int(payload.get("initiator", msg.from_node))
        ids: List[int] = [int(x) for x in payload.get("ids", payload.get("alive", []))]

        # Stale token check (Suspect g)
        if self._active and msg.lamport and self.current_election_lamport:
            if msg.lamport < self.current_election_lamport:
                logger.info(
                    f"Node {self.node_id}: Dropping stale Ring election token (lamport {msg.lamport} < current {self.current_election_lamport})"
                )
                return

        # Rule 5: If two initiators start at once, a node that already joined an election
        # with a HIGHER initiator id drops tokens from a lower initiator.
        if self._active and self.current_initiator_id is not None:
            if initiator < self.current_initiator_id:
                logger.info(
                    f"Node {self.node_id}: Dropping Ring election from lower initiator {initiator} in favor of {self.current_initiator_id}"
                )
                return

        self.current_election_id = msg.election_id
        self.current_initiator_id = initiator
        self.current_election_lamport = max(self.current_election_lamport, msg.lamport)
        self._active = True

        # Rule 4: When the token returns to the initiator (initiator already in ids), the leader is max(ids).
        if initiator == self.node_id and self.node_id in ids:
            logger.info(
                f"Node {self.node_id}: Ring election token returned! Alive ids collected: {ids}"
            )
            self.cancel_timers()
            winner = max(ids) if ids else self.node_id
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
            status = NodeStatus.LEADER if winner == self.node_id else NodeStatus.FOLLOWER
            await self.on_state_change(status, winner)

            await self.forward_around_ring(coord_msg)
            return

        # Not initiator (or initiator first seeing its token before completion):
        # append self to ids if not already there and forward
        if self.node_id not in ids:
            ids.append(self.node_id)
        payload["ids"] = ids
        payload["alive"] = ids

        self.cancel_timers()
        ring_size = max(1, len(self.get_peers()))
        timeout = self.token_timeout if self.token_timeout is not None else (3.0 * ring_size * 0.5)
        self._timer_task = asyncio.create_task(self._wait_election_timeout(timeout))

        await self.on_state_change(NodeStatus.ELECTING, None)
        msg.from_node = self.node_id
        await self.forward_around_ring(msg)

    async def handle_coordinator_token(self, msg: Message) -> None:
        """Handle incoming RING_COORDINATOR token."""
        payload = msg.payload
        initiator = int(payload.get("initiator", msg.from_node))
        raw_leader = payload.get("leader")
        leader = int(raw_leader) if raw_leader is not None else initiator

        # Safeguard: A living node must NEVER accept a leader lower than itself!
        # If an incoming coordinator announces a leader lower than this node,
        # reject it and immediately initiate an election to establish true leadership.
        alive = self.is_alive() if self.is_alive else True
        if alive and leader < self.node_id:
            logger.warning(
                f"Node {self.node_id}: Received RING_COORDINATOR with lower leader {leader}! Rejecting and initiating takeover election."
            )
            asyncio.create_task(self.start_election())
            return

        logger.info(f"Node {self.node_id}: Received RING_COORDINATOR token with leader {leader}")
        status = NodeStatus.LEADER if leader == self.node_id else NodeStatus.FOLLOWER
        await self.on_state_change(status, leader)
        self.cancel_timers()
        self.reset()

        # Rule 4: each node sets leader_id and forwards; it stops when it returns to the initiator.
        if initiator != self.node_id:
            msg.from_node = self.node_id
            await self.forward_around_ring(msg)
        else:
            logger.info(f"Node {self.node_id}: RING_COORDINATOR token completed circle. Election complete!")

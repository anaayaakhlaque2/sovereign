"""
Heartbeat Failure Detector
Implements FR-4: periodic heartbeats to leader, failure detection timeout.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Callable, Coroutine, Optional, Any

logger = logging.getLogger("sovereign.heartbeat")


class HeartbeatDetector:
    def __init__(
        self,
        node_id: int,
        get_leader_id: Callable[[], Optional[int]],
        send_heartbeat: Callable[[int], Coroutine[Any, Any, bool]],
        on_leader_failed: Callable[[], Coroutine[Any, Any, None]],
        ping_interval: float = 1.0,
        timeout: float = 2.2,
    ) -> None:
        self.node_id = node_id
        self.get_leader_id = get_leader_id
        self.send_heartbeat = send_heartbeat
        self.on_leader_failed = on_leader_failed
        self.ping_interval = ping_interval
        self.timeout = timeout

        self._task: Optional[asyncio.Task] = None
        self._running: bool = False
        self._last_ack_time: float = time.time()
        self._waiting_for_ack: bool = False
        self._tracked_leader: Optional[int] = None

    def reset(self) -> None:
        """Resets the heartbeat failure detector timer (e.g., when a new leader is elected)."""
        self._last_ack_time = time.time()
        self._waiting_for_ack = False
        self._tracked_leader = self.get_leader_id()

    def update_config(self, ping_interval: Optional[float] = None, timeout: Optional[float] = None) -> None:
        if ping_interval is not None:
            self.ping_interval = ping_interval
        if timeout is not None:
            self.timeout = timeout

    def record_ack(self, from_id: int) -> None:
        """Called when a HEARTBEAT_ACK is received from the leader."""
        leader = self.get_leader_id()
        if leader == from_id:
            self._last_ack_time = time.time()
            self._waiting_for_ack = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self.reset()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def _loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.ping_interval)
                if not self._running:
                    break

                leader_id = self.get_leader_id()

                # If leader changed since last check, reset timers so we don't penalize the new leader
                if leader_id != self._tracked_leader:
                    self._tracked_leader = leader_id
                    self._last_ack_time = time.time()
                    self._waiting_for_ack = False

                # If no leader or this node is the leader, do not ping
                if leader_id is None or leader_id == self.node_id:
                    continue

                # Check if we timed out waiting for the previous heartbeat
                now = time.time()
                if self._waiting_for_ack and (now - self._last_ack_time > self.timeout):
                    logger.warning(
                        f"Node {self.node_id}: Leader {leader_id} missed heartbeat (last ack {now - self._last_ack_time:.2f}s ago). Declaring failed!"
                    )
                    self._waiting_for_ack = False
                    self._last_ack_time = time.time()
                    # Add random jitter 0 to 300 ms to reduce simultaneous initiators (scaled for unit tests)
                    max_jitter = 0.3 if self.timeout >= 1.0 else (self.timeout * 0.1)
                    await asyncio.sleep(random.uniform(0.0, max_jitter))
                    await self.on_leader_failed()
                    continue

                # Send heartbeat
                self._waiting_for_ack = True
                success = await self.send_heartbeat(leader_id)
                if not success:
                    # Immediate connection failure to leader
                    if time.time() - self._last_ack_time > self.timeout:
                        logger.warning(
                            f"Node {self.node_id}: Cannot connect to leader {leader_id}. Declaring failed!"
                        )
                        self._waiting_for_ack = False
                        self._last_ack_time = time.time()
                        # Add random jitter 0 to 300 ms to reduce simultaneous initiators
                        await asyncio.sleep(random.uniform(0.0, 0.3))
                        await self.on_leader_failed()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Node {self.node_id}: Error in heartbeat loop: {e}", exc_info=True)
                await asyncio.sleep(0.5)

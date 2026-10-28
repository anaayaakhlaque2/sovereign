"""
Cluster Supervisor and Process Manager
Spawns, supervises, scales, and controls independent node OS processes.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional
from backend.config import NODE_COUNT, BASE_PORT, get_node_ports
from backend.protocol import AlgorithmType, ControlAction, NodeStatus

logger = logging.getLogger("sovereign.supervisor")

BASE_NODE_PORT = 9000  # Gateway uses 9000 (telemetry on 9090 or separate), nodes start at 9001


class ClusterSupervisor:
    def __init__(
        self,
        gateway_telemetry_port: int = 9090,
        default_count: int = NODE_COUNT,
        default_algorithm: AlgorithmType = AlgorithmType.BULLY,
    ) -> None:
        self.gateway_telemetry_port = gateway_telemetry_port
        self.current_algorithm = default_algorithm
        self.node_count = default_count

        # Processes: node_id -> Popen
        self.processes: Dict[int, subprocess.Popen] = {}
        # Ports: node_id -> port
        self.node_ports: Dict[int, int] = {}
        # Node states cache: node_id -> {"status": ..., "leader_id": ..., ...}
        self.node_cache: Dict[int, Dict[str, Any]] = {}
        # Cluster leader
        self._current_leader: Optional[int] = None

        # Network simulation settings
        self.simulated_delay: float = 0.0
        self.simulated_drop_rate: float = 0.0

        # Chaos mode task
        self.chaos_running: bool = False
        self._chaos_task: Optional[asyncio.Task] = None

    @property
    def current_leader(self) -> Optional[int]:
        if self._current_leader is not None:
            node_info = self.node_cache.get(self._current_leader)
            if node_info and node_info.get("status") == NodeStatus.DEAD.value:
                self._current_leader = None
        return self._current_leader

    @current_leader.setter
    def current_leader(self, val: Optional[int]) -> None:
        self._current_leader = val

    def _get_port_for_id(self, node_id: int) -> int:
        return BASE_NODE_PORT + node_id

    def build_peers_dict(self) -> Dict[int, int]:
        return {nid: self._get_port_for_id(nid) for nid in self.processes.keys()}

    async def start_cluster(self, count: Optional[int] = None) -> None:
        """Starts N node processes and updates membership."""
        n = count or self.node_count
        self.node_count = max(3, min(9, n))
        logger.info(f"Starting cluster with {self.node_count} nodes (Algorithm: {self.current_algorithm.value})...")

        # Compute ports
        for nid in range(1, self.node_count + 1):
            self.node_ports[nid] = self._get_port_for_id(nid)

        peers_json = json.dumps({str(k): v for k, v in self.node_ports.items()})

        # Spawn each process
        for nid in range(1, self.node_count + 1):
            self._spawn_node_process(nid, peers_json)

        # Allow servers to bind and start
        await asyncio.sleep(1.0)
        logger.info(f"Successfully spawned {len(self.processes)} node processes.")

    def _spawn_node_process(self, node_id: int, peers_json: str) -> None:
        port = self._get_port_for_id(node_id)
        cmd = [
            sys.executable,
            "-m",
            "backend.node.node",
            "--id",
            str(node_id),
            "--port",
            str(port),
            "--peers",
            peers_json,
            "--algo",
            self.current_algorithm.value,
            "--gateway-port",
            str(self.gateway_telemetry_port),
            "--ping-interval",
            "1.0",
            "--heartbeat-timeout",
            "2.2",
        ]

        logger.info(f"Spawning Node {node_id} on port {port}...")
        proc = subprocess.Popen(
            cmd,
            cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.processes[node_id] = proc
        self.node_ports[node_id] = port
        self.node_cache[node_id] = {
            "id": node_id,
            "port": port,
            "status": NodeStatus.FOLLOWER.value,
            "leader_id": self.current_leader,
            "algorithm": self.current_algorithm.value,
        }

    async def send_control(self, node_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Sends a CONTROL message to a specific node over TCP."""
        if node_id not in self.node_ports:
            return None

        port = self.node_ports[node_id]
        payload["type"] = "CONTROL"
        raw = json.dumps(payload) + "\n"

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", port),
                timeout=1.5,
            )
            writer.write(raw.encode("utf-8"))
            await writer.drain()

            reply_line = await asyncio.wait_for(reader.readline(), timeout=1.5)
            writer.close()
            await writer.wait_closed()

            if reply_line:
                return json.loads(reply_line.decode("utf-8").strip())
        except Exception as e:
            logger.warning(f"Failed to send control to Node {node_id} (port {port}): {e}")
        return None

    async def broadcast_control(self, payload: Dict[str, Any]) -> Dict[int, Optional[Dict[str, Any]]]:
        """Sends a CONTROL message to all running nodes concurrently."""
        results = {}
        tasks = [self.send_control(nid, payload) for nid in list(self.processes.keys())]
        replies = await asyncio.gather(*tasks, return_exceptions=True)
        for nid, rep in zip(list(self.processes.keys()), replies):
            results[nid] = rep if isinstance(rep, dict) else None
        return results

    async def get_nodes_internal_state(self) -> Dict[int, Any]:
        """Queries every running node process over TCP for its own internal view."""
        results = {}
        for nid in sorted(list(self.processes.keys())):
            reply = await self.send_control(nid, {"action": ControlAction.GET_STATE.value})
            if reply:
                results[nid] = {
                    "id": reply.get("id", nid),
                    "status": reply.get("status"),
                    "leader_id": reply.get("leader_id"),
                    "algorithm": reply.get("algorithm"),
                    "known_peers": reply.get("peers", []),
                    "election_id": reply.get("current_election_id"),
                    "lamport": reply.get("lamport", 0),
                }
            else:
                cached = self.node_cache.get(nid, {})
                results[nid] = {
                    "id": nid,
                    "status": cached.get("status", "DEAD"),
                    "leader_id": cached.get("leader_id"),
                    "algorithm": cached.get("algorithm", self.current_algorithm.value),
                    "known_peers": list(self.node_ports.keys()),
                    "election_id": None,
                    "lamport": 0,
                }
        return results

    async def kill_node(self, node_id: int) -> bool:
        """Kills a node via CONTROL kill."""
        reply = await self.send_control(node_id, {"action": ControlAction.KILL.value})
        if reply and reply.get("status") == "ok":
            if node_id in self.node_cache:
                self.node_cache[node_id]["status"] = NodeStatus.DEAD.value
                self.node_cache[node_id]["leader_id"] = None
            if self._current_leader == node_id:
                self._current_leader = None

            if hasattr(self, 'telemetry') and self.telemetry:
                await self.telemetry.broadcast_ws({
                    "type": "EVENT",
                    "event_type": "STATE_CHANGED",
                    "node_id": node_id,
                    "data": {"status": NodeStatus.DEAD.value, "leader_id": None},
                    "leader": self.current_leader,
                    "lamport": 0,
                    "ts": time.time(),
                })
            return True
        return False

    async def revive_node(self, node_id: int) -> bool:
        """Revives a node via CONTROL revive."""
        reply = await self.send_control(node_id, {"action": ControlAction.REVIVE.value})
        if reply and reply.get("status") == "ok":
            if node_id in self.node_cache:
                self.node_cache[node_id]["status"] = NodeStatus.FOLLOWER.value
            if hasattr(self, 'telemetry') and self.telemetry:
                await self.telemetry.broadcast_ws({
                    "type": "EVENT",
                    "event_type": "STATE_CHANGED",
                    "node_id": node_id,
                    "data": {"status": NodeStatus.FOLLOWER.value, "leader_id": self.current_leader},
                    "leader": self.current_leader,
                    "lamport": 0,
                    "ts": time.time(),
                })
            return True
        return False

    async def assassinate_leader(self) -> Optional[int]:
        """Finds and kills current cluster leader."""
        # Check cached leader or find from node states
        target = self.current_leader
        if not target:
            # Query nodes to find who they believe is leader
            for nid in self.node_cache:
                lid = self.node_cache[nid].get("leader_id")
                if lid and self.node_cache.get(lid, {}).get("status") != NodeStatus.DEAD.value:
                    target = lid
                    break

        if target:
            logger.warning(f"Assassinating Sovereign Leader Node {target}!")
            await self.kill_node(target)
            return target
        return None

    async def set_algorithm(self, algo: str) -> None:
        """Switches algorithm cluster-wide."""
        algorithm = AlgorithmType(algo.lower())
        self.current_algorithm = algorithm
        await self.broadcast_control({
            "action": ControlAction.SET_ALGORITHM.value,
            "algorithm": algorithm.value,
        })
        for c in self.node_cache.values():
            c["algorithm"] = algorithm.value
        logger.info(f"Switched cluster algorithm to {algorithm.value}")

    async def set_network_params(self, delay: float, drop_rate: float) -> None:
        """Updates simulated network latency and drop rate on all nodes."""
        self.simulated_delay = delay
        self.simulated_drop_rate = drop_rate
        await self.broadcast_control({
            "action": ControlAction.SET_NETWORK.value,
            "delay": delay,
            "drop_rate": drop_rate,
        })

    async def trigger_election(self, initiator_id: Optional[int] = None) -> bool:
        """Triggers an election starting from a specific node or lowest alive node."""
        target = initiator_id
        if target is None:
            alive = [nid for nid, c in self.node_cache.items() if c.get("status") != NodeStatus.DEAD.value]
            target = min(alive) if alive else None

        if target:
            reply = await self.send_control(target, {"action": ControlAction.START_ELECTION.value})
            return bool(reply and reply.get("status") == "ok")
        return False

    # -------------------------------------------------------------------------
    # Chaos Mode
    # -------------------------------------------------------------------------

    def set_chaos(self, enabled: bool) -> None:
        self.chaos_running = enabled
        if enabled:
            if not self._chaos_task or self._chaos_task.done():
                self._chaos_task = asyncio.create_task(self._chaos_loop())
                logger.info("Chaos Mode activated!")
        else:
            if self._chaos_task and not self._chaos_task.done():
                self._chaos_task.cancel()
            self._chaos_task = None
            logger.info("Chaos Mode deactivated.")

    async def _chaos_loop(self) -> None:
        import random

        while self.chaos_running:
            try:
                await asyncio.sleep(random.uniform(4.0, 7.0))
                if not self.chaos_running:
                    break

                all_ids = list(self.node_cache.keys())
                if not all_ids:
                    continue

                target_id = random.choice(all_ids)
                status = self.node_cache[target_id].get("status")

                if status == NodeStatus.DEAD.value:
                    logger.info(f"[Chaos] Reviving Node {target_id}")
                    await self.revive_node(target_id)
                else:
                    logger.info(f"[Chaos] Striking lightning on Node {target_id}!")
                    await self.kill_node(target_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Chaos loop error: {e}")

    # -------------------------------------------------------------------------
    # Shutdown
    # -------------------------------------------------------------------------

    def shutdown_all(self) -> None:
        """Kills all spawned node child processes."""
        self.set_chaos(False)
        logger.info(f"Stopping all {len(self.processes)} child processes...")
        for nid, proc in list(self.processes.items()):
            try:
                proc.terminate()
                proc.wait(timeout=0.5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self.processes.clear()
        logger.info("All node processes stopped.")

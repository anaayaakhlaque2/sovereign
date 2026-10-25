"""
Integration tests for Sovereign cluster.
Spawns real Node instances over real TCP sockets and exercises end-to-end elections.
"""
import asyncio
import pytest
from typing import Dict, List
from backend.node.node import Node
from backend.protocol import AlgorithmType, ControlAction, NodeStatus


@pytest.mark.asyncio
async def test_full_cluster_bully_and_ring_elections():
    # Setup 5 nodes on local ports
    ports = {1: 19101, 2: 19102, 3: 19103, 4: 19104, 5: 19105}
    nodes: Dict[int, Node] = {}

    for nid, port in ports.items():
        node = Node(
            node_id=nid,
            port=port,
            peers=ports,
            algorithm=AlgorithmType.BULLY,
            heartbeat_interval=0.4,
            heartbeat_timeout=1.0,
            ok_timeout=0.3,
            coordinator_timeout=3.0,
        )
        nodes[nid] = node

    # Start all 5 node servers
    for node in nodes.values():
        await node.start()

    try:
        # Step 1: Trigger election from the lowest node (Node 1) in Bully mode
        await nodes[1].trigger_election()

        # Wait up to 4 seconds for election convergence
        for _ in range(40):
            if all(n.leader_id == 5 for n in nodes.values() if n.status != NodeStatus.DEAD):
                break
            await asyncio.sleep(0.1)

        # Allow initial election storm to settle cleanly
        await asyncio.sleep(0.8)

        # Node 5 must be the elected leader on all alive nodes
        for nid, n in nodes.items():
            assert n.leader_id == 5, f"Node {nid} has leader {n.leader_id}, expected 5"
        assert nodes[5].status == NodeStatus.LEADER

        # Step 2: Assassinate the leader (Node 5)
        await nodes[5]._handle_control({"action": ControlAction.KILL.value})
        assert nodes[5].status == NodeStatus.DEAD

        # Heartbeat failure detector or manual trigger will start election
        # Wait up to 5 seconds for failure detection and Node 4 election
        for _ in range(50):
            alive_nodes = [n for n in nodes.values() if n.status != NodeStatus.DEAD]
            if all(n.leader_id == 4 for n in alive_nodes):
                break
            await asyncio.sleep(0.1)

        alive_nodes = [n for n in nodes.values() if n.status != NodeStatus.DEAD]
        for n in alive_nodes:
            assert n.leader_id == 4, f"Alive node {n.node_id} has leader {n.leader_id}, expected 4"
        assert nodes[4].status == NodeStatus.LEADER

        # Settle before revive
        await asyncio.sleep(0.5)

        # Step 3: Revive Node 5 -> Bully takeover (FR-8)
        # Higher node revives and immediately challenges/bullies
        await nodes[5]._handle_control({"action": ControlAction.REVIVE.value})
        for _ in range(50):
            if all(n.leader_id == 5 for n in nodes.values() if n.status != NodeStatus.DEAD):
                break
            await asyncio.sleep(0.1)

        for nid, n in nodes.items():
            assert n.leader_id == 5, f"Node {nid} has leader {n.leader_id}, expected 5 after revive"
        assert nodes[5].status == NodeStatus.LEADER

        # Settle before switching algorithm
        await asyncio.sleep(0.5)

        # Step 4: Switch cluster to Ring mode and run a Ring election
        for n in nodes.values():
            await n._handle_control({"action": ControlAction.SET_ALGORITHM.value, "algorithm": "ring"})
            assert n.algorithm == AlgorithmType.RING

        # Kill Node 5 again
        await nodes[5]._handle_control({"action": ControlAction.KILL.value})

        # Node 1 starts a Ring election
        await nodes[1].trigger_election()

        for _ in range(50):
            alive_nodes = [n for n in nodes.values() if n.status != NodeStatus.DEAD]
            if all(n.leader_id == 4 for n in alive_nodes):
                break
            await asyncio.sleep(0.1)

        alive_nodes = [n for n in nodes.values() if n.status != NodeStatus.DEAD]
        for n in alive_nodes:
            assert n.leader_id == 4, f"Node {n.node_id} leader is {n.leader_id}, expected 4 in Ring mode"
        assert nodes[4].status == NodeStatus.LEADER

    finally:
        # Cleanly stop all node servers
        for node in nodes.values():
            await node.stop()

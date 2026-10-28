"""
Sovereign Scenario Test Suite T1 - T11
Runs real Node OS processes communicating over real TCP sockets.
Parametrized across algorithms (Bully, Ring) and cluster sizes N in [3..9].
Asserts Invariants I1 to I4 after convergence.
"""
from __future__ import annotations

import asyncio
from collections import Counter
import pytest
from typing import Dict, List

from backend.node.node import Node
from backend.protocol import AlgorithmType, ControlAction, NodeStatus


async def make_cluster(
    count: int,
    base_port: int,
    algo: AlgorithmType = AlgorithmType.BULLY,
    heartbeat_interval: float = 0.5,
    heartbeat_timeout: float = 1.2,
    ok_timeout: float = 0.35,
    coordinator_timeout: float = 1.2,
    ring_token_timeout: float = 1.5,
) -> Dict[int, Node]:
    ports = {i: base_port + i for i in range(1, count + 1)}
    nodes: Dict[int, Node] = {}
    for nid, port in ports.items():
        node = Node(
            node_id=nid,
            port=port,
            peers=ports,
            algorithm=algo,
            heartbeat_interval=heartbeat_interval,
            heartbeat_timeout=heartbeat_timeout,
            ok_timeout=ok_timeout,
            coordinator_timeout=coordinator_timeout,
            ring_token_timeout=ring_token_timeout,
        )
        nodes[nid] = node
        await node.start()
    return nodes


async def stop_cluster(nodes: Dict[int, Node]) -> None:
    for node in list(nodes.values()):
        await node.stop()


def assert_invariants_i1_to_i4(nodes: Dict[int, Node], expected_leader: int) -> None:
    """
    Verifies the 4 core distributed invariants:
    I1: exactly one alive node has status LEADER
    I2: that node's id == max(alive ids)
    I3: every alive node's leader_id equals it
    I4: snapshot leader_id (majority agreement) equals it
    """
    alive_nodes = [n for n in nodes.values() if n.status != NodeStatus.DEAD]
    leader_nodes = [n for n in alive_nodes if n.status == NodeStatus.LEADER]

    # I1: exactly one alive node has status LEADER
    assert len(leader_nodes) == 1, (
        f"I1 VIOLATION: Expected exactly 1 leader node, found {len(leader_nodes)}: {[n.node_id for n in leader_nodes]}"
    )

    # I2: that node's id == max(alive ids)
    max_alive_id = max(n.node_id for n in alive_nodes)
    assert leader_nodes[0].node_id == max_alive_id, (
        f"I2 VIOLATION: Leader node {leader_nodes[0].node_id} != max alive id {max_alive_id}"
    )
    assert leader_nodes[0].node_id == expected_leader, (
        f"Leader node is {leader_nodes[0].node_id}, expected {expected_leader}"
    )

    # I3: every alive node's leader_id equals it
    for n in alive_nodes:
        assert n.leader_id == expected_leader, (
            f"I3 VIOLATION: Node {n.node_id} has leader_id={n.leader_id}, expected {expected_leader}"
        )
        if n.node_id != expected_leader:
            assert n.status == NodeStatus.FOLLOWER, (
                f"Node {n.node_id} has status={n.status}, expected FOLLOWER"
            )

    # I4: UI snapshot leader_id equals it (unanimous majority agreement)
    counts = Counter(n.leader_id for n in alive_nodes)
    assert len(counts) == 1 and counts.most_common(1)[0][0] == expected_leader, (
        f"I4 VIOLATION: Snapshot votes not unanimous: {dict(counts)}"
    )


# =============================================================================
# T1: fresh start: leader == N.
# =============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("algo", [AlgorithmType.BULLY, AlgorithmType.RING])
@pytest.mark.parametrize("n", [3, 5, 7, 9])
async def test_t1_fresh_start_leader_equals_n(algo: AlgorithmType, n: int):
    base_port = 23000 + (100 if algo == AlgorithmType.RING else 0) + n * 10
    cluster = await make_cluster(count=n, base_port=base_port, algo=algo)
    try:
        # Lowest node triggers election
        await cluster[1].trigger_election()

        for _ in range(60):
            alive = [node for node in cluster.values() if node.status != NodeStatus.DEAD]
            if all(node.leader_id == n for node in alive) and cluster[n].status == NodeStatus.LEADER:
                break
            await asyncio.sleep(0.08)

        assert_invariants_i1_to_i4(cluster, expected_leader=n)
    finally:
        await stop_cluster(cluster)


# =============================================================================
# T2: crash the leader: new leader == N-1.
# =============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("algo", [AlgorithmType.BULLY, AlgorithmType.RING])
@pytest.mark.parametrize("n", [3, 5, 7, 9])
async def test_t2_crash_leader_new_leader_is_n_minus_1(algo: AlgorithmType, n: int):
    base_port = 23500 + (100 if algo == AlgorithmType.RING else 0) + n * 10
    cluster = await make_cluster(count=n, base_port=base_port, algo=algo)
    try:
        # Crash leader N
        await cluster[n]._handle_control({"action": ControlAction.KILL.value})
        assert cluster[n].status == NodeStatus.DEAD

        # Node 1 starts election
        await cluster[1].trigger_election()

        expected = n - 1
        for _ in range(60):
            alive = [node for node in cluster.values() if node.status != NodeStatus.DEAD]
            if all(node.leader_id == expected for node in alive) and cluster[expected].status == NodeStatus.LEADER:
                break
            await asyncio.sleep(0.08)

        assert_invariants_i1_to_i4(cluster, expected_leader=expected)
    finally:
        await stop_cluster(cluster)


# =============================================================================
# T3: crash N then N-1 then N-2: leaders N-1, N-2, N-3.
# =============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("algo", [AlgorithmType.BULLY, AlgorithmType.RING])
async def test_t3_cascade_crashes(algo: AlgorithmType):
    base_port = 24000 + (100 if algo == AlgorithmType.RING else 0)
    cluster = await make_cluster(count=5, base_port=base_port, algo=algo)
    try:
        # Step 1: Kill 5 -> leader 4
        await cluster[5]._handle_control({"action": ControlAction.KILL.value})
        await cluster[1].trigger_election()
        for _ in range(50):
            alive = [node for node in cluster.values() if node.status != NodeStatus.DEAD]
            if (
                all(node.leader_id == 4 for node in alive)
                and cluster[4].status == NodeStatus.LEADER
                and all(node.status != NodeStatus.ELECTING for node in alive)
            ):
                break
            await asyncio.sleep(0.08)
        assert_invariants_i1_to_i4(cluster, expected_leader=4)

        # Step 2: Kill 4 -> leader 3
        await cluster[4]._handle_control({"action": ControlAction.KILL.value})
        await cluster[1].trigger_election()
        for _ in range(50):
            alive = [node for node in cluster.values() if node.status != NodeStatus.DEAD]
            if all(node.leader_id == 3 for node in alive) and cluster[3].status == NodeStatus.LEADER:
                break
            await asyncio.sleep(0.08)
        assert_invariants_i1_to_i4(cluster, expected_leader=3)

        # Step 3: Kill 3 -> leader 2
        await cluster[3]._handle_control({"action": ControlAction.KILL.value})
        await cluster[1].trigger_election()
        for _ in range(50):
            alive = [node for node in cluster.values() if node.status != NodeStatus.DEAD]
            if all(node.leader_id == 2 for node in alive) and cluster[2].status == NodeStatus.LEADER:
                break
            await asyncio.sleep(0.08)
        assert_invariants_i1_to_i4(cluster, expected_leader=2)
    finally:
        await stop_cluster(cluster)


# =============================================================================
# T4: crash a non-leader: leader unchanged.
# =============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("algo", [AlgorithmType.BULLY, AlgorithmType.RING])
async def test_t4_crash_non_leader_leader_unchanged(algo: AlgorithmType):
    base_port = 24200 + (100 if algo == AlgorithmType.RING else 0)
    cluster = await make_cluster(count=5, base_port=base_port, algo=algo)
    try:
        # Establish leader 5
        await cluster[5]._on_state_change(NodeStatus.LEADER, 5)
        for nid in range(1, 5):
            await cluster[nid]._on_state_change(NodeStatus.FOLLOWER, 5)

        # Crash non-leader 2
        await cluster[2]._handle_control({"action": ControlAction.KILL.value})
        assert cluster[2].status == NodeStatus.DEAD

        # Node 1 triggers election
        await cluster[1].trigger_election()
        for _ in range(60):
            alive = [node for node in cluster.values() if node.status != NodeStatus.DEAD]
            if (
                all(node.leader_id == 5 and node.status != NodeStatus.ELECTING for node in alive)
                and cluster[5].status == NodeStatus.LEADER
            ):
                break
            await asyncio.sleep(0.08)

        # Leader MUST remain 5!
        assert_invariants_i1_to_i4(cluster, expected_leader=5)
    finally:
        await stop_cluster(cluster)


# =============================================================================
# T5: crash leader and node 1 at same time: leader == N-1.
# =============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("algo", [AlgorithmType.BULLY, AlgorithmType.RING])
async def test_t5_crash_leader_and_node_1_simultaneously(algo: AlgorithmType):
    base_port = 24400 + (100 if algo == AlgorithmType.RING else 0)
    cluster = await make_cluster(count=5, base_port=base_port, algo=algo)
    try:
        # Crash 5 and 1 simultaneously
        await asyncio.gather(
            cluster[5]._handle_control({"action": ControlAction.KILL.value}),
            cluster[1]._handle_control({"action": ControlAction.KILL.value}),
        )

        # Node 2 starts election
        await cluster[2].trigger_election()

        for _ in range(50):
            alive = [node for node in cluster.values() if node.status != NodeStatus.DEAD]
            if (
                all(node.leader_id == 4 for node in alive)
                and cluster[4].status == NodeStatus.LEADER
                and all(node.status != NodeStatus.ELECTING for node in alive)
            ):
                break
            await asyncio.sleep(0.08)

        assert_invariants_i1_to_i4(cluster, expected_leader=4)
    finally:
        await stop_cluster(cluster)


# =============================================================================
# T6: two initiators at once: still one leader.
# =============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("algo", [AlgorithmType.BULLY, AlgorithmType.RING])
async def test_t6_two_initiators_at_once_converges_to_single_leader(algo: AlgorithmType):
    base_port = 24600 + (100 if algo == AlgorithmType.RING else 0)
    cluster = await make_cluster(count=5, base_port=base_port, algo=algo)
    try:
        # Crash node 5
        await cluster[5]._handle_control({"action": ControlAction.KILL.value})

        # Nodes 1 and 2 start simultaneously
        await asyncio.gather(
            cluster[1].trigger_election(),
            cluster[2].trigger_election(),
        )

        for _ in range(60):
            alive = [node for node in cluster.values() if node.status != NodeStatus.DEAD]
            if (
                all(node.leader_id == 4 for node in alive)
                and cluster[4].status == NodeStatus.LEADER
                and all(node.status != NodeStatus.ELECTING for node in alive)
            ):
                break
            await asyncio.sleep(0.08)

        assert_invariants_i1_to_i4(cluster, expected_leader=4)
    finally:
        await stop_cluster(cluster)


# =============================================================================
# T7: leader crashes during an election: restarts, one leader.
# =============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("algo", [AlgorithmType.BULLY, AlgorithmType.RING])
async def test_t7_leader_crashes_during_election(algo: AlgorithmType):
    base_port = 24800 + (100 if algo == AlgorithmType.RING else 0)
    cluster = await make_cluster(count=5, base_port=base_port, algo=algo)
    try:
        # Node 5 is dead initially
        await cluster[5]._handle_control({"action": ControlAction.KILL.value})

        # Node 1 starts election
        await cluster[1].trigger_election()
        await asyncio.sleep(0.1)

        # Mid-election, crash node 4!
        await cluster[4]._handle_control({"action": ControlAction.KILL.value})

        # Failure recovery or timeout converges to node 3
        for _ in range(60):
            alive = [node for node in cluster.values() if node.status != NodeStatus.DEAD]
            if all(node.leader_id == 3 for node in alive) and cluster[3].status == NodeStatus.LEADER:
                break
            await asyncio.sleep(0.1)

        assert_invariants_i1_to_i4(cluster, expected_leader=3)
    finally:
        await stop_cluster(cluster)


# =============================================================================
# T8: revive N after crashing it: Bully -> N leads again; Ring -> after Hold Election N leads.
# =============================================================================
@pytest.mark.asyncio
async def test_t8_revive_n_after_crashing():
    # --- Part A: Bully ---
    b_cluster = await make_cluster(count=5, base_port=25000, algo=AlgorithmType.BULLY)
    try:
        # Crash 5, node 4 takes leadership
        await b_cluster[5]._handle_control({"action": ControlAction.KILL.value})
        await b_cluster[1].trigger_election()
        for _ in range(50):
            if b_cluster[4].status == NodeStatus.LEADER and b_cluster[1].leader_id == 4:
                break
            await asyncio.sleep(0.08)
        assert b_cluster[4].status == NodeStatus.LEADER

        # Revive 5: Bully -> takes over immediately (Rule R7)
        await b_cluster[5]._handle_control({"action": ControlAction.REVIVE.value})
        for _ in range(50):
            alive = [node for node in b_cluster.values() if node.status != NodeStatus.DEAD]
            if all(node.leader_id == 5 for node in alive) and b_cluster[5].status == NodeStatus.LEADER:
                break
            await asyncio.sleep(0.08)
        assert_invariants_i1_to_i4(b_cluster, expected_leader=5)
    finally:
        await stop_cluster(b_cluster)

    # --- Part B: Ring ---
    r_cluster = await make_cluster(count=5, base_port=25100, algo=AlgorithmType.RING)
    try:
        # Crash 5, node 4 takes leadership
        await r_cluster[5]._handle_control({"action": ControlAction.KILL.value})
        await r_cluster[1].trigger_election()
        for _ in range(50):
            if r_cluster[4].status == NodeStatus.LEADER and r_cluster[1].leader_id == 4:
                break
            await asyncio.sleep(0.08)
        assert r_cluster[4].status == NodeStatus.LEADER

        # Revive 5: Ring -> rejoins ring quietly, does not interrupt
        await r_cluster[5]._handle_control({"action": ControlAction.REVIVE.value})
        await asyncio.sleep(0.3)

        # Trigger Hold Election -> Node 5 is elected!
        await r_cluster[1].trigger_election()
        for _ in range(50):
            alive = [node for node in r_cluster.values() if node.status != NodeStatus.DEAD]
            if (
                all(node.leader_id == 5 for node in alive)
                and r_cluster[5].status == NodeStatus.LEADER
                and all(node.status != NodeStatus.ELECTING for node in alive)
            ):
                break
            await asyncio.sleep(0.08)
        assert_invariants_i1_to_i4(r_cluster, expected_leader=5)
    finally:
        await stop_cluster(r_cluster)


# =============================================================================
# T9: crash everything except node 1: node 1 is leader (no deadlock).
# =============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("algo", [AlgorithmType.BULLY, AlgorithmType.RING])
async def test_t9_crash_all_except_node_1(algo: AlgorithmType):
    base_port = 25200 + (100 if algo == AlgorithmType.RING else 0)
    cluster = await make_cluster(count=5, base_port=base_port, algo=algo, ok_timeout=0.25)
    try:
        # Kill nodes 2, 3, 4, 5
        for nid in [2, 3, 4, 5]:
            await cluster[nid]._handle_control({"action": ControlAction.KILL.value})

        # Node 1 starts election
        await cluster[1].trigger_election()

        for _ in range(40):
            if cluster[1].status == NodeStatus.LEADER and cluster[1].leader_id == 1:
                break
            await asyncio.sleep(0.08)

        assert_invariants_i1_to_i4(cluster, expected_leader=1)
    finally:
        await stop_cluster(cluster)


# =============================================================================
# T10: latency 500 ms and 20% drop: still converges, one leader.
# =============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize("algo", [AlgorithmType.BULLY, AlgorithmType.RING])
async def test_t10_latency_and_packet_drop_converges(algo: AlgorithmType):
    base_port = 25400 + (100 if algo == AlgorithmType.RING else 0)
    cluster = await make_cluster(count=4, base_port=base_port, algo=algo, ok_timeout=0.6, coordinator_timeout=2.0)
    try:
        # Inject 100ms latency and 20% packet drop
        for node in cluster.values():
            node.network_delay = 0.05
            node.drop_rate = 0.20

        # Trigger election
        await cluster[1].trigger_election()

        for _ in range(80):
            alive = [node for node in cluster.values() if node.status != NodeStatus.DEAD]
            if (
                all(node.leader_id == 4 for node in alive)
                and cluster[4].status == NodeStatus.LEADER
                and all(node.status != NodeStatus.ELECTING for node in alive)
            ):
                break
            await asyncio.sleep(0.1)

        assert_invariants_i1_to_i4(cluster, expected_leader=4)
    finally:
        await stop_cluster(cluster)


# =============================================================================
# T11: message counts, N=5, leader crashed, node 1 only initiator.
# Bully delivered = 15 (ELECTION 6, OK 6, COORDINATOR 3)
# Ring delivered = 8 (4 RING_ELECTION + 4 RING_COORDINATOR)
# =============================================================================
@pytest.mark.asyncio
async def test_t11_exact_message_counts():
    # --- Part A: BULLY ---
    b_cluster = await make_cluster(
        count=5,
        base_port=25600,
        algo=AlgorithmType.BULLY,
        heartbeat_interval=100.0,
        heartbeat_timeout=100.0,
        ok_timeout=0.5,
        coordinator_timeout=2.0,
    )
    try:
        # Crash node 5
        await b_cluster[5]._handle_control({"action": ControlAction.KILL.value})
        for n in b_cluster.values():
            n.sent_messages.clear()

        # Node 1 is the ONLY initiator
        await b_cluster[1].bully.start_election()

        for _ in range(50):
            alive = [n for n in b_cluster.values() if n.status != NodeStatus.DEAD]
            if all(n.leader_id == 4 for n in alive) and b_cluster[4].status == NodeStatus.LEADER:
                break
            await asyncio.sleep(0.1)

        # Allow TCP connection timeout to dead node 5 (1.0s) to record
        await asyncio.sleep(1.3)
        assert_invariants_i1_to_i4(b_cluster, expected_leader=4)

        all_sent = []
        for n in b_cluster.values():
            all_sent.extend(n.sent_messages)

        delivered_election = [m for m in all_sent if m["type"] == "ELECTION" and m["delivered"]]
        delivered_ok = [m for m in all_sent if m["type"] == "OK" and m["delivered"]]
        delivered_coord = [m for m in all_sent if m["type"] == "COORDINATOR" and m["delivered"]]
        failed_attempts_to_5 = [m for m in all_sent if m["to"] == 5 and not m["delivered"]]

        assert len(delivered_election) == 6, f"Expected 6 delivered ELECTION, got {len(delivered_election)}"
        assert len(delivered_ok) == 6, f"Expected 6 delivered OK, got {len(delivered_ok)}"
        assert len(delivered_coord) == 3, f"Expected 3 delivered COORDINATOR, got {len(delivered_coord)}"
        assert len(delivered_election) + len(delivered_ok) + len(delivered_coord) == 15

        # Attempts to dead node 5: 4 ELECTION + 1 COORDINATOR = 5
        election_to_5 = [m for m in failed_attempts_to_5 if m["type"] == "ELECTION"]
        coord_to_5 = [m for m in failed_attempts_to_5 if m["type"] == "COORDINATOR"]
        assert len(election_to_5) == 4, f"Expected 4 ELECTION attempts to dead node 5, got {len(election_to_5)}"
        assert len(coord_to_5) == 1, f"Expected 1 COORDINATOR attempt to dead node 5, got {len(coord_to_5)}"
        assert len(failed_attempts_to_5) == 5
    finally:
        await stop_cluster(b_cluster)

    # --- Part B: RING ---
    r_cluster = await make_cluster(
        count=5,
        base_port=25700,
        algo=AlgorithmType.RING,
        heartbeat_interval=100.0,
        heartbeat_timeout=100.0,
    )
    try:
        # Crash node 5
        await r_cluster[5]._handle_control({"action": ControlAction.KILL.value})
        for n in r_cluster.values():
            n.sent_messages.clear()

        # Node 1 is the ONLY initiator
        await r_cluster[1].ring.start_election()

        for _ in range(50):
            alive = [n for n in r_cluster.values() if n.status != NodeStatus.DEAD]
            if all(n.leader_id == 4 for n in alive) and r_cluster[4].status == NodeStatus.LEADER:
                break
            await asyncio.sleep(0.1)

        await asyncio.sleep(1.3)
        assert_invariants_i1_to_i4(r_cluster, expected_leader=4)

        all_sent_ring = []
        for n in r_cluster.values():
            all_sent_ring.extend(n.sent_messages)

        delivered_ring_elec = [m for m in all_sent_ring if m["type"] == "RING_ELECTION" and m["delivered"]]
        delivered_ring_coord = [m for m in all_sent_ring if m["type"] == "RING_COORDINATOR" and m["delivered"]]
        failed_to_5 = [m for m in all_sent_ring if m["to"] == 5 and not m["delivered"]]

        assert len(delivered_ring_elec) == 4, f"Expected 4 RING_ELECTION hops, got {len(delivered_ring_elec)}"
        assert len(delivered_ring_coord) == 4, f"Expected 4 RING_COORDINATOR hops, got {len(delivered_ring_coord)}"
        assert len(delivered_ring_elec) + len(delivered_ring_coord) == 8
        assert len(failed_to_5) >= 1, f"Expected at least 1 failed attempt to dead node 5, got {len(failed_to_5)}"
    finally:
        await stop_cluster(r_cluster)
